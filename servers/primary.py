"""
Primary Clinical Trials MCP Server with async support and enterprise features.

This server provides high-performance async capabilities with comprehensive monitoring,
health checks, and enterprise-grade reliability features.
"""

import asyncio
import json
import logging
import sys
import time

from fastmcp import FastMCP
from mcp import ErrorData, McpError

from clinicaltrials.async_nodes import (
    AsyncBatchQueryTrialsNode,
    AsyncQueryTrialsNode,
    AsyncSummarizeTrialsNode,
)
from clinicaltrials.config import get_config
from utils.async_call_llm import cleanup_async_clients
from utils.cache_strategies import get_cache_analytics as get_cache_analytics_instance
from utils.circuit_breaker import get_all_circuit_breaker_stats

# from clinicaltrials.async_query import close_executor  # No longer needed - using pure async httpx
from utils.metrics import export_json, export_prometheus, get_metrics
from utils.node import AsyncFlow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Validate configuration on startup
try:
    config = get_config()
    logger.info("Configuration validated successfully")
except ValueError as e:
    logger.error(f"Configuration validation failed: {e}")
    sys.exit(1)

# Initialize FastMCP
mcp = FastMCP("Clinical Trials Async MCP Server")

# Global async flow instances
async_flow = None
async_batch_flow = None


def initialize_async_flow():
    """Initialize the async flow with nodes using new chaining syntax."""
    global async_flow

    # Create async nodes
    query_node = AsyncQueryTrialsNode()
    summarize_node = AsyncSummarizeTrialsNode()

    # Use new chaining syntax following PocketFlow documentation
    query_node >> summarize_node

    # Create async flow with automatic node registration
    async_flow = AsyncFlow(query_node)

    logger.info("Async flow initialized with query and summarize nodes using >> chaining")


def initialize_async_batch_flow():
    """Initialize the async batch flow for multiple mutations using new chaining syntax."""
    global async_batch_flow

    # Create async batch nodes
    batch_query_node = AsyncBatchQueryTrialsNode()
    summarize_node = AsyncSummarizeTrialsNode()

    # Use new chaining syntax following PocketFlow documentation
    batch_query_node >> summarize_node

    # Create async batch flow with automatic node registration
    async_batch_flow = AsyncFlow(batch_query_node)

    logger.info(
        "Async batch flow initialized with batch query and summarize nodes using >> chaining"
    )


async def _summarize_trials_async_impl(mutation: str) -> str:
    """
    Internal async implementation for summarizing clinical trials.

    This function contains the core logic that both sync and async versions call.

    Args:
        mutation: The genetic mutation to search for (e.g., "EGFR L858R")

    Returns:
        A formatted summary of relevant clinical trials

    Raises:
        McpError: If there's an error in processing the mutation query
    """
    try:
        logger.info(f"Async querying for: {mutation}")

        # Validate input
        if not mutation or not isinstance(mutation, str) or not mutation.strip():
            logger.error("Invalid mutation parameter provided")
            raise McpError(
                ErrorData(code=-1, message="Mutation parameter must be a non-empty string")
            )

        if async_flow is None:
            initialize_async_flow()

        assert async_flow is not None, "async_flow should be initialized"

        # Create shared context
        shared = {
            "mutation": mutation.strip(),
            "min_rank": 1,
            "max_rank": 20,  # Get more results for better summary
            "timeout": 15,
        }

        logger.info(f"Starting async flow for mutation: {mutation}")

        # Run async flow
        result = await async_flow.run(shared)

        # Check for successful execution
        if "summary" in result:
            logger.info(f"Successfully generated async summary for mutation: {mutation}")
            return result["summary"]
        elif "error" in result:
            # Handle known errors from the flow
            logger.error(f"Async flow execution failed: {result['error']}")
            raise McpError(
                ErrorData(code=-2, message=f"Failed to process mutation query: {result['error']}")
            )
        else:
            # Handle unexpected flow result
            logger.error(f"Unexpected async flow result: {result}")
            raise McpError(
                ErrorData(code=-3, message="No trials found or unexpected error in processing")
            )

    except McpError:
        # Re-raise MCP errors as-is
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise McpError(
            ErrorData(code=-4, message=f"Invalid input or configuration: {str(e)}")
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in async summarize_trials: {e}", exc_info=True)
        raise McpError(ErrorData(code=-5, message=f"An unexpected error occurred: {str(e)}")) from e


@mcp.tool()
async def summarize_trials_async(mutation: str) -> str:
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
    return await _summarize_trials_async_impl(mutation)


@mcp.tool()
async def summarize_multiple_trials_async(mutations: str) -> str:
    """
    Async batch version for multiple mutations.

    Query clinical trials for multiple mutations concurrently and return a combined summary.

    Args:
        mutations: Comma-separated list of mutations (e.g., "EGFR L858R,BRAF V600E,KRAS G12C")

    Returns:
        A formatted summary of relevant clinical trials for all mutations
    """
    try:
        # Parse mutations
        mutation_list = [m.strip() for m in mutations.split(",") if m.strip()]

        if not mutation_list:
            return "Error: No valid mutations provided"

        if len(mutation_list) > 10:
            return "Error: Too many mutations (max 10)"

        # Initialize batch flow if needed
        if "async_batch_flow" not in globals():
            initialize_async_batch_flow()

        assert async_batch_flow is not None, "async_batch_flow should be initialized"

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
        result = await async_batch_flow.run(shared)

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


@mcp.tool()
async def summarize_trials(mutation: str) -> str:
    """
    Backward compatible version of summarize_trials.

    This function wraps the async version to maintain backward compatibility.
    Note: This will be deprecated in favor of summarize_trials_async.

    Args:
        mutation: The genetic mutation to search for (e.g., "EGFR L858R")

    Returns:
        A formatted summary of relevant clinical trials
    """
    try:
        # Since we're in an async context, just call the async implementation
        return await _summarize_trials_async_impl(mutation)
    except Exception as e:
        logger.error(f"Error in wrapper: {e}", exc_info=True)
        return f"Error: {str(e)}"


@mcp.tool()
async def get_health_status() -> str:
    """
    Returns the comprehensive health status of the async MCP server and its components.

    Returns:
        A JSON string containing health status information including:
        - Service status and uptime
        - Circuit breaker states
        - Cache performance metrics
        - Async client health
        - Basic metrics summary
    """
    try:
        # Get circuit breaker statistics
        cb_stats = get_all_circuit_breaker_stats()

        # Get basic metrics
        metrics = get_metrics()

        # Get cache analytics
        try:
            cache_analytics = await get_cache_analytics_instance().get_comprehensive_stats()
        except Exception as e:
            logger.warning(f"Could not get cache analytics: {e}")
            cache_analytics = {"error": str(e)}

        # Create health status
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "clinical-trials-async-mcp",
            "version": "0.1.0",
            "features": {
                "async_support": True,
                "batch_processing": True,
                "distributed_caching": True,
                "cache_warming": True,
                "smart_invalidation": True,
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
        logger.error(f"Error getting health status: {e}")
        return json.dumps({"status": "error", "error": str(e), "timestamp": time.time()})


@mcp.tool()
def get_metrics_json() -> str:
    """
    Returns current metrics in JSON format.

    Returns:
        JSON string containing all current metrics including:
        - Async API call counters
        - Cache hit/miss ratios
        - Request duration histograms
        - Circuit breaker statistics
        - Async client pool metrics
    """
    try:
        return export_json()
    except Exception as e:
        logger.error(f"Error exporting metrics as JSON: {e}")
        return json.dumps(
            {"error": f"Failed to export metrics: {str(e)}", "timestamp": time.time()}
        )


@mcp.tool()
def get_metrics_prometheus() -> str:
    """
    Returns current metrics in Prometheus format.

    Returns:
        Prometheus-formatted metrics string suitable for scraping by monitoring systems.
        Includes all async counters, gauges, and histograms with proper type annotations.
    """
    try:
        return export_prometheus()
    except Exception as e:
        logger.error(f"Error exporting metrics as Prometheus: {e}")
        return f"# Error exporting metrics: {str(e)}"


@mcp.tool()
def get_circuit_breaker_status() -> str:
    """
    Returns detailed circuit breaker status and statistics for async operations.

    Returns:
        JSON string containing circuit breaker information including:
        - Current states (CLOSED, OPEN, HALF_OPEN)
        - Failure and success counts for async operations
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


@mcp.tool()
async def get_cache_analytics() -> str:
    """
    Returns comprehensive cache analytics and performance metrics.

    Returns:
        JSON string containing cache analytics including:
        - Hit rates and miss rates
        - Cache warming statistics
        - Invalidation metrics
        - Performance recommendations
        - Cache efficiency scores
    """
    try:
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


@mcp.tool()
async def get_cache_report() -> str:
    """
    Returns a formatted cache performance report.

    Returns:
        Markdown-formatted report with cache performance analysis and recommendations.
    """
    try:
        analytics = get_cache_analytics_instance()
        report = await analytics.generate_cache_report()
        return report

    except Exception as e:
        logger.error(f"Error generating cache report: {e}")
        return f"# Cache Report Error\n\nFailed to generate cache report: {str(e)}"


@mcp.tool()
async def warm_cache() -> str:
    """
    Manually trigger cache warming for common mutations.

    Returns:
        JSON string with cache warming results and statistics.
    """
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


@mcp.tool()
async def invalidate_cache(pattern: str = "*") -> str:
    """
    Manually trigger cache invalidation for a specific pattern.

    Args:
        pattern: Pattern to invalidate (default: "*" for all)

    Returns:
        JSON string with invalidation results.
    """
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


async def cleanup():
    """Clean up async resources."""
    await cleanup_async_clients()
    # No longer need to close executor - using pure async httpx


async def startup_tasks():
    """Perform startup tasks including cache warming."""
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


def main():
    """Main entry point for the primary async MCP server."""
    try:
        # Initialize the async flows
        initialize_async_flow()
        initialize_async_batch_flow()

        logger.info("Starting Clinical Trials Async MCP Server (Primary)")

        # Run startup tasks
        try:
            asyncio.run(startup_tasks())
        except Exception as e:
            logger.warning(f"Startup tasks failed: {e}")

        # Run the server
        mcp.run()

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        # Clean up async resources
        try:
            asyncio.run(cleanup())
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    main()
