"""
Async version of LLM calling utilities.
"""

import asyncio
import json
import logging
import time
from typing import Optional, List, Dict, Any
import httpx
from utils.retry import async_exponential_backoff_retry
from utils.circuit_breaker import async_circuit_breaker
from utils.metrics import timer, increment, histogram, gauge
from utils.response_validation import response_validator
from clinicaltrials.config import get_global_config

logger = logging.getLogger(__name__)

# Global async client for Anthropic API
_anthropic_async_client: Optional[httpx.AsyncClient] = None

async def get_anthropic_async_client() -> httpx.AsyncClient:
    """Get or create the global async HTTP client for Anthropic API."""
    global _anthropic_async_client
    if _anthropic_async_client is None:
        config = get_global_config()
        _anthropic_async_client = httpx.AsyncClient(
            headers={
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "User-Agent": config.user_agent
            },
            timeout=httpx.Timeout(
                connect=config.http_connect_timeout,
                read=config.anthropic_timeout,
                write=config.http_write_timeout,
                pool=config.http_pool_timeout
            ),
            limits=httpx.Limits(
                max_connections=config.http_max_connections,
                max_keepalive_connections=config.http_max_keepalive_connections
            )
        )
    return _anthropic_async_client

async def close_anthropic_async_client():
    """Close the global async HTTP client for Anthropic API."""
    global _anthropic_async_client
    if _anthropic_async_client:
        await _anthropic_async_client.aclose()
        _anthropic_async_client = None

@response_validator("anthropic_api")
async def _validate_anthropic_response_async(response_data: dict) -> dict:
    """Validate Anthropic API response structure."""
    return response_data

async def call_llm_async(prompt: str) -> str:
    """
    Async version of call_llm.
    
    Send a prompt to Claude via Anthropic API and return the response.

    This function uses configuration from the global config system.
    """
    config = get_global_config()
    
    if not config.anthropic_api_key:
        return "[ERROR: ANTHROPIC_API_KEY environment variable not set]"

    @async_circuit_breaker(
        name="anthropic_api_async",
        failure_threshold=config.circuit_breaker_failure_threshold,
        recovery_timeout=config.circuit_breaker_recovery_timeout
    )
    @async_exponential_backoff_retry(
        max_retries=config.max_retries,
        initial_delay=config.retry_initial_delay,
        backoff_factor=config.retry_backoff_factor,
        max_delay=config.retry_max_delay,
        jitter=config.retry_jitter,
        retry_on_status_codes=(429, 500, 502, 503, 504)
    )
    async def _retry_wrapper():
        return await _call_llm_async_impl(prompt, config)
    
    return await _retry_wrapper()

async def _call_llm_async_impl(prompt: str, config) -> str:
    """
    Internal async implementation of LLM call with metrics collection.
    """
    # Track LLM call metrics
    increment("anthropic_api_calls_total_async", tags={"model": config.anthropic_model})
    histogram("anthropic_api_prompt_length_async", len(prompt), tags={"model": config.anthropic_model})
    
    with timer("anthropic_api_request_async", tags={"model": config.anthropic_model}):
        try:
            client = await get_anthropic_async_client()
            
            # Set API key in client headers
            client.headers["x-api-key"] = config.anthropic_api_key

            data = {
                "model": config.anthropic_model,
                "max_tokens": config.anthropic_max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }

            start_time = time.time()
            logger.info("Sending async request to Anthropic API", extra={
                "model": data["model"],
                "max_tokens": data["max_tokens"],
                "prompt_length": len(prompt),
                "action": "async_llm_request_start"
            })

            response = await client.post(
                config.anthropic_api_url, 
                json=data, 
                timeout=config.anthropic_timeout
            )
            request_duration = time.time() - start_time

            response.raise_for_status()
            response_data = response.json()
            
            # Validate response structure
            await _validate_anthropic_response_async(response_data)
            
            response_text = response_data["content"][0]["text"]
            
            # Record success metrics
            increment("anthropic_api_success_async", tags={"model": config.anthropic_model})
            histogram("anthropic_api_request_duration_async", request_duration, tags={"model": config.anthropic_model})
            histogram("anthropic_api_response_length_async", len(response_text), tags={"model": config.anthropic_model})
            gauge("anthropic_api_last_request_duration_async", request_duration)
            gauge("anthropic_api_last_response_length_async", len(response_text))
            
            logger.info(f"Async Anthropic API request completed in {request_duration:.2f}s", extra={
                "model": data["model"],
                "request_duration": request_duration,
                "prompt_length": len(prompt),
                "response_length": len(response_text),
                "action": "async_llm_request_success"
            })
            
            return response_text
            
        except httpx.RequestError as e:
            request_duration = time.time() - start_time
            increment("anthropic_api_errors_async", tags={"error_type": "request_exception", "model": config.anthropic_model})
            histogram("anthropic_api_request_duration_async", request_duration, tags={"model": config.anthropic_model, "error": "request_exception"})
            logger.error(f"Async Anthropic API request failed: {str(e)}", extra={
                "model": data.get("model", "unknown"),
                "request_duration": request_duration,
                "prompt_length": len(prompt),
                "error": str(e),
                "action": "async_llm_request_error"
            })
            return f"[API ERROR: {str(e)}]"
            
        except Exception as e:
            request_duration = time.time() - start_time
            increment("anthropic_api_errors_async", tags={"error_type": "unexpected_error", "model": config.anthropic_model})
            histogram("anthropic_api_request_duration_async", request_duration, tags={"model": config.anthropic_model, "error": "unexpected"})
            logger.error(f"Unexpected error in async LLM call: {str(e)}", extra={
                "model": data.get("model", "unknown"),
                "request_duration": request_duration,
                "prompt_length": len(prompt),
                "error": str(e),
                "action": "async_llm_request_unexpected_error"
            })
            return f"[API ERROR: {str(e)}]"

async def call_llm_batch_async(
    prompts: List[str], 
    max_concurrent: int = 3
) -> List[str]:
    """
    Process multiple prompts concurrently for improved performance.
    
    Args:
        prompts (List[str]): List of prompts to process.
        max_concurrent (int): Maximum number of concurrent requests (default: 3).
    
    Returns:
        List[str]: List of responses in the same order as the input prompts.
    """
    # Track batch LLM metrics
    increment("anthropic_api_batch_calls", tags={"batch_size": str(len(prompts))})
    
    # Use semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _call_with_semaphore(prompt: str, index: int) -> tuple[int, str]:
        async with semaphore:
            result = await call_llm_async(prompt)
            return index, result
    
    # Execute all calls concurrently
    start_time = time.time()
    logger.info(f"Starting batch async LLM processing for {len(prompts)} prompts", extra={
        "batch_size": len(prompts),
        "max_concurrent": max_concurrent,
        "action": "batch_llm_start"
    })
    
    tasks = [_call_with_semaphore(prompt, i) for i, prompt in enumerate(prompts)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    batch_duration = time.time() - start_time
    histogram("anthropic_api_batch_duration", batch_duration, tags={"batch_size": str(len(prompts))})
    gauge("anthropic_api_last_batch_duration", batch_duration)
    
    # Process results and handle exceptions
    responses = [""] * len(prompts)  # Initialize with empty strings
    successful_calls = 0
    
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch LLM call exception: {result}", extra={
                "batch_size": len(prompts),
                "error": str(result),
                "action": "batch_llm_exception"
            })
            increment("anthropic_api_batch_errors", tags={"error_type": "exception"})
            continue
        
        index, response = result
        responses[index] = response
        
        # Count successful calls (those without error prefix)
        if not response.startswith("[API ERROR:"):
            successful_calls += 1
    
    # Record batch success metrics
    histogram("anthropic_api_batch_success_count", successful_calls, tags={"batch_size": str(len(prompts))})
    gauge("anthropic_api_last_batch_success_rate", successful_calls / len(prompts) if prompts else 0)
    
    logger.info(f"Batch async LLM processing completed: {successful_calls}/{len(prompts)} successful in {batch_duration:.2f}s", extra={
        "batch_size": len(prompts),
        "successful_calls": successful_calls,
        "batch_duration": batch_duration,
        "action": "batch_llm_complete"
    })
    
    return responses

async def cleanup_async_clients():
    """Clean up all async clients."""
    await close_anthropic_async_client()
    # Import here to avoid circular import
    from clinicaltrials.async_query import close_executor
    await close_executor()