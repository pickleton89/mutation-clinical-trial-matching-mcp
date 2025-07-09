"""
Functions to query clinicaltrials.gov for trials matching a mutation.
"""

import logging
import requests
import time
from functools import lru_cache
from typing import Dict, Any
from utils.retry import exponential_backoff_retry
from clinicaltrials.config import get_global_config

logger = logging.getLogger(__name__)

# Create a session for connection reuse
_session = requests.Session()

def _initialize_session():
    """Initialize session with configuration-based headers."""
    try:
        config = get_global_config()
        _session.headers.update({
            "Accept": "application/json",
            "User-Agent": config.user_agent
        })
    except ValueError:
        # Handle missing configuration gracefully (useful for tests)
        _session.headers.update({
            "Accept": "application/json",
            "User-Agent": "mutation-clinical-trial-matching-mcp/0.1.0 (Clinical Trials MCP Server)"
        })

# Initialize session headers
_initialize_session()

@lru_cache(maxsize=100)
def _query_clinical_trials_cached(mutation: str, min_rank: int = 1, max_rank: int = 10) -> Dict[str, Any]:
    """
    Internal cached version of query_clinical_trials without timeout parameter.
    """
    return _query_clinical_trials_with_retry(mutation, min_rank, max_rank, 10)

def _query_clinical_trials_with_retry(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> Dict[str, Any]:
    """
    Query clinical trials with retry logic applied.
    """
    config = get_global_config()
    
    @exponential_backoff_retry(
        max_retries=config.max_retries,
        initial_delay=config.retry_initial_delay,
        backoff_factor=config.retry_backoff_factor,
        max_delay=config.retry_max_delay,
        jitter=config.retry_jitter,
        retry_on_status_codes=(429, 500, 502, 503, 504)
    )
    def _retry_wrapper():
        return _query_clinical_trials_impl(mutation, min_rank, max_rank, timeout)
    
    return _retry_wrapper()

def _query_clinical_trials_impl(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> Dict[str, Any]:
    """
    Internal implementation of clinical trials query.
    """
    # Input validation
    if not mutation or not isinstance(mutation, str) or len(mutation.strip()) == 0:
        logger.error("Error: Mutation must be a non-empty string")
        return {"error": "Mutation must be a non-empty string", "studies": []}
    
    if not isinstance(min_rank, int) or min_rank < 1:
        logger.warning(f"Invalid min_rank {min_rank}. Setting to 1.")
        min_rank = 1
    
    if not isinstance(max_rank, int) or max_rank < min_rank:
        logger.warning(f"Invalid max_rank {max_rank}. Setting to {min_rank + 9}.")
        max_rank = min_rank + 9
    
    # Prepare request
    config = get_global_config()
    base_url = config.clinicaltrials_api_url
    params = {
        "format": "json",
        "query.term": mutation,
        "pageSize": max_rank - min_rank + 1
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
        
        response = _session.get(base_url, params=params, timeout=timeout)
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
            
    except requests.exceptions.Timeout:
        request_duration = time.time() - start_time
        logger.error(f"Timeout ({timeout}s) when querying clinicaltrials.gov", extra={
            "mutation": mutation,
            "timeout": timeout,
            "request_duration": request_duration,
            "action": "api_request_timeout"
        })
        return {"error": "The request to clinicaltrials.gov timed out", "studies": []}
    except requests.exceptions.ConnectionError as e:
        request_duration = time.time() - start_time
        logger.error(f"Connection error: {e}", extra={
            "mutation": mutation,
            "request_duration": request_duration,
            "error": str(e),
            "action": "api_request_connection_error"
        })
        return {"error": "Failed to connect to clinicaltrials.gov", "studies": []}
    except requests.RequestException as e:
        request_duration = time.time() - start_time
        logger.error(f"Request error: {e}", extra={
            "mutation": mutation,
            "request_duration": request_duration,
            "error": str(e),
            "action": "api_request_error"
        })
        return {"error": f"Error querying clinicaltrials.gov: {e}", "studies": []}

def query_clinical_trials(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> Dict[str, Any]:
    """
    Query clinicaltrials.gov for clinical trials related to a given mutation.
    
    Uses caching for improved performance on repeated queries with the same parameters.

    Args:
        mutation (str): The mutation or keyword to search for (e.g., 'EGFR L858R').
        min_rank (int): The minimum rank of results to return (default: 1).
        max_rank (int): The maximum rank of results to return (default: 10).
        timeout (int): Timeout for the HTTP request in seconds (default: 10).

    Returns:
        Dict[str, Any]: Parsed JSON response from clinicaltrials.gov, or error dictionary with 'error' and 'studies' keys if an error occurred.
    """
    # Use cached version for standard timeout, bypass cache for custom timeout
    if timeout == 10:
        cache_info = _query_clinical_trials_cached.cache_info()
        logger.debug(f"Cache stats: hits={cache_info.hits}, misses={cache_info.misses}, size={cache_info.currsize}")
        return _query_clinical_trials_cached(mutation, min_rank, max_rank)
    else:
        # For custom timeout, bypass cache but use retry logic
        return _query_clinical_trials_with_retry(mutation, min_rank, max_rank, timeout)

def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics for the clinical trials query cache.
    
    Returns:
        Dict[str, Any]: Cache statistics including hits, misses, current size, and max size.
    """
    cache_info = _query_clinical_trials_cached.cache_info()
    return {
        "hits": cache_info.hits,
        "misses": cache_info.misses,
        "current_size": cache_info.currsize,
        "max_size": cache_info.maxsize,
        "hit_rate": cache_info.hits / (cache_info.hits + cache_info.misses) if (cache_info.hits + cache_info.misses) > 0 else 0
    }

def clear_cache() -> None:
    """
    Clear the clinical trials query cache.
    """
    _query_clinical_trials_cached.cache_clear()
    logger.info("Clinical trials query cache cleared")
