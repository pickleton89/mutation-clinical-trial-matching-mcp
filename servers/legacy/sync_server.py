#!/usr/bin/env python3
import json
import logging
import sys
import time
from fastmcp import FastMCP
from mcp import McpError, ErrorData
from utils.node import Flow
from utils.metrics import get_metrics, export_prometheus, export_json
from utils.circuit_breaker import get_all_circuit_breaker_stats
from clinicaltrials.nodes import QueryTrialsNode, SummarizeTrialsNode
from clinicaltrials.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Validate configuration on startup
try:
    config = get_config()
    logger.info("Configuration validated successfully")
except ValueError as e:
    logger.error(f"Configuration validation failed: {e}")
    sys.exit(1)

# Initialize FastMCP server
mcp = FastMCP("Clinical Trials MCP")

@mcp.tool()
def summarize_trials(mutation: str) -> str:
    """
    Summarizes clinical trials for a specific genetic mutation.
    
    Args:
        mutation: The genetic mutation to search for (e.g., "BRAF V600E")
        
    Returns:
        A formatted summary of relevant clinical trials
        
    Raises:
        McpError: If there's an error in processing the mutation query
    """
    try:
        logger.info(f"Querying for: {mutation}")
        
        # Validate input
        if not mutation or not isinstance(mutation, str) or not mutation.strip():
            logger.error("Invalid mutation parameter provided")
            raise McpError(
                ErrorData(
                    code=-1,
                    message="Mutation parameter must be a non-empty string"
                )
            )
        
        # Create nodes
        query_node = QueryTrialsNode(min_rank=1, max_rank=10, timeout=10)
        summarize_node = SummarizeTrialsNode()
        
        # Create flow
        flow = Flow(start=query_node)
        flow.add_node("summarize", summarize_node)
        
        # Run flow with shared context
        shared = {"mutation": mutation.strip()}
        result = flow.run(shared)
        
        # Check for successful execution
        if "summary" in result:
            logger.info(f"Successfully generated summary for mutation: {mutation}")
            return result["summary"]
        elif "error" in result:
            # Handle known errors from the flow
            logger.error(f"Flow execution failed: {result['error']}")
            raise McpError(
                ErrorData(
                    code=-2,
                    message=f"Failed to process mutation query: {result['error']}"
                )
            )
        else:
            # Handle unexpected flow result
            logger.error(f"Unexpected flow result: {result}")
            raise McpError(
                ErrorData(
                    code=-3,
                    message="No trials found or unexpected error in processing"
                )
            )
            
    except McpError:
        # Re-raise MCP errors as-is
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise McpError(
            ErrorData(
                code=-4,
                message=f"Invalid input or configuration: {str(e)}"
            )
        )
    except Exception as e:
        logger.error(f"Unexpected error in summarize_trials: {e}", exc_info=True)
        raise McpError(
            ErrorData(
                code=-5,
                message=f"An unexpected error occurred: {str(e)}"
            )
        )

@mcp.tool()
def get_health_status() -> str:
    """
    Returns the health status of the MCP server and its components.
    
    Returns:
        A JSON string containing health status information including:
        - Service status and uptime
        - Circuit breaker states
        - Basic metrics summary
    """
    try:
        import json
        import time
        
        # Get circuit breaker statistics
        cb_stats = get_all_circuit_breaker_stats()
        
        # Get basic metrics
        metrics = get_metrics()
        
        # Create health status
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "clinical-trials-mcp",
            "version": "0.1.0",
            "circuit_breakers": {
                name: {
                    "failure_count": stats.failure_count,
                    "success_count": stats.success_count,
                    "total_calls": stats.total_calls,
                    "last_failure_time": stats.last_failure_time,
                    "last_success_time": stats.last_success_time
                }
                for name, stats in cb_stats.items()
            },
            "metrics_summary": {
                "total_counters": len(metrics.get("counters", {})),
                "total_gauges": len(metrics.get("gauges", {})),
                "total_histograms": len(metrics.get("histograms", {}))
            }
        }
        
        return json.dumps(health_status, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        })

@mcp.tool()
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
        return json.dumps({
            "error": f"Failed to export metrics: {str(e)}",
            "timestamp": time.time()
        })

@mcp.tool()
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

@mcp.tool()
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
        import json
        import time
        
        cb_stats = get_all_circuit_breaker_stats()
        
        status = {
            "timestamp": time.time(),
            "circuit_breakers": {}
        }
        
        for name, stats in cb_stats.items():
            status["circuit_breakers"][name] = {
                "failure_count": stats.failure_count,
                "success_count": stats.success_count,
                "total_calls": stats.total_calls,
                "state_changes": stats.state_changes,
                "last_failure_time": stats.last_failure_time,
                "last_success_time": stats.last_success_time,
                "last_failure_age_seconds": time.time() - stats.last_failure_time if stats.last_failure_time else None,
                "last_success_age_seconds": time.time() - stats.last_success_time if stats.last_success_time else None
            }
        
        return json.dumps(status, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        return json.dumps({
            "error": f"Failed to get circuit breaker status: {str(e)}",
            "timestamp": time.time()
        })

def main():
    """
    Main entry point for the Clinical Trials MCP server.
    """
    try:
        logger.info("Clinical Trials MCP server starting...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by keyboard")
    except Exception as e:
        logger.error(f"Fatal server error: {e}")
    finally:
        logger.info("Server shutting down")


if __name__ == "__main__":
    main()
