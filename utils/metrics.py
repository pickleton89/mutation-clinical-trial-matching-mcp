"""
Request Metrics System for API Performance Monitoring.

This module implements a comprehensive metrics collection system to track:
- API call counts and latencies
- Success/failure rates
- Cache hit/miss ratios
- Circuit breaker state changes
- Performance counters and distribution statistics
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
from threading import Lock
import json

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricPoint:
    """Individual metric data point."""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.COUNTER


@dataclass
class HistogramStats:
    """Histogram statistics for timing and distribution metrics."""
    count: int = 0
    sum: float = 0.0
    min: float = float('inf')
    max: float = float('-inf')
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    
    def update(self, value: float):
        """Update histogram statistics with a new value."""
        self.count += 1
        self.sum += value
        self.min = min(self.min, value)
        self.max = max(self.max, value)


class MetricsCollector:
    """
    Thread-safe metrics collector for API performance monitoring.
    
    Collects various types of metrics and provides aggregation and export capabilities.
    """
    
    def __init__(self, max_points: int = 10000):
        self.max_points = max_points
        self._points: deque = deque(maxlen=max_points)
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, HistogramStats] = defaultdict(HistogramStats)
        self._histogram_values: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._lock = Lock()
        
        logger.info("Metrics collector initialized", extra={
            "max_points": max_points,
            "action": "metrics_collector_initialized"
        })
    
    def increment(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to increment by (default: 1.0)
            tags: Optional tags for the metric
        """
        tags = tags or {}
        with self._lock:
            key = self._get_metric_key(name, tags)
            self._counters[key] += value
            
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags,
                metric_type=MetricType.COUNTER
            )
            self._points.append(point)
    
    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Current value
            tags: Optional tags for the metric
        """
        tags = tags or {}
        with self._lock:
            key = self._get_metric_key(name, tags)
            self._gauges[key] = value
            
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags,
                metric_type=MetricType.GAUGE
            )
            self._points.append(point)
    
    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Record a histogram metric value.
        
        Args:
            name: Metric name
            value: Value to record
            tags: Optional tags for the metric
        """
        tags = tags or {}
        with self._lock:
            key = self._get_metric_key(name, tags)
            self._histograms[key].update(value)
            self._histogram_values[key].append(value)
            
            point = MetricPoint(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags,
                metric_type=MetricType.HISTOGRAM
            )
            self._points.append(point)
    
    def timer(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Create a timer context manager for measuring execution time.
        
        Args:
            name: Metric name
            tags: Optional tags for the metric
            
        Returns:
            Timer context manager
        """
        return Timer(self, name, tags)
    
    def _get_metric_key(self, name: str, tags: Dict[str, str]) -> str:
        """Generate a unique key for a metric with its tags."""
        if not tags:
            return name
        
        sorted_tags = sorted(tags.items())
        tag_str = ",".join(f"{k}={v}" for k, v in sorted_tags)
        return f"{name}[{tag_str}]"
    
    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate percentiles for a list of values."""
        if not values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        def percentile(p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = k - f
            if f == n - 1:
                return sorted_values[f]
            return sorted_values[f] * (1 - c) + sorted_values[f + 1] * c
        
        return {
            "p50": percentile(0.5),
            "p95": percentile(0.95),
            "p99": percentile(0.99)
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all current metrics.
        
        Returns:
            Dictionary containing all metrics with their current values
        """
        with self._lock:
            metrics = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {}
            }
            
            # Calculate histogram statistics
            for key, hist in self._histograms.items():
                values = list(self._histogram_values[key])
                percentiles = self._calculate_percentiles(values)
                
                metrics["histograms"][key] = {
                    "count": hist.count,
                    "sum": hist.sum,
                    "min": hist.min if hist.min != float('inf') else 0.0,
                    "max": hist.max if hist.max != float('-inf') else 0.0,
                    "avg": hist.sum / hist.count if hist.count > 0 else 0.0,
                    **percentiles
                }
            
            return metrics
    
    def get_recent_points(self, limit: int = 100) -> List[MetricPoint]:
        """
        Get recent metric points.
        
        Args:
            limit: Maximum number of points to return
            
        Returns:
            List of recent metric points
        """
        with self._lock:
            points = list(self._points)
            return points[-limit:] if len(points) > limit else points
    
    def reset(self):
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._points.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._histogram_values.clear()
            
            logger.info("Metrics collector reset", extra={
                "action": "metrics_collector_reset"
            })
    
    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        metrics = self.get_metrics()
        
        # Export counters
        for key, value in metrics["counters"].items():
            name, tags = self._parse_metric_key(key)
            lines.append(f"# TYPE {name} counter")
            if tags:
                tag_str = ",".join(f'{k}="{v}"' for k, v in tags.items())
                lines.append(f"{name}{{{tag_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
        
        # Export gauges
        for key, value in metrics["gauges"].items():
            name, tags = self._parse_metric_key(key)
            lines.append(f"# TYPE {name} gauge")
            if tags:
                tag_str = ",".join(f'{k}="{v}"' for k, v in tags.items())
                lines.append(f"{name}{{{tag_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
        
        # Export histograms
        for key, hist in metrics["histograms"].items():
            name, tags = self._parse_metric_key(key)
            lines.append(f"# TYPE {name} histogram")
            
            tag_str = ""
            if tags:
                tag_str = ",".join(f'{k}="{v}"' for k, v in tags.items())
                tag_str = f"{{{tag_str}}}"
            
            lines.append(f"{name}_count{tag_str} {hist['count']}")
            lines.append(f"{name}_sum{tag_str} {hist['sum']}")
            lines.append(f"{name}_min{tag_str} {hist['min']}")
            lines.append(f"{name}_max{tag_str} {hist['max']}")
            lines.append(f"{name}_avg{tag_str} {hist['avg']}")
            
            # Add percentiles as separate metrics
            for percentile, value in [("p50", hist["p50"]), ("p95", hist["p95"]), ("p99", hist["p99"])]:
                lines.append(f"{name}_{percentile}{tag_str} {value}")
        
        return "\n".join(lines)
    
    def _parse_metric_key(self, key: str) -> tuple:
        """Parse a metric key back into name and tags."""
        if "[" not in key:
            return key, {}
        
        name, tag_part = key.split("[", 1)
        tag_part = tag_part.rstrip("]")
        
        tags = {}
        if tag_part:
            for tag_pair in tag_part.split(","):
                k, v = tag_pair.split("=", 1)
                tags[k] = v
        
        return name, tags
    
    def export_json(self) -> str:
        """
        Export metrics in JSON format.
        
        Returns:
            JSON-formatted metrics string
        """
        metrics = self.get_metrics()
        metrics["timestamp"] = time.time()
        return json.dumps(metrics, indent=2)


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, name: str, tags: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.tags = tags or {}
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.collector.histogram(f"{self.name}_duration", duration, self.tags)
            
            # Also track success/failure
            if exc_type is not None:
                self.collector.increment(f"{self.name}_errors", 1.0, self.tags)
            else:
                self.collector.increment(f"{self.name}_success", 1.0, self.tags)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None
_collector_lock = Lock()


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        Global MetricsCollector instance
    """
    global _metrics_collector
    with _collector_lock:
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector()
        return _metrics_collector


def reset_metrics_collector():
    """Reset the global metrics collector (useful for testing)."""
    global _metrics_collector
    with _collector_lock:
        if _metrics_collector is not None:
            _metrics_collector.reset()
        _metrics_collector = None


# Convenience functions for common metrics operations
def increment(name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None):
    """Increment a counter metric."""
    get_metrics_collector().increment(name, value, tags)


def gauge(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Set a gauge metric value."""
    get_metrics_collector().gauge(name, value, tags)


def histogram(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Record a histogram metric value."""
    get_metrics_collector().histogram(name, value, tags)


def timer(name: str, tags: Optional[Dict[str, str]] = None):
    """Create a timer context manager."""
    return get_metrics_collector().timer(name, tags)


def get_metrics() -> Dict[str, Any]:
    """Get all current metrics."""
    return get_metrics_collector().get_metrics()


def export_prometheus() -> str:
    """Export metrics in Prometheus format."""
    return get_metrics_collector().export_prometheus()


def export_json() -> str:
    """Export metrics in JSON format."""
    return get_metrics_collector().export_json()


# Decorator for automatic function timing
def timed(name: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
    """
    Decorator to automatically time function execution.
    
    Args:
        name: Optional metric name (defaults to function name)
        tags: Optional tags for the metric
    """
    def decorator(func: Callable) -> Callable:
        metric_name = name or func.__name__
        
        def wrapper(*args, **kwargs):
            with timer(metric_name, tags):
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator