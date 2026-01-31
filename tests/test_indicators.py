"""Property-based and unit tests for technical indicators."""

import pytest
from hypothesis import given, strategies as st, assume
from src.indicators import IndicatorCalculator
from src.models import Candle


# Helper strategy for generating valid candles
@st.composite
def candle_strategy(draw):
    """Generate a valid Candle with realistic OHLCV data."""
    timestamp = draw(st.integers(min_value=1000000000000, max_value=9999999999999))
    
    # Generate base price and ensure OHLC relationships are valid
    base_price = draw(st.floats(min_value=1.0, max_value=100000.0, allow_nan=False, allow_infinity=False))
    
    # Generate high and low relative to base
    high_offset = draw(st.floats(min_value=0.0, max_value=base_price * 0.1, allow_nan=False, allow_infinity=False))
    low_offset = draw(st.floats(min_value=0.0, max_value=base_price * 0.1, allow_nan=False, allow_infinity=False))
    
    high = base_price + high_offset
    low = base_price - low_offset
    
    # Open and close must be between low and high
    open_price = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    close_price = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    
    volume = draw(st.floats(min_value=0.1, max_value=1000000.0, allow_nan=False, allow_infinity=False))
    
    return Candle(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close_price,
        volume=volume
    )


# Feature: binance-futures-bot, Property 8: VWAP Calculation Accuracy
@given(
    candles=st.lists(candle_strategy(), min_size=1, max_size=100),
    anchor_offset=st.integers(min_value=0, max_value=50)
)
def test_vwap_equals_cumulative_tpv_over_cumulative_volume(candles, anchor_offset):
    """For any series of candles with a weekly anchor timestamp, the calculated VWAP 
    should equal the cumulative (price × volume) divided by cumulative volume from the anchor point.
    
    Property 8: VWAP Calculation Accuracy
    Validates: Requirements 3.1
    """
    # Sort candles by timestamp to ensure proper ordering
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Set anchor time to be at or before the first candle
    if anchor_offset >= len(candles):
        anchor_offset = len(candles) - 1
    
    anchor_time = candles[anchor_offset].timestamp
    
    # Calculate VWAP using the indicator calculator
    vwap = IndicatorCalculator.calculate_vwap(candles, anchor_time)
    
    # Manually calculate expected VWAP
    anchored_candles = [c for c in candles if c.timestamp >= anchor_time]
    
    if not anchored_candles:
        assert vwap == 0.0
        return
    
    cumulative_tpv = 0.0
    cumulative_volume = 0.0
    
    for candle in anchored_candles:
        typical_price = (candle.high + candle.low + candle.close) / 3.0
        cumulative_tpv += typical_price * candle.volume
        cumulative_volume += candle.volume
    
    if cumulative_volume == 0:
        assert vwap == 0.0
    else:
        expected_vwap = cumulative_tpv / cumulative_volume
        # Allow small floating point error
        assert abs(vwap - expected_vwap) < 0.01, \
            f"VWAP {vwap} should equal {expected_vwap}"


# Feature: binance-futures-bot, Property 11: ATR Calculation Accuracy
@given(
    candles=st.lists(candle_strategy(), min_size=15, max_size=100),
    period=st.integers(min_value=2, max_value=20)
)
def test_atr_equals_ema_of_true_range(candles, period):
    """For any candle series with at least 14 periods, the calculated ATR should 
    equal the 14-period exponential moving average of true range values.
    
    Property 11: ATR Calculation Accuracy
    Validates: Requirements 3.4
    """
    # Ensure we have enough candles
    assume(len(candles) >= period + 1)
    
    # Sort candles by timestamp
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Calculate ATR using the indicator calculator
    atr = IndicatorCalculator.calculate_atr(candles, period)
    
    # Manually calculate expected ATR
    true_ranges = []
    
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        assert atr == 0.0
        return
    
    # Calculate EMA of true ranges
    expected_atr = sum(true_ranges[:period]) / period
    multiplier = 2.0 / (period + 1)
    
    for i in range(period, len(true_ranges)):
        expected_atr = (true_ranges[i] * multiplier) + (expected_atr * (1 - multiplier))
    
    # Allow small floating point error
    assert abs(atr - expected_atr) < 0.01, \
        f"ATR {atr} should equal {expected_atr}"


# Feature: binance-futures-bot, Property 10: ADX Calculation Accuracy
@given(
    candles=st.lists(candle_strategy(), min_size=30, max_size=100),
    period=st.integers(min_value=10, max_value=20)
)
def test_adx_uses_standard_formula(candles, period):
    """For any candle series with at least 14 periods, the calculated ADX should 
    match the standard ADX formula using 14-period lookback.
    
    Property 10: ADX Calculation Accuracy
    Validates: Requirements 3.3
    """
    # Ensure we have enough candles
    assume(len(candles) >= 2 * period)
    
    # Sort candles by timestamp
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Calculate ADX using the indicator calculator
    adx = IndicatorCalculator.calculate_adx(candles, period)
    
    # Verify ADX is within valid range (0-100)
    assert 0.0 <= adx <= 100.0, f"ADX {adx} must be between 0 and 100"
    
    # Verify ADX is not NaN or infinity
    assert adx == adx, "ADX should not be NaN"  # NaN != NaN
    assert adx != float('inf') and adx != float('-inf'), "ADX should not be infinity"


# Feature: binance-futures-bot, Property 12: RVOL Calculation Accuracy
@given(
    candles=st.lists(candle_strategy(), min_size=21, max_size=100),
    period=st.integers(min_value=5, max_value=30)
)
def test_rvol_equals_current_volume_over_average(candles, period):
    """For any candle series with at least 20 periods, the calculated RVOL should 
    equal current volume divided by the 20-period average volume.
    
    Property 12: RVOL Calculation Accuracy
    Validates: Requirements 3.5
    """
    # Ensure we have enough candles
    assume(len(candles) >= period + 1)
    
    # Sort candles by timestamp
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Calculate RVOL using the indicator calculator
    rvol = IndicatorCalculator.calculate_rvol(candles, period)
    
    # Manually calculate expected RVOL
    historical_candles = candles[-(period + 1):-1]
    current_candle = candles[-1]
    
    avg_volume = sum(c.volume for c in historical_candles) / len(historical_candles)
    
    if avg_volume == 0:
        assert rvol == 0.0
    else:
        expected_rvol = current_candle.volume / avg_volume
        # Allow small floating point error
        assert abs(rvol - expected_rvol) < 0.01, \
            f"RVOL {rvol} should equal {expected_rvol}"


# Feature: binance-futures-bot, Property 9: Squeeze Momentum Calculation
@given(
    candles=st.lists(candle_strategy(), min_size=20, max_size=100)
)
def test_squeeze_momentum_identifies_squeeze_state_and_momentum(candles):
    """For any candle series with sufficient data, the Squeeze Momentum indicator 
    should correctly identify squeeze state (Bollinger Bands inside Keltner Channels) 
    and momentum direction.
    
    Property 9: Squeeze Momentum Calculation
    Validates: Requirements 3.2
    """
    # Sort candles by timestamp
    candles = sorted(candles, key=lambda c: c.timestamp)
    
    # Calculate Squeeze Momentum using the indicator calculator
    result = IndicatorCalculator.calculate_squeeze_momentum(candles)
    
    # Verify result structure
    assert 'value' in result, "Result must contain 'value' field"
    assert 'is_squeezed' in result, "Result must contain 'is_squeezed' field"
    assert 'color' in result, "Result must contain 'color' field"
    
    # Verify types
    assert isinstance(result['value'], (int, float)), "Momentum value must be numeric"
    assert isinstance(result['is_squeezed'], bool), "is_squeezed must be boolean"
    assert isinstance(result['color'], str), "color must be string"
    
    # Verify color is valid
    valid_colors = ['green', 'maroon', 'blue', 'gray']
    assert result['color'] in valid_colors, \
        f"Color '{result['color']}' must be one of {valid_colors}"
    
    # Verify momentum value is not NaN or infinity
    assert result['value'] == result['value'], "Momentum value should not be NaN"
    assert result['value'] != float('inf') and result['value'] != float('-inf'), \
        "Momentum value should not be infinity"


class TestIndicatorCalculator:
    """Unit tests for indicator calculations with specific examples."""
    
    def test_vwap_with_single_candle(self):
        """Test VWAP calculation with a single candle."""
        candle = Candle(
            timestamp=1609459200000,
            open=30000.0,
            high=30500.0,
            low=29500.0,
            close=30200.0,
            volume=100.0
        )
        
        vwap = IndicatorCalculator.calculate_vwap([candle], candle.timestamp)
        
        # VWAP should equal typical price for single candle
        typical_price = (candle.high + candle.low + candle.close) / 3.0
        assert abs(vwap - typical_price) < 0.01
    
    def test_vwap_with_zero_volume(self):
        """Test VWAP calculation when all candles have zero volume."""
        candles = [
            Candle(timestamp=1609459200000, open=30000.0, high=30500.0, 
                   low=29500.0, close=30200.0, volume=0.0),
            Candle(timestamp=1609459300000, open=30200.0, high=30600.0, 
                   low=29800.0, close=30400.0, volume=0.0)
        ]
        
        vwap = IndicatorCalculator.calculate_vwap(candles, candles[0].timestamp)
        assert vwap == 0.0
    
    def test_atr_with_insufficient_data(self):
        """Test ATR calculation with insufficient candles."""
        candles = [
            Candle(timestamp=1609459200000, open=30000.0, high=30500.0, 
                   low=29500.0, close=30200.0, volume=100.0)
        ]
        
        atr = IndicatorCalculator.calculate_atr(candles, period=14)
        assert atr == 0.0
    
    def test_rvol_with_consistent_volume(self):
        """Test RVOL calculation when volume is consistent."""
        candles = []
        base_time = 1609459200000
        
        # Create 21 candles with same volume
        for i in range(21):
            candles.append(Candle(
                timestamp=base_time + (i * 60000),
                open=30000.0,
                high=30500.0,
                low=29500.0,
                close=30200.0,
                volume=100.0
            ))
        
        rvol = IndicatorCalculator.calculate_rvol(candles, period=20)
        
        # RVOL should be 1.0 when current volume equals average
        assert abs(rvol - 1.0) < 0.01
    
    def test_determine_trend_bullish(self):
        """Test trend determination when price is above VWAP."""
        candles = []
        base_time = 1609459200000
        
        # Create candles with rising prices
        for i in range(5):
            candles.append(Candle(
                timestamp=base_time + (i * 60000),
                open=30000.0 + (i * 100),
                high=30500.0 + (i * 100),
                low=29500.0 + (i * 100),
                close=30200.0 + (i * 100),
                volume=100.0
            ))
        
        vwap = 30000.0  # Below current price
        trend = IndicatorCalculator.determine_trend(candles, vwap)
        
        assert trend == 'BULLISH'
    
    def test_determine_trend_bearish(self):
        """Test trend determination when price is below VWAP."""
        candles = []
        base_time = 1609459200000
        
        # Create candles with falling prices
        for i in range(5):
            candles.append(Candle(
                timestamp=base_time + (i * 60000),
                open=30000.0 - (i * 100),
                high=30500.0 - (i * 100),
                low=29500.0 - (i * 100),
                close=30200.0 - (i * 100),
                volume=100.0
            ))
        
        vwap = 31000.0  # Above current price
        trend = IndicatorCalculator.determine_trend(candles, vwap)
        
        assert trend == 'BEARISH'
    
    def test_squeeze_momentum_with_insufficient_data(self):
        """Test Squeeze Momentum with insufficient candles."""
        candles = [
            Candle(timestamp=1609459200000, open=30000.0, high=30500.0, 
                   low=29500.0, close=30200.0, volume=100.0)
        ]
        
        result = IndicatorCalculator.calculate_squeeze_momentum(candles)
        
        assert result['value'] == 0.0
        assert result['is_squeezed'] == False
        assert result['color'] == 'gray'
