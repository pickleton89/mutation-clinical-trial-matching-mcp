"""
Tests for circuit breaker functionality.
"""

import unittest
import time
from unittest.mock import Mock, patch
from threading import Thread
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.circuit_breaker import (
    CircuitBreaker, CircuitBreakerState, CircuitBreakerError,
    get_circuit_breaker, reset_all_circuit_breakers
)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_all_circuit_breakers()
        self.circuit_breaker = CircuitBreaker(
            name="test_cb",
            failure_threshold=3,
            recovery_timeout=1,
            success_threshold=2
        )
    
    def tearDown(self):
        """Clean up after tests."""
        reset_all_circuit_breakers()
    
    def test_initial_state(self):
        """Test that circuit breaker starts in CLOSED state."""
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.stats.failure_count, 0)
        self.assertEqual(self.circuit_breaker.stats.success_count, 0)
        self.assertEqual(self.circuit_breaker.stats.total_calls, 0)
    
    def test_successful_call(self):
        """Test successful function call through circuit breaker."""
        mock_func = Mock(return_value="success")
        
        result = self.circuit_breaker.call(mock_func, "arg1", kwarg1="value1")
        
        self.assertEqual(result, "success")
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
        self.assertEqual(self.circuit_breaker.stats.success_count, 1)
        self.assertEqual(self.circuit_breaker.stats.total_calls, 1)
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
    
    def test_failed_call(self):
        """Test failed function call through circuit breaker."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        with self.assertRaises(Exception):
            self.circuit_breaker.call(mock_func)
        
        self.assertEqual(self.circuit_breaker.stats.failure_count, 1)
        self.assertEqual(self.circuit_breaker.stats.total_calls, 1)
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
    
    def test_transition_to_open(self):
        """Test transition to OPEN state after failure threshold."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Execute enough failures to trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)
        self.assertEqual(self.circuit_breaker.stats.failure_count, 3)
    
    def test_open_state_rejects_calls(self):
        """Test that OPEN state rejects calls without executing function."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        # Reset mock to track new calls
        mock_func.reset_mock()
        
        # Try to call when OPEN - should raise CircuitBreakerError
        with self.assertRaises(CircuitBreakerError):
            self.circuit_breaker.call(mock_func)
        
        # Function should not have been called
        mock_func.assert_not_called()
        self.assertEqual(self.circuit_breaker.stats.total_calls, 4)  # 3 failures + 1 rejected
    
    def test_transition_to_half_open(self):
        """Test transition to HALF_OPEN state after recovery timeout."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Next call should transition to HALF_OPEN - reset mock to return success
        mock_func.side_effect = None
        mock_func.return_value = "success"
        result = self.circuit_breaker.call(mock_func)
        
        self.assertEqual(result, "success")
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.HALF_OPEN)
    
    def test_half_open_to_closed_transition(self):
        """Test transition from HALF_OPEN to CLOSED after successful calls."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Make successful calls to transition to CLOSED - reset mock
        mock_func.side_effect = None
        mock_func.return_value = "success"
        self.circuit_breaker.call(mock_func)  # First success in HALF_OPEN
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.HALF_OPEN)
        
        self.circuit_breaker.call(mock_func)  # Second success should close circuit
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.stats.failure_count, 0)  # Reset on close
    
    def test_half_open_to_open_transition(self):
        """Test transition from HALF_OPEN back to OPEN on failure."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        # Make one successful call to enter HALF_OPEN - reset mock
        mock_func.side_effect = None
        mock_func.return_value = "success"
        self.circuit_breaker.call(mock_func)
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.HALF_OPEN)
        
        # Fail again - should transition back to OPEN
        mock_func.side_effect = Exception("Test error")
        
        with self.assertRaises(Exception):
            self.circuit_breaker.call(mock_func)
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)
    
    def test_decorator_usage(self):
        """Test circuit breaker used as decorator."""
        @self.circuit_breaker
        def test_function(arg1, kwarg1=None):
            return f"result: {arg1}, {kwarg1}"
        
        result = test_function("test", kwarg1="value")
        self.assertEqual(result, "result: test, value")
        self.assertEqual(self.circuit_breaker.stats.success_count, 1)
    
    def test_circuit_breaker_error_details(self):
        """Test CircuitBreakerError contains proper details."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        # Try to call when OPEN
        try:
            self.circuit_breaker.call(mock_func)
            self.fail("Should have raised CircuitBreakerError")
        except CircuitBreakerError as e:
            self.assertEqual(e.name, "test_cb")
            self.assertEqual(e.failure_count, 3)
            self.assertIsNotNone(e.last_failure_time)
            self.assertIn("Circuit breaker 'test_cb' is OPEN", str(e))
    
    def test_reset_functionality(self):
        """Test circuit breaker reset functionality."""
        mock_func = Mock(side_effect=Exception("Test error"))
        
        # Trigger OPEN state
        for i in range(3):
            with self.assertRaises(Exception):
                self.circuit_breaker.call(mock_func)
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.OPEN)
        
        # Reset circuit breaker
        self.circuit_breaker.reset()
        
        self.assertEqual(self.circuit_breaker.state, CircuitBreakerState.CLOSED)
        self.assertEqual(self.circuit_breaker.stats.failure_count, 0)
        self.assertEqual(self.circuit_breaker.stats.success_count, 0)
        self.assertEqual(self.circuit_breaker.stats.total_calls, 0)
    
    def test_thread_safety(self):
        """Test circuit breaker thread safety."""
        mock_func = Mock(return_value="success")
        results = []
        
        def worker():
            try:
                result = self.circuit_breaker.call(mock_func)
                results.append(result)
            except Exception as e:
                results.append(f"error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All calls should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(all(result == "success" for result in results))
        self.assertEqual(self.circuit_breaker.stats.total_calls, 10)
        self.assertEqual(self.circuit_breaker.stats.success_count, 10)


class TestCircuitBreakerRegistry(unittest.TestCase):
    """Test circuit breaker registry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_all_circuit_breakers()
    
    def tearDown(self):
        """Clean up after tests."""
        reset_all_circuit_breakers()
    
    def test_get_circuit_breaker_creates_instance(self):
        """Test that get_circuit_breaker creates new instance."""
        cb = get_circuit_breaker("test_registry")
        
        self.assertIsInstance(cb, CircuitBreaker)
        self.assertEqual(cb.name, "test_registry")
        self.assertEqual(cb.failure_threshold, 5)  # Default value
    
    def test_get_circuit_breaker_returns_existing(self):
        """Test that get_circuit_breaker returns existing instance."""
        cb1 = get_circuit_breaker("test_registry")
        cb2 = get_circuit_breaker("test_registry")
        
        self.assertIs(cb1, cb2)
    
    def test_get_circuit_breaker_with_custom_params(self):
        """Test get_circuit_breaker with custom parameters."""
        cb = get_circuit_breaker(
            "test_custom",
            failure_threshold=10,
            recovery_timeout=30,
            success_threshold=3
        )
        
        self.assertEqual(cb.failure_threshold, 10)
        self.assertEqual(cb.recovery_timeout, 30)
        self.assertEqual(cb.success_threshold, 3)
    
    def test_circuit_breaker_decorator_function(self):
        """Test circuit_breaker decorator function."""
        from utils.circuit_breaker import circuit_breaker
        
        @circuit_breaker("test_decorator", failure_threshold=2)
        def test_function():
            return "success"
        
        result = test_function()
        self.assertEqual(result, "success")
        
        # Get the circuit breaker instance
        cb = get_circuit_breaker("test_decorator")
        self.assertEqual(cb.stats.success_count, 1)
        self.assertEqual(cb.failure_threshold, 2)
    
    @patch('utils.circuit_breaker._metrics_available', True)
    @patch('utils.circuit_breaker.increment')
    @patch('utils.circuit_breaker.gauge')
    def test_metrics_integration(self, mock_gauge, mock_increment):
        """Test that circuit breaker integrates with metrics system."""
        cb = CircuitBreaker("test_metrics")
        mock_func = Mock(return_value="success")
        
        # Make a successful call
        cb.call(mock_func)
        
        # Check that metrics were recorded
        mock_increment.assert_called()
        mock_gauge.assert_called()
        
        # Check specific metric calls
        increment_calls = [call[0] for call in mock_increment.call_args_list]
        self.assertIn(("circuit_breaker_total_calls",), increment_calls)
        self.assertIn(("circuit_breaker_success_calls",), increment_calls)


if __name__ == '__main__':
    unittest.main()