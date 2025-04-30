import sys
import json
import asyncio
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

def handle_request(request):
    method = request.get("method")
    req_id = request.get("id")
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
            "error": {"code": -32601, "message": "Method not found"}
        }
    return response

async def main():
    print("MCP server (async) starting...", file=sys.stderr, flush=True)
    loop = asyncio.get_event_loop()
    # Set up asyncio reader from stdin
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    while True:
        try:
            line = await reader.readline()
            if not line:
                await asyncio.sleep(1)
                continue
            line = line.decode().strip()
            print(f"Received line: {line}", file=sys.stderr, flush=True)
            try:
                request = json.loads(line)
                response = handle_request(request)
            except Exception as e:
                print(f"Exception: {e}", file=sys.stderr, flush=True)
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {"code": -32000, "message": str(e)}
                }
            print(json.dumps(response), flush=True)
        except Exception as main_e:
            print(f"Main loop exception: {main_e}", file=sys.stderr, flush=True)
            await asyncio.sleep(1)
    print("MCP server (async) exiting...", file=sys.stderr, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
