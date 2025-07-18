"""
Unified LLM service supporting both sync and async execution patterns.

This module provides a single LLM service interface that can operate in either
synchronous or asynchronous mode, eliminating code duplication between
utils/call_llm.py and utils/async_call_llm.py.
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union
from functools import lru_cache

from clinicaltrials.config import get_global_config
from utils.http_client import UnifiedHttpClient, create_anthropic_client
from utils.shared import (
    validate_llm_input,
    map_http_exception_to_error_response,
    time_request,
    process_json_response
)
from utils.metrics import increment, gauge, histogram
from utils.response_validation import response_validator


logger = logging.getLogger(__name__)


class LLMService:
    """
    Unified LLM service supporting both sync and async execution.
    
    This service provides a consistent interface for interacting with the
    Anthropic Claude API, supporting both synchronous and asynchronous
    execution modes with built-in resilience patterns.
    """
    
    def __init__(
        self,
        async_mode: bool = False,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_concurrent_requests: int = 5
    ):
        """
        Initialize the LLM service.
        
        Args:
            async_mode: Whether to use async execution
            api_key: Anthropic API key (defaults to env variable)
            model: Model to use (defaults to config)
            max_tokens: Max tokens to generate (defaults to config)
            temperature: Temperature for generation (defaults to config)
            max_concurrent_requests: Max concurrent requests for batch processing
        """
        self.async_mode = async_mode
        
        # Load configuration
        try:
            self.config = get_global_config()
        except ValueError as e:
            logger.warning(f"Failed to load global config: {e}. Using defaults.")
            self.config = None
        
        # Set up API configuration
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        
        self.model = model or getattr(self.config, 'anthropic_model', 'claude-3-5-sonnet-20241022')
        self.max_tokens = max_tokens or getattr(self.config, 'anthropic_max_tokens', 1000)
        self.temperature = temperature or getattr(self.config, 'anthropic_temperature', 0.0)
        
        # Set up HTTP client
        self._client = create_anthropic_client(async_mode=async_mode, api_key=self.api_key)
        
        # Set up concurrency control for async batch processing
        if async_mode:
            self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # Metrics prefix based on mode
        self._metrics_prefix = "anthropic_api"
        self._metrics_suffix = "_async" if async_mode else ""
        
        logger.info(
            f"LLM service initialized in {'async' if async_mode else 'sync'} mode",
            extra={
                "action": "llm_service_initialized",
                "async_mode": async_mode,
                "model": self.model,
                "max_tokens": self.max_tokens
            }
        )
    
    def _prepare_request(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Prepare request payload for the API.
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters to override defaults
            
        Returns:
            Dict containing the request payload
        """
        # Build messages
        messages = [{"role": "user", "content": prompt}]
        
        # Validate input
        validation_result = validate_llm_input(
            messages,
            model=kwargs.get('model', self.model),
            max_tokens=kwargs.get('max_tokens', self.max_tokens),
            temperature=kwargs.get('temperature', self.temperature)
        )
        
        if not validation_result["valid"]:
            raise ValueError(validation_result["error"])
        
        # Log any warnings
        for warning in validation_result["warnings"]:
            logger.warning(f"LLM input validation warning: {warning}")
        
        # Build request payload
        return {
            "model": kwargs.get('model', self.model),
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "temperature": kwargs.get('temperature', self.temperature),
            "messages": messages
        }
    
    def _process_response(self, response_data: Dict[str, Any], prompt: str) -> str:
        """
        Process API response and extract content.
        
        Args:
            response_data: Raw response data from API
            prompt: Original prompt for metrics
            
        Returns:
            Extracted response content
        """
        # Validate response structure
        if "content" not in response_data:
            raise ValueError("Response missing 'content' field")
        
        if not isinstance(response_data["content"], list) or len(response_data["content"]) == 0:
            raise ValueError("Response content is empty or invalid")
        
        # Extract text content
        content = response_data["content"][0]
        if content.get("type") != "text" or "text" not in content:
            raise ValueError("Response content is not text type")
        
        response_text = content["text"]
        
        # Record metrics
        prompt_length = len(prompt)
        response_length = len(response_text)
        
        histogram(f"{self._metrics_prefix}_prompt_length{self._metrics_suffix}", 
                 prompt_length, tags={"model": self.model})
        histogram(f"{self._metrics_prefix}_response_length{self._metrics_suffix}", 
                 response_length, tags={"model": self.model})
        gauge(f"{self._metrics_prefix}_last_prompt_length{self._metrics_suffix}", 
              prompt_length, tags={"model": self.model})
        gauge(f"{self._metrics_prefix}_last_response_length{self._metrics_suffix}", 
              response_length, tags={"model": self.model})
        
        return response_text
    
    @time_request("anthropic", "call_llm")
    @response_validator("anthropic_response")
    def call_llm(self, prompt: str, **kwargs) -> str:
        """
        Make a synchronous call to the LLM.
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters (model, max_tokens, temperature)
            
        Returns:
            The LLM response text
            
        Raises:
            ValueError: If configuration is invalid
            Exception: If the API call fails
        """
        if self.async_mode:
            # If in async mode but called synchronously, use sync fallback
            logger.warning("Sync call_llm() called on async-configured service")
            return asyncio.run(self.acall_llm(prompt, **kwargs))
        
        # Increment call counter
        increment(f"{self._metrics_prefix}_calls_total{self._metrics_suffix}", 
                 tags={"model": self.model})
        
        # Log request start
        logger.info(
            "Starting Anthropic API request",
            extra={
                "action": f"{self._metrics_prefix}_request_start{self._metrics_suffix}",
                "model": self.model,
                "prompt_length": len(prompt),
                "max_tokens": kwargs.get('max_tokens', self.max_tokens)
            }
        )
        
        try:
            # Prepare request
            request_data = self._prepare_request(prompt, **kwargs)
            
            # Make API call
            response = self._client.post(
                "v1/messages",
                json=request_data
            )
            
            # Check status
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Process and return
            result = self._process_response(response_data, prompt)
            
            # Record success
            increment(f"{self._metrics_prefix}_success{self._metrics_suffix}", 
                     tags={"model": self.model})
            
            logger.info(
                "Anthropic API request successful",
                extra={
                    "action": f"{self._metrics_prefix}_request_success{self._metrics_suffix}",
                    "model": self.model,
                    "response_length": len(result)
                }
            )
            
            return result
            
        except Exception as e:
            # Record failure
            increment(f"{self._metrics_prefix}_errors{self._metrics_suffix}", 
                     tags={"model": self.model, "error_type": type(e).__name__})
            
            logger.error(
                f"Anthropic API request failed: {str(e)}",
                extra={
                    "action": f"{self._metrics_prefix}_request_failed{self._metrics_suffix}",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            # Map to standard error response if it's an HTTP error
            if hasattr(e, 'response') or hasattr(e, 'request'):
                error_response = map_http_exception_to_error_response(
                    e, "anthropic", "LLM request failed"
                )
                raise ValueError(error_response["error"]) from e
            
            raise
    
    @time_request("anthropic", "call_llm_async")
    @response_validator("anthropic_response")
    async def acall_llm(self, prompt: str, **kwargs) -> str:
        """
        Make an asynchronous call to the LLM.
        
        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters (model, max_tokens, temperature)
            
        Returns:
            The LLM response text
            
        Raises:
            ValueError: If configuration is invalid
            Exception: If the API call fails
        """
        if not self.async_mode:
            raise RuntimeError("Cannot use acall_llm() when async_mode=False")
        
        # Increment call counter
        increment(f"{self._metrics_prefix}_calls_total{self._metrics_suffix}", 
                 tags={"model": self.model})
        
        # Log request start
        logger.info(
            "Starting async Anthropic API request",
            extra={
                "action": f"{self._metrics_prefix}_request_start{self._metrics_suffix}",
                "model": self.model,
                "prompt_length": len(prompt),
                "max_tokens": kwargs.get('max_tokens', self.max_tokens)
            }
        )
        
        try:
            # Prepare request
            request_data = self._prepare_request(prompt, **kwargs)
            
            # Make API call
            response = await self._client.apost(
                "v1/messages",
                json=request_data
            )
            
            # Check status
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Process and return
            result = self._process_response(response_data, prompt)
            
            # Record success
            increment(f"{self._metrics_prefix}_success{self._metrics_suffix}", 
                     tags={"model": self.model})
            
            logger.info(
                "Async Anthropic API request successful",
                extra={
                    "action": f"{self._metrics_prefix}_request_success{self._metrics_suffix}",
                    "model": self.model,
                    "response_length": len(result)
                }
            )
            
            return result
            
        except Exception as e:
            # Record failure
            increment(f"{self._metrics_prefix}_errors{self._metrics_suffix}", 
                     tags={"model": self.model, "error_type": type(e).__name__})
            
            logger.error(
                f"Async Anthropic API request failed: {str(e)}",
                extra={
                    "action": f"{self._metrics_prefix}_request_failed{self._metrics_suffix}",
                    "model": self.model,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            # Map to standard error response if it's an HTTP error
            if hasattr(e, 'response') or hasattr(e, 'request'):
                error_response = map_http_exception_to_error_response(
                    e, "anthropic", "LLM request failed"
                )
                raise ValueError(error_response["error"]) from e
            
            raise
    
    async def acall_llm_batch(self, prompts: List[str], **kwargs) -> List[Union[str, Exception]]:
        """
        Make batch asynchronous calls to the LLM with concurrency control.
        
        Args:
            prompts: List of prompts to process
            **kwargs: Additional parameters for each call
            
        Returns:
            List of responses or exceptions for each prompt
        """
        if not self.async_mode:
            raise RuntimeError("Cannot use acall_llm_batch() when async_mode=False")
        
        start_time = time.time()
        batch_size = len(prompts)
        
        logger.info(
            f"Starting batch LLM processing for {batch_size} prompts",
            extra={
                "action": "llm_batch_start",
                "batch_size": batch_size,
                "max_concurrent": self._semaphore._value
            }
        )
        
        increment(f"{self._metrics_prefix}_batch_calls{self._metrics_suffix}", 
                 tags={"batch_size": str(batch_size)})
        
        async def process_with_semaphore(prompt: str, index: int) -> Union[str, Exception]:
            """Process a single prompt with semaphore control."""
            async with self._semaphore:
                try:
                    logger.debug(f"Processing prompt {index + 1}/{batch_size}")
                    result = await self.acall_llm(prompt, **kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Failed to process prompt {index + 1}: {str(e)}")
                    return e
        
        # Process all prompts concurrently
        tasks = [
            process_with_semaphore(prompt, i) 
            for i, prompt in enumerate(prompts)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = batch_size - successes
        
        duration = time.time() - start_time
        
        # Record batch metrics
        increment(f"{self._metrics_prefix}_batch_success{self._metrics_suffix}", 
                 tags={"batch_size": str(successes)})
        increment(f"{self._metrics_prefix}_batch_errors{self._metrics_suffix}", 
                 tags={"batch_size": str(failures)})
        histogram(f"{self._metrics_prefix}_batch_duration{self._metrics_suffix}", 
                 duration, tags={"batch_size": str(batch_size)})
        gauge(f"{self._metrics_prefix}_batch_success_rate{self._metrics_suffix}", 
              successes / batch_size * 100 if batch_size > 0 else 0)
        
        logger.info(
            f"Completed batch LLM processing: {successes}/{batch_size} successful",
            extra={
                "action": "llm_batch_complete",
                "batch_size": batch_size,
                "successes": successes,
                "failures": failures,
                "duration": duration,
                "avg_time_per_prompt": duration / batch_size if batch_size > 0 else 0
            }
        )
        
        return results
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    async def aclose(self):
        """Async close the HTTP client."""
        await self._client.aclose()
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
    
    async def __aenter__(self):
        """Async context manager support."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager cleanup."""
        await self.aclose()


# Global service instances for backward compatibility
_sync_service: Optional[LLMService] = None
_async_service: Optional[LLMService] = None


@lru_cache(maxsize=1)
def get_sync_llm_service() -> LLMService:
    """Get or create the global sync LLM service."""
    global _sync_service
    if _sync_service is None:
        _sync_service = LLMService(async_mode=False)
    return _sync_service


@lru_cache(maxsize=1)
def get_async_llm_service() -> LLMService:
    """Get or create the global async LLM service."""
    global _async_service
    if _async_service is None:
        _async_service = LLMService(async_mode=True)
    return _async_service


async def cleanup_services():
    """Clean up all global LLM services."""
    global _sync_service, _async_service
    
    if _sync_service:
        _sync_service.close()
        _sync_service = None
    
    if _async_service:
        await _async_service.aclose()
        _async_service = None
    
    # Clear the caches
    get_sync_llm_service.cache_clear()
    get_async_llm_service.cache_clear()
    
    logger.info("LLM services cleaned up", extra={"action": "llm_services_cleanup"})