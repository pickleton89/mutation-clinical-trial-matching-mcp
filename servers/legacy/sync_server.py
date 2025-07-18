#!/usr/bin/env python3
"""
Legacy Sync Clinical Trials MCP Server.

⚠️  DEPRECATED: This module is deprecated and will be removed in a future version.
    Please use servers.main.UnifiedMCPServer(async_mode=False) instead.

MIGRATION GUIDE:
    Old: from servers.legacy.sync_server import main; main()
    New: from servers.main import UnifiedMCPServer; UnifiedMCPServer(async_mode=False).run()
"""

import logging
import warnings

# Issue deprecation warning
warnings.warn(
    "servers.legacy.sync_server is deprecated. Use servers.main.UnifiedMCPServer(async_mode=False) instead.",
    DeprecationWarning,
    stacklevel=2
)

# Redirect to unified server implementation
from servers.legacy_compat import SyncServerCompat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logger.warning(
    "servers.legacy.sync_server is deprecated. Please migrate to servers.main.UnifiedMCPServer(async_mode=False)"
)

# Create compatibility wrapper
_compat_server = SyncServerCompat()

# Expose the FastMCP app for backward compatibility
mcp = _compat_server.mcp


# All tools are now handled by the unified server via the compatibility wrapper

def main():
    """Main entry point for the legacy sync MCP server (compatibility wrapper)."""
    logger.warning("servers.legacy.sync_server.main() is deprecated. Use UnifiedMCPServer(async_mode=False).run() instead.")
    _compat_server.main()


if __name__ == "__main__":
    main()
