#!/usr/bin/env python3
"""
Basic MCP server implementation that follows a known working pattern.
This server only implements the echo method for testing.
"""
import json
import sys
import os

# Set up logging
def log(message):
    """Log a message to stderr"""
    print(f"LOG: {message}", file=sys.stderr, flush=True)

log(f"Starting basic MCP server with PID: {os.getpid()}")

def read_request():
    """Read a JSON-RPC request from stdin"""
    headers = {}
    
    # Read headers until empty line
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            log("EOF reached while reading headers")
            return None
            
        line_str = line.decode('utf-8').strip()
        log(f"Header line: {repr(line_str)}")
        
        if not line_str:  # Empty line marks end of headers
            break
            
        parts = line_str.split(':', 1)
        if len(parts) == 2:
            headers[parts[0].lower()] = parts[1].strip()
    
    # Get content length
    if 'content-length' not in headers:
        log("No Content-Length header found")
        return None
        
    content_length = int(headers['content-length'])
    log(f"Reading message with Content-Length: {content_length}")
    
    # Read the JSON content as bytes then decode
    content_bytes = sys.stdin.buffer.read(content_length)
    if not content_bytes:
        log("No content bytes read")
        return None
        
    content = content_bytes.decode('utf-8')
    log(f"Received content: {content}")
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        log(f"Failed to parse JSON: {e}")
        return None

def send_response(response):
    """Send a JSON-RPC response to stdout"""
    content = json.dumps(response)
    content_bytes = content.encode('utf-8')
    content_length = len(content_bytes)
    
    log(f"Sending response: {content}")
    
    # Write headers and content as bytes
    header = f"Content-Length: {content_length}\r\n\r\n"
    sys.stdout.buffer.write(header.encode('utf-8'))
    sys.stdout.buffer.write(content_bytes)
    sys.stdout.buffer.flush()
    log("Response sent successfully")

def main():
    """Main loop to handle requests"""
    log("Starting main loop")
    
    while True:
        # Read a request
        request = read_request()
        if not request:
            log("Failed to read request, continuing...")
            continue
            
        # Get request details
        method = request.get('method', '')
        params = request.get('params', {})
        req_id = request.get('id')
        
        log(f"Processing method: {method}")
        
        # Handle the request
        if method == 'initialize':
            response = {
                'jsonrpc': '2.0',
                'id': req_id,
                'result': {
                    'serverInfo': {
                        'name': 'Basic MCP Server',
                        'version': '1.0.0'
                    },
                    'capabilities': {
                        'methods': ['echo', 'get_manifest']
                    }
                }
            }
        elif method == 'get_manifest':
            response = {
                'jsonrpc': '2.0',
                'id': req_id,
                'result': {
                    'name': 'Basic MCP Server',
                    'displayName': 'Basic MCP',
                    'description': 'A basic MCP server for testing',
                    'displayDescription': 'Test MCP server with echo functionality',
                    'publisher': 'Jeff Kiefer',
                    'version': '1.0.0',
                    'icon': '🧪',
                    'category': 'tools',
                    'shortcut': 'B',
                    'methods': [
                        {
                            'name': 'echo',
                            'displayName': 'Echo',
                            'description': 'Echo back a message',
                            'displayDescription': 'Echo back the provided message',
                            'icon': '🔊',
                            'params': {
                                'message': 'string'
                            }
                        }
                    ]
                }
            }
        elif method == 'echo':
            message = params.get('message', 'No message provided')
            log(f"Echo request with message: {message}")
            response = {
                'jsonrpc': '2.0',
                'id': req_id,
                'result': f"Echo: {message}"
            }
        else:
            log(f"Unknown method: {method}")
            response = {
                'jsonrpc': '2.0',
                'id': req_id,
                'error': {
                    'code': -32601,
                    'message': f"Method not found: {method}"
                }
            }
            
        # Send the response
        send_response(response)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("Server interrupted by keyboard")
    except Exception as e:
        log(f"Unhandled exception: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
