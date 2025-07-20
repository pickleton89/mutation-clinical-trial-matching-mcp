"""
Shared utilities for unified sync/async operations.

This module contains common validation, error handling, and utility functions
that were previously duplicated across sync and async implementations.
"""

import json
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import httpx
import requests
import requests.exceptions

from utils.metrics import gauge, histogram, increment

logger = logging.getLogger(__name__)


# Input Validation Functions
def validate_mutation_input(
    mutation: str,
    min_rank: int | None = None,
    max_rank: int | None = None
) -> dict[str, Any]:
    """
    Unified input validation for mutation queries.

    Args:
        mutation: The mutation string to validate
        min_rank: Minimum rank for results (optional)
        max_rank: Maximum rank for results (optional)

    Returns:
        Dict containing validated parameters or error information
    """
    result = {
        "valid": True,
        "error": None,
        "mutation": mutation,
        "min_rank": min_rank,
        "max_rank": max_rank,
        "warnings": []
    }

    # Validate mutation
    if not mutation or not isinstance(mutation, str) or len(mutation.strip()) == 0:
        logger.error("Error: Mutation must be a non-empty string")
        increment("api_validation_errors", tags={"error_type": "invalid_mutation"})
        result["valid"] = False
        result["error"] = "Mutation must be a non-empty string"
        return result

    result["mutation"] = mutation.strip()

    # Validate min_rank
    if min_rank is not None:
        if not isinstance(min_rank, int) or min_rank < 1:
            logger.warning(f"Invalid min_rank {min_rank}. Setting to 1.")
            increment("api_validation_warnings", tags={"warning_type": "invalid_min_rank"})
            result["min_rank"] = 1
            result["warnings"].append(f"Invalid min_rank {min_rank}, corrected to 1")
        else:
            result["min_rank"] = min_rank

    # Validate max_rank
    if max_rank is not None:
        if not isinstance(max_rank, int) or max_rank < 1:
            logger.warning(f"Invalid max_rank {max_rank}. Setting to None (unlimited).")
            increment("api_validation_warnings", tags={"warning_type": "invalid_max_rank"})
            result["max_rank"] = None
            result["warnings"].append(f"Invalid max_rank {max_rank}, corrected to unlimited")
        else:
            result["max_rank"] = max_rank

    # Validate rank relationship
    if (result["min_rank"] is not None and result["max_rank"] is not None and
        result["min_rank"] > result["max_rank"]):
        logger.warning(f"min_rank ({result['min_rank']}) > max_rank ({result['max_rank']}). Swapping values.")
        increment("api_validation_warnings", tags={"warning_type": "rank_order_corrected"})
        result["min_rank"], result["max_rank"] = result["max_rank"], result["min_rank"]
        result["warnings"].append("min_rank and max_rank were swapped to maintain logical order")

    return result


def validate_llm_input(
    messages: list[dict[str, str]],
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None
) -> dict[str, Any]:
    """
    Unified input validation for LLM queries.

    Args:
        messages: List of message dictionaries
        model: Model name (optional)
        max_tokens: Maximum tokens to generate (optional)
        temperature: Temperature for generation (optional)

    Returns:
        Dict containing validated parameters or error information
    """
    result = {
        "valid": True,
        "error": None,
        "messages": messages,
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "warnings": []
    }

    # Validate messages
    if not messages or not isinstance(messages, list) or len(messages) == 0:
        logger.error("Error: Messages must be a non-empty list")
        increment("llm_validation_errors", tags={"error_type": "invalid_messages"})
        result["valid"] = False
        result["error"] = "Messages must be a non-empty list"
        return result

    # Validate message structure
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            logger.error(f"Error: Message {i} must be a dictionary")
            increment("llm_validation_errors", tags={"error_type": "invalid_message_structure"})
            result["valid"] = False
            result["error"] = f"Message {i} must be a dictionary"
            return result

        if "role" not in message or "content" not in message:
            logger.error(f"Error: Message {i} must have 'role' and 'content' fields")
            increment("llm_validation_errors", tags={"error_type": "missing_message_fields"})
            result["valid"] = False
            result["error"] = f"Message {i} must have 'role' and 'content' fields"
            return result

        if message["role"] not in ["user", "assistant", "system"]:
            logger.warning(f"Message {i} has unusual role: {message['role']}")
            increment("llm_validation_warnings", tags={"warning_type": "unusual_role"})
            result["warnings"].append(f"Message {i} has unusual role: {message['role']}")

    # Validate max_tokens
    if max_tokens is not None:
        if not isinstance(max_tokens, int) or max_tokens < 1:
            logger.warning(f"Invalid max_tokens {max_tokens}. Setting to 1000.")
            increment("llm_validation_warnings", tags={"warning_type": "invalid_max_tokens"})
            result["max_tokens"] = 1000
            result["warnings"].append(f"Invalid max_tokens {max_tokens}, corrected to 1000")

    # Validate temperature
    if temperature is not None:
        if not isinstance(temperature, int | float) or temperature < 0 or temperature > 2:
            logger.warning(f"Invalid temperature {temperature}. Setting to 0.7.")
            increment("llm_validation_warnings", tags={"warning_type": "invalid_temperature"})
            result["temperature"] = 0.7
            result["warnings"].append(f"Invalid temperature {temperature}, corrected to 0.7")

    return result


# Error Handling Functions
def map_http_exception_to_error_response(
    exception: Exception,
    service_name: str,
    default_message: str = "Request failed"
) -> dict[str, Any]:
    """
    Map HTTP exceptions to standardized error responses.

    Args:
        exception: The exception to map
        service_name: Name of the service for metrics tagging
        default_message: Default error message if mapping fails

    Returns:
        Standardized error response dictionary
    """
    error_response = {
        "error": default_message,
        "error_type": type(exception).__name__,
        "error_details": str(exception),
        "studies": [],  # For clinical trials responses
        "retry_after": None
    }

    # Handle requests exceptions (sync)
    if isinstance(exception, requests.exceptions.Timeout):
        error_response["error"] = "Request timed out"
        error_response["retry_after"] = 30
        increment("api_errors", tags={"service": service_name, "error_type": "timeout"})

    elif isinstance(exception, requests.exceptions.ConnectionError):
        error_response["error"] = "Connection failed"
        error_response["retry_after"] = 60
        increment("api_errors", tags={"service": service_name, "error_type": "connection_error"})

    elif isinstance(exception, requests.exceptions.HTTPError):
        if hasattr(exception, 'response') and exception.response is not None:
            status_code = exception.response.status_code
            if status_code == 429:
                error_response["error"] = "Rate limit exceeded"
                error_response["retry_after"] = 60
                increment("api_errors", tags={"service": service_name, "error_type": "rate_limit"})
            elif status_code >= 500:
                error_response["error"] = "Server error"
                error_response["retry_after"] = 120
                increment("api_errors", tags={"service": service_name, "error_type": "server_error"})
            elif status_code >= 400:
                error_response["error"] = "Client error"
                increment("api_errors", tags={"service": service_name, "error_type": "client_error"})
        else:
            increment("api_errors", tags={"service": service_name, "error_type": "http_error"})

    elif isinstance(exception, requests.exceptions.RequestException):
        increment("api_errors", tags={"service": service_name, "error_type": "request_error"})

    # Handle httpx exceptions (async)
    elif isinstance(exception, httpx.TimeoutException):
        error_response["error"] = "Request timed out"
        error_response["retry_after"] = 30
        increment("api_errors", tags={"service": service_name, "error_type": "timeout"})

    elif isinstance(exception, httpx.ConnectError):
        error_response["error"] = "Connection failed"
        error_response["retry_after"] = 60
        increment("api_errors", tags={"service": service_name, "error_type": "connection_error"})

    elif isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        if status_code == 429:
            error_response["error"] = "Rate limit exceeded"
            error_response["retry_after"] = 60
            increment("api_errors", tags={"service": service_name, "error_type": "rate_limit"})
        elif status_code >= 500:
            error_response["error"] = "Server error"
            error_response["retry_after"] = 120
            increment("api_errors", tags={"service": service_name, "error_type": "server_error"})
        elif status_code >= 400:
            error_response["error"] = "Client error"
            increment("api_errors", tags={"service": service_name, "error_type": "client_error"})

    elif isinstance(exception, httpx.RequestError):
        increment("api_errors", tags={"service": service_name, "error_type": "request_error"})

    # Handle JSON parsing errors
    elif isinstance(exception, ValueError) and "JSON" in str(exception):
        error_response["error"] = "Invalid JSON response"
        increment("api_errors", tags={"service": service_name, "error_type": "json_error"})

    # Generic exception handling
    else:
        increment("api_errors", tags={"service": service_name, "error_type": "unknown"})

    logger.error(
        f"HTTP request failed for {service_name}",
        extra={
            "action": "http_request_failed",
            "service": service_name,
            "error": error_response["error"],
            "error_type": error_response["error_type"],
            "error_details": error_response["error_details"]
        }
    )

    return error_response


# Request Timing Utilities
def time_request(service_name: str, operation_name: str = "request"):
    """
    Decorator to time requests and record metrics.

    Args:
        service_name: Name of the service for metrics tagging
        operation_name: Name of the operation for metrics tagging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success metrics
                increment("api_requests_total", tags={
                    "service": service_name,
                    "operation": operation_name,
                    "status": "success"
                })
                histogram("api_request_duration", duration, tags={
                    "service": service_name,
                    "operation": operation_name
                })
                gauge("api_last_request_duration", duration, tags={
                    "service": service_name
                })

                logger.info(
                    f"{service_name} {operation_name} completed successfully",
                    extra={
                        "action": f"{service_name}_{operation_name}_completed",
                        "service": service_name,
                        "operation": operation_name,
                        "duration": duration
                    }
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record error metrics
                increment("api_requests_total", tags={
                    "service": service_name,
                    "operation": operation_name,
                    "status": "error"
                })
                histogram("api_request_duration", duration, tags={
                    "service": service_name,
                    "operation": operation_name,
                    "error": "true"
                })

                logger.error(
                    f"{service_name} {operation_name} failed",
                    extra={
                        "action": f"{service_name}_{operation_name}_failed",
                        "service": service_name,
                        "operation": operation_name,
                        "duration": duration,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )

                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Record success metrics
                increment("api_requests_total", tags={
                    "service": service_name,
                    "operation": operation_name,
                    "status": "success"
                })
                histogram("api_request_duration", duration, tags={
                    "service": service_name,
                    "operation": operation_name
                })
                gauge("api_last_request_duration", duration, tags={
                    "service": service_name
                })

                logger.info(
                    f"{service_name} {operation_name} completed successfully",
                    extra={
                        "action": f"async_{service_name}_{operation_name}_completed",
                        "service": service_name,
                        "operation": operation_name,
                        "duration": duration
                    }
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                # Record error metrics
                increment("api_requests_total", tags={
                    "service": service_name,
                    "operation": operation_name,
                    "status": "error"
                })
                histogram("api_request_duration", duration, tags={
                    "service": service_name,
                    "operation": operation_name,
                    "error": "true"
                })

                logger.error(
                    f"{service_name} {operation_name} failed",
                    extra={
                        "action": f"async_{service_name}_{operation_name}_failed",
                        "service": service_name,
                        "operation": operation_name,
                        "duration": duration,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )

                raise

        # Determine if the function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Response Processing Utilities
def extract_studies_from_response(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract studies list from ClinicalTrials.gov API response.

    Args:
        response_data: Raw response data from API

    Returns:
        List of study dictionaries
    """
    try:
        if "studies" in response_data:
            studies = response_data["studies"]
        elif "Study" in response_data:
            studies = response_data["Study"]
        else:
            studies = []

        if not isinstance(studies, list):
            logger.warning("Studies data is not a list, converting to list")
            studies = [studies] if studies else []

        # Record study count metrics
        gauge("api_studies_returned", len(studies), tags={"service": "clinicaltrials"})

        logger.info(
            f"Extracted {len(studies)} studies from response",
            extra={
                "action": "studies_extracted",
                "study_count": len(studies)
            }
        )

        return studies

    except Exception as e:
        logger.error(
            "Failed to extract studies from response",
            extra={
                "action": "studies_extraction_failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        increment("response_processing_errors", tags={"error_type": "studies_extraction"})
        return []


def process_json_response(
    response_text: str,
    service_name: str,
    expected_fields: list[str] | None = None
) -> dict[str, Any]:
    """
    Process JSON response with error handling and validation.

    Args:
        response_text: Raw response text
        service_name: Name of the service for error tracking
        expected_fields: List of expected fields in response (optional)

    Returns:
        Parsed JSON data or error response
    """
    try:
        data = json.loads(response_text)

        # Validate expected fields if provided
        if expected_fields:
            missing_fields = [field for field in expected_fields if field not in data]
            if missing_fields:
                logger.warning(
                    f"Response missing expected fields: {missing_fields}",
                    extra={
                        "action": "response_validation_warning",
                        "service": service_name,
                        "missing_fields": missing_fields
                    }
                )
                increment("response_validation_warnings", tags={
                    "service": service_name,
                    "warning_type": "missing_fields"
                })

        # Record response size metrics
        gauge("api_response_size", len(response_text), tags={"service": service_name})

        return data

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(
            f"Failed to parse JSON response from {service_name}",
            extra={
                "action": "json_parsing_failed",
                "service": service_name,
                "error": str(e),
                "response_preview": response_text[:200] if response_text else None
            }
        )
        increment("response_processing_errors", tags={
            "service": service_name,
            "error_type": "json_parsing"
        })

        return {
            "error": "Invalid JSON response",
            "error_details": str(e),
            "studies": []
        }


# Configuration Helpers
def get_service_config(service_name: str, config_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Extract service-specific configuration with fallbacks.

    Args:
        service_name: Name of the service
        config_dict: Full configuration dictionary

    Returns:
        Service-specific configuration with defaults
    """
    service_config = config_dict.get(service_name, {})

    # Common defaults for all services
    defaults = {
        "timeout": 30.0,
        "max_retries": 3,
        "retry_delay": 1.0,
        "circuit_breaker_threshold": 5,
        "circuit_breaker_timeout": 60.0
    }

    # Service-specific defaults
    service_defaults = {
        "clinicaltrials": {
            "timeout": 10.0,
            "base_url": "https://clinicaltrials.gov/api/"
        },
        "anthropic": {
            "timeout": 60.0,
            "base_url": "https://api.anthropic.com/",
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1000
        }
    }

    # Merge configurations: defaults < service_defaults < service_config
    final_config = defaults.copy()
    if service_name in service_defaults:
        final_config.update(service_defaults[service_name])
    final_config.update(service_config)

    return final_config


# Session Management Utilities
class SessionManager:
    """Unified session manager for both sync and async HTTP sessions."""

    def __init__(self, async_mode: bool = False):
        self.async_mode = async_mode
        self._sessions = {}

    def get_session(self, service_name: str, **config) -> requests.Session | httpx.AsyncClient:
        """Get or create a session for the specified service."""
        if service_name not in self._sessions:
            if self.async_mode:
                self._sessions[service_name] = self._create_async_session(**config)
            else:
                self._sessions[service_name] = self._create_sync_session(**config)

        return self._sessions[service_name]

    def _create_sync_session(self, **config) -> requests.Session:
        """Create a configured sync session."""
        session = requests.Session()

        if "headers" in config:
            session.headers.update(config["headers"])

        return session

    def _create_async_session(self, **config) -> httpx.AsyncClient:
        """Create a configured async client."""
        client_config = {}

        if "headers" in config:
            client_config["headers"] = config["headers"]

        if "timeout" in config:
            client_config["timeout"] = config["timeout"]

        if "base_url" in config:
            client_config["base_url"] = config["base_url"]

        return httpx.AsyncClient(**client_config)

    def close_all(self):
        """Close all sessions."""
        for session in self._sessions.values():
            if hasattr(session, 'close'):
                session.close()

        self._sessions.clear()

    async def aclose_all(self):
        """Async close all sessions."""
        for session in self._sessions.values():
            if hasattr(session, 'aclose'):
                await session.aclose()
            elif hasattr(session, 'close'):
                session.close()

        self._sessions.clear()
