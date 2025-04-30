#!/usr/bin/env python3
"""
Pure MCP Server for clinical trials data.
This implementation uses no external SDKs, just standard Python libraries.
"""
import sys
import json
import asyncio
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

async def read_stdin():
    """Read a line from stdin asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sys.stdin.buffer.readline)

async def handle_summarize_trials(mutation):
    """Implementation of the summarize_trials method."""
    print(f"Querying for: {mutation}", file=sys.stderr, flush=True)
    
    trials_data = query_clinical_trials(mutation)
    if trials_data and "studies" in trials_data:
        summary = summarize_trials(trials_data["studies"])
    else:
        summary = "No trials found or error in fetching trials."
        
    return summary

async def main():
    """Main server loop."""
    print("Pure MCP server starting...", file=sys.stderr, flush=True)
    
    # Process requests indefinitely
    while True:
        try:
            # Read the next line from stdin
            line_bytes = await read_stdin()
            if not line_bytes:
                # If stdin is closed, wait a bit and try again
                await asyncio.sleep(0.1)
                continue
                
            # Decode and process the line
            line = line_bytes.decode('utf-8').strip()
            if not line:
                await asyncio.sleep(0.1)
                continue
                
            print(f"Received: {line}", file=sys.stderr, flush=True)
            
            # Parse the request
            try:
                request = json.loads(line)
                method = request.get("method")
                params = request.get("params", {})
                req_id = request.get("id")
                
                # Handle different methods
                if method == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
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
                elif method == "get_manifest":
                    response = {
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
                elif method == "summarize_trials":
                    mutation = params.get("mutation", "")
                    summary = await handle_summarize_trials(mutation)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": summary
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }
                
                # Send the response
                response_json = json.dumps(response)
                print(f"Sending: {response_json}", file=sys.stderr, flush=True)
                sys.stdout.buffer.write((response_json + '\n').encode('utf-8'))
                sys.stdout.buffer.flush()
                
            except json.JSONDecodeError:
                print("Invalid JSON received", file=sys.stderr, flush=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                sys.stdout.buffer.write((json.dumps(error_response) + '\n').encode('utf-8'))
                sys.stdout.buffer.flush()
                
            except Exception as e:
                print(f"Error processing request: {e}", file=sys.stderr, flush=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {"code": -32000, "message": str(e)}
                }
                sys.stdout.buffer.write((json.dumps(error_response) + '\n').encode('utf-8'))
                sys.stdout.buffer.flush()
                
        except Exception as e:
            print(f"Unhandled exception: {e}", file=sys.stderr, flush=True)
            # Don't exit, just continue the loop
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server exiting", file=sys.stderr, flush=True)
