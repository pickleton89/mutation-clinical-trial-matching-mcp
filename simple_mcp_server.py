#!/usr/bin/env python3
"""
Simple MCP server for clinical trials data.
This implementation focuses on reliability and simplicity.
"""
import sys
import json
import asyncio
import signal
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Keep track of whether the server should continue running
running = True

async def read_line():
    """Read a line from stdin asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sys.stdin.buffer.readline)

async def main():
    """Main server loop."""
    print("Simple MCP server starting...", file=sys.stderr, flush=True)
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)
    
    # Keep the server running indefinitely
    global running
    while running:
        try:
            # Read the next line from stdin
            line_bytes = await read_line()
            if not line_bytes:
                print("Stdin closed, waiting...", file=sys.stderr, flush=True)
                await asyncio.sleep(0.5)
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
                req_id = request.get("id")
                
                print(f"Processing method: {method}", file=sys.stderr, flush=True)
                
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
                    mutation = request["params"].get("mutation", "")
                    print(f"Querying for: {mutation}", file=sys.stderr, flush=True)
                    
                    trials_data = query_clinical_trials(mutation)
                    if trials_data and "studies" in trials_data:
                        summary = summarize_trials(trials_data["studies"])
                    else:
                        summary = "No trials found or error in fetching trials."
                        
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
                print(response_json, flush=True)
                sys.stdout.flush()  # Ensure the response is sent immediately
                
            except json.JSONDecodeError:
                print("Invalid JSON received", file=sys.stderr, flush=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                print(json.dumps(error_response), flush=True)
                sys.stdout.flush()
                
            except Exception as e:
                print(f"Error processing request: {e}", file=sys.stderr, flush=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {"code": -32000, "message": str(e)}
                }
                print(json.dumps(error_response), flush=True)
                sys.stdout.flush()
                
        except Exception as e:
            print(f"Unhandled exception: {e}", file=sys.stderr, flush=True)
            await asyncio.sleep(0.1)
            
        # Add a small delay to avoid busy-waiting
        await asyncio.sleep(0.01)
    
    print("Server shutting down gracefully", file=sys.stderr, flush=True)

def handle_signal():
    """Handle termination signals."""
    print("Received termination signal", file=sys.stderr, flush=True)
    global running
    running = False

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server exiting", file=sys.stderr, flush=True)
