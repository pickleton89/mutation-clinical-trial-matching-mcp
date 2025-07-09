"""
Configuration management for the Clinical Trials MCP Server.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass
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
    user_agent: str = "mutation-clinical-trial-matching-mcp/0.1.0 (Clinical Trials MCP Server)"


def load_config() -> APIConfig:
    """
    Load configuration from environment variables.
    
    Returns:
        APIConfig: Configuration object with values from environment variables
    """
    config = APIConfig()
    
    # Clinical Trials API Configuration
    config.clinicaltrials_api_url = os.getenv(
        "CLINICALTRIALS_API_URL", 
        config.clinicaltrials_api_url
    )
    config.clinicaltrials_timeout = int(os.getenv(
        "CLINICALTRIALS_TIMEOUT", 
        str(config.clinicaltrials_timeout)
    ))
    
    # Anthropic API Configuration
    config.anthropic_api_url = os.getenv(
        "ANTHROPIC_API_URL", 
        config.anthropic_api_url
    )
    config.anthropic_api_key = os.getenv(
        "ANTHROPIC_API_KEY", 
        config.anthropic_api_key
    )
    config.anthropic_model = os.getenv(
        "ANTHROPIC_MODEL", 
        config.anthropic_model
    )
    config.anthropic_max_tokens = int(os.getenv(
        "ANTHROPIC_MAX_TOKENS", 
        str(config.anthropic_max_tokens)
    ))
    config.anthropic_timeout = int(os.getenv(
        "ANTHROPIC_TIMEOUT", 
        str(config.anthropic_timeout)
    ))
    
    # Retry Configuration
    config.max_retries = int(os.getenv(
        "MAX_RETRIES", 
        str(config.max_retries)
    ))
    config.retry_initial_delay = float(os.getenv(
        "RETRY_INITIAL_DELAY", 
        str(config.retry_initial_delay)
    ))
    config.retry_backoff_factor = float(os.getenv(
        "RETRY_BACKOFF_FACTOR", 
        str(config.retry_backoff_factor)
    ))
    config.retry_max_delay = float(os.getenv(
        "RETRY_MAX_DELAY", 
        str(config.retry_max_delay)
    ))
    config.retry_jitter = os.getenv(
        "RETRY_JITTER", 
        str(config.retry_jitter)
    ).lower() in ('true', '1', 'yes', 'on')
    
    # Cache Configuration
    config.cache_size = int(os.getenv(
        "CACHE_SIZE", 
        str(config.cache_size)
    ))
    config.cache_ttl = int(os.getenv(
        "CACHE_TTL", 
        str(config.cache_ttl)
    ))
    
    # Circuit Breaker Configuration
    config.circuit_breaker_failure_threshold = int(os.getenv(
        "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 
        str(config.circuit_breaker_failure_threshold)
    ))
    config.circuit_breaker_recovery_timeout = int(os.getenv(
        "CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 
        str(config.circuit_breaker_recovery_timeout)
    ))
    
    # User Agent Configuration
    config.user_agent = os.getenv(
        "USER_AGENT", 
        config.user_agent
    )
    
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
    if not config.clinicaltrials_api_url.startswith(('http://', 'https://')):
        errors.append("CLINICALTRIALS_API_URL must be a valid URL")
    
    if not config.anthropic_api_url.startswith(('http://', 'https://')):
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
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info("Configuration loaded successfully", extra={
        "clinicaltrials_api_url": config.clinicaltrials_api_url,
        "anthropic_api_url": config.anthropic_api_url,
        "anthropic_model": config.anthropic_model,
        "max_retries": config.max_retries,
        "cache_size": config.cache_size,
        "action": "config_loaded"
    })
    
    return config


# Global configuration instance
_config: Optional[APIConfig] = None


def get_global_config() -> APIConfig:
    """
    Get the global configuration instance (lazy-loaded).
    
    Returns:
        APIConfig: Global configuration instance
    """
    global _config
    if _config is None:
        _config = get_config()
    return _config


def reset_global_config() -> None:
    """
    Reset the global configuration instance (useful for testing).
    """
    global _config
    _config = None