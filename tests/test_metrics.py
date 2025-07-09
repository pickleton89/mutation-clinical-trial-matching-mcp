"""
Tests for metrics collection system.
"""

import unittest
import time
from unittest.mock import Mock, patch
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.metrics import (
    MetricsCollector, MetricPoint, MetricType, HistogramStats,
    Timer, increment, gauge, histogram, timer, get_metrics,
    export_prometheus, export_json, reset_metrics_collector, timed
)


class TestMetricsCollector(unittest.TestCase):
    """Test metrics collector functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_metrics_collector()
        self.collector = MetricsCollector()
    
    def tearDown(self):
        """Clean up after tests."""
        reset_metrics_collector()
    
    def test_increment_counter(self):
        """Test incrementing counter metrics."""
        self.collector.increment("test_counter", 5.0)
        self.collector.increment("test_counter", 3.0)
        
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics["counters"]["test_counter"], 8.0)
    
    def test_increment_with_tags(self):
        """Test incrementing counter with tags."""
        self.collector.increment("api_calls", 1.0, tags={"endpoint": "trials"})
        self.collector.increment("api_calls", 1.0, tags={"endpoint": "health"})
        self.collector.increment("api_calls", 2.0, tags={"endpoint": "trials"})
        
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics["counters"]["api_calls[endpoint=trials]"], 3.0)
        self.assertEqual(metrics["counters"]["api_calls[endpoint=health]"], 1.0)
    
    def test_gauge_metric(self):
        """Test gauge metrics."""
        self.collector.gauge("memory_usage", 1024.5)
        self.collector.gauge("memory_usage", 2048.7)  # Overwrite previous value
        
        metrics = self.collector.get_metrics()
        self.assertEqual(metrics["gauges"]["memory_usage"], 2048.7)
    
    def test_histogram_metric(self):
        """Test histogram metrics."""
        values = [100, 200, 300, 150, 250]
        for value in values:
            self.collector.histogram("response_time", value)
        
        metrics = self.collector.get_metrics()
        hist = metrics["histograms"]["response_time"]
        
        self.assertEqual(hist["count"], 5)
        self.assertEqual(hist["sum"], 1000)
        self.assertEqual(hist["min"], 100)
        self.assertEqual(hist["max"], 300)
        self.assertEqual(hist["avg"], 200)
        self.assertEqual(hist["p50"], 200)  # Median
    
    def test_timer_context_manager(self):
        """Test timer context manager."""
        with self.collector.timer("test_operation"):
            time.sleep(0.1)
        
        metrics = self.collector.get_metrics()
        
        # Check that duration was recorded
        self.assertIn("test_operation_duration", metrics["histograms"])
        duration_hist = metrics["histograms"]["test_operation_duration"]
        self.assertEqual(duration_hist["count"], 1)
        self.assertGreater(duration_hist["sum"], 0.05)  # At least 50ms
        
        # Check that success was recorded
        self.assertEqual(metrics["counters"]["test_operation_success"], 1.0)
    
    def test_timer_with_exception(self):
        """Test timer context manager with exception."""
        try:
            with self.collector.timer("failing_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass
        
        metrics = self.collector.get_metrics()
        
        # Check that error was recorded
        self.assertEqual(metrics["counters"]["failing_operation_errors"], 1.0)
        
        # Duration should still be recorded
        self.assertIn("failing_operation_duration", metrics["histograms"])
    
    def test_timer_with_tags(self):
        """Test timer with tags."""
        with self.collector.timer("api_request", tags={"method": "GET"}):
            time.sleep(0.05)
        
        metrics = self.collector.get_metrics()
        
        # Check tagged metrics
        self.assertIn("api_request_duration[method=GET]", metrics["histograms"])
        self.assertEqual(metrics["counters"]["api_request_success[method=GET]"], 1.0)
    
    def test_recent_points(self):
        """Test getting recent metric points."""
        self.collector.increment("test", 1.0)
        self.collector.gauge("test_gauge", 100.0)
        self.collector.histogram("test_hist", 50.0)
        
        points = self.collector.get_recent_points(limit=10)
        
        self.assertEqual(len(points), 3)
        self.assertTrue(all(isinstance(p, MetricPoint) for p in points))
        
        # Check metric types
        types = [p.metric_type for p in points]
        self.assertIn(MetricType.COUNTER, types)
        self.assertIn(MetricType.GAUGE, types)
        self.assertIn(MetricType.HISTOGRAM, types)
    
    def test_reset_metrics(self):
        """Test resetting metrics collector."""
        self.collector.increment("test", 1.0)
        self.collector.gauge("test_gauge", 100.0)
        
        metrics_before = self.collector.get_metrics()
        self.assertTrue(len(metrics_before["counters"]) > 0)
        
        self.collector.reset()
        
        metrics_after = self.collector.get_metrics()
        self.assertEqual(len(metrics_after["counters"]), 0)
        self.assertEqual(len(metrics_after["gauges"]), 0)
        self.assertEqual(len(metrics_after["histograms"]), 0)
    
    def test_prometheus_export(self):
        """Test Prometheus format export."""
        self.collector.increment("http_requests_total", 10.0, tags={"method": "GET", "status": "200"})
        self.collector.gauge("memory_usage_bytes", 1024.5)
        self.collector.histogram("response_time_seconds", 0.1)
        
        prometheus_output = self.collector.export_prometheus()
        
        # Check that output contains expected elements
        self.assertIn("# TYPE http_requests_total counter", prometheus_output)
        self.assertIn("http_requests_total{method=\"GET\",status=\"200\"} 10.0", prometheus_output)
        self.assertIn("# TYPE memory_usage_bytes gauge", prometheus_output)
        self.assertIn("memory_usage_bytes 1024.5", prometheus_output)
        self.assertIn("# TYPE response_time_seconds histogram", prometheus_output)
        self.assertIn("response_time_seconds_count 1", prometheus_output)
    
    def test_json_export(self):
        """Test JSON format export."""
        self.collector.increment("test_counter", 5.0)
        self.collector.gauge("test_gauge", 100.0)
        
        json_output = self.collector.export_json()
        
        # Parse JSON and check contents
        import json
        data = json.loads(json_output)
        
        self.assertIn("counters", data)
        self.assertIn("gauges", data)
        self.assertIn("histograms", data)
        self.assertIn("timestamp", data)
        
        self.assertEqual(data["counters"]["test_counter"], 5.0)
        self.assertEqual(data["gauges"]["test_gauge"], 100.0)
    
    def test_max_points_limit(self):
        """Test that collector respects max_points limit."""
        collector = MetricsCollector(max_points=5)
        
        # Add more points than the limit
        for i in range(10):
            collector.increment(f"test_{i}", 1.0)
        
        points = collector.get_recent_points(limit=20)
        
        # Should only have 5 points (the limit)
        self.assertEqual(len(points), 5)
        
        # Should have the most recent points
        names = [p.name for p in points]
        self.assertIn("test_9", names)
        self.assertIn("test_8", names)
        self.assertIn("test_7", names)
        self.assertIn("test_6", names)
        self.assertIn("test_5", names)


class TestHistogramStats(unittest.TestCase):
    """Test histogram statistics calculations."""
    
    def test_histogram_stats_update(self):
        """Test histogram stats update functionality."""
        stats = HistogramStats()
        
        values = [10, 20, 30, 40, 50]
        for value in values:
            stats.update(value)
        
        self.assertEqual(stats.count, 5)
        self.assertEqual(stats.sum, 150)
        self.assertEqual(stats.min, 10)
        self.assertEqual(stats.max, 50)
    
    def test_histogram_single_value(self):
        """Test histogram with single value."""
        stats = HistogramStats()
        stats.update(42.5)
        
        self.assertEqual(stats.count, 1)
        self.assertEqual(stats.sum, 42.5)
        self.assertEqual(stats.min, 42.5)
        self.assertEqual(stats.max, 42.5)


class TestGlobalMetricsAPI(unittest.TestCase):
    """Test global metrics API functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_metrics_collector()
    
    def tearDown(self):
        """Clean up after tests."""
        reset_metrics_collector()
    
    def test_global_increment(self):
        """Test global increment function."""
        increment("global_counter", 10.0)
        increment("global_counter", 5.0)
        
        metrics = get_metrics()
        self.assertEqual(metrics["counters"]["global_counter"], 15.0)
    
    def test_global_gauge(self):
        """Test global gauge function."""
        gauge("global_gauge", 123.45)
        
        metrics = get_metrics()
        self.assertEqual(metrics["gauges"]["global_gauge"], 123.45)
    
    def test_global_histogram(self):
        """Test global histogram function."""
        histogram("global_histogram", 100.0)
        histogram("global_histogram", 200.0)
        
        metrics = get_metrics()
        hist = metrics["histograms"]["global_histogram"]
        
        self.assertEqual(hist["count"], 2)
        self.assertEqual(hist["sum"], 300.0)
        self.assertEqual(hist["avg"], 150.0)
    
    def test_global_timer(self):
        """Test global timer function."""
        with timer("global_timer"):
            time.sleep(0.05)
        
        metrics = get_metrics()
        
        self.assertIn("global_timer_duration", metrics["histograms"])
        self.assertEqual(metrics["counters"]["global_timer_success"], 1.0)
    
    def test_global_exports(self):
        """Test global export functions."""
        increment("test_metric", 1.0)
        
        prometheus_output = export_prometheus()
        json_output = export_json()
        
        self.assertIn("test_metric", prometheus_output)
        self.assertIn("test_metric", json_output)
    
    def test_timed_decorator(self):
        """Test timed decorator."""
        @timed("decorated_function")
        def slow_function():
            time.sleep(0.05)
            return "result"
        
        result = slow_function()
        
        self.assertEqual(result, "result")
        
        metrics = get_metrics()
        self.assertIn("decorated_function_duration", metrics["histograms"])
        self.assertEqual(metrics["counters"]["decorated_function_success"], 1.0)
    
    def test_timed_decorator_with_exception(self):
        """Test timed decorator with exception."""
        @timed("failing_function")
        def failing_function():
            raise ValueError("Test error")
        
        with self.assertRaises(ValueError):
            failing_function()
        
        metrics = get_metrics()
        self.assertIn("failing_function_duration", metrics["histograms"])
        self.assertEqual(metrics["counters"]["failing_function_errors"], 1.0)
    
    def test_timed_decorator_with_custom_name(self):
        """Test timed decorator with custom name."""
        @timed("custom_metric_name", tags={"version": "1.0"})
        def test_function():
            return "success"
        
        result = test_function()
        
        self.assertEqual(result, "success")
        
        metrics = get_metrics()
        self.assertIn("custom_metric_name_duration[version=1.0]", metrics["histograms"])
        self.assertEqual(metrics["counters"]["custom_metric_name_success[version=1.0]"], 1.0)


class TestTimer(unittest.TestCase):
    """Test Timer class functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        reset_metrics_collector()
        self.collector = MetricsCollector()
    
    def test_timer_context_manager(self):
        """Test Timer as context manager."""
        timer_obj = Timer(self.collector, "test_timer")
        
        with timer_obj:
            time.sleep(0.05)
        
        metrics = self.collector.get_metrics()
        
        # Check that metrics were recorded
        self.assertIn("test_timer_duration", metrics["histograms"])
        self.assertEqual(metrics["counters"]["test_timer_success"], 1.0)
    
    def test_timer_with_exception(self):
        """Test Timer with exception."""
        timer_obj = Timer(self.collector, "failing_timer")
        
        try:
            with timer_obj:
                raise RuntimeError("Test error")
        except RuntimeError:
            pass
        
        metrics = self.collector.get_metrics()
        
        # Check that error was recorded
        self.assertEqual(metrics["counters"]["failing_timer_errors"], 1.0)
        
        # Duration should still be recorded
        self.assertIn("failing_timer_duration", metrics["histograms"])
    
    def test_timer_with_tags(self):
        """Test Timer with tags."""
        timer_obj = Timer(self.collector, "tagged_timer", tags={"env": "test"})
        
        with timer_obj:
            time.sleep(0.01)
        
        metrics = self.collector.get_metrics()
        
        # Check tagged metrics
        self.assertIn("tagged_timer_duration[env=test]", metrics["histograms"])
        self.assertEqual(metrics["counters"]["tagged_timer_success[env=test]"], 1.0)


if __name__ == '__main__':
    unittest.main()