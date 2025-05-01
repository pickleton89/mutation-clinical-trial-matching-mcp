#!/usr/bin/env python3
import sys
from fastmcp import FastMCP
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials as summarize_trial_data

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
    
    trials_data = query_clinical_trials(mutation)
    if trials_data and "studies" in trials_data:
        summary = summarize_trial_data(trials_data["studies"])
    else:
        summary = "No trials found or error in fetching trials."
    
    return summary

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
