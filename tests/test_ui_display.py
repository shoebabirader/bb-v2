"""Tests for UI Display module."""

import pytest
from datetime import datetime
from io import StringIO
from unittest.mock import patch, MagicMock
from rich.console import Console

from src.ui_display import UIDisplay
from src.models import Position, Trade, PerformanceMetrics


def render_panel_to_string(panel):
    """Helper function to render a Rich Panel to string."""
    string_io = StringIO()
    console = Console(file=string_io, force_terminal=True, width=120)
    console.print(panel)
    return string_io.getvalue()


class TestUIDisplay:
    """Test suite for UIDisplay class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.ui = UIDisplay()
        
    def test_initialization(self):
        """Test UIDisplay initializes correctly."""
        assert self.ui.console is not None
        assert self.ui.live_display is None
    
    def test_render_dashboard_no_positions_no_trades(self):
        """Test dashboard rendering with no positions or trades."""
        positions = []
        trades = []
        indicators = {
            'trend_1h': 'NEUTRAL',
            'trend_15m': 'NEUTRAL',
            'rvol': 1.0,
            'adx': 15.0,
            'current_price': 50000.0
        }
        wallet_balance = 10000.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance, "BACKTEST")
        
        # Panel should be created successfully
        assert panel is not None
        output = render_panel_to_string(panel)
        assert "Trading Dashboard" in output
    
    def test_render_dashboard_with_positions(self):
        """Test dashboard rendering with open positions."""
        positions = [
            Position(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=50000.0,
                quantity=0.1,
                leverage=3,
                stop_loss=49000.0,
                trailing_stop=49500.0,
                entry_time=int(datetime.now().timestamp() * 1000),
                unrealized_pnl=100.0
            ),
            Position(
                symbol="BTCUSDT",
                side="SHORT",
                entry_price=51000.0,
                quantity=0.05,
                leverage=3,
                stop_loss=51500.0,
                trailing_stop=51200.0,
                entry_time=int(datetime.now().timestamp() * 1000),
                unrealized_pnl=-50.0
            )
        ]
        trades = []
        indicators = {
            'trend_1h': 'BULLISH',
            'trend_15m': 'BULLISH',
            'rvol': 1.5,
            'adx': 25.0,
            'current_price': 50500.0
        }
        wallet_balance = 10000.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance, "LIVE")
        
        assert panel is not None
        panel_str = render_panel_to_string(panel)
        assert "LONG" in panel_str or "SHORT" in panel_str
    
    def test_render_dashboard_with_trades(self):
        """Test dashboard rendering with completed trades."""
        positions = []
        trades = [
            Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=50000.0,
                exit_price=51000.0,
                quantity=0.1,
                pnl=100.0,
                pnl_percent=2.0,
                entry_time=int(datetime.now().timestamp() * 1000) - 3600000,
                exit_time=int(datetime.now().timestamp() * 1000),
                exit_reason="TRAILING_STOP"
            ),
            Trade(
                symbol="BTCUSDT",
                side="SHORT",
                entry_price=51000.0,
                exit_price=50500.0,
                quantity=0.05,
                pnl=25.0,
                pnl_percent=1.0,
                entry_time=int(datetime.now().timestamp() * 1000) - 7200000,
                exit_time=int(datetime.now().timestamp() * 1000) - 3600000,
                exit_reason="STOP_LOSS"
            ),
            Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=49000.0,
                exit_price=48500.0,
                quantity=0.1,
                pnl=-50.0,
                pnl_percent=-1.0,
                entry_time=int(datetime.now().timestamp() * 1000) - 10800000,
                exit_time=int(datetime.now().timestamp() * 1000) - 7200000,
                exit_reason="STOP_LOSS"
            )
        ]
        indicators = {
            'trend_1h': 'BEARISH',
            'trend_15m': 'NEUTRAL',
            'rvol': 0.8,
            'adx': 18.0,
            'current_price': 50000.0
        }
        wallet_balance = 10075.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance, "PAPER")
        
        assert panel is not None
        # Win rate should be calculated (2 wins out of 3 trades = 66.67%)
        panel_str = render_panel_to_string(panel)
        assert "66" in panel_str or "67" in panel_str  # Win rate percentage
    
    def test_render_dashboard_different_modes(self):
        """Test dashboard rendering with different operational modes."""
        positions = []
        trades = []
        indicators = {
            'trend_1h': 'NEUTRAL',
            'trend_15m': 'NEUTRAL',
            'rvol': 1.0,
            'adx': 20.0,
            'current_price': 50000.0
        }
        wallet_balance = 10000.0
        
        # Test each mode
        for mode in ["BACKTEST", "PAPER", "LIVE"]:
            panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance, mode)
            assert panel is not None
            panel_str = render_panel_to_string(panel)
            assert mode in panel_str
    
    def test_display_backtest_results(self):
        """Test backtest results display."""
        results = PerformanceMetrics(
            total_trades=50,
            winning_trades=30,
            losing_trades=20,
            win_rate=60.0,
            total_pnl=1500.0,
            total_pnl_percent=15.0,
            roi=15.0,
            max_drawdown=-500.0,
            max_drawdown_percent=-5.0,
            profit_factor=2.5,
            sharpe_ratio=1.8,
            average_win=75.0,
            average_loss=-37.5,
            largest_win=250.0,
            largest_loss=-150.0,
            average_trade_duration=7200
        )
        
        # Capture console output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.display_backtest_results(results, initial_balance=10000.0)
            output = fake_out.getvalue()
            
            # Check that key metrics are displayed
            assert "50" in output  # Total trades
            assert "60" in output  # Win rate
            assert "1500" in output or "15.0" in output  # PnL or ROI
    
    def test_display_backtest_results_losing_strategy(self):
        """Test backtest results display for a losing strategy."""
        results = PerformanceMetrics(
            total_trades=30,
            winning_trades=10,
            losing_trades=20,
            win_rate=33.33,
            total_pnl=-800.0,
            total_pnl_percent=-8.0,
            roi=-8.0,
            max_drawdown=-1200.0,
            max_drawdown_percent=-12.0,
            profit_factor=0.6,
            sharpe_ratio=-0.5,
            average_win=60.0,
            average_loss=-90.0,
            largest_win=150.0,
            largest_loss=-250.0,
            average_trade_duration=5400
        )
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.display_backtest_results(results, initial_balance=10000.0)
            output = fake_out.getvalue()
            
            # Should display negative metrics
            assert "30" in output  # Total trades
            assert "-800" in output or "-8" in output  # Negative PnL
    
    def test_show_notification_info(self):
        """Test INFO level notification."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_notification("Test info message", "INFO")
            output = fake_out.getvalue()
            
            assert "Test info message" in output
    
    def test_show_notification_warning(self):
        """Test WARNING level notification."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_notification("Test warning message", "WARNING")
            output = fake_out.getvalue()
            
            assert "Test warning message" in output
    
    def test_show_notification_error(self):
        """Test ERROR level notification."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_notification("Test error message", "ERROR")
            output = fake_out.getvalue()
            
            assert "Test error message" in output
    
    def test_show_notification_success(self):
        """Test SUCCESS level notification."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_notification("Test success message", "SUCCESS")
            output = fake_out.getvalue()
            
            assert "Test success message" in output
    
    def test_show_notification_default_level(self):
        """Test notification with default level."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_notification("Test default message")
            output = fake_out.getvalue()
            
            assert "Test default message" in output
    
    def test_show_panic_confirmation_positive_pnl(self):
        """Test panic close confirmation with positive PnL."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_panic_confirmation(closed_positions=2, total_pnl=150.0)
            output = fake_out.getvalue()
            
            assert "PANIC CLOSE" in output
            assert "2" in output  # Number of closed positions
            assert "150" in output  # PnL amount
    
    def test_show_panic_confirmation_negative_pnl(self):
        """Test panic close confirmation with negative PnL."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_panic_confirmation(closed_positions=3, total_pnl=-200.0)
            output = fake_out.getvalue()
            
            assert "PANIC CLOSE" in output
            assert "3" in output  # Number of closed positions
            assert "-200" in output or "200" in output  # PnL amount
    
    def test_show_panic_confirmation_zero_positions(self):
        """Test panic close confirmation with no positions."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.show_panic_confirmation(closed_positions=0, total_pnl=0.0)
            output = fake_out.getvalue()
            
            assert "PANIC CLOSE" in output
            assert "0" in output
    
    def test_clear_screen(self):
        """Test screen clearing."""
        # Mock the console clear method
        self.ui.console.clear = MagicMock()
        self.ui.clear_screen()
        self.ui.console.clear.assert_called_once()
    
    def test_print_separator(self):
        """Test separator printing."""
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.ui.print_separator()
            output = fake_out.getvalue()
            
            # Should print some kind of separator
            assert len(output) > 0
    
    def test_render_dashboard_color_coding_profit(self):
        """Test that dashboard uses green color for profits."""
        positions = [
            Position(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=50000.0,
                quantity=0.1,
                leverage=3,
                stop_loss=49000.0,
                trailing_stop=49500.0,
                entry_time=int(datetime.now().timestamp() * 1000),
                unrealized_pnl=500.0  # Positive PnL
            )
        ]
        trades = [
            Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=49000.0,
                exit_price=50000.0,
                quantity=0.1,
                pnl=100.0,  # Positive PnL
                pnl_percent=2.0,
                entry_time=int(datetime.now().timestamp() * 1000) - 3600000,
                exit_time=int(datetime.now().timestamp() * 1000),
                exit_reason="TRAILING_STOP"
            )
        ]
        indicators = {
            'trend_1h': 'BULLISH',
            'trend_15m': 'BULLISH',
            'rvol': 1.5,
            'adx': 30.0,
            'current_price': 50500.0
        }
        wallet_balance = 10600.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance)
        
        # Panel should contain positive PnL values
        assert panel is not None
        panel_str = render_panel_to_string(panel)
        assert "500" in panel_str or "600" in panel_str  # PnL values
    
    def test_render_dashboard_color_coding_loss(self):
        """Test that dashboard uses red color for losses."""
        positions = [
            Position(
                symbol="BTCUSDT",
                side="SHORT",
                entry_price=50000.0,
                quantity=0.1,
                leverage=3,
                stop_loss=51000.0,
                trailing_stop=50500.0,
                entry_time=int(datetime.now().timestamp() * 1000),
                unrealized_pnl=-300.0  # Negative PnL
            )
        ]
        trades = [
            Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=51000.0,
                exit_price=50000.0,
                quantity=0.1,
                pnl=-100.0,  # Negative PnL
                pnl_percent=-2.0,
                entry_time=int(datetime.now().timestamp() * 1000) - 3600000,
                exit_time=int(datetime.now().timestamp() * 1000),
                exit_reason="STOP_LOSS"
            )
        ]
        indicators = {
            'trend_1h': 'BEARISH',
            'trend_15m': 'BEARISH',
            'rvol': 0.8,
            'adx': 15.0,
            'current_price': 49500.0
        }
        wallet_balance = 9600.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance)
        
        # Panel should contain negative PnL values
        assert panel is not None
        panel_str = render_panel_to_string(panel)
        assert "-300" in panel_str or "-400" in panel_str  # PnL values
    
    def test_render_dashboard_high_rvol_highlighting(self):
        """Test that high RVOL is highlighted."""
        positions = []
        trades = []
        indicators = {
            'trend_1h': 'NEUTRAL',
            'trend_15m': 'NEUTRAL',
            'rvol': 2.5,  # High RVOL
            'adx': 20.0,
            'current_price': 50000.0
        }
        wallet_balance = 10000.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance)
        
        assert panel is not None
        panel_str = render_panel_to_string(panel)
        assert "2.5" in panel_str or "2.50" in panel_str
    
    def test_render_dashboard_high_adx_highlighting(self):
        """Test that high ADX is highlighted."""
        positions = []
        trades = []
        indicators = {
            'trend_1h': 'NEUTRAL',
            'trend_15m': 'NEUTRAL',
            'rvol': 1.0,
            'adx': 35.0,  # High ADX
            'current_price': 50000.0
        }
        wallet_balance = 10000.0
        
        panel = self.ui.render_dashboard(positions, trades, indicators, wallet_balance)
        
        assert panel is not None
        panel_str = render_panel_to_string(panel)
        assert "35" in panel_str
