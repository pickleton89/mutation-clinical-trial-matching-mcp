"""
Tests for unified nodes in both sync and async modes.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from clinicaltrials.unified_nodes import QueryTrialsNode, SummarizeTrialsNode, BatchQueryTrialsNode
from utils.unified_node import UnifiedFlow


class TestQueryTrialsNode:
    """Test the unified QueryTrialsNode."""
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_node_initialization(self, async_mode):
        """Test node initialization in both modes."""
        node = QueryTrialsNode(
            async_mode=async_mode,
            min_rank=1,
            max_rank=5,
            timeout=30.0
        )
        
        assert node.async_mode == async_mode
        assert node.min_rank == 1
        assert node.max_rank == 5
        assert node.timeout == 30.0
        assert node.trials_service.async_mode == async_mode
    
    def test_prep_method(self):
        """Test prep method extracts mutation correctly."""
        node = QueryTrialsNode(async_mode=False)
        
        shared = {"mutation": "BRAF V600E"}
        result = node.prep(shared)
        
        assert result == "BRAF V600E"
    
    def test_prep_method_missing_mutation(self):
        """Test prep method raises error when mutation is missing."""
        node = QueryTrialsNode(async_mode=False)
        
        shared = {}
        
        with pytest.raises(ValueError, match="No mutation found"):
            node.prep(shared)
    
    @patch('clinicaltrials.service.ClinicalTrialsService')
    def test_sync_exec_method(self, mock_service_class):
        """Test sync exec method."""
        # Set up mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.query_trials.return_value = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}
            ]
        }
        
        node = QueryTrialsNode(async_mode=False, min_rank=1, max_rank=5)
        
        result = node.exec("BRAF V600E")
        
        assert "studies" in result
        assert len(result["studies"]) == 1
        mock_service.query_trials.assert_called_once_with(
            mutation="BRAF V600E",
            min_rank=1,
            max_rank=5,
            custom_timeout=None
        )
    
    @patch('clinicaltrials.service.ClinicalTrialsService')
    @pytest.mark.asyncio
    async def test_async_exec_method(self, mock_service_class):
        """Test async exec method."""
        # Set up mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.aquery_trials = AsyncMock(return_value={
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}
            ]
        })
        
        node = QueryTrialsNode(async_mode=True, min_rank=1, max_rank=5)
        
        result = await node.aexec("BRAF V600E")
        
        assert "studies" in result
        assert len(result["studies"]) == 1
        mock_service.aquery_trials.assert_called_once_with(
            mutation="BRAF V600E",
            min_rank=1,
            max_rank=5
        )
    
    def test_post_method(self):
        """Test post method stores results correctly."""
        node = QueryTrialsNode(async_mode=False)
        
        shared = {}
        prep_result = "BRAF V600E"
        exec_result = {
            "studies": [
                {"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}
            ]
        }
        
        next_node_id = node.post(shared, prep_result, exec_result)
        
        assert shared["trials_data"] == exec_result
        assert shared["studies"] == exec_result["studies"]
        assert shared["queried_mutation"] == "BRAF V600E"
        assert "query_error" not in shared
    
    def test_post_method_with_error(self):
        """Test post method handles errors correctly."""
        node = QueryTrialsNode(async_mode=False)
        
        shared = {}
        prep_result = "INVALID"
        exec_result = {
            "error": "Invalid mutation format",
            "studies": []
        }
        
        next_node_id = node.post(shared, prep_result, exec_result)
        
        assert shared["trials_data"] == exec_result
        assert shared["studies"] == []
        assert shared["query_error"] == "Invalid mutation format"


class TestSummarizeTrialsNode:
    """Test the unified SummarizeTrialsNode."""
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_node_initialization(self, async_mode):
        """Test node initialization in both modes."""
        node = SummarizeTrialsNode(
            async_mode=async_mode,
            model="claude-3-sonnet",
            max_tokens=2000
        )
        
        assert node.async_mode == async_mode
        assert node.model == "claude-3-sonnet"
        assert node.max_tokens == 2000
        assert node.llm_service.async_mode == async_mode
    
    def test_prep_method(self):
        """Test prep method extracts studies correctly."""
        node = SummarizeTrialsNode(async_mode=False)
        
        studies = [
            {"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}
        ]
        shared = {"studies": studies, "mutation": "BRAF V600E"}
        
        result = node.prep(shared)
        
        assert result == studies
        assert node._current_mutation == "BRAF V600E"
    
    def test_prep_method_empty_studies(self):
        """Test prep method handles empty studies."""
        node = SummarizeTrialsNode(async_mode=False)
        
        shared = {"studies": [], "mutation": "UNKNOWN"}
        
        result = node.prep(shared)
        
        assert result == []
        assert node._current_mutation == "UNKNOWN"
    
    def test_build_summarization_prompt_empty(self):
        """Test prompt building with empty studies."""
        node = SummarizeTrialsNode(async_mode=False)
        
        prompt = node._build_summarization_prompt([], "BRAF V600E")
        
        assert "No clinical trials were found" in prompt
        assert "BRAF V600E" in prompt
    
    def test_build_summarization_prompt_with_studies(self):
        """Test prompt building with studies."""
        node = SummarizeTrialsNode(async_mode=False)
        
        studies = [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT12345678",
                        "briefTitle": "Test Trial for BRAF"
                    },
                    "statusModule": {
                        "overallStatus": "RECRUITING"
                    },
                    "designModule": {
                        "phases": ["PHASE2"]
                    }
                }
            }
        ]
        
        prompt = node._build_summarization_prompt(studies, "BRAF V600E")
        
        assert "BRAF V600E" in prompt
        assert "NCT12345678" in prompt
        assert "Test Trial for BRAF" in prompt
        assert "RECRUITING" in prompt
        assert "PHASE2" in prompt
    
    @patch('utils.llm_service.LLMService')
    def test_sync_exec_method(self, mock_service_class):
        """Test sync exec method."""
        # Set up mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.call_llm.return_value = "# Clinical Trial Summary\n\nTest summary content"
        
        node = SummarizeTrialsNode(async_mode=False)
        node._current_mutation = "BRAF V600E"
        
        studies = [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        result = node.exec(studies)
        
        assert result == "# Clinical Trial Summary\n\nTest summary content"
        mock_service.call_llm.assert_called_once()
        
        # Check that the prompt was built correctly
        call_args = mock_service.call_llm.call_args[0][0]
        assert "BRAF V600E" in call_args
    
    @patch('utils.llm_service.LLMService')
    @pytest.mark.asyncio
    async def test_async_exec_method(self, mock_service_class):
        """Test async exec method."""
        # Set up mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.acall_llm = AsyncMock(return_value="# Async Clinical Trial Summary\n\nTest summary content")
        
        node = SummarizeTrialsNode(async_mode=True)
        node._current_mutation = "BRAF V600E"
        
        studies = [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        result = await node.aexec(studies)
        
        assert result == "# Async Clinical Trial Summary\n\nTest summary content"
        mock_service.acall_llm.assert_called_once()
        
        # Check that the prompt was built correctly
        call_args = mock_service.acall_llm.call_args[0][0]
        assert "BRAF V600E" in call_args
    
    def test_post_method(self):
        """Test post method stores summary correctly."""
        node = SummarizeTrialsNode(async_mode=False)
        
        shared = {"mutation": "BRAF V600E"}
        prep_result = [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        exec_result = "# Clinical Trial Summary\n\nTest summary"
        
        next_node_id = node.post(shared, prep_result, exec_result)
        
        assert shared["summary"] == exec_result


class TestBatchQueryTrialsNode:
    """Test the unified BatchQueryTrialsNode."""
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_node_initialization(self, async_mode):
        """Test batch node initialization in both modes."""
        node = BatchQueryTrialsNode(
            async_mode=async_mode,
            min_rank=1,
            max_rank=5,
            max_concurrent=3
        )
        
        assert node.async_mode == async_mode
        assert node.min_rank == 1
        assert node.max_rank == 5
        assert node.max_concurrent == 3
        assert node.trials_service.async_mode == async_mode
    
    def test_prep_method_with_mutations_list(self):
        """Test prep method with mutations list."""
        node = BatchQueryTrialsNode(async_mode=False)
        
        shared = {"mutations": ["BRAF V600E", "EGFR L858R", "ALK EML4"]}
        result = node.prep(shared)
        
        assert result == ["BRAF V600E", "EGFR L858R", "ALK EML4"]
    
    def test_prep_method_with_single_mutation(self):
        """Test prep method falls back to single mutation."""
        node = BatchQueryTrialsNode(async_mode=False)
        
        shared = {"mutation": "BRAF V600E"}
        result = node.prep(shared)
        
        assert result == ["BRAF V600E"]
    
    def test_prep_method_no_mutations(self):
        """Test prep method raises error when no mutations found."""
        node = BatchQueryTrialsNode(async_mode=False)
        
        shared = {}
        
        with pytest.raises(ValueError, match="No mutations found"):
            node.prep(shared)
    
    @patch('clinicaltrials.service.ClinicalTrialsService')
    def test_sync_exec_single(self, mock_service_class):
        """Test sync exec_single method."""
        # Set up mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.query_trials.return_value = {
            "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        }
        
        node = BatchQueryTrialsNode(async_mode=False)
        
        result = node.exec_single("BRAF V600E")
        
        assert "studies" in result
        assert result["mutation"] == "BRAF V600E"
        mock_service.query_trials.assert_called_once()
    
    @patch('clinicaltrials.service.ClinicalTrialsService')
    @pytest.mark.asyncio
    async def test_async_exec_single(self, mock_service_class):
        """Test async exec_single method."""
        # Set up mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.aquery_trials = AsyncMock(return_value={
            "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        })
        
        node = BatchQueryTrialsNode(async_mode=True)
        
        result = await node.aexec_single("BRAF V600E")
        
        assert "studies" in result
        assert result["mutation"] == "BRAF V600E"
        mock_service.aquery_trials.assert_called_once()
    
    def test_post_method(self):
        """Test post method aggregates results correctly."""
        node = BatchQueryTrialsNode(async_mode=False)
        
        shared = {}
        prep_result = ["BRAF V600E", "EGFR L858R"]
        exec_result = [
            {"studies": [{"nctId": "NCT1"}], "mutation": "BRAF V600E"},
            {"studies": [{"nctId": "NCT2"}, {"nctId": "NCT3"}], "mutation": "EGFR L858R"}
        ]
        
        next_node_id = node.post(shared, prep_result, exec_result)
        
        assert shared["batch_results"] == exec_result
        assert shared["queried_mutations"] == prep_result
        assert shared["batch_stats"]["total_mutations"] == 2
        assert shared["batch_stats"]["successful_queries"] == 2
        assert shared["batch_stats"]["total_studies"] == 3
        assert shared["batch_stats"]["errors"] == []
    
    def test_post_method_with_errors(self):
        """Test post method handles errors correctly."""
        node = BatchQueryTrialsNode(async_mode=False)
        
        shared = {}
        prep_result = ["BRAF V600E", "INVALID", "EGFR L858R"]
        exec_result = [
            {"studies": [{"nctId": "NCT1"}], "mutation": "BRAF V600E"},
            {"error": "Invalid mutation", "studies": [], "mutation": "INVALID"},
            Exception("Network error")
        ]
        
        next_node_id = node.post(shared, prep_result, exec_result)
        
        assert shared["batch_stats"]["total_mutations"] == 3
        assert shared["batch_stats"]["successful_queries"] == 1
        assert shared["batch_stats"]["total_studies"] == 1
        assert len(shared["batch_stats"]["errors"]) == 2


class TestUnifiedFlow:
    """Test the unified flow with unified nodes."""
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_flow_initialization(self, async_mode):
        """Test flow initialization with unified nodes."""
        query_node = QueryTrialsNode(async_mode=async_mode)
        flow = UnifiedFlow(start_node=query_node, async_mode=async_mode)
        
        assert flow.async_mode == async_mode
        assert flow.start_node == query_node
        assert query_node.node_id in flow.nodes
    
    @patch('clinicaltrials.service.ClinicalTrialsService')
    @patch('utils.llm_service.LLMService')
    def test_sync_flow_execution(self, mock_llm_service_class, mock_trials_service_class):
        """Test sync flow execution."""
        # Set up mocks
        mock_trials_service = Mock()
        mock_trials_service_class.return_value = mock_trials_service
        mock_trials_service.query_trials.return_value = {
            "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        }
        
        mock_llm_service = Mock()
        mock_llm_service_class.return_value = mock_llm_service
        mock_llm_service.call_llm.return_value = "# Summary\n\nTest summary"
        
        # Create nodes and flow
        query_node = QueryTrialsNode(async_mode=False)
        summarize_node = SummarizeTrialsNode(async_mode=False)
        
        # Set up chaining
        query_node >> summarize_node
        
        flow = UnifiedFlow(start_node=query_node, async_mode=False)
        flow.add_node(summarize_node)
        
        # Execute flow
        initial_shared = {"mutation": "BRAF V600E"}
        result = flow.execute(initial_shared)
        
        # Verify results
        assert "trials_data" in result
        assert "studies" in result
        assert "summary" in result
        assert result["summary"] == "# Summary\n\nTest summary"
    
    @patch('clinicaltrials.service.ClinicalTrialsService')
    @patch('utils.llm_service.LLMService')
    @pytest.mark.asyncio
    async def test_async_flow_execution(self, mock_llm_service_class, mock_trials_service_class):
        """Test async flow execution."""
        # Set up mocks
        mock_trials_service = Mock()
        mock_trials_service_class.return_value = mock_trials_service
        mock_trials_service.aquery_trials = AsyncMock(return_value={
            "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]
        })
        
        mock_llm_service = Mock()
        mock_llm_service_class.return_value = mock_llm_service
        mock_llm_service.acall_llm = AsyncMock(return_value="# Async Summary\n\nTest summary")
        
        # Create nodes and flow
        query_node = QueryTrialsNode(async_mode=True)
        summarize_node = SummarizeTrialsNode(async_mode=True)
        
        # Set up chaining
        query_node >> summarize_node
        
        flow = UnifiedFlow(start_node=query_node, async_mode=True)
        flow.add_node(summarize_node)
        
        # Execute flow
        initial_shared = {"mutation": "BRAF V600E"}
        result = await flow.aexecute(initial_shared)
        
        # Verify results
        assert "trials_data" in result
        assert "studies" in result
        assert "summary" in result
        assert result["summary"] == "# Async Summary\n\nTest summary"