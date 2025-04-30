#!/usr/bin/env python3
"""
Clinical Trials MCP Server using the official MCP Python SDK.
This implementation follows best practices for MCP servers.
"""
import sys
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server

from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Create the server
app = Server("clinical-trials-mcp")

# Handle methods explicitly in the request handler
async def handle_summarize_trials(mutation: str) -> str:
    """Summarizes clinical trials for a mutation."""
    print(f"Querying for: {mutation}", file=sys.stderr, flush=True)
    
    trials_data = query_clinical_trials(mutation)
    if trials_data and "studies" in trials_data:
        summary = summarize_trials(trials_data["studies"])
    else:
        summary = "No trials found or error in fetching trials."
        
    return summary

# Main function to run the server
async def main():
    print("MCP server starting with official SDK...", file=sys.stderr, flush=True)
    async with stdio_server() as streams:
        # Run server with stdio transport
        await app.run(
            streams[0],  # stdin
            streams[1],  # stdout
            app.create_initialization_options()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server shutting down", file=sys.stderr, flush=True)
