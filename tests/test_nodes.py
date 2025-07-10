"""
Tests for the Node implementation.
"""

import unittest
from unittest.mock import MagicMock, patch

from clinicaltrials.nodes import QueryTrialsNode, SummarizeTrialsNode
from utils.node import Flow


class TestQueryTrialsNode(unittest.TestCase):
    """Test the QueryTrialsNode class."""

    @patch('clinicaltrials.nodes.query_clinical_trials')
    def test_query_trials_node(self, mock_query):
        """Test the QueryTrialsNode workflow."""
        # Setup mock
        mock_response = {
            "studies": [
                {"protocolSection": {"identificationModule": {"briefTitle": "Test Trial"}}}
            ]
        }
        mock_query.return_value = mock_response

        # Create node and test
        node = QueryTrialsNode()
        shared = {"mutation": "BRAF V600E"}

        # Test prep
        prep_result = node.prep(shared)
        self.assertEqual(prep_result, "BRAF V600E")

        # Test exec
        exec_result = node.exec(prep_result)
        self.assertEqual(exec_result, mock_response)
        mock_query.assert_called_once_with(
            mutation="BRAF V600E",
            min_rank=1,
            max_rank=10,
            timeout=10
        )

        # Test post
        next_node = node.post(shared, prep_result, exec_result)
        self.assertEqual(next_node, "summarize")
        self.assertEqual(shared["trials_data"], mock_response)
        self.assertEqual(shared["studies"], mock_response["studies"])


class TestSummarizeTrialsNode(unittest.TestCase):
    """Test the SummarizeTrialsNode class."""

    @patch('clinicaltrials.nodes.format_trial_summary')
    def test_summarize_trials_node(self, mock_summarize):
        """Test the SummarizeTrialsNode workflow."""
        # Setup mock
        mock_summary = "# Clinical Trials Summary\n\nFound 1 clinical trial."
        mock_summarize.return_value = mock_summary

        # Test data
        studies = [
            {"protocolSection": {"identificationModule": {"briefTitle": "Test Trial"}}}
        ]

        # Create node and test
        node = SummarizeTrialsNode()
        shared = {"studies": studies}

        # Test prep
        prep_result = node.prep(shared)
        self.assertEqual(prep_result, studies)

        # Test exec
        exec_result = node.exec(prep_result)
        self.assertEqual(exec_result, mock_summary)
        mock_summarize.assert_called_once_with(studies)

        # Test post
        next_node = node.post(shared, prep_result, exec_result)
        self.assertIsNone(next_node)
        self.assertEqual(shared["summary"], mock_summary)


class TestFlow(unittest.TestCase):
    """Test the Flow class."""

    def test_flow_execution(self):
        """Test that a flow executes nodes in the correct order."""
        # Create mock nodes
        query_node = MagicMock()
        query_node.process.return_value = "summarize"

        summarize_node = MagicMock()
        summarize_node.process.return_value = None

        # Create flow
        flow = Flow(start=query_node)
        flow.add_node("summarize", summarize_node)

        # Run flow
        shared = {"mutation": "BRAF V600E"}
        flow.run(shared)

        # Verify node execution
        query_node.process.assert_called_once_with(shared)
        summarize_node.process.assert_called_once_with(shared)


if __name__ == '__main__':
    unittest.main()
