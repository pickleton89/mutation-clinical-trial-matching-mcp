"""
Tests for the Node implementation.
"""

import unittest
from unittest.mock import MagicMock, patch

from clinicaltrials.unified_nodes import QueryTrialsNode, SummarizeTrialsNode
from utils.unified_node import UnifiedFlow as Flow


class TestQueryTrialsNode(unittest.TestCase):
    """Test the QueryTrialsNode class."""

    @patch("clinicaltrials.service.ClinicalTrialsService.query_trials")
    def test_query_trials_node(self, mock_query):
        """Test the QueryTrialsNode workflow."""
        # Setup mock
        mock_response = {
            "studies": [{"protocolSection": {"identificationModule": {"briefTitle": "Test Trial"}}}]
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
            mutation="BRAF V600E", min_rank=1, max_rank=10, custom_timeout=None
        )

        # Test post
        next_node = node.post(shared, prep_result, exec_result)
        # By default, get_next_node_id returns None unless configured
        self.assertIsNone(next_node)
        self.assertEqual(shared["trials_data"], mock_response)
        self.assertEqual(shared["studies"], mock_response["studies"])


class TestSummarizeTrialsNode(unittest.TestCase):
    """Test the SummarizeTrialsNode class."""

    @patch("utils.llm_service.LLMService.call_llm")
    def test_summarize_trials_node(self, mock_summarize):
        """Test the SummarizeTrialsNode workflow."""
        # Setup mock
        mock_summary = "# Clinical Trials Summary\n\nFound 1 clinical trial."
        mock_summarize.return_value = mock_summary

        # Test data
        studies = [{"protocolSection": {"identificationModule": {"briefTitle": "Test Trial"}}}]

        # Create node and test
        node = SummarizeTrialsNode()
        shared = {"studies": studies}

        # Test prep
        prep_result = node.prep(shared)
        self.assertEqual(prep_result, studies)

        # Test exec
        exec_result = node.exec(prep_result)
        self.assertEqual(exec_result, mock_summary)
        # The actual call includes a prompt, so we just check it was called
        mock_summarize.assert_called_once()

        # Test post
        next_node = node.post(shared, prep_result, exec_result)
        self.assertIsNone(next_node)
        self.assertEqual(shared["summary"], mock_summary)


class TestFlow(unittest.TestCase):
    """Test the Flow class."""

    def test_flow_execution(self):
        """Test that a flow can be created and configured."""
        # This test now just verifies basic flow creation since the old
        # Flow interface with add_node() and process() methods no longer exists
        # in the unified architecture
        
        # Create a simple mock node for flow creation
        query_node = MagicMock()
        
        # Create flow - this tests the new UnifiedFlow constructor
        flow = Flow(start_node=query_node)
        
        # Verify flow was created with the start node
        self.assertEqual(flow.start_node, query_node)
        self.assertIsInstance(flow, Flow)
        
        # Note: The old add_node() and run() methods don't exist in UnifiedFlow
        # The unified architecture uses execute() and a different node chaining approach


if __name__ == "__main__":
    unittest.main()
