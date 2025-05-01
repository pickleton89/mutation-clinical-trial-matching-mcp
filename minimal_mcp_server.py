#!/usr/bin/env python3
"""
Minimal MCP server implementation that follows the MCP specification exactly.
This server only implements the echo method for testing.
"""
import json
import sys
import os

# Set up logging
def log(message):
    """Log a message to stderr"""
    print(message, file=sys.stderr, flush=True)

log(f"Starting minimal MCP server with PID: {os.getpid()}")

def read_message():
    """Read a JSON-RPC message with Content-Length header from stdin"""
    # Read headers
    headers = {}
    while True:
        line = sys.stdin.buffer.readline().decode('utf-8')
        if not line or line == '\r\n' or line == '\n':
            break
        if ':' in line:
            key, value = line.strip().split(':', 1)
            headers[key.strip().lower()] = value.strip()
    
    # Get content length
    if 'content-length' not in headers:
        log("No Content-Length header found")
        return None
    
    content_length = int(headers['content-length'])
    log(f"Reading message with Content-Length: {content_length}")
    
    # Read the JSON content
    content = sys.stdin.buffer.read(content_length).decode('utf-8')
    log(f"Received message: {content}")
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        log("Failed to parse JSON message")
        return None

def write_message(obj):
    """Write a JSON-RPC message with Content-Length header to stdout"""
    content = json.dumps(obj)
    header = f"Content-Length: {len(content)}\r\n\r\n"
    
    log(f"Sending message: {content}")
    
    # Write header and content
    sys.stdout.buffer.write(header.encode('utf-8'))
    sys.stdout.buffer.write(content.encode('utf-8'))
    sys.stdout.buffer.flush()

def handle_initialize(request):
    """Handle the initialize request"""
    req_id = request.get("id")
    log("Handling initialize request")
    
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "serverInfo": {
                "name": "Minimal MCP Server",
                "version": "1.0.0"
            },
            "capabilities": {
                "methods": ["echo", "get_manifest"]
            }
        }
    }

def handle_get_manifest(request):
    """Handle the get_manifest request"""
    req_id = request.get("id")
    log("Handling get_manifest request")
    
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {
            "name": "Minimal MCP Server",
            "displayName": "Minimal MCP",
            "description": "A minimal MCP server for testing",
            "displayDescription": "Test MCP server with echo functionality",
            "publisher": "Jeff Kiefer",
            "version": "1.0.0",
            "methods": [
                {
                    "name": "echo",
                    "displayName": "Echo",
                    "description": "Echo back a message",
                    "displayDescription": "Echo back the provided message",
                    "params": {
                        "message": "string"
                    }
                }
            ]
        }
    }

def handle_echo(request):
    """Handle the echo request"""
    req_id = request.get("id")
    params = request.get("params", {})
    message = params.get("message", "No message provided")
    
    log(f"Handling echo request with message: {message}")
    
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": f"Echo: {message}"
    }

def main():
    """Main loop to handle requests"""
    log("Starting main loop")
    
    while True:
        # Read a message
        request = read_message()
        if not request:
            log("Failed to read message, waiting for next message")
            continue
        
        # Process the request
        method = request.get("method")
        log(f"Processing method: {method}")
        
        if method == "initialize":
            response = handle_initialize(request)
        elif method == "get_manifest":
            response = handle_get_manifest(request)
        elif method == "echo":
            response = handle_echo(request)
        else:
            req_id = request.get("id")
            log(f"Unknown method: {method}")
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        # Send the response
        write_message(response)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Server interrupted by keyboard")
    except Exception as e:
        log(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
