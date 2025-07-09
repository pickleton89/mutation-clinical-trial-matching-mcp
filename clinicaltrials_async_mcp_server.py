"""
Async version of Clinical Trials MCP Server with backward compatibility.

This server provides async capabilities while maintaining compatibility with the sync interface.
"""

import asyncio
import logging
from typing import Dict, Any
from fastmcp import FastMCP
from clinicaltrials.async_nodes import AsyncQueryTrialsNode, AsyncSummarizeTrialsNode, AsyncBatchQueryTrialsNode
from utils.node import AsyncFlow
from utils.async_call_llm import cleanup_async_clients

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("Clinical Trials Async MCP Server")

# Global async flow instance
async_flow = None

def initialize_async_flow():
    """Initialize the async flow with nodes."""
    global async_flow
    
    # Create async nodes
    query_node = AsyncQueryTrialsNode()
    summarize_node = AsyncSummarizeTrialsNode()
    
    # Create async flow
    async_flow = AsyncFlow(query_node)
    async_flow.add_node("summarize_trials", summarize_node)
    
    logger.info("Async flow initialized with query and summarize nodes")

def initialize_async_batch_flow():
    """Initialize the async batch flow for multiple mutations."""
    global async_batch_flow
    
    # Create async batch nodes
    batch_query_node = AsyncBatchQueryTrialsNode()
    summarize_node = AsyncSummarizeTrialsNode()
    
    # Create async batch flow
    async_batch_flow = AsyncFlow(batch_query_node)
    async_batch_flow.add_node("summarize_trials", summarize_node)
    
    logger.info("Async batch flow initialized with batch query and summarize nodes")

@mcp.tool()
async def summarize_trials_async(mutation: str) -> str:
    """
    Async version of summarize_trials.
    
    Query clinical trials for a specific mutation and return a summary.
    This is the async version that uses httpx for concurrent requests.
    
    Args:
        mutation: The genetic mutation to search for (e.g., "EGFR L858R")
        
    Returns:
        A formatted summary of relevant clinical trials
    """
    try:
        if async_flow is None:
            initialize_async_flow()
        
        # Create shared context
        shared = {
            "mutation": mutation,
            "min_rank": 1,
            "max_rank": 20,  # Get more results for better summary
            "timeout": 15
        }
        
        logger.info(f"Starting async flow for mutation: {mutation}")
        
        # Run async flow
        result = await async_flow.run(shared)
        
        # Check for errors
        if "error" in result:
            logger.error(f"Error in async flow: {result['error']}")
            return f"Error: {result['error']}"
        
        # Return summary
        summary = result.get("summary", "No summary generated")
        logger.info(f"Async flow completed successfully for mutation: {mutation}")
        
        return summary
        
    except Exception as e:
        logger.error(f"Unexpected error in async summarize_trials: {e}", exc_info=True)
        return f"Error: {str(e)}"

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
        if 'async_batch_flow' not in globals():
            initialize_async_batch_flow()
        
        # Create shared context
        shared = {
            "mutations": mutation_list,
            "min_rank": 1,
            "max_rank": 10,  # Fewer results per mutation for batch
            "timeout": 15,
            "max_concurrent": 5
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
def summarize_trials(mutation: str) -> str:
    """
    Backward compatible sync version of summarize_trials.
    
    This function wraps the async version to maintain backward compatibility.
    
    Args:
        mutation: The genetic mutation to search for (e.g., "EGFR L858R")
        
    Returns:
        A formatted summary of relevant clinical trials
    """
    try:
        # Run the async version in the current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an event loop, create a new task
            task = loop.create_task(summarize_trials_async(mutation))
            # This is a hack for compatibility - in production, the MCP server should handle this
            return "Error: Cannot run sync version in async context. Please use summarize_trials_async."
        else:
            # Run the async version
            return loop.run_until_complete(summarize_trials_async(mutation))
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}", exc_info=True)
        return f"Error: {str(e)}"

async def cleanup():
    """Clean up async resources."""
    await cleanup_async_clients()

def main():
    """Main entry point for the async MCP server."""
    try:
        # Initialize the async flow
        initialize_async_flow()
        initialize_async_batch_flow()
        
        logger.info("Starting Clinical Trials Async MCP Server")
        
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