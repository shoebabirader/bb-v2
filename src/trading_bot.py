"""Main Trading Bot orchestration class for Binance Futures Trading Bot.

This module provides the main TradingBot class that coordinates all subsystems
and implements the main event loop for real-time trading.
"""

import time
import logging
import signal
import sys
from typing import Optional, List, Dict
from binance.client import Client
try:
    from pynput import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    logger.warning("pynput not available - keyboard listener disabled")

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
from src.portfolio_manager import PortfolioManager


# Configure logging with BOTH file and console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler(sys.stdout)  # Print to console
    ]
)
logger = logging.getLogger(__name__)
logger.info("=" * 80)
logger.info("TRADING BOT STARTING")
logger.info("=" * 80)


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
        
        # Initialize portfolio manager (if enabled)
        self.portfolio_manager: Optional[PortfolioManager] = None
        if config.enable_portfolio_management:
            self.portfolio_manager = PortfolioManager(config)
            logger.info(f"Portfolio Manager initialized with {len(config.portfolio_symbols)} symbols")
        
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
    
    def _fetch_multi_symbol_data(self, symbols: List[str], days: int = 7):
        """Fetch historical data for multiple symbols.
        
        Args:
            symbols: List of symbols to fetch data for
            days: Number of days of historical data
        """
        for idx, symbol in enumerate(symbols):
            try:
                # Add delay between symbols to avoid rate limiting (except for first symbol)
                if idx > 0:
                    delay = 0.5  # 500ms delay between symbols
                    logger.info(f"Waiting {delay}s before fetching {symbol} data...")
                    time.sleep(delay)
                
                logger.info(f"Fetching 15m data for {symbol}...")
                candles_15m = self.data_manager.fetch_historical_data(days=days, timeframe="15m", symbol=symbol)
                logger.info(f"  Fetched {len(candles_15m)} candles for {symbol} 15m")
                
                logger.info(f"Fetching 1h data for {symbol}...")
                candles_1h = self.data_manager.fetch_historical_data(days=days, timeframe="1h", symbol=symbol)
                logger.info(f"  Fetched {len(candles_1h)} candles for {symbol} 1h")
                
                # Fetch additional timeframes if multi-timeframe is enabled
                if self.config.enable_multi_timeframe:
                    logger.info(f"Multi-timeframe enabled, fetching 5m data for {symbol}...")
                    candles_5m = self.data_manager.fetch_historical_data(days=days, timeframe="5m", symbol=symbol)
                    logger.info(f"  Fetched {len(candles_5m)} candles for {symbol} 5m")
                    
                    logger.info(f"Multi-timeframe enabled, fetching 4h data for {symbol}...")
                    candles_4h = self.data_manager.fetch_historical_data(days=days, timeframe="4h", symbol=symbol)
                    logger.info(f"  Fetched {len(candles_4h)} candles for {symbol} 4h")
                else:
                    logger.info(f"Multi-timeframe disabled, skipping 5m and 4h data for {symbol}")
                
                logger.info(f"[OK] Fetched historical data for {symbol}")
            except Exception as e:
                logger.error(f"[X] Error fetching data for {symbol}: {e}", exc_info=True)
                raise  # Re-raise to stop execution if data fetch fails
    
    def _get_trading_symbols(self) -> List[str]:
        """Get list of symbols to trade.
        
        Returns:
            List of symbol strings. If portfolio management is enabled,
            returns all portfolio symbols. Otherwise, returns single primary symbol.
        """
        if self.config.enable_portfolio_management and self.portfolio_manager:
            return self.portfolio_manager.symbols
        else:
            return [self.config.symbol]
    
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
            
            # Fetch additional timeframes if multi-timeframe is enabled
            candles_5m = None
            candles_4h = None
            
            if self.config.enable_multi_timeframe:
                self.ui_display.show_notification(
                    "Multi-timeframe enabled: Fetching 5m and 4h data...",
                    "INFO"
                )
                
                candles_5m = self.data_manager.fetch_historical_data(
                    days=self.config.backtest_days,
                    timeframe="5m"
                )
                
                candles_4h = self.data_manager.fetch_historical_data(
                    days=self.config.backtest_days,
                    timeframe="4h"
                )
                
                self.ui_display.show_notification(
                    f"Fetched {len(candles_15m)} 15m, {len(candles_1h)} 1h, "
                    f"{len(candles_5m)} 5m, {len(candles_4h)} 4h candles",
                    "SUCCESS"
                )
            else:
                self.ui_display.show_notification(
                    f"Fetched {len(candles_15m)} 15m candles and {len(candles_1h)} 1h candles",
                    "SUCCESS"
                )
            
            # Run backtest
            self.ui_display.show_notification("Running backtest...", "INFO")
            
            # Use default balance for backtest (don't fetch from real account)
            backtest_balance = 10000.0
            
            results = self.backtest_engine.run_backtest(
                candles_15m=candles_15m,
                candles_1h=candles_1h,
                initial_balance=backtest_balance,
                candles_5m=candles_5m,
                candles_4h=candles_4h
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
            self.ui_display.display_backtest_results(metrics, backtest_balance)
            
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
        
        # Validate API authentication
        if not self.order_executor.validate_authentication():
            raise ValueError("API authentication failed. Check your API keys and permissions.")
        
        # Get list of symbols to trade
        trading_symbols = self._get_trading_symbols()
        
        # Warn if portfolio management is enabled with multiple symbols
        if self.config.enable_portfolio_management and len(trading_symbols) > 1:
            self.ui_display.show_notification(
                f"[OK] Portfolio management enabled with {len(trading_symbols)} symbols: {', '.join(trading_symbols)}",
                "SUCCESS"
            )
            self.ui_display.show_notification(
                f"Portfolio risk limits: Max total risk {self.config.portfolio_max_total_risk:.0%}, "
                f"Max single allocation {self.config.portfolio_max_single_allocation:.0%}",
                "INFO"
            )
        else:
            self.ui_display.show_notification(
                f"Trading single symbol: {self.config.symbol}",
                "INFO"
            )
        
        try:
            # Get initial balance
            self.wallet_balance = self.order_executor.get_account_balance()
            self.ui_display.show_notification(
                f"Initial balance: ${self.wallet_balance:.2f}",
                "INFO"
            )
            
            # Fetch initial historical data for all symbols
            self.ui_display.show_notification(
                f"Fetching initial historical data for {len(trading_symbols)} symbol(s)...",
                "INFO"
            )
            
            self._fetch_multi_symbol_data(trading_symbols, days=7)
            
            # Verify data was fetched successfully and wait if needed
            logger.info("Verifying all symbol data is loaded...")
            all_symbols_ready = True
            
            for symbol in trading_symbols:
                buffer_5m = self.data_manager._symbol_buffers.get(symbol, {}).get('5m', [])
                buffer_4h = self.data_manager._symbol_buffers.get(symbol, {}).get('4h', [])
                buffer_15m = self.data_manager._symbol_buffers.get(symbol, {}).get('15m', [])
                buffer_1h = self.data_manager._symbol_buffers.get(symbol, {}).get('1h', [])
                
                logger.info(f"  {symbol}: 15m={len(buffer_15m)}, 1h={len(buffer_1h)}, 5m={len(buffer_5m)}, 4h={len(buffer_4h)}")
                
                # Check minimum requirements
                if len(buffer_15m) < 50 or len(buffer_1h) < 30:
                    logger.error(f"  [X] {symbol}: Insufficient base timeframe data!")
                    all_symbols_ready = False
                
                # Check multi-timeframe requirements
                if self.config.enable_multi_timeframe:
                    if len(buffer_5m) == 0:
                        logger.error(f"  [X] {symbol}: 5m buffer is EMPTY!")
                        all_symbols_ready = False
                    if len(buffer_4h) == 0:
                        logger.error(f"  [X] {symbol}: 4h buffer is EMPTY!")
                        all_symbols_ready = False
            
            if not all_symbols_ready:
                error_msg = "Failed to load required data for all symbols. Cannot start trading."
                logger.error(error_msg)
                self.ui_display.show_notification(error_msg, "ERROR")
                raise RuntimeError(error_msg)
            
            logger.info("[OK] All symbol data verified successfully")
            self.ui_display.show_notification(
                f"[OK] Data loaded for {len(trading_symbols)} symbol(s)",
                "SUCCESS"
            )
            
            # Start WebSocket streams for all symbols
            self.ui_display.show_notification(
                f"Starting WebSocket streams for {len(trading_symbols)} symbol(s)...",
                "INFO"
            )
            
            for symbol in trading_symbols:
                self.data_manager.start_websocket_streams(symbol=symbol)
                logger.info(f"Started WebSocket for {symbol}")
            
            # Give WebSocket streams time to connect and receive initial data
            self.ui_display.show_notification(
                "Waiting for WebSocket connections to stabilize...",
                "INFO"
            )
            time.sleep(3)  # Wait 3 seconds for WebSocket to connect and receive data
            
            # Start keyboard listener for panic close
            self._start_keyboard_listener()
            
            # Run main event loop
            self._run_event_loop(simulate_execution=True)
        
        except Exception as e:
            self.logger.log_error(e, "Error during paper trading")
            
            # Check if it's a network timeout error
            error_msg = str(e)
            if any(keyword in error_msg.lower() for keyword in ['timeout', 'timed out', 'connection']):
                self.ui_display.show_notification(
                    "Network timeout connecting to Binance API",
                    "ERROR"
                )
                self.ui_display.show_notification(
                    "Possible causes: 1) Slow internet connection, 2) Binance API overloaded, 3) Firewall/VPN issues",
                    "WARNING"
                )
                self.ui_display.show_notification(
                    "Try: 1) Check your internet connection, 2) Wait a few minutes and retry, 3) Disable VPN if using one",
                    "INFO"
                )
            else:
                self.ui_display.show_notification(f"Paper trading error: {str(e)}", "ERROR")
            raise
    
    def _run_live_trading(self):
        """Run live trading mode with real execution."""
        logger.info("=" * 80)
        logger.info("LIVE TRADING MODE ACTIVATED")
        logger.info("[WARNING]  REAL MONEY AT RISK [WARNING]")
        logger.info("=" * 80)
        self.ui_display.show_notification("Starting LIVE trading mode...", "WARNING")
        self.ui_display.show_notification("[WARNING]  REAL MONEY AT RISK [WARNING]", "ERROR")
        
        # Validate API authentication
        if not self.order_executor.validate_authentication():
            raise ValueError("API authentication failed. Check your API keys and permissions.")
        
        # Get list of symbols to trade
        trading_symbols = self._get_trading_symbols()
        
        # Warn if portfolio management is enabled with multiple symbols
        if self.config.enable_portfolio_management and len(trading_symbols) > 1:
            self.ui_display.show_notification(
                f"[OK] Portfolio management enabled with {len(trading_symbols)} symbols: {', '.join(trading_symbols)}",
                "SUCCESS"
            )
            self.ui_display.show_notification(
                f"Portfolio risk limits: Max total risk {self.config.portfolio_max_total_risk:.0%}, "
                f"Max single allocation {self.config.portfolio_max_single_allocation:.0%}",
                "INFO"
            )
        else:
            self.ui_display.show_notification(
                f"Trading single symbol: {self.config.symbol}",
                "INFO"
            )
        
        try:
            # Configure leverage and margin type for all symbols
            self.ui_display.show_notification("Configuring leverage and margin...", "INFO")
            
            for symbol in trading_symbols:
                self.order_executor.set_leverage(symbol, self.config.leverage)
                self.order_executor.set_margin_type(symbol, "ISOLATED")
                logger.info(f"Configured leverage for {symbol}")
            
            # Get initial balance
            self.wallet_balance = self.order_executor.get_account_balance()
            self.ui_display.show_notification(
                f"Initial balance: ${self.wallet_balance:.2f}",
                "INFO"
            )
            
            # Fetch initial historical data for all symbols
            self.ui_display.show_notification(
                f"Fetching initial historical data for {len(trading_symbols)} symbol(s)...",
                "INFO"
            )
            
            self._fetch_multi_symbol_data(trading_symbols, days=7)
            
            # Verify data was fetched successfully
            for symbol in trading_symbols:
                buffer_5m = self.data_manager._symbol_buffers.get(symbol, {}).get('5m', [])
                buffer_4h = self.data_manager._symbol_buffers.get(symbol, {}).get('4h', [])
                buffer_15m = self.data_manager._symbol_buffers.get(symbol, {}).get('15m', [])
                buffer_1h = self.data_manager._symbol_buffers.get(symbol, {}).get('1h', [])
                logger.info(f"Data loaded for {symbol}: 5m={len(buffer_5m)}, 15m={len(buffer_15m)}, 1h={len(buffer_1h)}, 4h={len(buffer_4h)} candles")
            
            # Start WebSocket streams for all symbols
            self.ui_display.show_notification(
                f"Starting WebSocket streams for {len(trading_symbols)} symbol(s)...",
                "INFO"
            )
            
            for symbol in trading_symbols:
                self.data_manager.start_websocket_streams(symbol=symbol)
                logger.info(f"Started WebSocket for {symbol}")
            
            # Give WebSocket streams time to connect and receive initial data
            self.ui_display.show_notification(
                "Waiting for WebSocket connections to stabilize...",
                "INFO"
            )
            time.sleep(3)  # Wait 3 seconds for WebSocket to connect and receive data
            
            # Start keyboard listener for panic close
            self._start_keyboard_listener()
            
            # Run main event loop
            self._run_event_loop(simulate_execution=False)
        
        except Exception as e:
            self.logger.log_error(e, "Error during live trading")
            
            # Check if it's a network timeout error
            error_msg = str(e)
            if any(keyword in error_msg.lower() for keyword in ['timeout', 'timed out', 'connection']):
                self.ui_display.show_notification(
                    "Network timeout connecting to Binance API",
                    "ERROR"
                )
                self.ui_display.show_notification(
                    "Possible causes: 1) Slow internet connection, 2) Binance API overloaded, 3) Firewall/VPN issues",
                    "WARNING"
                )
                self.ui_display.show_notification(
                    "Try: 1) Check your internet connection, 2) Wait a few minutes and retry, 3) Disable VPN if using one",
                    "INFO"
                )
            else:
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
        last_correlation_update = 0
        correlation_update_interval = 3600  # Update correlations every hour
        
        # Get list of symbols to trade
        trading_symbols = self._get_trading_symbols()
        
        try:
            while self.running and not self._panic_triggered:
                current_time = time.time()
                
                # Update dashboard at regular intervals
                if current_time - last_update_time >= update_interval:
                    self._update_dashboard()
                    last_update_time = current_time
                
                # Update correlation matrix if portfolio management is enabled
                if self.portfolio_manager and current_time - last_correlation_update >= correlation_update_interval:
                    self._update_portfolio_correlations(trading_symbols)
                    last_correlation_update = current_time
                
                # Process each symbol
                for symbol in trading_symbols:
                    self._process_symbol(symbol, simulate_execution)
                
                # Rebalance portfolio if enabled
                if self.portfolio_manager:
                    self._rebalance_portfolio(trading_symbols, simulate_execution)
                
                # Sleep briefly to avoid busy-waiting
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            self.ui_display.show_notification("Keyboard interrupt received", "WARNING")
        
        except Exception as e:
            self.logger.log_error(e, "Error in main event loop")
            self.ui_display.show_notification(f"Event loop error: {str(e)}", "ERROR")
            raise
    
    def _update_portfolio_correlations(self, symbols: List[str]):
        """Update correlation matrix for portfolio management.
        
        Args:
            symbols: List of symbols to calculate correlations for
        """
        if not self.portfolio_manager:
            return
        
        try:
            # Collect price data for all symbols
            price_data = {}
            for symbol in symbols:
                # Get 30 days of 1h candles for correlation calculation
                candles = self.data_manager.get_latest_candles("1h", 720, symbol=symbol)  # 30 days
                
                if candles and len(candles) >= 30:
                    price_data[symbol] = candles
            
            # Build correlation matrix
            if len(price_data) >= 2:
                self.portfolio_manager.build_correlation_matrix(price_data)
                logger.info("Updated portfolio correlation matrix")
        
        except Exception as e:
            logger.error(f"Error updating portfolio correlations: {e}")
    
    def _process_symbol(self, symbol: str, simulate_execution: bool):
        """Process trading logic for a single symbol.
        
        Args:
            symbol: Symbol to process
            simulate_execution: If True, simulate order execution
        """
        try:
            # CRITICAL FIX: Fetch FRESH data with use_cache=FALSE to ensure latest market data
            # This prevents the bot from using stale cached data for signal detection
            candles_15m = self.data_manager.fetch_historical_data(days=2, timeframe="15m", symbol=symbol, use_cache=False)
            candles_1h = self.data_manager.fetch_historical_data(days=2, timeframe="1h", symbol=symbol, use_cache=False)
            
            # ALWAYS fetch additional timeframes if configured (regardless of feature manager state)
            # The feature manager controls whether the strategy USES the data, not whether we FETCH it
            candles_5m = None
            candles_4h = None
            
            logger.info(f"[{symbol}] CHECK: enable_multi_timeframe = {self.config.enable_multi_timeframe}")
            
            if self.config.enable_multi_timeframe:
                logger.info(f"[{symbol}] FETCHING 5m and 4h data...")
                candles_5m = self.data_manager.get_latest_candles("5m", 300, symbol=symbol)
                candles_4h = self.data_manager.get_latest_candles("4h", 50, symbol=symbol)
                logger.info(f"[{symbol}] FETCHED 5m={len(candles_5m) if candles_5m else 0}, 4h={len(candles_4h) if candles_4h else 0}")
            else:
                logger.warning(f"[{symbol}] Multi-timeframe is DISABLED in config!")
            
            # Check if we have sufficient data
            if len(candles_15m) < 50 or len(candles_1h) < 30:
                return
            
            # Update indicators (strategy will check feature_manager internally)
            self.strategy.update_indicators(candles_15m, candles_1h, candles_5m, candles_4h)
            
            # Get current price
            current_price = candles_15m[-1].close if candles_15m else 0.0
            
            # Check for active position
            active_position = self.risk_manager.get_active_position(symbol)
            
            if active_position:
                # Update portfolio manager position
                if self.portfolio_manager:
                    self.portfolio_manager.update_position(symbol, active_position)
                
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
                            symbol=symbol,
                            side=side,
                            quantity=active_position.quantity,
                            reduce_only=True
                        )
                    
                    # Update balance
                    self.wallet_balance += trade.pnl
                    
                    # Update portfolio manager PnL
                    if self.portfolio_manager:
                        self.portfolio_manager.update_pnl(symbol, trade.pnl)
                        self.portfolio_manager.update_position(symbol, None)
                    
                    # Log trade
                    self.logger.log_trade(trade)
                    
                    # Show notification
                    pnl_text = f"+${trade.pnl:.2f}" if trade.pnl >= 0 else f"${trade.pnl:.2f}"
                    self.ui_display.show_notification(
                        f"[{symbol}] Position closed: {trade.side} @ ${trade.exit_price:.2f} | PnL: {pnl_text}",
                        "SUCCESS" if trade.pnl >= 0 else "WARNING"
                    )
            
            else:
                # No active position, check for entry signals
                if self.risk_manager.is_signal_generation_enabled():
                    # DEBUG: Log current indicators BEFORE checking signals
                    ind = self.strategy.current_indicators
                    logger.info(f"[{symbol}] INDICATORS: ADX={ind.adx:.2f}, RVOL={ind.rvol:.2f}, SqzColor={ind.squeeze_color}, SqzVal={ind.squeeze_value:.4f}, Trend15m={ind.trend_15m}, Trend1h={ind.trend_1h}, PriceVsVWAP={ind.price_vs_vwap}")
                    
                    long_signal = self.strategy.check_long_entry(symbol)
                    short_signal = self.strategy.check_short_entry(symbol)
                    
                    # DEBUG LOGGING
                    logger.info(f"[{symbol}] Signal check: LONG={long_signal is not None}, SHORT={short_signal is not None}")
                    if long_signal:
                        logger.info(f"[{symbol}] 🎯 LONG SIGNAL DETECTED! Price=${long_signal.price:.4f}")
                    if short_signal:
                        logger.info(f"[{symbol}] 🎯 SHORT SIGNAL DETECTED! Price=${short_signal.price:.4f}")
                    
                    signal = long_signal or short_signal
                    
                    if signal:
                        logger.info(f"[{symbol}] [OK] Signal exists, proceeding to open position...")
                        # Check portfolio risk limits if portfolio management is enabled
                        if self.portfolio_manager:
                            if not self.portfolio_manager.check_total_risk(self.wallet_balance):
                                logger.info(f"Skipping {symbol} signal - portfolio risk limit exceeded")
                                return
                        
                        # Open position
                        atr = self.strategy.current_indicators.atr_15m
                        logger.info(f"[{symbol}] Opening position: ATR=${atr:.4f}, Balance=${self.wallet_balance:.2f}")
                        position = self.risk_manager.open_position(
                            signal,
                            self.wallet_balance,
                            atr
                        )
                        logger.info(f"[{symbol}] [OK] Position created: {position.side} qty={position.quantity:.4f} @ ${position.entry_price:.4f}")
                        
                        # Check if portfolio manager allows this position
                        if self.portfolio_manager:
                            if not self.portfolio_manager.can_add_position(symbol, position, self.wallet_balance):
                                logger.info(f"Skipping {symbol} signal - would exceed portfolio risk limits")
                                self.risk_manager.close_position(position, current_price, "SIGNAL_EXIT")
                                return
                        
                        # Execute entry order (if not simulating)
                        logger.info(f"[{symbol}] Checking if should execute order (simulate={simulate_execution})...")
                        if not simulate_execution:
                            logger.info(f"[{symbol}] =" * 40)
                            logger.info(f"[{symbol}] EXECUTING REAL ORDER ON BINANCE")
                            logger.info(f"[{symbol}] Symbol: {symbol}")
                            logger.info(f"[{symbol}] Side: {position.side}")
                            logger.info(f"[{symbol}] Quantity: {position.quantity}")
                            logger.info(f"[{symbol}] Entry Price: {position.entry_price}")
                            logger.info(f"[{symbol}] =" * 40)
                            
                            # Validate margin availability
                            margin_required = (position.entry_price * position.quantity) / position.leverage
                            logger.info(f"[{symbol}] Margin required: ${margin_required:.2f}, Available: ${self.wallet_balance:.2f}")
                            
                            if self.order_executor.validate_margin_availability(
                                symbol,
                                margin_required
                            ):
                                logger.info(f"[{symbol}] [OK] Margin validated, placing order...")
                                side = "BUY" if position.side == "LONG" else "SELL"
                                self.order_executor.place_market_order(
                                    symbol=symbol,
                                    side=side,
                                    quantity=position.quantity
                                )
                                logger.info(f"[{symbol}] ✅ ORDER EXECUTED: {side} {position.quantity:.4f} @ market")
                            else:
                                # Insufficient margin, close position
                                self.risk_manager.close_position(
                                    position,
                                    current_price,
                                    "SIGNAL_EXIT"
                                )
                                self.ui_display.show_notification(
                                    f"[{symbol}] Insufficient margin for trade",
                                    "ERROR"
                                )
                                return
                        
                        # Update portfolio manager
                        if self.portfolio_manager:
                            self.portfolio_manager.update_position(symbol, position)
                        
                        # Show notification
                        self.ui_display.show_notification(
                            f"[{symbol}] Position opened: {position.side} @ ${position.entry_price:.2f}",
                            "SUCCESS"
                        )
        
        except Exception as e:
            logger.error(f"Error processing symbol {symbol}: {e}")
    
    def _rebalance_portfolio(self, symbols: List[str], simulate_execution: bool):
        """Rebalance portfolio allocations if needed.
        
        Args:
            symbols: List of symbols in portfolio
            simulate_execution: If True, simulate order execution
        """
        if not self.portfolio_manager:
            return
        
        try:
            # Collect signals for all symbols
            signals = {}
            for symbol in symbols:
                # Get latest candles
                candles_15m = self.data_manager.get_latest_candles("15m", 200, symbol=symbol)
                candles_1h = self.data_manager.get_latest_candles("1h", 100, symbol=symbol)
                
                if len(candles_15m) >= 50 and len(candles_1h) >= 30:
                    # Update indicators
                    self.strategy.update_indicators(candles_15m, candles_1h)
                    
                    # Check for signals
                    long_signal = self.strategy.check_long_entry(symbol)
                    short_signal = self.strategy.check_short_entry(symbol)
                    
                    signal = long_signal or short_signal
                    if signal:
                        signals[symbol] = signal
            
            # Rebalance if needed
            if signals:
                new_allocations = self.portfolio_manager.rebalance_portfolio(
                    signals,
                    self.wallet_balance
                )
                
                if new_allocations:
                    logger.info(f"Portfolio rebalanced: {new_allocations}")
        
        except Exception as e:
            logger.error(f"Error rebalancing portfolio: {e}")
    
    def _update_dashboard(self):
        """Update the terminal dashboard with current state."""
        try:
            # Get active positions and trades
            positions = self.risk_manager.get_all_active_positions()
            trades = self.risk_manager.get_closed_trades()
            
            # Get current indicators
            indicators = self.strategy.get_indicator_snapshot()
            
            # Get advanced features data
            advanced_features = self.strategy.get_advanced_features_data()
            
            # Log rate limiter stats periodically (every 10 updates)
            if not hasattr(self, '_dashboard_update_count'):
                self._dashboard_update_count = 0
            self._dashboard_update_count += 1
            
            if self._dashboard_update_count % 10 == 0:
                rate_stats = self.data_manager.rate_limiter.get_stats()
                logger.debug(
                    f"Rate limiter: {rate_stats['current_requests_per_minute']}/{rate_stats['max_requests_per_minute']} "
                    f"requests/min ({rate_stats['utilization_percent']:.1f}% utilization)"
                )
            
            # Render dashboard
            dashboard = self.ui_display.render_dashboard(
                positions=positions,
                trades=trades,
                indicators=indicators,
                wallet_balance=self.wallet_balance,
                mode=self.config.run_mode,
                market_regime=advanced_features.get('market_regime'),
                ml_prediction=advanced_features.get('ml_prediction'),
                volume_profile=advanced_features.get('volume_profile'),
                adaptive_thresholds=advanced_features.get('adaptive_thresholds')
            )
            
            # Clear screen and print dashboard
            self.ui_display.clear_screen()
            self.ui_display.console.print(dashboard)
        
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
    
    def _start_keyboard_listener(self):
        """Start keyboard listener for panic close (ESC key)."""
        if not KEYBOARD_AVAILABLE:
            logger.info("Keyboard listener not available (headless mode)")
            return
            
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
