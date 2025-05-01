#!/usr/bin/env python3
import sys
import json
import asyncio
import os
import time
import threading
import traceback
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Debug mode - set to True for more verbose logging
DEBUG = True

def debug_log(message):
    """Log debug messages to stderr if DEBUG is enabled"""
    if DEBUG:
        print(f"DEBUG: {message}", file=sys.stderr, flush=True)


async def read_stdin():
    """Read a line from stdin asynchronously."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, sys.stdin.readline)


# ---------- MCP stdio framing helpers ----------
def _read_message_sync():
    """Blocking helper that reads a single framed JSON-RPC message from stdin."""
    headers = b""
    while True:
        # Check if stdin has data available
        import select
        readable, _, _ = select.select([sys.stdin], [], [], 0.1)
        if not readable:
            debug_log("No data available on stdin")
            # Return None to indicate no message available yet
            return "NO_DATA_YET"
        
        debug_log("Reading line from stdin buffer")
        line = sys.stdin.buffer.readline()
        if not line:
            # EOF or pipe closed
            return None
        headers += line
        if line in (b"\r\n", b"\n"):
            break  # End of headers

    try:
        header_text = headers.decode()
    except UnicodeDecodeError:
        print("Failed to decode header bytes", file=sys.stderr, flush=True)
        return None

    # Debug: show raw header block
    debug_log(f"Raw headers: {repr(header_text)}")

    # Extract Content-Length
    length = 0
    for header_line in header_text.splitlines():
        if header_line.lower().startswith("content-length:"):
            try:
                length = int(header_line.split(":", 1)[1].strip())
            except ValueError:
                length = 0
            break

    if length <= 0:
        debug_log("No valid Content-Length found, trying fallback to raw message")
        # Fallback: try to parse the headers as a raw JSON message
        return header_text

    debug_log(f"Reading {length} bytes from stdin")
    body = sys.stdin.buffer.read(length)
    if not body:
        debug_log("Expected body bytes not available")
        return None

    try:
        decoded = body.decode()
        debug_log(f"Decoded body: {decoded[:100]}...")  # Log first 100 chars
        return decoded
    except UnicodeDecodeError:
        debug_log("Failed to decode body bytes")
        return None


async def read_message():
    """Asynchronously read a framed JSON-RPC message using the blocking helper."""
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _read_message_sync)
        
        if result == "NO_DATA_YET":
            return None
            
        return result
    except Exception as e:
        debug_log(f"Error in read_message: {e}")
        traceback.print_exc(file=sys.stderr)
        # Return None on error
        return None


def send_message(obj):
    """Write a JSON-RPC response with Content-Length framing to stdout."""
    raw = json.dumps(obj)
    msg = f"Content-Length: {len(raw)}\r\n\r\n{raw}"
    sys.stdout.write(msg)
    sys.stdout.flush()


async def process_request(request_str):
    """Process a single JSON-RPC request."""
    debug_log(f"Processing request: {request_str[:100]}...")  # Log first 100 chars
    try:
        request = json.loads(request_str)
        method = request.get("method")
        req_id = request.get("id")

        print(f"Processing method: {method}", file=sys.stderr, flush=True)

        if method == "initialize":
            # This is the critical first message from Claude Desktop
            debug_log("Handling initialize request")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "serverInfo": {"name": "Clinical Trials MCP", "version": "1.0.0"},
                    "capabilities": {"methods": ["summarize_trials", "get_manifest"]},
                },
            }
        elif method == "notifications/cancelled":
            # Handle cancellation notification
            debug_log("Received cancellation notification")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": None
            }
        elif method == "get_manifest":
            debug_log("Handling get_manifest request")
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
            debug_log("Handling summarize_trials request")
            mutation = request["params"].get("mutation", "")
            print(f"Querying for: {mutation}", file=sys.stderr, flush=True)

            trials_data = query_clinical_trials(mutation)
            if trials_data and "studies" in trials_data:
                summary = summarize_trials(trials_data["studies"])
            else:
                summary = "No trials found or error in fetching trials."

            return {"jsonrpc": "2.0", "id": req_id, "result": summary}
        else:
            debug_log(f"Unknown method: {method}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
    except json.JSONDecodeError:
        print("Invalid JSON received", file=sys.stderr, flush=True)
        debug_log(f"Invalid JSON: {request_str}")
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32700, "message": "Parse error"},
        }
    except Exception as e:
        print(f"Error processing request: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
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
    print(f"PID: {os.getpid()}", file=sys.stderr, flush=True)
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
            
            # Check if we got a message
            if line is None:
                await asyncio.sleep(0.1)
                continue
                
            if not line:
                # Don't exit when stdin is closed
                print("Stdin appears closed. Waiting for new data...", file=sys.stderr, flush=True)
                # Sleep to avoid CPU spinning
                await asyncio.sleep(2)
                continue

            print(f"Received: {line}", file=sys.stderr, flush=True)

            # Try to parse as JSON directly (fallback for non-framed messages)
            if not line.strip().startswith("{"):
                debug_log("Received non-JSON message, skipping")
                await asyncio.sleep(0.1)
                continue

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
            debug_log("Exception in main loop")
            traceback.print_exc(file=sys.stderr)
            # Continue processing requests even if one fails
            await asyncio.sleep(1)


def run_forever():
    """Run a completely separate thread that just keeps the process alive."""
    
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
        debug_log("Starting main asyncio loop")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error in main loop: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        print("Main loop error, but keep-alive thread continues running", file=sys.stderr, flush=True)
        import time
        while True:
            time.sleep(60)  # Sleep forever, let the daemon thread do the work
    finally:
        print("Main loop is shutting down, but process will continue running", file=sys.stderr, flush=True)
