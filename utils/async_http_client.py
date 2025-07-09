"""
Unified HTTP client manager for async operations.

This module provides centralized async HTTP client management following PocketFlow
design principles. It ensures proper connection pooling, timeout configuration,
and resource cleanup across all API services.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import httpx
from clinicaltrials.config import get_global_config

logger = logging.getLogger(__name__)

# Global HTTP clients for different services
_clients: Dict[str, httpx.AsyncClient] = {}
_client_lock = asyncio.Lock()


class AsyncHttpClientManager:
    """
    Centralized manager for async HTTP clients with service-specific configurations.
    
    This class provides:
    - Shared connection pooling across requests
    - Unified timeout configuration
    - Proper resource cleanup
    - Per-service client instances
    """
    
    @staticmethod
    async def get_client(service: str, **kwargs) -> httpx.AsyncClient:
        """
        Get or create an async HTTP client for a specific service.
        
        Args:
            service: Service identifier (e.g., 'clinicaltrials', 'anthropic')
            **kwargs: Additional client configuration options
            
        Returns:
            httpx.AsyncClient: Configured async HTTP client
        """
        async with _client_lock:
            if service not in _clients:
                _clients[service] = await AsyncHttpClientManager._create_client(service, **kwargs)
            return _clients[service]
    
    @staticmethod
    async def _create_client(service: str, **kwargs) -> httpx.AsyncClient:
        """
        Create a new async HTTP client with service-specific configuration.
        
        Args:
            service: Service identifier
            **kwargs: Additional client configuration options
            
        Returns:
            httpx.AsyncClient: Configured async HTTP client
        """
        config = get_global_config()
        
        # Base configuration common to all services
        base_config = {
            "timeout": httpx.Timeout(
                connect=config.http_connect_timeout,
                read=kwargs.get('read_timeout', config.http_read_timeout),
                write=config.http_write_timeout,
                pool=config.http_pool_timeout
            ),
            "limits": httpx.Limits(
                max_connections=config.http_max_connections,
                max_keepalive_connections=config.http_max_keepalive_connections
            ),
            "follow_redirects": kwargs.get('follow_redirects', True),
            "headers": kwargs.get('headers', {})
        }
        
        # Service-specific configurations
        if service == 'clinicaltrials':
            base_config['headers'].update({
                "Accept": "application/json",
                "User-Agent": config.user_agent
            })
            # Use standard read timeout for clinical trials API
            base_config['timeout'] = httpx.Timeout(
                connect=config.http_connect_timeout,
                read=config.http_read_timeout,
                write=config.http_write_timeout,
                pool=config.http_pool_timeout
            )
            
        elif service == 'anthropic':
            base_config['headers'].update({
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "User-Agent": config.user_agent
            })
            # Use longer timeout for Anthropic API
            base_config['timeout'] = httpx.Timeout(
                connect=config.http_connect_timeout,
                read=config.anthropic_timeout,
                write=config.http_write_timeout,
                pool=config.http_pool_timeout
            )
        
        # Override with any additional kwargs
        base_config.update({k: v for k, v in kwargs.items() if k not in ['read_timeout', 'follow_redirects', 'headers']})
        
        logger.info(f"Creating async HTTP client for service: {service}", extra={
            "service": service,
            "connect_timeout": base_config['timeout'].connect,
            "read_timeout": base_config['timeout'].read,
            "max_connections": base_config['limits'].max_connections,
            "action": "http_client_creation"
        })
        
        return httpx.AsyncClient(**base_config)
    
    @staticmethod
    async def close_client(service: str) -> None:
        """
        Close and remove a specific service client.
        
        Args:
            service: Service identifier
        """
        async with _client_lock:
            if service in _clients:
                await _clients[service].aclose()
                del _clients[service]
                logger.info(f"Closed async HTTP client for service: {service}", extra={
                    "service": service,
                    "action": "http_client_cleanup"
                })
    
    @staticmethod
    async def close_all_clients() -> None:
        """Close all active HTTP clients."""
        async with _client_lock:
            for service, client in _clients.items():
                await client.aclose()
                logger.info(f"Closed async HTTP client for service: {service}", extra={
                    "service": service,
                    "action": "http_client_cleanup"
                })
            _clients.clear()
            logger.info("All async HTTP clients closed", extra={
                "action": "http_clients_cleanup_complete"
            })
    
    @staticmethod
    async def get_client_info() -> Dict[str, Any]:
        """
        Get information about active clients.
        
        Returns:
            Dict containing client status information
        """
        async with _client_lock:
            return {
                "active_clients": list(_clients.keys()),
                "client_count": len(_clients),
                "services": {
                    service: {
                        "is_closed": client.is_closed,
                        "timeout": {
                            "connect": client.timeout.connect,
                            "read": client.timeout.read,
                            "write": client.timeout.write,
                            "pool": client.timeout.pool
                        },
                        "limits": {
                            "max_connections": getattr(client, '_limits', {}).get('max_connections', 'N/A'),
                            "max_keepalive_connections": getattr(client, '_limits', {}).get('max_keepalive_connections', 'N/A')
                        }
                    }
                    for service, client in _clients.items()
                }
            }


# Convenience functions for common operations
async def get_clinicaltrials_client() -> httpx.AsyncClient:
    """Get the async HTTP client for clinicaltrials.gov API."""
    return await AsyncHttpClientManager.get_client('clinicaltrials')


async def get_anthropic_client() -> httpx.AsyncClient:
    """Get the async HTTP client for Anthropic API."""
    return await AsyncHttpClientManager.get_client('anthropic')


async def cleanup_all_clients() -> None:
    """Clean up all HTTP clients. Should be called on application shutdown."""
    await AsyncHttpClientManager.close_all_clients()