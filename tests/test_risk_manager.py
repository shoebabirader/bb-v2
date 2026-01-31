"""Property-based and unit tests for RiskManager."""

import pytest
from hypothesis import given, strategies as st, settings
from src.config import Config
from src.models import Position, Signal
from src.position_sizer import PositionSizer
from src.risk_manager import RiskManager


# Test fixtures
@pytest.fixture
def config():
    """Create a test configuration."""
    config = Config()
    config.symbol = "BTCUSDT"
    config.risk_per_trade = 0.01
    config.leverage = 3
    config.stop_loss_atr_multiplier = 2.0
    config.trailing_stop_atr_multiplier = 1.5
    return config


@pytest.fixture
def position_sizer(config):
    """Create a PositionSizer instance."""
    return PositionSizer(config)


@pytest.fixture
def risk_manager(config, position_sizer):
    """Create a RiskManager instance."""
    return RiskManager(config, position_sizer)


# Property-based tests

# Feature: binance-futures-bot, Property 24: Initial Stop-Loss Placement
@settings(max_examples=100)
@given(
    wallet_balance=st.floats(min_value=100, max_value=100000),
    entry_price=st.floats(min_value=1, max_value=100000),
    atr=st.floats(min_value=0.01, max_value=1000),
    signal_type=st.sampled_from(["LONG_ENTRY", "SHORT_ENTRY"])
)
def test_initial_stop_loss_placement(wallet_balance, entry_price, atr, signal_type):
    """For any newly opened position, the initial stop-loss price should be 
    exactly 2x ATR away from the entry price in the direction that limits loss.
    
    Validates: Requirements 8.1
    """
    # Create config and dependencies
    config = Config()
    config.symbol = "BTCUSDT"
    config.risk_per_trade = 0.01
    config.leverage = 3
    config.stop_loss_atr_multiplier = 2.0
    config.trailing_stop_atr_multiplier = 1.5
    
    position_sizer = PositionSizer(config)
    risk_manager = RiskManager(config, position_sizer)
    
    # Create signal
    signal = Signal(
        type=signal_type,
        timestamp=1000000,
        price=entry_price,
        indicators={}
    )
    
    # Open position
    position = risk_manager.open_position(
        signal=signal,
        wallet_balance=wallet_balance,
        atr=atr
    )
    
    # Calculate expected stop distance
    expected_stop_distance = config.stop_loss_atr_multiplier * atr
    
    # Verify stop-loss placement
    if position.side == "LONG":
        # For long positions, stop should be below entry
        actual_stop_distance = position.entry_price - position.stop_loss
        assert actual_stop_distance >= 0, "Long position stop should be below entry"
        assert abs(actual_stop_distance - expected_stop_distance) < 0.01, \
            f"Stop distance should be 2x ATR. Expected: {expected_stop_distance}, Got: {actual_stop_distance}"
    else:  # SHORT
        # For short positions, stop should be above entry
        actual_stop_distance = position.stop_loss - position.entry_price
        assert actual_stop_distance >= 0, "Short position stop should be above entry"
        assert abs(actual_stop_distance - expected_stop_distance) < 0.01, \
            f"Stop distance should be 2x ATR. Expected: {expected_stop_distance}, Got: {actual_stop_distance}"
    
    # Verify trailing stop is initially same as stop_loss
    assert position.trailing_stop == position.stop_loss, \
        "Initial trailing stop should equal initial stop-loss"


# Feature: binance-futures-bot, Property 25: Trailing Stop Activation and Updates
@settings(max_examples=100)
@given(
    entry_price=st.floats(min_value=1000, max_value=50000),
    atr=st.floats(min_value=10, max_value=500),
    price_move_percent=st.floats(min_value=0.01, max_value=0.1),  # 1-10% favorable move
    side=st.sampled_from(["LONG", "SHORT"])
)
def test_trailing_stop_only_tightens(entry_price, atr, price_move_percent, side):
    """For any position in profit, the trailing stop should be set at 1.5x ATR 
    from current price, and should only move closer to current price (never farther away).
    
    Validates: Requirements 8.2, 8.3, 8.5
    """
    # Create config and dependencies
    config = Config()
    config.symbol = "BTCUSDT"
    config.risk_per_trade = 0.01
    config.leverage = 3
    config.stop_loss_atr_multiplier = 2.0
    config.trailing_stop_atr_multiplier = 1.5
    
    position_sizer = PositionSizer(config)
    risk_manager = RiskManager(config, position_sizer)
    
    # Create a position manually
    stop_distance = config.stop_loss_atr_multiplier * atr
    if side == "LONG":
        initial_stop = entry_price - stop_distance
    else:
        initial_stop = entry_price + stop_distance
    
    position = Position(
        symbol="BTCUSDT",
        side=side,
        entry_price=entry_price,
        quantity=0.1,
        leverage=3,
        stop_loss=initial_stop,
        trailing_stop=initial_stop,
        entry_time=1000000,
        unrealized_pnl=0.0
    )
    
    # Add position to risk manager
    risk_manager.active_positions["BTCUSDT"] = position
    
    # Move price favorably
    if side == "LONG":
        new_price = entry_price * (1 + price_move_percent)
    else:
        new_price = entry_price * (1 - price_move_percent)
    
    # Store old trailing stop
    old_trailing_stop = position.trailing_stop
    
    # Update stops
    risk_manager.update_stops(position, new_price, atr)
    
    # Verify trailing stop moved in favorable direction (tightened)
    if side == "LONG":
        # For long, trailing stop should move up (increase)
        assert position.trailing_stop >= old_trailing_stop, \
            f"Long trailing stop should only move up. Old: {old_trailing_stop}, New: {position.trailing_stop}"
        
        # Verify it's at 1.5x ATR from current price (or at old stop if that's tighter)
        expected_new_stop = new_price - (config.trailing_stop_atr_multiplier * atr)
        if expected_new_stop > old_trailing_stop:
            assert abs(position.trailing_stop - expected_new_stop) < 0.01, \
                f"Trailing stop should be 1.5x ATR from price. Expected: {expected_new_stop}, Got: {position.trailing_stop}"
    else:  # SHORT
        # For short, trailing stop should move down (decrease)
        assert position.trailing_stop <= old_trailing_stop, \
            f"Short trailing stop should only move down. Old: {old_trailing_stop}, New: {position.trailing_stop}"
        
        # Verify it's at 1.5x ATR from current price (or at old stop if that's tighter)
        expected_new_stop = new_price + (config.trailing_stop_atr_multiplier * atr)
        if expected_new_stop < old_trailing_stop:
            assert abs(position.trailing_stop - expected_new_stop) < 0.01, \
                f"Trailing stop should be 1.5x ATR from price. Expected: {expected_new_stop}, Got: {position.trailing_stop}"
    
    # Now move price unfavorably and verify stop doesn't widen
    if side == "LONG":
        unfavorable_price = new_price * 0.99  # Price drops slightly
    else:
        unfavorable_price = new_price * 1.01  # Price rises slightly
    
    current_trailing_stop = position.trailing_stop
    risk_manager.update_stops(position, unfavorable_price, atr)
    
    # Verify stop didn't widen
    if side == "LONG":
        assert position.trailing_stop >= current_trailing_stop, \
            "Long trailing stop should never widen (decrease)"
    else:
        assert position.trailing_stop <= current_trailing_stop, \
            "Short trailing stop should never widen (increase)"


# Feature: binance-futures-bot, Property 26: Stop-Loss Trigger Execution
@settings(max_examples=100)
@given(
    entry_price=st.floats(min_value=10000, max_value=50000),  # Higher minimum to avoid edge cases
    atr=st.floats(min_value=10, max_value=500),
    side=st.sampled_from(["LONG", "SHORT"])
)
def test_stop_loss_trigger_detection(entry_price, atr, side):
    """For any position where current price crosses the stop-loss level, 
    the position should be detected as stopped out.
    
    Validates: Requirements 8.4
    """
    # Create config and dependencies
    config = Config()
    config.symbol = "BTCUSDT"
    config.risk_per_trade = 0.01
    config.leverage = 3
    config.stop_loss_atr_multiplier = 2.0
    config.trailing_stop_atr_multiplier = 1.5
    
    position_sizer = PositionSizer(config)
    risk_manager = RiskManager(config, position_sizer)
    
    # Create a position
    stop_distance = config.stop_loss_atr_multiplier * atr
    if side == "LONG":
        stop_price = entry_price - stop_distance
    else:
        stop_price = entry_price + stop_distance
    
    # Skip if stop price is invalid (negative or zero)
    if stop_price <= 0:
        return
    
    position = Position(
        symbol="BTCUSDT",
        side=side,
        entry_price=entry_price,
        quantity=0.1,
        leverage=3,
        stop_loss=stop_price,
        trailing_stop=stop_price,
        entry_time=1000000,
        unrealized_pnl=0.0
    )
    
    # Test price at stop level
    assert risk_manager.check_stop_hit(position, stop_price) == True, \
        "Stop should be hit when price equals stop level"
    
    # Test price beyond stop level
    if side == "LONG":
        # For long, price below stop should trigger
        below_stop = stop_price * 0.99
        if below_stop > 0:  # Only test if valid price
            assert risk_manager.check_stop_hit(position, below_stop) == True, \
                "Long stop should be hit when price is below stop level"
        
        # Price above stop should not trigger
        above_stop = stop_price * 1.01
        assert risk_manager.check_stop_hit(position, above_stop) == False, \
            "Long stop should not be hit when price is above stop level"
    else:  # SHORT
        # For short, price above stop should trigger
        above_stop = stop_price * 1.01
        assert risk_manager.check_stop_hit(position, above_stop) == True, \
            "Short stop should be hit when price is above stop level"
        
        # Price below stop should not trigger
        below_stop = stop_price * 0.99
        assert risk_manager.check_stop_hit(position, below_stop) == False, \
            "Short stop should not be hit when price is below stop level"


# Feature: binance-futures-bot, Property 29: Panic Close Completeness
@settings(max_examples=100)
@given(
    num_positions=st.integers(min_value=1, max_value=5),
    current_price=st.floats(min_value=1000, max_value=50000)
)
def test_panic_close_completeness(num_positions, current_price):
    """For any panic close trigger, all open positions should be closed, 
    and no new signals should be generated afterward.
    
    Validates: Requirements 10.1, 10.2, 10.3
    """
    # Create config and dependencies
    config = Config()
    config.symbol = "BTCUSDT"
    config.risk_per_trade = 0.01
    config.leverage = 3
    config.stop_loss_atr_multiplier = 2.0
    config.trailing_stop_atr_multiplier = 1.5
    
    position_sizer = PositionSizer(config)
    risk_manager = RiskManager(config, position_sizer)
    
    # Create multiple positions
    for i in range(num_positions):
        side = "LONG" if i % 2 == 0 else "SHORT"
        position = Position(
            symbol=f"SYMBOL{i}",
            side=side,
            entry_price=current_price,
            quantity=0.1,
            leverage=3,
            stop_loss=current_price * 0.98 if side == "LONG" else current_price * 1.02,
            trailing_stop=current_price * 0.98 if side == "LONG" else current_price * 1.02,
            entry_time=1000000 + i,
            unrealized_pnl=0.0
        )
        risk_manager.active_positions[f"SYMBOL{i}"] = position
    
    # Verify positions exist
    assert len(risk_manager.active_positions) == num_positions, \
        f"Should have {num_positions} active positions"
    
    # Trigger panic close
    trades = risk_manager.close_all_positions(current_price)
    
    # Verify all positions were closed
    assert len(risk_manager.active_positions) == 0, \
        "All positions should be closed after panic"
    
    # Verify correct number of trades generated
    assert len(trades) == num_positions, \
        f"Should generate {num_positions} trades, got {len(trades)}"
    
    # Verify all trades have PANIC exit reason
    for trade in trades:
        assert trade.exit_reason == "PANIC", \
            f"All trades should have PANIC exit reason, got {trade.exit_reason}"
        assert trade.exit_price == current_price, \
            f"All trades should exit at current price {current_price}, got {trade.exit_price}"
    
    # Verify signal generation is disabled
    assert risk_manager.is_signal_generation_enabled() == False, \
        "Signal generation should be disabled after panic close"


# Unit tests for specific scenarios

def test_open_long_position(risk_manager):
    """Test opening a long position."""
    signal = Signal(
        type="LONG_ENTRY",
        timestamp=1000000,
        price=50000.0,
        indicators={}
    )
    
    position = risk_manager.open_position(
        signal=signal,
        wallet_balance=10000.0,
        atr=100.0
    )
    
    assert position.side == "LONG"
    assert position.entry_price == 50000.0
    assert position.stop_loss < position.entry_price
    assert position.symbol == "BTCUSDT"
    assert risk_manager.has_active_position("BTCUSDT")


def test_open_short_position(risk_manager):
    """Test opening a short position."""
    signal = Signal(
        type="SHORT_ENTRY",
        timestamp=1000000,
        price=50000.0,
        indicators={}
    )
    
    position = risk_manager.open_position(
        signal=signal,
        wallet_balance=10000.0,
        atr=100.0
    )
    
    assert position.side == "SHORT"
    assert position.entry_price == 50000.0
    assert position.stop_loss > position.entry_price
    assert position.symbol == "BTCUSDT"


def test_close_position_with_profit(risk_manager):
    """Test closing a position with profit."""
    # Create a long position
    signal = Signal(
        type="LONG_ENTRY",
        timestamp=1000000,
        price=50000.0,
        indicators={}
    )
    
    position = risk_manager.open_position(
        signal=signal,
        wallet_balance=10000.0,
        atr=100.0
    )
    
    # Close at higher price (profit)
    trade = risk_manager.close_position(
        position=position,
        exit_price=51000.0,
        reason="SIGNAL_EXIT"
    )
    
    assert trade.pnl > 0
    assert trade.exit_reason == "SIGNAL_EXIT"
    assert not risk_manager.has_active_position("BTCUSDT")


def test_close_position_with_loss(risk_manager):
    """Test closing a position with loss."""
    # Create a long position
    signal = Signal(
        type="LONG_ENTRY",
        timestamp=1000000,
        price=50000.0,
        indicators={}
    )
    
    position = risk_manager.open_position(
        signal=signal,
        wallet_balance=10000.0,
        atr=100.0
    )
    
    # Close at lower price (loss)
    trade = risk_manager.close_position(
        position=position,
        exit_price=49000.0,
        reason="STOP_LOSS"
    )
    
    assert trade.pnl < 0
    assert trade.exit_reason == "STOP_LOSS"


def test_invalid_signal_type(risk_manager):
    """Test that invalid signal type raises error."""
    signal = Signal(
        type="INVALID",
        timestamp=1000000,
        price=50000.0,
        indicators={}
    )
    
    with pytest.raises(ValueError, match="Invalid signal type"):
        risk_manager.open_position(
            signal=signal,
            wallet_balance=10000.0,
            atr=100.0
        )


def test_invalid_exit_reason(risk_manager):
    """Test that invalid exit reason raises error."""
    signal = Signal(
        type="LONG_ENTRY",
        timestamp=1000000,
        price=50000.0,
        indicators={}
    )
    
    position = risk_manager.open_position(
        signal=signal,
        wallet_balance=10000.0,
        atr=100.0
    )
    
    with pytest.raises(ValueError, match="Invalid exit reason"):
        risk_manager.close_position(
            position=position,
            exit_price=51000.0,
            reason="INVALID_REASON"
        )
