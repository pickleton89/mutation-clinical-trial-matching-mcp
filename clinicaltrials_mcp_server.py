#!/usr/bin/env python3
import sys
from fastmcp import FastMCP
from utils.node import Flow
from clinicaltrials.nodes import QueryTrialsNode, SummarizeTrialsNode

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
    print(f"Querying for: {mutation}", file=sys.stderr, flush=True)
    
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
        print("Clinical Trials MCP server starting...", file=sys.stderr, flush=True)
        mcp.run()
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server shutting down", file=sys.stderr, flush=True)
