"""
Unified HTTP client supporting both sync and async execution patterns.

This module provides a single HTTP client interface that can operate in either
synchronous (using requests) or asynchronous (using httpx) mode, eliminating
code duplication between sync and async implementations.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Union, Callable
import warnings

import httpx
import requests

from clinicaltrials.config import get_global_config
from utils.metrics import increment, gauge, histogram, timer
from utils.retry import exponential_backoff_retry, async_exponential_backoff_retry
from utils.circuit_breaker import circuit_breaker, async_circuit_breaker


logger = logging.getLogger(__name__)


class HttpResponse:
    """Unified response wrapper for both requests and httpx responses."""
    
    def __init__(self, response: Union[requests.Response, httpx.Response]):
        self._response = response
        self._is_async = isinstance(response, httpx.Response)
    
    @property
    def status_code(self) -> int:
        return self._response.status_code
    
    @property
    def headers(self) -> Dict[str, str]:
        return dict(self._response.headers)
    
    @property
    def text(self) -> str:
        return self._response.text
    
    def json(self) -> Dict[str, Any]:
        return self._response.json()
    
    def raise_for_status(self) -> None:
        self._response.raise_for_status()


class UnifiedHttpClient:
    """HTTP client supporting both sync and async execution."""
    
    def __init__(
        self,
        async_mode: bool = False,
        service_name: str = "generic",
        base_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout_config: Optional[Dict[str, Union[int, float]]] = None,
        retry_config: Optional[Dict[str, Any]] = None,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize unified HTTP client.
        
        Args:
            async_mode: Whether to use async (httpx) or sync (requests) mode
            service_name: Name for metrics and circuit breaker identification
            base_url: Base URL for requests
            headers: Default headers to include with requests
            timeout_config: Timeout configuration dict
            retry_config: Retry configuration dict
            circuit_breaker_config: Circuit breaker configuration dict
            **kwargs: Additional configuration passed to underlying client
        """
        self.async_mode = async_mode
        self.service_name = service_name
        self.base_url = base_url
        
        # Load global configuration
        try:
            self.config = get_global_config()
        except ValueError as e:
            logger.warning(f"Failed to load global config: {e}. Using defaults.")
            self.config = None
        
        # Set up headers
        self.default_headers = self._setup_headers(headers)
        
        # Set up timeout configuration
        self.timeout_config = self._setup_timeout_config(timeout_config)
        
        # Set up retry configuration
        self.retry_config = self._setup_retry_config(retry_config)
        
        # Set up circuit breaker configuration
        self.circuit_breaker_config = self._setup_circuit_breaker_config(circuit_breaker_config)
        
        # Initialize the underlying client
        self._client = None
        self._session = None
        self._setup_client(**kwargs)
    
    def _setup_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Set up default headers with config-based fallbacks."""
        default_headers = {
            "Accept": "application/json",
            "User-Agent": getattr(self.config, 'user_agent', 'UnifiedHttpClient/1.0')
        }
        
        if headers:
            default_headers.update(headers)
        
        return default_headers
    
    def _setup_timeout_config(self, timeout_config: Optional[Dict[str, Union[int, float]]]) -> Dict[str, Union[int, float]]:
        """Set up timeout configuration with config-based defaults."""
        if timeout_config:
            return timeout_config
        
        if self.async_mode:
            return {
                'connect': getattr(self.config, 'http_connect_timeout', 5.0),
                'read': getattr(self.config, 'http_read_timeout', 30.0),
                'write': getattr(self.config, 'http_write_timeout', 10.0),
                'pool': getattr(self.config, 'http_pool_timeout', 5.0),
            }
        else:
            return {
                'timeout': getattr(self.config, 'clinicaltrials_timeout', 10.0)
            }
    
    def _setup_retry_config(self, retry_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Set up retry configuration with config-based defaults."""
        if retry_config:
            return retry_config
        
        return {
            'max_retries': getattr(self.config, 'max_retries', 3),
            'initial_delay': getattr(self.config, 'retry_initial_delay', 1.0),
            'backoff_factor': getattr(self.config, 'retry_backoff_factor', 2.0),
            'max_delay': getattr(self.config, 'retry_max_delay', 60.0),
            'jitter': getattr(self.config, 'retry_jitter', True),
            'retry_on_status_codes': (429, 500, 502, 503, 504),
        }
    
    def _setup_circuit_breaker_config(self, circuit_breaker_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Set up circuit breaker configuration with config-based defaults."""
        if circuit_breaker_config:
            return circuit_breaker_config
        
        return {
            'name': f"{self.service_name}_http_client",
            'failure_threshold': getattr(self.config, 'circuit_breaker_failure_threshold', 5),
            'recovery_timeout': getattr(self.config, 'circuit_breaker_recovery_timeout', 60.0),
        }
    
    def _setup_client(self, **kwargs):
        """Initialize the underlying HTTP client based on mode."""
        if self.async_mode:
            self._setup_async_client(**kwargs)
        else:
            self._setup_sync_client(**kwargs)
    
    def _setup_async_client(self, **kwargs):
        """Set up async httpx client."""
        # Create timeout object
        timeout = httpx.Timeout(
            connect=self.timeout_config['connect'],
            read=self.timeout_config['read'],
            write=self.timeout_config['write'],
            pool=self.timeout_config['pool'],
        )
        
        # Create limits object
        limits = httpx.Limits(
            max_connections=getattr(self.config, 'http_max_connections', 100),
            max_keepalive_connections=getattr(self.config, 'http_max_keepalive_connections', 20),
            keepalive_expiry=getattr(self.config, 'http_keepalive_expiry', 60.0),
        )
        
        # Set up client configuration
        client_config = {
            'base_url': self.base_url,
            'headers': self.default_headers,
            'timeout': timeout,
            'limits': limits,
            **kwargs
        }
        
        self._client = httpx.AsyncClient(**client_config)
    
    def _setup_sync_client(self, **kwargs):
        """Set up sync requests session."""
        self._session = requests.Session()
        self._session.headers.update(self.default_headers)
        
        # Store timeout for use in requests
        self._sync_timeout = self.timeout_config['timeout']
    
    @property
    def is_async(self) -> bool:
        """Check if client is in async mode."""
        return self.async_mode
    
    def _apply_retry_decorator(self, func: Callable) -> Callable:
        """Apply appropriate retry decorator based on mode."""
        if self.async_mode:
            return async_exponential_backoff_retry(**self.retry_config)(func)
        else:
            return exponential_backoff_retry(**self.retry_config)(func)
    
    def _apply_circuit_breaker_decorator(self, func: Callable) -> Callable:
        """Apply appropriate circuit breaker decorator based on mode."""
        if self.async_mode:
            return async_circuit_breaker(**self.circuit_breaker_config)(func)
        else:
            return circuit_breaker(**self.circuit_breaker_config)(func)
    
    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs
    ) -> HttpResponse:
        """
        Unified request method - sync or async based on mode.
        
        This method automatically detects the execution context and routes
        to the appropriate implementation.
        """
        if self.async_mode:
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, but this is the sync method
                warnings.warn(
                    "Using sync request() method in async context. "
                    "Consider using arequest() for better performance.",
                    RuntimeWarning
                )
                # Run the async version in the current loop
                return loop.run_until_complete(
                    self.arequest(method, url, headers=headers, params=params, 
                                json=json, data=data, **kwargs)
                )
            except RuntimeError:
                # No event loop running, use sync fallback
                return self._sync_request_fallback(method, url, headers=headers, 
                                                 params=params, json=json, 
                                                 data=data, **kwargs)
        else:
            return self._sync_request(method, url, headers=headers, params=params,
                                    json=json, data=data, **kwargs)
    
    async def arequest(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs
    ) -> HttpResponse:
        """Explicit async request method."""
        if not self.async_mode:
            raise RuntimeError("Cannot use arequest() when async_mode=False")
        
        return await self._async_request(method, url, headers=headers, 
                                       params=params, json=json, data=data, **kwargs)
    
    def _sync_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs
    ) -> HttpResponse:
        """Internal sync request implementation."""
        
        @self._apply_circuit_breaker_decorator
        @self._apply_retry_decorator
        def _make_request():
            # Merge headers
            request_headers = self.default_headers.copy()
            if headers:
                request_headers.update(headers)
            
            # Start timing
            start_time = time.time()
            
            try:
                # Make the request
                response = self._session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=self._sync_timeout,
                    **kwargs
                )
                
                # Record metrics
                request_duration = time.time() - start_time
                increment("http_requests_total", tags={
                    "service": self.service_name,
                    "method": method,
                    "status_code": str(response.status_code)
                })
                histogram("http_request_duration", request_duration, tags={
                    "service": self.service_name,
                    "method": method
                })
                gauge("http_last_request_duration", request_duration, tags={
                    "service": self.service_name
                })
                
                logger.info(
                    f"HTTP {method} request completed",
                    extra={
                        "action": "http_request_completed",
                        "service": self.service_name,
                        "method": method,
                        "url": url,
                        "status_code": response.status_code,
                        "duration": request_duration
                    }
                )
                
                return HttpResponse(response)
                
            except Exception as e:
                request_duration = time.time() - start_time
                increment("http_errors_total", tags={
                    "service": self.service_name,
                    "method": method,
                    "error_type": type(e).__name__
                })
                histogram("http_request_duration", request_duration, tags={
                    "service": self.service_name,
                    "method": method,
                    "error": "true"
                })
                
                logger.error(
                    f"HTTP {method} request failed",
                    extra={
                        "action": "http_request_failed",
                        "service": self.service_name,
                        "method": method,
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration": request_duration
                    }
                )
                raise
        
        return _make_request()
    
    async def _async_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs
    ) -> HttpResponse:
        """Internal async request implementation."""
        
        @self._apply_circuit_breaker_decorator
        @self._apply_retry_decorator
        async def _make_request():
            # Merge headers
            request_headers = self.default_headers.copy()
            if headers:
                request_headers.update(headers)
            
            # Start timing
            start_time = time.time()
            
            try:
                # Make the request
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json,
                    data=data,
                    **kwargs
                )
                
                # Record metrics
                request_duration = time.time() - start_time
                increment("http_requests_total", tags={
                    "service": self.service_name,
                    "method": method,
                    "status_code": str(response.status_code)
                })
                histogram("http_request_duration", request_duration, tags={
                    "service": self.service_name,
                    "method": method
                })
                gauge("http_last_request_duration", request_duration, tags={
                    "service": self.service_name
                })
                
                logger.info(
                    f"HTTP {method} request completed",
                    extra={
                        "action": "async_http_request_completed",
                        "service": self.service_name,
                        "method": method,
                        "url": url,
                        "status_code": response.status_code,
                        "duration": request_duration
                    }
                )
                
                return HttpResponse(response)
                
            except Exception as e:
                request_duration = time.time() - start_time
                increment("http_errors_total", tags={
                    "service": self.service_name,
                    "method": method,
                    "error_type": type(e).__name__
                })
                histogram("http_request_duration", request_duration, tags={
                    "service": self.service_name,
                    "method": method,
                    "error": "true"
                })
                
                logger.error(
                    f"HTTP {method} request failed",
                    extra={
                        "action": "async_http_request_failed",
                        "service": self.service_name,
                        "method": method,
                        "url": url,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration": request_duration
                    }
                )
                raise
        
        return await _make_request()
    
    def _sync_request_fallback(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs
    ) -> HttpResponse:
        """Fallback sync request when async client is configured but no event loop exists."""
        logger.warning(
            "Using sync fallback for async-configured client",
            extra={
                "action": "http_sync_fallback",
                "service": self.service_name,
                "method": method,
                "url": url
            }
        )
        
        # Temporarily create a sync session for this request
        with requests.Session() as session:
            session.headers.update(self.default_headers)
            
            start_time = time.time()
            
            try:
                response = session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=self.timeout_config.get('read', 30.0),
                    **kwargs
                )
                
                request_duration = time.time() - start_time
                increment("http_fallback_requests_total", tags={
                    "service": self.service_name,
                    "method": method
                })
                
                return HttpResponse(response)
                
            except Exception as e:
                request_duration = time.time() - start_time
                increment("http_fallback_errors_total", tags={
                    "service": self.service_name,
                    "method": method,
                    "error_type": type(e).__name__
                })
                raise
    
    # Convenience methods for common HTTP verbs
    def get(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for GET requests."""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for POST requests."""
        return self.request("POST", url, **kwargs)
    
    def put(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for PUT requests."""
        return self.request("PUT", url, **kwargs)
    
    def delete(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for DELETE requests."""
        return self.request("DELETE", url, **kwargs)
    
    async def aget(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for async GET requests."""
        return await self.arequest("GET", url, **kwargs)
    
    async def apost(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for async POST requests."""
        return await self.arequest("POST", url, **kwargs)
    
    async def aput(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for async PUT requests."""
        return await self.arequest("PUT", url, **kwargs)
    
    async def adelete(self, url: str, **kwargs) -> HttpResponse:
        """Convenience method for async DELETE requests."""
        return await self.arequest("DELETE", url, **kwargs)
    
    def close(self):
        """Close the underlying client/session."""
        if self.async_mode and self._client:
            # For async clients, this needs to be called from an async context
            asyncio.create_task(self._client.aclose())
        elif self._session:
            self._session.close()
    
    async def aclose(self):
        """Async close method."""
        if self.async_mode and self._client:
            await self._client.aclose()
        elif self._session:
            self._session.close()
    
    def __enter__(self):
        """Context manager support for sync mode."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup for sync mode."""
        self.close()
    
    async def __aenter__(self):
        """Async context manager support."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager cleanup."""
        await self.aclose()


# Factory functions for common service types
def create_clinicaltrials_client(async_mode: bool = False) -> UnifiedHttpClient:
    """Create a pre-configured client for ClinicalTrials.gov API."""
    return UnifiedHttpClient(
        async_mode=async_mode,
        service_name="clinicaltrials",
        base_url="https://clinicaltrials.gov/api/",
        headers={
            "Accept": "application/json"
        }
    )


def create_anthropic_client(async_mode: bool = False, api_key: Optional[str] = None) -> UnifiedHttpClient:
    """Create a pre-configured client for Anthropic API."""
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    if api_key:
        headers["x-api-key"] = api_key
    
    return UnifiedHttpClient(
        async_mode=async_mode,
        service_name="anthropic",
        base_url="https://api.anthropic.com/",
        headers=headers
    )