"""
Unified Clinical Trials MCP Server supporting both sync and async execution modes.

This server consolidates the functionality from servers/primary.py and servers/legacy/sync_server.py
into a single implementation that can operate in either synchronous or asynchronous mode
based on configuration or auto-detection.

Features:
- Unified MCP tool interface supporting both sync/async
- Runtime mode selection via environment variables
- Backward compatibility with existing tool signatures
- Auto-detection of execution context
- Enterprise features: caching, circuit breakers, metrics, health checks
- Cache warming and management
- Comprehensive monitoring and analytics
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, Any, Optional

from fastmcp import FastMCP
from mcp import ErrorData, McpError

from clinicaltrials.config import get_config
from clinicaltrials.unified_nodes import QueryTrialsNode, SummarizeTrialsNode, BatchQueryTrialsNode
from utils.unified_node import UnifiedFlow
from utils.metrics import export_json, export_prometheus, get_metrics
from utils.circuit_breaker import get_all_circuit_breaker_stats


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class UnifiedMCPServer:
    """
    Unified MCP server supporting both sync and async execution modes.
    
    This server can operate in either synchronous or asynchronous mode based on:
    1. Explicit configuration via MCP_ASYNC_MODE environment variable
    2. Auto-detection of execution context
    3. Runtime mode selection
    """
    
    def __init__(self, async_mode: Optional[bool] = None):
        """
        Initialize the unified MCP server.
        
        Args:
            async_mode: Force sync (False) or async (True) mode. 
                       If None, auto-detect from environment.
        """
        self.async_mode = self._determine_async_mode(async_mode)
        self.app = FastMCP("Clinical Trials Unified MCP Server")
        
        # Global flow instances
        self.single_flow: Optional[UnifiedFlow] = None
        self.batch_flow: Optional[UnifiedFlow] = None
        
        # Server info
        self.version = "0.2.1"
        self.service_name = f"clinical-trials-mcp-{'async' if self.async_mode else 'sync'}"
        
        logger.info(
            f"Initialized Unified MCP Server in {'async' if self.async_mode else 'sync'} mode",
            extra={
                "action": "unified_server_initialized",
                "async_mode": self.async_mode,
                "service_name": self.service_name,
                "version": self.version
            }
        )
        
        # Set up tools
        self._setup_tools()
    
    def _determine_async_mode(self, explicit_mode: Optional[bool]) -> bool:
        """
        Determine whether to use async mode.
        
        Args:
            explicit_mode: Explicitly requested mode
            
        Returns:
            True for async mode, False for sync mode
        """
        if explicit_mode is not None:
            logger.info(f"Using explicit async mode: {explicit_mode}")
            return explicit_mode
        
        # Check environment variable
        env_mode = os.getenv("MCP_ASYNC_MODE", "").lower()
        if env_mode in ("true", "1", "yes", "on"):
            logger.info("Async mode enabled via MCP_ASYNC_MODE environment variable")
            return True
        elif env_mode in ("false", "0", "no", "off"):
            logger.info("Sync mode enabled via MCP_ASYNC_MODE environment variable")
            return False
        
        # Auto-detect based on event loop
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                logger.info("Auto-detected async mode (event loop is running)")
                return True
        except RuntimeError:
            pass
        
        # Default to async mode for better performance
        logger.info("Defaulting to async mode for better performance")
        return True
    
    def _setup_tools(self):
        """Set up MCP tools based on the selected mode."""
        if self.async_mode:
            self._setup_async_tools()
        else:
            self._setup_sync_tools()
        
        # Set up common monitoring tools (work in both modes)
        self._setup_monitoring_tools()
    
    def _setup_async_tools(self):
        """Set up async MCP tools."""
        
        @self.app.tool()
        async def summarize_trials(mutation: str) -> str:
            """
            Primary async function for summarizing clinical trials.

            Query clinical trials for a specific mutation and return a summary.
            This function uses async/await with httpx for high-performance concurrent requests.

            Args:
                mutation: The genetic mutation to search for (e.g., "EGFR L858R")

            Returns:
                A formatted summary of relevant clinical trials

            Raises:
                McpError: If there's an error in processing the mutation query
            """
            return await self._summarize_trials_async_impl(mutation)
        
        @self.app.tool()
        async def summarize_trials_async(mutation: str) -> str:
            """
            Explicit async function for summarizing clinical trials.
            
            Identical to summarize_trials but explicitly named for async usage.
            """
            return await self._summarize_trials_async_impl(mutation)
        
        @self.app.tool()
        async def summarize_multiple_trials(mutations: str) -> str:
            """
            Async batch version for multiple mutations.

            Query clinical trials for multiple mutations concurrently and return a combined summary.

            Args:
                mutations: Comma-separated list of mutations (e.g., "EGFR L858R,BRAF V600E,KRAS G12C")

            Returns:
                A formatted summary of relevant clinical trials for all mutations
            """
            return await self._summarize_multiple_trials_async_impl(mutations)
        
        # Async-only enterprise features
        @self.app.tool()
        async def get_health_status() -> str:
            """
            Returns the comprehensive health status of the MCP server and its components.
            
            Returns:
                JSON string containing health status with async-specific metrics
            """
            return await self._get_async_health_status()
        
        @self.app.tool()
        async def get_cache_analytics() -> str:
            """
            Returns comprehensive cache analytics and performance metrics.
            """
            return await self._get_cache_analytics()
        
        @self.app.tool()
        async def get_cache_report() -> str:
            """
            Returns a formatted cache performance report.
            """
            return await self._get_cache_report()
        
        @self.app.tool()
        async def warm_cache() -> str:
            """
            Manually trigger cache warming for common mutations.
            """
            return await self._warm_cache()
        
        @self.app.tool()
        async def invalidate_cache(pattern: str = "*") -> str:
            """
            Manually trigger cache invalidation for a specific pattern.
            """
            return await self._invalidate_cache(pattern)
    
    def _setup_sync_tools(self):
        """Set up sync MCP tools."""
        
        @self.app.tool()
        def summarize_trials(mutation: str) -> str:
            """
            Synchronous function for summarizing clinical trials.

            Query clinical trials for a specific mutation and return a summary.
            This function uses synchronous requests for simple, blocking operation.

            Args:
                mutation: The genetic mutation to search for (e.g., "EGFR L858R")

            Returns:
                A formatted summary of relevant clinical trials

            Raises:
                McpError: If there's an error in processing the mutation query
            """
            return self._summarize_trials_sync_impl(mutation)
        
        @self.app.tool()
        def summarize_multiple_trials(mutations: str) -> str:
            """
            Sync batch version for multiple mutations.
            
            Args:
                mutations: Comma-separated list of mutations
                
            Returns:
                Combined summary for all mutations
            """
            return self._summarize_multiple_trials_sync_impl(mutations)
        
        @self.app.tool()
        def get_health_status() -> str:
            """
            Returns the health status of the MCP server and its components.
            """
            return self._get_sync_health_status()
    
    def _setup_monitoring_tools(self):
        """Set up monitoring tools that work in both modes."""
        
        @self.app.tool()
        def get_metrics_json() -> str:
            """
            Returns current metrics in JSON format.

            Returns:
                JSON string containing all current metrics including:
                - Counters (API calls, cache hits/misses, errors)
                - Gauges (current values like cache size, hit rates)
                - Histograms (request durations, response sizes, etc.)
            """
            try:
                return export_json()
            except Exception as e:
                logger.error(f"Error exporting metrics as JSON: {e}")
                return json.dumps(
                    {"error": f"Failed to export metrics: {str(e)}", "timestamp": time.time()}
                )
        
        @self.app.tool()
        def get_metrics_prometheus() -> str:
            """
            Returns current metrics in Prometheus format.

            Returns:
                Prometheus-formatted metrics string suitable for scraping by monitoring systems.
                Includes all counters, gauges, and histograms with proper type annotations.
            """
            try:
                return export_prometheus()
            except Exception as e:
                logger.error(f"Error exporting metrics as Prometheus: {e}")
                return f"# Error exporting metrics: {str(e)}"
        
        @self.app.tool()
        def get_circuit_breaker_status() -> str:
            """
            Returns detailed circuit breaker status and statistics.

            Returns:
                JSON string containing circuit breaker information including:
                - Current states (CLOSED, OPEN, HALF_OPEN)
                - Failure and success counts
                - State change history
                - Last failure/success times
            """
            try:
                cb_stats = get_all_circuit_breaker_stats()

                status = {"timestamp": time.time(), "circuit_breakers": {}}

                for name, stats in cb_stats.items():
                    status["circuit_breakers"][name] = {
                        "failure_count": stats.failure_count,
                        "success_count": stats.success_count,
                        "total_calls": stats.total_calls,
                        "state_changes": stats.state_changes,
                        "last_failure_time": stats.last_failure_time,
                        "last_success_time": stats.last_success_time,
                        "last_failure_age_seconds": time.time() - stats.last_failure_time
                        if stats.last_failure_time
                        else None,
                        "last_success_age_seconds": time.time() - stats.last_success_time
                        if stats.last_success_time
                        else None,
                    }

                return json.dumps(status, indent=2)

            except Exception as e:
                logger.error(f"Error getting circuit breaker status: {e}")
                return json.dumps(
                    {"error": f"Failed to get circuit breaker status: {str(e)}", "timestamp": time.time()}
                )
    
    def initialize_flows(self):
        """Initialize the unified flows for single and batch processing."""
        logger.info("Initializing unified flows")
        
        # Initialize single mutation flow
        query_node = QueryTrialsNode(async_mode=self.async_mode)
        summarize_node = SummarizeTrialsNode(async_mode=self.async_mode)
        
        # Use PocketFlow chaining syntax
        query_node >> summarize_node
        
        self.single_flow = UnifiedFlow(
            start_node=query_node,
            async_mode=self.async_mode
        )
        self.single_flow.add_node(summarize_node)
        
        # Initialize batch mutation flow
        batch_query_node = BatchQueryTrialsNode(async_mode=self.async_mode)
        batch_summarize_node = SummarizeTrialsNode(async_mode=self.async_mode)
        
        # Use PocketFlow chaining syntax for batch flow
        batch_query_node >> batch_summarize_node
        
        self.batch_flow = UnifiedFlow(
            start_node=batch_query_node,
            async_mode=self.async_mode
        )
        self.batch_flow.add_node(batch_summarize_node)
        
        logger.info(
            f"Unified flows initialized in {'async' if self.async_mode else 'sync'} mode",
            extra={
                "action": "flows_initialized",
                "async_mode": self.async_mode,
                "single_flow_nodes": len(self.single_flow.nodes),
                "batch_flow_nodes": len(self.batch_flow.nodes)
            }
        )
    
    # Core implementation methods
    async def _summarize_trials_async_impl(self, mutation: str) -> str:
        """Internal async implementation for summarizing clinical trials."""
        try:
            logger.info(f"Async querying for: {mutation}")

            # Validate input
            if not mutation or not isinstance(mutation, str) or not mutation.strip():
                logger.error("Invalid mutation parameter provided")
                raise McpError(
                    ErrorData(code=-1, message="Mutation parameter must be a non-empty string")
                )

            if self.single_flow is None:
                self.initialize_flows()

            assert self.single_flow is not None, "single_flow should be initialized"

            # Create shared context
            shared = {
                "mutation": mutation.strip(),
                "min_rank": 1,
                "max_rank": 20,  # Get more results for better summary
                "timeout": 15,
            }

            logger.info(f"Starting async flow for mutation: {mutation}")

            # Run async flow
            result = await self.single_flow.aexecute(shared)

            # Check for successful execution
            if "summary" in result:
                logger.info(f"Successfully generated async summary for mutation: {mutation}")
                return result["summary"]
            elif "error" in result:
                logger.error(f"Async flow execution failed: {result['error']}")
                raise McpError(
                    ErrorData(code=-2, message=f"Failed to process mutation query: {result['error']}")
                )
            else:
                logger.error(f"Unexpected async flow result: {result}")
                raise McpError(
                    ErrorData(code=-3, message="No trials found or unexpected error in processing")
                )

        except McpError:
            raise
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise McpError(
                ErrorData(code=-4, message=f"Invalid input or configuration: {str(e)}")
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error in async summarize_trials: {e}", exc_info=True)
            raise McpError(ErrorData(code=-5, message=f"An unexpected error occurred: {str(e)}")) from e
    
    def _summarize_trials_sync_impl(self, mutation: str) -> str:
        """Internal sync implementation for summarizing clinical trials."""
        try:
            logger.info(f"Sync querying for: {mutation}")

            # Validate input
            if not mutation or not isinstance(mutation, str) or not mutation.strip():
                logger.error("Invalid mutation parameter provided")
                raise McpError(
                    ErrorData(code=-1, message="Mutation parameter must be a non-empty string")
                )

            if self.single_flow is None:
                self.initialize_flows()

            assert self.single_flow is not None, "single_flow should be initialized"

            # Create shared context
            shared = {
                "mutation": mutation.strip(),
                "min_rank": 1,
                "max_rank": 10,  # Fewer results for sync processing
                "timeout": 10,
            }

            logger.info(f"Starting sync flow for mutation: {mutation}")

            # Run sync flow
            result = self.single_flow.execute(shared)

            # Check for successful execution
            if "summary" in result:
                logger.info(f"Successfully generated sync summary for mutation: {mutation}")
                return result["summary"]
            elif "error" in result:
                logger.error(f"Sync flow execution failed: {result['error']}")
                raise McpError(
                    ErrorData(code=-2, message=f"Failed to process mutation query: {result['error']}")
                )
            else:
                logger.error(f"Unexpected sync flow result: {result}")
                raise McpError(
                    ErrorData(code=-3, message="No trials found or unexpected error in processing")
                )

        except McpError:
            raise
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            raise McpError(
                ErrorData(code=-4, message=f"Invalid input or configuration: {str(e)}")
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error in sync summarize_trials: {e}", exc_info=True)
            raise McpError(ErrorData(code=-5, message=f"An unexpected error occurred: {str(e)}")) from e
    
    async def _summarize_multiple_trials_async_impl(self, mutations: str) -> str:
        """Internal async implementation for batch processing multiple mutations."""
        try:
            # Parse mutations
            mutation_list = [m.strip() for m in mutations.split(",") if m.strip()]

            if not mutation_list:
                return "Error: No valid mutations provided"

            if len(mutation_list) > 10:
                return "Error: Too many mutations (max 10)"

            # Initialize batch flow if needed
            if self.batch_flow is None:
                self.initialize_flows()

            assert self.batch_flow is not None, "batch_flow should be initialized"

            # Create shared context
            shared = {
                "mutations": mutation_list,
                "min_rank": 1,
                "max_rank": 10,  # Fewer results per mutation for batch
                "timeout": 15,
                "max_concurrent": 5,
            }

            logger.info(f"Starting async batch flow for {len(mutation_list)} mutations")

            # Run async batch flow
            result = await self.batch_flow.aexecute(shared)

            # Check for errors
            if "error" in result:
                logger.error(f"Error in async batch flow: {result['error']}")
                return f"Error: {result['error']}"

            # Return summary
            summary = result.get("summary", "No summary generated")
            logger.info(f"Async batch flow completed successfully for {len(mutation_list)} mutations")

            return summary

        except Exception as e:
            logger.error(f"Unexpected error in async batch summarize_trials: {e}", exc_info=True)
            return f"Error: {str(e)}"
    
    def _summarize_multiple_trials_sync_impl(self, mutations: str) -> str:
        """Internal sync implementation for batch processing multiple mutations."""
        try:
            # Parse mutations
            mutation_list = [m.strip() for m in mutations.split(",") if m.strip()]

            if not mutation_list:
                return "Error: No valid mutations provided"

            if len(mutation_list) > 5:  # Lower limit for sync processing
                return "Error: Too many mutations for sync processing (max 5)"

            # Process each mutation sequentially in sync mode
            results = []
            for mutation in mutation_list:
                try:
                    summary = self._summarize_trials_sync_impl(mutation)
                    results.append(f"## {mutation}\n\n{summary}")
                except Exception as e:
                    results.append(f"## {mutation}\n\nError: {str(e)}")

            # Combine results
            combined_summary = f"# Clinical Trials Summary for Multiple Mutations\n\n"
            combined_summary += f"Processed {len(mutation_list)} mutations:\n\n"
            combined_summary += "\n\n---\n\n".join(results)

            return combined_summary

        except Exception as e:
            logger.error(f"Unexpected error in sync batch summarize_trials: {e}", exc_info=True)
            return f"Error: {str(e)}"
    
    async def _get_async_health_status(self) -> str:
        """Get comprehensive health status for async mode."""
        try:
            # Get circuit breaker statistics
            cb_stats = get_all_circuit_breaker_stats()

            # Get basic metrics
            metrics = get_metrics()

            # Get cache analytics (async-only feature)
            try:
                from utils.cache_strategies import get_cache_analytics as get_cache_analytics_instance
                cache_analytics = await get_cache_analytics_instance().get_comprehensive_stats()
            except Exception as e:
                logger.warning(f"Could not get cache analytics: {e}")
                cache_analytics = {"error": str(e)}

            # Create health status
            health_status = {
                "status": "healthy",
                "timestamp": time.time(),
                "service": self.service_name,
                "version": self.version,
                "mode": "async",
                "features": {
                    "async_support": True,
                    "batch_processing": True,
                    "distributed_caching": True,
                    "cache_warming": True,
                    "smart_invalidation": True,
                    "unified_architecture": True,
                },
                "circuit_breakers": {
                    name: {
                        "failure_count": stats.failure_count,
                        "success_count": stats.success_count,
                        "total_calls": stats.total_calls,
                        "last_failure_time": stats.last_failure_time,
                        "last_success_time": stats.last_success_time,
                    }
                    for name, stats in cb_stats.items()
                },
                "cache_analytics": cache_analytics,
                "metrics_summary": {
                    "total_counters": len(metrics.get("counters", {})),
                    "total_gauges": len(metrics.get("gauges", {})),
                    "total_histograms": len(metrics.get("histograms", {})),
                },
            }

            return json.dumps(health_status, indent=2)

        except Exception as e:
            logger.error(f"Error getting async health status: {e}")
            return json.dumps({"status": "error", "error": str(e), "timestamp": time.time()})
    
    def _get_sync_health_status(self) -> str:
        """Get health status for sync mode."""
        try:
            # Get circuit breaker statistics
            cb_stats = get_all_circuit_breaker_stats()

            # Get basic metrics
            metrics = get_metrics()

            # Create health status
            health_status = {
                "status": "healthy",
                "timestamp": time.time(),
                "service": self.service_name,
                "version": self.version,
                "mode": "sync",
                "features": {
                    "async_support": False,
                    "batch_processing": True,
                    "distributed_caching": False,
                    "cache_warming": False,
                    "smart_invalidation": False,
                    "unified_architecture": True,
                },
                "circuit_breakers": {
                    name: {
                        "failure_count": stats.failure_count,
                        "success_count": stats.success_count,
                        "total_calls": stats.total_calls,
                        "last_failure_time": stats.last_failure_time,
                        "last_success_time": stats.last_success_time,
                    }
                    for name, stats in cb_stats.items()
                },
                "metrics_summary": {
                    "total_counters": len(metrics.get("counters", {})),
                    "total_gauges": len(metrics.get("gauges", {})),
                    "total_histograms": len(metrics.get("histograms", {})),
                },
            }

            return json.dumps(health_status, indent=2)

        except Exception as e:
            logger.error(f"Error getting sync health status: {e}")
            return json.dumps({"status": "error", "error": str(e), "timestamp": time.time()})
    
    # Async-only cache management methods
    async def _get_cache_analytics(self) -> str:
        """Get comprehensive cache analytics (async-only)."""
        try:
            from utils.cache_strategies import get_cache_analytics as get_cache_analytics_instance
            analytics = get_cache_analytics_instance()

            # Get comprehensive stats
            stats = await analytics.get_comprehensive_stats()

            # Get efficiency analysis
            efficiency = await analytics.analyze_cache_efficiency()

            # Combine all analytics
            cache_analytics = {
                "timestamp": time.time(),
                "comprehensive_stats": stats,
                "efficiency_analysis": efficiency,
                "cache_health": "healthy" if efficiency["efficiency_score"] > 70 else "degraded",
            }

            return json.dumps(cache_analytics, indent=2)

        except Exception as e:
            logger.error(f"Error getting cache analytics: {e}")
            return json.dumps(
                {"error": f"Failed to get cache analytics: {str(e)}", "timestamp": time.time()}
            )
    
    async def _get_cache_report(self) -> str:
        """Get formatted cache performance report (async-only)."""
        try:
            from utils.cache_strategies import get_cache_analytics as get_cache_analytics_instance
            analytics = get_cache_analytics_instance()
            report = await analytics.generate_cache_report()
            return report

        except Exception as e:
            logger.error(f"Error generating cache report: {e}")
            return f"# Cache Report Error\n\nFailed to generate cache report: {str(e)}"
    
    async def _warm_cache(self) -> str:
        """Manually trigger cache warming (async-only)."""
        try:
            from utils.cache_strategies import get_cache_warmer

            warmer = get_cache_warmer()

            # Warm common mutations
            common_results = await warmer.warm_common_mutations()

            # Warm trending mutations
            trending_results = await warmer.warm_trending_mutations()

            # Get warming statistics
            stats = warmer.get_warming_stats()

            results = {
                "timestamp": time.time(),
                "common_mutations_warmed": common_results,
                "trending_mutations_warmed": trending_results,
                "warming_statistics": stats,
                "status": "completed",
            }

            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Error warming cache: {e}")
            return json.dumps({"error": f"Failed to warm cache: {str(e)}", "timestamp": time.time()})
    
    async def _invalidate_cache(self, pattern: str = "*") -> str:
        """Manually trigger cache invalidation (async-only)."""
        try:
            from utils.cache_strategies import get_smart_invalidator

            invalidator = get_smart_invalidator()

            if pattern == "*":
                # Invalidate all patterns
                invalidated = await invalidator.invalidate_pattern_async("*")
            else:
                # Invalidate specific pattern
                invalidated = await invalidator.invalidate_pattern_async(pattern)

            results = {
                "timestamp": time.time(),
                "pattern": pattern,
                "invalidated_count": invalidated,
                "status": "completed",
            }

            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return json.dumps(
                {"error": f"Failed to invalidate cache: {str(e)}", "timestamp": time.time()}
            )
    
    async def startup_tasks(self):
        """Perform startup tasks including cache warming (async mode only)."""
        if not self.async_mode:
            logger.info("Startup tasks skipped (sync mode)")
            return
        
        try:
            from utils.cache_strategies import get_cache_warmer

            logger.info("Performing startup tasks...")

            # Warm cache with common mutations
            warmer = get_cache_warmer()
            common_count = await warmer.warm_common_mutations()
            trending_count = await warmer.warm_trending_mutations()

            logger.info(
                f"Cache warming completed: {common_count} common, {trending_count} trending mutations"
            )

        except Exception as e:
            logger.warning(f"Startup tasks failed (non-critical): {e}")
    
    async def cleanup(self):
        """Clean up resources."""
        if self.async_mode:
            try:
                from utils.async_call_llm import cleanup_async_clients
                await cleanup_async_clients()
            except Exception as e:
                logger.error(f"Error during async cleanup: {e}")
        
        logger.info("Server cleanup completed")
    
    def run(self):
        """Main entry point to run the unified server."""
        try:
            # Validate configuration on startup
            try:
                config = get_config()
                logger.info("Configuration validated successfully")
            except ValueError as e:
                logger.error(f"Configuration validation failed: {e}")
                sys.exit(1)
            
            # Initialize flows
            self.initialize_flows()

            logger.info(f"Starting Unified Clinical Trials MCP Server in {'async' if self.async_mode else 'sync'} mode")

            # Run startup tasks if in async mode
            if self.async_mode:
                try:
                    asyncio.run(self.startup_tasks())
                except Exception as e:
                    logger.warning(f"Startup tasks failed: {e}")

            # Run the server
            self.app.run()

        except KeyboardInterrupt:
            logger.info("Server interrupted by user")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)
        finally:
            # Clean up resources
            try:
                if self.async_mode:
                    asyncio.run(self.cleanup())
                else:
                    logger.info("Sync cleanup completed")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")


# Global server instance
unified_server = None


def create_server(async_mode: Optional[bool] = None) -> UnifiedMCPServer:
    """
    Create and return a unified MCP server instance.
    
    Args:
        async_mode: Force sync/async mode. If None, auto-detect.
        
    Returns:
        Configured UnifiedMCPServer instance
    """
    global unified_server
    if unified_server is None:
        unified_server = UnifiedMCPServer(async_mode=async_mode)
    assert unified_server is not None  # Type narrowing
    return unified_server


def main():
    """Main entry point for the unified MCP server."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()