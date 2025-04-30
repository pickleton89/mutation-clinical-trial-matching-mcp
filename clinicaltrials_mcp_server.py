import sys
import json
import time
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

def main():
    print("MCP server starting...", file=sys.stderr, flush=True)
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                print("stdin closed or empty, sleeping for 1 second...", file=sys.stderr, flush=True)
                time.sleep(1)
                continue
            print(f"Received line: {line.strip()}", file=sys.stderr, flush=True)
            try:
                request = json.loads(line)
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
    print("MCP server exiting...", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
