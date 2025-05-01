#!/usr/bin/env python3
import json
import subprocess
import sys

def send_jsonrpc_request(method, params=None, request_id=1):
    """Send a JSON-RPC request to the MCP server via stdin and get the response."""
    if params is None:
        params = {}
    
    # Create the JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id
    }
    
    # Convert to JSON
    request_json = json.dumps(request)
    
    # Add Content-Length header
    message = f"Content-Length: {len(request_json)}\r\n\r\n{request_json}"
    
    # Start the server process
    server_path = "/Users/jeffkiefer/Documents/projects/mutation_clinical_trial_matching_mcp/clinicaltrials_mcp_server.py"
    process = subprocess.Popen(
        ["python3", server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # We need binary mode for exact byte counting
        cwd="/Users/jeffkiefer/Documents/projects/mutation_clinical_trial_matching_mcp"
    )
    
    # Send the request
    process.stdin.write(message.encode())
    process.stdin.flush()
    
    # Read the response headers
    headers = b""
    while True:
        line = process.stdout.readline()
        headers += line
        if line in (b"\r\n", b"\n"):
            break
    
    # Parse Content-Length
    content_length = 0
    for header in headers.decode().splitlines():
        if header.lower().startswith("content-length:"):
            content_length = int(header.split(":", 1)[1].strip())
            break
    
    # Read the response body
    response_body = process.stdout.read(content_length)
    
    # Get stderr output
    stderr_output = process.stderr.read()
    
    # Terminate the process
    process.terminate()
    
    return {
        "response": json.loads(response_body.decode()) if response_body else None,
        "stderr": stderr_output.decode()
    }

if __name__ == "__main__":
    # Test initialize request
    print("Sending initialize request...")
    result = send_jsonrpc_request(
        "initialize", 
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.1.0"}
        }
    )
    
    print("\n=== Response ===")
    print(json.dumps(result["response"], indent=2))
    
    print("\n=== Server Logs ===")
    print(result["stderr"])
