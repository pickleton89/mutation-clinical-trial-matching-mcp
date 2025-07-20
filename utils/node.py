"""
Backward compatibility layer for legacy utils.node imports.

This module provides deprecated classes that map to the new unified
architecture, ensuring existing code continues to work during migration.

DEPRECATED: This module is provided for backward compatibility only.
Use utils.unified_node.UnifiedNode and utils.unified_node.UnifiedFlow instead.
"""

import warnings
from typing import Any

from utils.unified_node import UnifiedFlow as _UnifiedFlow
from utils.unified_node import UnifiedNode as _UnifiedNode


class Node(_UnifiedNode):
    """
    DEPRECATED: Use UnifiedNode instead.

    Backward compatibility wrapper for sync Node execution.
    This class forces synchronous execution mode for compatibility
    with legacy code that expects blocking operations.
    """

    def __init__(self, node_id: str | None = None, **services):
        warnings.warn(
            "utils.node.Node is deprecated. "
            "Use utils.unified_node.UnifiedNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Force sync mode for backward compatibility
        super().__init__(async_mode=False, node_id=node_id, **services)

    def prep(self, shared: dict[str, Any]) -> Any:
        """
        Prepare data for execution.

        Override this method to extract and validate data from shared context.
        """
        return shared

    def exec(self, prep_result: Any) -> Any:
        """
        Execute the main node logic.

        Override this method to implement the core node functionality.
        """
        return prep_result

    def post(
        self,
        shared: dict[str, Any],
        prep_result: Any,
        exec_result: Any
    ) -> str | None:
        """
        Post-process results and update shared context.

        Override this method to handle results and determine next node.
        Return the next node ID or None to end execution.
        """
        return self.get_next_node_id(exec_result)


class AsyncNode(_UnifiedNode):
    """
    DEPRECATED: Use UnifiedNode instead.

    Backward compatibility wrapper for async Node execution.
    This class forces asynchronous execution mode for compatibility
    with legacy code that expects async operations.
    """

    def __init__(self, node_id: str | None = None, **services):
        warnings.warn(
            "utils.node.AsyncNode is deprecated. "
            "Use utils.unified_node.UnifiedNode instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Force async mode for backward compatibility
        super().__init__(async_mode=True, node_id=node_id, **services)


class Flow(_UnifiedFlow):
    """
    DEPRECATED: Use UnifiedFlow instead.

    Backward compatibility wrapper for sync Flow execution.
    This class forces synchronous execution mode for compatibility
    with legacy code that expects blocking flow operations.
    """

    def __init__(self, start_node=None):
        warnings.warn(
            "utils.node.Flow is deprecated. "
            "Use utils.unified_node.UnifiedFlow instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Force sync mode for backward compatibility
        super().__init__(start_node=start_node, async_mode=False)

    def run(self, shared: dict[str, Any]) -> dict[str, Any]:
        """
        Backward compatibility method for execute().

        DEPRECATED: Use execute() instead.
        """
        warnings.warn(
            "Flow.run() is deprecated. Use Flow.execute() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.execute(shared)


class AsyncFlow(_UnifiedFlow):
    """
    DEPRECATED: Use UnifiedFlow instead.

    Backward compatibility wrapper for async Flow execution.
    This class forces asynchronous execution mode for compatibility
    with legacy code that expects async flow operations.
    """

    def __init__(self, start_node=None):
        warnings.warn(
            "utils.node.AsyncFlow is deprecated. "
            "Use utils.unified_node.UnifiedFlow instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Force async mode for backward compatibility
        super().__init__(start_node=start_node, async_mode=True)

    async def run(self, shared: dict[str, Any]) -> dict[str, Any]:
        """
        Backward compatibility method for aexecute().

        DEPRECATED: Use aexecute() instead.
        """
        warnings.warn(
            "AsyncFlow.run() is deprecated. Use AsyncFlow.aexecute() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return await self.aexecute(shared)


# Module-level exports for drop-in compatibility
__all__ = [
    'Node',
    'AsyncNode',
    'Flow',
    'AsyncFlow'
]
