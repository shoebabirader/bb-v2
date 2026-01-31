"""Strategy engine for signal generation in Binance Futures Trading Bot."""

from typing import List, Optional, Dict
from src.models import Candle, Signal, IndicatorState
from src.indicators import IndicatorCalculator
from src.config import Config
import time


class StrategyEngine:
    """Strategy engine that generates trading signals based on technical indicators.
    
    The engine calculates indicators on multiple timeframes (15m and 1h),
    determines trend direction, and generates LONG_ENTRY or SHORT_ENTRY signals
    when all conditions are met.
    """
    
    def __init__(self, config: Config):
        """Initialize the strategy engine.
        
        Args:
            config: Configuration object with indicator parameters
        """
        self.config = config
        self.indicator_calc = IndicatorCalculator()
        self.current_indicators = IndicatorState()
        self._previous_squeeze_color = "gray"
        
    def update_indicators(
        self, 
        candles_15m: List[Candle], 
        candles_1h: List[Candle]
    ) -> None:
        """Recalculate all indicators with latest candle data.
        
        Updates the current_indicators state with fresh calculations.
        Skips update if insufficient data is available.
        
        Args:
            candles_15m: List of 15-minute candles
            candles_1h: List of 1-hour candles
        """
        # Check if we have sufficient data
        if not self._has_sufficient_data(candles_15m, candles_1h):
            return
        
        # Get current price
        self.current_indicators.current_price = candles_15m[-1].close
        
        # Calculate weekly anchor time (most recent Monday 00:00 UTC)
        current_time = candles_15m[-1].timestamp
        # Simplified: use a fixed anchor for now (can be improved)
        # For production, calculate actual weekly open
        self.current_indicators.weekly_anchor_time = self._get_weekly_anchor(current_time)
        
        # Calculate VWAP for both timeframes
        self.current_indicators.vwap_15m = self.indicator_calc.calculate_vwap(
            candles_15m, 
            self.current_indicators.weekly_anchor_time
        )
        self.current_indicators.vwap_1h = self.indicator_calc.calculate_vwap(
            candles_1h, 
            self.current_indicators.weekly_anchor_time
        )
        
        # Calculate ATR for both timeframes
        self.current_indicators.atr_15m = self.indicator_calc.calculate_atr(
            candles_15m, 
            self.config.atr_period
        )
        self.current_indicators.atr_1h = self.indicator_calc.calculate_atr(
            candles_1h, 
            self.config.atr_period
        )
        
        # Calculate ADX on 15m timeframe
        self.current_indicators.adx = self.indicator_calc.calculate_adx(
            candles_15m, 
            self.config.adx_period
        )
        
        # Calculate RVOL on 15m timeframe
        self.current_indicators.rvol = self.indicator_calc.calculate_rvol(
            candles_15m, 
            self.config.rvol_period
        )
        
        # Calculate Squeeze Momentum on 15m timeframe
        squeeze_result = self.indicator_calc.calculate_squeeze_momentum(candles_15m)
        self.current_indicators.squeeze_value = squeeze_result['value']
        self.current_indicators.is_squeezed = squeeze_result['is_squeezed']
        self.current_indicators.previous_squeeze_color = self._previous_squeeze_color
        self.current_indicators.squeeze_color = squeeze_result['color']
        
        # Update previous squeeze color for next iteration
        self._previous_squeeze_color = squeeze_result['color']
        
        # Determine trends
        self.current_indicators.trend_15m = self.indicator_calc.determine_trend(
            candles_15m, 
            self.current_indicators.vwap_15m
        )
        self.current_indicators.trend_1h = self.indicator_calc.determine_trend(
            candles_1h, 
            self.current_indicators.vwap_1h
        )
        
        # Determine price vs VWAP
        if self.current_indicators.current_price > self.current_indicators.vwap_15m:
            self.current_indicators.price_vs_vwap = "ABOVE"
        else:
            self.current_indicators.price_vs_vwap = "BELOW"
    
    def check_long_entry(self) -> Optional[Signal]:
        """Check if long entry conditions are met.
        
        Long entry conditions:
        1. 15m price > VWAP
        2. 1h trend is BULLISH
        3. Squeeze releases green (positive momentum)
        4. ADX > threshold (default 20)
        5. RVOL > threshold (default 1.2)
        
        Returns:
            Signal object if all conditions met, None otherwise
        """
        # Check all conditions
        conditions_met = (
            self.current_indicators.price_vs_vwap == "ABOVE" and
            self.current_indicators.trend_1h == "BULLISH" and
            self.current_indicators.squeeze_color == "green" and
            self.current_indicators.adx > self.config.adx_threshold and
            self.current_indicators.rvol > self.config.rvol_threshold
        )
        
        if not conditions_met:
            return None
        
        # Create signal with indicator snapshot
        signal = Signal(
            type="LONG_ENTRY",
            timestamp=int(time.time() * 1000),
            price=self.current_indicators.current_price,
            indicators=self.get_indicator_snapshot()
        )
        
        return signal
    
    def check_short_entry(self) -> Optional[Signal]:
        """Check if short entry conditions are met.
        
        Short entry conditions:
        1. 15m price < VWAP
        2. 1h trend is BEARISH
        3. Squeeze releases maroon (negative momentum)
        4. ADX > threshold (default 20)
        5. RVOL > threshold (default 1.2)
        
        Returns:
            Signal object if all conditions met, None otherwise
        """
        # Check all conditions
        conditions_met = (
            self.current_indicators.price_vs_vwap == "BELOW" and
            self.current_indicators.trend_1h == "BEARISH" and
            self.current_indicators.squeeze_color == "maroon" and
            self.current_indicators.adx > self.config.adx_threshold and
            self.current_indicators.rvol > self.config.rvol_threshold
        )
        
        if not conditions_met:
            return None
        
        # Create signal with indicator snapshot
        signal = Signal(
            type="SHORT_ENTRY",
            timestamp=int(time.time() * 1000),
            price=self.current_indicators.current_price,
            indicators=self.get_indicator_snapshot()
        )
        
        return signal
    
    def get_indicator_snapshot(self) -> Dict[str, float]:
        """Return current indicator values for logging and display.
        
        Returns:
            Dictionary containing all current indicator values
        """
        return {
            'vwap_15m': self.current_indicators.vwap_15m,
            'vwap_1h': self.current_indicators.vwap_1h,
            'atr_15m': self.current_indicators.atr_15m,
            'atr_1h': self.current_indicators.atr_1h,
            'adx': self.current_indicators.adx,
            'rvol': self.current_indicators.rvol,
            'squeeze_value': self.current_indicators.squeeze_value,
            'squeeze_color': self.current_indicators.squeeze_color,
            'is_squeezed': float(self.current_indicators.is_squeezed),
            'trend_15m': self.current_indicators.trend_15m,
            'trend_1h': self.current_indicators.trend_1h,
            'current_price': self.current_indicators.current_price,
            'price_vs_vwap': self.current_indicators.price_vs_vwap
        }
    
    def _has_sufficient_data(
        self, 
        candles_15m: List[Candle], 
        candles_1h: List[Candle]
    ) -> bool:
        """Check if there is sufficient data to calculate indicators.
        
        Args:
            candles_15m: List of 15-minute candles
            candles_1h: List of 1-hour candles
            
        Returns:
            True if sufficient data available, False otherwise
        """
        # Need enough data for all indicators
        # ATR and ADX need at least 2 * period candles
        min_15m_candles = max(
            2 * self.config.atr_period,
            2 * self.config.adx_period,
            self.config.rvol_period + 1,
            20  # For squeeze momentum (BB period)
        )
        
        min_1h_candles = max(
            2 * self.config.atr_period,
            3  # For trend determination
        )
        
        return (
            len(candles_15m) >= min_15m_candles and
            len(candles_1h) >= min_1h_candles
        )
    
    def _get_weekly_anchor(self, timestamp_ms: int) -> int:
        """Calculate the most recent weekly anchor time (Monday 00:00 UTC).
        
        Args:
            timestamp_ms: Current timestamp in milliseconds
            
        Returns:
            Timestamp of most recent Monday 00:00 UTC in milliseconds
        """
        # Convert to seconds
        timestamp_s = timestamp_ms // 1000
        
        # Get day of week (0 = Monday, 6 = Sunday)
        import datetime
        dt = datetime.datetime.utcfromtimestamp(timestamp_s)
        days_since_monday = dt.weekday()
        
        # Calculate Monday 00:00 UTC
        monday_dt = dt - datetime.timedelta(
            days=days_since_monday,
            hours=dt.hour,
            minutes=dt.minute,
            seconds=dt.second,
            microseconds=dt.microsecond
        )
        
        # Convert back to milliseconds
        return int(monday_dt.timestamp() * 1000)
