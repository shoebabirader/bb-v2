"""Main Trading Bot orchestration class for Binance Futures Trading Bot.

This module provides the main TradingBot class that coordinates all subsystems
and implements the main event loop for real-time trading.
"""

import time
import logging
import signal
import sys
from typing import Optional
from binance.client import Client
from pynput import keyboard

from src.config import Config
from src.data_manager import DataManager
from src.strategy import StrategyEngine
from src.risk_manager import RiskManager
from src.position_sizer import PositionSizer
from src.order_executor import OrderExecutor
from src.ui_display import UIDisplay
from src.backtest_engine import BacktestEngine
from src.logger import get_logger, TradingLogger
from src.models import PerformanceMetrics


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator.
    
    Coordinates all subsystems:
    - Data management (historical and real-time)
    - Strategy engine (signal generation)
    - Risk management (position sizing and stops)
    - Order execution (Binance API integration)
    - UI display (terminal dashboard)
    - Logging and persistence
    
    Supports three operational modes:
    - BACKTEST: Simulate strategy on historical data
    - PAPER: Real-time trading with simulated execution
    - LIVE: Real-time trading with actual order execution
    """
    
    def __init__(self, config: Config):
        """Initialize TradingBot with configuration.
        
        Args:
            config: Configuration object with all parameters
        """
        self.config = config
        self.running = False
        self._panic_triggered = False
        
        # Initialize logger
        self.logger = get_logger()
        
        # Initialize Binance client (needed for all modes to fetch data)
        self.client: Optional[Client] = None
        if config.api_key and config.api_secret:
            self.client = Client(config.api_key, config.api_secret)
            logger.info("Binance client initialized")
        elif config.run_mode in ["PAPER", "LIVE"]:
            raise ValueError("API keys required for PAPER and LIVE modes")
        
        # Initialize subsystems
        self.data_manager = DataManager(config, self.client)
        self.strategy = StrategyEngine(config)
        self.position_sizer = PositionSizer(config)
        self.risk_manager = RiskManager(config, self.position_sizer)
        self.order_executor = OrderExecutor(config, self.client)
        self.ui_display = UIDisplay()
        
        # Initialize backtest engine (only for BACKTEST mode)
        self.backtest_engine: Optional[BacktestEngine] = None
        if config.run_mode == "BACKTEST":
            self.backtest_engine = BacktestEngine(config, self.strategy, self.risk_manager)
        
        # Keyboard listener for panic close
        self.keyboard_listener: Optional[keyboard.Listener] = None
        
        # Wallet balance tracking
        self.wallet_balance = 10000.0  # Default for backtest/paper
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"TradingBot initialized in {config.run_mode} mode")
    
    def start(self):
        """Start the trading bot based on configured mode.
        
        Routes to appropriate execution method based on run_mode:
        - BACKTEST: Run backtest on historical data
        - PAPER: Start paper trading with real-time data
        - LIVE: Start live trading with real execution
        """
        self.logger.log_system_event(f"Starting TradingBot in {self.config.run_mode} mode")
        
        try:
            if self.config.run_mode == "BACKTEST":
                self._run_backtest()
            elif self.config.run_mode == "PAPER":
                self._run_paper_trading()
            elif self.config.run_mode == "LIVE":
                self._run_live_trading()
            else:
                raise ValueError(f"Invalid run_mode: {self.config.run_mode}")
        
        except Exception as e:
            self.logger.log_error(e, "Error in TradingBot.start()")
            self.ui_display.show_notification(f"Fatal error: {str(e)}", "ERROR")
            raise
        
        finally:
            self._shutdown()
    
    def _run_backtest(self):
        """Run backtest mode on historical data."""
        self.ui_display.show_notification("Starting backtest mode...", "INFO")
        
        try:
            # Fetch historical data
            self.ui_display.show_notification(
                f"Fetching {self.config.backtest_days} days of historical data...",
                "INFO"
            )
            
            candles_15m = self.data_manager.fetch_historical_data(
                days=self.config.backtest_days,
                timeframe="15m"
            )
            
            candles_1h = self.data_manager.fetch_historical_data(
                days=self.config.backtest_days,
                timeframe="1h"
            )
            
            self.ui_display.show_notification(
                f"Fetched {len(candles_15m)} 15m candles and {len(candles_1h)} 1h candles",
                "SUCCESS"
            )
            
            # Run backtest
            self.ui_display.show_notification("Running backtest...", "INFO")
            
            results = self.backtest_engine.run_backtest(
                candles_15m=candles_15m,
                candles_1h=candles_1h,
                initial_balance=self.wallet_balance
            )
            
            # Convert results dict to PerformanceMetrics
            metrics = PerformanceMetrics(
                total_trades=results['total_trades'],
                winning_trades=results['winning_trades'],
                losing_trades=results['losing_trades'],
                win_rate=results['win_rate'],
                total_pnl=results['total_pnl'],
                roi=results['roi'],
                max_drawdown=results['max_drawdown'],
                profit_factor=results['profit_factor'],
                sharpe_ratio=results['sharpe_ratio'],
                average_win=results['average_win'],
                average_loss=results['average_loss'],
                largest_win=results['largest_win'],
                largest_loss=results['largest_loss'],
                average_trade_duration=results['average_trade_duration']
            )
            
            # Display results
            self.ui_display.display_backtest_results(metrics, self.wallet_balance)
            
            # Save results
            self.logger.save_performance_metrics(metrics, self.config.log_file)
            self.ui_display.show_notification(
                f"Results saved to {self.config.log_file}",
                "SUCCESS"
            )
            
            # Log all trades
            for trade in self.backtest_engine.get_trades():
                self.logger.log_trade(trade)
        
        except Exception as e:
            self.logger.log_error(e, "Error during backtest execution")
            self.ui_display.show_notification(f"Backtest error: {str(e)}", "ERROR")
            raise
    
    def _run_paper_trading(self):
        """Run paper trading mode with real-time data but simulated execution."""
        self.ui_display.show_notification("Starting paper trading mode...", "INFO")
        
        try:
            # Get initial balance
            self.wallet_balance = self.order_executor.get_account_balance()
            self.ui_display.show_notification(
                f"Initial balance: ${self.wallet_balance:.2f}",
                "INFO"
            )
            
            # Fetch initial historical data for indicators
            self.ui_display.show_notification("Fetching initial historical data...", "INFO")
            
            self.data_manager.fetch_historical_data(days=7, timeframe="15m")
            self.data_manager.fetch_historical_data(days=7, timeframe="1h")
            
            # Start WebSocket streams
            self.ui_display.show_notification("Starting WebSocket streams...", "INFO")
            self.data_manager.start_websocket_streams()
            
            # Start keyboard listener for panic close
            self._start_keyboard_listener()
            
            # Run main event loop
            self._run_event_loop(simulate_execution=True)
        
        except Exception as e:
            self.logger.log_error(e, "Error during paper trading")
            self.ui_display.show_notification(f"Paper trading error: {str(e)}", "ERROR")
            raise
    
    def _run_live_trading(self):
        """Run live trading mode with real execution."""
        self.ui_display.show_notification("Starting LIVE trading mode...", "WARNING")
        self.ui_display.show_notification("⚠️  REAL MONEY AT RISK ⚠️", "ERROR")
        
        try:
            # Configure leverage and margin type
            self.ui_display.show_notification("Configuring leverage and margin...", "INFO")
            
            self.order_executor.set_leverage(self.config.symbol, self.config.leverage)
            self.order_executor.set_margin_type(self.config.symbol, "ISOLATED")
            
            # Get initial balance
            self.wallet_balance = self.order_executor.get_account_balance()
            self.ui_display.show_notification(
                f"Initial balance: ${self.wallet_balance:.2f}",
                "INFO"
            )
            
            # Fetch initial historical data for indicators
            self.ui_display.show_notification("Fetching initial historical data...", "INFO")
            
            self.data_manager.fetch_historical_data(days=7, timeframe="15m")
            self.data_manager.fetch_historical_data(days=7, timeframe="1h")
            
            # Start WebSocket streams
            self.ui_display.show_notification("Starting WebSocket streams...", "INFO")
            self.data_manager.start_websocket_streams()
            
            # Start keyboard listener for panic close
            self._start_keyboard_listener()
            
            # Run main event loop
            self._run_event_loop(simulate_execution=False)
        
        except Exception as e:
            self.logger.log_error(e, "Error during live trading")
            self.ui_display.show_notification(f"Live trading error: {str(e)}", "ERROR")
            raise
    
    def _run_event_loop(self, simulate_execution: bool = False):
        """Main event loop for real-time trading.
        
        Args:
            simulate_execution: If True, simulate order execution (paper trading)
        """
        self.running = True
        self.ui_display.show_notification("Trading bot is now running", "SUCCESS")
        self.ui_display.show_notification("Press ESC to panic close all positions", "WARNING")
        
        last_update_time = time.time()
        update_interval = 1.0  # Update dashboard every 1 second
        
        try:
            while self.running and not self._panic_triggered:
                current_time = time.time()
                
                # Update dashboard at regular intervals
                if current_time - last_update_time >= update_interval:
                    self._update_dashboard()
                    last_update_time = current_time
                
                # Get latest candles
                candles_15m = self.data_manager.get_latest_candles("15m", 200)
                candles_1h = self.data_manager.get_latest_candles("1h", 100)
                
                # Check if we have sufficient data
                if len(candles_15m) < 50 or len(candles_1h) < 30:
                    time.sleep(1)
                    continue
                
                # Update indicators
                self.strategy.update_indicators(candles_15m, candles_1h)
                
                # Get current price
                current_price = candles_15m[-1].close if candles_15m else 0.0
                
                # Check for active position
                active_position = self.risk_manager.get_active_position(self.config.symbol)
                
                if active_position:
                    # Update stops
                    atr = self.strategy.current_indicators.atr_15m
                    self.risk_manager.update_stops(active_position, current_price, atr)
                    
                    # Check if stop was hit
                    if self.risk_manager.check_stop_hit(active_position, current_price):
                        # Close position
                        trade = self.risk_manager.close_position(
                            active_position,
                            current_price,
                            "TRAILING_STOP"
                        )
                        
                        # Execute close order (if not simulating)
                        if not simulate_execution:
                            side = "SELL" if active_position.side == "LONG" else "BUY"
                            self.order_executor.place_market_order(
                                symbol=self.config.symbol,
                                side=side,
                                quantity=active_position.quantity,
                                reduce_only=True
                            )
                        
                        # Update balance
                        self.wallet_balance += trade.pnl
                        
                        # Log trade
                        self.logger.log_trade(trade)
                        
                        # Show notification
                        pnl_text = f"+${trade.pnl:.2f}" if trade.pnl >= 0 else f"${trade.pnl:.2f}"
                        self.ui_display.show_notification(
                            f"Position closed: {trade.side} @ ${trade.exit_price:.2f} | PnL: {pnl_text}",
                            "SUCCESS" if trade.pnl >= 0 else "WARNING"
                        )
                
                else:
                    # No active position, check for entry signals
                    if self.risk_manager.is_signal_generation_enabled():
                        long_signal = self.strategy.check_long_entry()
                        short_signal = self.strategy.check_short_entry()
                        
                        signal = long_signal or short_signal
                        
                        if signal:
                            # Open position
                            atr = self.strategy.current_indicators.atr_15m
                            position = self.risk_manager.open_position(
                                signal,
                                self.wallet_balance,
                                atr
                            )
                            
                            # Execute entry order (if not simulating)
                            if not simulate_execution:
                                # Validate margin availability
                                margin_required = (position.entry_price * position.quantity) / position.leverage
                                
                                if self.order_executor.validate_margin_availability(
                                    self.config.symbol,
                                    margin_required
                                ):
                                    side = "BUY" if position.side == "LONG" else "SELL"
                                    self.order_executor.place_market_order(
                                        symbol=self.config.symbol,
                                        side=side,
                                        quantity=position.quantity
                                    )
                                else:
                                    # Insufficient margin, close position
                                    self.risk_manager.close_position(
                                        position,
                                        current_price,
                                        "SIGNAL_EXIT"
                                    )
                                    self.ui_display.show_notification(
                                        "Insufficient margin for trade",
                                        "ERROR"
                                    )
                                    continue
                            
                            # Show notification
                            self.ui_display.show_notification(
                                f"Position opened: {position.side} @ ${position.entry_price:.2f}",
                                "SUCCESS"
                            )
                
                # Sleep briefly to avoid busy-waiting
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            self.ui_display.show_notification("Keyboard interrupt received", "WARNING")
        
        except Exception as e:
            self.logger.log_error(e, "Error in main event loop")
            self.ui_display.show_notification(f"Event loop error: {str(e)}", "ERROR")
            raise
    
    def _update_dashboard(self):
        """Update the terminal dashboard with current state."""
        try:
            # Get active positions and trades
            positions = self.risk_manager.get_all_active_positions()
            trades = self.risk_manager.get_closed_trades()
            
            # Get current indicators
            indicators = self.strategy.get_indicator_snapshot()
            
            # Render dashboard
            dashboard = self.ui_display.render_dashboard(
                positions=positions,
                trades=trades,
                indicators=indicators,
                wallet_balance=self.wallet_balance,
                mode=self.config.run_mode
            )
            
            # Clear screen and print dashboard
            self.ui_display.clear_screen()
            self.ui_display.console.print(dashboard)
        
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
    
    def _start_keyboard_listener(self):
        """Start keyboard listener for panic close (ESC key)."""
        def on_press(key):
            try:
                if key == keyboard.Key.esc:
                    self._trigger_panic_close()
            except Exception as e:
                logger.error(f"Error in keyboard listener: {e}")
        
        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()
        logger.info("Keyboard listener started (ESC for panic close)")
    
    def _trigger_panic_close(self):
        """Trigger emergency panic close of all positions."""
        if self._panic_triggered:
            return  # Already triggered
        
        self._panic_triggered = True
        self.ui_display.show_notification("🚨 PANIC CLOSE TRIGGERED 🚨", "ERROR")
        
        try:
            # Get current price
            candles_15m = self.data_manager.get_latest_candles("15m", 1)
            current_price = candles_15m[-1].close if candles_15m else 0.0
            
            # Close all positions
            closed_trades = self.risk_manager.close_all_positions(current_price)
            
            # Execute close orders (if in LIVE mode)
            if self.config.run_mode == "LIVE":
                for trade in closed_trades:
                    side = "SELL" if trade.side == "LONG" else "BUY"
                    # Note: In production, we'd need to get the actual position quantity
                    # For now, we use the trade quantity
                    self.order_executor.place_market_order(
                        symbol=self.config.symbol,
                        side=side,
                        quantity=trade.quantity,
                        reduce_only=True
                    )
            
            # Calculate total PnL
            total_pnl = sum(trade.pnl for trade in closed_trades)
            
            # Update balance
            self.wallet_balance += total_pnl
            
            # Log all trades
            for trade in closed_trades:
                self.logger.log_trade(trade)
            
            # Show confirmation
            self.ui_display.show_panic_confirmation(len(closed_trades), total_pnl)
            
            # Stop the bot
            self.running = False
        
        except Exception as e:
            self.logger.log_error(e, "Error during panic close")
            self.ui_display.show_notification(f"Panic close error: {str(e)}", "ERROR")
    
    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def _shutdown(self):
        """Perform graceful shutdown and cleanup."""
        self.logger.log_system_event("Initiating graceful shutdown")
        self.ui_display.show_notification("Shutting down...", "INFO")
        
        try:
            # Stop keyboard listener
            if self.keyboard_listener is not None:
                self.keyboard_listener.stop()
                logger.info("Keyboard listener stopped")
            
            # Stop WebSocket streams
            if self.config.run_mode in ["PAPER", "LIVE"]:
                self.data_manager.stop_websocket_streams()
                logger.info("WebSocket streams stopped")
            
            # Close any remaining positions (if not already closed by panic)
            if not self._panic_triggered:
                active_positions = self.risk_manager.get_all_active_positions()
                if active_positions:
                    self.ui_display.show_notification(
                        f"Closing {len(active_positions)} open position(s)...",
                        "WARNING"
                    )
                    
                    candles_15m = self.data_manager.get_latest_candles("15m", 1)
                    current_price = candles_15m[-1].close if candles_15m else 0.0
                    
                    closed_trades = self.risk_manager.close_all_positions(current_price)
                    
                    # Log trades
                    for trade in closed_trades:
                        self.logger.log_trade(trade)
            
            # Save final performance metrics (if in PAPER or LIVE mode)
            if self.config.run_mode in ["PAPER", "LIVE"]:
                trades = self.risk_manager.get_closed_trades()
                if trades:
                    # Calculate metrics
                    total_trades = len(trades)
                    winning_trades = sum(1 for t in trades if t.pnl > 0)
                    losing_trades = sum(1 for t in trades if t.pnl <= 0)
                    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
                    total_pnl = sum(t.pnl for t in trades)
                    
                    metrics = PerformanceMetrics(
                        total_trades=total_trades,
                        winning_trades=winning_trades,
                        losing_trades=losing_trades,
                        win_rate=win_rate,
                        total_pnl=total_pnl
                    )
                    
                    self.logger.save_performance_metrics(metrics, self.config.log_file)
            
            self.logger.log_system_event("Shutdown complete")
            self.ui_display.show_notification("Shutdown complete", "SUCCESS")
        
        except Exception as e:
            self.logger.log_error(e, "Error during shutdown")
            logger.error(f"Shutdown error: {e}")


def main():
    """Main entry point for the trading bot."""
    try:
        # Load configuration
        config = Config.load_from_file()
        
        # Log applied defaults
        defaults = config.get_applied_defaults()
        if defaults:
            logger.info("Applied default configuration values:")
            for default in defaults:
                logger.info(f"  - {default}")
        
        # Create and start trading bot
        bot = TradingBot(config)
        bot.start()
    
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print(f"\n❌ Configuration Error:\n{e}\n")
        sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal Error:\n{e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
