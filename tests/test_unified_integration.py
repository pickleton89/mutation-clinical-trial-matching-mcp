"""
Integration tests for unified components demonstrating end-to-end flow.

This test suite validates that the new unified HTTP client, LLM service,
and Clinical Trials service work together correctly in both sync and async modes.
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from utils.http_client import UnifiedHttpClient
from utils.llm_service import LLMService
from clinicaltrials.service import ClinicalTrialsService


class TestUnifiedIntegration:
    """Test integration between all unified components."""
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_complete_flow_mock(self, async_mode):
        """Test complete flow from query to LLM summarization (mocked)."""
        
        # Mock responses
        mock_trials_response = {
            "studies": [
                {
                    "protocolSection": {
                        "identificationModule": {
                            "nctId": "NCT12345678",
                            "briefTitle": "Test Trial for BRAF V600E Mutation"
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
        }
        
        mock_llm_response = {
            "content": [
                {
                    "type": "text",
                    "text": "# Clinical Trial Summary\n\n**NCT12345678**: Test Trial for BRAF V600E Mutation\n- Status: RECRUITING\n- Phase: 2"
                }
            ]
        }
        
        if async_mode:
            asyncio.run(self._test_async_flow(mock_trials_response, mock_llm_response))
        else:
            self._test_sync_flow(mock_trials_response, mock_llm_response)
    
    def _test_sync_flow(self, mock_trials_response: Dict[str, Any], mock_llm_response: Dict[str, Any]):
        """Test synchronous flow."""
        with patch('utils.http_client.requests.Session') as mock_session_class:
            # Set up mocks
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock trials API response
            mock_trials_resp = Mock()
            mock_trials_resp.status_code = 200
            mock_trials_resp.text = str(mock_trials_response).replace("'", '"')
            mock_trials_resp.json.return_value = mock_trials_response
            
            # Mock LLM API response
            mock_llm_resp = Mock()
            mock_llm_resp.status_code = 200
            mock_llm_resp.text = str(mock_llm_response).replace("'", '"')
            mock_llm_resp.json.return_value = mock_llm_response
            
            # Configure session to return appropriate responses
            def side_effect(*args, **kwargs):
                url = kwargs.get('url', args[1] if len(args) > 1 else '')
                if 'clinicaltrials.gov' in url or 'v2/studies' in url:
                    return mock_trials_resp
                elif 'anthropic.com' in url or 'v1/messages' in url:
                    return mock_llm_resp
                else:
                    raise ValueError(f"Unexpected URL: {url}")
            
            mock_session.request.side_effect = side_effect
            mock_session.get.side_effect = side_effect
            mock_session.post.side_effect = side_effect
            
            # Mock decorators to avoid their complexity in integration test
            with patch('utils.http_client.exponential_backoff_retry') as mock_retry, \
                 patch('utils.http_client.circuit_breaker') as mock_cb, \
                 patch('utils.shared.time_request') as mock_timer, \
                 patch('utils.response_validation.response_validator') as mock_validator:
                
                mock_retry.return_value = lambda f: f
                mock_cb.return_value = lambda f: f
                mock_timer.return_value = lambda f: f
                mock_validator.return_value = lambda f: f
                
                # Test the complete flow
                self._execute_sync_flow(mock_trials_response, mock_llm_response)
    
    def _execute_sync_flow(self, expected_trials: Dict[str, Any], expected_llm: Dict[str, Any]):
        """Execute the sync flow test."""
        # 1. Create services
        trials_service = ClinicalTrialsService(async_mode=False)
        llm_service = LLMService(async_mode=False, api_key="test-key")
        
        # 2. Query trials
        mutation = "BRAF V600E"
        trials_result = trials_service.query_trials(mutation, min_rank=1, max_rank=5)
        
        # Verify trials result
        assert "error" not in trials_result
        assert "studies" in trials_result
        assert len(trials_result["studies"]) > 0
        
        study = trials_result["studies"][0]
        assert "protocolSection" in study
        assert "identificationModule" in study["protocolSection"]
        assert "nctId" in study["protocolSection"]["identificationModule"]
        
        # 3. Generate summary with LLM
        prompt = f"Summarize these clinical trials for {mutation}: {trials_result['studies']}"
        summary = llm_service.call_llm(prompt)
        
        # Verify LLM result
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "Clinical Trial Summary" in summary or "NCT12345678" in summary
        
        # 4. Cleanup
        trials_service.close()
        llm_service.close()
    
    async def _test_async_flow(self, mock_trials_response: Dict[str, Any], mock_llm_response: Dict[str, Any]):
        """Test asynchronous flow."""
        with patch('utils.http_client.httpx.AsyncClient') as mock_client_class:
            # Set up mocks
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # Mock trials API response
            mock_trials_resp = Mock()
            mock_trials_resp.status_code = 200
            mock_trials_resp.text = str(mock_trials_response).replace("'", '"')
            mock_trials_resp.json.return_value = mock_trials_response
            
            # Mock LLM API response
            mock_llm_resp = Mock()
            mock_llm_resp.status_code = 200
            mock_llm_resp.text = str(mock_llm_response).replace("'", '"')
            mock_llm_resp.json.return_value = mock_llm_response
            
            # Configure client to return appropriate responses
            async def side_effect(*args, **kwargs):
                url = kwargs.get('url', args[1] if len(args) > 1 else '')
                if 'clinicaltrials.gov' in url or 'v2/studies' in url:
                    return mock_trials_resp
                elif 'anthropic.com' in url or 'v1/messages' in url:
                    return mock_llm_resp
                else:
                    raise ValueError(f"Unexpected URL: {url}")
            
            mock_client.request = AsyncMock(side_effect=side_effect)
            mock_client.get = AsyncMock(side_effect=side_effect)
            mock_client.post = AsyncMock(side_effect=side_effect)
            mock_client.aclose = AsyncMock()
            
            # Mock decorators to avoid their complexity in integration test
            with patch('utils.http_client.async_exponential_backoff_retry') as mock_retry, \
                 patch('utils.http_client.async_circuit_breaker') as mock_cb, \
                 patch('utils.shared.time_request') as mock_timer, \
                 patch('utils.response_validation.response_validator') as mock_validator:
                
                mock_retry.return_value = lambda f: f
                mock_cb.return_value = lambda f: f
                mock_timer.return_value = lambda f: f
                mock_validator.return_value = lambda f: f
                
                # Test the complete async flow
                await self._execute_async_flow(mock_trials_response, mock_llm_response)
    
    async def _execute_async_flow(self, expected_trials: Dict[str, Any], expected_llm: Dict[str, Any]):
        """Execute the async flow test."""
        # 1. Create async services
        trials_service = ClinicalTrialsService(async_mode=True)
        llm_service = LLMService(async_mode=True, api_key="test-key")
        
        # 2. Query trials asynchronously
        mutation = "BRAF V600E"
        trials_result = await trials_service.aquery_trials(mutation, min_rank=1, max_rank=5)
        
        # Verify trials result
        assert "error" not in trials_result
        assert "studies" in trials_result
        assert len(trials_result["studies"]) > 0
        
        study = trials_result["studies"][0]
        assert "protocolSection" in study
        assert "identificationModule" in study["protocolSection"]
        assert "nctId" in study["protocolSection"]["identificationModule"]
        
        # 3. Generate summary with LLM asynchronously
        prompt = f"Summarize these clinical trials for {mutation}: {trials_result['studies']}"
        summary = await llm_service.acall_llm(prompt)
        
        # Verify LLM result
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "Clinical Trial Summary" in summary or "NCT12345678" in summary
        
        # 4. Cleanup
        await trials_service.aclose()
        await llm_service.aclose()
    
    @pytest.mark.parametrize("async_mode", [False, True])
    def test_error_handling_integration(self, async_mode):
        """Test error handling across integrated components."""
        if async_mode:
            asyncio.run(self._test_async_error_handling())
        else:
            self._test_sync_error_handling()
    
    def _test_sync_error_handling(self):
        """Test sync error handling."""
        with patch('utils.http_client.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock error response
            mock_resp = Mock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
            
            mock_session.request.return_value = mock_resp
            mock_session.get.return_value = mock_resp
            
            # Mock decorators
            with patch('utils.http_client.exponential_backoff_retry') as mock_retry, \
                 patch('utils.http_client.circuit_breaker') as mock_cb, \
                 patch('utils.shared.time_request') as mock_timer:
                
                mock_retry.return_value = lambda f: f
                mock_cb.return_value = lambda f: f
                mock_timer.return_value = lambda f: f
                
                # Test error handling
                trials_service = ClinicalTrialsService(async_mode=False)
                
                # Should return error response, not raise exception
                result = trials_service.query_trials("BRAF V600E")
                
                assert "error" in result
                assert "studies" in result
                assert result["studies"] == []
                
                trials_service.close()
    
    async def _test_async_error_handling(self):
        """Test async error handling."""
        with patch('utils.http_client.httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # Mock error response
            mock_resp = Mock()
            mock_resp.status_code = 500
            mock_resp.text = "Internal Server Error"
            mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
            
            mock_client.request = AsyncMock(return_value=mock_resp)
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.aclose = AsyncMock()
            
            # Mock decorators
            with patch('utils.http_client.async_exponential_backoff_retry') as mock_retry, \
                 patch('utils.http_client.async_circuit_breaker') as mock_cb, \
                 patch('utils.shared.time_request') as mock_timer:
                
                mock_retry.return_value = lambda f: f
                mock_cb.return_value = lambda f: f
                mock_timer.return_value = lambda f: f
                
                # Test error handling
                trials_service = ClinicalTrialsService(async_mode=True)
                
                # Should return error response, not raise exception
                result = await trials_service.aquery_trials("BRAF V600E")
                
                assert "error" in result
                assert "studies" in result
                assert result["studies"] == []
                
                await trials_service.aclose()
    
    def test_service_factory_functions(self):
        """Test that service factory functions work correctly."""
        # Import and test factory functions
        from clinicaltrials.service import get_sync_trials_service, get_async_trials_service
        from utils.llm_service import get_sync_llm_service, get_async_llm_service
        
        # Test sync services
        sync_trials = get_sync_trials_service()
        assert isinstance(sync_trials, ClinicalTrialsService)
        assert not sync_trials.async_mode
        
        # Test that we get the same instance (singleton pattern)
        sync_trials2 = get_sync_trials_service()
        assert sync_trials is sync_trials2
        
        # Test async services
        async_trials = get_async_trials_service()
        assert isinstance(async_trials, ClinicalTrialsService)
        assert async_trials.async_mode
        
        # Test that we get the same instance (singleton pattern)
        async_trials2 = get_async_trials_service()
        assert async_trials is async_trials2
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch processing capabilities."""
        with patch('utils.http_client.httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            # Mock successful responses for multiple mutations
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT12345", "briefTitle": "Test Trial"}}}]}'
            mock_response.json.return_value = {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {
                                "nctId": "NCT12345",
                                "briefTitle": "Test Trial"
                            }
                        }
                    }
                ]
            }
            
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            
            # Mock decorators
            with patch('utils.http_client.async_exponential_backoff_retry') as mock_retry, \
                 patch('utils.http_client.async_circuit_breaker') as mock_cb, \
                 patch('utils.shared.time_request') as mock_timer:
                
                mock_retry.return_value = lambda f: f
                mock_cb.return_value = lambda f: f
                mock_timer.return_value = lambda f: f
                
                # Test batch processing
                trials_service = ClinicalTrialsService(async_mode=True, max_concurrent_requests=2)
                
                mutations = ["BRAF V600E", "EGFR L858R", "ALK EML4"]
                results = await trials_service.aquery_trials_batch(mutations)
                
                assert len(results) == 3
                for result in results:
                    assert "studies" in result
                    assert len(result["studies"]) > 0
                
                await trials_service.aclose()
    
    def test_caching_functionality(self):
        """Test caching functionality in sync mode."""
        with patch('utils.http_client.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock response
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.text = '{"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT12345"}}}]}'
            mock_resp.json.return_value = {
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {
                                "nctId": "NCT12345"
                            }
                        }
                    }
                ]
            }
            
            mock_session.get.return_value = mock_resp
            
            # Mock decorators
            with patch('utils.http_client.exponential_backoff_retry') as mock_retry, \
                 patch('utils.http_client.circuit_breaker') as mock_cb, \
                 patch('utils.shared.time_request') as mock_timer:
                
                mock_retry.return_value = lambda f: f
                mock_cb.return_value = lambda f: f
                mock_timer.return_value = lambda f: f
                
                # Test caching
                trials_service = ClinicalTrialsService(async_mode=False, cache_enabled=True)
                
                # First call - should hit API
                result1 = trials_service.query_trials("BRAF V600E")
                assert "studies" in result1
                
                # Second call - should hit cache
                result2 = trials_service.query_trials("BRAF V600E")
                assert result1 == result2
                
                # Check cache stats
                cache_info = trials_service.get_cache_info()
                assert cache_info is not None
                assert cache_info["hits"] >= 1
                
                # Clear cache
                trials_service.clear_cache()
                cache_info_after_clear = trials_service.get_cache_info()
                assert cache_info_after_clear["hits"] == 0
                
                trials_service.close()