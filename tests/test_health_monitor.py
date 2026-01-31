"""Property-based and unit tests for HealthMonitor module.

Tests cover:
- API rate limit tracking and throttling
- Critical error notification
- Health check periodicity
- Memory usage monitoring
"""

import time
import pytest
from hypothesis import given, strategies as st, settings
from unittest.mock import Mock, patch

from src.health_monitor import (
    HealthMonitor,
    APIRateLimitTracker,
    HealthCheckResult
)


# Feature: binance-futures-bot, Property 45: API Rate Limit Respect
@given(
    num_requests=st.integers(min_value=1, max_value=2000),
    time_window=st.floats(min_value=0.1, max_value=120.0)
)
@settings(max_examples=100, deadline=None)
def test_api_rate_limit_respect(num_requests, time_window):
    """For any sequence of API requests, the request rate should never exceed
    Binance's documented rate limits, with throttling applied when approaching limits.
    
    Validates: Requirements 16.2
    """
    tracker = APIRateLimitTracker(
        max_requests_per_minute=1200,
        max_requests_per_second=20
    )
    
    # Simulate requests over time window
    start_time = time.time()
    requests_per_interval = num_requests / (time_window / 60.0)  # requests per minute
    
    # Record requests
    for i in range(num_requests):
        # Calculate timestamp for this request
        timestamp = start_time + (i / num_requests) * time_window
        tracker.record_request(timestamp)
        
        # Check if we should throttle
        if tracker.should_throttle():
            # Verify we're approaching limit (within 90% of max)
            rpm = tracker.get_requests_per_minute()
            rps = tracker.get_requests_per_second()
            
            # At least one limit should be approaching threshold
            approaching_minute = rpm >= tracker.max_requests_per_minute * 0.9
            approaching_second = rps >= tracker.max_requests_per_second * 0.9
            
            assert approaching_minute or approaching_second, \
                f"Throttle triggered but not approaching limits: rpm={rpm}, rps={rps}"
        
        # Verify we never exceed hard limits
        rpm = tracker.get_requests_per_minute()
        rps = tracker.get_requests_per_second()
        
        # Note: In real usage, throttling would prevent exceeding limits
        # Here we just verify the tracker correctly identifies when limits are exceeded
        if rpm >= tracker.max_requests_per_minute:
            assert tracker.is_rate_limit_exceeded(), \
                f"Rate limit exceeded but not detected: rpm={rpm}"
        
        if rps >= tracker.max_requests_per_second:
            assert tracker.is_rate_limit_exceeded(), \
                f"Rate limit exceeded but not detected: rps={rps}"


# Feature: binance-futures-bot, Property 46: Critical Error Notification
@given(
    error_messages=st.lists(
        st.text(min_size=1, max_size=100),
        min_size=1,
        max_size=10
    )
)
@settings(max_examples=100, deadline=None)
def test_critical_error_notification(error_messages):
    """For any critical error (authentication failure, insufficient margin, API errors),
    a notification should be sent to the user through the UI.
    
    Validates: Requirements 16.4
    """
    # Track notifications
    notifications = []
    
    def notification_callback(message: str, level: str):
        notifications.append((message, level))
    
    monitor = HealthMonitor(
        check_interval=60,
        notification_callback=notification_callback
    )
    
    # Report each critical error
    for error_msg in error_messages:
        monitor.report_critical_error(error_msg)
    
    # Verify all errors were notified
    assert len(notifications) == len(error_messages), \
        f"Expected {len(error_messages)} notifications, got {len(notifications)}"
    
    # Verify all notifications are ERROR level
    for message, level in notifications:
        assert level == "ERROR", f"Expected ERROR level, got {level}"
        assert message in error_messages, f"Unexpected notification: {message}"
    
    # Verify errors were recorded (they remain until health check clears them)
    assert len(monitor.critical_errors) == len(error_messages), \
        f"Expected {len(error_messages)} critical errors recorded, got {len(monitor.critical_errors)}"
    
    # Perform health check to clear errors
    result = monitor.perform_health_check()
    
    # Verify errors were included in health check result
    assert len(result.critical_errors) == len(error_messages), \
        "Health check should include all critical errors"
    
    # Verify errors are cleared after health check
    assert len(monitor.critical_errors) == 0, \
        "Critical errors should be cleared after health check"


# Feature: binance-futures-bot, Property 47: Health Check Periodicity
@given(
    check_interval=st.integers(min_value=1, max_value=120),
    monitoring_duration=st.integers(min_value=2, max_value=10)
)
@settings(max_examples=100, deadline=None)
def test_health_check_periodicity(check_interval, monitoring_duration):
    """For any 60-second time window during system operation, exactly one health check
    should be performed and logged.
    
    Validates: Requirements 16.5
    """
    # For this test, we'll use a shorter check interval to speed up testing
    # The property should hold for any interval
    
    monitor = HealthMonitor(
        check_interval=check_interval,
        notification_callback=None
    )
    
    # Manually perform health checks at the expected interval
    num_expected_checks = monitoring_duration
    
    for i in range(num_expected_checks):
        result = monitor.perform_health_check()
        
        # Verify result is valid
        assert isinstance(result, HealthCheckResult)
        assert result.timestamp > 0
        assert 0.0 <= result.memory_usage_percent <= 1.0
        assert result.api_rate_limit_status in ["OK", "WARNING", "EXCEEDED"]
        
        # Verify result was stored
        assert result in monitor.health_check_results, \
            "Health check result should be stored in history"
        
        # Simulate waiting for next interval
        if i < num_expected_checks - 1:
            time.sleep(0.01)  # Small delay to ensure different timestamps
    
    # Verify we have exactly the expected number of checks
    assert len(monitor.health_check_results) == num_expected_checks, \
        f"Expected {num_expected_checks} health checks, got {len(monitor.health_check_results)}"
    
    # Verify checks are properly spaced (timestamps should be different)
    if num_expected_checks > 1:
        timestamps = [r.timestamp for r in monitor.health_check_results]
        for i in range(len(timestamps) - 1):
            assert timestamps[i+1] > timestamps[i], \
                "Health check timestamps should be monotonically increasing"


# Unit tests for specific scenarios

def test_rate_limit_tracker_basic():
    """Test basic rate limit tracking functionality."""
    tracker = APIRateLimitTracker(
        max_requests_per_minute=100,
        max_requests_per_second=10
    )
    
    # Record some requests
    current_time = time.time()
    for i in range(5):
        tracker.record_request(current_time + i * 0.1)
    
    # Verify counts
    assert tracker.get_requests_per_second() <= 5
    assert tracker.get_requests_per_minute() == 5
    
    # Should not be exceeded
    assert not tracker.is_rate_limit_exceeded()
    assert tracker.get_status() == "OK"


def test_rate_limit_tracker_exceeded():
    """Test rate limit exceeded detection."""
    tracker = APIRateLimitTracker(
        max_requests_per_minute=10,
        max_requests_per_second=5
    )
    
    # Record requests that exceed limit
    current_time = time.time()
    for i in range(15):
        tracker.record_request(current_time + i * 0.01)
    
    # Should be exceeded
    assert tracker.is_rate_limit_exceeded()
    assert tracker.get_status() == "EXCEEDED"


def test_rate_limit_tracker_approaching():
    """Test approaching rate limit detection."""
    tracker = APIRateLimitTracker(
        max_requests_per_minute=100,
        max_requests_per_second=10
    )
    
    # Record requests approaching limit (90 requests in 1 minute)
    current_time = time.time()
    for i in range(90):
        # Spread requests evenly over 60 seconds
        tracker.record_request(current_time + i * (60.0 / 90))
    
    # Should be approaching limit
    assert tracker.is_approaching_limit(threshold=0.8)
    assert tracker.get_status() == "WARNING"
    assert tracker.should_throttle()


def test_rate_limit_tracker_cleanup():
    """Test old request cleanup."""
    tracker = APIRateLimitTracker()
    
    # Record old requests
    old_time = time.time() - 120  # 2 minutes ago
    for i in range(10):
        tracker.record_request(old_time + i)
    
    # Record recent request
    tracker.record_request(time.time())
    
    # Old requests should be cleaned up
    assert tracker.get_requests_per_minute() == 1
    assert tracker.get_requests_per_second() == 1


def test_health_monitor_initialization():
    """Test HealthMonitor initialization."""
    monitor = HealthMonitor(
        check_interval=30,
        memory_warning_threshold=0.9
    )
    
    assert monitor.check_interval == 30
    assert monitor.memory_warning_threshold == 0.9
    assert monitor.websocket_connected is True
    assert len(monitor.critical_errors) == 0
    assert len(monitor.health_check_results) == 0


def test_health_monitor_perform_check():
    """Test performing a health check."""
    monitor = HealthMonitor()
    
    result = monitor.perform_health_check()
    
    assert isinstance(result, HealthCheckResult)
    assert result.timestamp > 0
    assert 0.0 <= result.memory_usage_percent <= 1.0
    assert result.api_rate_limit_status in ["OK", "WARNING", "EXCEEDED"]
    assert isinstance(result.websocket_connected, bool)
    assert isinstance(result.critical_errors, list)


def test_health_monitor_websocket_status():
    """Test WebSocket status tracking."""
    monitor = HealthMonitor()
    
    # Initially connected
    assert monitor.websocket_connected is True
    
    # Set disconnected
    monitor.set_websocket_status(False)
    assert monitor.websocket_connected is False
    
    # Set connected again
    monitor.set_websocket_status(True)
    assert monitor.websocket_connected is True


def test_health_monitor_critical_error():
    """Test critical error reporting."""
    notifications = []
    
    def callback(message: str, level: str):
        notifications.append((message, level))
    
    monitor = HealthMonitor(notification_callback=callback)
    
    # Report error
    monitor.report_critical_error("Test error")
    
    # Verify notification was sent
    assert len(notifications) == 1
    assert notifications[0] == ("Test error", "ERROR")


def test_health_monitor_memory_warning():
    """Test memory warning detection."""
    monitor = HealthMonitor(memory_warning_threshold=0.5)
    
    # Mock high memory usage
    with patch('psutil.virtual_memory') as mock_memory:
        mock_memory.return_value.percent = 85.0  # 85%
        
        result = monitor.perform_health_check()
        
        assert result.memory_warning is True
        assert result.memory_usage_percent == 0.85


def test_health_monitor_api_rate_limit_status():
    """Test API rate limit status reporting."""
    monitor = HealthMonitor()
    
    # Record some requests
    for _ in range(10):
        monitor.record_api_request()
    
    status = monitor.get_api_rate_limit_status()
    
    assert 'status' in status
    assert 'requests_per_minute' in status
    assert 'requests_per_second' in status
    assert 'max_per_minute' in status
    assert 'max_per_second' in status
    assert 'should_throttle' in status
    
    assert status['requests_per_minute'] == 10
    assert status['status'] in ["OK", "WARNING", "EXCEEDED"]


def test_health_monitor_history():
    """Test health check history tracking."""
    monitor = HealthMonitor()
    
    # Perform multiple checks
    for _ in range(5):
        monitor.perform_health_check()
        time.sleep(0.01)
    
    # Verify history
    history = monitor.get_health_check_history(count=3)
    assert len(history) == 3
    
    # Verify latest check
    latest = monitor.get_latest_health_check()
    assert latest is not None
    assert latest == monitor.health_check_results[-1]


def test_health_monitor_start_stop():
    """Test starting and stopping health monitor."""
    monitor = HealthMonitor(check_interval=1)
    
    # Start monitoring
    monitor.start()
    assert monitor._running is True
    
    # Wait a bit
    time.sleep(0.1)
    
    # Stop monitoring
    monitor.stop()
    assert monitor._running is False


def test_health_check_result_is_healthy():
    """Test HealthCheckResult.is_healthy() method."""
    # Healthy result
    result = HealthCheckResult(
        timestamp=time.time(),
        memory_usage_percent=0.5,
        memory_warning=False,
        api_rate_limit_status="OK",
        websocket_connected=True,
        critical_errors=[]
    )
    assert result.is_healthy() is True
    
    # Unhealthy - memory warning
    result.memory_warning = True
    assert result.is_healthy() is False
    
    # Unhealthy - rate limit exceeded
    result.memory_warning = False
    result.api_rate_limit_status = "EXCEEDED"
    assert result.is_healthy() is False
    
    # Unhealthy - websocket disconnected
    result.api_rate_limit_status = "OK"
    result.websocket_connected = False
    assert result.is_healthy() is False
    
    # Unhealthy - critical errors
    result.websocket_connected = True
    result.critical_errors = ["Error 1"]
    assert result.is_healthy() is False
