import sys
import json
import asyncio
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials


def handle_request(request):
    method = request.get("method")
    req_id = request.get("id")
    print(f"Handling method: {method} with id: {req_id}", file=sys.stderr, flush=True)

    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "serverInfo": {"name": "Clinical Trials MCP", "version": "1.0.0"},
                "capabilities": {"methods": ["summarize_trials", "get_manifest"]},
            },
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
                        "params": {"mutation": "string"},
                    }
                ],
            },
        }
    elif method == "summarize_trials":
        try:
            mutation = request["params"].get("mutation", "")
            print(f"Querying for mutation: {mutation}", file=sys.stderr, flush=True)
            trials_data = query_clinical_trials(mutation)
            if trials_data and "studies" in trials_data:
                summary = summarize_trials(trials_data["studies"])
            else:
                summary = "No trials found or error in fetching trials."
            response = {"jsonrpc": "2.0", "id": req_id, "result": summary}
        except Exception as e:
            print(f"Error in summarize_trials: {e}", file=sys.stderr, flush=True)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }
    else:
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return response


async def main():
    print("MCP server (async) starting...", file=sys.stderr, flush=True)

    # Set up asyncio reader from stdin
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    # Set up asyncio writer to stdout
    writer_transport, writer_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

    print("MCP server ready to process requests", file=sys.stderr, flush=True)

    while True:
        try:
            line = await reader.readline()
            if not line:
                print("Empty line received, waiting...", file=sys.stderr, flush=True)
                await asyncio.sleep(0.1)
                continue

            line_str = line.decode().strip()
            print(f"Received line: {line_str}", file=sys.stderr, flush=True)

            try:
                request = json.loads(line_str)
                response = handle_request(request)

                # Send the response
                response_json = json.dumps(response)
                print(f"Sending response: {response_json}", file=sys.stderr, flush=True)
                writer.write((response_json + "\n").encode())
                await writer.drain()

            except json.JSONDecodeError as je:
                print(f"JSON decode error: {je}", file=sys.stderr, flush=True)
                continue
            except Exception as e:
                print(f"Exception processing request: {e}", file=sys.stderr, flush=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if "request" in locals() else None,
                    "error": {"code": -32000, "message": str(e)},
                }
                writer.write((json.dumps(error_response) + "\n").encode())
                await writer.drain()

        except asyncio.CancelledError:
            print("Server task cancelled", file=sys.stderr, flush=True)
            break
        except Exception as main_e:
            print(f"Main loop exception: {main_e}", file=sys.stderr, flush=True)
            await asyncio.sleep(0.1)

    print("MCP server exiting...", file=sys.stderr, flush=True)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Server interrupted by keyboard", file=sys.stderr, flush=True)
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        print("Server shutdown complete", file=sys.stderr, flush=True)
