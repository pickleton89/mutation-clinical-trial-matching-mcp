"""
Unit tests for utils.retry module
"""

import unittest
from unittest.mock import Mock, call, patch

from requests import exceptions as requests_exceptions

from utils.retry import _calculate_delay, exponential_backoff_retry, get_retry_stats


class TestExponentialBackoffRetry(unittest.TestCase):
    """Test the exponential backoff retry decorator."""

    def test_successful_function_no_retry(self):
        """Test that successful functions don't retry."""
        @exponential_backoff_retry(max_retries=3)
        def successful_function():
            return "success"

        result = successful_function()
        self.assertEqual(result, "success")

    def test_retry_on_exception(self):
        """Test retry behavior on retriable exceptions."""
        call_count = 0

        @exponential_backoff_retry(max_retries=2, initial_delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests_exceptions.ConnectionError("Connection failed")
            return "success after retries"

        result = failing_function()
        self.assertEqual(result, "success after retries")
        self.assertEqual(call_count, 3)

    def test_retry_exhausted(self):
        """Test that function fails after exhausting retries."""
        call_count = 0

        @exponential_backoff_retry(max_retries=2, initial_delay=0.01)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise requests_exceptions.ConnectionError("Always fails")

        with self.assertRaises(requests_exceptions.ConnectionError):
            always_failing_function()

        self.assertEqual(call_count, 3)  # Initial call + 2 retries

    def test_non_retriable_exception(self):
        """Test that non-retriable exceptions are not retried."""
        call_count = 0

        @exponential_backoff_retry(max_retries=3, initial_delay=0.01)
        def non_retriable_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retriable error")

        with self.assertRaises(ValueError):
            non_retriable_function()

        self.assertEqual(call_count, 1)  # Only initial call

    def test_retry_on_status_codes(self):
        """Test retry behavior on specific HTTP status codes."""
        call_count = 0

        @exponential_backoff_retry(max_retries=2, initial_delay=0.01, retry_on_status_codes=(500, 502))
        def status_code_function():
            nonlocal call_count
            call_count += 1

            response = Mock()
            if call_count < 3:
                response.status_code = 500
            else:
                response.status_code = 200
            return response

        result = status_code_function()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(call_count, 3)

    def test_custom_retriable_exceptions(self):
        """Test custom retriable exceptions."""
        call_count = 0

        @exponential_backoff_retry(
            max_retries=2,
            initial_delay=0.01,
            retriable_exceptions=(ValueError,)
        )
        def custom_exception_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Custom retriable error")
            return "success"

        result = custom_exception_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_calculate_delay(self):
        """Test delay calculation with exponential backoff."""
        # Test basic exponential backoff
        delay1 = _calculate_delay(0, 1.0, 2.0, 60.0, False)
        delay2 = _calculate_delay(1, 1.0, 2.0, 60.0, False)
        delay3 = _calculate_delay(2, 1.0, 2.0, 60.0, False)

        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 4.0)

        # Test max delay cap
        delay_capped = _calculate_delay(10, 1.0, 2.0, 5.0, False)
        self.assertEqual(delay_capped, 5.0)

        # Test jitter adds randomness
        delay_jitter1 = _calculate_delay(1, 1.0, 2.0, 60.0, True)
        delay_jitter2 = _calculate_delay(1, 1.0, 2.0, 60.0, True)

        # Should be around 2.0 but with some variation
        self.assertGreater(delay_jitter1, 1.0)
        self.assertLess(delay_jitter1, 3.0)

        # With jitter, two calls should likely give different results
        # (this could rarely fail due to randomness, but very unlikely)
        self.assertNotEqual(delay_jitter1, delay_jitter2)

    @patch('time.sleep')
    def test_retry_timing(self, mock_sleep):
        """Test that retry timing works correctly."""
        call_count = 0

        @exponential_backoff_retry(max_retries=2, initial_delay=1.0, backoff_factor=2.0, jitter=False)
        def timing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise requests_exceptions.ConnectionError("Timing test")
            return "success"

        result = timing_function()
        self.assertEqual(result, "success")

        # Should have slept twice: 1.0s and 2.0s
        expected_calls = [call(1.0), call(2.0)]
        mock_sleep.assert_has_calls(expected_calls)


class TestRetryStats(unittest.TestCase):
    """Test retry statistics functionality."""

    def test_get_retry_stats_no_stats(self):
        """Test getting stats for function without retry stats."""
        def regular_function():
            return "test"

        stats = get_retry_stats(regular_function)
        expected = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_retries": 0,
            "average_retries": 0.0
        }
        self.assertEqual(stats, expected)


if __name__ == '__main__':
    unittest.main()
