"""
Unit tests for clinicaltrials.query
"""

import unittest
from unittest.mock import Mock, patch

import requests
from requests import exceptions as requests_exceptions

from clinicaltrials.config import reset_global_config
from clinicaltrials.query import clear_cache, query_clinical_trials


class TestQueryClinicalTrials(unittest.TestCase):
    """Test the query_clinical_trials function."""

    def setUp(self):
        """Clear cache and reset config before each test."""
        clear_cache()
        reset_global_config()

        # Mock environment variables for testing
        self.env_patcher = patch.dict('os.environ', {
            'ANTHROPIC_API_KEY': 'test-key-123'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after each test."""
        self.env_patcher.stop()

    @patch('clinicaltrials.query._session.get')
    def test_successful_query(self, mock_get):
        """Test successful API query with valid response."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "studies": [
                {"protocolSection": {"identificationModule": {"briefTitle": "Test Trial 1"}}},
                {"protocolSection": {"identificationModule": {"briefTitle": "Test Trial 2"}}}
            ]
        }
        mock_get.return_value = mock_response

        # Call the function
        result = query_clinical_trials("BRAF V600E")

        # Verify results
        self.assertIsInstance(result, dict)
        self.assertIn("studies", result)
        self.assertEqual(len(result["studies"]), 2)
        self.assertEqual(result["studies"][0]["protocolSection"]["identificationModule"]["briefTitle"], "Test Trial 1")

        # Verify API call was made correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn("https://clinicaltrials.gov/api/v2/studies", call_args[0][0])
        self.assertEqual(call_args[1]["params"]["query.term"], "BRAF V600E")
        self.assertEqual(call_args[1]["params"]["pageSize"], 10)
        self.assertEqual(call_args[1]["timeout"], 10)

    @patch('clinicaltrials.query._session.get')
    def test_empty_mutation_error(self, mock_get):
        """Test error handling for empty mutation string."""
        result = query_clinical_trials("")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Mutation must be a non-empty string")
        self.assertEqual(result["studies"], [])

        # Verify no API call was made
        mock_get.assert_not_called()

    @patch('clinicaltrials.query._session.get')
    def test_none_mutation_error(self, mock_get):
        """Test error handling for None mutation."""
        result = query_clinical_trials(None)

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Mutation must be a non-empty string")
        self.assertEqual(result["studies"], [])

        # Verify no API call was made
        mock_get.assert_not_called()

    @patch('clinicaltrials.query._session.get')
    def test_whitespace_mutation_error(self, mock_get):
        """Test error handling for whitespace-only mutation."""
        result = query_clinical_trials("   ")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Mutation must be a non-empty string")
        self.assertEqual(result["studies"], [])

        # Verify no API call was made
        mock_get.assert_not_called()

    @patch('clinicaltrials.query._session.get')
    def test_invalid_min_rank_parameter(self, mock_get):
        """Test parameter validation and correction for min_rank."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"studies": []}
        mock_get.return_value = mock_response

        # Test with invalid min_rank
        result = query_clinical_trials("BRAF V600E", min_rank=0)

        # Verify the function still works (min_rank corrected to 1)
        self.assertIsInstance(result, dict)
        self.assertIn("studies", result)

        # Verify API call was made with corrected pageSize
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["pageSize"], 10)  # Should be 10 (1 to 10)

    @patch('clinicaltrials.query._session.get')
    def test_invalid_max_rank_parameter(self, mock_get):
        """Test parameter validation and correction for max_rank."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"studies": []}
        mock_get.return_value = mock_response

        # Test with invalid max_rank
        result = query_clinical_trials("BRAF V600E", min_rank=5, max_rank=3)

        # Verify the function still works (max_rank corrected)
        self.assertIsInstance(result, dict)
        self.assertIn("studies", result)

        # Verify API call was made with corrected pageSize
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["pageSize"], 10)  # Should be 10 (5 to 14)

    @patch('clinicaltrials.query._session.get')
    def test_api_error_status_code(self, mock_get):
        """Test handling of non-200 API response."""
        # Mock API error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_get.return_value = mock_response

        # Call the function
        result = query_clinical_trials("BRAF V600E")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("API Error (Status 400)", result["error"])
        self.assertEqual(result["studies"], [])

    @patch('clinicaltrials.query._session.get')
    def test_json_parsing_error(self, mock_get):
        """Test handling of invalid JSON response."""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not valid JSON"
        mock_get.return_value = mock_response

        # Call the function
        result = query_clinical_trials("BRAF V600E")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Failed to parse API response", result["error"])
        self.assertEqual(result["studies"], [])

    @patch('clinicaltrials.query._session.get')
    def test_timeout_error(self, mock_get):
        """Test handling of request timeout."""
        # Mock timeout error
        mock_get.side_effect = requests_exceptions.Timeout()

        # Call the function
        result = query_clinical_trials("BRAF V600E")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("timed out", result["error"])
        self.assertEqual(result["studies"], [])

    @patch('clinicaltrials.query._session.get')
    def test_connection_error(self, mock_get):
        """Test handling of connection error."""
        # Mock connection error
        mock_get.side_effect = requests_exceptions.ConnectionError("Connection failed")

        # Call the function
        result = query_clinical_trials("BRAF V600E")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Failed to connect", result["error"])
        self.assertEqual(result["studies"], [])

    @patch('clinicaltrials.query._session.get')
    def test_general_request_error(self, mock_get):
        """Test handling of general request error."""
        # Mock general request error
        mock_get.side_effect = requests.RequestException("Request failed")

        # Call the function
        result = query_clinical_trials("BRAF V600E")

        # Verify error response
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        self.assertIn("Error querying clinicaltrials.gov", result["error"])
        self.assertEqual(result["studies"], [])

    @patch('clinicaltrials.query._session.get')
    def test_custom_timeout_parameter(self, mock_get):
        """Test custom timeout parameter is passed correctly."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"studies": []}
        mock_get.return_value = mock_response

        # Call with custom timeout
        query_clinical_trials("BRAF V600E", timeout=30)

        # Verify timeout parameter was passed
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["timeout"], 30)

    @patch('clinicaltrials.query._session.get')
    def test_custom_rank_range(self, mock_get):
        """Test custom min_rank and max_rank parameters."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"studies": []}
        mock_get.return_value = mock_response

        # Call with custom rank range
        query_clinical_trials("BRAF V600E", min_rank=5, max_rank=15)

        # Verify pageSize parameter was calculated correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["pageSize"], 11)  # 15 - 5 + 1 = 11


if __name__ == '__main__':
    unittest.main()
