"""
Unified Clinical Trials service supporting both sync and async execution patterns.

This module provides a single Clinical Trials service interface that can operate
in either synchronous or asynchronous mode, eliminating code duplication between
clinicaltrials/query.py and clinicaltrials/async_query.py.
"""

import asyncio
import logging
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode

from clinicaltrials.config import get_global_config
from utils.http_client import create_clinicaltrials_client
from utils.shared import (
    validate_mutation_input,
    map_http_exception_to_error_response,
    time_request,
    extract_studies_from_response,
    process_json_response
)
from utils.metrics import increment, gauge, histogram
from utils.response_validation import response_validator


logger = logging.getLogger(__name__)


class ClinicalTrialsService:
    """
    Unified Clinical Trials query service supporting both sync and async execution.
    
    This service provides a consistent interface for querying the ClinicalTrials.gov
    API, supporting both synchronous and asynchronous execution modes with built-in
    caching, resilience patterns, and metrics collection.
    """
    
    def __init__(
        self,
        async_mode: bool = False,
        cache_enabled: bool = True,
        cache_size: int = 100,
        max_concurrent_requests: int = 5
    ):
        """
        Initialize the Clinical Trials service.
        
        Args:
            async_mode: Whether to use async execution
            cache_enabled: Whether to enable result caching (sync mode only)
            cache_size: Maximum number of cached results
            max_concurrent_requests: Max concurrent requests for batch processing
        """
        self.async_mode = async_mode
        self.cache_enabled = cache_enabled and not async_mode  # Only sync supports caching
        self.cache_size = cache_size
        
        # Load configuration
        try:
            self.config = get_global_config()
        except ValueError as e:
            logger.warning(f"Failed to load global config: {e}. Using defaults.")
            self.config = None
        
        # Set up HTTP client
        self._client = create_clinicaltrials_client(async_mode=async_mode)
        
        # Set up concurrency control for async batch processing
        if async_mode:
            self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Set up caching for sync mode
        if self.cache_enabled:
            self._setup_cache()
        
        # Metrics prefix based on mode
        self._metrics_prefix = "clinicaltrials_api"
        self._metrics_suffix = "_async" if async_mode else ""
        
        # Track service statistics
        self._stats = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0
        }
        
        logger.info(
            f"Clinical Trials service initialized in {'async' if async_mode else 'sync'} mode",
            extra={
                "action": "clinicaltrials_service_initialized",
                "async_mode": async_mode,
                "cache_enabled": self.cache_enabled,
                "cache_size": cache_size if self.cache_enabled else None
            }
        )
    
    def _setup_cache(self):
        """Set up LRU cache for sync mode."""
        # Create a cached version of the internal query method
        self._cached_query = lru_cache(maxsize=self.cache_size)(self._execute_query_sync)
    
    def _build_query_params(self, mutation: str, min_rank: int, max_rank: int) -> str:
        """
        Build query parameters for the API request.
        
        Args:
            mutation: The mutation to search for
            min_rank: Minimum rank for results
            max_rank: Maximum rank for results
            
        Returns:
            URL-encoded query string
        """
        # Calculate page size based on rank range
        page_size = min(max_rank - min_rank + 1, 1000)  # API max is 1000
        
        params = {
            "format": "json",
            "query.term": mutation,
            "pageSize": page_size
        }
        
        return urlencode(params)
    
    def _execute_query_sync(self, mutation: str, min_rank: int, max_rank: int) -> Dict[str, Any]:
        """
        Internal sync query execution (can be cached).
        
        Args:
            mutation: The mutation to search for
            min_rank: Minimum rank for results
            max_rank: Maximum rank for results
            
        Returns:
            Query results dictionary
        """
        # Build query URL
        query_params = self._build_query_params(mutation, min_rank, max_rank)
        url = f"v2/studies?{query_params}"
        
        # Make request
        response = self._client.get(url)
        
        # Check status
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(f"ClinicalTrials API returned error: {error_msg}")
            
            # Map HTTP errors to standard format
            error_response = {
                "error": f"ClinicalTrials API error: HTTP {response.status_code}",
                "studies": []
            }
            
            if response.status_code == 429:
                error_response["error"] = "Rate limit exceeded. Please try again later."
                error_response["retry_after"] = 60
            elif response.status_code >= 500:
                error_response["error"] = "ClinicalTrials API server error. Please try again later."
                error_response["retry_after"] = 120
            
            return error_response
        
        # Parse response
        response_data = process_json_response(
            response.text,
            self._metrics_prefix,
            expected_fields=["studies"]
        )
        
        # Extract studies
        studies = extract_studies_from_response(response_data)
        
        # Filter by rank if needed
        if min_rank > 1 or max_rank < len(studies):
            studies = studies[min_rank-1:max_rank]
        
        return {"studies": studies}
    
    async def _execute_query_async(self, mutation: str, min_rank: int, max_rank: int) -> Dict[str, Any]:
        """
        Internal async query execution.
        
        Args:
            mutation: The mutation to search for
            min_rank: Minimum rank for results
            max_rank: Maximum rank for results
            
        Returns:
            Query results dictionary
        """
        # Build query URL
        query_params = self._build_query_params(mutation, min_rank, max_rank)
        url = f"v2/studies?{query_params}"
        
        # Make request
        response = await self._client.aget(url)
        
        # Check status
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(f"ClinicalTrials API returned error: {error_msg}")
            
            # Map HTTP errors to standard format
            error_response = {
                "error": f"ClinicalTrials API error: HTTP {response.status_code}",
                "studies": []
            }
            
            if response.status_code == 429:
                error_response["error"] = "Rate limit exceeded. Please try again later."
                error_response["retry_after"] = 60
            elif response.status_code >= 500:
                error_response["error"] = "ClinicalTrials API server error. Please try again later."
                error_response["retry_after"] = 120
            
            return error_response
        
        # Parse response
        response_data = process_json_response(
            response.text,
            self._metrics_prefix,
            expected_fields=["studies"]
        )
        
        # Extract studies
        studies = extract_studies_from_response(response_data)
        
        # Filter by rank if needed
        if min_rank > 1 or max_rank < len(studies):
            studies = studies[min_rank-1:max_rank]
        
        return {"studies": studies}
    
    @time_request("clinicaltrials", "query_trials")
    @response_validator("clinicaltrials_response")
    def query_trials(
        self,
        mutation: str,
        min_rank: int = 1,
        max_rank: int = 10,
        custom_timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Query clinical trials for a given mutation (sync).
        
        Args:
            mutation: The genetic mutation to search for
            min_rank: Minimum rank for results (default: 1)
            max_rank: Maximum rank for results (default: 10)
            custom_timeout: Custom timeout in seconds (bypasses cache)
            
        Returns:
            Dictionary containing studies list and optional error information
        """
        if self.async_mode:
            # If in async mode but called synchronously, use sync fallback
            logger.warning("Sync query_trials() called on async-configured service")
            return asyncio.run(self.aquery_trials(mutation, min_rank, max_rank))
        
        # Update statistics
        self._stats["total_queries"] += 1
        
        # Validate input
        validation_result = validate_mutation_input(mutation, min_rank, max_rank)
        if not validation_result["valid"]:
            return {"error": validation_result["error"], "studies": []}
        
        # Use validated values
        mutation = validation_result["mutation"]
        min_rank = validation_result["min_rank"]
        max_rank = validation_result["max_rank"]
        
        # Log warnings
        for warning in validation_result["warnings"]:
            logger.warning(f"Input validation: {warning}")
        
        # Increment metrics
        increment(f"{self._metrics_prefix}_calls_total{self._metrics_suffix}")
        
        logger.info(
            f"Querying ClinicalTrials API for mutation: {mutation}",
            extra={
                "action": f"{self._metrics_prefix}_query_start{self._metrics_suffix}",
                "mutation": mutation,
                "min_rank": min_rank,
                "max_rank": max_rank,
                "cache_enabled": self.cache_enabled,
                "custom_timeout": custom_timeout
            }
        )
        
        try:
            # Use cache if enabled and no custom timeout
            if self.cache_enabled and custom_timeout is None:
                result = self._cached_query(mutation, min_rank, max_rank)
                
                # Track cache statistics
                cache_info = self._cached_query.cache_info()
                if cache_info.hits > self._stats["cache_hits"]:
                    self._stats["cache_hits"] = cache_info.hits
                    increment(f"{self._metrics_prefix}_cache_hits{self._metrics_suffix}")
                    logger.info(f"Cache hit for mutation: {mutation}")
                else:
                    self._stats["cache_misses"] = cache_info.misses
                    increment(f"{self._metrics_prefix}_cache_misses{self._metrics_suffix}")
                    logger.info(f"Cache miss for mutation: {mutation}")
            else:
                # Direct execution (no cache)
                result = self._execute_query_sync(mutation, min_rank, max_rank)
            
            # Handle errors in result
            if "error" in result:
                self._stats["errors"] += 1
                increment(f"{self._metrics_prefix}_errors{self._metrics_suffix}",
                         tags={"error_type": "api_error"})
                return result
            
            # Success metrics
            study_count = len(result.get("studies", []))
            increment(f"{self._metrics_prefix}_success{self._metrics_suffix}")
            gauge(f"{self._metrics_prefix}_study_count{self._metrics_suffix}", study_count)
            
            logger.info(
                f"Successfully retrieved {study_count} studies for mutation: {mutation}",
                extra={
                    "action": f"{self._metrics_prefix}_query_success{self._metrics_suffix}",
                    "mutation": mutation,
                    "study_count": study_count
                }
            )
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            increment(f"{self._metrics_prefix}_errors{self._metrics_suffix}",
                     tags={"error_type": type(e).__name__})
            
            logger.error(
                f"Failed to query trials for mutation {mutation}: {str(e)}",
                extra={
                    "action": f"{self._metrics_prefix}_query_failed{self._metrics_suffix}",
                    "mutation": mutation,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            # Map exception to error response
            error_response = map_http_exception_to_error_response(
                e, "clinicaltrials", f"Failed to query trials for {mutation}"
            )
            return error_response
    
    @time_request("clinicaltrials", "query_trials_async")
    @response_validator("clinicaltrials_response")
    async def aquery_trials(
        self,
        mutation: str,
        min_rank: int = 1,
        max_rank: int = 10
    ) -> Dict[str, Any]:
        """
        Query clinical trials for a given mutation (async).
        
        Args:
            mutation: The genetic mutation to search for
            min_rank: Minimum rank for results (default: 1)
            max_rank: Maximum rank for results (default: 10)
            
        Returns:
            Dictionary containing studies list and optional error information
        """
        if not self.async_mode:
            raise RuntimeError("Cannot use aquery_trials() when async_mode=False")
        
        # Update statistics
        self._stats["total_queries"] += 1
        
        # Validate input
        validation_result = validate_mutation_input(mutation, min_rank, max_rank)
        if not validation_result["valid"]:
            return {"error": validation_result["error"], "studies": []}
        
        # Use validated values
        mutation = validation_result["mutation"]
        min_rank = validation_result["min_rank"]
        max_rank = validation_result["max_rank"]
        
        # Log warnings
        for warning in validation_result["warnings"]:
            logger.warning(f"Input validation: {warning}")
        
        # Increment metrics
        increment(f"{self._metrics_prefix}_calls_total{self._metrics_suffix}")
        
        logger.info(
            f"Async querying ClinicalTrials API for mutation: {mutation}",
            extra={
                "action": f"{self._metrics_prefix}_query_start{self._metrics_suffix}",
                "mutation": mutation,
                "min_rank": min_rank,
                "max_rank": max_rank
            }
        )
        
        try:
            # Direct async execution
            result = await self._execute_query_async(mutation, min_rank, max_rank)
            
            # Handle errors in result
            if "error" in result:
                self._stats["errors"] += 1
                increment(f"{self._metrics_prefix}_errors{self._metrics_suffix}",
                         tags={"error_type": "api_error"})
                return result
            
            # Success metrics
            study_count = len(result.get("studies", []))
            increment(f"{self._metrics_prefix}_success{self._metrics_suffix}")
            gauge(f"{self._metrics_prefix}_study_count{self._metrics_suffix}", study_count)
            
            logger.info(
                f"Successfully retrieved {study_count} studies for mutation: {mutation}",
                extra={
                    "action": f"{self._metrics_prefix}_query_success{self._metrics_suffix}",
                    "mutation": mutation,
                    "study_count": study_count
                }
            )
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            increment(f"{self._metrics_prefix}_errors{self._metrics_suffix}",
                     tags={"error_type": type(e).__name__})
            
            logger.error(
                f"Failed to async query trials for mutation {mutation}: {str(e)}",
                extra={
                    "action": f"{self._metrics_prefix}_query_failed{self._metrics_suffix}",
                    "mutation": mutation,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            # Map exception to error response
            error_response = map_http_exception_to_error_response(
                e, "clinicaltrials", f"Failed to query trials for {mutation}"
            )
            return error_response
    
    async def aquery_trials_batch(
        self,
        mutations: List[str],
        min_rank: int = 1,
        max_rank: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query clinical trials for multiple mutations concurrently.
        
        Args:
            mutations: List of mutations to query
            min_rank: Minimum rank for results
            max_rank: Maximum rank for results
            
        Returns:
            List of results for each mutation
        """
        if not self.async_mode:
            raise RuntimeError("Cannot use aquery_trials_batch() when async_mode=False")
        
        start_time = time.time()
        batch_size = len(mutations)
        
        logger.info(
            f"Starting batch query for {batch_size} mutations",
            extra={
                "action": "clinicaltrials_batch_start",
                "batch_size": batch_size,
                "max_concurrent": self._semaphore._value
            }
        )
        
        increment(f"{self._metrics_prefix}_batch_calls{self._metrics_suffix}",
                 tags={"batch_size": str(batch_size)})
        
        async def query_with_semaphore(mutation: str, index: int) -> Dict[str, Any]:
            """Query a single mutation with semaphore control."""
            async with self._semaphore:
                try:
                    logger.debug(f"Querying mutation {index + 1}/{batch_size}: {mutation}")
                    result = await self.aquery_trials(mutation, min_rank, max_rank)
                    return result
                except Exception as e:
                    logger.error(f"Failed to query mutation {mutation}: {str(e)}")
                    return {"error": str(e), "studies": [], "mutation": mutation}
        
        # Process all mutations concurrently
        tasks = [
            query_with_semaphore(mutation, i)
            for i, mutation in enumerate(mutations)
        ]
        results = await asyncio.gather(*tasks)
        
        # Count successes and failures
        successes = sum(1 for r in results if "error" not in r)
        failures = batch_size - successes
        
        duration = time.time() - start_time
        
        # Record batch metrics
        increment(f"{self._metrics_prefix}_batch_success{self._metrics_suffix}",
                 tags={"batch_size": str(successes)})
        increment(f"{self._metrics_prefix}_batch_errors{self._metrics_suffix}",
                 tags={"batch_size": str(failures)})
        histogram(f"{self._metrics_prefix}_batch_duration{self._metrics_suffix}",
                 duration, tags={"batch_size": str(batch_size)})
        gauge(f"{self._metrics_prefix}_batch_success_rate{self._metrics_suffix}",
              successes / batch_size * 100 if batch_size > 0 else 0)
        
        logger.info(
            f"Completed batch query: {successes}/{batch_size} successful",
            extra={
                "action": "clinicaltrials_batch_complete",
                "batch_size": batch_size,
                "successes": successes,
                "failures": failures,
                "duration": duration,
                "avg_time_per_mutation": duration / batch_size if batch_size > 0 else 0
            }
        )
        
        return results
    
    def get_cache_info(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics (sync mode only).
        
        Returns:
            Cache statistics or None if caching is disabled
        """
        if not self.cache_enabled:
            return None
        
        cache_info = self._cached_query.cache_info()
        return {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "maxsize": cache_info.maxsize,
            "currsize": cache_info.currsize,
            "hit_rate": cache_info.hits / (cache_info.hits + cache_info.misses) * 100
                       if (cache_info.hits + cache_info.misses) > 0 else 0
        }
    
    def clear_cache(self):
        """Clear the cache (sync mode only)."""
        if self.cache_enabled:
            self._cached_query.cache_clear()
            logger.info("Clinical trials cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        stats = self._stats.copy()
        if self.cache_enabled:
            stats["cache_info"] = self.get_cache_info()
        return stats
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    async def aclose(self):
        """Async close the HTTP client."""
        await self._client.aclose()
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
    
    async def __aenter__(self):
        """Async context manager support."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager cleanup."""
        await self.aclose()


# Global service instances for backward compatibility
_sync_service: Optional[ClinicalTrialsService] = None
_async_service: Optional[ClinicalTrialsService] = None


@lru_cache(maxsize=1)
def get_sync_trials_service() -> ClinicalTrialsService:
    """Get or create the global sync Clinical Trials service."""
    global _sync_service
    if _sync_service is None:
        _sync_service = ClinicalTrialsService(async_mode=False)
    return _sync_service


@lru_cache(maxsize=1)
def get_async_trials_service() -> ClinicalTrialsService:
    """Get or create the global async Clinical Trials service."""
    global _async_service
    if _async_service is None:
        _async_service = ClinicalTrialsService(async_mode=True)
    return _async_service


async def cleanup_services():
    """Clean up all global Clinical Trials services."""
    global _sync_service, _async_service
    
    if _sync_service:
        _sync_service.close()
        _sync_service = None
    
    if _async_service:
        await _async_service.aclose()
        _async_service = None
    
    # Clear the caches
    get_sync_trials_service.cache_clear()
    get_async_trials_service.cache_clear()
    
    logger.info("Clinical Trials services cleaned up", 
                extra={"action": "clinicaltrials_services_cleanup"})