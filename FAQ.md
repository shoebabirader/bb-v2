# Frequently Asked Questions (FAQ)

## Data and Storage

### Q: Where is historical data stored?
**A:** Historical data is stored **in memory only** using circular buffers (deque with maxlen=500). It is NOT saved to disk. This design choice provides:
- Fast access for real-time trading
- Automatic memory management
- No disk I/O overhead
- Efficient use of resources

See [DATA_FLOW_EXPLANATION.md](DATA_FLOW_EXPLANATION.md) for details.

### Q: What happens when the bot restarts?
**A:** When the bot restarts:
- **BACKTEST mode**: Fetches historical data fresh from Binance API
- **PAPER/LIVE mode**: Fetches 7 days of historical data for indicator warmup, then starts WebSocket for real-time data
- Previous candle data is lost (but can be re-fetched)
- Trade logs and performance metrics are preserved on disk

### Q: How much memory does the bot use?
**A:** Memory usage is minimal:
- 500 15-minute candles × ~100 bytes = ~50 KB
- 500 1-hour candles × ~100 bytes = ~50 KB
- Total candle data: ~100 KB
- Plus Python overhead and libraries: typically 50-100 MB total

### Q: Can I save historical data to disk?
**A:** Yes, you can modify the code to save data, but it's not recommended because:
- Binance API provides historical data on demand
- Disk storage adds complexity
- Real-time trading only needs recent data
- Memory-based approach is faster

---

## Trading Modes

### Q: Does PAPER mode use real-time data?
**A:** Yes! PAPER mode:
- ✅ Fetches 7 days of historical data initially (for indicator warmup)
- ✅ Connects to Binance WebSocket for real-time data
- ✅ Receives live candles as they close
- ✅ Generates signals based on current market conditions
- ❌ Does NOT place real orders (simulated execution only)

### Q: Does LIVE mode use historical data?
**A:** LIVE mode uses BOTH:
- **Historical data**: 7 days fetched at startup for indicator warmup
- **Real-time data**: WebSocket streams for continuous live updates
- The historical data is just for initialization; all trading decisions are based on live data

### Q: Why does PAPER/LIVE mode fetch 7 days of historical data?
**A:** The 7 days of historical data is needed because:
- Indicators need historical context (e.g., 14-period ATR needs 14 candles)
- VWAP is anchored to weekly open (needs data from start of week)
- Strategy needs to calculate trend direction before generating signals
- Without this warmup period, indicators would be inaccurate initially

### Q: How long does a backtest take?
**A:** Backtest speed depends on the amount of data:
- 7 days: ~30 seconds
- 30 days: ~2 minutes
- 90 days: ~5-10 minutes
- The bot processes historical data as fast as possible (no waiting for real-time)

---

## Configuration

### Q: Do I need API keys for BACKTEST mode?
**A:** Yes, API keys are needed for BACKTEST mode to fetch historical data from Binance. However:
- The keys only need READ permissions
- No trading permissions required
- No orders are placed
- Completely safe

### Q: What API permissions do I need?
**A:** Required permissions:
- **BACKTEST mode**: Read-only (to fetch historical data)
- **PAPER mode**: Read-only (to fetch data and account balance)
- **LIVE mode**: Futures trading enabled (to place real orders)

### Q: Can I test without API keys?
**A:** No, API keys are required for all modes because:
- Historical data must be fetched from Binance
- Even BACKTEST mode needs to download candle data
- You can create API keys with read-only permissions for safe testing

### Q: How do I get Binance API keys?
**A:** 
1. Log in to Binance
2. Go to API Management
3. Create new API key
4. For BACKTEST/PAPER: Enable "Enable Reading" only
5. For LIVE: Enable "Enable Futures" (⚠️ be careful!)
6. Save keys securely (never share them)

---

## Strategy and Signals

### Q: What strategy does the bot use?
**A:** The bot uses a multi-indicator strategy:
- **VWAP**: Anchored to weekly open for trend direction
- **Squeeze Momentum**: LazyBear's indicator for momentum
- **ADX**: Trend strength (must be > 20)
- **RVOL**: Relative volume (must be > 1.2)
- **Multi-timeframe**: 1h trend filter + 15m entry signals

### Q: Can I modify the strategy?
**A:** Yes! The strategy is in `src/strategy.py`. You can:
- Modify indicator parameters
- Add new indicators
- Change entry/exit conditions
- Adjust timeframes
- Remember to update tests after modifications

### Q: How often does the bot check for signals?
**A:** 
- **BACKTEST mode**: Checks every historical candle (processes all data)
- **PAPER/LIVE mode**: Checks when new candles close (every 15 minutes for 15m timeframe)

### Q: Can the bot trade multiple symbols?
**A:** Currently, the bot trades one symbol at a time (configured in config.json). To trade multiple symbols:
- Run multiple instances with different configs
- Or modify the code to support multiple symbols (requires significant changes)

---

## Risk Management

### Q: How does position sizing work?
**A:** Position sizing uses the 1% risk rule:
1. Risk amount = Wallet balance × 1%
2. Stop distance = 2 × ATR
3. Position size = Risk amount / Stop distance
4. Adjusted for 3x leverage

Example: $10,000 balance, ATR = $500
- Risk = $10,000 × 1% = $100
- Stop distance = 2 × $500 = $1,000
- Position size = $100 / $1,000 = 0.1 BTC
- With 3x leverage: Can control 0.1 BTC with ~$1,667 margin

### Q: Can I change the risk percentage?
**A:** Yes, edit `risk_per_trade` in config.json:
- Default: 0.01 (1%)
- Range: 0.001 to 0.05 (0.1% to 5%)
- ⚠️ Higher risk = higher potential profit AND loss

### Q: What is isolated margin?
**A:** Isolated margin means:
- Each position has its own margin allocation
- If one position is liquidated, others are unaffected
- Limits risk to the specific position
- Safer than cross-margin (which uses entire account balance)

### Q: How do stop-losses work?
**A:** The bot uses two types of stops:
1. **Initial stop-loss**: Set at 2× ATR from entry price
2. **Trailing stop**: Activates when in profit, set at 1.5× ATR from current price
3. Stops only tighten, never widen
4. Automatically managed by the bot

---

## Errors and Troubleshooting

### Q: What if WebSocket disconnects?
**A:** The bot automatically:
1. Detects disconnection
2. Attempts reconnection with exponential backoff
3. Tries up to 5 times (1s, 2s, 4s, 8s, 16s delays)
4. If all attempts fail, logs error and stops

### Q: What if I lose internet connection?
**A:** 
- **BACKTEST mode**: No impact (uses already-fetched data)
- **PAPER/LIVE mode**: WebSocket disconnects, bot attempts reconnection
- If reconnection fails, bot stops to prevent trading without data
- Existing positions remain open on Binance

### Q: What if Binance API is down?
**A:** 
- Bot will fail to fetch data or place orders
- Error is logged with details
- Bot stops to prevent issues
- You can manually close positions on Binance website

### Q: How do I stop the bot?
**A:** Three ways:
1. **Graceful shutdown**: Press Ctrl+C (closes positions, saves logs)
2. **Panic close**: Press ESC (immediately closes all positions)
3. **Force kill**: Close terminal (positions remain open on Binance!)

---

## Performance and Results

### Q: What metrics does the bot calculate?
**A:** Performance metrics include:
- Total trades, winning trades, losing trades
- Win rate (percentage)
- Total PnL and ROI
- Maximum drawdown
- Profit factor (gross profit / gross loss)
- Sharpe ratio
- Average win/loss
- Largest win/loss
- Average trade duration

### Q: Where are results saved?
**A:** Results are saved to:
- `binance_results.json` - Performance metrics
- `logs/trades.log` - Detailed trade logs
- `logs/errors.log` - Error logs
- `logs/system.log` - System events

### Q: Can I view results while bot is running?
**A:** Yes! In PAPER/LIVE mode:
- Terminal dashboard updates every second
- Shows current PnL, win rate, indicators
- Press ESC to stop and see final results

### Q: How accurate is backtesting?
**A:** Backtesting includes:
- ✅ Realistic fees (0.05%)
- ✅ Slippage (0.02%)
- ✅ Realistic fill logic (within candle high/low)
- ❌ Does NOT account for: liquidity issues, extreme volatility, exchange outages
- Results are indicative but not guaranteed for live trading

---

## Safety and Security

### Q: Is my API key secure?
**A:** The bot:
- ✅ Redacts API keys from all logs
- ✅ Never displays keys in terminal
- ✅ Stores keys only in config.json (keep this file secure!)
- ⚠️ Never share your config.json file
- ⚠️ Use environment variables for extra security

### Q: Can I lose more than my balance?
**A:** With isolated margin:
- ✅ Each position is isolated
- ✅ Maximum loss per position = margin allocated
- ✅ Other positions unaffected
- ⚠️ Still possible to lose entire position margin
- ⚠️ Use proper risk management (1% per trade)

### Q: What if the bot has a bug?
**A:** Safety features:
- ✅ Comprehensive test suite (16 integration tests, 47 property tests)
- ✅ Panic close button (ESC key)
- ✅ Stop-loss on every position
- ✅ Position size limits
- ⚠️ Always test in BACKTEST mode first
- ⚠️ Then test in PAPER mode before going live
- ⚠️ Start with small position sizes

### Q: Should I run this bot with real money?
**A:** Only if:
- ✅ You've tested thoroughly in BACKTEST mode
- ✅ You've tested in PAPER mode with live data
- ✅ You understand the strategy and risks
- ✅ You can afford to lose the money
- ✅ You're monitoring the bot actively
- ⚠️ Never risk more than you can afford to lose
- ⚠️ Cryptocurrency trading is highly risky

---

## Technical Questions

### Q: What Python version is required?
**A:** Python 3.9 or higher is required. Tested with Python 3.14.

### Q: What dependencies are needed?
**A:** See `requirements.txt`:
- python-binance (Binance API)
- pandas, numpy (data processing)
- hypothesis (property-based testing)
- pytest (testing)
- rich (terminal UI)
- pynput (keyboard input)
- psutil (system monitoring)

### Q: Can I run this on a server?
**A:** Yes, but:
- Terminal UI requires a terminal (use tmux/screen)
- Keyboard listener (ESC key) requires terminal access
- Consider running in a VPS with SSH access
- Set up proper logging and monitoring

### Q: Can I run multiple instances?
**A:** Yes, you can run multiple instances:
- Use different config files
- Trade different symbols
- Use different strategies
- Each instance is independent

### Q: How do I update the bot?
**A:** To update:
1. Stop the bot gracefully (Ctrl+C)
2. Pull latest code changes
3. Run tests: `pytest`
4. Update config if needed
5. Restart the bot

---

## Getting Help

### Q: Where can I get help?
**A:** 
- Read the documentation: README.md, DATA_FLOW_EXPLANATION.md
- Check the logs: `logs/errors.log`, `logs/system.log`
- Review the code: All source code is documented
- Run tests: `pytest -v` to verify everything works

### Q: How do I report a bug?
**A:** When reporting bugs, include:
- Error message from logs
- Configuration used (redact API keys!)
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS

### Q: Can I contribute?
**A:** Yes! Areas for contribution:
- Additional strategies
- More indicators
- Better UI
- Performance optimizations
- Documentation improvements
- Bug fixes

---

## Common Issues

### Q: "ModuleNotFoundError: No module named 'binance'"
**A:** Install dependencies: `pip install -r requirements.txt`

### Q: "Binance client not initialized"
**A:** Add API keys to config.json or set environment variables

### Q: "Historical data contains gaps"
**A:** Binance API returned incomplete data. Try:
- Reducing backtest days
- Checking internet connection
- Trying again later

### Q: "Insufficient margin for trade"
**A:** 
- Increase wallet balance
- Reduce leverage
- Reduce risk_per_trade percentage
- Check Binance account balance

### Q: Bot is slow in BACKTEST mode
**A:** 
- Reduce backtest_days in config
- Use faster hardware
- Close other applications
- This is normal for large datasets (90 days = ~8,640 candles)

### Q: WebSocket keeps disconnecting
**A:** 
- Check internet connection
- Check Binance API status
- Verify API keys are valid
- Check firewall settings
