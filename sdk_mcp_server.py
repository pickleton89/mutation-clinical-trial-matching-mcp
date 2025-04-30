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

# Register methods with the server to handle specific requests
async def handle_request(request):
    """Process incoming JSON-RPC requests"""
    method = request.get("method")
    params = request.get("params", {})
    req_id = request.get("id")
    
    print(f"Handling method: {method}", file=sys.stderr, flush=True)
    
    if method == "summarize_trials":
        mutation = params.get("mutation", "")
        result = await handle_summarize_trials(mutation)
        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    elif method == "get_manifest":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "name": "Clinical Trials MCP",
                "description": "Summarizes clinical trial data for mutations.",
                "methods": [
                    {
                        "name": "summarize_trials",
                        "description": "Summarizes clinical trials for a mutation.",
                        "params": {
                            "mutation": "string"
                        }
                    }
                ]
            }
        }
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

# Main function to run the server
async def main():
    print("MCP server starting with official SDK...", file=sys.stderr, flush=True)
    
    async with stdio_server() as streams:
        # Handle initialization request
        init_data = await streams[0].readline()
        if not init_data:
            print("No initialization data received", file=sys.stderr, flush=True)
            return
            
        try:
            init_request = json.loads(init_data)
            if init_request.get("method") == "initialize":
                init_response = {
                    "jsonrpc": "2.0",
                    "id": init_request.get("id"),
                    "result": {
                        "serverInfo": {
                            "name": "Clinical Trials MCP",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "methods": ["summarize_trials", "get_manifest"]
                        }
                    }
                }
                
                # Send initialization response
                init_response_json = json.dumps(init_response)
                print(f"Sending initialization response: {init_response_json}", file=sys.stderr, flush=True)
                streams[1].write(init_response_json + '\n')
                await streams[1].drain()
                
                # Process subsequent requests
                while True:
                    line = await streams[0].readline()
                    if not line:
                        # Sleep briefly to avoid busy-waiting
                        await asyncio.sleep(0.1)
                        continue
                        
                    try:
                        request = json.loads(line)
                        response = await handle_request(request)
                        
                        response_json = json.dumps(response)
                        print(f"Sending: {response_json}", file=sys.stderr, flush=True)
                        streams[1].write(response_json + '\n')
                        await streams[1].drain()
                    except json.JSONDecodeError:
                        print("Invalid JSON received", file=sys.stderr, flush=True)
                    except Exception as e:
                        print(f"Error processing request: {e}", file=sys.stderr, flush=True)
                        error_response = {
                            "jsonrpc": "2.0",
                            "id": request.get("id") if 'request' in locals() else None,
                            "error": {"code": -32000, "message": str(e)}
                        }
                        streams[1].write(json.dumps(error_response) + '\n')
                        await streams[1].drain()
            else:
                print(f"Unexpected first message: {init_request}", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Error during initialization: {e}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server shutting down", file=sys.stderr, flush=True)
