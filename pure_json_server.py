#!/usr/bin/env python3
"""
Pure JSON MCP Server - sends and receives raw JSON without Content-Length headers
This matches what Claude Desktop expects for MCP communication
"""
import json
import sys
import os

def log(message):
    """Log a message to stderr"""
    print(f"LOG: {message}", file=sys.stderr, flush=True)

log(f"Starting Pure JSON MCP Server with PID: {os.getpid()}")

def main():
    """Main loop to process requests"""
    log("Starting main loop")
    
    # Process requests in a loop
    while True:
        try:
            # Read a line from stdin
            line = sys.stdin.readline()
            if not line:
                log("Reached EOF, exiting")
                break
                
            line = line.strip()
            if not line:
                continue
                
            log(f"Received line: {line}")
            
            # Try to parse the line as JSON
            try:
                request = json.loads(line)
                log(f"Parsed line as JSON: {request}")
            except json.JSONDecodeError:
                log(f"Failed to parse line as JSON: {line}")
                continue
            
            # Process the request
            method = request.get("method", "")
            req_id = request.get("id")
            
            log(f"Processing method: {method}")
            
            # Handle different methods
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "serverInfo": {
                            "name": "Pure JSON MCP Server",
                            "version": "1.0.0"
                        },
                        "capabilities": {
                            "methods": ["echo", "get_manifest"]
                        }
                    }
                }
            elif method == "get_manifest":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "name": "Pure JSON MCP Server",
                        "displayName": "Echo",
                        "description": "A simple echo server for testing",
                        "displayDescription": "Test server with echo functionality",
                        "publisher": "Jeff Kiefer",
                        "version": "1.0.0",
                        "icon": "🔊",
                        "category": "tools",
                        "shortcut": "E",
                        "methods": [
                            {
                                "name": "echo",
                                "displayName": "Echo",
                                "description": "Echo back a message",
                                "displayDescription": "Echo back the provided message",
                                "icon": "🔊",
                                "params": {
                                    "message": "string"
                                }
                            }
                        ]
                    }
                }
            elif method == "echo":
                params = request.get("params", {})
                message = params.get("message", "No message provided")
                log(f"Echo request with message: {message}")
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": f"Echo: {message}"
                }
            else:
                log(f"Unknown method: {method}")
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            
            # Send the response as raw JSON (no Content-Length header)
            response_json = json.dumps(response)
            log(f"Sending response: {response_json}")
            
            # Write the JSON response directly to stdout with a newline
            sys.stdout.write(response_json + "\n")
            sys.stdout.flush()
            log("Response sent")
            
        except Exception as e:
            log(f"Error processing request: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Server interrupted by keyboard")
    except Exception as e:
        log(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
