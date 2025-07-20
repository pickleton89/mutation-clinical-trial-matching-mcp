"""
Circuit Breaker Pattern Implementation for API Resilience.

This module implements the Circuit Breaker pattern to improve API resilience by:
- Failing fast when an API consistently fails
- Automatic recovery after a cool-down period
- Configurable failure threshold and recovery timeout
"""

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

# Import metrics at module level with fallback
try:
    from utils.metrics import gauge, increment

    _metrics_available = True
except ImportError:
    _metrics_available = False

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""

    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    state_changes: int = 0
    total_calls: int = 0


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, name: str, failure_count: int, last_failure_time: float | None = None):
        self.name = name
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time

        if last_failure_time:
            time_since_failure = time.time() - last_failure_time
            super().__init__(
                f"Circuit breaker '{name}' is OPEN. "
                f"Failure count: {failure_count}, "
                f"Last failure: {time_since_failure:.1f}s ago"
            )
        else:
            super().__init__(f"Circuit breaker '{name}' is OPEN. Failure count: {failure_count}")


class CircuitBreaker(Generic[T]):
    """
    Circuit Breaker implementation for API resilience.

    The circuit breaker monitors API calls and transitions between states:
    - CLOSED: Normal operation, calls are allowed
    - OPEN: Circuit is open, calls fail fast
    - HALF_OPEN: Testing if service has recovered

    Args:
        name: Name of the circuit breaker (for logging/identification)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before transitioning to HALF_OPEN
        success_threshold: Number of successes in HALF_OPEN to close circuit
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self._state = CircuitBreakerState.CLOSED
        self._stats = CircuitBreakerStats()
        self._lock = Lock()

        logger.info(
            f"Circuit breaker '{name}' initialized",
            extra={
                "circuit_breaker_name": name,
                "failure_threshold": failure_threshold,
                "recovery_timeout": recovery_timeout,
                "success_threshold": success_threshold,
                "action": "circuit_breaker_initialized",
            },
        )

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self._stats

    def _can_attempt_call(self) -> bool:
        """Check if a call can be attempted based on current state."""
        with self._lock:
            if self._state == CircuitBreakerState.CLOSED:
                return True

            if self._state == CircuitBreakerState.HALF_OPEN:
                return True

            if self._state == CircuitBreakerState.OPEN:
                # Check if recovery timeout has elapsed
                if (
                    self._stats.last_failure_time
                    and time.time() - self._stats.last_failure_time >= self.recovery_timeout
                ):
                    self._transition_to_half_open()
                    return True
                return False

            return False

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state."""
        self._state = CircuitBreakerState.HALF_OPEN
        self._stats.state_changes += 1

        # Record metrics if available
        if _metrics_available:
            increment(
                "circuit_breaker_state_changes", tags={"name": self.name, "new_state": "half_open"}
            )
            gauge(f"circuit_breaker_state_{self.name}", 1)  # 1 for HALF_OPEN

        logger.info(
            f"Circuit breaker '{self.name}' transitioned to HALF_OPEN",
            extra={
                "circuit_breaker_name": self.name,
                "new_state": "half_open",
                "failure_count": self._stats.failure_count,
                "action": "circuit_breaker_state_change",
            },
        )

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitBreakerState.OPEN
        self._stats.state_changes += 1

        # Record metrics if available
        if _metrics_available:
            increment(
                "circuit_breaker_state_changes", tags={"name": self.name, "new_state": "open"}
            )
            increment("circuit_breaker_open_events", tags={"name": self.name})
            gauge(f"circuit_breaker_state_{self.name}", 2)  # 2 for OPEN

        logger.warning(
            f"Circuit breaker '{self.name}' transitioned to OPEN",
            extra={
                "circuit_breaker_name": self.name,
                "new_state": "open",
                "failure_count": self._stats.failure_count,
                "failure_threshold": self.failure_threshold,
                "action": "circuit_breaker_state_change",
            },
        )

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitBreakerState.CLOSED
        self._stats.state_changes += 1
        self._stats.failure_count = 0  # Reset failure count

        # Record metrics if available
        if _metrics_available:
            increment(
                "circuit_breaker_state_changes", tags={"name": self.name, "new_state": "closed"}
            )
            increment("circuit_breaker_recovery_events", tags={"name": self.name})
            gauge(f"circuit_breaker_state_{self.name}", 0)  # 0 for CLOSED

        logger.info(
            f"Circuit breaker '{self.name}' transitioned to CLOSED",
            extra={
                "circuit_breaker_name": self.name,
                "new_state": "closed",
                "success_count": self._stats.success_count,
                "action": "circuit_breaker_state_change",
            },
        )

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.success_count += 1
            self._stats.last_success_time = time.time()

            # Record metrics if available
            if _metrics_available:
                increment("circuit_breaker_success_calls", tags={"name": self.name})
                gauge(f"circuit_breaker_success_count_{self.name}", self._stats.success_count)

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._stats.success_count >= self.success_threshold:
                    self._transition_to_closed()

    def _record_failure(self, exception: Exception) -> None:
        """Record a failed call."""
        with self._lock:
            self._stats.failure_count += 1
            self._stats.last_failure_time = time.time()

            # Record metrics if available
            if _metrics_available:
                increment("circuit_breaker_failure_calls", tags={"name": self.name})
                gauge(f"circuit_breaker_failure_count_{self.name}", self._stats.failure_count)

            if self._state == CircuitBreakerState.HALF_OPEN:
                # Transition back to OPEN on any failure in HALF_OPEN
                self._transition_to_open()
            elif self._state == CircuitBreakerState.CLOSED:
                # Check if we should transition to OPEN
                if self._stats.failure_count >= self.failure_threshold:
                    self._transition_to_open()

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            CircuitBreakerError: If circuit breaker is open
            Any exception raised by the function
        """
        with self._lock:
            self._stats.total_calls += 1

        # Record metrics if available
        if _metrics_available:
            increment("circuit_breaker_total_calls", tags={"name": self.name})
            gauge(f"circuit_breaker_total_calls_{self.name}", self._stats.total_calls)

        if not self._can_attempt_call():
            if _metrics_available:
                increment("circuit_breaker_rejected_calls", tags={"name": self.name})
            raise CircuitBreakerError(
                self.name, self._stats.failure_count, self._stats.last_failure_time
            )

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator interface for circuit breaker.

        Args:
            func: Function to protect with circuit breaker

        Returns:
            Wrapped function with circuit breaker protection
        """

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.call(func, *args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._stats = CircuitBreakerStats()

            logger.info(
                f"Circuit breaker '{self.name}' reset",
                extra={"circuit_breaker_name": self.name, "action": "circuit_breaker_reset"},
            )


# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = Lock()


def get_circuit_breaker(
    name: str, failure_threshold: int = 5, recovery_timeout: int = 60, success_threshold: int = 1
) -> CircuitBreaker:
    """
    Get or create a circuit breaker instance.

    Args:
        name: Name of the circuit breaker
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before transitioning to HALF_OPEN
        success_threshold: Number of successes in HALF_OPEN to close circuit

    Returns:
        CircuitBreaker instance
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                success_threshold=success_threshold,
            )
        return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers (useful for testing)."""
    with _registry_lock:
        for cb in _circuit_breakers.values():
            cb.reset()
        _circuit_breakers.clear()


def get_all_circuit_breaker_stats() -> dict[str, CircuitBreakerStats]:
    """
    Get statistics for all circuit breakers.

    Returns:
        Dictionary mapping circuit breaker names to their statistics
    """
    with _registry_lock:
        return {name: cb.stats for name, cb in _circuit_breakers.items()}


def circuit_breaker(
    name: str, failure_threshold: int = 5, recovery_timeout: int = 60, success_threshold: int = 1
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to add circuit breaker protection to a function.

    Args:
        name: Name of the circuit breaker
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before transitioning to HALF_OPEN
        success_threshold: Number of successes in HALF_OPEN to close circuit

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cb = get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
        )
        return cb(func)

    return decorator


def async_circuit_breaker(
    name: str, failure_threshold: int = 5, recovery_timeout: int = 60, success_threshold: int = 1
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Async decorator to add circuit breaker protection to an async function.

    Args:
        name: Name of the circuit breaker
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before transitioning to HALF_OPEN
        success_threshold: Number of successes in HALF_OPEN to close circuit

    Returns:
        Async decorator function
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        cb = get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            with cb._lock:
                cb._stats.total_calls += 1

            # Record metrics if available
            if _metrics_available:
                increment("circuit_breaker_total_calls", tags={"name": cb.name})
                gauge(f"circuit_breaker_total_calls_{cb.name}", cb._stats.total_calls)

            if not cb._can_attempt_call():
                if _metrics_available:
                    increment("circuit_breaker_rejected_calls", tags={"name": cb.name})
                raise CircuitBreakerError(
                    cb.name, cb._stats.failure_count, cb._stats.last_failure_time
                )

            try:
                result = await func(*args, **kwargs)
                cb._record_success()
                return result
            except Exception as e:
                cb._record_failure(e)
                raise

        return async_wrapper

    return decorator
