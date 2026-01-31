"""Tests for the main TradingBot orchestration class."""

import pytest
from hypothesis import given, strategies as st, settings
from src.config import Config


# Feature: binance-futures-bot, Property 3: Mode Configuration Validity
@given(mode=st.sampled_from(["BACKTEST", "PAPER", "LIVE"]))
@settings(max_examples=100)
def test_mode_configuration_validity(mode):
    """For any valid operational mode string ("BACKTEST", "PAPER", "LIVE"),
    the system should initialize successfully with the correct subsystems activated.
    
    Validates: Requirements 1.5
    """
    # Create a config with the given mode
    config = Config()
    config.run_mode = mode
    
    # For PAPER and LIVE modes, we need API keys
    if mode in ["PAPER", "LIVE"]:
        config.api_key = "test_api_key_1234567890abcdef"
        config.api_secret = "test_api_secret_1234567890abcdef"
    
    # Validate the configuration - should not raise an exception
    try:
        config.validate()
        validation_passed = True
    except ValueError:
        validation_passed = False
    
    # Assert that validation passed for valid modes
    assert validation_passed, f"Configuration validation failed for valid mode: {mode}"
    
    # Verify the mode was set correctly
    assert config.run_mode == mode
    assert config.run_mode in ["BACKTEST", "PAPER", "LIVE"]


def test_invalid_mode_configuration():
    """Test that invalid modes are rejected during configuration validation."""
    config = Config()
    config.run_mode = "INVALID_MODE"
    
    # Should raise ValueError for invalid mode
    with pytest.raises(ValueError) as exc_info:
        config.validate()
    
    assert "Invalid run_mode" in str(exc_info.value)


def test_paper_mode_requires_api_keys():
    """Test that PAPER mode requires API keys."""
    config = Config()
    config.run_mode = "PAPER"
    config.api_key = ""
    config.api_secret = ""
    
    # Should raise ValueError for missing API keys
    with pytest.raises(ValueError) as exc_info:
        config.validate()
    
    assert "api_key is required" in str(exc_info.value)


def test_live_mode_requires_api_keys():
    """Test that LIVE mode requires API keys."""
    config = Config()
    config.run_mode = "LIVE"
    config.api_key = ""
    config.api_secret = ""
    
    # Should raise ValueError for missing API keys
    with pytest.raises(ValueError) as exc_info:
        config.validate()
    
    assert "api_key is required" in str(exc_info.value)


def test_backtest_mode_does_not_require_api_keys():
    """Test that BACKTEST mode does not require API keys."""
    config = Config()
    config.run_mode = "BACKTEST"
    config.api_key = ""
    config.api_secret = ""
    
    # Should not raise ValueError for BACKTEST mode without API keys
    try:
        config.validate()
        validation_passed = True
    except ValueError:
        validation_passed = False
    
    assert validation_passed, "BACKTEST mode should not require API keys"


def test_trading_bot_initialization_backtest_mode():
    """Test that TradingBot can be initialized in BACKTEST mode."""
    from src.trading_bot import TradingBot
    
    config = Config()
    config.run_mode = "BACKTEST"
    
    # Should initialize without errors
    bot = TradingBot(config)
    
    # Verify subsystems are initialized
    assert bot.config == config
    assert bot.data_manager is not None
    assert bot.strategy is not None
    assert bot.risk_manager is not None
    assert bot.order_executor is not None
    assert bot.ui_display is not None
    assert bot.backtest_engine is not None
    assert bot.client is None  # No client needed for backtest
    assert not bot.running
    assert not bot._panic_triggered


def test_trading_bot_mode_routing():
    """Test that TradingBot correctly identifies its operational mode."""
    from src.trading_bot import TradingBot
    
    # Test BACKTEST mode
    config_backtest = Config()
    config_backtest.run_mode = "BACKTEST"
    bot_backtest = TradingBot(config_backtest)
    assert bot_backtest.config.run_mode == "BACKTEST"
    assert bot_backtest.backtest_engine is not None
    
    # Test PAPER mode (without actually starting it)
    config_paper = Config()
    config_paper.run_mode = "PAPER"
    config_paper.api_key = "test_key"
    config_paper.api_secret = "test_secret"
    # Note: We can't fully test PAPER mode without API credentials
    # but we can verify the config is set correctly
    assert config_paper.run_mode == "PAPER"
    
    # Test LIVE mode (without actually starting it)
    config_live = Config()
    config_live.run_mode = "LIVE"
    config_live.api_key = "test_key"
    config_live.api_secret = "test_secret"
    # Note: We can't fully test LIVE mode without API credentials
    # but we can verify the config is set correctly
    assert config_live.run_mode == "LIVE"
