"""
Node implementations for clinical trials functionality.

This module provides PocketFlow Node implementations for querying and processing
clinical trial data from clinicaltrials.gov.
"""

from typing import Any

from clinicaltrials.query import query_clinical_trials
from llm.summarize import summarize_trials as format_trial_summary
from utils.node import Node


class QueryTrialsNode(Node[str, dict[str, Any]]):
    """
    Node for querying clinical trials based on a mutation.
    """

    def __init__(self, min_rank: int = 1, max_rank: int = 10, timeout: int = 10):
        """
        Initialize the QueryTrialsNode.

        Args:
            min_rank: The minimum rank of results to return (default: 1)
            max_rank: The maximum rank of results to return (default: 10)
            timeout: Timeout for the HTTP request in seconds (default: 10)
        """
        super().__init__()
        self.min_rank = min_rank
        self.max_rank = max_rank
        self.timeout = timeout

    def prep(self, shared: dict[str, Any]) -> str:
        """
        Extract the mutation from the shared context.

        Args:
            shared: The shared context dictionary

        Returns:
            The mutation string
        """
        if "mutation" not in shared:
            raise ValueError("Mutation not found in shared context")
        return shared["mutation"]

    def exec(self, mutation: str) -> dict[str, Any]:
        """
        Query clinicaltrials.gov for the mutation.

        Args:
            mutation: The mutation to search for

        Returns:
            The API response data
        """
        return query_clinical_trials(
            mutation=mutation, min_rank=self.min_rank, max_rank=self.max_rank, timeout=self.timeout
        )

    def post(self, shared: dict[str, Any], mutation: str, result: dict[str, Any]) -> str | None:
        """
        Store the query results in the shared context.

        Args:
            shared: The shared context dictionary
            mutation: The mutation that was searched for
            result: The API response data

        Returns:
            Next node ID or None
        """
        shared["trials_data"] = result
        shared["studies"] = result.get("studies", [])
        next_id = self.get_next_node_id()
        # For backward compatibility, return "summarize" if no next node is configured
        return next_id if next_id else "summarize"


class SummarizeTrialsNode(Node[list[dict[str, Any]], str]):
    """
    Node for summarizing clinical trial data.
    """

    def __init__(self):
        super().__init__()

    def prep(self, shared: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract the studies from the shared context.

        Args:
            shared: The shared context dictionary

        Returns:
            List of study data
        """
        if "studies" not in shared:
            raise ValueError("Studies not found in shared context")
        return shared["studies"]

    def exec(self, studies: list[dict[str, Any]]) -> str:
        """
        Generate a summary of the clinical trials.

        Args:
            studies: List of study data

        Returns:
            Formatted summary
        """
        return format_trial_summary(studies)

    def post(
        self, shared: dict[str, Any], studies: list[dict[str, Any]], summary: str
    ) -> str | None:
        """
        Store the summary in the shared context.

        Args:
            shared: The shared context dictionary
            studies: The studies that were summarized
            summary: The formatted summary

        Returns:
            Next node ID or None
        """
        shared["summary"] = summary
        return None  # End of flow
