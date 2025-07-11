"""
Retry utilities with exponential backoff for API calls.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

import httpx
from requests import exceptions as requests_exceptions

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_JITTER = True

# Exceptions that should trigger retries (legacy - use ASYNC_RETRIABLE_EXCEPTIONS)
RETRIABLE_EXCEPTIONS = (
    requests_exceptions.Timeout,
    requests_exceptions.ConnectionError,
    requests_exceptions.HTTPError,
    requests_exceptions.RequestException,
)

# Async exceptions that should trigger retries
ASYNC_RETRIABLE_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.HTTPStatusError,
    httpx.RequestError,
)


def exponential_backoff_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_delay: float = DEFAULT_MAX_DELAY,
    jitter: bool = DEFAULT_JITTER,
    retriable_exceptions: tuple[type[Exception], ...] = RETRIABLE_EXCEPTIONS,
    retry_on_status_codes: tuple[int, ...] = (500, 502, 503, 504, 429),
) -> Callable:
    """
    Decorator that implements exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        max_delay: Maximum delay between retries
        jitter: Whether to add random jitter to reduce thundering herd
        retriable_exceptions: Tuple of exception types that should trigger retries
        retry_on_status_codes: HTTP status codes that should trigger retries

    Returns:
        Decorator function that applies retry logic
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Check if we have a response object with status code
                    if (
                        hasattr(result, "status_code")
                        and result.status_code in retry_on_status_codes
                    ):
                        if attempt < max_retries:
                            delay = _calculate_delay(
                                attempt, initial_delay, backoff_factor, max_delay, jitter
                            )
                            logger.warning(
                                f"HTTP {result.status_code} received, retrying in {delay:.2f}s "
                                f"(attempt {attempt + 1}/{max_retries + 1})",
                                extra={
                                    "function": getattr(func, "__name__", "unknown"),
                                    "attempt": attempt + 1,
                                    "max_retries": max_retries + 1,
                                    "delay": delay,
                                    "status_code": result.status_code,
                                    "action": "retry_on_status_code",
                                },
                            )
                            time.sleep(delay)
                            continue

                    # Success case
                    if attempt > 0:
                        logger.info(
                            f"Function {getattr(func, '__name__', 'unknown')} succeeded after {attempt} retries",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "attempts": attempt + 1,
                                "action": "retry_success",
                            },
                        )
                    return result

                except retriable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = _calculate_delay(
                            attempt, initial_delay, backoff_factor, max_delay, jitter
                        )
                        logger.warning(
                            f"Exception {type(e).__name__} in {getattr(func, '__name__', 'unknown')}, retrying in {delay:.2f}s "
                            f"(attempt {attempt + 1}/{max_retries + 1}): {str(e)}",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "attempt": attempt + 1,
                                "max_retries": max_retries + 1,
                                "delay": delay,
                                "exception": str(e),
                                "exception_type": type(e).__name__,
                                "action": "retry_on_exception",
                            },
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Function {getattr(func, '__name__', 'unknown')} failed after {max_retries} retries: {str(e)}",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "max_retries": max_retries,
                                "exception": str(e),
                                "exception_type": type(e).__name__,
                                "action": "retry_exhausted",
                            },
                        )
                        raise
                except Exception as e:
                    # Non-retriable exceptions should be raised immediately
                    logger.error(
                        f"Non-retriable exception in {getattr(func, '__name__', 'unknown')}: {str(e)}",
                        extra={
                            "function": getattr(func, "__name__", "unknown"),
                            "exception": str(e),
                            "exception_type": type(e).__name__,
                            "action": "non_retriable_exception",
                        },
                    )
                    raise

            # This should never be reached due to the raise in the except block
            # But adding it for completeness
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def _calculate_delay(
    attempt: int, initial_delay: float, backoff_factor: float, max_delay: float, jitter: bool
) -> float:
    """
    Calculate delay for exponential backoff with optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        initial_delay: Initial delay in seconds
        backoff_factor: Factor to multiply delay by
        max_delay: Maximum delay allowed
        jitter: Whether to add random jitter

    Returns:
        Calculated delay in seconds
    """
    delay = initial_delay * (backoff_factor**attempt)
    delay = min(delay, max_delay)

    if jitter:
        # Add ±25% random jitter to prevent thundering herd
        jitter_amount = delay * 0.25
        delay += random.uniform(-jitter_amount, jitter_amount)
        delay = max(0.1, delay)  # Ensure minimum delay

    return delay


def async_exponential_backoff_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_delay: float = DEFAULT_MAX_DELAY,
    jitter: bool = DEFAULT_JITTER,
    retriable_exceptions: tuple[type[Exception], ...] = ASYNC_RETRIABLE_EXCEPTIONS,
    retry_on_status_codes: tuple[int, ...] = (500, 502, 503, 504, 429),
) -> Callable:
    """
    Async decorator that implements exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Factor to multiply delay by after each retry
        max_delay: Maximum delay between retries
        jitter: Whether to add random jitter to reduce thundering herd
        retriable_exceptions: Tuple of exception types that should trigger retries
        retry_on_status_codes: HTTP status codes that should trigger retries

    Returns:
        Async decorator function that applies retry logic
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)

                    # Check if we have a response object with status code
                    if (
                        hasattr(result, "status_code")
                        and result.status_code in retry_on_status_codes
                    ):
                        if attempt < max_retries:
                            delay = _calculate_delay(
                                attempt, initial_delay, backoff_factor, max_delay, jitter
                            )
                            logger.warning(
                                f"Async HTTP {result.status_code} received, retrying in {delay:.2f}s "
                                f"(attempt {attempt + 1}/{max_retries + 1})",
                                extra={
                                    "function": getattr(func, "__name__", "unknown"),
                                    "attempt": attempt + 1,
                                    "max_retries": max_retries + 1,
                                    "delay": delay,
                                    "status_code": result.status_code,
                                    "action": "async_retry_on_status_code",
                                },
                            )
                            await asyncio.sleep(delay)
                            continue

                    # Success case
                    if attempt > 0:
                        logger.info(
                            f"Async function {getattr(func, '__name__', 'unknown')} succeeded after {attempt} retries",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "attempts": attempt + 1,
                                "action": "async_retry_success",
                            },
                        )
                    return result

                except retriable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = _calculate_delay(
                            attempt, initial_delay, backoff_factor, max_delay, jitter
                        )
                        logger.warning(
                            f"Async exception {type(e).__name__} in {getattr(func, '__name__', 'unknown')}, retrying in {delay:.2f}s "
                            f"(attempt {attempt + 1}/{max_retries + 1}): {str(e)}",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "attempt": attempt + 1,
                                "max_retries": max_retries + 1,
                                "delay": delay,
                                "exception": str(e),
                                "exception_type": type(e).__name__,
                                "action": "async_retry_on_exception",
                            },
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Async function {getattr(func, '__name__', 'unknown')} failed after {max_retries} retries: {str(e)}",
                            extra={
                                "function": getattr(func, "__name__", "unknown"),
                                "max_retries": max_retries,
                                "exception": str(e),
                                "exception_type": type(e).__name__,
                                "action": "async_retry_exhausted",
                            },
                        )
                        raise
                except Exception as e:
                    # Non-retriable exceptions should be raised immediately
                    logger.error(
                        f"Non-retriable async exception in {getattr(func, '__name__', 'unknown')}: {str(e)}",
                        extra={
                            "function": getattr(func, "__name__", "unknown"),
                            "exception": str(e),
                            "exception_type": type(e).__name__,
                            "action": "async_non_retriable_exception",
                        },
                    )
                    raise

            # This should never be reached due to the raise in the except block
            # But adding it for completeness
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def get_retry_stats(func: Callable) -> dict:
    """
    Get retry statistics for a decorated function.

    Args:
        func: The decorated function

    Returns:
        Dictionary with retry statistics
    """
    if not hasattr(func, "_retry_stats"):
        return {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_retries": 0,
            "average_retries": 0.0,
        }

    stats = cast(dict, func._retry_stats)
    total_calls = stats.get("total_calls", 0)
    return {
        "total_calls": total_calls,
        "successful_calls": stats.get("successful_calls", 0),
        "failed_calls": stats.get("failed_calls", 0),
        "total_retries": stats.get("total_retries", 0),
        "average_retries": stats.get("total_retries", 0) / total_calls if total_calls > 0 else 0.0,
    }
