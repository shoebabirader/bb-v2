# Data Flow Visual Diagrams

## BACKTEST Mode Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        BACKTEST MODE                             │
│                    (Historical Data Only)                        │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   Binance    │
    │     API      │
    └──────┬───────┘
           │
           │ Fetch 90 days of historical data
           │ (One-time at startup)
           ↓
    ┌──────────────┐
    │ Data Manager │
    │              │
    │ In-Memory    │
    │ Buffers:     │
    │ • 15m: 500   │
    │ • 1h:  500   │
    └──────┬───────┘
           │
           │ Historical candles
           ↓
    ┌──────────────┐
    │  Backtest    │
    │   Engine     │
    │              │
    │ Iterates     │
    │ through all  │
    │ candles      │
    └──────┬───────┘
           │
           │ For each candle
           ↓
    ┌──────────────┐
    │  Strategy    │
    │   Engine     │
    │              │
    │ Calculate    │
    │ indicators   │
    │ Generate     │
    │ signals      │
    └──────┬───────┘
           │
           │ Signals
           ↓
    ┌──────────────┐
    │    Risk      │
    │  Manager     │
    │              │
    │ Size         │
    │ positions    │
    │ Manage stops │
    └──────┬───────┘
           │
           │ Simulated trades
           ↓
    ┌──────────────┐
    │   Results    │
    │              │
    │ • Metrics    │
    │ • Trade log  │
    │ • JSON file  │
    └──────────────┘

    ✅ No WebSocket
    ✅ No real orders
    ✅ Safe testing
```

---

## PAPER Trading Mode Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        PAPER MODE                                │
│              (Historical + Real-time Data)                       │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: INITIALIZATION
    ┌──────────────┐
    │   Binance    │
    │     API      │
    └──────┬───────┘
           │
           │ Fetch 7 days historical
           │ (For indicator warmup)
           ↓
    ┌──────────────┐
    │ Data Manager │
    │              │
    │ In-Memory    │
    │ Buffers:     │
    │ • 15m: 500   │
    │ • 1h:  500   │
    └──────────────┘

PHASE 2: REAL-TIME TRADING
    ┌──────────────┐
    │   Binance    │
    │  WebSocket   │
    └──────┬───────┘
           │
           │ Live candles every 15m/1h
           │ (Continuous stream)
           ↓
    ┌──────────────┐
    │ Data Manager │
    │              │
    │ Append to    │
    │ buffers      │
    └──────┬───────┘
           │
           │ Latest candles
           ↓
    ┌──────────────┐
    │  Strategy    │
    │   Engine     │
    │              │
    │ Calculate    │
    │ indicators   │
    │ on LIVE data │
    └──────┬───────┘
           │
           │ Signals
           ↓
    ┌──────────────┐
    │    Risk      │
    │  Manager     │
    │              │
    │ Size         │
    │ positions    │
    └──────┬───────┘
           │
           │ Simulated execution
           ↓
    ┌──────────────┐
    │   No Real    │
    │   Orders     │
    │              │
    │ Track PnL    │
    │ as if live   │
    └──────────────┘

    ✅ WebSocket active
    ✅ Live data
    ✅ No real orders
    ✅ Safe testing with current market
```

---

## LIVE Trading Mode Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         LIVE MODE                                │
│              (Historical + Real-time Data)                       │
│                    ⚠️  REAL MONEY AT RISK ⚠️                     │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: INITIALIZATION
    ┌──────────────┐
    │   Binance    │
    │     API      │
    └──────┬───────┘
           │
           │ 1. Configure leverage (3x)
           │ 2. Set margin (ISOLATED)
           │ 3. Fetch 7 days historical
           ↓
    ┌──────────────┐
    │ Data Manager │
    │              │
    │ In-Memory    │
    │ Buffers      │
    └──────────────┘

PHASE 2: REAL-TIME TRADING
    ┌──────────────┐
    │   Binance    │
    │  WebSocket   │
    └──────┬───────┘
           │
           │ Live candles every 15m/1h
           ↓
    ┌──────────────┐
    │ Data Manager │
    │              │
    │ Append to    │
    │ buffers      │
    └──────┬───────┘
           │
           │ Latest candles
           ↓
    ┌──────────────┐
    │  Strategy    │
    │   Engine     │
    │              │
    │ Calculate    │
    │ indicators   │
    └──────┬───────┘
           │
           │ Signals
           ↓
    ┌──────────────┐
    │    Risk      │
    │  Manager     │
    │              │
    │ Size         │
    │ positions    │
    └──────┬───────┘
           │
           │ Position details
           ↓
    ┌──────────────┐
    │    Order     │
    │  Executor    │
    │              │
    │ Place REAL   │
    │ market order │
    └──────┬───────┘
           │
           │ REAL ORDER
           ↓
    ┌──────────────┐
    │   Binance    │
    │   Futures    │
    │              │
    │ Execute on   │
    │ exchange     │
    └──────────────┘

    ✅ WebSocket active
    ✅ Live data
    ⚠️ REAL ORDERS
    ⚠️ REAL MONEY
    ⚠️ REAL RISK
```

---

## Memory Buffer Management

```
┌─────────────────────────────────────────────────────────────────┐
│                    CIRCULAR BUFFER (deque)                       │
│                      maxlen = 500                                │
└─────────────────────────────────────────────────────────────────┘

When buffer is NOT full:
┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
│ 1 │ 2 │ 3 │ 4 │ 5 │   │   │   │   │   │  ← New candles added
└───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
                        ↑
                    Next position

When buffer is FULL (500 candles):
┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
│497│498│499│500│ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │  ← Oldest removed
└───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
                    ↑
                New candle replaces oldest

Benefits:
✅ Automatic memory management
✅ Always keeps most recent 500 candles
✅ No manual cleanup needed
✅ Fast O(1) append and access
✅ Perfect for real-time trading
```

---

## Data Persistence

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHAT GETS SAVED TO DISK                       │
└─────────────────────────────────────────────────────────────────┘

Memory (NOT saved):
┌──────────────────┐
│  Candle Buffers  │  ← In-memory only
│  • 15m candles   │
│  • 1h candles    │
│  • Indicators    │
└──────────────────┘

Disk (Saved):
┌──────────────────┐
│  logs/           │
│  ├─ trades.log   │  ← All executed trades
│  ├─ errors.log   │  ← Errors with stack traces
│  └─ system.log   │  ← System events
└──────────────────┘

┌──────────────────┐
│ binance_results  │  ← Performance metrics
│     .json        │     (ROI, win rate, etc.)
└──────────────────┘

Why not save candles?
✅ Reduces disk I/O
✅ Faster performance
✅ Can always re-fetch from Binance
✅ Only need recent data for trading
```

---

## WebSocket Reconnection Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  WEBSOCKET RECONNECTION                          │
│                  (Exponential Backoff)                           │
└─────────────────────────────────────────────────────────────────┘

Normal Operation:
    ┌──────────────┐
    │  WebSocket   │
    │  Connected   │
    └──────┬───────┘
           │
           │ Receiving live data
           ↓
    ┌──────────────┐
    │   Trading    │
    │    Active    │
    └──────────────┘

Disconnection Detected:
    ┌──────────────┐
    │ Disconnect!  │
    └──────┬───────┘
           │
           ↓
    Attempt 1: Wait 1 second
           ↓
    Attempt 2: Wait 2 seconds
           ↓
    Attempt 3: Wait 4 seconds
           ↓
    Attempt 4: Wait 8 seconds
           ↓
    Attempt 5: Wait 16 seconds
           ↓
    Max attempts reached → Give up

    ✅ Automatic reconnection
    ✅ Exponential backoff
    ✅ Max 5 attempts
    ✅ Thread-safe
```

---

## Summary Comparison

```
┌──────────────┬─────────────┬─────────────┬─────────────┐
│   Feature    │  BACKTEST   │    PAPER    │    LIVE     │
├──────────────┼─────────────┼─────────────┼─────────────┤
│ Data Source  │ Historical  │ Hist + Live │ Hist + Live │
│              │    only     │             │             │
├──────────────┼─────────────┼─────────────┼─────────────┤
│ WebSocket    │     ❌      │     ✅      │     ✅      │
├──────────────┼─────────────┼─────────────┼─────────────┤
│ Real Orders  │     ❌      │     ❌      │     ⚠️      │
├──────────────┼─────────────┼─────────────┼─────────────┤
│ Money Risk   │     ❌      │     ❌      │     ⚠️      │
├──────────────┼─────────────┼─────────────┼─────────────┤
│ Speed        │    Fast     │  Real-time  │  Real-time  │
├──────────────┼─────────────┼─────────────┼─────────────┤
│ Use Case     │ Test past   │ Test live   │ Trade real  │
│              │    data     │    safely   │    money    │
└──────────────┴─────────────┴─────────────┴─────────────┘
```
