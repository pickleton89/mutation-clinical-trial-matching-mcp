"""
Unified Node framework supporting both sync and async execution patterns.

This module provides a unified node architecture that can operate in either
synchronous or asynchronous mode, eliminating code duplication between
sync and async node implementations while preserving all PocketFlow features.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic, Union, Callable, Set
from collections.abc import Awaitable

from utils.metrics import increment, gauge, histogram


logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class UnifiedNode(Generic[T, R], ABC):
    """
    Unified base class for nodes supporting both sync and async execution.
    
    This class provides a single implementation that can operate in either
    synchronous or asynchronous mode, determined at runtime based on the
    execution context or explicit configuration.
    """
    
    def __init__(
        self,
        async_mode: Optional[bool] = None,
        node_id: Optional[str] = None,
        **services
    ):
        """
        Initialize the unified node.
        
        Args:
            async_mode: Force sync (False) or async (True) mode. If None, auto-detect.
            node_id: Unique identifier for this node
            **services: Service dependencies to inject
        """
        self.async_mode = async_mode
        self.node_id = node_id or self.__class__.__name__
        self.services = services
        
        # Node chaining support
        self._next_nodes: Dict[str, 'UnifiedNode'] = {}
        self._default_next: Optional[str] = None
        
        # Performance tracking
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._last_execution_time: Optional[float] = None
        
        logger.debug(
            f"Initialized unified node: {self.node_id}",
            extra={
                "action": "unified_node_initialized",
                "node_id": self.node_id,
                "async_mode": async_mode,
                "services": list(services.keys())
            }
        )
    
    def _detect_async_mode(self) -> bool:
        """
        Auto-detect whether to use async mode based on method implementations.
        
        Returns:
            True if async mode should be used, False otherwise
        """
        if self.async_mode is not None:
            return self.async_mode
        
        # Check if any of the core methods are async
        return (
            asyncio.iscoroutinefunction(self.prep) or
            asyncio.iscoroutinefunction(self.exec) or
            asyncio.iscoroutinefunction(self.post)
        )
    
    def _log_execution_start(self, shared: Dict[str, Any], operation: str):
        """Log the start of node execution."""
        logger.info(
            f"Starting {operation} execution for node: {self.node_id}",
            extra={
                "action": f"node_{operation}_start",
                "node_id": self.node_id,
                "async_mode": self._detect_async_mode(),
                "shared_keys": list(shared.keys()) if shared else []
            }
        )
    
    def _log_execution_complete(self, operation: str, duration: float, result_summary: str = ""):
        """Log the completion of node execution."""
        logger.info(
            f"Completed {operation} execution for node: {self.node_id} in {duration:.3f}s",
            extra={
                "action": f"node_{operation}_complete",
                "node_id": self.node_id,
                "duration": duration,
                "result_summary": result_summary
            }
        )
    
    def _record_execution_metrics(self, duration: float, success: bool = True):
        """Record execution metrics."""
        self._execution_count += 1
        self._total_execution_time += duration
        self._last_execution_time = duration
        
        # Record metrics
        increment("node_executions_total", tags={
            "node_id": self.node_id,
            "status": "success" if success else "error",
            "async_mode": str(self._detect_async_mode())
        })
        histogram("node_execution_duration", duration, tags={
            "node_id": self.node_id,
            "async_mode": str(self._detect_async_mode())
        })
        gauge("node_last_execution_duration", duration, tags={
            "node_id": self.node_id
        })
    
    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def prep(self, shared: Dict[str, Any]) -> T:
        """
        Prepare data for execution (sync version).
        
        Args:
            shared: Shared context dictionary
            
        Returns:
            Prepared data for exec method
        """
        pass
    
    @abstractmethod
    def exec(self, prep_result: T) -> R:
        """
        Execute the main operation (sync version).
        
        Args:
            prep_result: Data prepared by prep method
            
        Returns:
            Result of the operation
        """
        pass
    
    def post(
        self,
        shared: Dict[str, Any],
        prep_result: T,
        exec_result: R
    ) -> Optional[str]:
        """
        Post-process results and update shared context (sync version).
        
        Args:
            shared: Shared context dictionary
            prep_result: Data from prep method
            exec_result: Result from exec method
            
        Returns:
            ID of next node to execute, or None to end flow
        """
        # Default implementation: store result and continue to next node
        shared[f"{self.node_id}_result"] = exec_result
        return self.get_next_node_id(exec_result)
    
    # Async versions (can be overridden for true async implementations)
    async def aprep(self, shared: Dict[str, Any]) -> T:
        """
        Async version of prep. Default implementation calls sync version.
        """
        if asyncio.iscoroutinefunction(self.prep):
            return await self.prep(shared)
        return self.prep(shared)
    
    async def aexec(self, prep_result: T) -> R:
        """
        Async version of exec. Default implementation calls sync version.
        """
        if asyncio.iscoroutinefunction(self.exec):
            return await self.exec(prep_result)
        return self.exec(prep_result)
    
    async def apost(
        self,
        shared: Dict[str, Any],
        prep_result: T,
        exec_result: R
    ) -> Optional[str]:
        """
        Async version of post. Default implementation calls sync version.
        """
        if asyncio.iscoroutinefunction(self.post):
            return await self.post(shared, prep_result, exec_result)
        return self.post(shared, prep_result, exec_result)
    
    def process(self, shared: Dict[str, Any]) -> Optional[str]:
        """
        Main synchronous processing method.
        
        Args:
            shared: Shared context dictionary
            
        Returns:
            ID of next node to execute, or None to end flow
        """
        if self._detect_async_mode():
            # If async mode is detected, run async version
            logger.warning(
                f"Sync process() called on async-configured node {self.node_id}. "
                "Consider using aprocess() for better performance."
            )
            return asyncio.run(self.aprocess(shared))
        
        return self._sync_process(shared)
    
    async def aprocess(self, shared: Dict[str, Any]) -> Optional[str]:
        """
        Main asynchronous processing method.
        
        Args:
            shared: Shared context dictionary
            
        Returns:
            ID of next node to execute, or None to end flow
        """
        start_time = time.time()
        
        try:
            self._log_execution_start(shared, "async_process")
            
            # Execute the three-phase pipeline
            prep_result = await self.aprep(shared)
            exec_result = await self.aexec(prep_result)
            next_node_id = await self.apost(shared, prep_result, exec_result)
            
            duration = time.time() - start_time
            self._record_execution_metrics(duration, success=True)
            self._log_execution_complete(
                "async_process", 
                duration, 
                f"next_node: {next_node_id}"
            )
            
            return next_node_id
            
        except Exception as e:
            duration = time.time() - start_time
            self._record_execution_metrics(duration, success=False)
            
            logger.error(
                f"Async execution failed for node {self.node_id}: {str(e)}",
                extra={
                    "action": "node_async_process_failed",
                    "node_id": self.node_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration": duration
                }
            )
            
            # Store error in shared context
            shared["error"] = {
                "node_id": self.node_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            raise
    
    def _sync_process(self, shared: Dict[str, Any]) -> Optional[str]:
        """
        Internal synchronous processing implementation.
        
        Args:
            shared: Shared context dictionary
            
        Returns:
            ID of next node to execute, or None to end flow
        """
        start_time = time.time()
        
        try:
            self._log_execution_start(shared, "sync_process")
            
            # Execute the three-phase pipeline
            prep_result = self.prep(shared)
            exec_result = self.exec(prep_result)
            next_node_id = self.post(shared, prep_result, exec_result)
            
            duration = time.time() - start_time
            self._record_execution_metrics(duration, success=True)
            self._log_execution_complete(
                "sync_process", 
                duration, 
                f"next_node: {next_node_id}"
            )
            
            return next_node_id
            
        except Exception as e:
            duration = time.time() - start_time
            self._record_execution_metrics(duration, success=False)
            
            logger.error(
                f"Sync execution failed for node {self.node_id}: {str(e)}",
                extra={
                    "action": "node_sync_process_failed",
                    "node_id": self.node_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration": duration
                }
            )
            
            # Store error in shared context
            shared["error"] = {
                "node_id": self.node_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
            
            raise
    
    # Node chaining support (preserving PocketFlow syntax)
    def __rshift__(self, other: 'UnifiedNode') -> 'UnifiedNode':
        """
        Chain this node to another using >> operator.
        
        Args:
            other: The next node in the chain
            
        Returns:
            The other node (for further chaining)
        """
        self._default_next = other.node_id
        self._next_nodes[other.node_id] = other
        return other
    
    def __sub__(self, condition: str) -> 'NodeBranch':
        """
        Create a conditional branch using - operator.
        
        Args:
            condition: Condition for branching
            
        Returns:
            NodeBranch object for chaining
        """
        return NodeBranch(self, condition)
    
    def get_next_node_id(self, exec_result: R) -> Optional[str]:
        """
        Determine the next node ID based on execution result.
        
        Args:
            exec_result: Result from exec method
            
        Returns:
            ID of next node, or None to end flow
        """
        # Default behavior: use the default next node
        return self._default_next
    
    def add_next_node(self, condition: str, node: 'UnifiedNode'):
        """
        Add a conditional next node.
        
        Args:
            condition: Condition for this branch
            node: Node to execute if condition is met
        """
        self._next_nodes[node.node_id] = node
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """
        Get execution statistics for this node.
        
        Returns:
            Dictionary with execution statistics
        """
        return {
            "node_id": self.node_id,
            "execution_count": self._execution_count,
            "total_execution_time": self._total_execution_time,
            "average_execution_time": (
                self._total_execution_time / self._execution_count 
                if self._execution_count > 0 else 0
            ),
            "last_execution_time": self._last_execution_time,
            "async_mode": self._detect_async_mode()
        }


class NodeBranch:
    """Helper class for conditional node branching."""
    
    def __init__(self, source_node: UnifiedNode, condition: str):
        self.source_node = source_node
        self.condition = condition
    
    def __rshift__(self, target_node: UnifiedNode) -> UnifiedNode:
        """
        Complete the branch by specifying the target node.
        
        Args:
            target_node: Node to execute if condition is met
            
        Returns:
            The target node (for further chaining)
        """
        self.source_node.add_next_node(self.condition, target_node)
        return target_node


class UnifiedBatchNode(UnifiedNode[List[T], List[R]]):
    """
    Unified batch node for processing multiple items.
    
    This node can process multiple items either sequentially (sync mode)
    or concurrently (async mode) while preserving the same interface.
    """
    
    def __init__(
        self,
        async_mode: Optional[bool] = None,
        max_concurrent: int = 5,
        **kwargs
    ):
        """
        Initialize batch node.
        
        Args:
            async_mode: Force sync/async mode
            max_concurrent: Maximum concurrent operations in async mode
            **kwargs: Additional arguments for base class
        """
        super().__init__(async_mode=async_mode, **kwargs)
        self.max_concurrent = max_concurrent
        
        if self._detect_async_mode():
            self._semaphore = asyncio.Semaphore(max_concurrent)
    
    @abstractmethod
    def exec_single(self, item: T) -> R:
        """
        Execute operation on a single item.
        
        Args:
            item: Single item to process
            
        Returns:
            Result for the item
        """
        pass
    
    async def aexec_single(self, item: T) -> R:
        """
        Async version of exec_single.
        """
        if asyncio.iscoroutinefunction(self.exec_single):
            return await self.exec_single(item)
        return self.exec_single(item)
    
    def exec(self, prep_result: List[T]) -> List[R]:
        """
        Execute batch operation synchronously.
        
        Args:
            prep_result: List of items to process
            
        Returns:
            List of results
        """
        if self._detect_async_mode():
            logger.warning(
                f"Sync batch exec() called on async-configured node {self.node_id}"
            )
            return asyncio.run(self.aexec(prep_result))
        
        logger.info(
            f"Processing {len(prep_result)} items synchronously",
            extra={
                "action": "batch_sync_start",
                "node_id": self.node_id,
                "item_count": len(prep_result)
            }
        )
        
        results = []
        for i, item in enumerate(prep_result):
            try:
                result = self.exec_single(item)
                results.append(result)
                logger.debug(f"Processed item {i + 1}/{len(prep_result)}")
            except Exception as e:
                logger.error(f"Failed to process item {i + 1}: {str(e)}")
                results.append(e)
        
        return results
    
    async def aexec(self, prep_result: List[T]) -> List[R]:
        """
        Execute batch operation asynchronously with concurrency control.
        
        Args:
            prep_result: List of items to process
            
        Returns:
            List of results
        """
        logger.info(
            f"Processing {len(prep_result)} items asynchronously (max concurrent: {self.max_concurrent})",
            extra={
                "action": "batch_async_start",
                "node_id": self.node_id,
                "item_count": len(prep_result),
                "max_concurrent": self.max_concurrent
            }
        )
        
        async def process_with_semaphore(item: T, index: int) -> R:
            """Process a single item with semaphore control."""
            async with self._semaphore:
                try:
                    logger.debug(f"Processing item {index + 1}/{len(prep_result)}")
                    result = await self.aexec_single(item)
                    return result
                except Exception as e:
                    logger.error(f"Failed to process item {index + 1}: {str(e)}")
                    raise
        
        # Process all items concurrently
        tasks = [
            process_with_semaphore(item, i)
            for i, item in enumerate(prep_result)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results


class UnifiedFlow:
    """
    Unified flow orchestrator supporting both sync and async nodes.
    
    This flow can execute a sequence of nodes, automatically detecting
    whether to use sync or async execution based on the node types.
    """
    
    def __init__(
        self,
        start_node: Optional[UnifiedNode] = None,
        async_mode: Optional[bool] = None
    ):
        """
        Initialize the unified flow.
        
        Args:
            start_node: Initial node to execute
            async_mode: Force sync/async mode. If None, auto-detect from nodes.
        """
        self.start_node = start_node
        self.async_mode = async_mode
        self.nodes: Dict[str, UnifiedNode] = {}
        
        if start_node:
            self.add_node(start_node)
    
    def add_node(self, node: UnifiedNode):
        """Add a node to the flow."""
        self.nodes[node.node_id] = node
    
    def _detect_flow_async_mode(self) -> bool:
        """Detect if the flow should run in async mode."""
        if self.async_mode is not None:
            return self.async_mode
        
        # Check if any node requires async mode
        return any(node._detect_async_mode() for node in self.nodes.values())
    
    def execute(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the flow synchronously.
        
        Args:
            shared: Initial shared context
            
        Returns:
            Final shared context
        """
        if self._detect_flow_async_mode():
            logger.warning("Sync execute() called on async-configured flow")
            return asyncio.run(self.aexecute(shared))
        
        return self._sync_execute(shared)
    
    async def aexecute(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the flow asynchronously.
        
        Args:
            shared: Initial shared context
            
        Returns:
            Final shared context
        """
        if not self.start_node:
            raise ValueError("No start node specified")
        
        current_node_id = self.start_node.node_id
        execution_path = []
        
        logger.info(
            f"Starting async flow execution from node: {current_node_id}",
            extra={
                "action": "flow_async_start",
                "start_node": current_node_id,
                "total_nodes": len(self.nodes)
            }
        )
        
        while current_node_id:
            if current_node_id not in self.nodes:
                logger.error(f"Node {current_node_id} not found in flow")
                break
            
            execution_path.append(current_node_id)
            current_node = self.nodes[current_node_id]
            
            try:
                current_node_id = await current_node.aprocess(shared)
            except Exception as e:
                logger.error(
                    f"Flow execution failed at node {current_node_id}: {str(e)}",
                    extra={
                        "action": "flow_async_failed",
                        "failed_node": current_node_id,
                        "execution_path": execution_path,
                        "error": str(e)
                    }
                )
                break
        
        logger.info(
            f"Completed async flow execution. Path: {' -> '.join(execution_path)}",
            extra={
                "action": "flow_async_complete",
                "execution_path": execution_path,
                "final_shared_keys": list(shared.keys())
            }
        )
        
        return shared
    
    def _sync_execute(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the flow synchronously."""
        if not self.start_node:
            raise ValueError("No start node specified")
        
        current_node_id = self.start_node.node_id
        execution_path = []
        
        logger.info(
            f"Starting sync flow execution from node: {current_node_id}",
            extra={
                "action": "flow_sync_start",
                "start_node": current_node_id,
                "total_nodes": len(self.nodes)
            }
        )
        
        while current_node_id:
            if current_node_id not in self.nodes:
                logger.error(f"Node {current_node_id} not found in flow")
                break
            
            execution_path.append(current_node_id)
            current_node = self.nodes[current_node_id]
            
            try:
                current_node_id = current_node.process(shared)
            except Exception as e:
                logger.error(
                    f"Flow execution failed at node {current_node_id}: {str(e)}",
                    extra={
                        "action": "flow_sync_failed",
                        "failed_node": current_node_id,
                        "execution_path": execution_path,
                        "error": str(e)
                    }
                )
                break
        
        logger.info(
            f"Completed sync flow execution. Path: {' -> '.join(execution_path)}",
            extra={
                "action": "flow_sync_complete",
                "execution_path": execution_path,
                "final_shared_keys": list(shared.keys())
            }
        )
        
        return shared