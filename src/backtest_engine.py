"""Backtest engine for simulating trading strategy on historical data."""

import numpy as np
from typing import List, Dict, Optional
from src.config import Config
from src.models import Candle, Trade, PerformanceMetrics, Signal, Position
from src.strategy import StrategyEngine
from src.risk_manager import RiskManager


class BacktestEngine:
    """Backtesting engine that simulates trading on historical data.
    
    Implements realistic trade execution with fees and slippage,
    tracks equity curve, and calculates comprehensive performance metrics.
    """
    
    def __init__(
        self, 
        config: Config, 
        strategy: StrategyEngine, 
        risk_mgr: RiskManager
    ):
        """Initialize BacktestEngine with strategy and risk manager.
        
        Args:
            config: Configuration object with backtest parameters
            strategy: StrategyEngine instance for signal generation
            risk_mgr: RiskManager instance for position management
        """
        self.config = config
        self.strategy = strategy
        self.risk_mgr = risk_mgr
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.initial_balance = 0.0
        self.current_balance = 0.0
    
    def run_backtest(
        self, 
        candles_15m: List[Candle],
        candles_1h: List[Candle],
        initial_balance: float = 10000.0
    ) -> Dict:
        """Execute backtest on historical data.
        
        Iterates through historical candles, generates signals, simulates
        trade execution with realistic fills, and tracks performance.
        
        Args:
            candles_15m: List of 15-minute historical candles
            candles_1h: List of 1-hour historical candles
            initial_balance: Starting wallet balance in USDT
            
        Returns:
            Dictionary containing performance metrics:
                - total_trades: int
                - winning_trades: int
                - losing_trades: int
                - win_rate: float
                - total_pnl: float
                - roi: float
                - max_drawdown: float
                - profit_factor: float
                - sharpe_ratio: float
                
        Raises:
            ValueError: If inputs are invalid
        """
        if initial_balance <= 0:
            raise ValueError(f"initial_balance must be positive, got {initial_balance}")
        
        if not candles_15m or not candles_1h:
            raise ValueError("Candle lists cannot be empty")
        
        # Initialize backtest state
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.equity_curve = [initial_balance]
        self.trades = []
        
        # We need to align 15m and 1h candles
        # For simplicity, we'll iterate through 15m candles and update 1h when needed
        # In production, this would need more sophisticated time alignment
        
        # Build a sliding window of candles for indicator calculation
        min_candles_15m = 50  # Enough for all indicators
        min_candles_1h = 30
        
        # Iterate through 15m candles
        for i in range(min_candles_15m, len(candles_15m)):
            # Get current window of candles
            current_candles_15m = candles_15m[max(0, i - 200):i + 1]
            
            # Get corresponding 1h candles (approximate alignment)
            # Each 1h candle = 4 x 15m candles
            current_1h_index = min(i // 4, len(candles_1h) - 1)
            current_candles_1h = candles_1h[max(0, current_1h_index - 100):current_1h_index + 1]
            
            if len(current_candles_1h) < min_candles_1h:
                continue
            
            # Update indicators
            self.strategy.update_indicators(current_candles_15m, current_candles_1h)
            
            # Get current candle
            current_candle = candles_15m[i]
            current_price = current_candle.close
            
            # Check if we have an active position
            active_position = self.risk_mgr.get_active_position(self.config.symbol)
            
            if active_position:
                # Update stops and check for stop hit
                atr = self.strategy.current_indicators.atr_15m
                self.risk_mgr.update_stops(active_position, current_price, atr)
                
                # Check if stop was hit during this candle
                if self._check_stop_hit_in_candle(active_position, current_candle):
                    # Simulate stop-loss execution
                    exit_price = self.simulate_trade_execution(
                        signal_type="EXIT",
                        candle=current_candle,
                        is_long=(active_position.side == "LONG")
                    )
                    
                    # Apply fees and slippage
                    exit_price = self.apply_fees_and_slippage(
                        exit_price, 
                        "SELL" if active_position.side == "LONG" else "BUY"
                    )
                    
                    # Close position
                    trade = self.risk_mgr.close_position(
                        active_position,
                        exit_price,
                        "TRAILING_STOP"
                    )
                    
                    # Update balance
                    self.current_balance += trade.pnl
                    self.trades.append(trade)
            else:
                # No active position, check for entry signals
                long_signal = self.strategy.check_long_entry()
                short_signal = self.strategy.check_short_entry()
                
                signal = long_signal or short_signal
                
                if signal:
                    # Simulate entry execution
                    entry_price = self.simulate_trade_execution(
                        signal_type=signal.type,
                        candle=current_candle,
                        is_long=(signal.type == "LONG_ENTRY")
                    )
                    
                    # Apply fees and slippage
                    entry_price = self.apply_fees_and_slippage(
                        entry_price,
                        "BUY" if signal.type == "LONG_ENTRY" else "SELL"
                    )
                    
                    # Update signal price with simulated execution price
                    signal.price = entry_price
                    
                    # Open position
                    atr = self.strategy.current_indicators.atr_15m
                    position = self.risk_mgr.open_position(
                        signal,
                        self.current_balance,
                        atr
                    )
            
            # Track equity (balance + unrealized PnL)
            equity = self.current_balance
            if active_position:
                equity += active_position.unrealized_pnl
            self.equity_curve.append(equity)
        
        # Close any remaining open positions at the end
        active_position = self.risk_mgr.get_active_position(self.config.symbol)
        if active_position:
            final_candle = candles_15m[-1]
            exit_price = self.apply_fees_and_slippage(
                final_candle.close,
                "SELL" if active_position.side == "LONG" else "BUY"
            )
            trade = self.risk_mgr.close_position(
                active_position,
                exit_price,
                "SIGNAL_EXIT"
            )
            self.current_balance += trade.pnl
            self.trades.append(trade)
        
        # Calculate and return metrics
        return self.calculate_metrics()
    
    def simulate_trade_execution(
        self, 
        signal_type: str,
        candle: Candle,
        is_long: bool
    ) -> float:
        """Simulate order fill with realistic fill logic.
        
        For entries: Uses candle open price as approximation
        For exits: Uses a price within the candle's high/low range
        
        Args:
            signal_type: Type of signal ("LONG_ENTRY", "SHORT_ENTRY", "EXIT")
            candle: Current candle for fill simulation
            is_long: Whether this is a long position
            
        Returns:
            Simulated fill price
            
        Raises:
            ValueError: If inputs are invalid
        """
        if signal_type in ["LONG_ENTRY", "SHORT_ENTRY"]:
            # For entries, assume we get filled at the open of the next candle
            # In reality, this would be more sophisticated
            return candle.open
        
        elif signal_type == "EXIT":
            # For exits (stop-loss), simulate fill within candle range
            # For long positions, stop is hit on downside
            # For short positions, stop is hit on upside
            if is_long:
                # Long stop-loss: use a price between low and close
                # Assume we get filled closer to the low
                return candle.low + (candle.close - candle.low) * 0.3
            else:
                # Short stop-loss: use a price between close and high
                # Assume we get filled closer to the high
                return candle.close + (candle.high - candle.close) * 0.7
        
        else:
            raise ValueError(f"Invalid signal_type: {signal_type}")
    
    def apply_fees_and_slippage(self, price: float, side: str) -> float:
        """Apply trading fees and slippage to execution price.
        
        Fees and slippage are applied in the unfavorable direction:
        - For buys: increase the price (pay more)
        - For sells: decrease the price (receive less)
        
        Args:
            price: Base execution price
            side: Order side ("BUY" or "SELL")
            
        Returns:
            Adjusted price with fees and slippage applied
            
        Raises:
            ValueError: If inputs are invalid
        """
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")
        
        if side not in ["BUY", "SELL"]:
            raise ValueError(f"side must be 'BUY' or 'SELL', got {side}")
        
        # Calculate total cost (fee + slippage)
        total_cost = self.config.trading_fee + self.config.slippage
        
        if side == "BUY":
            # For buys, increase price (unfavorable)
            return price * (1 + total_cost)
        else:  # SELL
            # For sells, decrease price (unfavorable)
            return price * (1 - total_cost)
    
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics from trade history.
        
        Calculates comprehensive metrics including:
        - Win rate and trade counts
        - Total PnL and ROI
        - Maximum drawdown
        - Profit factor
        - Sharpe ratio
        - Average win/loss
        
        Returns:
            Dictionary containing all performance metrics
        """
        if not self.trades:
            # No trades executed
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'roi': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0,
                'sharpe_ratio': 0.0,
                'average_win': 0.0,
                'average_loss': 0.0,
                'largest_win': 0.0,
                'largest_loss': 0.0,
                'average_trade_duration': 0
            }
        
        # Basic trade statistics
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl <= 0)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # PnL calculations
        total_pnl = sum(t.pnl for t in self.trades)
        roi = (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0.0
        
        # Drawdown calculation
        max_drawdown = self._calculate_max_drawdown()
        
        # Profit factor (gross profit / gross loss)
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
        
        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        # Win/Loss statistics
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [t.pnl for t in self.trades if t.pnl < 0]
        
        average_win = (sum(wins) / len(wins)) if wins else 0.0
        average_loss = (sum(losses) / len(losses)) if losses else 0.0
        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0
        
        # Trade duration
        durations = [t.exit_time - t.entry_time for t in self.trades]
        average_trade_duration = int(sum(durations) / len(durations)) if durations else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'roi': roi,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'average_win': average_win,
            'average_loss': average_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'average_trade_duration': average_trade_duration
        }
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from equity curve.
        
        Returns:
            Maximum drawdown in quote currency (USDT)
        """
        if not self.equity_curve:
            return 0.0
        
        max_drawdown = 0.0
        peak = self.equity_curve[0]
        
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from trade returns.
        
        Sharpe ratio = (Mean return - Risk-free rate) / Std deviation of returns
        Assumes risk-free rate = 0 for simplicity
        
        Returns:
            Sharpe ratio (annualized approximation)
        """
        if len(self.trades) < 2:
            return 0.0
        
        # Calculate returns as percentage of balance at trade time
        returns = []
        for trade in self.trades:
            # Approximate balance at trade time
            trade_return = trade.pnl_percent / 100  # Convert to decimal
            returns.append(trade_return)
        
        if not returns:
            return 0.0
        
        # Calculate mean and std deviation
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Sharpe ratio (not annualized, just per-trade)
        sharpe = mean_return / std_return
        
        # Approximate annualization (assuming ~250 trading days)
        # This is a rough approximation
        sharpe_annualized = sharpe * np.sqrt(250)
        
        return sharpe_annualized
    
    def _check_stop_hit_in_candle(
        self, 
        position: Position, 
        candle: Candle
    ) -> bool:
        """Check if stop-loss was hit during this candle.
        
        Args:
            position: Active position to check
            candle: Current candle
            
        Returns:
            True if stop was hit, False otherwise
        """
        if position.side == "LONG":
            # For long positions, check if low touched the stop
            return candle.low <= position.trailing_stop
        else:  # SHORT
            # For short positions, check if high touched the stop
            return candle.high >= position.trailing_stop
    
    def get_equity_curve(self) -> List[float]:
        """Get the equity curve from the backtest.
        
        Returns:
            List of equity values throughout the backtest
        """
        return self.equity_curve.copy()
    
    def get_trades(self) -> List[Trade]:
        """Get all trades from the backtest.
        
        Returns:
            List of Trade objects
        """
        return self.trades.copy()
