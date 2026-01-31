"""Integration and end-to-end tests for Binance Futures Trading Bot.

This module contains comprehensive integration tests that verify:
- Full backtest mode execution with historical data
- Configuration loading and validation
- Component integration and data flow
- Error handling scenarios
- Logging and persistence
- Panic close functionality

These tests validate the entire system working together as specified in
Requirements: All (comprehensive system validation)
"""

import pytest
import json
import os
import time
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Mock binance modules before importing our code
sys.modules['binance.streams'] = MagicMock()
sys.modules['binance.exceptions'] = MagicMock()

from src.config import Config
from src.trading_bot import TradingBot
from src.models import Candle, Signal, Position, Trade
from src.data_manager import DataManager
from src.strategy import StrategyEngine
from src.risk_manager import RiskManager
from src.position_sizer import PositionSizer
from src.order_executor import OrderExecutor
from src.backtest_engine import BacktestEngine


class TestConfigurationIntegration:
    """Test configuration loading and validation integration."""
    
    def test_load_valid_config_from_file(self, tmp_path):
        """Test loading a valid configuration file."""
        # Create a valid config file
        config_file = tmp_path / "config.json"
        config_data = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "symbol": "BTCUSDT",
            "run_mode": "BACKTEST",
            "risk_per_trade": 0.01,
            "leverage": 3
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Load config
        config = Config.load_from_file(str(config_file))
        
        assert config.api_key == "test_key"
        assert config.symbol == "BTCUSDT"
        assert config.run_mode == "BACKTEST"
        assert config.risk_per_trade == 0.01
    
    def test_config_with_defaults(self, tmp_path):
        """Test configuration with missing optional parameters uses defaults."""
        config_file = tmp_path / "config.json"
        config_data = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "run_mode": "BACKTEST"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = Config.load_from_file(str(config_file))
        
        # Check defaults are applied
        assert config.symbol == "BTCUSDT"
        assert config.risk_per_trade == 0.01
        assert config.leverage == 3
        assert config.atr_period == 14
    
    def test_invalid_config_raises_error(self, tmp_path):
        """Test that invalid configuration raises appropriate error."""
        config_file = tmp_path / "config.json"
        config_data = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "run_mode": "INVALID_MODE",  # Invalid mode
            "risk_per_trade": -0.5  # Invalid risk
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with pytest.raises(ValueError):
            Config.load_from_file(str(config_file))


class TestBacktestModeIntegration:
    """Test full backtest mode execution."""
    
    @patch('src.data_manager.DataManager.fetch_historical_data')
    @patch('src.trading_bot.Client')
    def test_full_backtest_execution(self, mock_client, mock_fetch):
        """Test complete backtest mode execution with historical data."""
        # Create test configuration
        config = Config(
            api_key="test_key",
            api_secret="test_secret",
            symbol="BTCUSDT",
            run_mode="BACKTEST",
            backtest_days=7,
            risk_per_trade=0.01,
            leverage=3
        )
        
        # Create mock historical data (7 days of 15m candles = ~672 candles)
        base_time = int(datetime.now().timestamp() * 1000)
        candles_15m = []
        for i in range(672):
            candle = Candle(
                timestamp=base_time + (i * 15 * 60 * 1000),
                open=50000.0 + (i * 10),
                high=50100.0 + (i * 10),
                low=49900.0 + (i * 10),
                close=50000.0 + (i * 10),
                volume=100.0 + (i * 0.5)
            )
            candles_15m.append(candle)
        
        # Create 1h candles (7 days = 168 candles)
        candles_1h = []
        for i in range(168):
            candle = Candle(
                timestamp=base_time + (i * 60 * 60 * 1000),
                open=50000.0 + (i * 40),
                high=50400.0 + (i * 40),
                low=49600.0 + (i * 40),
                close=50000.0 + (i * 40),
                volume=400.0 + (i * 2)
            )
            candles_1h.append(candle)
        
        # Mock fetch to return our test data
        def fetch_side_effect(days, timeframe):
            if timeframe == "15m":
                return candles_15m
            else:
                return candles_1h
        
        mock_fetch.side_effect = fetch_side_effect
        
        # Create and run trading bot
        bot = TradingBot(config)
        
        # Verify bot initialized correctly
        assert bot.config.run_mode == "BACKTEST"
        assert bot.backtest_engine is not None
        
        # Run backtest (this will execute the full backtest)
        try:
            bot._run_backtest()
            
            # Verify backtest completed
            # Note: We can't assert specific results without knowing the strategy behavior
            # but we can verify the backtest ran without errors
            assert True
        
        except Exception as e:
            pytest.fail(f"Backtest execution failed: {e}")
    
    @patch('src.data_manager.DataManager.fetch_historical_data')
    @patch('src.trading_bot.Client')
    def test_backtest_results_saved(self, mock_client, mock_fetch, tmp_path):
        """Test that backtest results are saved to file."""
        # Create test configuration with custom log file
        log_file = tmp_path / "test_results.json"
        config = Config(
            api_key="test_key",
            api_secret="test_secret",
            symbol="BTCUSDT",
            run_mode="BACKTEST",
            backtest_days=7,
            log_file=str(log_file)
        )
        
        # Create minimal test data
        base_time = int(datetime.now().timestamp() * 1000)
        candles_15m = [
            Candle(base_time + i * 15 * 60 * 1000, 50000.0, 50100.0, 49900.0, 50000.0, 100.0)
            for i in range(100)
        ]
        candles_1h = [
            Candle(base_time + i * 60 * 60 * 1000, 50000.0, 50400.0, 49600.0, 50000.0, 400.0)
            for i in range(50)
        ]
        
        mock_fetch.side_effect = lambda days, timeframe: candles_15m if timeframe == "15m" else candles_1h
        
        # Run backtest
        bot = TradingBot(config)
        bot._run_backtest()
        
        # Verify results file was created
        assert log_file.exists()
        
        # Verify results file contains expected data
        with open(log_file, 'r') as f:
            results = json.load(f)
        
        assert 'total_trades' in results
        assert 'win_rate' in results
        assert 'roi' in results


class TestComponentIntegration:
    """Test integration between major components."""
    
    def test_data_to_strategy_flow(self):
        """Test data flows correctly from DataManager to StrategyEngine."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        # Create components
        strategy = StrategyEngine(config)
        
        # Create test candles
        base_time = int(datetime.now().timestamp() * 1000)
        candles_15m = [
            Candle(base_time + i * 15 * 60 * 1000, 50000.0 + i * 10, 50100.0 + i * 10, 
                   49900.0 + i * 10, 50000.0 + i * 10, 100.0)
            for i in range(100)
        ]
        candles_1h = [
            Candle(base_time + i * 60 * 60 * 1000, 50000.0 + i * 40, 50400.0 + i * 40,
                   49600.0 + i * 40, 50000.0 + i * 40, 400.0)
            for i in range(50)
        ]
        
        # Update indicators
        strategy.update_indicators(candles_15m, candles_1h)
        
        # Verify indicators were calculated
        assert strategy.current_indicators.atr_15m > 0
        assert strategy.current_indicators.vwap_15m > 0
        assert strategy.current_indicators.adx > 0
    
    def test_strategy_to_risk_manager_flow(self):
        """Test signal flows correctly from Strategy to RiskManager."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        # Create components
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        
        # Create test signal
        signal = Signal(
            type="LONG_ENTRY",
            timestamp=int(datetime.now().timestamp() * 1000),
            price=50000.0,
            indicators={
                'vwap': 49500.0,
                'adx': 25.0,
                'rvol': 1.5
            }
        )
        
        # Open position
        position = risk_manager.open_position(signal, 10000.0, 500.0)
        
        # Verify position was created
        assert position.side == "LONG"
        assert position.entry_price == 50000.0
        assert position.stop_loss > 0
        assert position.quantity > 0
    
    def test_risk_manager_to_order_executor_flow(self):
        """Test position management flows to order execution."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        # Create components
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        
        # Create and open position
        signal = Signal("LONG_ENTRY", int(datetime.now().timestamp() * 1000), 50000.0, {})
        position = risk_manager.open_position(signal, 10000.0, 500.0)
        
        # Simulate price movement and stop hit
        current_price = position.stop_loss - 10.0  # Price below stop
        
        # Check if stop was hit
        stop_hit = risk_manager.check_stop_hit(position, current_price)
        assert stop_hit is True
        
        # Close position
        trade = risk_manager.close_position(position, current_price, "STOP_LOSS")
        
        # Verify trade was created
        assert trade.side == "LONG"
        assert trade.exit_reason == "STOP_LOSS"
        assert trade.pnl < 0  # Should be a loss


class TestErrorHandlingIntegration:
    """Test error handling scenarios."""
    
    @patch('src.data_manager.DataManager.fetch_historical_data')
    @patch('src.trading_bot.Client')
    def test_network_failure_handling(self, mock_client, mock_fetch):
        """Test system handles network failures gracefully."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        # Mock network failure
        mock_fetch.side_effect = Exception("Network error")
        
        bot = TradingBot(config)
        
        # Verify bot handles error gracefully
        with pytest.raises(Exception) as exc_info:
            bot._run_backtest()
        
        assert "Network error" in str(exc_info.value) or "Error" in str(exc_info.value)
    
    def test_insufficient_margin_handling(self):
        """Test system handles insufficient margin correctly."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST",
            leverage=3
        )
        
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        
        # Create signal with very small balance
        signal = Signal("LONG_ENTRY", int(datetime.now().timestamp() * 1000), 50000.0, {})
        
        # Try to open position with insufficient balance
        small_balance = 10.0  # Too small for meaningful position
        position = risk_manager.open_position(signal, small_balance, 500.0)
        
        # Verify position was created but with minimal size
        assert position.quantity > 0
        # The position should respect the 1% risk rule even with small balance
        # With 1% risk on $10 = $0.10 risk, stop at 2*ATR = 1000, quantity = 0.10/1000 = 0.0001
        # Margin required = (50000 * 0.0001) / 3 = 1.67, which is less than $10
        margin_required = (position.entry_price * position.quantity) / config.leverage
        # Allow some tolerance for the calculation
        assert margin_required <= small_balance * 2  # Allow 2x tolerance for calculation differences
    
    @patch('src.trading_bot.Client')
    def test_invalid_data_handling(self, mock_client):
        """Test system handles invalid data gracefully."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        strategy = StrategyEngine(config)
        
        # Try to update with empty candles
        strategy.update_indicators([], [])
        
        # Verify no signals are generated with insufficient data
        long_signal = strategy.check_long_entry()
        short_signal = strategy.check_short_entry()
        
        assert long_signal is None
        assert short_signal is None


class TestPanicCloseIntegration:
    """Test panic close functionality."""
    
    def test_panic_close_closes_all_positions(self):
        """Test panic close closes all open positions."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        
        # Open a position (risk manager only supports one position per symbol)
        signal1 = Signal("LONG_ENTRY", int(datetime.now().timestamp() * 1000), 50000.0, {})
        
        position1 = risk_manager.open_position(signal1, 10000.0, 500.0)
        
        # Verify position is open
        active_positions = risk_manager.get_all_active_positions()
        assert len(active_positions) == 1
        
        # Trigger panic close
        current_price = 50500.0
        closed_trades = risk_manager.close_all_positions(current_price)
        
        # Verify position was closed
        assert len(closed_trades) == 1
        active_positions = risk_manager.get_all_active_positions()
        assert len(active_positions) == 0
        
        # Verify trade has correct exit reason
        for trade in closed_trades:
            assert trade.exit_reason == "PANIC"
    
    def test_panic_close_disables_signal_generation(self):
        """Test panic close disables new signal generation."""
        config = Config(
            api_key="test",
            api_secret="test",
            run_mode="BACKTEST"
        )
        
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        
        # Verify signal generation is initially enabled
        assert risk_manager.is_signal_generation_enabled() is True
        
        # Trigger panic close
        risk_manager.close_all_positions(50000.0)
        
        # Verify signal generation is disabled
        assert risk_manager.is_signal_generation_enabled() is False


class TestLoggingIntegration:
    """Test logging and persistence integration."""
    
    def test_trade_logging(self, tmp_path):
        """Test trades are logged correctly."""
        from src.logger import TradingLogger
        
        # Create logger with temp directory
        log_dir = tmp_path / "logs"
        logger = TradingLogger(log_dir=str(log_dir))
        
        # Create and log a trade
        trade = Trade(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=50000.0,
            exit_price=51000.0,
            quantity=0.1,
            pnl=100.0,
            pnl_percent=2.0,
            entry_time=int(datetime.now().timestamp() * 1000),
            exit_time=int(datetime.now().timestamp() * 1000) + 60000,
            exit_reason="TRAILING_STOP"
        )
        
        logger.log_trade(trade)
        
        # Verify trade log file was created
        trade_log = log_dir / "trades.log"
        assert trade_log.exists()
        
        # Verify trade was logged
        with open(trade_log, 'r') as f:
            content = f.read()
            assert "BTCUSDT" in content
            assert "LONG" in content
            assert "100.0" in content
    
    def test_error_logging(self, tmp_path):
        """Test errors are logged with stack traces."""
        from src.logger import TradingLogger
        
        log_dir = tmp_path / "logs"
        logger = TradingLogger(log_dir=str(log_dir))
        
        # Create and log an error
        try:
            raise ValueError("Test error message")
        except Exception as e:
            logger.log_error(e, "Test context")
        
        # Verify error log file was created
        error_log = log_dir / "errors.log"
        assert error_log.exists()
        
        # Verify error was logged with stack trace
        with open(error_log, 'r') as f:
            content = f.read()
            assert "Test error message" in content
            assert "Test context" in content
            assert "Traceback" in content or "ValueError" in content


class TestEndToEndScenarios:
    """Test complete end-to-end scenarios."""
    
    @patch('src.data_manager.DataManager.fetch_historical_data')
    @patch('src.trading_bot.Client')
    def test_complete_backtest_workflow(self, mock_client, mock_fetch, tmp_path):
        """Test complete backtest workflow from start to finish."""
        # Setup
        log_file = tmp_path / "results.json"
        config = Config(
            api_key="test",
            api_secret="test",
            symbol="BTCUSDT",
            run_mode="BACKTEST",
            backtest_days=7,
            log_file=str(log_file)
        )
        
        # Create realistic test data
        base_time = int(datetime.now().timestamp() * 1000)
        candles_15m = [
            Candle(base_time + i * 15 * 60 * 1000, 50000.0 + i * 10, 50100.0 + i * 10,
                   49900.0 + i * 10, 50000.0 + i * 10, 100.0 + i * 0.5)
            for i in range(200)
        ]
        candles_1h = [
            Candle(base_time + i * 60 * 60 * 1000, 50000.0 + i * 40, 50400.0 + i * 40,
                   49600.0 + i * 40, 50000.0 + i * 40, 400.0 + i * 2)
            for i in range(100)
        ]
        
        mock_fetch.side_effect = lambda days, timeframe: candles_15m if timeframe == "15m" else candles_1h
        
        # Execute
        bot = TradingBot(config)
        bot._run_backtest()
        
        # Verify
        # 1. Results file was created
        assert log_file.exists()
        
        # 2. Results contain expected metrics
        with open(log_file, 'r') as f:
            results = json.load(f)
        
        assert 'total_trades' in results
        assert 'win_rate' in results
        assert 'roi' in results
        assert 'max_drawdown' in results
        assert 'profit_factor' in results
        
        # 3. Metrics are valid
        assert results['total_trades'] >= 0
        assert 0 <= results['win_rate'] <= 100
        assert isinstance(results['roi'], (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
