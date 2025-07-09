#!/usr/bin/env python3
import logging
import sys
from fastmcp import FastMCP
from mcp import McpError, ErrorData
from utils.node import Flow
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
