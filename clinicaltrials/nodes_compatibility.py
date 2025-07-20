"""
Backward compatibility wrappers for node migration.

This module provides deprecated node classes that map to the new
unified nodes, ensuring existing code continues to work during migration.
"""

import warnings

from clinicaltrials.unified_nodes import BatchQueryTrialsNode as UnifiedBatchQueryTrialsNode
from clinicaltrials.unified_nodes import QueryTrialsNode as UnifiedQueryTrialsNode
from clinicaltrials.unified_nodes import SummarizeTrialsNode as UnifiedSummarizeTrialsNode
from utils.unified_node import UnifiedFlow


# Sync node compatibility wrappers (replacing clinicaltrials/nodes.py)
class QueryTrialsNode(UnifiedQueryTrialsNode):
    """
    DEPRECATED: Use unified QueryTrialsNode instead.

    Backward compatibility wrapper for sync QueryTrialsNode.
    """

    def __init__(self, min_rank: int = 1, max_rank: int = 10, timeout: float | None = None):
        warnings.warn(
            "clinicaltrials.nodes.QueryTrialsNode is deprecated. "
            "Use clinicaltrials.unified_nodes.QueryTrialsNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(
            async_mode=False,  # Force sync mode for compatibility
            min_rank=min_rank,
            max_rank=max_rank,
            timeout=timeout
        )


class SummarizeTrialsNode(UnifiedSummarizeTrialsNode):
    """
    DEPRECATED: Use unified SummarizeTrialsNode instead.

    Backward compatibility wrapper for sync SummarizeTrialsNode.
    """

    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        warnings.warn(
            "clinicaltrials.nodes.SummarizeTrialsNode is deprecated. "
            "Use clinicaltrials.unified_nodes.SummarizeTrialsNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(
            async_mode=False,  # Force sync mode for compatibility
            model=model,
            max_tokens=max_tokens
        )


# Async node compatibility wrappers (replacing clinicaltrials/async_nodes.py)
class AsyncQueryTrialsNode(UnifiedQueryTrialsNode):
    """
    DEPRECATED: Use unified QueryTrialsNode instead.

    Backward compatibility wrapper for async QueryTrialsNode.
    """

    def __init__(self, min_rank: int = 1, max_rank: int = 10):
        warnings.warn(
            "clinicaltrials.async_nodes.AsyncQueryTrialsNode is deprecated. "
            "Use clinicaltrials.unified_nodes.QueryTrialsNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(
            async_mode=True,  # Force async mode for compatibility
            min_rank=min_rank,
            max_rank=max_rank
        )


class AsyncSummarizeTrialsNode(UnifiedSummarizeTrialsNode):
    """
    DEPRECATED: Use unified SummarizeTrialsNode instead.

    Backward compatibility wrapper for async SummarizeTrialsNode.
    """

    def __init__(self, model: str | None = None, max_tokens: int | None = None):
        warnings.warn(
            "clinicaltrials.async_nodes.AsyncSummarizeTrialsNode is deprecated. "
            "Use clinicaltrials.unified_nodes.SummarizeTrialsNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(
            async_mode=True,  # Force async mode for compatibility
            model=model,
            max_tokens=max_tokens
        )


class AsyncBatchQueryTrialsNode(UnifiedBatchQueryTrialsNode):
    """
    DEPRECATED: Use unified BatchQueryTrialsNode instead.

    Backward compatibility wrapper for async batch QueryTrialsNode.
    """

    def __init__(
        self,
        min_rank: int = 1,
        max_rank: int = 10,
        max_concurrent: int = 5
    ):
        warnings.warn(
            "clinicaltrials.async_nodes.AsyncBatchQueryTrialsNode is deprecated. "
            "Use clinicaltrials.unified_nodes.BatchQueryTrialsNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(
            async_mode=True,  # Force async mode for compatibility
            min_rank=min_rank,
            max_rank=max_rank,
            max_concurrent=max_concurrent
        )


# Flow compatibility wrappers (replacing utils/node.py Flow classes)
class Flow(UnifiedFlow):
    """
    DEPRECATED: Use UnifiedFlow instead.

    Backward compatibility wrapper for sync Flow.
    """

    def __init__(self, start_node=None):
        warnings.warn(
            "utils.node.Flow is deprecated. "
            "Use utils.unified_node.UnifiedFlow instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(start_node=start_node, async_mode=False)


class AsyncFlow(UnifiedFlow):
    """
    DEPRECATED: Use UnifiedFlow instead.

    Backward compatibility wrapper for async Flow.
    """

    def __init__(self, start_node=None):
        warnings.warn(
            "utils.node.AsyncFlow is deprecated. "
            "Use utils.unified_node.UnifiedFlow instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(start_node=start_node, async_mode=True)


# Module-level exports for drop-in compatibility
__all__ = [
    # Sync node classes
    'QueryTrialsNode',
    'SummarizeTrialsNode',

    # Async node classes
    'AsyncQueryTrialsNode',
    'AsyncSummarizeTrialsNode',
    'AsyncBatchQueryTrialsNode',

    # Flow classes
    'Flow',
    'AsyncFlow'
]
