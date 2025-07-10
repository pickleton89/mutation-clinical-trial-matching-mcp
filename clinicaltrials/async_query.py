"""
Async functions to query clinicaltrials.gov for trials matching a mutation.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, cast
import requests
from requests import exceptions as requests_exceptions
from concurrent.futures import ThreadPoolExecutor
from utils.retry import async_exponential_backoff_retry
from utils.circuit_breaker import async_circuit_breaker
from utils.metrics import timer, increment, histogram, gauge
from utils.response_validation import response_validator
from clinicaltrials.config import get_global_config

logger = logging.getLogger(__name__)

# Global thread pool executor for async requests
_executor: Optional[ThreadPoolExecutor] = None

def get_executor() -> ThreadPoolExecutor:
    """Get or create the global thread pool executor."""
    global _executor
    if _executor is None:
        config = get_global_config()
        _executor = ThreadPoolExecutor(max_workers=config.http_max_connections)
    return cast(ThreadPoolExecutor, _executor)

async def close_executor():
    """Close the global thread pool executor."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None

@response_validator("clinical_trials_api")
async def _async_query_clinical_trials_with_retry(
    mutation: str, 
    min_rank: int = 1, 
    max_rank: int = 10, 
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Query clinical trials with async retry logic and circuit breaker applied.
    """
    config = get_global_config()
    
    @async_circuit_breaker(
        name="clinicaltrials_api_async",
        failure_threshold=config.circuit_breaker_failure_threshold,
        recovery_timeout=config.circuit_breaker_recovery_timeout
    )
    @async_exponential_backoff_retry(
        max_retries=config.max_retries,
        initial_delay=config.retry_initial_delay,
        backoff_factor=config.retry_backoff_factor,
        max_delay=config.retry_max_delay,
        jitter=config.retry_jitter,
        retry_on_status_codes=(429, 500, 502, 503, 504)
    )
    async def _retry_wrapper():
        return await _async_query_clinical_trials_impl(mutation, min_rank, max_rank, timeout)
    
    return await _retry_wrapper()

def _sync_query_clinical_trials_impl(
    mutation: str, 
    min_rank: int = 1, 
    max_rank: int = 10, 
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Synchronous implementation of clinical trials query using requests library.
    """
    # Prepare request
    config = get_global_config()
    base_url = config.clinicaltrials_api_url
    params = {
        "format": "json",
        "query.term": mutation,
        "pageSize": max_rank - min_rank + 1
    }
    
    headers = {
        "Accept": "application/json",
        "User-Agent": config.user_agent
    }
    
    try:
        start_time = time.time()
        
        logger.info(f"Querying clinicaltrials.gov for mutation: {mutation}", extra={
            "mutation": mutation,
            "min_rank": min_rank,
            "max_rank": max_rank,
            "timeout": timeout,
            "action": "api_request_start"
        })
        
        response = requests.get(base_url, params=params, headers=headers, timeout=timeout)
        request_duration = time.time() - start_time
        
        # Check for non-200 status codes
        if response.status_code != 200:
            logger.error(f"API Error (Status {response.status_code}): {response.text}", extra={
                "mutation": mutation,
                "status_code": response.status_code,
                "request_duration": request_duration,
                "action": "api_request_error"
            })
            return {"error": f"API Error (Status {response.status_code})", "studies": []}
        
        # Try to parse JSON
        try:
            result = response.json()
            study_count = len(result.get("studies", []))
            
            logger.info(f"Found {study_count} studies for mutation {mutation} in {request_duration:.2f}s", extra={
                "mutation": mutation,
                "study_count": study_count,
                "request_duration": request_duration,
                "action": "api_request_success"
            })
            return result
            
        except ValueError as json_err:
            logger.error(f"JSON parsing error: {json_err}", extra={
                "mutation": mutation,
                "request_duration": request_duration,
                "json_error": str(json_err),
                "action": "json_parse_error"
            })
            logger.debug("Response content: %s", response.text[:500] + "..." if len(response.text) > 500 else response.text)
            return {"error": f"Failed to parse API response: {json_err}", "studies": []}
            
    except requests_exceptions.Timeout:
        request_duration = time.time() - start_time
        logger.error(f"Timeout ({timeout}s) when querying clinicaltrials.gov", extra={
            "mutation": mutation,
            "timeout": timeout,
            "request_duration": request_duration,
            "action": "api_request_timeout"
        })
        return {"error": "The request to clinicaltrials.gov timed out", "studies": []}
        
    except requests_exceptions.ConnectionError as e:
        request_duration = time.time() - start_time
        logger.error(f"Connection error: {e}", extra={
            "mutation": mutation,
            "request_duration": request_duration,
            "error": str(e),
            "action": "api_request_connection_error"
        })
        return {"error": "Failed to connect to clinicaltrials.gov", "studies": []}
        
    except requests_exceptions.RequestException as e:
        request_duration = time.time() - start_time
        logger.error(f"Request error: {e}", extra={
            "mutation": mutation,
            "request_duration": request_duration,
            "error": str(e),
            "action": "api_request_error"
        })
        return {"error": f"Error querying clinicaltrials.gov: {e}", "studies": []}

async def _async_query_clinical_trials_impl(
    mutation: str, 
    min_rank: int = 1, 
    max_rank: int = 10, 
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Internal async implementation of clinical trials query with metrics collection.
    """
    # Track API call metrics
    increment("clinicaltrials_api_calls_total_async", tags={"mutation": mutation})
    
    # Input validation
    if not mutation or not isinstance(mutation, str) or len(mutation.strip()) == 0:
        logger.error("Error: Mutation must be a non-empty string")
        increment("clinicaltrials_api_validation_errors_async", tags={"error_type": "invalid_mutation"})
        return {"error": "Mutation must be a non-empty string", "studies": []}
    
    if not isinstance(min_rank, int) or min_rank < 1:
        logger.warning(f"Invalid min_rank {min_rank}. Setting to 1.")
        increment("clinicaltrials_api_validation_warnings_async", tags={"warning_type": "invalid_min_rank"})
        min_rank = 1
    
    if not isinstance(max_rank, int) or max_rank < min_rank:
        logger.warning(f"Invalid max_rank {max_rank}. Setting to {min_rank + 9}.")
        increment("clinicaltrials_api_validation_warnings_async", tags={"warning_type": "invalid_max_rank"})
        max_rank = min_rank + 9
    
    with timer("clinicaltrials_api_request_async", tags={"mutation": mutation}):
        try:
            # Run the synchronous function in a thread pool
            executor = get_executor()
            result = await asyncio.get_event_loop().run_in_executor(
                executor, 
                _sync_query_clinical_trials_impl,
                mutation, min_rank, max_rank, timeout
            )
            
            # Record success metrics
            if "error" not in result:
                study_count = len(result.get("studies", []))
                increment("clinicaltrials_api_success_async", tags={"mutation": mutation})
                histogram("clinicaltrials_api_study_count_async", study_count, tags={"mutation": mutation})
                gauge("clinicaltrials_api_last_study_count_async", study_count)
            else:
                increment("clinicaltrials_api_errors_async", tags={"error_type": "api_error"})
                
            return result
            
        except Exception as e:
            increment("clinicaltrials_api_errors_async", tags={"error_type": "unexpected_error"})
            logger.error(f"Unexpected error in async query: {e}", extra={
                "mutation": mutation,
                "error": str(e),
                "action": "async_api_request_error"
            })
            return {"error": f"Unexpected error: {str(e)}", "studies": []}

async def query_clinical_trials_async(
    mutation: str, 
    min_rank: int = 1, 
    max_rank: int = 10, 
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Async version of query_clinical_trials.
    
    Query clinicaltrials.gov for clinical trials related to a given mutation.

    Args:
        mutation (str): The mutation or keyword to search for (e.g., 'EGFR L858R').
        min_rank (int): The minimum rank of results to return (default: 1).
        max_rank (int): The maximum rank of results to return (default: 10).
        timeout (int): Timeout for the HTTP request in seconds (default: 10).

    Returns:
        Dict[str, Any]: Parsed JSON response from clinicaltrials.gov, or error dictionary 
                       with 'error' and 'studies' keys if an error occurred.
    """
    return await _async_query_clinical_trials_with_retry(mutation, min_rank, max_rank, timeout)

async def query_multiple_mutations_async(
    mutations: List[str], 
    min_rank: int = 1, 
    max_rank: int = 10, 
    timeout: int = 10,
    max_concurrent: int = 5
) -> Dict[str, Dict[str, Any]]:
    """
    Query multiple mutations concurrently for improved performance.
    
    Args:
        mutations (List[str]): List of mutations to query for.
        min_rank (int): The minimum rank of results to return (default: 1).
        max_rank (int): The maximum rank of results to return (default: 10).
        timeout (int): Timeout for each HTTP request in seconds (default: 10).
        max_concurrent (int): Maximum number of concurrent requests (default: 5).
    
    Returns:
        Dict[str, Dict[str, Any]]: Dictionary mapping mutation names to their results.
    """
    # Track batch query metrics
    increment("clinicaltrials_api_batch_queries", tags={"batch_size": str(len(mutations))})
    
    # Use semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _query_with_semaphore(mutation: str) -> tuple[str, Dict[str, Any]]:
        async with semaphore:
            result = await query_clinical_trials_async(mutation, min_rank, max_rank, timeout)
            return mutation, result
    
    # Execute all queries concurrently
    start_time = time.time()
    logger.info(f"Starting batch async query for {len(mutations)} mutations", extra={
        "mutations": mutations,
        "batch_size": len(mutations),
        "max_concurrent": max_concurrent,
        "action": "batch_query_start"
    })
    
    tasks = [_query_with_semaphore(mutation) for mutation in mutations]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    batch_duration = time.time() - start_time
    histogram("clinicaltrials_api_batch_duration", batch_duration, tags={"batch_size": str(len(mutations))})
    gauge("clinicaltrials_api_last_batch_duration", batch_duration)
    
    # Process results and handle exceptions
    mutation_results = {}
    successful_queries = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch query exception: {result}", extra={
                "batch_size": len(mutations),
                "error": str(result),
                "action": "batch_query_exception"
            })
            increment("clinicaltrials_api_batch_errors", tags={"error_type": "exception"})
            continue
        
        mutation, query_result = result
        mutation_results[mutation] = query_result
        
        # Count successful queries (those without error key)
        if "error" not in query_result:
            successful_queries += 1
    
    # Record batch success metrics
    histogram("clinicaltrials_api_batch_success_count", successful_queries, tags={"batch_size": str(len(mutations))})
    gauge("clinicaltrials_api_last_batch_success_rate", successful_queries / len(mutations) if mutations else 0)
    
    logger.info(f"Batch async query completed: {successful_queries}/{len(mutations)} successful in {batch_duration:.2f}s", extra={
        "mutations": mutations,
        "batch_size": len(mutations),
        "successful_queries": successful_queries,
        "batch_duration": batch_duration,
        "action": "batch_query_complete"
    })
    
    return mutation_results