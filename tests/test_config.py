"""Property-based and unit tests for configuration management."""

import json
import os
import tempfile
import pytest
from hypothesis import given, strategies as st
from src.config import Config


# Feature: binance-futures-bot, Property 38: Configuration Validation
@given(
    risk_per_trade=st.floats(min_value=0.0001, max_value=0.1),
    leverage=st.integers(min_value=1, max_value=125),
    atr_period=st.integers(min_value=1, max_value=100),
    adx_period=st.integers(min_value=1, max_value=100),
    adx_threshold=st.floats(min_value=0, max_value=100),
    rvol_period=st.integers(min_value=1, max_value=100),
    rvol_threshold=st.floats(min_value=0.1, max_value=10.0),
    backtest_days=st.integers(min_value=1, max_value=365),
    trading_fee=st.floats(min_value=0, max_value=0.01),
    slippage=st.floats(min_value=0, max_value=0.01),
    stop_loss_atr_multiplier=st.floats(min_value=0.1, max_value=10.0),
    trailing_stop_atr_multiplier=st.floats(min_value=0.1, max_value=10.0),
    run_mode=st.sampled_from(["BACKTEST", "PAPER", "LIVE"])
)
def test_valid_configuration_passes_validation(
    risk_per_trade, leverage, atr_period, adx_period, adx_threshold,
    rvol_period, rvol_threshold, backtest_days, trading_fee, slippage,
    stop_loss_atr_multiplier, trailing_stop_atr_multiplier, run_mode
):
    """For any valid configuration parameters, validation should pass without errors.
    
    Property 38: Configuration Validation
    Validates: Requirements 14.2
    """
    config = Config()
    config.risk_per_trade = risk_per_trade
    config.leverage = leverage
    config.atr_period = atr_period
    config.adx_period = adx_period
    config.adx_threshold = adx_threshold
    config.rvol_period = rvol_period
    config.rvol_threshold = rvol_threshold
    config.backtest_days = backtest_days
    config.trading_fee = trading_fee
    config.slippage = slippage
    config.stop_loss_atr_multiplier = stop_loss_atr_multiplier
    config.trailing_stop_atr_multiplier = trailing_stop_atr_multiplier
    config.run_mode = run_mode
    
    # For PAPER and LIVE modes, set dummy API keys
    if run_mode in ["PAPER", "LIVE"]:
        config.api_key = "test_api_key"
        config.api_secret = "test_api_secret"
    
    # Should not raise any exception
    config.validate()


# Feature: binance-futures-bot, Property 40: Default Configuration Values
@given(
    missing_params=st.lists(
        st.sampled_from([
            "symbol", "timeframe_entry", "timeframe_filter",
            "risk_per_trade", "leverage", "stop_loss_atr_multiplier",
            "trailing_stop_atr_multiplier", "atr_period", "adx_period",
            "adx_threshold", "rvol_period", "rvol_threshold",
            "backtest_days", "trading_fee", "slippage", "log_file"
        ]),
        min_size=1,
        max_size=5,
        unique=True
    )
)
def test_missing_optional_parameters_use_defaults(missing_params):
    """For any optional configuration parameter that is missing, 
    the system should use documented default values.
    
    Property 40: Default Configuration Values
    Validates: Requirements 14.5
    """
    # Create a minimal config dict (only required for BACKTEST mode)
    config_data = {
        "run_mode": "BACKTEST",
        "symbol": "BTCUSDT",
        "timeframe_entry": "15m",
        "timeframe_filter": "1h",
        "risk_per_trade": 0.01,
        "leverage": 3,
        "stop_loss_atr_multiplier": 2.0,
        "trailing_stop_atr_multiplier": 1.5,
        "atr_period": 14,
        "adx_period": 14,
        "adx_threshold": 20.0,
        "rvol_period": 20,
        "rvol_threshold": 1.2,
        "backtest_days": 90,
        "trading_fee": 0.0005,
        "slippage": 0.0002,
        "log_file": "binance_results.json"
    }
    
    # Remove the parameters we want to test as missing
    for param in missing_params:
        if param in config_data:
            del config_data[param]
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        # Load config from file
        config = Config.load_from_file(temp_path)
        
        # Verify that defaults were applied
        applied_defaults = config.get_applied_defaults()
        
        # At least one default should have been applied for missing params
        assert len(applied_defaults) > 0, "Expected defaults to be applied for missing parameters"
        
        # Verify the config is still valid
        config.validate()
        
    finally:
        # Clean up temp file
        os.unlink(temp_path)


# Feature: binance-futures-bot, Property 39: Invalid Configuration Rejection
class TestInvalidConfigurationRejection:
    """Unit tests for invalid configuration scenarios.
    
    Property 39: Invalid Configuration Rejection
    Validates: Requirements 14.3
    """
    
    def test_negative_risk_per_trade_rejected(self):
        """Negative risk_per_trade should be rejected."""
        config = Config()
        config.risk_per_trade = -0.01
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "risk_per_trade" in str(exc_info.value).lower()
    
    def test_excessive_risk_per_trade_rejected(self):
        """Risk per trade > 10% should be rejected."""
        config = Config()
        config.risk_per_trade = 0.15
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "risk_per_trade" in str(exc_info.value).lower()
    
    def test_invalid_run_mode_rejected(self):
        """Invalid run_mode should be rejected."""
        config = Config()
        config.run_mode = "INVALID_MODE"
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "run_mode" in str(exc_info.value).lower()
    
    def test_invalid_leverage_rejected(self):
        """Leverage outside 1-125 range should be rejected."""
        config = Config()
        config.leverage = 0
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "leverage" in str(exc_info.value).lower()
        
        config.leverage = 200
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "leverage" in str(exc_info.value).lower()
    
    def test_negative_atr_period_rejected(self):
        """Negative or zero ATR period should be rejected."""
        config = Config()
        config.atr_period = 0
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "atr_period" in str(exc_info.value).lower()
    
    def test_invalid_timeframe_rejected(self):
        """Invalid timeframe strings should be rejected."""
        config = Config()
        config.timeframe_entry = "invalid"
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "timeframe_entry" in str(exc_info.value).lower()
    
    def test_missing_api_keys_for_live_mode_rejected(self):
        """Missing API keys in LIVE mode should be rejected."""
        config = Config()
        config.run_mode = "LIVE"
        config.api_key = ""
        config.api_secret = ""
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value).lower()
        assert "api_key" in error_msg or "api_secret" in error_msg
    
    def test_missing_api_keys_for_paper_mode_rejected(self):
        """Missing API keys in PAPER mode should be rejected."""
        config = Config()
        config.run_mode = "PAPER"
        config.api_key = ""
        config.api_secret = ""
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value).lower()
        assert "api_key" in error_msg or "api_secret" in error_msg
    
    def test_negative_stop_loss_multiplier_rejected(self):
        """Negative stop loss multiplier should be rejected."""
        config = Config()
        config.stop_loss_atr_multiplier = -1.0
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "stop_loss_atr_multiplier" in str(exc_info.value).lower()
    
    def test_invalid_adx_threshold_rejected(self):
        """ADX threshold outside 0-100 range should be rejected."""
        config = Config()
        config.adx_threshold = 150.0
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "adx_threshold" in str(exc_info.value).lower()
    
    def test_multiple_errors_reported_together(self):
        """Multiple validation errors should be reported together."""
        config = Config()
        config.risk_per_trade = -0.01
        config.leverage = 0
        config.run_mode = "INVALID"
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        error_msg = str(exc_info.value).lower()
        # Should contain multiple error messages
        assert "risk_per_trade" in error_msg
        assert "leverage" in error_msg
        assert "run_mode" in error_msg


def test_api_key_redaction():
    """Test that API keys are properly redacted for logging."""
    config = Config()
    
    # Test with normal length key
    key = "abcdefghijklmnopqrstuvwxyz"
    redacted = config.redact_api_key(key)
    assert redacted == "abcd...wxyz"
    assert len(redacted) < len(key)
    
    # Test with short key
    short_key = "abc"
    redacted_short = config.redact_api_key(short_key)
    assert redacted_short == "****"
    
    # Test with empty key
    empty_key = ""
    redacted_empty = config.redact_api_key(empty_key)
    assert redacted_empty == "****"
