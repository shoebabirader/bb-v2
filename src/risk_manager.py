"""Risk management and position tracking for Binance Futures Trading Bot."""

import time
from typing import Dict, List, Optional
from src.config import Config
from src.models import Position, Trade, Signal
from src.position_sizer import PositionSizer


class RiskManager:
    """Manages open positions, stop-loss levels, and risk controls.
    
    Responsible for:
    - Opening positions with calculated size and stops
    - Updating trailing stops as price moves favorably
    - Detecting stop-loss triggers
    - Closing positions and generating trade records
    - Emergency panic close functionality
    """
    
    def __init__(self, config: Config, position_sizer: PositionSizer):
        """Initialize RiskManager with configuration and position sizer.
        
        Args:
            config: Configuration object containing risk parameters
            position_sizer: PositionSizer instance for calculating sizes and stops
        """
        self.config = config
        self.position_sizer = position_sizer
        self.active_positions: Dict[str, Position] = {}
        self.closed_trades: List[Trade] = []
        self._signal_generation_enabled = True
    
    def open_position(
        self, 
        signal: Signal, 
        wallet_balance: float, 
        atr: float
    ) -> Position:
        """Create new position with calculated size and stops.
        
        Calculates position size based on 1% risk rule, sets initial stop-loss
        at 2x ATR, and initializes trailing stop at the same level.
        
        Args:
            signal: Entry signal containing type, price, and timestamp
            wallet_balance: Current wallet balance in quote currency (USDT)
            atr: Current Average True Range value
            
        Returns:
            Position object with all parameters set
            
        Raises:
            ValueError: If signal type is invalid or inputs are invalid
        """
        # Validate signal type
        if signal.type not in ["LONG_ENTRY", "SHORT_ENTRY"]:
            raise ValueError(f"Invalid signal type for opening position: {signal.type}")
        
        # Determine position side
        side = "LONG" if signal.type == "LONG_ENTRY" else "SHORT"
        
        # Calculate position size and stops
        sizing_result = self.position_sizer.calculate_position_size(
            wallet_balance=wallet_balance,
            entry_price=signal.price,
            atr=atr
        )
        
        # Calculate initial stop-loss price based on position side
        if side == "LONG":
            # For long positions, stop is below entry
            stop_loss_price = signal.price - sizing_result['stop_loss_distance']
        else:
            # For short positions, stop is above entry
            stop_loss_price = signal.price + sizing_result['stop_loss_distance']
        
        # Create position object
        position = Position(
            symbol=self.config.symbol,
            side=side,
            entry_price=signal.price,
            quantity=sizing_result['quantity'],
            leverage=self.config.leverage,
            stop_loss=stop_loss_price,
            trailing_stop=stop_loss_price,  # Initially same as stop_loss
            entry_time=signal.timestamp,
            unrealized_pnl=0.0
        )
        
        # Store position in active positions
        self.active_positions[self.config.symbol] = position
        
        return position
    
    def update_stops(self, position: Position, current_price: float, atr: float) -> None:
        """Update trailing stop-loss if price moves favorably.
        
        Only tightens stops, never widens them. For long positions, moves stop up.
        For short positions, moves stop down.
        
        Args:
            position: Position to update
            current_price: Current market price
            atr: Current Average True Range value
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Calculate new trailing stop using position sizer
        new_trailing_stop = self.position_sizer.calculate_trailing_stop(
            position=position,
            current_price=current_price,
            atr=atr
        )
        
        # Update position's trailing stop
        position.trailing_stop = new_trailing_stop
        
        # Update unrealized PnL
        if position.side == "LONG":
            position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
        else:  # SHORT
            position.unrealized_pnl = (position.entry_price - current_price) * position.quantity
    
    def check_stop_hit(self, position: Position, current_price: float) -> bool:
        """Check if stop-loss or trailing stop is hit.
        
        For long positions: stop is hit if price <= trailing_stop
        For short positions: stop is hit if price >= trailing_stop
        
        Args:
            position: Position to check
            current_price: Current market price
            
        Returns:
            True if stop is hit, False otherwise
            
        Raises:
            ValueError: If position side is invalid
        """
        if position.side == "LONG":
            # For long positions, stop is hit if price drops to or below stop
            return current_price <= position.trailing_stop
        elif position.side == "SHORT":
            # For short positions, stop is hit if price rises to or above stop
            return current_price >= position.trailing_stop
        else:
            raise ValueError(f"Invalid position side: {position.side}")
    
    def close_position(
        self, 
        position: Position, 
        exit_price: float, 
        reason: str
    ) -> Trade:
        """Close position and return trade record.
        
        Calculates final PnL and creates a Trade object with all details.
        Removes position from active positions.
        
        Args:
            position: Position to close
            exit_price: Price at which position is closed
            reason: Exit reason ("STOP_LOSS", "TRAILING_STOP", "SIGNAL_EXIT", "PANIC")
            
        Returns:
            Trade object with complete trade details
            
        Raises:
            ValueError: If exit reason is invalid or inputs are invalid
        """
        # Validate exit reason
        valid_reasons = ["STOP_LOSS", "TRAILING_STOP", "SIGNAL_EXIT", "PANIC"]
        if reason not in valid_reasons:
            raise ValueError(f"Invalid exit reason: {reason}. Must be one of: {', '.join(valid_reasons)}")
        
        # Validate exit price
        if exit_price <= 0:
            raise ValueError(f"exit_price must be positive, got {exit_price}")
        
        # Calculate PnL
        if position.side == "LONG":
            # For long: profit when exit > entry
            pnl = (exit_price - position.entry_price) * position.quantity
        else:  # SHORT
            # For short: profit when entry > exit
            pnl = (position.entry_price - exit_price) * position.quantity
        
        # Calculate PnL percentage
        position_value = position.entry_price * position.quantity
        pnl_percent = (pnl / position_value) * 100 if position_value > 0 else 0.0
        
        # Get current timestamp
        exit_time = int(time.time() * 1000)  # milliseconds
        
        # Create trade record
        trade = Trade(
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            entry_time=position.entry_time,
            exit_time=exit_time,
            exit_reason=reason
        )
        
        # Store trade in closed trades
        self.closed_trades.append(trade)
        
        # Remove position from active positions
        if position.symbol in self.active_positions:
            del self.active_positions[position.symbol]
        
        return trade
    
    def close_all_positions(self, current_price: float) -> List[Trade]:
        """Emergency close all positions (panic button).
        
        Closes all active positions at current market price with "PANIC" reason.
        Disables signal generation after panic close.
        
        Args:
            current_price: Current market price for closing positions
            
        Returns:
            List of Trade objects for all closed positions
            
        Raises:
            ValueError: If current_price is invalid
        """
        if current_price <= 0:
            raise ValueError(f"current_price must be positive, got {current_price}")
        
        trades = []
        
        # Close all active positions
        # Create a copy of keys to avoid modifying dict during iteration
        symbols = list(self.active_positions.keys())
        
        for symbol in symbols:
            position = self.active_positions[symbol]
            trade = self.close_position(
                position=position,
                exit_price=current_price,
                reason="PANIC"
            )
            trades.append(trade)
        
        # Disable signal generation
        self._signal_generation_enabled = False
        
        return trades
    
    def is_signal_generation_enabled(self) -> bool:
        """Check if signal generation is enabled.
        
        Returns:
            True if signal generation is enabled, False if disabled (e.g., after panic close)
        """
        return self._signal_generation_enabled
    
    def get_active_position(self, symbol: str) -> Optional[Position]:
        """Get active position for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Position object if exists, None otherwise
        """
        return self.active_positions.get(symbol)
    
    def has_active_position(self, symbol: str) -> bool:
        """Check if there's an active position for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            True if position exists, False otherwise
        """
        return symbol in self.active_positions
    
    def get_all_active_positions(self) -> List[Position]:
        """Get all active positions.
        
        Returns:
            List of all active Position objects
        """
        return list(self.active_positions.values())
    
    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades.
        
        Returns:
            List of all closed Trade objects
        """
        return self.closed_trades.copy()
