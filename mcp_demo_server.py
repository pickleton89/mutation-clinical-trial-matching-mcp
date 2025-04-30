#!/usr/bin/env python3
"""
Simple MCP server using the official Python SDK.
This demonstrates a working example that you can build upon.
"""
from mcp.server.fastmcp import FastMCP
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Create an MCP server
mcp = FastMCP("Clinical Trials MCP")

# Add a tool to summarize clinical trials for a mutation
@mcp.tool()
def summarize_trials_for_mutation(mutation: str) -> str:
    """
    Summarize clinical trials related to a specific genetic mutation.
    
    Args:
        mutation: The genetic mutation to search for (e.g., 'EGFR L858R')
    
    Returns:
        A summary of relevant clinical trials
    """
    print(f"Querying for: {mutation}")
    
    # Call the existing query function
    trials_data = query_clinical_trials(mutation)
    
    if trials_data and "studies" in trials_data:
        # Use the existing summarize function
        summary = summarize_trials(trials_data["studies"])
        return summary
    else:
        return "No clinical trials found or error in fetching trials."

# Start the server when this script is run directly
if __name__ == "__main__":
    print("Starting Clinical Trials MCP server...")
    # This will automatically handle all the MCP protocol details
    mcp.run()
