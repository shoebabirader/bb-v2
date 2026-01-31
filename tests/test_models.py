"""Property-based and unit tests for data models."""

import pytest
from hypothesis import given, strategies as st
from src.models import Candle, Position, Trade, Signal, IndicatorState, PerformanceMetrics


# Feature: binance-futures-bot, Property 7: Trade Log Completeness
@given(
    symbol=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    side=st.sampled_from(["LONG", "SHORT"]),
    entry_price=st.floats(min_value=0.01, max_value=1000000, allow_nan=False, allow_infinity=False),
    exit_price=st.floats(min_value=0.01, max_value=1000000, allow_nan=False, allow_infinity=False),
    quantity=st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False),
    entry_time=st.integers(min_value=1000000000000, max_value=9999999999999),
    exit_time=st.integers(min_value=1000000000000, max_value=9999999999999),
    exit_reason=st.sampled_from(["STOP_LOSS", "TRAILING_STOP", "SIGNAL_EXIT", "PANIC"])
)
def test_trade_log_contains_all_required_fields(
    symbol, side, entry_price, exit_price, quantity, entry_time, exit_time, exit_reason
):
    """For any executed trade, the trade log should contain entry_price, exit_price, 
    pnl, and timestamp fields with valid values.
    
    Property 7: Trade Log Completeness
    Validates: Requirements 2.5
    """
    # Ensure exit_time is after entry_time
    if exit_time < entry_time:
        entry_time, exit_time = exit_time, entry_time
    
    # Calculate PnL based on side
    if side == "LONG":
        pnl = (exit_price - entry_price) * quantity
    else:  # SHORT
        pnl = (entry_price - exit_price) * quantity
    
    pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price * quantity > 0 else 0.0
    
    # Create trade object
    trade = Trade(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=quantity,
        pnl=pnl,
        pnl_percent=pnl_percent,
        entry_time=entry_time,
        exit_time=exit_time,
        exit_reason=exit_reason
    )
    
    # Verify all required fields are present and valid
    assert hasattr(trade, 'entry_price'), "Trade must have entry_price field"
    assert hasattr(trade, 'exit_price'), "Trade must have exit_price field"
    assert hasattr(trade, 'pnl'), "Trade must have pnl field"
    assert hasattr(trade, 'entry_time'), "Trade must have entry_time (timestamp) field"
    assert hasattr(trade, 'exit_time'), "Trade must have exit_time (timestamp) field"
    
    # Verify values are valid (not None, not NaN)
    assert trade.entry_price is not None and trade.entry_price > 0, "entry_price must be valid and positive"
    assert trade.exit_price is not None and trade.exit_price > 0, "exit_price must be valid and positive"
    assert trade.pnl is not None, "pnl must be valid"
    assert trade.entry_time is not None and trade.entry_time > 0, "entry_time must be valid and positive"
    assert trade.exit_time is not None and trade.exit_time > 0, "exit_time must be valid and positive"
    
    # Verify timestamps are in correct order
    assert trade.exit_time >= trade.entry_time, "exit_time must be after or equal to entry_time"
    
    # Verify additional required fields
    assert hasattr(trade, 'symbol'), "Trade must have symbol field"
    assert hasattr(trade, 'side'), "Trade must have side field"
    assert hasattr(trade, 'quantity'), "Trade must have quantity field"
    assert hasattr(trade, 'exit_reason'), "Trade must have exit_reason field"
    
    assert trade.symbol is not None and len(trade.symbol) > 0, "symbol must be valid"
    assert trade.side in ["LONG", "SHORT"], "side must be LONG or SHORT"
    assert trade.quantity > 0, "quantity must be positive"
    assert trade.exit_reason in ["STOP_LOSS", "TRAILING_STOP", "SIGNAL_EXIT", "PANIC"], \
        "exit_reason must be valid"


class TestDataModels:
    """Unit tests for data model creation and validation."""
    
    def test_candle_creation(self):
        """Test creating a Candle object with valid data."""
        candle = Candle(
            timestamp=1609459200000,
            open=29000.0,
            high=29500.0,
            low=28800.0,
            close=29200.0,
            volume=1500.5
        )
        
        assert candle.timestamp == 1609459200000
        assert candle.open == 29000.0
        assert candle.high == 29500.0
        assert candle.low == 28800.0
        assert candle.close == 29200.0
        assert candle.volume == 1500.5
    
    def test_position_creation(self):
        """Test creating a Position object with valid data."""
        position = Position(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=30000.0,
            quantity=0.5,
            leverage=3,
            stop_loss=29400.0,
            trailing_stop=29400.0,
            entry_time=1609459200000,
            unrealized_pnl=0.0
        )
        
        assert position.symbol == "BTCUSDT"
        assert position.side == "LONG"
        assert position.entry_price == 30000.0
        assert position.quantity == 0.5
        assert position.leverage == 3
        assert position.stop_loss == 29400.0
        assert position.trailing_stop == 29400.0
        assert position.entry_time == 1609459200000
        assert position.unrealized_pnl == 0.0
    
    def test_trade_creation_long(self):
        """Test creating a Trade object for a long position."""
        trade = Trade(
            symbol="BTCUSDT",
            side="LONG",
            entry_price=30000.0,
            exit_price=31000.0,
            quantity=0.5,
            pnl=500.0,
            pnl_percent=3.33,
            entry_time=1609459200000,
            exit_time=1609545600000,
            exit_reason="TRAILING_STOP"
        )
        
        assert trade.symbol == "BTCUSDT"
        assert trade.side == "LONG"
        assert trade.entry_price == 30000.0
        assert trade.exit_price == 31000.0
        assert trade.quantity == 0.5
        assert trade.pnl == 500.0
        assert trade.exit_reason == "TRAILING_STOP"
    
    def test_trade_creation_short(self):
        """Test creating a Trade object for a short position."""
        trade = Trade(
            symbol="BTCUSDT",
            side="SHORT",
            entry_price=30000.0,
            exit_price=29000.0,
            quantity=0.5,
            pnl=500.0,
            pnl_percent=3.33,
            entry_time=1609459200000,
            exit_time=1609545600000,
            exit_reason="SIGNAL_EXIT"
        )
        
        assert trade.side == "SHORT"
        assert trade.pnl == 500.0
        assert trade.exit_reason == "SIGNAL_EXIT"
    
    def test_signal_creation(self):
        """Test creating a Signal object with indicator snapshot."""
        indicators = {
            "vwap": 30000.0,
            "adx": 25.5,
            "rvol": 1.5,
            "squeeze_color": "green"
        }
        
        signal = Signal(
            type="LONG_ENTRY",
            timestamp=1609459200000,
            price=30100.0,
            indicators=indicators
        )
        
        assert signal.type == "LONG_ENTRY"
        assert signal.timestamp == 1609459200000
        assert signal.price == 30100.0
        assert signal.indicators["vwap"] == 30000.0
        assert signal.indicators["adx"] == 25.5
    
    def test_indicator_state_creation(self):
        """Test creating an IndicatorState object."""
        state = IndicatorState(
            vwap_15m=30000.0,
            vwap_1h=29900.0,
            weekly_anchor_time=1609459200000,
            squeeze_value=5.2,
            squeeze_color="green",
            is_squeezed=False,
            previous_squeeze_color="gray",
            adx=25.5,
            trend_1h="BULLISH",
            trend_15m="BULLISH",
            atr_15m=300.0,
            atr_1h=450.0,
            rvol=1.5,
            current_price=30100.0,
            price_vs_vwap="ABOVE"
        )
        
        assert state.vwap_15m == 30000.0
        assert state.trend_1h == "BULLISH"
        assert state.squeeze_color == "green"
        assert state.rvol == 1.5
    
    def test_performance_metrics_creation(self):
        """Test creating a PerformanceMetrics object."""
        metrics = PerformanceMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=60.0,
            total_pnl=5000.0,
            total_pnl_percent=50.0,
            roi=50.0,
            max_drawdown=1000.0,
            max_drawdown_percent=10.0,
            profit_factor=1.5,
            sharpe_ratio=1.2,
            average_win=150.0,
            average_loss=75.0,
            largest_win=500.0,
            largest_loss=200.0,
            average_trade_duration=3600
        )
        
        assert metrics.total_trades == 100
        assert metrics.winning_trades == 60
        assert metrics.win_rate == 60.0
        assert metrics.profit_factor == 1.5
        assert metrics.sharpe_ratio == 1.2
