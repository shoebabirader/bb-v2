"""System Health Monitoring module for Binance Futures Trading Bot.

This module provides health monitoring capabilities including:
- Periodic health checks (60-second intervals)
- API rate limit monitoring and throttling
- Critical error notification system
- Memory usage monitoring with warnings at 80%
"""

import time
import logging
import psutil
import threading
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    timestamp: float
    memory_usage_percent: float
    memory_warning: bool
    api_rate_limit_status: str
    websocket_connected: bool
    critical_errors: List[str] = field(default_factory=list)
    
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return (
            not self.memory_warning and
            self.api_rate_limit_status != "EXCEEDED" and
            self.websocket_connected and
            len(self.critical_errors) == 0
        )


@dataclass
class APIRateLimitTracker:
    """Tracks API rate limits."""
    max_requests_per_minute: int = 1200  # Binance default
    max_requests_per_second: int = 20
    
    # Request tracking
    requests_last_minute: List[float] = field(default_factory=list)
    requests_last_second: List[float] = field(default_factory=list)
    
    def record_request(self, timestamp: Optional[float] = None):
        """Record an API request.
        
        Args:
            timestamp: Request timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.requests_last_minute.append(timestamp)
        self.requests_last_second.append(timestamp)
        
        # Clean old requests
        self._clean_old_requests(timestamp)
    
    def _clean_old_requests(self, current_time: float):
        """Remove requests older than tracking window.
        
        Args:
            current_time: Current timestamp
        """
        # Remove requests older than 1 minute
        minute_ago = current_time - 60
        self.requests_last_minute = [
            t for t in self.requests_last_minute if t > minute_ago
        ]
        
        # Remove requests older than 1 second
        second_ago = current_time - 1
        self.requests_last_second = [
            t for t in self.requests_last_second if t > second_ago
        ]
    
    def get_requests_per_minute(self) -> int:
        """Get number of requests in the last minute."""
        self._clean_old_requests(time.time())
        return len(self.requests_last_minute)
    
    def get_requests_per_second(self) -> int:
        """Get number of requests in the last second."""
        self._clean_old_requests(time.time())
        return len(self.requests_last_second)
    
    def is_rate_limit_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return (
            self.get_requests_per_minute() >= self.max_requests_per_minute or
            self.get_requests_per_second() >= self.max_requests_per_second
        )
    
    def is_approaching_limit(self, threshold: float = 0.8) -> bool:
        """Check if approaching rate limit.
        
        Args:
            threshold: Threshold as fraction of limit (default 0.8 = 80%)
        
        Returns:
            True if approaching limit
        """
        minute_threshold = int(self.max_requests_per_minute * threshold)
        second_threshold = int(self.max_requests_per_second * threshold)
        
        return (
            self.get_requests_per_minute() >= minute_threshold or
            self.get_requests_per_second() >= second_threshold
        )
    
    def get_status(self) -> str:
        """Get rate limit status.
        
        Returns:
            Status string: "OK", "WARNING", or "EXCEEDED"
        """
        if self.is_rate_limit_exceeded():
            return "EXCEEDED"
        elif self.is_approaching_limit():
            return "WARNING"
        else:
            return "OK"
    
    def should_throttle(self) -> bool:
        """Check if requests should be throttled.
        
        Returns:
            True if should throttle
        """
        return self.is_approaching_limit(threshold=0.9)


class HealthMonitor:
    """System health monitoring service.
    
    Monitors:
    - Memory usage
    - API rate limits
    - WebSocket connection status
    - Critical errors
    
    Performs health checks at 60-second intervals.
    """
    
    def __init__(
        self,
        check_interval: int = 60,
        memory_warning_threshold: float = 0.8,
        notification_callback: Optional[Callable[[str, str], None]] = None
    ):
        """Initialize HealthMonitor.
        
        Args:
            check_interval: Health check interval in seconds (default 60)
            memory_warning_threshold: Memory usage threshold for warnings (default 0.8 = 80%)
            notification_callback: Callback for critical error notifications (message, level)
        """
        self.check_interval = check_interval
        self.memory_warning_threshold = memory_warning_threshold
        self.notification_callback = notification_callback
        
        # Health check tracking
        self.last_check_time: Optional[float] = None
        self.health_check_results: List[HealthCheckResult] = []
        
        # API rate limit tracking
        self.rate_limit_tracker = APIRateLimitTracker()
        
        # WebSocket status
        self.websocket_connected = True
        
        # Critical errors
        self.critical_errors: List[str] = []
        
        # Monitoring thread
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._running = False
        
        logger.info(f"HealthMonitor initialized (check_interval={check_interval}s)")
    
    def start(self):
        """Start health monitoring in background thread."""
        if self._running:
            logger.warning("HealthMonitor already running")
            return
        
        self._running = True
        self._stop_monitoring.clear()
        
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitoring_thread.start()
        
        logger.info("HealthMonitor started")
    
    def stop(self):
        """Stop health monitoring."""
        if not self._running:
            return
        
        self._running = False
        self._stop_monitoring.set()
        
        if self._monitoring_thread is not None:
            self._monitoring_thread.join(timeout=5)
        
        logger.info("HealthMonitor stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop (runs in background thread)."""
        while not self._stop_monitoring.is_set():
            try:
                # Perform health check (this now stores the result automatically)
                result = self.perform_health_check()
                
                # Log result
                if result.is_healthy():
                    logger.info(f"Health check passed: memory={result.memory_usage_percent:.1f}%, "
                               f"api_rate={result.api_rate_limit_status}")
                else:
                    logger.warning(f"Health check failed: {result}")
                
                # Notify on critical issues
                if result.memory_warning:
                    self._notify_critical_error(
                        f"High memory usage: {result.memory_usage_percent:.1f}%",
                        "WARNING"
                    )
                
                if result.api_rate_limit_status == "EXCEEDED":
                    self._notify_critical_error(
                        "API rate limit exceeded",
                        "ERROR"
                    )
                
                if not result.websocket_connected:
                    self._notify_critical_error(
                        "WebSocket disconnected",
                        "WARNING"
                    )
                
                for error in result.critical_errors:
                    self._notify_critical_error(error, "ERROR")
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}", exc_info=True)
            
            # Wait for next check interval
            self._stop_monitoring.wait(self.check_interval)
    
    def perform_health_check(self) -> HealthCheckResult:
        """Perform a health check.
        
        Returns:
            HealthCheckResult with current system status
        """
        timestamp = time.time()
        
        # Check memory usage
        memory_info = psutil.virtual_memory()
        memory_usage_percent = memory_info.percent / 100.0
        memory_warning = memory_usage_percent >= self.memory_warning_threshold
        
        # Check API rate limit status
        api_rate_limit_status = self.rate_limit_tracker.get_status()
        
        # Create result
        result = HealthCheckResult(
            timestamp=timestamp,
            memory_usage_percent=memory_usage_percent,
            memory_warning=memory_warning,
            api_rate_limit_status=api_rate_limit_status,
            websocket_connected=self.websocket_connected,
            critical_errors=self.critical_errors.copy()
        )
        
        # Store result in history
        self.health_check_results.append(result)
        
        # Keep only last 100 results
        if len(self.health_check_results) > 100:
            self.health_check_results = self.health_check_results[-100:]
        
        # Update last check time
        self.last_check_time = timestamp
        
        # Clear critical errors after reporting
        self.critical_errors.clear()
        
        return result
    
    def record_api_request(self):
        """Record an API request for rate limit tracking."""
        self.rate_limit_tracker.record_request()
    
    def should_throttle_requests(self) -> bool:
        """Check if API requests should be throttled.
        
        Returns:
            True if should throttle
        """
        return self.rate_limit_tracker.should_throttle()
    
    def set_websocket_status(self, connected: bool):
        """Update WebSocket connection status.
        
        Args:
            connected: True if connected, False if disconnected
        """
        if self.websocket_connected != connected:
            self.websocket_connected = connected
            status = "connected" if connected else "disconnected"
            logger.info(f"WebSocket status changed: {status}")
    
    def report_critical_error(self, error_message: str):
        """Report a critical error.
        
        Args:
            error_message: Error message
        """
        self.critical_errors.append(error_message)
        logger.error(f"Critical error reported: {error_message}")
        
        # Immediate notification
        self._notify_critical_error(error_message, "ERROR")
    
    def _notify_critical_error(self, message: str, level: str):
        """Send critical error notification.
        
        Args:
            message: Error message
            level: Severity level ("INFO", "WARNING", "ERROR")
        """
        if self.notification_callback is not None:
            try:
                self.notification_callback(message, level)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")
    
    def get_latest_health_check(self) -> Optional[HealthCheckResult]:
        """Get the most recent health check result.
        
        Returns:
            Latest HealthCheckResult or None if no checks performed
        """
        if not self.health_check_results:
            return None
        return self.health_check_results[-1]
    
    def get_health_check_history(self, count: int = 10) -> List[HealthCheckResult]:
        """Get recent health check history.
        
        Args:
            count: Number of recent results to return
        
        Returns:
            List of recent HealthCheckResult objects
        """
        return self.health_check_results[-count:]
    
    def get_memory_usage(self) -> float:
        """Get current memory usage percentage.
        
        Returns:
            Memory usage as percentage (0.0 to 1.0)
        """
        memory_info = psutil.virtual_memory()
        return memory_info.percent / 100.0
    
    def get_api_rate_limit_status(self) -> Dict[str, any]:
        """Get detailed API rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        return {
            'status': self.rate_limit_tracker.get_status(),
            'requests_per_minute': self.rate_limit_tracker.get_requests_per_minute(),
            'requests_per_second': self.rate_limit_tracker.get_requests_per_second(),
            'max_per_minute': self.rate_limit_tracker.max_requests_per_minute,
            'max_per_second': self.rate_limit_tracker.max_requests_per_second,
            'should_throttle': self.rate_limit_tracker.should_throttle()
        }
