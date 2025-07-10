import sys

from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials

# Main workflow for clinical trial search and summarization.

def main():
    """
    Main function to accept a mutation, query clinicaltrials.gov, parse results, and summarize with Claude.
    """
    if len(sys.argv) < 2:
        sys.exit(1)
    mutation = " ".join(sys.argv[1:])
    raw_results = query_clinical_trials(mutation)
    if not raw_results or "studies" not in raw_results or not raw_results["studies"]:
        sys.exit(0)
    summarize_trials(raw_results["studies"])

if __name__ == "__main__":
    main()
