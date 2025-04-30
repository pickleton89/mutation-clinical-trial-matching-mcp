import os
import socket
import json

# Claude Desktop MCP socket path (default, override with CLAUDE_MCP_SOCKET env var if needed)
MCP_SOCKET_PATH = os.environ.get("CLAUDE_MCP_SOCKET", "/tmp/claude-mcp.sock")

def call_llm(prompt: str) -> str:
    """
    Send a prompt to Claude Desktop via MCP socket and return the response.
    """
    # Construct MCP message (Claude Desktop expects JSON with a 'prompt' field)
    mcp_request = json.dumps({"prompt": prompt})
    response = ""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(MCP_SOCKET_PATH)
            client.sendall(mcp_request.encode("utf-8"))
            chunks = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
            response_data = b"".join(chunks).decode("utf-8")
            # Claude Desktop may respond with JSON; parse if so
            try:
                resp_json = json.loads(response_data)
                response = resp_json.get("completion", response_data)
            except Exception:
                response = response_data
    except Exception as e:
        response = f"[MCP ERROR: {e}]"
    return response

if __name__ == "__main__":
    prompt = "What is the meaning of life?"
    print(call_llm(prompt))
