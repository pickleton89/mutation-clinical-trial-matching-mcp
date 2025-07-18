"""
Configuration module for the unified MCP server.

This module provides configuration management for runtime mode selection,
server settings, and feature toggles for the unified clinical trials MCP server.
"""

import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for the unified MCP server."""
    
    # Execution mode
    async_mode: Optional[bool] = None  # None = auto-detect
    
    # Server settings
    service_name: str = "clinical-trials-mcp"
    version: str = "0.2.1"
    
    # Query settings
    default_min_rank: int = 1
    default_max_rank_sync: int = 10  # Lower for sync mode
    default_max_rank_async: int = 20  # Higher for async mode
    default_timeout_sync: float = 10.0
    default_timeout_async: float = 15.0
    
    # Batch processing
    max_mutations_sync: int = 5  # Lower limit for sync processing
    max_mutations_async: int = 10  # Higher limit for async processing
    max_concurrent_async: int = 5
    
    # Feature toggles
    enable_cache_warming: bool = True
    enable_cache_analytics: bool = True
    enable_distributed_caching: bool = True
    enable_smart_invalidation: bool = True
    enable_circuit_breakers: bool = True
    enable_metrics: bool = True
    
    # Monitoring
    enable_health_checks: bool = True
    enable_prometheus_metrics: bool = True
    enable_cache_reports: bool = True
    
    # Startup behavior
    run_startup_tasks: bool = True
    warmup_common_mutations: bool = True
    warmup_trending_mutations: bool = True
    
    # Environment overrides
    env_overrides: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Apply environment variable overrides after initialization."""
        self._apply_env_overrides()
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration."""
        
        # Async mode override
        env_async = os.getenv("MCP_ASYNC_MODE", "").lower()
        if env_async in ("true", "1", "yes", "on"):
            self.async_mode = True
            logger.info("Async mode enabled via MCP_ASYNC_MODE environment variable")
        elif env_async in ("false", "0", "no", "off"):
            self.async_mode = False
            logger.info("Sync mode enabled via MCP_ASYNC_MODE environment variable")
        
        # Service name override
        if service_name := os.getenv("MCP_SERVICE_NAME"):
            self.service_name = service_name
            logger.info(f"Service name overridden via environment: {service_name}")
        
        # Query limits
        if max_rank := os.getenv("MCP_MAX_RANK"):
            try:
                max_rank_int = int(max_rank)
                self.default_max_rank_sync = min(max_rank_int, 10)
                self.default_max_rank_async = max_rank_int
                logger.info(f"Max rank overridden via environment: {max_rank_int}")
            except ValueError:
                logger.warning(f"Invalid MCP_MAX_RANK value: {max_rank}")
        
        # Timeout overrides
        if timeout := os.getenv("MCP_TIMEOUT"):
            try:
                timeout_float = float(timeout)
                self.default_timeout_sync = timeout_float
                self.default_timeout_async = timeout_float
                logger.info(f"Timeout overridden via environment: {timeout_float}")
            except ValueError:
                logger.warning(f"Invalid MCP_TIMEOUT value: {timeout}")
        
        # Concurrency override
        if max_concurrent := os.getenv("MCP_MAX_CONCURRENT"):
            try:
                self.max_concurrent_async = int(max_concurrent)
                logger.info(f"Max concurrent overridden via environment: {max_concurrent}")
            except ValueError:
                logger.warning(f"Invalid MCP_MAX_CONCURRENT value: {max_concurrent}")
        
        # Feature toggles
        self._apply_feature_toggle("MCP_ENABLE_CACHE_WARMING", "enable_cache_warming")
        self._apply_feature_toggle("MCP_ENABLE_CACHE_ANALYTICS", "enable_cache_analytics")
        self._apply_feature_toggle("MCP_ENABLE_DISTRIBUTED_CACHING", "enable_distributed_caching")
        self._apply_feature_toggle("MCP_ENABLE_SMART_INVALIDATION", "enable_smart_invalidation")
        self._apply_feature_toggle("MCP_ENABLE_CIRCUIT_BREAKERS", "enable_circuit_breakers")
        self._apply_feature_toggle("MCP_ENABLE_METRICS", "enable_metrics")
        self._apply_feature_toggle("MCP_ENABLE_HEALTH_CHECKS", "enable_health_checks")
        self._apply_feature_toggle("MCP_ENABLE_PROMETHEUS_METRICS", "enable_prometheus_metrics")
        self._apply_feature_toggle("MCP_RUN_STARTUP_TASKS", "run_startup_tasks")
    
    def _apply_feature_toggle(self, env_var: str, config_attr: str):
        """Apply a boolean feature toggle from environment variable."""
        env_value = os.getenv(env_var, "").lower()
        if env_value in ("true", "1", "yes", "on"):
            setattr(self, config_attr, True)
            logger.info(f"{config_attr} enabled via {env_var}")
        elif env_value in ("false", "0", "no", "off"):
            setattr(self, config_attr, False)
            logger.info(f"{config_attr} disabled via {env_var}")
    
    def get_max_rank(self, async_mode: bool) -> int:
        """Get appropriate max rank based on execution mode."""
        return self.default_max_rank_async if async_mode else self.default_max_rank_sync
    
    def get_timeout(self, async_mode: bool) -> float:
        """Get appropriate timeout based on execution mode."""
        return self.default_timeout_async if async_mode else self.default_timeout_sync
    
    def get_max_mutations(self, async_mode: bool) -> int:
        """Get appropriate max mutations limit based on execution mode."""
        return self.max_mutations_async if async_mode else self.max_mutations_sync
    
    def get_effective_service_name(self, async_mode: bool) -> str:
        """Get effective service name with mode suffix."""
        mode_suffix = "async" if async_mode else "sync"
        return f"{self.service_name}-{mode_suffix}"
    
    def get_features_dict(self, async_mode: bool) -> Dict[str, bool]:
        """Get feature dictionary based on execution mode."""
        features = {
            "async_support": async_mode,
            "batch_processing": True,
            "unified_architecture": True,
            "circuit_breakers": self.enable_circuit_breakers,
            "metrics": self.enable_metrics,
            "health_checks": self.enable_health_checks,
            "prometheus_metrics": self.enable_prometheus_metrics,
        }
        
        # Async-only features
        if async_mode:
            features.update({
                "distributed_caching": self.enable_distributed_caching,
                "cache_warming": self.enable_cache_warming,
                "smart_invalidation": self.enable_smart_invalidation,
                "cache_analytics": self.enable_cache_analytics,
                "cache_reports": self.enable_cache_reports,
            })
        else:
            features.update({
                "distributed_caching": False,
                "cache_warming": False,
                "smart_invalidation": False,
                "cache_analytics": False,
                "cache_reports": False,
            })
        
        return features
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "async_mode": self.async_mode,
            "service_name": self.service_name,
            "version": self.version,
            "query_settings": {
                "default_min_rank": self.default_min_rank,
                "default_max_rank_sync": self.default_max_rank_sync,
                "default_max_rank_async": self.default_max_rank_async,
                "default_timeout_sync": self.default_timeout_sync,
                "default_timeout_async": self.default_timeout_async,
            },
            "batch_settings": {
                "max_mutations_sync": self.max_mutations_sync,
                "max_mutations_async": self.max_mutations_async,
                "max_concurrent_async": self.max_concurrent_async,
            },
            "features": {
                "enable_cache_warming": self.enable_cache_warming,
                "enable_cache_analytics": self.enable_cache_analytics,
                "enable_distributed_caching": self.enable_distributed_caching,
                "enable_smart_invalidation": self.enable_smart_invalidation,
                "enable_circuit_breakers": self.enable_circuit_breakers,
                "enable_metrics": self.enable_metrics,
                "enable_health_checks": self.enable_health_checks,
                "enable_prometheus_metrics": self.enable_prometheus_metrics,
                "enable_cache_reports": self.enable_cache_reports,
            },
            "startup": {
                "run_startup_tasks": self.run_startup_tasks,
                "warmup_common_mutations": self.warmup_common_mutations,
                "warmup_trending_mutations": self.warmup_trending_mutations,
            }
        }


# Global configuration instance
_config: Optional[ServerConfig] = None


def get_server_config() -> ServerConfig:
    """
    Get the global server configuration instance.
    
    Returns:
        ServerConfig instance with environment overrides applied
    """
    global _config
    if _config is None:
        _config = ServerConfig()
        logger.info("Server configuration initialized")
    # Type narrowing by creating local variable
    config = _config
    assert config is not None
    return config


def create_server_config(**overrides) -> ServerConfig:
    """
    Create a new server configuration with specific overrides.
    
    Args:
        **overrides: Configuration overrides
        
    Returns:
        New ServerConfig instance
    """
    config = ServerConfig()
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
            logger.info(f"Configuration override: {key} = {value}")
        else:
            logger.warning(f"Unknown configuration key: {key}")
    
    return config


def detect_async_mode() -> bool:
    """
    Detect whether to use async mode based on various factors.
    
    Returns:
        True for async mode, False for sync mode
    """
    config = get_server_config()
    
    # Check if explicitly configured
    if config.async_mode is not None:
        logger.info(f"Using explicit async mode: {config.async_mode}")
        return config.async_mode
    
    # Check event loop
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        if loop and loop.is_running():
            logger.info("Auto-detected async mode (event loop is running)")
            return True
    except RuntimeError:
        pass
    
    # Default to async for better performance
    logger.info("Defaulting to async mode for better performance")
    return True


def get_runtime_config(async_mode: Optional[bool] = None) -> Dict[str, Any]:
    """
    Get runtime configuration for a specific execution mode.
    
    Args:
        async_mode: Execution mode. If None, auto-detect.
        
    Returns:
        Runtime configuration dictionary
    """
    config = get_server_config()
    effective_async_mode = async_mode if async_mode is not None else detect_async_mode()
    
    return {
        "async_mode": effective_async_mode,
        "service_name": config.get_effective_service_name(effective_async_mode),
        "version": config.version,
        "max_rank": config.get_max_rank(effective_async_mode),
        "timeout": config.get_timeout(effective_async_mode),
        "max_mutations": config.get_max_mutations(effective_async_mode),
        "max_concurrent": config.max_concurrent_async if effective_async_mode else 1,
        "features": config.get_features_dict(effective_async_mode),
    }


# Configuration validation
def validate_server_config(config: ServerConfig) -> None:
    """
    Validate server configuration values.
    
    Args:
        config: Configuration to validate
        
    Raises:
        ValueError: If configuration is invalid
    """
    if config.default_min_rank < 1:
        raise ValueError("default_min_rank must be at least 1")
    
    if config.default_max_rank_sync < config.default_min_rank:
        raise ValueError("default_max_rank_sync must be >= default_min_rank")
    
    if config.default_max_rank_async < config.default_min_rank:
        raise ValueError("default_max_rank_async must be >= default_min_rank")
    
    if config.default_timeout_sync <= 0:
        raise ValueError("default_timeout_sync must be positive")
    
    if config.default_timeout_async <= 0:
        raise ValueError("default_timeout_async must be positive")
    
    if config.max_mutations_sync < 1:
        raise ValueError("max_mutations_sync must be at least 1")
    
    if config.max_mutations_async < 1:
        raise ValueError("max_mutations_async must be at least 1")
    
    if config.max_concurrent_async < 1:
        raise ValueError("max_concurrent_async must be at least 1")
    
    logger.info("Server configuration validation passed")


def print_config_summary(config: Optional[ServerConfig] = None) -> str:
    """
    Print a summary of the current configuration.
    
    Args:
        config: Configuration to summarize. If None, use global config.
        
    Returns:
        Configuration summary string
    """
    if config is None:
        config = get_server_config()
    
    summary_lines = [
        "# Unified MCP Server Configuration Summary",
        "",
        f"**Version:** {config.version}",
        f"**Service Name:** {config.service_name}",
        f"**Async Mode:** {config.async_mode if config.async_mode is not None else 'auto-detect'}",
        "",
        "## Query Settings",
        f"- Min Rank: {config.default_min_rank}",
        f"- Max Rank (Sync): {config.default_max_rank_sync}",
        f"- Max Rank (Async): {config.default_max_rank_async}",
        f"- Timeout (Sync): {config.default_timeout_sync}s",
        f"- Timeout (Async): {config.default_timeout_async}s",
        "",
        "## Batch Processing",
        f"- Max Mutations (Sync): {config.max_mutations_sync}",
        f"- Max Mutations (Async): {config.max_mutations_async}",
        f"- Max Concurrent (Async): {config.max_concurrent_async}",
        "",
        "## Features",
    ]
    
    features = [
        ("Cache Warming", config.enable_cache_warming),
        ("Cache Analytics", config.enable_cache_analytics),
        ("Distributed Caching", config.enable_distributed_caching),
        ("Smart Invalidation", config.enable_smart_invalidation),
        ("Circuit Breakers", config.enable_circuit_breakers),
        ("Metrics", config.enable_metrics),
        ("Health Checks", config.enable_health_checks),
        ("Prometheus Metrics", config.enable_prometheus_metrics),
        ("Cache Reports", config.enable_cache_reports),
    ]
    
    for feature_name, enabled in features:
        status = "✅ Enabled" if enabled else "❌ Disabled"
        summary_lines.append(f"- {feature_name}: {status}")
    
    summary_lines.extend([
        "",
        "## Startup Behavior",
        f"- Run Startup Tasks: {'✅ Yes' if config.run_startup_tasks else '❌ No'}",
        f"- Warmup Common Mutations: {'✅ Yes' if config.warmup_common_mutations else '❌ No'}",
        f"- Warmup Trending Mutations: {'✅ Yes' if config.warmup_trending_mutations else '❌ No'}",
    ])
    
    return "\n".join(summary_lines)