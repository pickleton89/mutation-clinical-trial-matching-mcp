"""
Backward compatibility wrappers for LLM service migration.

This module provides deprecated function signatures that map to the new
unified LLM service, ensuring existing code continues to work during migration.
"""

import warnings
from typing import List, Union

from utils.llm_service import get_sync_llm_service, get_async_llm_service, cleanup_services


# Sync compatibility functions (replacing utils/call_llm.py)
def call_llm(prompt: str) -> str:
    """
    DEPRECATED: Use LLMService.call_llm() instead.
    
    Backward compatibility wrapper for sync LLM calls.
    """
    warnings.warn(
        "call_llm() is deprecated. Use LLMService.call_llm() or get_sync_llm_service().call_llm() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_sync_llm_service()
    return service.call_llm(prompt)


# Async compatibility functions (replacing utils/async_call_llm.py)
async def call_llm_async(prompt: str) -> str:
    """
    DEPRECATED: Use LLMService.acall_llm() instead.
    
    Backward compatibility wrapper for async LLM calls.
    """
    warnings.warn(
        "call_llm_async() is deprecated. Use LLMService.acall_llm() or get_async_llm_service().acall_llm() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_async_llm_service()
    return await service.acall_llm(prompt)


async def call_llm_batch_async(prompts: List[str]) -> List[Union[str, Exception]]:
    """
    DEPRECATED: Use LLMService.acall_llm_batch() instead.
    
    Backward compatibility wrapper for batch async LLM calls.
    """
    warnings.warn(
        "call_llm_batch_async() is deprecated. Use LLMService.acall_llm_batch() or get_async_llm_service().acall_llm_batch() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    service = get_async_llm_service()
    return await service.acall_llm_batch(prompts)


async def cleanup_async_clients():
    """
    DEPRECATED: Use cleanup_services() instead.
    
    Backward compatibility wrapper for client cleanup.
    """
    warnings.warn(
        "cleanup_async_clients() is deprecated. Use cleanup_services() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    await cleanup_services()


# Module-level exports for drop-in compatibility
__all__ = [
    'call_llm',
    'call_llm_async', 
    'call_llm_batch_async',
    'cleanup_async_clients'
]