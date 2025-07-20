"""
Tests for the UnifiedHttpClient supporting both sync and async modes.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import requests
import requests.exceptions

from utils.http_client import (
    HttpResponse,
    UnifiedHttpClient,
    create_anthropic_client,
    create_clinicaltrials_client,
)


class TestHttpResponse:
    """Test the HttpResponse wrapper class."""

    def test_requests_response_wrapper(self):
        """Test HttpResponse with requests.Response."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"test": "data"}'
        mock_response.json.return_value = {"test": "data"}

        wrapped = HttpResponse(mock_response)

        assert wrapped.status_code == 200
        assert wrapped.headers == {"Content-Type": "application/json"}
        assert wrapped.text == '{"test": "data"}'
        assert wrapped.json() == {"test": "data"}

        wrapped.raise_for_status()
        mock_response.raise_for_status.assert_called_once()

    def test_httpx_response_wrapper(self):
        """Test HttpResponse with httpx.Response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = '{"test": "data"}'
        mock_response.json.return_value = {"test": "data"}

        wrapped = HttpResponse(mock_response)

        assert wrapped.status_code == 200
        assert wrapped.headers == {"Content-Type": "application/json"}
        assert wrapped.text == '{"test": "data"}'
        assert wrapped.json() == {"test": "data"}

        wrapped.raise_for_status()
        mock_response.raise_for_status.assert_called_once()


class TestUnifiedHttpClient:
    """Test the UnifiedHttpClient class."""

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_client_initialization(self, async_mode):
        """Test client initialization in both modes."""
        client = UnifiedHttpClient(
            async_mode=async_mode,
            service_name="test_service",
            base_url="https://api.example.com",
            headers={"Custom-Header": "value"}
        )

        assert client.async_mode == async_mode
        assert client.service_name == "test_service"
        assert client.base_url == "https://api.example.com"
        assert "Custom-Header" in client.default_headers
        assert client.default_headers["Custom-Header"] == "value"
        assert "Accept" in client.default_headers
        assert "User-Agent" in client.default_headers

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_timeout_configuration(self, async_mode):
        """Test timeout configuration for both modes."""
        timeout_config = {"connect": 5.0, "read": 30.0} if async_mode else {"timeout": 10.0}

        client = UnifiedHttpClient(
            async_mode=async_mode,
            timeout_config=timeout_config
        )

        if async_mode:
            assert client.timeout_config["connect"] == 5.0
            assert client.timeout_config["read"] == 30.0
        else:
            assert client.timeout_config["timeout"] == 10.0

    @patch('requests.Session')
    def test_sync_client_setup(self, mock_session_class):
        """Test sync client setup."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        client = UnifiedHttpClient(async_mode=False, service_name="test")

        assert client._session == mock_session
        mock_session.headers.update.assert_called_once()
        assert client._sync_timeout == client.timeout_config["timeout"]

    @patch('httpx.AsyncClient')
    def test_async_client_setup(self, mock_client_class):
        """Test async client setup."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        client = UnifiedHttpClient(async_mode=True, service_name="test")

        assert client._client == mock_client
        mock_client_class.assert_called_once()
        call_args = mock_client_class.call_args[1]
        assert "timeout" in call_args
        assert "limits" in call_args
        assert "headers" in call_args

    @patch('requests.Session.request')
    @patch('utils.metrics.increment')
    @patch('utils.metrics.histogram')
    @patch('utils.metrics.gauge')
    def test_sync_request_success(self, mock_gauge, mock_histogram, mock_increment, mock_request):
        """Test successful sync request."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_request.return_value = mock_response

        client = UnifiedHttpClient(async_mode=False, service_name="test")

        # Mock the decorators to avoid circuit breaker and retry logic in tests
        with patch('utils.http_client.exponential_backoff_retry') as mock_retry, \
             patch('utils.http_client.circuit_breaker') as mock_cb:

            mock_retry.return_value = lambda f: f
            mock_cb.return_value = lambda f: f

            response = client.get("https://api.example.com/test")

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        mock_request.assert_called_once()
        mock_increment.assert_called()
        mock_histogram.assert_called()
        mock_gauge.assert_called()

    @patch('httpx.AsyncClient.request')
    @patch('utils.metrics.increment')
    @patch('utils.metrics.histogram')
    @patch('utils.metrics.gauge')
    @pytest.mark.asyncio
    async def test_async_request_success(self, mock_gauge, mock_histogram, mock_increment, mock_request):
        """Test successful async request."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_request.return_value = mock_response

        client = UnifiedHttpClient(async_mode=True, service_name="test")

        # Mock the decorators to avoid circuit breaker and retry logic in tests
        with patch('utils.http_client.async_exponential_backoff_retry') as mock_retry, \
             patch('utils.http_client.async_circuit_breaker') as mock_cb:

            mock_retry.return_value = lambda f: f
            mock_cb.return_value = lambda f: f

            response = await client.aget("https://api.example.com/test")

        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        mock_request.assert_called_once()
        mock_increment.assert_called()
        mock_histogram.assert_called()
        mock_gauge.assert_called()

    @patch('requests.Session.request')
    @patch('utils.metrics.increment')
    def test_sync_request_error(self, mock_increment, mock_request):
        """Test sync request error handling."""
        mock_request.side_effect = requests.exceptions.Timeout("Request timeout")

        client = UnifiedHttpClient(async_mode=False, service_name="test")

        # Mock the decorators to avoid retry logic in tests
        with patch('utils.http_client.exponential_backoff_retry') as mock_retry, \
             patch('utils.http_client.circuit_breaker') as mock_cb:

            mock_retry.return_value = lambda f: f
            mock_cb.return_value = lambda f: f

            with pytest.raises(requests.exceptions.Timeout):
                client.get("https://api.example.com/test")

        mock_increment.assert_called_with("http_errors_total", tags={
            "service": "test",
            "method": "GET",
            "error_type": "Timeout"
        })

    @patch('httpx.AsyncClient.request')
    @patch('utils.metrics.increment')
    @pytest.mark.asyncio
    async def test_async_request_error(self, mock_increment, mock_request):
        """Test async request error handling."""
        mock_request.side_effect = httpx.TimeoutException("Request timeout")

        client = UnifiedHttpClient(async_mode=True, service_name="test")

        # Mock the decorators to avoid retry logic in tests
        with patch('utils.http_client.async_exponential_backoff_retry') as mock_retry, \
             patch('utils.http_client.async_circuit_breaker') as mock_cb:

            mock_retry.return_value = lambda f: f
            mock_cb.return_value = lambda f: f

            with pytest.raises(httpx.TimeoutException):
                await client.aget("https://api.example.com/test")

        mock_increment.assert_called_with("http_errors_total", tags={
            "service": "test",
            "method": "GET",
            "error_type": "TimeoutException"
        })

    def test_sync_fallback_warning(self):
        """Test sync fallback when async client is used outside event loop."""
        client = UnifiedHttpClient(async_mode=True, service_name="test")

        with patch('requests.Session') as mock_session_class, \
             patch('warnings.warn') as mock_warn:

            mock_session = Mock()
            mock_session_class.return_value.__enter__.return_value = mock_session
            mock_response = Mock(spec=requests.Response)
            mock_response.status_code = 200
            mock_session.request.return_value = mock_response

            # This should trigger the sync fallback
            client.get("https://api.example.com/test")

            mock_warn.assert_called_once()
            assert "sync request() method in async context" in str(mock_warn.call_args[0][0])

    @patch('requests.Session.request')
    def test_convenience_methods_sync(self, mock_request):
        """Test convenience methods in sync mode."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = UnifiedHttpClient(async_mode=False, service_name="test")

        with patch('utils.http_client.exponential_backoff_retry') as mock_retry, \
             patch('utils.http_client.circuit_breaker') as mock_cb:

            mock_retry.return_value = lambda f: f
            mock_cb.return_value = lambda f: f

            # Test all convenience methods
            client.get("https://api.example.com/test")
            client.post("https://api.example.com/test", json={"data": "test"})
            client.put("https://api.example.com/test", json={"data": "test"})
            client.delete("https://api.example.com/test")

        assert mock_request.call_count == 4

        # Verify methods were called with correct HTTP verbs
        call_args_list = [call[1]["method"] for call in mock_request.call_args_list]
        assert "GET" in call_args_list
        assert "POST" in call_args_list
        assert "PUT" in call_args_list
        assert "DELETE" in call_args_list

    @patch('httpx.AsyncClient.request')
    @pytest.mark.asyncio
    async def test_convenience_methods_async(self, mock_request):
        """Test convenience methods in async mode."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = UnifiedHttpClient(async_mode=True, service_name="test")

        with patch('utils.http_client.async_exponential_backoff_retry') as mock_retry, \
             patch('utils.http_client.async_circuit_breaker') as mock_cb:

            mock_retry.return_value = lambda f: f
            mock_cb.return_value = lambda f: f

            # Test all async convenience methods
            await client.aget("https://api.example.com/test")
            await client.apost("https://api.example.com/test", json={"data": "test"})
            await client.aput("https://api.example.com/test", json={"data": "test"})
            await client.adelete("https://api.example.com/test")

        assert mock_request.call_count == 4

        # Verify methods were called with correct HTTP verbs
        call_args_list = [call[1]["method"] for call in mock_request.call_args_list]
        assert "GET" in call_args_list
        assert "POST" in call_args_list
        assert "PUT" in call_args_list
        assert "DELETE" in call_args_list

    def test_context_manager_sync(self):
        """Test context manager support for sync mode."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            with UnifiedHttpClient(async_mode=False, service_name="test") as client:
                assert client is not None

            # Should call close on session
            mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_async(self):
        """Test async context manager support."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with UnifiedHttpClient(async_mode=True, service_name="test") as client:
                assert client is not None

            # Should call aclose on client
            mock_client.aclose.assert_called_once()

    def test_mixed_mode_error(self):
        """Test error when using async method on sync client."""
        client = UnifiedHttpClient(async_mode=False, service_name="test")

        with pytest.raises(RuntimeError, match="Cannot use arequest\\(\\) when async_mode=False"):
            asyncio.run(client.arequest("GET", "https://api.example.com/test"))


class TestFactoryFunctions:
    """Test the factory functions for creating pre-configured clients."""

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_create_clinicaltrials_client(self, async_mode):
        """Test ClinicalTrials.gov client factory."""
        client = create_clinicaltrials_client(async_mode=async_mode)

        assert client.async_mode == async_mode
        assert client.service_name == "clinicaltrials"
        assert client.base_url == "https://clinicaltrials.gov/api/"
        assert client.default_headers["Accept"] == "application/json"

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_create_anthropic_client(self, async_mode):
        """Test Anthropic API client factory."""
        api_key = "test-api-key"
        client = create_anthropic_client(async_mode=async_mode, api_key=api_key)

        assert client.async_mode == async_mode
        assert client.service_name == "anthropic"
        assert client.base_url == "https://api.anthropic.com/"
        assert client.default_headers["content-type"] == "application/json"
        assert client.default_headers["anthropic-version"] == "2023-06-01"
        assert client.default_headers["x-api-key"] == api_key

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_create_anthropic_client_no_key(self, async_mode):
        """Test Anthropic API client factory without API key."""
        client = create_anthropic_client(async_mode=async_mode)

        assert "x-api-key" not in client.default_headers


class TestIntegration:
    """Integration tests for the UnifiedHttpClient."""

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_configuration_loading(self, async_mode):
        """Test that client loads configuration correctly."""
        with patch('clinicaltrials.config.get_global_config') as mock_config:
            mock_config.return_value = Mock(
                user_agent="Test Agent",
                clinicaltrials_timeout=15.0,
                max_retries=5
            )

            client = UnifiedHttpClient(async_mode=async_mode, service_name="test")

            assert "Test Agent" in client.default_headers["User-Agent"]
            if not async_mode:
                assert client.timeout_config["timeout"] == 15.0
            assert client.retry_config["max_retries"] == 5

    @pytest.mark.parametrize("async_mode", [False, True])
    def test_configuration_fallback(self, async_mode):
        """Test that client handles configuration loading errors."""
        with patch('clinicaltrials.config.get_global_config') as mock_config:
            mock_config.side_effect = ValueError("Config error")

            # Should not raise an exception
            client = UnifiedHttpClient(async_mode=async_mode, service_name="test")

            # Should use default user agent
            assert "UnifiedHttpClient" in client.default_headers["User-Agent"]
