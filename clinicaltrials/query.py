"""
Functions to query clinicaltrials.gov for trials matching a mutation.
"""

import logging
import time
from functools import lru_cache
from typing import Any

import requests
from requests import exceptions as requests_exceptions

from clinicaltrials.config import get_global_config
from utils.circuit_breaker import circuit_breaker
from utils.metrics import gauge, histogram, increment, timer
from utils.response_validation import response_validator
from utils.retry import exponential_backoff_retry

logger = logging.getLogger(__name__)

# NOTE: This is a legacy sync implementation - use clinicaltrials.async_query for new code
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
@response_validator("clinical_trials_api")
def _query_clinical_trials_cached(mutation: str, min_rank: int = 1, max_rank: int = 10) -> dict[str, Any]:
    """
    Internal cached version of query_clinical_trials without timeout parameter.
    """
    return _query_clinical_trials_with_retry(mutation, min_rank, max_rank, 10)

@response_validator("clinical_trials_api")
def _query_clinical_trials_with_retry(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> dict[str, Any]:
    """
    Query clinical trials with retry logic and circuit breaker applied.
    """
    config = get_global_config()

    @circuit_breaker(
        name="clinicaltrials_api",
        failure_threshold=config.circuit_breaker_failure_threshold,
        recovery_timeout=config.circuit_breaker_recovery_timeout
    )
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

def _query_clinical_trials_impl(mutation: str, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> dict[str, Any]:
    """
    Internal implementation of clinical trials query with metrics collection.
    """
    # Track API call metrics
    increment("clinicaltrials_api_calls_total", tags={"mutation": mutation})

    # Input validation
    if not mutation or not isinstance(mutation, str) or len(mutation.strip()) == 0:
        logger.error("Error: Mutation must be a non-empty string")
        increment("clinicaltrials_api_validation_errors", tags={"error_type": "invalid_mutation"})
        return {"error": "Mutation must be a non-empty string", "studies": []}

    if not isinstance(min_rank, int) or min_rank < 1:
        logger.warning(f"Invalid min_rank {min_rank}. Setting to 1.")
        increment("clinicaltrials_api_validation_warnings", tags={"warning_type": "invalid_min_rank"})
        min_rank = 1

    if not isinstance(max_rank, int) or max_rank < min_rank:
        logger.warning(f"Invalid max_rank {max_rank}. Setting to {min_rank + 9}.")
        increment("clinicaltrials_api_validation_warnings", tags={"warning_type": "invalid_max_rank"})
        max_rank = min_rank + 9

    # Prepare request
    config = get_global_config()
    base_url = config.clinicaltrials_api_url
    params = {
        "format": "json",
        "query.term": mutation,
        "pageSize": max_rank - min_rank + 1
    }

    with timer("clinicaltrials_api_request", tags={"mutation": mutation}):
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

            # Record request metrics
            histogram("clinicaltrials_api_request_duration", request_duration, tags={"mutation": mutation})
            gauge("clinicaltrials_api_last_request_duration", request_duration)

            # Check for non-200 status codes
            if response.status_code != 200:
                increment("clinicaltrials_api_errors", tags={"error_type": "http_error", "status_code": str(response.status_code)})
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

                # Record success metrics
                increment("clinicaltrials_api_success", tags={"mutation": mutation})
                histogram("clinicaltrials_api_study_count", study_count, tags={"mutation": mutation})
                gauge("clinicaltrials_api_last_study_count", study_count)

                logger.info(f"Found {study_count} studies for mutation {mutation} in {request_duration:.2f}s", extra={
                    "mutation": mutation,
                    "study_count": study_count,
                    "request_duration": request_duration,
                    "action": "api_request_success"
                })
                return result
            except ValueError as json_err:
                increment("clinicaltrials_api_errors", tags={"error_type": "json_parse_error"})
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
            increment("clinicaltrials_api_errors", tags={"error_type": "timeout"})
            histogram("clinicaltrials_api_request_duration", request_duration, tags={"mutation": mutation, "error": "timeout"})
            logger.error(f"Timeout ({timeout}s) when querying clinicaltrials.gov", extra={
                "mutation": mutation,
                "timeout": timeout,
                "request_duration": request_duration,
                "action": "api_request_timeout"
            })
            return {"error": "The request to clinicaltrials.gov timed out", "studies": []}
        except requests_exceptions.ConnectionError as e:
            request_duration = time.time() - start_time
            increment("clinicaltrials_api_errors", tags={"error_type": "connection_error"})
            histogram("clinicaltrials_api_request_duration", request_duration, tags={"mutation": mutation, "error": "connection"})
            logger.error(f"Connection error: {e}", extra={
                "mutation": mutation,
                "request_duration": request_duration,
                "error": str(e),
                "action": "api_request_connection_error"
            })
            return {"error": "Failed to connect to clinicaltrials.gov", "studies": []}
        except requests.RequestException as e:
            request_duration = time.time() - start_time
            increment("clinicaltrials_api_errors", tags={"error_type": "request_error"})
            histogram("clinicaltrials_api_request_duration", request_duration, tags={"mutation": mutation, "error": "request"})
            logger.error(f"Request error: {e}", extra={
                "mutation": mutation,
                "request_duration": request_duration,
                "error": str(e),
                "action": "api_request_error"
            })
            return {"error": f"Error querying clinicaltrials.gov: {e}", "studies": []}

def query_clinical_trials(mutation: str | None, min_rank: int = 1, max_rank: int = 10, timeout: int = 10) -> dict[str, Any]:
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
        cache_info_before = _query_clinical_trials_cached.cache_info()
        result = _query_clinical_trials_cached(mutation, min_rank, max_rank)
        cache_info_after = _query_clinical_trials_cached.cache_info()

        # Track cache hit/miss metrics
        if cache_info_after.hits > cache_info_before.hits:
            increment("clinicaltrials_cache_hits", tags={"mutation": mutation})
        else:
            increment("clinicaltrials_cache_misses", tags={"mutation": mutation})

        # Update cache statistics gauges
        gauge("clinicaltrials_cache_size", cache_info_after.currsize)
        gauge("clinicaltrials_cache_hit_rate",
              cache_info_after.hits / (cache_info_after.hits + cache_info_after.misses)
              if (cache_info_after.hits + cache_info_after.misses) > 0 else 0)

        logger.debug(f"Cache stats: hits={cache_info_after.hits}, misses={cache_info_after.misses}, size={cache_info_after.currsize}")
        return result
    else:
        # For custom timeout, bypass cache but use retry logic
        increment("clinicaltrials_cache_bypassed", tags={"reason": "custom_timeout"})
        return _query_clinical_trials_with_retry(mutation, min_rank, max_rank, timeout)

def get_cache_stats() -> dict[str, Any]:
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
