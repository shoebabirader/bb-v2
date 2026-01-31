# Data Flow Explanation

## How Historical Data is Stored and Used

### Storage Location

**Historical data is NOT stored on disk** - it's stored **in memory only** using circular buffers:

```python
# From src/data_manager.py
self.candles_15m: deque = deque(maxlen=500)  # Max 500 15-minute candles
self.candles_1h: deque = deque(maxlen=500)   # Max 500 1-hour candles
```

**Why circular buffers?**
- Memory efficient (automatically removes old data when full)
- Fast access to recent candles
- No disk I/O overhead
- Perfect for real-time trading where you only need recent history

**What gets stored on disk:**
- ✅ Trade logs (`logs/trades.log`)
- ✅ Error logs (`logs/errors.log`)
- ✅ System logs (`logs/system.log`)
- ✅ Performance metrics (`binance_results.json`)
- ❌ Historical candle data (NOT stored)

---

## Data Flow by Mode

### 1. BACKTEST Mode

**Data Source:** Historical data fetched from Binance API

**Flow:**
```
1. Fetch historical data from Binance API
   ↓
2. Store in memory (candles_15m, candles_1h buffers)
   ↓
3. Backtest engine iterates through historical candles
   ↓
4. Strategy calculates indicators on historical data
   ↓
5. Generates signals based on historical conditions
   ↓
6. Simulates trades with fees and slippage
   ↓
7. Results saved to binance_results.json
```

**Key Points:**
- ✅ Uses ONLY historical data
- ✅ Data is fetched once at startup
- ✅ No real-time updates
- ✅ No WebSocket connections
- ✅ Simulates trading on past data
- ✅ Safe - no real money involved

**Example:**
```python
# Fetches 90 days of historical data
candles_15m = data_manager.fetch_historical_data(days=90, timeframe="15m")
candles_1h = data_manager.fetch_historical_data(days=90, timeframe="1h")

# Backtest engine processes all historical candles
backtest_engine.run_backtest(candles_15m, candles_1h)
```

---

### 2. PAPER Trading Mode

**Data Source:** Real-time data from Binance WebSocket + Initial historical data

**Flow:**
```
1. Fetch 7 days of historical data (for indicator warmup)
   ↓
2. Store in memory buffers
   ↓
3. Start WebSocket connections for real-time data
   ↓
4. Receive live candles as they close (every 15m and 1h)
   ↓
5. Add new candles to memory buffers
   ↓
6. Strategy calculates indicators on latest data
   ↓
7. Generates signals based on LIVE market conditions
   ↓
8. SIMULATES order execution (no real orders)
   ↓
9. Tracks performance as if trading live
```

**Key Points:**
- ✅ Uses LIVE real-time data from WebSocket
- ✅ Fetches initial historical data for indicator calculation
- ✅ WebSocket streams provide continuous updates
- ✅ Simulates execution (no real orders placed)
- ✅ Safe - no real money involved
- ✅ Tests strategy with current market conditions

**Example:**
```python
# Initial historical data for indicators
data_manager.fetch_historical_data(days=7, timeframe="15m")
data_manager.fetch_historical_data(days=7, timeframe="1h")

# Start WebSocket for real-time updates
data_manager.start_websocket_streams()

# As new candles arrive via WebSocket:
# - They're added to memory buffers
# - Strategy recalculates indicators
# - Generates signals on live data
# - Simulates trades (no real execution)
```

---

### 3. LIVE Trading Mode

**Data Source:** Real-time data from Binance WebSocket + Initial historical data

**Flow:**
```
1. Fetch 7 days of historical data (for indicator warmup)
   ↓
2. Store in memory buffers
   ↓
3. Configure leverage and margin on Binance
   ↓
4. Start WebSocket connections for real-time data
   ↓
5. Receive live candles as they close
   ↓
6. Add new candles to memory buffers
   ↓
7. Strategy calculates indicators on latest data
   ↓
8. Generates signals based on LIVE market conditions
   ↓
9. EXECUTES REAL ORDERS on Binance Futures
   ↓
10. Manages real positions with real money
```

**Key Points:**
- ✅ Uses LIVE real-time data from WebSocket
- ✅ Fetches initial historical data for indicator calculation
- ✅ WebSocket streams provide continuous updates
- ⚠️ EXECUTES REAL ORDERS on Binance
- ⚠️ TRADES WITH REAL MONEY
- ⚠️ Real risk - can lose money

**Example:**
```python
# Initial historical data for indicators
data_manager.fetch_historical_data(days=7, timeframe="15m")
data_manager.fetch_historical_data(days=7, timeframe="1h")

# Configure trading parameters
order_executor.set_leverage(symbol, 3)
order_executor.set_margin_type(symbol, "ISOLATED")

# Start WebSocket for real-time updates
data_manager.start_websocket_streams()

# As new candles arrive via WebSocket:
# - They're added to memory buffers
# - Strategy recalculates indicators
# - Generates signals on live data
# - PLACES REAL ORDERS on Binance
```

---

## Comparison Table

| Feature | BACKTEST | PAPER | LIVE |
|---------|----------|-------|------|
| **Data Source** | Historical only | Historical + Real-time | Historical + Real-time |
| **Initial Data** | 90 days (configurable) | 7 days | 7 days |
| **WebSocket** | ❌ No | ✅ Yes | ✅ Yes |
| **Real-time Updates** | ❌ No | ✅ Yes | ✅ Yes |
| **Order Execution** | Simulated | Simulated | **REAL** |
| **Money at Risk** | ❌ No | ❌ No | ⚠️ **YES** |
| **Use Case** | Test strategy on past data | Test with live data safely | Trade with real money |
| **API Keys Required** | Optional | Required | Required |
| **Speed** | Fast (processes all data at once) | Real-time (waits for candles) | Real-time (waits for candles) |

---

## Why This Design?

### Memory-Only Storage
1. **Speed**: No disk I/O bottlenecks
2. **Simplicity**: No database management
3. **Efficiency**: Circular buffers auto-manage memory
4. **Real-time**: Perfect for live trading

### Initial Historical Data in PAPER/LIVE
The 7 days of historical data is needed because:
- Indicators need historical context (e.g., 14-period ATR needs 14 candles)
- VWAP is anchored to weekly open (needs data from start of week)
- Strategy needs to calculate trend direction before trading

### WebSocket for Real-time Data
- Provides instant updates when candles close
- More efficient than polling the API
- Automatic reconnection on disconnect
- Low latency for time-sensitive trading

---

## Data Persistence

**What IS saved to disk:**

1. **Trade Logs** (`logs/trades.log`)
   - Every trade executed (entry, exit, PnL)
   - Timestamped and detailed
   - Rotates daily

2. **Error Logs** (`logs/errors.log`)
   - All errors with stack traces
   - System issues and exceptions
   - Rotates daily

3. **System Logs** (`logs/system.log`)
   - System events and status
   - Startup, shutdown, configuration
   - Rotates daily

4. **Performance Metrics** (`binance_results.json`)
   - Final backtest results
   - ROI, win rate, drawdown, etc.
   - Saved at end of backtest or shutdown

**What is NOT saved:**
- ❌ Historical candle data
- ❌ Real-time candle data
- ❌ Indicator values
- ❌ WebSocket messages

---

## Summary

**BACKTEST Mode:**
- Fetches historical data → Processes in memory → Simulates trades → Saves results
- **Uses ONLY historical data**

**PAPER Mode:**
- Fetches initial historical data → Starts WebSocket → Receives live data → Simulates trades
- **Uses historical data for warmup, then LIVE data for trading**

**LIVE Mode:**
- Fetches initial historical data → Starts WebSocket → Receives live data → Executes REAL trades
- **Uses historical data for warmup, then LIVE data for REAL trading**

All data is stored in memory for performance. Only logs and results are saved to disk.
