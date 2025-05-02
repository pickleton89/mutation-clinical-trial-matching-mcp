import sys
from clinicaltrials.query import query_clinical_trials

from llm.summarize import summarize_trials

# Main workflow for clinical trial search and summarization.

def main():
    """
    Main function to accept a mutation, query clinicaltrials.gov, parse results, and summarize with Claude.
    """
    if len(sys.argv) < 2:
        print("Usage: python main.py <mutation>")
        sys.exit(1)
    mutation = " ".join(sys.argv[1:])
    print(f"Searching for clinical trials for mutation: {mutation}\n")
    raw_results = query_clinical_trials(mutation)
    if not raw_results or "studies" not in raw_results or not raw_results["studies"]:
        print("No trials found for the given mutation.")
        sys.exit(0)
    summary = summarize_trials(raw_results["studies"])
    print("\n===== LLM Summary =====\n")
    print(summary)

if __name__ == "__main__":
    main()