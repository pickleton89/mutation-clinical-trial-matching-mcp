"""
Configuration management for the Clinical Trials MCP Server.
"""

import logging
import os
from dataclasses import dataclass
from typing import cast

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


@dataclass
class APIConfig:
    """Configuration for API endpoints and settings."""

    # Clinical Trials API Configuration
    clinicaltrials_api_url: str = "https://clinicaltrials.gov/api/v2/studies"
    clinicaltrials_timeout: int = 10

    # Anthropic API Configuration
    anthropic_api_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-opus-20240229"
    anthropic_max_tokens: int = 1000
    anthropic_timeout: int = 30

    # Retry Configuration
    max_retries: int = 3
    retry_initial_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    retry_max_delay: float = 60.0
    retry_jitter: bool = True

    # Cache Configuration
    cache_size: int = 100
    cache_ttl: int = 3600

    # Circuit Breaker Configuration (for future use)
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60

    # User Agent Configuration
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

    # HTTP Connection Configuration (for async clients)
    http_connect_timeout: int = 5
    http_read_timeout: int = 30
    http_write_timeout: int = 10
    http_pool_timeout: int = 5
    http_max_connections: int = 100
    http_max_keepalive_connections: int = 20

    # Advanced Connection Pool Configuration
    http_keepalive_expiry: int = 60  # seconds to keep connections alive
    http_max_keepalive_size: int = 1024  # max bytes for keep-alive connection
    http_retries: int = 3  # connection-level retries

    # Concurrent Request Management
    max_concurrent_requests: int = 10  # global semaphore limit
    max_concurrent_per_host: int = 5  # per-host concurrent limit

    # Performance Optimization
    enable_http2: bool = (
        False  # enable HTTP/2 support (requires h2 package) - disabled due to 403 errors
    )
    enable_connection_pooling: bool = True
    connection_pool_size: int = 100  # dedicated pool size per service

    # Redis Configuration (for distributed caching)
    redis_url: str = "redis://localhost:6379"
    redis_max_connections: int = 10
    redis_timeout: int = 5


def load_config() -> APIConfig:
    """
    Load configuration from environment variables.

    Returns:
        APIConfig: Configuration object with values from environment variables
    """
    config = APIConfig()

    # Clinical Trials API Configuration
    config.clinicaltrials_api_url = os.getenv(
        "CLINICALTRIALS_API_URL", config.clinicaltrials_api_url
    )
    config.clinicaltrials_timeout = int(
        os.getenv("CLINICALTRIALS_TIMEOUT", str(config.clinicaltrials_timeout))
    )

    # Anthropic API Configuration
    config.anthropic_api_url = os.getenv("ANTHROPIC_API_URL", config.anthropic_api_url)
    config.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", config.anthropic_api_key)
    config.anthropic_model = os.getenv("ANTHROPIC_MODEL", config.anthropic_model)
    config.anthropic_max_tokens = int(
        os.getenv("ANTHROPIC_MAX_TOKENS", str(config.anthropic_max_tokens))
    )
    config.anthropic_timeout = int(os.getenv("ANTHROPIC_TIMEOUT", str(config.anthropic_timeout)))

    # Retry Configuration
    config.max_retries = int(os.getenv("MAX_RETRIES", str(config.max_retries)))
    config.retry_initial_delay = float(
        os.getenv("RETRY_INITIAL_DELAY", str(config.retry_initial_delay))
    )
    config.retry_backoff_factor = float(
        os.getenv("RETRY_BACKOFF_FACTOR", str(config.retry_backoff_factor))
    )
    config.retry_max_delay = float(os.getenv("RETRY_MAX_DELAY", str(config.retry_max_delay)))
    config.retry_jitter = os.getenv("RETRY_JITTER", str(config.retry_jitter)).lower() in (
        "true",
        "1",
        "yes",
        "on",
    )

    # Cache Configuration
    config.cache_size = int(os.getenv("CACHE_SIZE", str(config.cache_size)))
    config.cache_ttl = int(os.getenv("CACHE_TTL", str(config.cache_ttl)))

    # Circuit Breaker Configuration
    config.circuit_breaker_failure_threshold = int(
        os.getenv(
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD", str(config.circuit_breaker_failure_threshold)
        )
    )
    config.circuit_breaker_recovery_timeout = int(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", str(config.circuit_breaker_recovery_timeout))
    )

    # User Agent Configuration
    config.user_agent = os.getenv("USER_AGENT", config.user_agent)

    # HTTP Connection Configuration
    config.http_connect_timeout = int(
        os.getenv("HTTP_CONNECT_TIMEOUT", str(config.http_connect_timeout))
    )
    config.http_read_timeout = int(os.getenv("HTTP_READ_TIMEOUT", str(config.http_read_timeout)))
    config.http_write_timeout = int(os.getenv("HTTP_WRITE_TIMEOUT", str(config.http_write_timeout)))
    config.http_pool_timeout = int(os.getenv("HTTP_POOL_TIMEOUT", str(config.http_pool_timeout)))
    config.http_max_connections = int(
        os.getenv("HTTP_MAX_CONNECTIONS", str(config.http_max_connections))
    )
    config.http_max_keepalive_connections = int(
        os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", str(config.http_max_keepalive_connections))
    )

    # Redis Configuration
    config.redis_url = os.getenv("REDIS_URL", config.redis_url)
    config.redis_max_connections = int(
        os.getenv("REDIS_MAX_CONNECTIONS", str(config.redis_max_connections))
    )
    config.redis_timeout = int(os.getenv("REDIS_TIMEOUT", str(config.redis_timeout)))

    return config


def validate_config(config: APIConfig) -> list[str]:
    """
    Validate configuration and return list of validation errors.

    Args:
        config: Configuration object to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Required fields
    if not config.anthropic_api_key:
        errors.append("ANTHROPIC_API_KEY is required")

    # URL validation
    if not config.clinicaltrials_api_url.startswith(("http://", "https://")):
        errors.append("CLINICALTRIALS_API_URL must be a valid URL")

    if not config.anthropic_api_url.startswith(("http://", "https://")):
        errors.append("ANTHROPIC_API_URL must be a valid URL")

    # Numeric validation
    if config.clinicaltrials_timeout <= 0:
        errors.append("CLINICALTRIALS_TIMEOUT must be positive")

    if config.anthropic_timeout <= 0:
        errors.append("ANTHROPIC_TIMEOUT must be positive")

    if config.anthropic_max_tokens <= 0:
        errors.append("ANTHROPIC_MAX_TOKENS must be positive")

    if config.max_retries < 0:
        errors.append("MAX_RETRIES must be non-negative")

    if config.retry_initial_delay <= 0:
        errors.append("RETRY_INITIAL_DELAY must be positive")

    if config.retry_backoff_factor <= 0:
        errors.append("RETRY_BACKOFF_FACTOR must be positive")

    if config.retry_max_delay <= 0:
        errors.append("RETRY_MAX_DELAY must be positive")

    if config.cache_size <= 0:
        errors.append("CACHE_SIZE must be positive")

    if config.cache_ttl <= 0:
        errors.append("CACHE_TTL must be positive")

    if config.circuit_breaker_failure_threshold <= 0:
        errors.append("CIRCUIT_BREAKER_FAILURE_THRESHOLD must be positive")

    if config.circuit_breaker_recovery_timeout <= 0:
        errors.append("CIRCUIT_BREAKER_RECOVERY_TIMEOUT must be positive")

    # HTTP Connection Configuration validation
    if config.http_connect_timeout <= 0:
        errors.append("HTTP_CONNECT_TIMEOUT must be positive")

    if config.http_read_timeout <= 0:
        errors.append("HTTP_READ_TIMEOUT must be positive")

    if config.http_write_timeout <= 0:
        errors.append("HTTP_WRITE_TIMEOUT must be positive")

    if config.http_pool_timeout <= 0:
        errors.append("HTTP_POOL_TIMEOUT must be positive")

    if config.http_max_connections <= 0:
        errors.append("HTTP_MAX_CONNECTIONS must be positive")

    if config.http_max_keepalive_connections <= 0:
        errors.append("HTTP_MAX_KEEPALIVE_CONNECTIONS must be positive")

    if config.http_max_keepalive_connections > config.http_max_connections:
        errors.append("HTTP_MAX_KEEPALIVE_CONNECTIONS cannot be greater than HTTP_MAX_CONNECTIONS")

    # Redis Configuration validation
    if not config.redis_url.startswith(("redis://", "rediss://")):
        errors.append("REDIS_URL must be a valid Redis URL (redis:// or rediss://)")

    if config.redis_max_connections <= 0:
        errors.append("REDIS_MAX_CONNECTIONS must be positive")

    if config.redis_timeout <= 0:
        errors.append("REDIS_TIMEOUT must be positive")

    # Logical validation
    if config.retry_initial_delay > config.retry_max_delay:
        errors.append("RETRY_INITIAL_DELAY cannot be greater than RETRY_MAX_DELAY")

    return errors


def get_config() -> APIConfig:
    """
    Get validated configuration.

    Returns:
        APIConfig: Validated configuration object

    Raises:
        ValueError: If configuration is invalid
    """
    config = load_config()
    errors = validate_config(config)

    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(
            f"  - {error}" for error in errors
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info(
        "Configuration loaded successfully",
        extra={
            "clinicaltrials_api_url": config.clinicaltrials_api_url,
            "anthropic_api_url": config.anthropic_api_url,
            "anthropic_model": config.anthropic_model,
            "max_retries": config.max_retries,
            "cache_size": config.cache_size,
            "action": "config_loaded",
        },
    )

    return config


# Global configuration instance
_config: APIConfig | None = None


def get_global_config() -> APIConfig:
    """
    Get the global configuration instance (lazy-loaded).

    Returns:
        APIConfig: Global configuration instance
    """
    global _config
    if _config is None:
        _config = get_config()
    return cast(APIConfig, _config)


def reset_global_config() -> None:
    """
    Reset the global configuration instance (useful for testing).
    """
    global _config
    _config = None
