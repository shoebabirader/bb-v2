"""Example usage of UIDisplay module.

This file demonstrates how to use the UIDisplay class for terminal-based
monitoring of the trading bot.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from src.ui_display import UIDisplay
from src.models import Position, Trade, PerformanceMetrics


def example_live_dashboard():
    """Example of rendering a live trading dashboard."""
    ui = UIDisplay()
    
    # Sample data
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
            unrealized_pnl=150.0
        )
    ]
    
    trades = [
        Trade(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=49000.0,
            exit_price=50000.0,
            quantity=0.1,
            pnl=100.0,
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
        'adx': 25.0,
        'current_price': 50150.0
    }
    
    wallet_balance = 10250.0
    
    # Render dashboard
    panel = ui.render_dashboard(
        positions=positions,
        trades=trades,
        indicators=indicators,
        wallet_balance=wallet_balance,
        mode="LIVE"
    )
    
    # Print the dashboard
    ui.console.print(panel)


def example_backtest_results():
    """Example of displaying backtest results."""
    ui = UIDisplay()
    
    results = PerformanceMetrics(
        total_trades=50,
        winning_trades=32,
        losing_trades=18,
        win_rate=64.0,
        total_pnl=2500.0,
        total_pnl_percent=25.0,
        roi=25.0,
        max_drawdown=-800.0,
        max_drawdown_percent=-8.0,
        profit_factor=2.8,
        sharpe_ratio=1.9,
        average_win=125.0,
        average_loss=-62.5,
        largest_win=450.0,
        largest_loss=-200.0,
        average_trade_duration=7200
    )
    
    ui.display_backtest_results(results, initial_balance=10000.0)


def example_notifications():
    """Example of showing different notification types."""
    ui = UIDisplay()
    
    ui.show_notification("System started successfully", "SUCCESS")
    ui.show_notification("WebSocket connected", "INFO")
    ui.show_notification("High volatility detected", "WARNING")
    ui.show_notification("Order placement failed", "ERROR")


def example_panic_close():
    """Example of panic close confirmation."""
    ui = UIDisplay()
    
    ui.show_panic_confirmation(closed_positions=2, total_pnl=75.0)


if __name__ == "__main__":
    print("\n=== Live Dashboard Example ===")
    example_live_dashboard()
    
    print("\n\n=== Backtest Results Example ===")
    example_backtest_results()
    
    print("\n\n=== Notifications Example ===")
    example_notifications()
    
    print("\n\n=== Panic Close Example ===")
    example_panic_close()
