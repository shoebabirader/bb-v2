"""Property-based tests for PositionSizer class."""

import pytest
from hypothesis import given, strategies as st, settings
from src.position_sizer import PositionSizer
from src.config import Config
from src.models import Position


# Helper function to create a test config
def create_test_config():
    """Create a Config instance with default test values."""
    config = Config()
    config.risk_per_trade = 0.01  # 1%
    config.leverage = 3
    config.stop_loss_atr_multiplier = 2.0
    config.trailing_stop_atr_multiplier = 1.5
    return config


# Feature: binance-futures-bot, Property 19: Position Size Risk Calculation
@given(
    wallet_balance=st.floats(min_value=100, max_value=100000),
    entry_price=st.floats(min_value=1, max_value=100000),
    atr=st.floats(min_value=0.01, max_value=1000)
)
@settings(max_examples=100)
def test_position_size_risks_exactly_one_percent(wallet_balance, entry_price, atr):
    """For any position size calculation, the potential loss at stop-loss 
    should equal exactly 1% of wallet balance.
    
    Validates: Requirements 7.1
    """
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    result = position_sizer.calculate_position_size(wallet_balance, entry_price, atr)
    
    stop_distance = result['stop_loss_distance']
    quantity = result['quantity']
    
    # Calculate potential loss: quantity * stop_distance
    potential_loss = quantity * stop_distance
    
    # Expected risk is 1% of wallet balance
    expected_risk = wallet_balance * 0.01
    
    # Allow small floating point error (0.1% tolerance)
    # Note: If quantity was adjusted to meet minimum order size, 
    # the risk might be slightly higher than 1%
    if quantity > position_sizer.min_order_size:
        # Only check exact 1% risk if we're above minimum order size
        assert abs(potential_loss - expected_risk) / expected_risk < 0.001, \
            f"Risk should be 1% of balance. Expected {expected_risk}, got {potential_loss}"


# Feature: binance-futures-bot, Property 20: Stop-Loss Distance Calculation
@given(
    wallet_balance=st.floats(min_value=100, max_value=100000),
    entry_price=st.floats(min_value=1, max_value=100000),
    atr=st.floats(min_value=0.01, max_value=1000)
)
@settings(max_examples=100)
def test_stop_loss_distance_equals_two_times_atr(wallet_balance, entry_price, atr):
    """For any new position, the stop-loss distance from entry price 
    should equal exactly 2x the current ATR value.
    
    Validates: Requirements 7.2
    """
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    result = position_sizer.calculate_position_size(wallet_balance, entry_price, atr)
    
    stop_distance = result['stop_loss_distance']
    expected_distance = 2.0 * atr
    
    # Check that stop distance is exactly 2x ATR
    assert abs(stop_distance - expected_distance) < 1e-10, \
        f"Stop distance should be 2x ATR. Expected {expected_distance}, got {stop_distance}"


# Feature: binance-futures-bot, Property 21: Leverage Factor in Position Sizing
@given(
    wallet_balance=st.floats(min_value=100, max_value=100000),
    entry_price=st.floats(min_value=1, max_value=100000),
    atr=st.floats(min_value=0.01, max_value=1000)
)
@settings(max_examples=100)
def test_leverage_factor_in_margin_calculation(wallet_balance, entry_price, atr):
    """For any position size calculation, the margin required should equal 
    (position_value / leverage) where leverage is 3.
    
    Validates: Requirements 7.3
    """
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    result = position_sizer.calculate_position_size(wallet_balance, entry_price, atr)
    
    quantity = result['quantity']
    margin_required = result['margin_required']
    
    # Calculate expected margin: (quantity * entry_price) / leverage
    position_value = quantity * entry_price
    expected_margin = position_value / config.leverage
    
    # Check that margin calculation accounts for leverage correctly
    assert abs(margin_required - expected_margin) < 1e-6, \
        f"Margin should be position_value / leverage. Expected {expected_margin}, got {margin_required}"


# Feature: binance-futures-bot, Property 22: Position Size Recalculation on Balance Change
@given(
    initial_balance=st.floats(min_value=1000, max_value=50000),
    balance_change=st.floats(min_value=-0.5, max_value=2.0),  # -50% to +200%
    entry_price=st.floats(min_value=1, max_value=100000),
    atr=st.floats(min_value=0.01, max_value=1000)
)
@settings(max_examples=100)
def test_position_size_recalculation_on_balance_change(initial_balance, balance_change, entry_price, atr):
    """For any wallet balance change, the next position size calculation should 
    use the new balance value, resulting in a different position size if ATR remains constant.
    
    Validates: Requirements 7.4
    """
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    # Calculate position size with initial balance
    result1 = position_sizer.calculate_position_size(initial_balance, entry_price, atr)
    quantity1 = result1['quantity']
    
    # Calculate new balance (ensure it's positive)
    new_balance = initial_balance * (1 + balance_change)
    if new_balance <= 0:
        new_balance = 100  # Minimum balance for test
    
    # Calculate position size with new balance
    result2 = position_sizer.calculate_position_size(new_balance, entry_price, atr)
    quantity2 = result2['quantity']
    
    # If balance changed, position size should change proportionally
    # (unless constrained by minimum order size)
    if abs(balance_change) > 0.01:  # Significant balance change
        if quantity1 > position_sizer.min_order_size and quantity2 > position_sizer.min_order_size:
            # Both above minimum, so should scale with balance
            ratio = quantity2 / quantity1
            expected_ratio = new_balance / initial_balance
            
            # Allow 1% tolerance for floating point errors
            assert abs(ratio - expected_ratio) / expected_ratio < 0.01, \
                f"Position size should scale with balance. Expected ratio {expected_ratio}, got {ratio}"


# Feature: binance-futures-bot, Property 23: Minimum Order Size Validation
@given(
    quantity=st.floats(min_value=0.0001, max_value=10.0)
)
@settings(max_examples=100)
def test_minimum_order_size_validation(quantity):
    """For any calculated position size, it should be validated against 
    Binance's minimum order requirements before order placement.
    
    Validates: Requirements 7.5
    """
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    # Test validation function
    is_valid = position_sizer.validate_order_size(quantity)
    
    # Should return True if quantity >= min_order_size, False otherwise
    if quantity >= position_sizer.min_order_size:
        assert is_valid, f"Quantity {quantity} should be valid (>= {position_sizer.min_order_size})"
    else:
        assert not is_valid, f"Quantity {quantity} should be invalid (< {position_sizer.min_order_size})"


# Additional property test for trailing stop behavior
# Feature: binance-futures-bot, Property 25: Trailing Stop Activation and Updates
@given(
    entry_price=st.floats(min_value=1000, max_value=50000),
    price_move=st.floats(min_value=0.01, max_value=0.5),  # 1% to 50% move
    atr=st.floats(min_value=10, max_value=1000),
    side=st.sampled_from(["LONG", "SHORT"])
)
@settings(max_examples=100)
def test_trailing_stop_only_tightens_never_widens(entry_price, price_move, atr, side):
    """For any position in profit, the trailing stop should be set at 1.5x ATR 
    from current price, and should only move closer to current price (never farther away).
    
    Validates: Requirements 8.2, 8.3, 8.5
    """
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    # Create a position
    if side == "LONG":
        # For long, price moves up
        current_price = entry_price * (1 + price_move)
        initial_trailing_stop = entry_price - (1.5 * atr)
    else:
        # For short, price moves down
        current_price = entry_price * (1 - price_move)
        initial_trailing_stop = entry_price + (1.5 * atr)
    
    position = Position(
        symbol="BTCUSDT",
        side=side,
        entry_price=entry_price,
        quantity=0.1,
        leverage=3,
        stop_loss=entry_price - (2 * atr) if side == "LONG" else entry_price + (2 * atr),
        trailing_stop=initial_trailing_stop,
        entry_time=1000000,
        unrealized_pnl=0.0
    )
    
    # Calculate new trailing stop
    new_trailing_stop = position_sizer.calculate_trailing_stop(position, current_price, atr)
    
    # Verify trailing stop only tightens
    if side == "LONG":
        # For long positions, trailing stop should move up (increase) or stay same
        assert new_trailing_stop >= position.trailing_stop, \
            f"Long trailing stop should only move up. Old: {position.trailing_stop}, New: {new_trailing_stop}"
        
        # Should be approximately 1.5x ATR below current price (if it moved)
        expected_stop = current_price - (1.5 * atr)
        if new_trailing_stop > position.trailing_stop:
            assert abs(new_trailing_stop - expected_stop) < 1e-6, \
                f"New trailing stop should be 1.5x ATR below price. Expected {expected_stop}, got {new_trailing_stop}"
    else:
        # For short positions, trailing stop should move down (decrease) or stay same
        assert new_trailing_stop <= position.trailing_stop, \
            f"Short trailing stop should only move down. Old: {position.trailing_stop}, New: {new_trailing_stop}"
        
        # Should be approximately 1.5x ATR above current price (if it moved)
        expected_stop = current_price + (1.5 * atr)
        if new_trailing_stop < position.trailing_stop:
            assert abs(new_trailing_stop - expected_stop) < 1e-6, \
                f"New trailing stop should be 1.5x ATR above price. Expected {expected_stop}, got {new_trailing_stop}"


# Unit tests for edge cases and error handling
def test_calculate_position_size_with_zero_wallet_balance():
    """Test that zero wallet balance raises ValueError."""
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    with pytest.raises(ValueError, match="wallet_balance must be positive"):
        position_sizer.calculate_position_size(0, 50000, 100)


def test_calculate_position_size_with_negative_entry_price():
    """Test that negative entry price raises ValueError."""
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    with pytest.raises(ValueError, match="entry_price must be positive"):
        position_sizer.calculate_position_size(10000, -50000, 100)


def test_calculate_position_size_with_zero_atr():
    """Test that zero ATR raises ValueError."""
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    with pytest.raises(ValueError, match="atr must be positive"):
        position_sizer.calculate_position_size(10000, 50000, 0)


def test_calculate_trailing_stop_with_invalid_side():
    """Test that invalid position side raises ValueError."""
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    position = Position(
        symbol="BTCUSDT",
        side="INVALID",
        entry_price=50000,
        quantity=0.1,
        leverage=3,
        stop_loss=49000,
        trailing_stop=49500,
        entry_time=1000000,
        unrealized_pnl=0.0
    )
    
    with pytest.raises(ValueError, match="Invalid position side"):
        position_sizer.calculate_trailing_stop(position, 51000, 100)


def test_set_min_order_size_with_negative_value():
    """Test that negative minimum order size raises ValueError."""
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    with pytest.raises(ValueError, match="min_size must be positive"):
        position_sizer.set_min_order_size(-0.001)


def test_position_size_respects_minimum_order_size():
    """Test that position size is adjusted to meet minimum order requirements."""
    config = create_test_config()
    position_sizer = PositionSizer(config)
    
    # Use very small balance and large ATR to force quantity below minimum
    result = position_sizer.calculate_position_size(
        wallet_balance=100,
        entry_price=50000,
        atr=1000  # Large ATR = large stop distance = small position size
    )
    
    # Should be at least minimum order size
    assert result['quantity'] >= position_sizer.min_order_size, \
        f"Quantity should be at least {position_sizer.min_order_size}, got {result['quantity']}"
