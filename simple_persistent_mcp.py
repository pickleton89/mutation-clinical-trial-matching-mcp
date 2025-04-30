#!/usr/bin/env python3
"""
Simple persistent MCP server for clinical trials data.
This implementation uses a simplified approach to ensure the server stays running.
"""
import sys
import json
import time
import threading
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Global flag to keep the server running
running = True

def handle_summarize_trials(mutation):
    """Implementation of the summarize_trials method."""
    print(f"Querying for: {mutation}", file=sys.stderr, flush=True)
    
    trials_data = query_clinical_trials(mutation)
    if trials_data and "studies" in trials_data:
        summary = summarize_trials(trials_data["studies"])
    else:
        summary = "No trials found or error in fetching trials."
        
    return summary

def process_request(request):
    """Process a single JSON-RPC request."""
    try:
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")
        
        print(f"Processing method: {method}", file=sys.stderr, flush=True)
        
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
            summary = handle_summarize_trials(mutation)
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
        
        return response
    except Exception as e:
        print(f"Error processing request: {e}", file=sys.stderr, flush=True)
        return {
            "jsonrpc": "2.0",
            "id": request.get("id") if hasattr(request, "get") else None,
            "error": {"code": -32000, "message": str(e)}
        }

def reader_thread():
    """Thread to read from stdin and process requests."""
    global running
    
    print("MCP server starting (reader thread)...", file=sys.stderr, flush=True)
    
    try:
        while running:
            line = sys.stdin.readline()
            if not line:
                # No input, sleep a bit to avoid busy-waiting
                time.sleep(0.1)
                continue
                
            line = line.strip()
            if not line:
                time.sleep(0.1)
                continue
                
            print(f"Received: {line}", file=sys.stderr, flush=True)
            
            try:
                request = json.loads(line)
                response = process_request(request)
                
                response_json = json.dumps(response)
                print(f"Sending: {response_json}", file=sys.stderr, flush=True)
                
                # Write response to stdout
                print(response_json, flush=True)
                
            except json.JSONDecodeError:
                print("Invalid JSON received", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"Error in reader thread: {e}", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal error in reader thread: {e}", file=sys.stderr, flush=True)
    finally:
        print("Reader thread exiting", file=sys.stderr, flush=True)

def heartbeat_thread():
    """Thread to keep the server alive by periodically writing to stderr."""
    global running
    
    print("Heartbeat thread starting...", file=sys.stderr, flush=True)
    
    try:
        # Send a heartbeat every 5 seconds to keep the connection alive
        counter = 0
        while running:
            time.sleep(5)
            counter += 1
            # Write a heartbeat message to stderr every 5 seconds
            print(f"Heartbeat ({counter}): Server is still running", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Error in heartbeat thread: {e}", file=sys.stderr, flush=True)
    finally:
        print("Heartbeat thread exiting", file=sys.stderr, flush=True)

def main():
    """Main entry point - starts the reader and heartbeat threads."""
    global running
    
    try:
        # Start the reader thread
        reader = threading.Thread(target=reader_thread)
        reader.daemon = True
        reader.start()
        
        # Start the heartbeat thread
        heartbeat = threading.Thread(target=heartbeat_thread)
        heartbeat.daemon = True
        heartbeat.start()
        
        # Wait for the reader thread to finish
        reader.join()
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        running = False
        print("Server shutting down", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
