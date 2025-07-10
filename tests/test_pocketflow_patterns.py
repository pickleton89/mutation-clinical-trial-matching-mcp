"""
Tests for PocketFlow pattern alignment improvements.

This module tests the new chaining and branching functionality that aligns
with PocketFlow documentation patterns.
"""

import unittest
from typing import Any

from utils.node import AsyncFlow, AsyncNode, Flow, Node


class MockNode(Node):
    """Mock node for chaining tests."""

    def __init__(self, name: str = "test_node"):
        super().__init__()
        self.name = name
        self.prep_called = False
        self.exec_called = False
        self.post_called = False

    def prep(self, shared: dict[str, Any]) -> str:
        self.prep_called = True
        # Check if previous node result exists, otherwise use original input
        prev_result = shared.get(f"{self.name}_input")
        if prev_result is None:
            return shared.get("input", "")
        return prev_result

    def exec(self, prep_result: str) -> str:
        self.exec_called = True
        return f"{self.name}_processed_{prep_result}"

    def post(self, shared: dict[str, Any], prep_result: str, exec_result: str) -> str | None:
        self.post_called = True
        shared[f"{self.name}_result"] = exec_result

        # Set input for next node if it exists
        if self._next_node:
            shared[f"{self._next_node.name}_input"] = exec_result

        return self.get_next_node_id()


class MockBranchingNode(Node):
    """Mock node for branching tests."""

    def __init__(self, name: str = "branch_node"):
        super().__init__()
        self.name = name
        self.decision_logic = None

    def prep(self, shared: dict[str, Any]) -> dict[str, Any]:
        return shared

    def exec(self, prep_result: dict[str, Any]) -> str:
        # Decision logic for branching
        value = prep_result.get("value", 0)
        if value > 10:
            return "high"
        elif value > 5:
            return "medium"
        else:
            return "low"

    def post(self, shared: dict[str, Any], prep_result: dict[str, Any], exec_result: str) -> str | None:
        shared["decision"] = exec_result

        # Set input for target branch node if it exists
        if exec_result in self._branches:
            target_node = self._branches[exec_result]
            shared[f"{target_node.name}_input"] = prep_result.get("input", "")

        return self.get_next_node_id(exec_result)


class MockAsyncNode(AsyncNode):
    """Mock async node for chaining tests."""

    def __init__(self, name: str = "async_test_node"):
        super().__init__()
        self.name = name
        self.prep_called = False
        self.exec_called = False
        self.post_called = False

    async def prep(self, shared: dict[str, Any]) -> str:
        self.prep_called = True
        return shared.get("input", "")

    async def exec(self, prep_result: str) -> str:
        self.exec_called = True
        return f"{self.name}_async_processed_{prep_result}"

    async def post(self, shared: dict[str, Any], prep_result: str, exec_result: str) -> str | None:
        self.post_called = True
        shared[f"{self.name}_result"] = exec_result
        return self.get_next_node_id()


class TestPocketFlowPatterns(unittest.TestCase):
    """Test cases for PocketFlow pattern alignment."""

    def test_node_chaining_operator(self):
        """Test the >> operator for node chaining."""
        node1 = MockNode("node1")
        node2 = MockNode("node2")

        # Test chaining syntax
        result = node1 >> node2

        # Verify chaining
        self.assertEqual(result, node2)
        self.assertEqual(node1._next_node, node2)

    def test_multiple_node_chaining(self):
        """Test chaining multiple nodes."""
        node1 = MockNode("node1")
        node2 = MockNode("node2")
        node3 = MockNode("node3")

        # Test multiple chaining
        node1 >> node2 >> node3

        # Verify chaining
        self.assertEqual(node1._next_node, node2)
        self.assertEqual(node2._next_node, node3)
        self.assertIsNone(node3._next_node)

    def test_branching_operator(self):
        """Test the - operator for branching."""
        branch_node = MockBranchingNode("branch")
        high_node = MockNode("high")
        medium_node = MockNode("medium")
        low_node = MockNode("low")

        # Test branching syntax
        branch_node - "high" >> high_node
        branch_node - "medium" >> medium_node
        branch_node - "low" >> low_node

        # Verify branching
        self.assertEqual(branch_node._branches["high"], high_node)
        self.assertEqual(branch_node._branches["medium"], medium_node)
        self.assertEqual(branch_node._branches["low"], low_node)

    def test_flow_with_chaining(self):
        """Test flow execution with chained nodes."""
        node1 = MockNode("node1")
        node2 = MockNode("node2")

        # Chain nodes
        node1 >> node2

        # Create flow
        flow = Flow(node1)

        # Run flow
        shared = {"input": "test"}
        result = flow.run(shared)

        # Verify execution
        self.assertTrue(node1.prep_called)
        self.assertTrue(node1.exec_called)
        self.assertTrue(node1.post_called)
        self.assertTrue(node2.prep_called)
        self.assertTrue(node2.exec_called)
        self.assertTrue(node2.post_called)

        # Verify results
        self.assertEqual(result["node1_result"], "node1_processed_test")
        self.assertEqual(result["node2_result"], "node2_processed_node1_processed_test")

    def test_flow_with_branching(self):
        """Test flow execution with branching."""
        branch_node = MockBranchingNode("branch")
        high_node = MockNode("high")
        medium_node = MockNode("medium")
        low_node = MockNode("low")

        # Set up branching
        branch_node - "high" >> high_node
        branch_node - "medium" >> medium_node
        branch_node - "low" >> low_node

        # Create flow
        flow = Flow(branch_node)

        # Test high branch
        shared = {"value": 15}
        result = flow.run(shared)

        self.assertEqual(result["decision"], "high")
        self.assertTrue("high_result" in result)
        self.assertFalse("medium_result" in result)
        self.assertFalse("low_result" in result)

        # Test medium branch
        shared = {"value": 7}
        result = flow.run(shared)

        self.assertEqual(result["decision"], "medium")
        self.assertTrue("medium_result" in result)
        self.assertFalse("high_result" in result)
        self.assertFalse("low_result" in result)

        # Test low branch
        shared = {"value": 2}
        result = flow.run(shared)

        self.assertEqual(result["decision"], "low")
        self.assertTrue("low_result" in result)
        self.assertFalse("high_result" in result)
        self.assertFalse("medium_result" in result)

    def test_complex_flow_with_chaining_and_branching(self):
        """Test complex flow with both chaining and branching."""
        initial_node = MockNode("initial")
        branch_node = MockBranchingNode("branch")
        high_node = MockNode("high")
        medium_node = MockNode("medium")
        low_node = MockNode("low")
        final_node = MockNode("final")

        # Set up complex flow
        initial_node >> branch_node
        branch_node - "high" >> high_node >> final_node
        branch_node - "medium" >> medium_node >> final_node
        branch_node - "low" >> low_node >> final_node

        # Create flow
        flow = Flow(initial_node)

        # Test execution
        shared = {"input": "test", "value": 12}
        result = flow.run(shared)

        # Verify all nodes were called appropriately
        self.assertTrue(initial_node.prep_called)
        self.assertTrue(initial_node.exec_called)
        self.assertTrue(initial_node.post_called)

        self.assertEqual(result["decision"], "high")
        self.assertTrue("high_result" in result)
        self.assertTrue("final_result" in result)

    def test_async_node_chaining(self):
        """Test async node chaining."""
        async_node1 = MockAsyncNode("async1")
        async_node2 = MockAsyncNode("async2")

        # Test async chaining
        result = async_node1 >> async_node2

        # Verify chaining
        self.assertEqual(result, async_node2)
        self.assertEqual(async_node1._next_node, async_node2)

    async def test_async_flow_execution(self):
        """Test async flow execution with chained nodes."""
        async_node1 = MockAsyncNode("async1")
        async_node2 = MockAsyncNode("async2")

        # Chain nodes
        async_node1 >> async_node2

        # Create async flow
        flow = AsyncFlow(async_node1)

        # Run flow
        shared = {"input": "async_test"}
        result = await flow.run(shared)

        # Verify execution
        self.assertTrue(async_node1.prep_called)
        self.assertTrue(async_node1.exec_called)
        self.assertTrue(async_node1.post_called)
        self.assertTrue(async_node2.prep_called)
        self.assertTrue(async_node2.exec_called)
        self.assertTrue(async_node2.post_called)

        # Verify results
        self.assertEqual(result["async1_result"], "async1_async_processed_async_test")
        self.assertEqual(result["async2_result"], "async2_async_processed_async1_async_processed_async_test")

    def test_node_auto_registration(self):
        """Test automatic node registration in flows."""
        node1 = MockNode("node1")
        node2 = MockNode("node2")
        node3 = MockNode("node3")

        # Create complex chaining
        node1 >> node2 >> node3

        # Create flow
        flow = Flow(node1)

        # Verify all nodes are registered
        self.assertEqual(len(flow.nodes), 3)

        # Verify node IDs are correct
        node1_id = f"node_{id(node1)}"
        node2_id = f"node_{id(node2)}"
        node3_id = f"node_{id(node3)}"

        self.assertIn(node1_id, flow.nodes)
        self.assertIn(node2_id, flow.nodes)
        self.assertIn(node3_id, flow.nodes)

    def test_branching_auto_registration(self):
        """Test automatic registration of branched nodes."""
        branch_node = MockBranchingNode("branch")
        high_node = MockNode("high")
        medium_node = MockNode("medium")
        low_node = MockNode("low")

        # Set up branching
        branch_node - "high" >> high_node
        branch_node - "medium" >> medium_node
        branch_node - "low" >> low_node

        # Create flow
        flow = Flow(branch_node)

        # Verify all nodes are registered
        self.assertEqual(len(flow.nodes), 4)  # branch + 3 target nodes

        # Verify specific nodes
        branch_id = f"node_{id(branch_node)}"
        high_id = f"node_{id(high_node)}"
        medium_id = f"node_{id(medium_node)}"
        low_id = f"node_{id(low_node)}"

        self.assertIn(branch_id, flow.nodes)
        self.assertIn(high_id, flow.nodes)
        self.assertIn(medium_id, flow.nodes)
        self.assertIn(low_id, flow.nodes)

    def test_get_next_node_id_logic(self):
        """Test the get_next_node_id method logic."""
        node1 = MockNode("node1")
        node2 = MockNode("node2")
        node3 = MockNode("node3")

        # Test simple chaining
        node1 >> node2
        next_id = node1.get_next_node_id()
        expected_id = f"node_{id(node2)}"
        self.assertEqual(next_id, expected_id)

        # Test branching
        node1 - "action1" >> node3
        next_id = node1.get_next_node_id("action1")
        expected_id = f"node_{id(node3)}"
        self.assertEqual(next_id, expected_id)

        # Test branching with default fallback
        next_id = node1.get_next_node_id("unknown_action")
        expected_id = f"node_{id(node2)}"  # Should fall back to chained node
        self.assertEqual(next_id, expected_id)

    def test_error_handling_in_chained_flow(self):
        """Test error handling in chained flows."""
        class ErrorNode(Node):
            def __init__(self):
                super().__init__()
                self.name = "error_node"

            def prep(self, shared: dict[str, Any]) -> str:
                return "test"

            def exec(self, prep_result: str) -> str:
                raise ValueError("Test error")

            def post(self, shared: dict[str, Any], prep_result: str, exec_result: str) -> str | None:
                return self.get_next_node_id()

        node1 = MockNode("node1")
        error_node = ErrorNode()
        node3 = MockNode("node3")

        # Chain nodes
        node1 >> error_node >> node3

        # Create flow
        flow = Flow(node1)

        # Run flow
        shared = {"input": "test"}
        result = flow.run(shared)

        # Verify error was handled
        self.assertIn("error", result)
        self.assertEqual(result["error_type"], "ValueError")

        # Verify node1 executed but node3 didn't
        self.assertTrue(node1.prep_called)
        self.assertTrue(node1.exec_called)
        self.assertTrue(node1.post_called)
        self.assertFalse(node3.prep_called)


if __name__ == "__main__":
    unittest.main()
