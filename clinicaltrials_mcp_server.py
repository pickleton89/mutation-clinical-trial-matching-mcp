#!/usr/bin/env python3
import sys
import json
import asyncio
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials


async def read_stdin():
    """Read a line from stdin asynchronously."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sys.stdin.readline)


async def process_request(request_str):
    """Process a single JSON-RPC request."""
    try:
        request = json.loads(request_str)
        method = request.get("method")
        req_id = request.get("id")

        print(f"Processing method: {method}", file=sys.stderr, flush=True)

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "serverInfo": {"name": "Clinical Trials MCP", "version": "1.0.0"},
                    "capabilities": {"methods": ["summarize_trials", "get_manifest"]},
                },
            }
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
                            "params": {"mutation": "string"},
                        }
                    ],
                },
            }
        elif method == "summarize_trials":
            mutation = request["params"].get("mutation", "")
            print(f"Querying for: {mutation}", file=sys.stderr, flush=True)

            trials_data = query_clinical_trials(mutation)
            if trials_data and "studies" in trials_data:
                summary = summarize_trials(trials_data["studies"])
            else:
                summary = "No trials found or error in fetching trials."

            return {"jsonrpc": "2.0", "id": req_id, "result": summary}
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
    except json.JSONDecodeError:
        print("Invalid JSON received", file=sys.stderr, flush=True)
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"},
        }
    except Exception as e:
        print(f"Error processing request: {e}", file=sys.stderr, flush=True)
        return {
            "jsonrpc": "2.0",
            "id": request.get("id") if "request" in locals() else None,
            "error": {"code": -32000, "message": str(e)},
        }


async def main():
    """Main entry point for the MCP server."""
    print("Clinical Trials MCP server starting...", file=sys.stderr, flush=True)

    # Process requests indefinitely
    while True:
        try:
            # Read the next line from stdin
            line = await read_stdin()
            if not line:
                # Don't exit when stdin is closed - Claude Desktop may close stdin after initialization
                # Instead, log it and wait for new connections
                print("Stdin appears closed. Waiting for new data...", file=sys.stderr, flush=True)
                # Sleep to avoid CPU spinning
                await asyncio.sleep(1)
                continue

            line = line.strip()
            if not line:
                # Skip empty lines
                continue

            print(f"Received: {line}", file=sys.stderr, flush=True)

            # Process the request
            response = await process_request(line)

            # Send the response
            response_json = json.dumps(response)
            print(f"Sending: {response_json}", file=sys.stderr, flush=True)
            print(response_json, flush=True)

            # For debugging: add a delay to ensure the response is sent
            await asyncio.sleep(0.01)

        except Exception as e:
            print(f"Unhandled exception: {e}", file=sys.stderr, flush=True)
            # Continue processing requests even if one fails
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server shutting down", file=sys.stderr, flush=True)
