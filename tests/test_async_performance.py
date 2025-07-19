"""
Performance tests for async implementation.
"""

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from clinicaltrials.unified_nodes import QueryTrialsNode, BatchQueryTrialsNode
from clinicaltrials.service import get_async_trials_service
from utils.llm_service import get_async_llm_service
from utils.unified_node import UnifiedFlow


class TestAsyncPerformance(unittest.TestCase):
    """Test async performance improvements."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_mutations = ["EGFR L858R", "BRAF V600E", "KRAS G12C", "ALK EML4", "ROS1 CD74"]
        self.mock_response = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {"briefTitle": "Test Study", "nctId": "NCT123456"},
                        "statusModule": {"overallStatus": "Recruiting"},
                    }
                }
            ]
        }

    @patch("clinicaltrials.async_query.get_async_client")
    async def test_async_query_performance(self, mock_get_client):
        """Test that async query performs well."""
        # Mock async client
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_response
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Test single async query
        start_time = time.time()
        result = await query_clinical_trials_async("EGFR L858R")
        single_duration = time.time() - start_time

        self.assertIsInstance(result, dict)
        self.assertIn("studies", result)
        self.assertLess(single_duration, 1.0)  # Should complete within 1 second

    @patch("clinicaltrials.async_query.get_async_client")
    async def test_batch_query_performance(self, mock_get_client):
        """Test that batch queries are faster than sequential queries."""
        # Mock async client
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_response
        mock_client.get.return_value = mock_response
        mock_get_client.return_value = mock_client

        # Test batch query
        start_time = time.time()
        batch_result = await query_multiple_mutations_async(self.test_mutations)
        batch_duration = time.time() - start_time

        # Test sequential queries for comparison
        start_time = time.time()
        sequential_results = {}
        for mutation in self.test_mutations:
            sequential_results[mutation] = await query_clinical_trials_async(mutation)
        sequential_duration = time.time() - start_time

        # Batch should be faster than sequential (with some tolerance for test timing)
        self.assertLess(batch_duration, sequential_duration * 0.8)
        self.assertEqual(len(batch_result), len(self.test_mutations))

    @patch("utils.async_call_llm.get_anthropic_async_client")
    async def test_llm_batch_performance(self, mock_get_client):
        """Test that batch LLM calls are faster than sequential calls."""
        # Mock async client
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"content": [{"text": "Mock response"}]}
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_get_client.return_value = mock_client

        prompts = [f"Summarize trials for {mutation}" for mutation in self.test_mutations]

        # Test batch LLM calls
        start_time = time.time()
        batch_results = await call_llm_batch_async(prompts)
        batch_duration = time.time() - start_time

        # Test sequential LLM calls
        start_time = time.time()
        sequential_results = []
        for prompt in prompts:
            result = await call_llm_async(prompt)
            sequential_results.append(result)
        sequential_duration = time.time() - start_time

        # Batch should be faster than sequential
        self.assertLess(batch_duration, sequential_duration * 0.8)
        self.assertEqual(len(batch_results), len(prompts))

    @patch("clinicaltrials.async_query.get_async_client")
    @patch("utils.async_call_llm.get_anthropic_async_client")
    async def test_async_flow_performance(self, mock_llm_client, mock_api_client):
        """Test performance of async flow execution."""
        # Mock API client
        mock_api_response = AsyncMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = self.mock_response
        mock_api_client.return_value.get.return_value = mock_api_response

        # Mock LLM client
        mock_llm_response = AsyncMock()
        mock_llm_response.status_code = 200
        mock_llm_response.json.return_value = {"content": [{"text": "Mock summary"}]}
        mock_llm_response.raise_for_status = MagicMock()
        mock_llm_client.return_value.post.return_value = mock_llm_response

        # Create async flow
        query_node = AsyncQueryTrialsNode()
        flow = AsyncFlow(query_node)

        # Test flow performance
        start_time = time.time()
        shared = {"mutation": "EGFR L858R"}
        result = await flow.run(shared)
        flow_duration = time.time() - start_time

        self.assertIsInstance(result, dict)
        self.assertIn("trials_data", result)
        self.assertLess(flow_duration, 2.0)  # Should complete within 2 seconds

    @patch("clinicaltrials.async_query.get_async_client")
    async def test_concurrent_request_limits(self, mock_get_client):
        """Test that concurrent request limits are respected."""
        # Mock async client with delay to test concurrency
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.mock_response

        # Add delay to simulate real network requests
        async def mock_get_with_delay(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return mock_response

        mock_client.get.side_effect = mock_get_with_delay
        mock_get_client.return_value = mock_client

        # Test with different concurrency limits
        mutations = self.test_mutations * 2  # 10 mutations

        # Test with high concurrency
        start_time = time.time()
        result_high = await query_multiple_mutations_async(mutations, max_concurrent=10)
        high_duration = time.time() - start_time

        # Test with low concurrency
        start_time = time.time()
        result_low = await query_multiple_mutations_async(mutations, max_concurrent=2)
        low_duration = time.time() - start_time

        # Both should complete successfully
        self.assertEqual(len(result_high), len(mutations))
        self.assertEqual(len(result_low), len(mutations))

        # High concurrency should be faster
        self.assertLess(high_duration, low_duration)

    def test_async_vs_sync_compatibility(self):
        """Test that async and sync interfaces are compatible."""
        # This would be a more complex test involving actual sync/async comparison
        # For now, just verify the interfaces exist
        # Both functions should have similar signatures
        import inspect

        from clinicaltrials.service import get_async_trials_service, get_sync_trials_service
        
        async_service = get_async_trials_service()
        sync_service = get_sync_trials_service()

        sync_sig = inspect.signature(query_clinical_trials)
        async_sig = inspect.signature(query_clinical_trials_async)

        # Parameter names should match
        sync_params = set(sync_sig.parameters.keys())
        async_params = set(async_sig.parameters.keys())

        self.assertEqual(sync_params, async_params)


class TestAsyncPerformanceRunner:
    """Helper class to run async performance tests."""

    @staticmethod
    def run_async_test(test_method):
        """Run an async test method."""
        test_instance = TestAsyncPerformance()
        test_instance.setUp()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(test_method(test_instance))
        finally:
            loop.close()


if __name__ == "__main__":
    # Run async tests
    runner = TestAsyncPerformanceRunner()

    print("Running async performance tests...")

    # Test async query performance
    try:
        runner.run_async_test(TestAsyncPerformance.test_async_query_performance)
        print("✓ Async query performance test passed")
    except Exception as e:
        print(f"✗ Async query performance test failed: {e}")

    # Test batch query performance
    try:
        runner.run_async_test(TestAsyncPerformance.test_batch_query_performance)
        print("✓ Batch query performance test passed")
    except Exception as e:
        print(f"✗ Batch query performance test failed: {e}")

    # Test LLM batch performance
    try:
        runner.run_async_test(TestAsyncPerformance.test_llm_batch_performance)
        print("✓ LLM batch performance test passed")
    except Exception as e:
        print(f"✗ LLM batch performance test failed: {e}")

    # Test async flow performance
    try:
        runner.run_async_test(TestAsyncPerformance.test_async_flow_performance)
        print("✓ Async flow performance test passed")
    except Exception as e:
        print(f"✗ Async flow performance test failed: {e}")

    # Test concurrent request limits
    try:
        runner.run_async_test(TestAsyncPerformance.test_concurrent_request_limits)
        print("✓ Concurrent request limits test passed")
    except Exception as e:
        print(f"✗ Concurrent request limits test failed: {e}")

    # Run regular unit tests
    unittest.main(verbosity=2)
