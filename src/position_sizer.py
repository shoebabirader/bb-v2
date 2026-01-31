"""Position sizing and risk calculations for Binance Futures Trading Bot."""

from typing import Dict
from src.config import Config
from src.models import Position


class PositionSizer:
    """Calculates position sizes and manages stop-loss levels based on risk parameters.
    
    Implements the 1% risk rule with ATR-based stop-loss placement and trailing stops.
    Accounts for leverage in position sizing calculations.
    """
    
    def __init__(self, config: Config):
        """Initialize PositionSizer with configuration.
        
        Args:
            config: Configuration object containing risk parameters
        """
        self.config = config
        # Binance minimum order size for BTCUSDT (in BTC)
        # This is a typical minimum, actual value should be fetched from exchange info
        self.min_order_size = 0.001
    
    def calculate_position_size(
        self, 
        wallet_balance: float, 
        entry_price: float, 
        atr: float
    ) -> Dict[str, float]:
        """Calculate position size based on 1% risk rule with 2x ATR stop.
        
        Uses the formula:
        - Risk Amount = wallet_balance * risk_per_trade (1%)
        - Stop Distance = 2 * ATR
        - Position Size = Risk Amount / Stop Distance
        - Margin Required = (Position Size * Entry Price) / Leverage
        
        Args:
            wallet_balance: Current wallet balance in quote currency (USDT)
            entry_price: Intended entry price for the position
            atr: Current Average True Range value
            
        Returns:
            Dictionary containing:
                - quantity: Position size in base currency
                - stop_loss_distance: Distance from entry to stop-loss
                - stop_loss_price: Absolute stop-loss price (not used for orders)
                - margin_required: Margin required for this position
                
        Raises:
            ValueError: If inputs are invalid (negative or zero values)
        """
        # Validate inputs
        if wallet_balance <= 0:
            raise ValueError(f"wallet_balance must be positive, got {wallet_balance}")
        if entry_price <= 0:
            raise ValueError(f"entry_price must be positive, got {entry_price}")
        if atr <= 0:
            raise ValueError(f"atr must be positive, got {atr}")
        
        # Calculate risk amount (1% of wallet balance)
        risk_amount = wallet_balance * self.config.risk_per_trade
        
        # Calculate stop-loss distance (2x ATR)
        stop_loss_distance = self.config.stop_loss_atr_multiplier * atr
        
        # Calculate position size in base currency (BTC)
        # Risk Amount = Quantity * Stop Distance
        # Therefore: Quantity = Risk Amount / Stop Distance
        quantity = risk_amount / stop_loss_distance
        
        # Validate minimum order size
        if quantity < self.min_order_size:
            # If calculated size is below minimum, use minimum size
            # This means we'll risk slightly more than 1% in this case
            quantity = self.min_order_size
        
        # Calculate margin required (accounting for leverage)
        # Margin = (Position Value) / Leverage
        position_notional_value = quantity * entry_price
        margin_required = position_notional_value / self.config.leverage
        
        # Calculate stop-loss price (for reference, not used in actual orders)
        # This is just for logging/display purposes
        stop_loss_price = entry_price - stop_loss_distance
        
        return {
            'quantity': quantity,
            'stop_loss_distance': stop_loss_distance,
            'stop_loss_price': stop_loss_price,
            'margin_required': margin_required
        }
    
    def calculate_trailing_stop(
        self, 
        position: Position, 
        current_price: float, 
        atr: float
    ) -> float:
        """Calculate trailing stop price at 1.5x ATR from current price.
        
        The trailing stop only moves in the favorable direction (tightens),
        never widens. For long positions, it moves up. For short positions,
        it moves down.
        
        Args:
            position: Current position object
            current_price: Current market price
            atr: Current Average True Range value
            
        Returns:
            New trailing stop price (only if it's more favorable than current)
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if current_price <= 0:
            raise ValueError(f"current_price must be positive, got {current_price}")
        if atr <= 0:
            raise ValueError(f"atr must be positive, got {atr}")
        
        # Calculate trailing stop distance (1.5x ATR)
        trailing_distance = self.config.trailing_stop_atr_multiplier * atr
        
        if position.side == "LONG":
            # For long positions, trailing stop is below current price
            new_trailing_stop = current_price - trailing_distance
            
            # Only update if new stop is higher (tighter) than current
            # Never widen the stop
            if new_trailing_stop > position.trailing_stop:
                return new_trailing_stop
            else:
                return position.trailing_stop
        
        elif position.side == "SHORT":
            # For short positions, trailing stop is above current price
            new_trailing_stop = current_price + trailing_distance
            
            # Only update if new stop is lower (tighter) than current
            # Never widen the stop
            if new_trailing_stop < position.trailing_stop:
                return new_trailing_stop
            else:
                return position.trailing_stop
        
        else:
            raise ValueError(f"Invalid position side: {position.side}. Must be 'LONG' or 'SHORT'")
    
    def validate_order_size(self, quantity: float) -> bool:
        """Validate that order size meets Binance minimum requirements.
        
        Args:
            quantity: Order quantity in base currency
            
        Returns:
            True if order size is valid, False otherwise
        """
        return quantity >= self.min_order_size
    
    def set_min_order_size(self, min_size: float) -> None:
        """Set minimum order size (should be fetched from exchange info).
        
        Args:
            min_size: Minimum order size in base currency
        """
        if min_size <= 0:
            raise ValueError(f"min_size must be positive, got {min_size}")
        self.min_order_size = min_size
