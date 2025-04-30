import sys
import json
from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

def main():
    for line in sys.stdin:
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
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id") if 'request' in locals() else None,
                "error": {"code": -32000, "message": str(e)}
            }
        print(json.dumps(response), flush=True)

if __name__ == "__main__":
    main()
