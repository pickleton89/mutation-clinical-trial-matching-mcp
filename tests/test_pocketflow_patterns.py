"""
Tests for PocketFlow pattern alignment improvements.

This module tests the unified node framework that replaced the legacy
PocketFlow pattern implementations.
"""

import unittest
from typing import Any, Dict

from utils.unified_node import UnifiedFlow, UnifiedNode


class MockNode(UnifiedNode[str, str]):
    """Mock node for unified framework tests."""

    def prep(self, shared: Dict[str, Any]) -> str:
        """Extract input from shared context."""
        return shared.get("input", "")

    def exec(self, prep_result: str) -> str:
        """Process the input."""
        return f"processed_{prep_result}"

    def post(self, shared: Dict[str, Any], prep_result: str, exec_result: str) -> str:
        """Store result and return next node."""
        shared["result"] = exec_result
        return "end"


class TestUnifiedPocketFlowPatterns(unittest.TestCase):
    """Test the unified node framework patterns."""

    def test_basic_node_execution(self):
        """Test basic node execution in sync mode."""
        node = MockNode()
        shared = {"input": "test"}
        
        # Test prep
        prep_result = node.prep(shared)
        self.assertEqual(prep_result, "test")
        
        # Test exec
        exec_result = node.exec(prep_result)
        self.assertEqual(exec_result, "processed_test")
        
        # Test post
        next_node = node.post(shared, prep_result, exec_result)
        self.assertEqual(next_node, "end")
        self.assertEqual(shared["result"], "processed_test")

    def test_unified_flow_execution(self):
        """Test that unified flow can execute nodes."""
        node = MockNode()
        flow = UnifiedFlow(node)
        
        shared = {"input": "flow_test"}
        result = flow.execute(shared)
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["result"], "processed_flow_test")

    def test_auto_mode_detection(self):
        """Test that nodes can auto-detect their execution mode."""
        node = MockNode()
        
        # Should default to sync mode for non-async methods
        self.assertFalse(node._detect_async_mode())

    def test_node_initialization(self):
        """Test node initialization with different parameters."""
        # Test with explicit async mode
        node = MockNode(async_mode=True)
        self.assertTrue(node.async_mode)
        
        # Test with node ID
        node = MockNode(node_id="test_node")
        self.assertEqual(node.node_id, "test_node")
        
        # Test default node ID
        node = MockNode()
        self.assertEqual(node.node_id, "MockNode")


if __name__ == "__main__":
    unittest.main(verbosity=2)