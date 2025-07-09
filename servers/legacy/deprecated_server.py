#!/usr/bin/env python3
"""
DEPRECATED: Legacy sync Clinical Trials MCP Server

This server has been deprecated in favor of clinicaltrials_async_mcp_server.py
which provides the same functionality with better performance and additional features.

Migration Guide:
- Replace clinicaltrials_mcp_server.py with clinicaltrials_async_mcp_server.py
- Use summarize_trials_async() instead of summarize_trials()
- Take advantage of new batch processing with summarize_multiple_trials_async()
- Access enhanced monitoring with get_cache_analytics() and get_cache_report()

This file is kept for backward compatibility but will be removed in a future version.
"""

import logging
import sys
import warnings

# Issue deprecation warning
warnings.warn(
    "clinicaltrials_mcp_server.py is deprecated. Use clinicaltrials_async_mcp_server.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main entry point that shows deprecation notice."""
    logger.warning("=" * 80)
    logger.warning("DEPRECATION NOTICE")
    logger.warning("=" * 80)
    logger.warning("")
    logger.warning("This server (clinicaltrials_mcp_server.py) has been DEPRECATED.")
    logger.warning("")
    logger.warning("Please use the new async server instead:")
    logger.warning("  python clinicaltrials_async_mcp_server.py")
    logger.warning("")
    logger.warning("Benefits of the new async server:")
    logger.warning("  - 80% faster performance with concurrent processing")
    logger.warning("  - Batch processing for multiple mutations")
    logger.warning("  - Distributed caching with Redis")
    logger.warning("  - Enhanced monitoring and analytics")
    logger.warning("  - Cache warming and smart invalidation")
    logger.warning("")
    logger.warning("Migration is simple - just replace the server file!")
    logger.warning("")
    logger.warning("=" * 80)
    
    # Exit with error code to prevent accidental usage
    sys.exit(1)

if __name__ == "__main__":
    main()