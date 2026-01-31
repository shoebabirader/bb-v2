"""Property-based tests for StrategyEngine."""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from src.strategy import StrategyEngine
from src.config import Config
from src.models import Candle, IndicatorState
from typing import List
import time


# Helper function to generate valid candle data
@st.composite
def candle_list(draw, min_candles=50, max_candles=100):
    """Generate a list of valid candles with realistic price movements."""
    num_candles = draw(st.integers(min_value=min_candles, max_value=max_candles))
    
    # Start with a base price
    base_price = draw(st.floats(min_value=1000, max_value=50000))
    base_volume = draw(st.floats(min_value=100, max_value=10000))
    
    candles = []
    current_time = int(time.time() * 1000) - (num_candles * 15 * 60 * 1000)  # 15 min intervals
    
    for i in range(num_candles):
        # Generate OHLC with realistic relationships
        open_price = base_price * draw(st.floats(min_value=0.95, max_value=1.05))
        close_price = open_price * draw(st.floats(min_value=0.98, max_value=1.02))
        high_price = max(open_price, close_price) * draw(st.floats(min_value=1.0, max_value=1.01))
        low_price = min(open_price, close_price) * draw(st.floats(min_value=0.99, max_value=1.0))
        volume = base_volume * draw(st.floats(min_value=0.5, max_value=2.0))
        
        candles.append(Candle(
            timestamp=current_time + (i * 15 * 60 * 1000),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        ))
        
        # Update base price for next candle (random walk)
        base_price = close_price
    
    return candles


@st.composite
def candle_list_1h(draw, min_candles=30, max_candles=50):
    """Generate a list of 1-hour candles."""
    num_candles = draw(st.integers(min_value=min_candles, max_value=max_candles))
    
    base_price = draw(st.floats(min_value=1000, max_value=50000))
    base_volume = draw(st.floats(min_value=1000, max_value=50000))
    
    candles = []
    current_time = int(time.time() * 1000) - (num_candles * 60 * 60 * 1000)  # 1 hour intervals
    
    for i in range(num_candles):
        open_price = base_price * draw(st.floats(min_value=0.95, max_value=1.05))
        close_price = open_price * draw(st.floats(min_value=0.98, max_value=1.02))
        high_price = max(open_price, close_price) * draw(st.floats(min_value=1.0, max_value=1.01))
        low_price = min(open_price, close_price) * draw(st.floats(min_value=0.99, max_value=1.0))
        volume = base_volume * draw(st.floats(min_value=0.5, max_value=2.0))
        
        candles.append(Candle(
            timestamp=current_time + (i * 60 * 60 * 1000),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume
        ))
        
        base_price = close_price
    
    return candles


# Feature: binance-futures-bot, Property 16: Long Entry Signal Validity
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large])
@given(
    candles_15m=candle_list(min_candles=50, max_candles=100),
    candles_1h=candle_list_1h(min_candles=30, max_candles=50)
)
def test_long_entry_signal_validity(candles_15m: List[Candle], candles_1h: List[Candle]):
    """Property 16: Long Entry Signal Validity
    
    For any LONG_ENTRY signal generated, all of the following conditions must be true:
    - 15m price > VWAP
    - 1h trend is bullish
    - Squeeze releases green
    - ADX > 20
    - RVOL > 1.2
    
    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5
    """
    config = Config()
    strategy = StrategyEngine(config)
    
    # Update indicators
    strategy.update_indicators(candles_15m, candles_1h)
    
    # Check for long entry signal
    signal = strategy.check_long_entry()
    
    # If a signal was generated, verify all conditions are met
    if signal is not None:
        assert signal.type == "LONG_ENTRY", "Signal type must be LONG_ENTRY"
        
        # Verify all conditions
        assert strategy.current_indicators.price_vs_vwap == "ABOVE", \
            "Price must be above VWAP for long entry"
        
        assert strategy.current_indicators.trend_1h == "BULLISH", \
            "1h trend must be BULLISH for long entry"
        
        assert strategy.current_indicators.squeeze_color == "green", \
            "Squeeze must release green for long entry"
        
        assert strategy.current_indicators.adx > config.adx_threshold, \
            f"ADX must be > {config.adx_threshold} for long entry"
        
        assert strategy.current_indicators.rvol > config.rvol_threshold, \
            f"RVOL must be > {config.rvol_threshold} for long entry"
        
        # Verify signal has required fields
        assert signal.timestamp > 0, "Signal must have valid timestamp"
        assert signal.price > 0, "Signal must have valid price"
        assert isinstance(signal.indicators, dict), "Signal must have indicators dict"


# Feature: binance-futures-bot, Property 17: Short Entry Signal Validity
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large])
@given(
    candles_15m=candle_list(min_candles=50, max_candles=100),
    candles_1h=candle_list_1h(min_candles=30, max_candles=50)
)
def test_short_entry_signal_validity(candles_15m: List[Candle], candles_1h: List[Candle]):
    """Property 17: Short Entry Signal Validity
    
    For any SHORT_ENTRY signal generated, all of the following conditions must be true:
    - 15m price < VWAP
    - 1h trend is bearish
    - Squeeze releases maroon
    - ADX > 20
    - RVOL > 1.2
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    config = Config()
    strategy = StrategyEngine(config)
    
    # Update indicators
    strategy.update_indicators(candles_15m, candles_1h)
    
    # Check for short entry signal
    signal = strategy.check_short_entry()
    
    # If a signal was generated, verify all conditions are met
    if signal is not None:
        assert signal.type == "SHORT_ENTRY", "Signal type must be SHORT_ENTRY"
        
        # Verify all conditions
        assert strategy.current_indicators.price_vs_vwap == "BELOW", \
            "Price must be below VWAP for short entry"
        
        assert strategy.current_indicators.trend_1h == "BEARISH", \
            "1h trend must be BEARISH for short entry"
        
        assert strategy.current_indicators.squeeze_color == "maroon", \
            "Squeeze must release maroon for short entry"
        
        assert strategy.current_indicators.adx > config.adx_threshold, \
            f"ADX must be > {config.adx_threshold} for short entry"
        
        assert strategy.current_indicators.rvol > config.rvol_threshold, \
            f"RVOL must be > {config.rvol_threshold} for short entry"
        
        # Verify signal has required fields
        assert signal.timestamp > 0, "Signal must have valid timestamp"
        assert signal.price > 0, "Signal must have valid price"
        assert isinstance(signal.indicators, dict), "Signal must have indicators dict"


# Feature: binance-futures-bot, Property 18: Signal Completeness
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large])
@given(
    candles_15m=candle_list(min_candles=50, max_candles=100),
    candles_1h=candle_list_1h(min_candles=30, max_candles=50)
)
def test_signal_completeness(candles_15m: List[Candle], candles_1h: List[Candle]):
    """Property 18: Signal Completeness
    
    For any entry signal (LONG or SHORT), the signal object should contain
    type, timestamp, price, and indicators fields with valid values.
    
    Validates: Requirements 5.6, 6.6
    """
    config = Config()
    strategy = StrategyEngine(config)
    
    # Update indicators
    strategy.update_indicators(candles_15m, candles_1h)
    
    # Check both long and short signals
    long_signal = strategy.check_long_entry()
    short_signal = strategy.check_short_entry()
    
    # Test whichever signal was generated
    for signal in [long_signal, short_signal]:
        if signal is not None:
            # Verify all required fields are present
            assert hasattr(signal, 'type'), "Signal must have 'type' field"
            assert hasattr(signal, 'timestamp'), "Signal must have 'timestamp' field"
            assert hasattr(signal, 'price'), "Signal must have 'price' field"
            assert hasattr(signal, 'indicators'), "Signal must have 'indicators' field"
            
            # Verify field values are valid
            assert signal.type in ["LONG_ENTRY", "SHORT_ENTRY", "EXIT"], \
                "Signal type must be valid"
            assert signal.timestamp > 0, "Timestamp must be positive"
            assert signal.price > 0, "Price must be positive"
            assert isinstance(signal.indicators, dict), "Indicators must be a dictionary"
            assert len(signal.indicators) > 0, "Indicators dict must not be empty"


# Feature: binance-futures-bot, Property 14: Bullish Trend Signal Filtering
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large])
@given(
    candles_15m=candle_list(min_candles=50, max_candles=100),
    candles_1h=candle_list_1h(min_candles=30, max_candles=50)
)
def test_bullish_trend_signal_filtering(candles_15m: List[Candle], candles_1h: List[Candle]):
    """Property 14: Bullish Trend Signal Filtering
    
    For any market state where the 1-hour trend is bullish, the Signal_Generator
    should only emit LONG_ENTRY signals and never emit SHORT_ENTRY signals.
    
    Validates: Requirements 4.2
    """
    config = Config()
    strategy = StrategyEngine(config)
    
    # Update indicators
    strategy.update_indicators(candles_15m, candles_1h)
    
    # If 1h trend is bullish, check signal filtering
    if strategy.current_indicators.trend_1h == "BULLISH":
        long_signal = strategy.check_long_entry()
        short_signal = strategy.check_short_entry()
        
        # Short signal should never be generated when trend is bullish
        assert short_signal is None, \
            "SHORT_ENTRY signal should not be generated when 1h trend is BULLISH"
        
        # If any signal is generated, it must be long
        if long_signal is not None:
            assert long_signal.type == "LONG_ENTRY", \
                "Only LONG_ENTRY signals allowed when 1h trend is BULLISH"


# Feature: binance-futures-bot, Property 15: Bearish Trend Signal Filtering
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large])
@given(
    candles_15m=candle_list(min_candles=50, max_candles=100),
    candles_1h=candle_list_1h(min_candles=30, max_candles=50)
)
def test_bearish_trend_signal_filtering(candles_15m: List[Candle], candles_1h: List[Candle]):
    """Property 15: Bearish Trend Signal Filtering
    
    For any market state where the 1-hour trend is bearish, the Signal_Generator
    should only emit SHORT_ENTRY signals and never emit LONG_ENTRY signals.
    
    Validates: Requirements 4.3
    """
    config = Config()
    strategy = StrategyEngine(config)
    
    # Update indicators
    strategy.update_indicators(candles_15m, candles_1h)
    
    # If 1h trend is bearish, check signal filtering
    if strategy.current_indicators.trend_1h == "BEARISH":
        long_signal = strategy.check_long_entry()
        short_signal = strategy.check_short_entry()
        
        # Long signal should never be generated when trend is bearish
        assert long_signal is None, \
            "LONG_ENTRY signal should not be generated when 1h trend is BEARISH"
        
        # If any signal is generated, it must be short
        if short_signal is not None:
            assert short_signal.type == "SHORT_ENTRY", \
                "Only SHORT_ENTRY signals allowed when 1h trend is BEARISH"


# Feature: binance-futures-bot, Property 13: Trend Direction Consistency
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large])
@given(
    candles_1h=candle_list_1h(min_candles=30, max_candles=50)
)
def test_trend_direction_consistency(candles_1h: List[Candle]):
    """Property 13: Trend Direction Consistency
    
    For any 1-hour candle data with VWAP and momentum indicators, the determined
    trend direction should remain consistent until the next 1-hour candle close.
    
    Validates: Requirements 4.1, 4.4
    """
    config = Config()
    strategy = StrategyEngine(config)
    
    # Generate 15m candles (need them for update_indicators)
    candles_15m = []
    base_price = candles_1h[0].open if candles_1h else 30000
    current_time = int(time.time() * 1000) - (50 * 15 * 60 * 1000)
    
    for i in range(50):
        candles_15m.append(Candle(
            timestamp=current_time + (i * 15 * 60 * 1000),
            open=base_price,
            high=base_price * 1.01,
            low=base_price * 0.99,
            close=base_price,
            volume=1000
        ))
    
    # Update indicators with initial data
    strategy.update_indicators(candles_15m, candles_1h)
    initial_trend = strategy.current_indicators.trend_1h
    
    # Update indicators again with same 1h data (simulating time passing within same 1h candle)
    # Add a few more 15m candles but keep 1h data the same
    for i in range(4):
        candles_15m.append(Candle(
            timestamp=candles_15m[-1].timestamp + (15 * 60 * 1000),
            open=base_price,
            high=base_price * 1.01,
            low=base_price * 0.99,
            close=base_price,
            volume=1000
        ))
    
    strategy.update_indicators(candles_15m, candles_1h)
    updated_trend = strategy.current_indicators.trend_1h
    
    # Trend should remain consistent when 1h data hasn't changed
    assert initial_trend == updated_trend, \
        "Trend direction should remain consistent when 1h candle data hasn't changed"
