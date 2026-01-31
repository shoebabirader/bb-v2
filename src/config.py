"""Configuration management for Binance Futures Trading Bot."""

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Configuration class for the trading bot.
    
    Loads configuration from config.json and environment variables.
    Validates all parameters before allowing system initialization.
    """
    
    # API Configuration
    api_key: str = ""
    api_secret: str = ""
    
    # Trading Parameters
    symbol: str = "BTCUSDT"
    timeframe_entry: str = "15m"
    timeframe_filter: str = "1h"
    
    # Risk Parameters
    risk_per_trade: float = 0.01  # 1%
    leverage: int = 3
    stop_loss_atr_multiplier: float = 2.0
    trailing_stop_atr_multiplier: float = 1.5
    
    # Indicator Parameters
    atr_period: int = 14
    adx_period: int = 14
    adx_threshold: float = 20.0
    rvol_period: int = 20
    rvol_threshold: float = 1.2
    
    # Backtest Parameters
    backtest_days: int = 90
    trading_fee: float = 0.0005  # 0.05%
    slippage: float = 0.0002     # 0.02%
    
    # System Parameters
    run_mode: str = "BACKTEST"  # BACKTEST, PAPER, LIVE
    log_file: str = "binance_results.json"
    
    # Applied defaults tracking
    _applied_defaults: list = field(default_factory=list, init=False, repr=False)
    
    @classmethod
    def load_from_file(cls, config_path: str = "config/config.json") -> "Config":
        """Load configuration from JSON file and environment variables.
        
        Args:
            config_path: Path to the configuration JSON file
            
        Returns:
            Config instance with loaded and validated configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        config = cls()
        
        # Load from JSON file if it exists
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                config._load_from_dict(config_data)
        else:
            # Track that we're using all defaults
            config._applied_defaults.append("No config file found, using all defaults")
        
        # Override with environment variables (higher priority)
        config._load_from_env()
        
        # Validate configuration
        config.validate()
        
        return config
    
    def _load_from_dict(self, config_data: dict) -> None:
        """Load configuration from dictionary."""
        # API Configuration
        if "api_key" in config_data:
            self.api_key = config_data["api_key"]
        else:
            self._applied_defaults.append("api_key (will check environment variables)")
            
        if "api_secret" in config_data:
            self.api_secret = config_data["api_secret"]
        else:
            self._applied_defaults.append("api_secret (will check environment variables)")
        
        # Trading Parameters
        if "symbol" in config_data:
            self.symbol = config_data["symbol"]
        else:
            self._applied_defaults.append(f"symbol (default: {self.symbol})")
            
        if "timeframe_entry" in config_data:
            self.timeframe_entry = config_data["timeframe_entry"]
        else:
            self._applied_defaults.append(f"timeframe_entry (default: {self.timeframe_entry})")
            
        if "timeframe_filter" in config_data:
            self.timeframe_filter = config_data["timeframe_filter"]
        else:
            self._applied_defaults.append(f"timeframe_filter (default: {self.timeframe_filter})")
        
        # Risk Parameters
        if "risk_per_trade" in config_data:
            self.risk_per_trade = float(config_data["risk_per_trade"])
        else:
            self._applied_defaults.append(f"risk_per_trade (default: {self.risk_per_trade})")
            
        if "leverage" in config_data:
            self.leverage = int(config_data["leverage"])
        else:
            self._applied_defaults.append(f"leverage (default: {self.leverage})")
            
        if "stop_loss_atr_multiplier" in config_data:
            self.stop_loss_atr_multiplier = float(config_data["stop_loss_atr_multiplier"])
        else:
            self._applied_defaults.append(f"stop_loss_atr_multiplier (default: {self.stop_loss_atr_multiplier})")
            
        if "trailing_stop_atr_multiplier" in config_data:
            self.trailing_stop_atr_multiplier = float(config_data["trailing_stop_atr_multiplier"])
        else:
            self._applied_defaults.append(f"trailing_stop_atr_multiplier (default: {self.trailing_stop_atr_multiplier})")
        
        # Indicator Parameters
        if "atr_period" in config_data:
            self.atr_period = int(config_data["atr_period"])
        else:
            self._applied_defaults.append(f"atr_period (default: {self.atr_period})")
            
        if "adx_period" in config_data:
            self.adx_period = int(config_data["adx_period"])
        else:
            self._applied_defaults.append(f"adx_period (default: {self.adx_period})")
            
        if "adx_threshold" in config_data:
            self.adx_threshold = float(config_data["adx_threshold"])
        else:
            self._applied_defaults.append(f"adx_threshold (default: {self.adx_threshold})")
            
        if "rvol_period" in config_data:
            self.rvol_period = int(config_data["rvol_period"])
        else:
            self._applied_defaults.append(f"rvol_period (default: {self.rvol_period})")
            
        if "rvol_threshold" in config_data:
            self.rvol_threshold = float(config_data["rvol_threshold"])
        else:
            self._applied_defaults.append(f"rvol_threshold (default: {self.rvol_threshold})")
        
        # Backtest Parameters
        if "backtest_days" in config_data:
            self.backtest_days = int(config_data["backtest_days"])
        else:
            self._applied_defaults.append(f"backtest_days (default: {self.backtest_days})")
            
        if "trading_fee" in config_data:
            self.trading_fee = float(config_data["trading_fee"])
        else:
            self._applied_defaults.append(f"trading_fee (default: {self.trading_fee})")
            
        if "slippage" in config_data:
            self.slippage = float(config_data["slippage"])
        else:
            self._applied_defaults.append(f"slippage (default: {self.slippage})")
        
        # System Parameters
        if "run_mode" in config_data:
            self.run_mode = config_data["run_mode"]
        else:
            self._applied_defaults.append(f"run_mode (default: {self.run_mode})")
            
        if "log_file" in config_data:
            self.log_file = config_data["log_file"]
        else:
            self._applied_defaults.append(f"log_file (default: {self.log_file})")
    
    def _load_from_env(self) -> None:
        """Load configuration from environment variables (overrides file config)."""
        if os.getenv("BINANCE_API_KEY"):
            self.api_key = os.getenv("BINANCE_API_KEY")
        
        if os.getenv("BINANCE_API_SECRET"):
            self.api_secret = os.getenv("BINANCE_API_SECRET")
        
        if os.getenv("TRADING_SYMBOL"):
            self.symbol = os.getenv("TRADING_SYMBOL")
        
        if os.getenv("RUN_MODE"):
            self.run_mode = os.getenv("RUN_MODE")
    
    def redact_api_key(self, key: str) -> str:
        """Redact API key for safe logging/display.
        
        Args:
            key: API key to redact
            
        Returns:
            Redacted key showing only first 4 and last 4 characters
        """
        if not key or len(key) < 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"
    
    def validate(self) -> None:
        """Validate all configuration parameters.
        
        Raises:
            ValueError: If any configuration parameter is invalid
        """
        errors = []
        
        # Validate run mode
        valid_modes = ["BACKTEST", "PAPER", "LIVE"]
        if self.run_mode not in valid_modes:
            errors.append(f"Invalid run_mode '{self.run_mode}'. Must be one of: {', '.join(valid_modes)}")
        
        # Validate API keys for PAPER and LIVE modes
        if self.run_mode in ["PAPER", "LIVE"]:
            if not self.api_key:
                errors.append("api_key is required for PAPER and LIVE modes")
            if not self.api_secret:
                errors.append("api_secret is required for PAPER and LIVE modes")
        
        # Validate risk parameters
        if self.risk_per_trade <= 0 or self.risk_per_trade > 1.0:
            errors.append(f"Invalid risk_per_trade {self.risk_per_trade}. Must be between 0 and 1.0 (0-100%)")
        
        if self.leverage < 1 or self.leverage > 125:
            errors.append(f"Invalid leverage {self.leverage}. Must be between 1 and 125")
        
        if self.stop_loss_atr_multiplier <= 0:
            errors.append(f"Invalid stop_loss_atr_multiplier {self.stop_loss_atr_multiplier}. Must be positive")
        
        if self.trailing_stop_atr_multiplier <= 0:
            errors.append(f"Invalid trailing_stop_atr_multiplier {self.trailing_stop_atr_multiplier}. Must be positive")
        
        # Validate indicator parameters
        if self.atr_period < 1:
            errors.append(f"Invalid atr_period {self.atr_period}. Must be at least 1")
        
        if self.adx_period < 1:
            errors.append(f"Invalid adx_period {self.adx_period}. Must be at least 1")
        
        if self.adx_threshold < 0 or self.adx_threshold > 100:
            errors.append(f"Invalid adx_threshold {self.adx_threshold}. Must be between 0 and 100")
        
        if self.rvol_period < 1:
            errors.append(f"Invalid rvol_period {self.rvol_period}. Must be at least 1")
        
        if self.rvol_threshold <= 0:
            errors.append(f"Invalid rvol_threshold {self.rvol_threshold}. Must be positive")
        
        # Validate backtest parameters
        if self.backtest_days < 1:
            errors.append(f"Invalid backtest_days {self.backtest_days}. Must be at least 1")
        
        if self.trading_fee < 0 or self.trading_fee > 0.01:
            errors.append(f"Invalid trading_fee {self.trading_fee}. Must be between 0 and 0.01 (0-1%)")
        
        if self.slippage < 0 or self.slippage > 0.01:
            errors.append(f"Invalid slippage {self.slippage}. Must be between 0 and 0.01 (0-1%)")
        
        # Validate timeframes
        valid_timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"]
        if self.timeframe_entry not in valid_timeframes:
            errors.append(f"Invalid timeframe_entry '{self.timeframe_entry}'. Must be one of: {', '.join(valid_timeframes)}")
        
        if self.timeframe_filter not in valid_timeframes:
            errors.append(f"Invalid timeframe_filter '{self.timeframe_filter}'. Must be one of: {', '.join(valid_timeframes)}")
        
        # If there are errors, raise ValueError with all error messages
        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            raise ValueError(error_message)
    
    def get_applied_defaults(self) -> list:
        """Get list of configuration parameters that used default values.
        
        Returns:
            List of parameter names that used defaults
        """
        return self._applied_defaults.copy()
