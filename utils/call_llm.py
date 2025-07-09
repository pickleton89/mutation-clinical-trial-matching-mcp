import os
import json
import time
import logging
from typing import Optional
import requests
from dotenv import load_dotenv
from utils.retry import exponential_backoff_retry
from utils.circuit_breaker import circuit_breaker
from utils.metrics import timer, increment, histogram, gauge
from utils.response_validation import response_validator
from clinicaltrials.config import get_global_config

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# NOTE: This is a legacy sync implementation - use utils.async_call_llm for new code
# Create a session for connection reuse
_session = requests.Session()

def _initialize_session():
    """Initialize session with configuration-based headers."""
    try:
        config = get_global_config()
        _session.headers.update({
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "User-Agent": config.user_agent
        })
    except ValueError:
        # Handle missing configuration gracefully (useful for tests)
        _session.headers.update({
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "User-Agent": "mutation-clinical-trial-matching-mcp/0.1.0 (Clinical Trials MCP Server)"
        })

# Initialize session headers
_initialize_session()


def call_llm(prompt: str) -> str:
    """
    Send a prompt to Claude via Anthropic API and return the response.

    This function uses configuration from the global config system.
    
    NOTE: This is a legacy sync implementation - use utils.async_call_llm for new code
    """
    config = get_global_config()
    
    if not config.anthropic_api_key:
        return "[ERROR: ANTHROPIC_API_KEY environment variable not set]"

    @circuit_breaker(
        name="anthropic_api",
        failure_threshold=config.circuit_breaker_failure_threshold,
        recovery_timeout=config.circuit_breaker_recovery_timeout
    )
    @exponential_backoff_retry(
        max_retries=config.max_retries,
        initial_delay=config.retry_initial_delay,
        backoff_factor=config.retry_backoff_factor,
        max_delay=config.retry_max_delay,
        jitter=config.retry_jitter,
        retry_on_status_codes=(429, 500, 502, 503, 504)
    )
    def _retry_wrapper():
        return _call_llm_impl(prompt, config)
    
    return _retry_wrapper()

@response_validator("anthropic_api")
def _validate_anthropic_response(response_data: dict) -> dict:
    """Validate Anthropic API response structure."""
    return response_data

def _call_llm_impl(prompt: str, config) -> str:
    """
    Internal implementation of LLM call with metrics collection.
    """
    # Track LLM call metrics
    increment("anthropic_api_calls_total", tags={"model": config.anthropic_model})
    histogram("anthropic_api_prompt_length", len(prompt), tags={"model": config.anthropic_model})
    
    with timer("anthropic_api_request", tags={"model": config.anthropic_model}):
        try:
            # Set API key in session headers
            _session.headers["x-api-key"] = config.anthropic_api_key

            data = {
                "model": config.anthropic_model,
                "max_tokens": config.anthropic_max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }

            start_time = time.time()
            logger.info("Sending request to Anthropic API", extra={
                "model": data["model"],
                "max_tokens": data["max_tokens"],
                "prompt_length": len(prompt),
                "action": "llm_request_start"
            })

            response = _session.post(
                config.anthropic_api_url, json=data, timeout=config.anthropic_timeout
            )
            request_duration = time.time() - start_time

            response.raise_for_status()
            response_data = response.json()
            
            # Validate response structure
            _validate_anthropic_response(response_data)
            
            response_text = response_data["content"][0]["text"]
            
            # Record success metrics
            increment("anthropic_api_success", tags={"model": config.anthropic_model})
            histogram("anthropic_api_request_duration", request_duration, tags={"model": config.anthropic_model})
            histogram("anthropic_api_response_length", len(response_text), tags={"model": config.anthropic_model})
            gauge("anthropic_api_last_request_duration", request_duration)
            gauge("anthropic_api_last_response_length", len(response_text))
            
            logger.info(f"Anthropic API request completed in {request_duration:.2f}s", extra={
                "model": data["model"],
                "request_duration": request_duration,
                "prompt_length": len(prompt),
                "response_length": len(response_text),
                "action": "llm_request_success"
            })
            
            return response_text
        except requests.exceptions.RequestException as e:
            request_duration = time.time() - start_time
            increment("anthropic_api_errors", tags={"error_type": "request_exception", "model": config.anthropic_model})
            histogram("anthropic_api_request_duration", request_duration, tags={"model": config.anthropic_model, "error": "request_exception"})
            logger.error(f"Anthropic API request failed: {str(e)}", extra={
                "model": data.get("model", "unknown"),
                "request_duration": request_duration,
                "prompt_length": len(prompt),
                "error": str(e),
                "action": "llm_request_error"
            })
            return f"[API ERROR: {str(e)}]"
        except Exception as e:
            request_duration = time.time() - start_time
            increment("anthropic_api_errors", tags={"error_type": "unexpected_error", "model": config.anthropic_model})
            histogram("anthropic_api_request_duration", request_duration, tags={"model": config.anthropic_model, "error": "unexpected"})
            logger.error(f"Unexpected error in LLM call: {str(e)}", extra={
                "model": data.get("model", "unknown"),
                "request_duration": request_duration,
                "prompt_length": len(prompt),
                "error": str(e),
                "action": "llm_request_unexpected_error"
            })
            return f"[API ERROR: {str(e)}]"


if __name__ == "__main__":
    prompt = "What is the meaning of life?"
    print(call_llm(prompt))
