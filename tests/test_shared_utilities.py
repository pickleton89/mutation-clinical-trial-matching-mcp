"""
Tests for the shared utilities module.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
import requests
import requests.exceptions

from utils.shared import (
    SessionManager,
    extract_studies_from_response,
    get_service_config,
    map_http_exception_to_error_response,
    process_json_response,
    time_request,
    validate_llm_input,
    validate_mutation_input,
)


class TestValidationFunctions:
    """Test input validation functions."""

    def test_validate_mutation_input_valid(self):
        """Test valid mutation input."""
        result = validate_mutation_input("BRAF V600E", min_rank=1, max_rank=100)

        assert result["valid"] is True
        assert result["error"] is None
        assert result["mutation"] == "BRAF V600E"
        assert result["min_rank"] == 1
        assert result["max_rank"] == 100
        assert len(result["warnings"]) == 0

    def test_validate_mutation_input_empty_mutation(self):
        """Test empty mutation input."""
        with patch('utils.metrics.increment') as mock_increment:
            result = validate_mutation_input("")

            assert result["valid"] is False
            assert "non-empty string" in result["error"]
            mock_increment.assert_called_with("api_validation_errors", tags={"error_type": "invalid_mutation"})

    def test_validate_mutation_input_none_mutation(self):
        """Test None mutation input."""
        with patch('utils.metrics.increment') as mock_increment:
            result = validate_mutation_input(None)  # type: ignore[arg-type]

            assert result["valid"] is False
            assert "non-empty string" in result["error"]
            mock_increment.assert_called_with("api_validation_errors", tags={"error_type": "invalid_mutation"})

    def test_validate_mutation_input_invalid_min_rank(self):
        """Test invalid min_rank correction."""
        with patch('utils.metrics.increment') as mock_increment:
            result = validate_mutation_input("BRAF V600E", min_rank=0)

            assert result["valid"] is True
            assert result["min_rank"] == 1
            assert "Invalid min_rank 0, corrected to 1" in result["warnings"]
            mock_increment.assert_called_with("api_validation_warnings", tags={"warning_type": "invalid_min_rank"})

    def test_validate_mutation_input_invalid_max_rank(self):
        """Test invalid max_rank correction."""
        with patch('utils.metrics.increment') as mock_increment:
            result = validate_mutation_input("BRAF V600E", max_rank=-5)

            assert result["valid"] is True
            assert result["max_rank"] is None
            assert "Invalid max_rank -5, corrected to unlimited" in result["warnings"]
            mock_increment.assert_called_with("api_validation_warnings", tags={"warning_type": "invalid_max_rank"})

    def test_validate_mutation_input_rank_order_correction(self):
        """Test rank order correction."""
        with patch('utils.metrics.increment') as mock_increment:
            result = validate_mutation_input("BRAF V600E", min_rank=100, max_rank=50)

            assert result["valid"] is True
            assert result["min_rank"] == 50
            assert result["max_rank"] == 100
            assert "min_rank and max_rank were swapped" in result["warnings"][0]
            mock_increment.assert_called_with("api_validation_warnings", tags={"warning_type": "rank_order_corrected"})

    def test_validate_mutation_input_whitespace_trimming(self):
        """Test whitespace trimming."""
        result = validate_mutation_input("  BRAF V600E  ")

        assert result["valid"] is True
        assert result["mutation"] == "BRAF V600E"

    def test_validate_llm_input_valid(self):
        """Test valid LLM input."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        result = validate_llm_input(messages, model="claude-3", max_tokens=1000, temperature=0.7)

        assert result["valid"] is True
        assert result["error"] is None
        assert result["messages"] == messages
        assert result["model"] == "claude-3"
        assert result["max_tokens"] == 1000
        assert result["temperature"] == 0.7
        assert len(result["warnings"]) == 0

    def test_validate_llm_input_empty_messages(self):
        """Test empty messages list."""
        with patch('utils.metrics.increment') as mock_increment:
            result = validate_llm_input([])

            assert result["valid"] is False
            assert "non-empty list" in result["error"]
            mock_increment.assert_called_with("llm_validation_errors", tags={"error_type": "invalid_messages"})

    def test_validate_llm_input_invalid_message_structure(self):
        """Test invalid message structure."""
        messages = [
            {"role": "user", "content": "Hello"},
            "invalid message"
        ]

        with patch('utils.metrics.increment') as mock_increment:
            result = validate_llm_input(messages)

            assert result["valid"] is False
            assert "Message 1 must be a dictionary" in result["error"]
            mock_increment.assert_called_with("llm_validation_errors", tags={"error_type": "invalid_message_structure"})

    def test_validate_llm_input_missing_fields(self):
        """Test missing required fields in message."""
        messages = [
            {"role": "user"},  # Missing content
        ]

        with patch('utils.metrics.increment') as mock_increment:
            result = validate_llm_input(messages)

            assert result["valid"] is False
            assert "must have 'role' and 'content' fields" in result["error"]
            mock_increment.assert_called_with("llm_validation_errors", tags={"error_type": "missing_message_fields"})

    def test_validate_llm_input_unusual_role(self):
        """Test unusual role warning."""
        messages = [
            {"role": "moderator", "content": "Hello"}
        ]

        with patch('utils.metrics.increment') as mock_increment:
            result = validate_llm_input(messages)

            assert result["valid"] is True
            assert "unusual role: moderator" in result["warnings"][0]
            mock_increment.assert_called_with("llm_validation_warnings", tags={"warning_type": "unusual_role"})

    def test_validate_llm_input_invalid_max_tokens(self):
        """Test invalid max_tokens correction."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch('utils.metrics.increment') as mock_increment:
            result = validate_llm_input(messages, max_tokens=-100)

            assert result["valid"] is True
            assert result["max_tokens"] == 1000
            assert "Invalid max_tokens -100, corrected to 1000" in result["warnings"]
            mock_increment.assert_called_with("llm_validation_warnings", tags={"warning_type": "invalid_max_tokens"})

    def test_validate_llm_input_invalid_temperature(self):
        """Test invalid temperature correction."""
        messages = [{"role": "user", "content": "Hello"}]

        with patch('utils.metrics.increment') as mock_increment:
            result = validate_llm_input(messages, temperature=5.0)

            assert result["valid"] is True
            assert result["temperature"] == 0.7
            assert "Invalid temperature 5.0, corrected to 0.7" in result["warnings"]
            mock_increment.assert_called_with("llm_validation_warnings", tags={"warning_type": "invalid_temperature"})


class TestErrorHandling:
    """Test error handling functions."""

    def test_map_requests_timeout_exception(self):
        """Test mapping requests timeout exception."""
        exception = requests.exceptions.Timeout("Request timeout")

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Request timed out"
            assert result["retry_after"] == 30
            assert result["error_type"] == "Timeout"
            assert result["studies"] == []
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "timeout"})

    def test_map_requests_connection_error(self):
        """Test mapping requests connection error."""
        exception = requests.exceptions.ConnectionError("Connection failed")

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Connection failed"
            assert result["retry_after"] == 60
            assert result["error_type"] == "ConnectionError"
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "connection_error"})

    def test_map_requests_http_error_429(self):
        """Test mapping requests HTTP 429 error."""
        mock_response = Mock()
        mock_response.status_code = 429
        exception = requests.exceptions.HTTPError("Rate limit")
        exception.response = mock_response

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Rate limit exceeded"
            assert result["retry_after"] == 60
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "rate_limit"})

    def test_map_requests_http_error_500(self):
        """Test mapping requests HTTP 500 error."""
        mock_response = Mock()
        mock_response.status_code = 500
        exception = requests.exceptions.HTTPError("Server error")
        exception.response = mock_response

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Server error"
            assert result["retry_after"] == 120
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "server_error"})

    def test_map_httpx_timeout_exception(self):
        """Test mapping httpx timeout exception."""
        exception = httpx.TimeoutException("Request timeout")

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Request timed out"
            assert result["retry_after"] == 30
            assert result["error_type"] == "TimeoutException"
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "timeout"})

    def test_map_httpx_connect_error(self):
        """Test mapping httpx connect error."""
        exception = httpx.ConnectError("Connection failed")

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Connection failed"
            assert result["retry_after"] == 60
            assert result["error_type"] == "ConnectError"
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "connection_error"})

    def test_map_httpx_http_status_error(self):
        """Test mapping httpx HTTP status error."""
        mock_response = Mock()
        mock_response.status_code = 429
        exception = httpx.HTTPStatusError("Rate limit", request=None, response=mock_response)

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Rate limit exceeded"
            assert result["retry_after"] == 60
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "rate_limit"})

    def test_map_json_error(self):
        """Test mapping JSON parsing error."""
        exception = ValueError("Invalid JSON format")

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Invalid JSON response"
            assert result["error_type"] == "ValueError"
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "json_error"})

    def test_map_unknown_exception(self):
        """Test mapping unknown exception."""
        exception = RuntimeError("Unknown error")

        with patch('utils.metrics.increment') as mock_increment:
            result = map_http_exception_to_error_response(exception, "test_service")

            assert result["error"] == "Request failed"
            assert result["error_type"] == "RuntimeError"
            assert result["error_details"] == "Unknown error"
            mock_increment.assert_called_with("api_errors", tags={"service": "test_service", "error_type": "unknown"})


class TestTimingDecorator:
    """Test request timing decorator."""

    @patch('utils.metrics.increment')
    @patch('utils.metrics.histogram')
    @patch('utils.metrics.gauge')
    def test_time_request_sync_success(self, mock_gauge, mock_histogram, mock_increment):
        """Test timing decorator for successful sync function."""
        @time_request("test_service", "test_operation")
        def test_function():
            time.sleep(0.01)  # Small delay for timing
            return "success"

        result = test_function()

        assert result == "success"
        mock_increment.assert_called_with("api_requests_total", tags={
            "service": "test_service",
            "operation": "test_operation",
            "status": "success"
        })
        mock_histogram.assert_called()
        mock_gauge.assert_called()

    @patch('utils.metrics.increment')
    @patch('utils.metrics.histogram')
    def test_time_request_sync_error(self, mock_histogram, mock_increment):
        """Test timing decorator for failed sync function."""
        @time_request("test_service", "test_operation")
        def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            test_function()

        mock_increment.assert_called_with("api_requests_total", tags={
            "service": "test_service",
            "operation": "test_operation",
            "status": "error"
        })
        mock_histogram.assert_called()

    @patch('utils.metrics.increment')
    @patch('utils.metrics.histogram')
    @patch('utils.metrics.gauge')
    @pytest.mark.asyncio
    async def test_time_request_async_success(self, mock_gauge, mock_histogram, mock_increment):
        """Test timing decorator for successful async function."""
        @time_request("test_service", "test_operation")
        async def test_function():
            await asyncio.sleep(0.01)  # Small delay for timing
            return "success"

        result = await test_function()

        assert result == "success"
        mock_increment.assert_called_with("api_requests_total", tags={
            "service": "test_service",
            "operation": "test_operation",
            "status": "success"
        })
        mock_histogram.assert_called()
        mock_gauge.assert_called()

    @patch('utils.metrics.increment')
    @patch('utils.metrics.histogram')
    @pytest.mark.asyncio
    async def test_time_request_async_error(self, mock_histogram, mock_increment):
        """Test timing decorator for failed async function."""
        @time_request("test_service", "test_operation")
        async def test_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await test_function()

        mock_increment.assert_called_with("api_requests_total", tags={
            "service": "test_service",
            "operation": "test_operation",
            "status": "error"
        })
        mock_histogram.assert_called()


class TestResponseProcessing:
    """Test response processing utilities."""

    def test_extract_studies_from_response_studies_key(self):
        """Test extracting studies from response with 'studies' key."""
        response_data = {
            "studies": [
                {"nct_id": "NCT12345", "title": "Study 1"},
                {"nct_id": "NCT67890", "title": "Study 2"}
            ]
        }

        with patch('utils.metrics.gauge') as mock_gauge:
            studies = extract_studies_from_response(response_data)

            assert len(studies) == 2
            assert studies[0]["nct_id"] == "NCT12345"
            assert studies[1]["nct_id"] == "NCT67890"
            mock_gauge.assert_called_with("api_studies_returned", 2, tags={"service": "clinicaltrials"})

    def test_extract_studies_from_response_study_key(self):
        """Test extracting studies from response with 'Study' key."""
        response_data = {
            "Study": [
                {"nct_id": "NCT12345", "title": "Study 1"}
            ]
        }

        with patch('utils.metrics.gauge') as mock_gauge:
            studies = extract_studies_from_response(response_data)

            assert len(studies) == 1
            assert studies[0]["nct_id"] == "NCT12345"
            mock_gauge.assert_called_with("api_studies_returned", 1, tags={"service": "clinicaltrials"})

    def test_extract_studies_from_response_single_study(self):
        """Test extracting single study (not in list)."""
        response_data = {
            "studies": {"nct_id": "NCT12345", "title": "Study 1"}
        }

        with patch('utils.metrics.gauge'):
            studies = extract_studies_from_response(response_data)

            assert len(studies) == 1
            assert studies[0]["nct_id"] == "NCT12345"

    def test_extract_studies_from_response_no_studies(self):
        """Test extracting from response with no studies."""
        response_data = {"other_data": "value"}

        with patch('utils.metrics.gauge') as mock_gauge:
            studies = extract_studies_from_response(response_data)

            assert len(studies) == 0
            mock_gauge.assert_called_with("api_studies_returned", 0, tags={"service": "clinicaltrials"})

    def test_extract_studies_from_response_error(self):
        """Test extracting studies with error."""
        response_data = None

        with patch('utils.metrics.increment') as mock_increment, \
             patch('utils.metrics.gauge'):

            studies = extract_studies_from_response(response_data)  # type: ignore[arg-type]

            assert len(studies) == 0
            mock_increment.assert_called_with("response_processing_errors", tags={"error_type": "studies_extraction"})

    def test_process_json_response_valid(self):
        """Test processing valid JSON response."""
        response_text = '{"success": true, "data": "test"}'

        with patch('utils.metrics.gauge') as mock_gauge:
            result = process_json_response(response_text, "test_service")

            assert result["success"] is True
            assert result["data"] == "test"
            mock_gauge.assert_called_with("api_response_size", len(response_text), tags={"service": "test_service"})

    def test_process_json_response_invalid(self):
        """Test processing invalid JSON response."""
        response_text = "invalid json"

        with patch('utils.metrics.increment') as mock_increment, \
             patch('utils.metrics.gauge'):

            result = process_json_response(response_text, "test_service")

            assert result["error"] == "Invalid JSON response"
            assert result["studies"] == []
            mock_increment.assert_called_with("response_processing_errors", tags={
                "service": "test_service",
                "error_type": "json_parsing"
            })

    def test_process_json_response_missing_fields(self):
        """Test processing JSON response with missing expected fields."""
        response_text = '{"data": "test"}'
        expected_fields = ["success", "message"]

        with patch('utils.metrics.increment') as mock_increment:
            result = process_json_response(response_text, "test_service", expected_fields)

            assert result["data"] == "test"
            mock_increment.assert_called_with("response_validation_warnings", tags={
                "service": "test_service",
                "warning_type": "missing_fields"
            })


class TestConfigurationHelpers:
    """Test configuration helper functions."""

    def test_get_service_config_basic(self):
        """Test basic service configuration retrieval."""
        config_dict = {
            "test_service": {
                "timeout": 15.0,
                "custom_option": "value"
            }
        }

        result = get_service_config("test_service", config_dict)

        assert result["timeout"] == 15.0
        assert result["custom_option"] == "value"
        assert result["max_retries"] == 3  # Default value
        assert result["circuit_breaker_threshold"] == 5  # Default value

    def test_get_service_config_clinicaltrials(self):
        """Test ClinicalTrials service configuration with defaults."""
        config_dict = {}

        result = get_service_config("clinicaltrials", config_dict)

        assert result["timeout"] == 10.0  # Service-specific default
        assert result["base_url"] == "https://clinicaltrials.gov/api/"
        assert result["max_retries"] == 3  # Common default

    def test_get_service_config_anthropic(self):
        """Test Anthropic service configuration with defaults."""
        config_dict = {}

        result = get_service_config("anthropic", config_dict)

        assert result["timeout"] == 60.0  # Service-specific default
        assert result["base_url"] == "https://api.anthropic.com/"
        assert result["model"] == "claude-3-5-sonnet-20241022"
        assert result["max_tokens"] == 1000

    def test_get_service_config_override(self):
        """Test service configuration with overrides."""
        config_dict = {
            "anthropic": {
                "timeout": 120.0,  # Override default
                "max_tokens": 2000  # Override default
            }
        }

        result = get_service_config("anthropic", config_dict)

        assert result["timeout"] == 120.0  # Overridden
        assert result["max_tokens"] == 2000  # Overridden
        assert result["model"] == "claude-3-5-sonnet-20241022"  # Still default


class TestSessionManager:
    """Test the SessionManager class."""

    def test_session_manager_sync(self):
        """Test SessionManager in sync mode."""
        manager = SessionManager(async_mode=False)

        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            session = manager.get_session("test_service", headers={"Custom": "Header"})

            assert session == mock_session
            mock_session.headers.update.assert_called_with({"Custom": "Header"})

    def test_session_manager_async(self):
        """Test SessionManager in async mode."""
        manager = SessionManager(async_mode=True)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            client = manager.get_session("test_service",
                                       headers={"Custom": "Header"},
                                       timeout=30.0,
                                       base_url="https://api.example.com")

            assert client == mock_client
            mock_client_class.assert_called_with(
                headers={"Custom": "Header"},
                timeout=30.0,
                base_url="https://api.example.com"
            )

    def test_session_manager_reuse(self):
        """Test that SessionManager reuses sessions."""
        manager = SessionManager(async_mode=False)

        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            session1 = manager.get_session("test_service")
            session2 = manager.get_session("test_service")

            assert session1 is session2
            assert mock_session_class.call_count == 1

    def test_session_manager_close_all_sync(self):
        """Test closing all sync sessions."""
        manager = SessionManager(async_mode=False)

        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            manager.get_session("test_service")
            manager.close_all()

            mock_session.close.assert_called_once()
            assert len(manager._sessions) == 0

    @pytest.mark.asyncio
    async def test_session_manager_close_all_async(self):
        """Test closing all async sessions."""
        manager = SessionManager(async_mode=True)

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = Mock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            manager.get_session("test_service")
            await manager.aclose_all()

            mock_client.aclose.assert_called_once()
            assert len(manager._sessions) == 0
