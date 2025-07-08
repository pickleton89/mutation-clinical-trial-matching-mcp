#!/usr/bin/env python3
import logging
import sys
from fastmcp import FastMCP
from utils.node import Flow
from clinicaltrials.nodes import QueryTrialsNode, SummarizeTrialsNode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

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
    """
    logger.info(f"Querying for: {mutation}")
    
    # Create nodes
    query_node = QueryTrialsNode(min_rank=1, max_rank=10, timeout=10)
    summarize_node = SummarizeTrialsNode()
    
    # Create flow
    flow = Flow(start=query_node)
    flow.add_node("summarize", summarize_node)
    
    # Run flow with shared context
    shared = {"mutation": mutation}
    result = flow.run(shared)
    
    # Return summary or error message
    if "summary" in result:
        return result["summary"]
    else:
        return "No trials found or error in fetching trials."

if __name__ == "__main__":
    try:
        logger.info("Clinical Trials MCP server starting...")
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by keyboard")
    except Exception as e:
        logger.error(f"Fatal server error: {e}")
    finally:
        logger.info("Server shutting down")
