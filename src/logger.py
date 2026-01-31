"""Logging and persistence module for Binance Futures Trading Bot.

This module provides comprehensive logging functionality including:
- Trade logging to local files
- Error logging with stack traces
- Performance metrics persistence
- API key redaction for security
- Daily log file rotation
"""

import logging
import json
import os
import re
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from logging.handlers import TimedRotatingFileHandler

from src.models import Trade, PerformanceMetrics


class APIKeyRedactingFormatter(logging.Formatter):
    """Custom formatter that redacts API keys from log messages."""
    
    # Patterns to match potential API keys
    # Match alphanumeric and common special chars, but stop before quotes/whitespace
    # Exclude scientific notation (e.g., 1.23e-45) by not matching patterns with 'e' followed by digits
    API_KEY_PATTERNS = [
        r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9](?![0-9.]*e[+-]?[0-9])[^\s"\']{19,})(?=["\']?(?:\s|$|,|}))',
        r'api[_-]?secret["\']?\s*[:=]\s*["\']?([A-Za-z0-9](?![0-9.]*e[+-]?[0-9])[^\s"\']{19,})(?=["\']?(?:\s|$|,|}))',
        r'BINANCE[_-]?API[_-]?KEY["\']?\s*[:=]\s*["\']?([A-Za-z0-9](?![0-9.]*e[+-]?[0-9])[^\s"\']{19,})(?=["\']?(?:\s|$|,|}))',
        r'BINANCE[_-]?API[_-]?SECRET["\']?\s*[:=]\s*["\']?([A-Za-z0-9](?![0-9.]*e[+-]?[0-9])[^\s"\']{19,})(?=["\']?(?:\s|$|,|}))',
        # Match standalone long strings that look like keys (20+ chars, starts with alnum)
        # Match any non-whitespace except quotes, but exclude scientific notation
        r'(?<![A-Za-z0-9])([A-Za-z0-9](?![0-9.]*e[+-]?[0-9])[^\s"\']{19,})(?![A-Za-z0-9])',
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with API key redaction.
        
        Args:
            record: Log record to format
            
        Returns:
            Formatted log message with API keys redacted
        """
        # Format the message first
        message = super().format(record)
        
        # Redact API keys
        for pattern in self.API_KEY_PATTERNS:
            message = re.sub(pattern, lambda m: self._redact_match(m), message, flags=re.IGNORECASE)
        
        return message
    
    def _redact_match(self, match: re.Match) -> str:
        """Redact a matched API key.
        
        Args:
            match: Regex match object
            
        Returns:
            Redacted string showing only first/last few characters
        """
        # Get the full match
        full_match = match.group(0)
        
        # Try to get the captured group (the actual key)
        try:
            key = match.group(1)
        except IndexError:
            key = full_match
        
        # Only redact if the key looks realistic
        # Real API keys are typically 20+ characters and have both letters and digits
        is_long_enough = len(key) >= 20
        
        # Check if it has both letters and digits (realistic API key pattern)
        has_letters = any(c.isalpha() for c in key)
        has_digits = any(c.isdigit() for c in key)
        
        # Count alphanumeric characters
        alnum_count = sum(1 for c in key if c.isalnum())
        alnum_ratio = alnum_count / len(key) if len(key) > 0 else 0
        
        # Redact if:
        # 1. Long enough (20+ chars)
        # 2. Has both letters and digits (realistic API key)
        # 3. Mostly alphanumeric (>70% to handle edge cases with special chars)
        if is_long_enough and has_letters and has_digits and alnum_ratio > 0.7:
            # If key is long enough, show first 4 and last 4 characters
            if len(key) >= 12:
                redacted = f"{key[:4]}...{key[-4:]}"
            else:
                redacted = "***REDACTED***"
            
            # Replace the key in the full match
            return full_match.replace(key, redacted)
        else:
            # Don't redact unrealistic keys (too short, no mixed alphanumeric, or too many special chars)
            return full_match


class TradingLogger:
    """Main logging class for the trading bot.
    
    Provides methods for:
    - Trade logging
    - Error logging with stack traces
    - Performance metrics persistence
    - General system logging
    
    All logs automatically redact API keys for security.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize the trading logger.
        
        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = log_dir
        self._ensure_log_directory()
        
        # Set up different loggers
        self.trade_logger = self._setup_trade_logger()
        self.error_logger = self._setup_error_logger()
        self.system_logger = self._setup_system_logger()
    
    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _setup_trade_logger(self) -> logging.Logger:
        """Set up logger for trade execution logs.
        
        Returns:
            Configured trade logger with daily rotation
        """
        logger = logging.getLogger("trading_bot.trades")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Create rotating file handler (rotates daily at midnight)
        trade_log_path = os.path.join(self.log_dir, "trades.log")
        handler = TimedRotatingFileHandler(
            trade_log_path,
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding="utf-8"
        )
        handler.suffix = "%Y-%m-%d"
        
        # Set formatter with API key redaction
        formatter = APIKeyRedactingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        return logger
    
    def _setup_error_logger(self) -> logging.Logger:
        """Set up logger for error logs with stack traces.
        
        Returns:
            Configured error logger with daily rotation
        """
        logger = logging.getLogger("trading_bot.errors")
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Create rotating file handler (rotates daily at midnight)
        error_log_path = os.path.join(self.log_dir, "errors.log")
        handler = TimedRotatingFileHandler(
            error_log_path,
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding="utf-8"
        )
        handler.suffix = "%Y-%m-%d"
        
        # Set formatter with API key redaction
        formatter = APIKeyRedactingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        return logger
    
    def _setup_system_logger(self) -> logging.Logger:
        """Set up logger for general system logs.
        
        Returns:
            Configured system logger with daily rotation
        """
        logger = logging.getLogger("trading_bot.system")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Create rotating file handler (rotates daily at midnight)
        system_log_path = os.path.join(self.log_dir, "system.log")
        handler = TimedRotatingFileHandler(
            system_log_path,
            when="midnight",
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding="utf-8"
        )
        handler.suffix = "%Y-%m-%d"
        
        # Set formatter with API key redaction
        formatter = APIKeyRedactingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        return logger
    
    def log_trade(self, trade: Trade) -> None:
        """Log a completed trade with all required fields.
        
        Args:
            trade: Trade object to log
        """
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "symbol": trade.symbol,
            "side": trade.side,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "quantity": trade.quantity,
            "pnl": trade.pnl,
            "pnl_percent": trade.pnl_percent,
            "entry_time": trade.entry_time,
            "exit_time": trade.exit_time,
            "exit_reason": trade.exit_reason
        }
        
        # Use allow_nan=False to ensure valid JSON (converts inf/nan to null)
        # This prevents JSON serialization issues with extreme floating point values
        self.trade_logger.info(f"TRADE_EXECUTED: {json.dumps(trade_data, allow_nan=False)}")
    
    def log_error(self, error: Exception, context: Optional[str] = None) -> None:
        """Log an error with full stack trace.
        
        Args:
            error: Exception that occurred
            context: Optional context description
        """
        error_message = f"ERROR: {str(error)}"
        if context:
            error_message = f"{context} - {error_message}"
        
        # Get full stack trace
        stack_trace = traceback.format_exc()
        
        self.error_logger.error(f"{error_message}\nStack Trace:\n{stack_trace}")
    
    def log_system_event(self, message: str, level: str = "INFO") -> None:
        """Log a general system event.
        
        Args:
            message: Log message
            level: Log level (INFO, WARNING, ERROR)
        """
        level = level.upper()
        
        if level == "INFO":
            self.system_logger.info(message)
        elif level == "WARNING":
            self.system_logger.warning(message)
        elif level == "ERROR":
            self.system_logger.error(message)
        else:
            self.system_logger.info(message)
    
    def save_performance_metrics(
        self, 
        metrics: PerformanceMetrics, 
        output_file: str = "binance_results.json"
    ) -> None:
        """Save performance metrics to JSON file.
        
        Args:
            metrics: PerformanceMetrics object to save
            output_file: Output file path
        """
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "total_trades": metrics.total_trades,
            "winning_trades": metrics.winning_trades,
            "losing_trades": metrics.losing_trades,
            "win_rate": metrics.win_rate,
            "total_pnl": metrics.total_pnl,
            "total_pnl_percent": metrics.total_pnl_percent,
            "roi": metrics.roi,
            "max_drawdown": metrics.max_drawdown,
            "max_drawdown_percent": metrics.max_drawdown_percent,
            "profit_factor": metrics.profit_factor,
            "sharpe_ratio": metrics.sharpe_ratio,
            "average_win": metrics.average_win,
            "average_loss": metrics.average_loss,
            "largest_win": metrics.largest_win,
            "largest_loss": metrics.largest_loss,
            "average_trade_duration": metrics.average_trade_duration
        }
        
        # Ensure output directory exists
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Save to file
        with open(output_file, 'w') as f:
            json.dump(metrics_data, f, indent=2)
        
        self.system_logger.info(f"Performance metrics saved to {output_file}")
    
    def load_performance_metrics(self, input_file: str = "binance_results.json") -> Optional[Dict[str, Any]]:
        """Load performance metrics from JSON file.
        
        Args:
            input_file: Input file path
            
        Returns:
            Dictionary containing metrics data, or None if file doesn't exist
        """
        if not os.path.exists(input_file):
            return None
        
        with open(input_file, 'r') as f:
            return json.load(f)
    
    def get_trade_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get trade history from log files.
        
        Args:
            days: Number of days of history to retrieve
            
        Returns:
            List of trade dictionaries
        """
        trades = []
        
        # Read from current and rotated log files
        trade_log_path = os.path.join(self.log_dir, "trades.log")
        
        if os.path.exists(trade_log_path):
            with open(trade_log_path, 'r') as f:
                for line in f:
                    if "TRADE_EXECUTED:" in line:
                        try:
                            # Extract JSON part
                            json_start = line.index("{")
                            trade_data = json.loads(line[json_start:])
                            trades.append(trade_data)
                        except (ValueError, json.JSONDecodeError):
                            continue
        
        return trades


# Global logger instance
_logger_instance: Optional[TradingLogger] = None


def get_logger(log_dir: str = "logs") -> TradingLogger:
    """Get or create the global logger instance.
    
    Args:
        log_dir: Directory to store log files
        
    Returns:
        TradingLogger instance
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = TradingLogger(log_dir)
    
    return _logger_instance
