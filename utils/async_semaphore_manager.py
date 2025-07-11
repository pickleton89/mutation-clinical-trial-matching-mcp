"""
Async semaphore manager for concurrent request rate limiting.

This module provides centralized semaphore management for controlling
concurrent requests across different services and operations.
"""

import asyncio
import logging

from clinicaltrials.config import get_global_config

logger = logging.getLogger(__name__)

# Global semaphores for different services
_semaphores: dict[str, asyncio.Semaphore] = {}
_semaphore_lock = asyncio.Lock()


class AsyncSemaphoreManager:
    """
    Centralized manager for async semaphores to control concurrent operations.

    This class provides:
    - Per-service semaphore management
    - Global and per-host concurrency limits
    - Metrics collection for semaphore usage
    - Dynamic semaphore configuration
    """

    @staticmethod
    async def get_semaphore(service: str, custom_limit: int | None = None) -> asyncio.Semaphore:
        """
        Get or create a semaphore for a specific service.

        Args:
            service: Service identifier (e.g., 'clinicaltrials', 'anthropic')
            custom_limit: Custom semaphore limit, overrides config

        Returns:
            asyncio.Semaphore: Configured semaphore for the service
        """
        async with _semaphore_lock:
            if service not in _semaphores:
                _semaphores[service] = await AsyncSemaphoreManager._create_semaphore(
                    service, custom_limit
                )
            return _semaphores[service]

    @staticmethod
    async def _create_semaphore(service: str, custom_limit: int | None = None) -> asyncio.Semaphore:
        """
        Create a new semaphore with service-specific configuration.

        Args:
            service: Service identifier
            custom_limit: Custom limit to override config

        Returns:
            asyncio.Semaphore: Configured semaphore
        """
        config = get_global_config()

        # Determine semaphore limit based on service and config
        if custom_limit is not None:
            limit = custom_limit
        elif service == "clinicaltrials":
            limit = config.max_concurrent_per_host
        elif service == "anthropic":
            limit = config.max_concurrent_per_host
        else:
            limit = config.max_concurrent_requests

        logger.info(
            f"Creating semaphore for service: {service} with limit: {limit}",
            extra={
                "service": service,
                "limit": limit,
                "custom_limit": custom_limit is not None,
                "action": "semaphore_creation",
            },
        )

        return asyncio.Semaphore(limit)

    @staticmethod
    async def get_semaphore_info() -> dict[str, dict]:
        """
        Get information about active semaphores.

        Returns:
            Dict containing semaphore status information
        """
        async with _semaphore_lock:
            return {
                "active_semaphores": list(_semaphores.keys()),
                "semaphore_count": len(_semaphores),
                "semaphores": {
                    service: {
                        "value": semaphore._value,
                        "waiters": len(semaphore._waiters)
                        if hasattr(semaphore, "_waiters") and semaphore._waiters is not None
                        else 0,
                        "locked": semaphore._value == 0,
                    }
                    for service, semaphore in _semaphores.items()
                },
            }

    @staticmethod
    async def reset_semaphore(service: str, new_limit: int | None = None) -> None:
        """
        Reset a semaphore with a new limit.

        Args:
            service: Service identifier
            new_limit: New semaphore limit
        """
        async with _semaphore_lock:
            if service in _semaphores:
                del _semaphores[service]
                logger.info(
                    f"Reset semaphore for service: {service}",
                    extra={"service": service, "new_limit": new_limit, "action": "semaphore_reset"},
                )

            if new_limit is not None:
                _semaphores[service] = await AsyncSemaphoreManager._create_semaphore(
                    service, new_limit
                )

    @staticmethod
    async def clear_all_semaphores() -> None:
        """Clear all semaphores."""
        async with _semaphore_lock:
            _semaphores.clear()
            logger.info("All semaphores cleared", extra={"action": "semaphores_cleared"})


# Convenience functions for common operations
async def get_clinicaltrials_semaphore(custom_limit: int | None = None) -> asyncio.Semaphore:
    """Get the semaphore for clinicaltrials.gov API."""
    return await AsyncSemaphoreManager.get_semaphore("clinicaltrials", custom_limit)


async def get_anthropic_semaphore(custom_limit: int | None = None) -> asyncio.Semaphore:
    """Get the semaphore for Anthropic API."""
    return await AsyncSemaphoreManager.get_semaphore("anthropic", custom_limit)


async def get_global_semaphore(custom_limit: int | None = None) -> asyncio.Semaphore:
    """Get the global semaphore for overall request limiting."""
    return await AsyncSemaphoreManager.get_semaphore("global", custom_limit)


# Context manager for semaphore-controlled operations
class SemaphoreContext:
    """Context manager for semaphore-controlled operations with metrics."""

    def __init__(self, service: str, operation: str, custom_limit: int | None = None):
        self.service = service
        self.operation = operation
        self.custom_limit = custom_limit
        self.semaphore = None

    async def __aenter__(self):
        self.semaphore = await AsyncSemaphoreManager.get_semaphore(self.service, self.custom_limit)

        # Track semaphore acquisition metrics
        try:
            from utils.metrics import gauge, increment

            increment(
                "semaphore_acquisitions_total",
                tags={"service": self.service, "operation": self.operation},
            )
            gauge("semaphore_current_value", self.semaphore._value, tags={"service": self.service})
        except ImportError:
            pass

        await self.semaphore.acquire()

        logger.debug(
            f"Acquired semaphore for {self.service}:{self.operation}",
            extra={
                "service": self.service,
                "operation": self.operation,
                "semaphore_value": self.semaphore._value,
                "action": "semaphore_acquired",
            },
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.semaphore:
            self.semaphore.release()

            # Track semaphore release metrics
            try:
                from utils.metrics import gauge, increment

                increment(
                    "semaphore_releases_total",
                    tags={"service": self.service, "operation": self.operation},
                )
                gauge(
                    "semaphore_current_value", self.semaphore._value, tags={"service": self.service}
                )
            except ImportError:
                pass

            logger.debug(
                f"Released semaphore for {self.service}:{self.operation}",
                extra={
                    "service": self.service,
                    "operation": self.operation,
                    "semaphore_value": self.semaphore._value,
                    "action": "semaphore_released",
                },
            )
