"""
Optimized batch processing utilities for async operations.

This module provides advanced batch processing capabilities with:
- Intelligent batch size optimization
- Connection reuse across batch operations
- Adaptive rate limiting
- Comprehensive metrics and monitoring
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from utils.async_semaphore_manager import SemaphoreContext
from utils.metrics import gauge, histogram, increment

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor:
    """
    Advanced batch processor with intelligent batching and rate limiting.

    Features:
    - Adaptive batch sizing based on response times
    - Connection reuse optimization
    - Comprehensive error handling and recovery
    - Detailed metrics collection
    """

    def __init__(
        self,
        service_name: str,
        operation_name: str,
        max_batch_size: int = 10,
        max_concurrent: int = 5,
        adaptive_sizing: bool = True,
        min_batch_size: int = 1,
        target_latency_ms: float = 1000.0,
    ):
        """
        Initialize the batch processor.

        Args:
            service_name: Name of the service for metrics and semaphore management
            operation_name: Name of the operation for logging and metrics
            max_batch_size: Maximum items to process in a single batch
            max_concurrent: Maximum concurrent batch operations
            adaptive_sizing: Whether to adaptively adjust batch sizes
            min_batch_size: Minimum batch size for adaptive sizing
            target_latency_ms: Target latency for adaptive batch sizing
        """
        self.service_name = service_name
        self.operation_name = operation_name
        self.max_batch_size = max_batch_size
        self.max_concurrent = max_concurrent
        self.adaptive_sizing = adaptive_sizing
        self.min_batch_size = min_batch_size
        self.target_latency_ms = target_latency_ms

        # Adaptive sizing state
        self.current_batch_size = max_batch_size
        self.recent_latencies = []
        self.max_latency_samples = 10

        # Performance metrics
        self.total_processed = 0
        self.total_errors = 0
        self.batch_count = 0

    async def process_batch(
        self,
        items: list[T],
        processor_func: Callable[[T], Awaitable[R]],
        error_handler: Callable[[T, Exception], Awaitable[R]] | None = None,
    ) -> list[R]:
        """
        Process a batch of items with optimal concurrency and error handling.

        Args:
            items: List of items to process
            processor_func: Async function to process each item
            error_handler: Optional error handler function

        Returns:
            List of results in the same order as input items
        """
        if not items:
            return []

        start_time = time.time()

        # Determine optimal batch size
        if self.adaptive_sizing:
            batch_size = self._calculate_optimal_batch_size(len(items))
        else:
            batch_size = min(self.current_batch_size, len(items))

        logger.info(
            f"Starting batch processing: {len(items)} items with batch size {batch_size}",
            extra={
                "service": self.service_name,
                "operation": self.operation_name,
                "total_items": len(items),
                "batch_size": batch_size,
                "max_concurrent": self.max_concurrent,
                "action": "batch_start",
            },
        )

        # Track batch metrics
        increment(
            "batch_processor_batches_total",
            tags={"service": self.service_name, "operation": self.operation_name},
        )
        gauge(
            "batch_processor_batch_size",
            batch_size,
            tags={"service": self.service_name, "operation": self.operation_name},
        )

        # Create batches
        batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

        # Process batches concurrently
        results = []
        batch_tasks = []

        for batch_idx, batch in enumerate(batches):
            task = self._process_single_batch(batch, batch_idx, processor_func, error_handler)
            batch_tasks.append(task)

        # Execute batches with concurrency limit
        batch_results = await self._execute_batches_concurrently(batch_tasks)

        # Flatten results maintaining order
        for batch_result in batch_results:
            results.extend(batch_result)

        # Update performance metrics
        total_duration = time.time() - start_time
        self.total_processed += len(items)
        self.batch_count += 1

        # Update adaptive sizing
        if self.adaptive_sizing:
            self._update_adaptive_sizing(total_duration, len(items))

        # Record comprehensive metrics
        histogram(
            "batch_processor_duration",
            total_duration,
            tags={"service": self.service_name, "operation": self.operation_name},
        )
        histogram(
            "batch_processor_items_per_second",
            len(items) / total_duration,
            tags={"service": self.service_name, "operation": self.operation_name},
        )
        gauge(
            "batch_processor_total_processed",
            self.total_processed,
            tags={"service": self.service_name, "operation": self.operation_name},
        )

        logger.info(
            f"Batch processing completed: {len(items)} items in {total_duration:.2f}s",
            extra={
                "service": self.service_name,
                "operation": self.operation_name,
                "total_items": len(items),
                "duration": total_duration,
                "items_per_second": len(items) / total_duration,
                "batch_count": len(batches),
                "action": "batch_complete",
            },
        )

        return results

    async def _process_single_batch(
        self,
        batch: list[T],
        batch_idx: int,
        processor_func: Callable[[T], Awaitable[R]],
        error_handler: Callable[[T, Exception], Awaitable[R]] | None = None,
    ) -> list[R]:
        """Process a single batch of items."""
        batch_start_time = time.time()

        async def _process_item_with_error_handling(item: T) -> R:
            try:
                return await processor_func(item)
            except Exception as e:
                self.total_errors += 1
                increment(
                    "batch_processor_errors_total",
                    tags={
                        "service": self.service_name,
                        "operation": self.operation_name,
                        "error_type": type(e).__name__,
                    },
                )

                if error_handler:
                    return await error_handler(item, e)
                else:
                    logger.error(
                        f"Error processing item in batch {batch_idx}: {e}",
                        extra={
                            "service": self.service_name,
                            "operation": self.operation_name,
                            "batch_idx": batch_idx,
                            "error": str(e),
                            "action": "batch_item_error",
                        },
                    )
                    raise

        # Process batch items concurrently with semaphore control
        async with SemaphoreContext(self.service_name, f"{self.operation_name}_batch"):
            tasks = [_process_item_with_error_handling(item) for item in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any remaining exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Unhandled exception in batch {batch_idx}, item {i}: {result}",
                    extra={
                        "service": self.service_name,
                        "operation": self.operation_name,
                        "batch_idx": batch_idx,
                        "item_idx": i,
                        "error": str(result),
                        "action": "batch_item_exception",
                    },
                )
                # Re-raise or provide default value based on error handling strategy
                if error_handler is None:
                    raise result
                else:
                    # If we have an error handler, we should have handled this already
                    # This is a fallback for unexpected exceptions
                    processed_results.append(None)
            else:
                processed_results.append(result)

        batch_duration = time.time() - batch_start_time
        histogram(
            "batch_processor_single_batch_duration",
            batch_duration,
            tags={"service": self.service_name, "operation": self.operation_name},
        )

        return processed_results

    async def _execute_batches_concurrently(
        self, batch_tasks: list[Awaitable[list[R]]]
    ) -> list[list[R]]:
        """Execute batch tasks with concurrency control."""
        # Use semaphore to limit concurrent batch operations
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _execute_with_semaphore(task: Awaitable[list[R]]) -> list[R]:
            async with semaphore:
                return await task

        # Execute all batches concurrently
        controlled_tasks = [_execute_with_semaphore(task) for task in batch_tasks]
        return await asyncio.gather(*controlled_tasks)

    def _calculate_optimal_batch_size(self, total_items: int) -> int:
        """Calculate optimal batch size based on recent performance."""
        if not self.recent_latencies:
            return min(self.current_batch_size, total_items)

        # Calculate average latency
        avg_latency = sum(self.recent_latencies) / len(self.recent_latencies)

        # Adjust batch size based on latency
        if avg_latency > self.target_latency_ms:
            # Reduce batch size if latency is too high
            new_size = max(self.min_batch_size, int(self.current_batch_size * 0.8))
        elif avg_latency < self.target_latency_ms * 0.5:
            # Increase batch size if latency is very low
            new_size = min(self.max_batch_size, int(self.current_batch_size * 1.2))
        else:
            # Keep current size if latency is in target range
            new_size = self.current_batch_size

        self.current_batch_size = min(new_size, total_items)

        logger.debug(
            f"Adaptive batch sizing: {self.current_batch_size} (avg_latency: {avg_latency:.2f}ms)",
            extra={
                "service": self.service_name,
                "operation": self.operation_name,
                "current_batch_size": self.current_batch_size,
                "avg_latency": avg_latency,
                "target_latency": self.target_latency_ms,
                "action": "adaptive_sizing",
            },
        )

        return self.current_batch_size

    def _update_adaptive_sizing(self, duration: float, items_count: int):
        """Update adaptive sizing based on recent performance."""
        latency_per_item = (duration * 1000) / items_count  # Convert to ms per item

        self.recent_latencies.append(latency_per_item)
        if len(self.recent_latencies) > self.max_latency_samples:
            self.recent_latencies.pop(0)

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics for the batch processor."""
        return {
            "total_processed": self.total_processed,
            "total_errors": self.total_errors,
            "batch_count": self.batch_count,
            "current_batch_size": self.current_batch_size,
            "error_rate": self.total_errors / max(self.total_processed, 1),
            "avg_latency_ms": sum(self.recent_latencies) / len(self.recent_latencies)
            if self.recent_latencies
            else 0,
            "configuration": {
                "max_batch_size": self.max_batch_size,
                "max_concurrent": self.max_concurrent,
                "adaptive_sizing": self.adaptive_sizing,
                "target_latency_ms": self.target_latency_ms,
            },
        }


# Convenience function for simple batch processing
async def process_batch_simple(
    items: list[T],
    processor_func: Callable[[T], Awaitable[R]],
    service_name: str = "default",
    operation_name: str = "batch_process",
    max_concurrent: int = 5,
) -> list[R]:
    """
    Simple batch processing function for basic use cases.

    Args:
        items: List of items to process
        processor_func: Async function to process each item
        service_name: Service name for metrics
        operation_name: Operation name for metrics
        max_concurrent: Maximum concurrent operations

    Returns:
        List of results in the same order as input items
    """
    processor = BatchProcessor(
        service_name=service_name,
        operation_name=operation_name,
        max_concurrent=max_concurrent,
        adaptive_sizing=False,  # Keep it simple for the basic function
    )

    return await processor.process_batch(items, processor_func)
