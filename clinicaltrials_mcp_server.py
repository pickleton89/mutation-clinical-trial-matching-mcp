import sys
import json
import asyncio
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

async def read_stdin():
    return (await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)).strip()

async def server_loop():
    print("MCP server starting...", file=sys.stderr, flush=True)
    
    while True:
        try:
            line = await read_stdin()
            if not line:
                await asyncio.sleep(0.1)
                continue
                
            print(f"Received: {line}", file=sys.stderr, flush=True)
            
            try:
                request = json.loads(line)
                method = request.get("method")
                req_id = request.get("id")
                
                print(f"Processing method: {method}", file=sys.stderr, flush=True)
                
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
                    print(f"Querying for: {mutation}", file=sys.stderr, flush=True)
                    
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
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }
                    
                response_json = json.dumps(response)
                print(f"Sending: {response_json}", file=sys.stderr, flush=True)
                print(response_json, flush=True)
                
            except json.JSONDecodeError:
                print("Invalid JSON received", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"Error processing request: {e}", file=sys.stderr, flush=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {"code": -32000, "message": str(e)}
                }
                print(json.dumps(error_response), flush=True)
                
        except Exception as outer_e:
            print(f"Outer exception: {outer_e}", file=sys.stderr, flush=True)
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    try:
        asyncio.run(server_loop())
    except KeyboardInterrupt:
        print("Server interrupted", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"Fatal server error: {e}", file=sys.stderr, flush=True)
    finally:
        print("Server shutting down", file=sys.stderr, flush=True)
