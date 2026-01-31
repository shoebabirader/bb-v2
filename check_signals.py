"""Quick script to check why signals aren't being generated."""

from src.config import Config
from src.data_manager import DataManager
from src.strategy import StrategyEngine
from binance.client import Client

# Load config
config = Config.load_from_file()

# Create client
client = Client(config.api_key, config.api_secret)

# Create data manager and strategy
data_manager = DataManager(config, client)
strategy = StrategyEngine(config)

# Fetch data
print("Fetching market data...")
candles_15m = data_manager.fetch_historical_data(days=2, timeframe="15m")
candles_1h = data_manager.fetch_historical_data(days=2, timeframe="1h")

print(f"Got {len(candles_15m)} 15m candles and {len(candles_1h)} 1h candles")

# Check if candles have data
if candles_15m:
    print(f"\nFirst 15m candle: Open={candles_15m[0].open}, Close={candles_15m[0].close}")
    print(f"Last 15m candle: Open={candles_15m[-1].open}, Close={candles_15m[-1].close}")
if candles_1h:
    print(f"\nFirst 1h candle: Open={candles_1h[0].open}, Close={candles_1h[0].close}")
    print(f"Last 1h candle: Open={candles_1h[-1].open}, Close={candles_1h[-1].close}")

# Update indicators
print("\nUpdating indicators...")
strategy.update_indicators(candles_15m, candles_1h)

# Print current indicator values
indicators = strategy.current_indicators
print("\n=== CURRENT MARKET CONDITIONS ===")
print(f"Symbol: {config.symbol}")
print(f"Current Price: ${indicators.current_price:.4f}")
print(f"\n15m Indicators:")
print(f"  VWAP: ${indicators.vwap_15m:.4f}")
print(f"  ATR: ${indicators.atr_15m:.4f}")
print(f"  Trend: {indicators.trend_15m}")
print(f"  Price vs VWAP: {indicators.price_vs_vwap}")
print(f"\n1h Indicators:")
print(f"  VWAP: ${indicators.vwap_1h:.4f}")
print(f"  ATR: ${indicators.atr_1h:.4f}")
print(f"  Trend: {indicators.trend_1h}")
print(f"\nSignal Indicators:")
print(f"  ADX: {indicators.adx:.2f} (threshold: {config.adx_threshold})")
print(f"  RVOL: {indicators.rvol:.2f} (threshold: {config.rvol_threshold})")
print(f"  Squeeze Color: {indicators.squeeze_color}")
print(f"  Is Squeezed: {indicators.is_squeezed}")

# Check entry conditions
print("\n=== LONG ENTRY CONDITIONS ===")
print(f"✓ Price > VWAP (15m): {indicators.price_vs_vwap == 'ABOVE'} ({indicators.current_price:.4f} vs {indicators.vwap_15m:.4f})")
print(f"✓ 1h Trend Bullish: {indicators.trend_1h == 'BULLISH'} (trend: {indicators.trend_1h})")
print(f"✓ Squeeze Green: {indicators.squeeze_color == 'green'} (color: {indicators.squeeze_color})")
print(f"✓ ADX > {config.adx_threshold}: {indicators.adx > config.adx_threshold} (ADX: {indicators.adx:.2f})")
print(f"✓ RVOL > {config.rvol_threshold}: {indicators.rvol > config.rvol_threshold} (RVOL: {indicators.rvol:.2f})")

long_signal = strategy.check_long_entry()
print(f"\nLONG SIGNAL: {'YES ✓' if long_signal else 'NO ✗'}")

print("\n=== SHORT ENTRY CONDITIONS ===")
print(f"✓ Price < VWAP (15m): {indicators.price_vs_vwap == 'BELOW'} ({indicators.current_price:.4f} vs {indicators.vwap_15m:.4f})")
print(f"✓ 1h Trend Bearish: {indicators.trend_1h == 'BEARISH'} (trend: {indicators.trend_1h})")
print(f"✓ Squeeze Red: {indicators.squeeze_color == 'red'} (color: {indicators.squeeze_color})")
print(f"✓ ADX > {config.adx_threshold}: {indicators.adx > config.adx_threshold} (ADX: {indicators.adx:.2f})")
print(f"✓ RVOL > {config.rvol_threshold}: {indicators.rvol > config.rvol_threshold} (RVOL: {indicators.rvol:.2f})")

short_signal = strategy.check_short_entry()
print(f"\nSHORT SIGNAL: {'YES ✓' if short_signal else 'NO ✗'}")
