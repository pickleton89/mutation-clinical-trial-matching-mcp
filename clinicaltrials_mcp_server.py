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


# ---------- MCP stdio framing helpers ----------
async def read_message():
    """Read a single JSON-RPC message framed with Content-Length headers."""
    loop = asyncio.get_running_loop()
    headers = b""  # Accumulate header bytes
    while True:
        line = await loop.run_in_executor(None, sys.stdin.buffer.readline)
        if not line:
            return None  # EOF
        headers += line
        # Header section ends with a blank line
        if line in (b"\r\n", b"\n"):
            break

    # Parse Content-Length
    length = 0
    for header_line in headers.decode().splitlines():
        if header_line.lower().startswith("content-length:"):
            try:
                length = int(header_line.split(":")[1].strip())
            except ValueError:
                length = 0
            break

    if length <= 0:
        return None  # Malformed header

    # Read exactly `length` bytes for the JSON body
    body = await loop.run_in_executor(None, sys.stdin.buffer.read, length)
    if not body:
        return None
    return body.decode()


def send_message(obj):
    """Write a JSON-RPC response with Content-Length framing to stdout."""
    raw = json.dumps(obj)
    msg = f"Content-Length: {len(raw)}\r\n\r\n{raw}"
    sys.stdout.write(msg)
    sys.stdout.flush()


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


async def keep_alive():
    """Keep the server alive even if there's no input."""
    while True:
        print("Server still alive...", file=sys.stderr, flush=True)
        await asyncio.sleep(30)  # Log every 30 seconds


async def main():
    """Main entry point for the MCP server."""
    print("Clinical Trials MCP server starting...", file=sys.stderr, flush=True)
    
    # Start the keep-alive task to ensure the server doesn't exit
    # We don't need to track this task, we just need it to run
    asyncio.create_task(keep_alive())
    # Uncomment this if you want to explicitly track the task
    # keep_alive_task = asyncio.create_task(keep_alive())
    
    # Process requests indefinitely
    while True:
        try:
            # Wait for the next framed JSON-RPC message with a timeout
            read_task = asyncio.create_task(read_message())
            try:
                line = await asyncio.wait_for(read_task, timeout=5)  # 5 second timeout
            except asyncio.TimeoutError:
                # Timeout reached, continue the loop
                await asyncio.sleep(0.1)
                continue
                
            if not line:
                # Don't exit when stdin is closed
                print("Stdin appears closed. Waiting for new data...", file=sys.stderr, flush=True)
                # Sleep to avoid CPU spinning
                await asyncio.sleep(2)
                continue

            print(f"Received: {line}", file=sys.stderr, flush=True)

            # Process the request
            response = await process_request(line)

            # Send the response
            response_json = json.dumps(response)
            print(f"Sending: {response_json}", file=sys.stderr, flush=True)
            send_message(response)

            # For debugging: add a delay to ensure the response is sent
            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"Unhandled exception in main loop: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # Continue processing requests even if one fails
            await asyncio.sleep(1)


def run_forever():
    """Run a completely separate thread that just keeps the process alive."""
    import threading
    import time
    
    def keep_process_alive():
        while True:
            print("Process keep-alive thread running...", file=sys.stderr, flush=True)
            time.sleep(10)  # Sleep for 10 seconds
    
    # Start a daemon thread that will keep running
    thread = threading.Thread(target=keep_process_alive, daemon=True)
    thread.start()

if __name__ == "__main__":
    # First, start a separate thread that will keep the process alive no matter what
    run_forever()
    
    # Then run the normal server loop
    try:
        print("Starting MCP server - using separate thread to ensure continuous operation", file=sys.stderr, flush=True)
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error in main loop: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        # Even if the main loop crashes, the process will stay alive
        # Just sleep forever to keep the process running
        print("Main loop error, but keep-alive thread continues running", file=sys.stderr, flush=True)
        import time
        while True:
            time.sleep(60)  # Sleep forever, let the daemon thread do the work
    finally:
        print("Main loop is shutting down, but process will continue running", file=sys.stderr, flush=True)
