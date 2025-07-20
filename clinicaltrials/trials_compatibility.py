"""
Backward compatibility wrappers for Clinical Trials service migration.

This module provides deprecated function signatures that map to the new
unified Clinical Trials service, ensuring existing code continues to work during migration.
"""

import warnings
from typing import Any

from clinicaltrials.service import get_async_trials_service, get_sync_trials_service


# Sync compatibility functions (replacing clinicaltrials/query.py)
def query_trials_for_mutation(
    mutation: str,
    min_rank: int = 1,
    max_rank: int = 10,
    custom_timeout: float | None = None
) -> dict[str, Any]:
    """
    DEPRECATED: Use ClinicalTrialsService.query_trials() instead.

    Backward compatibility wrapper for sync trial queries.
    """
    warnings.warn(
        "query_trials_for_mutation() is deprecated. Use ClinicalTrialsService.query_trials() or get_sync_trials_service().query_trials() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_sync_trials_service()
    return service.query_trials(mutation, min_rank, max_rank, custom_timeout)


# Async compatibility functions (replacing clinicaltrials/async_query.py)
async def query_trials_async(
    mutation: str,
    min_rank: int = 1,
    max_rank: int = 10
) -> dict[str, Any]:
    """
    DEPRECATED: Use ClinicalTrialsService.aquery_trials() instead.

    Backward compatibility wrapper for async trial queries.
    """
    warnings.warn(
        "query_trials_async() is deprecated. Use ClinicalTrialsService.aquery_trials() or get_async_trials_service().aquery_trials() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_async_trials_service()
    return await service.aquery_trials(mutation, min_rank, max_rank)


async def query_multiple_mutations_async(
    mutations: list[str],
    min_rank: int = 1,
    max_rank: int = 10
) -> list[dict[str, Any]]:
    """
    DEPRECATED: Use ClinicalTrialsService.aquery_trials_batch() instead.

    Backward compatibility wrapper for batch async trial queries.
    """
    warnings.warn(
        "query_multiple_mutations_async() is deprecated. Use ClinicalTrialsService.aquery_trials_batch() or get_async_trials_service().aquery_trials_batch() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_async_trials_service()
    return await service.aquery_trials_batch(mutations, min_rank, max_rank)


# Cache management compatibility (from sync query.py)
def get_cache_stats() -> dict[str, Any]:
    """
    DEPRECATED: Use ClinicalTrialsService.get_cache_info() instead.

    Backward compatibility wrapper for cache statistics.
    """
    warnings.warn(
        "get_cache_stats() is deprecated. Use ClinicalTrialsService.get_cache_info() or get_sync_trials_service().get_cache_info() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_sync_trials_service()
    cache_info = service.get_cache_info()

    if cache_info:
        # Convert to old format
        return {
            "hits": cache_info["hits"],
            "misses": cache_info["misses"],
            "maxsize": cache_info["maxsize"],
            "currsize": cache_info["currsize"],
            "hit_rate": cache_info["hit_rate"]
        }
    else:
        return {
            "hits": 0,
            "misses": 0,
            "maxsize": 0,
            "currsize": 0,
            "hit_rate": 0.0
        }


def clear_cache():
    """
    DEPRECATED: Use ClinicalTrialsService.clear_cache() instead.

    Backward compatibility wrapper for cache clearing.
    """
    warnings.warn(
        "clear_cache() is deprecated. Use ClinicalTrialsService.clear_cache() or get_sync_trials_service().clear_cache() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_sync_trials_service()
    service.clear_cache()


# Module-level exports for drop-in compatibility
__all__ = [
    'query_trials_for_mutation',
    'query_trials_async',
    'query_multiple_mutations_async',
    'get_cache_stats',
    'clear_cache'
]
