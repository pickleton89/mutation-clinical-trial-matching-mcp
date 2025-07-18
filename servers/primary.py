"""
Primary Clinical Trials MCP Server with async support and enterprise features.

⚠️  DEPRECATED: This module is deprecated and will be removed in a future version.
    Please use servers.main.UnifiedMCPServer(async_mode=True) instead.

This server provides high-performance async capabilities with comprehensive monitoring,
health checks, and enterprise-grade reliability features.

MIGRATION GUIDE:
    Old: from servers.primary import main; main()
    New: from servers.main import UnifiedMCPServer; UnifiedMCPServer(async_mode=True).run()
"""

import logging
import warnings

# Issue deprecation warning
warnings.warn(
    "servers.primary is deprecated. Use servers.main.UnifiedMCPServer(async_mode=True) instead.",
    DeprecationWarning,
    stacklevel=2
)

# Redirect to unified server implementation
from servers.legacy_compat import AsyncServerCompat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logger.warning(
    "servers.primary is deprecated. Please migrate to servers.main.UnifiedMCPServer(async_mode=True)"
)

# Create compatibility wrapper
_compat_server = AsyncServerCompat()

# Expose the FastMCP app for backward compatibility
mcp = _compat_server.mcp

# Global async flow instances (for backward compatibility)
async_flow = None
async_batch_flow = None


def initialize_async_flow():
    """Initialize the async flow (compatibility wrapper)."""
    logger.warning("initialize_async_flow() is deprecated. Flows are auto-initialized in the unified server.")
    _compat_server.initialize_async_flow()


def initialize_async_batch_flow():
    """Initialize the async batch flow (compatibility wrapper)."""
    logger.warning("initialize_async_batch_flow() is deprecated. Flows are auto-initialized in the unified server.")
    _compat_server.initialize_async_batch_flow()


# Compatibility functions that redirect to unified server
# All tools are now handled by the unified server via the compatibility wrapper

async def cleanup():
    """Clean up async resources (compatibility wrapper)."""
    logger.warning("cleanup() is deprecated. Use UnifiedMCPServer.cleanup() instead.")
    await _compat_server.cleanup()


async def startup_tasks():
    """Perform startup tasks (compatibility wrapper)."""
    logger.warning("startup_tasks() is deprecated. Use UnifiedMCPServer.startup_tasks() instead.")
    await _compat_server.startup_tasks()


def main():
    """Main entry point for the primary async MCP server (compatibility wrapper)."""
    logger.warning("servers.primary.main() is deprecated. Use UnifiedMCPServer(async_mode=True).run() instead.")
    _compat_server.main()


if __name__ == "__main__":
    main()
