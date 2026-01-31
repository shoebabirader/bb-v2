# Implementation Plan: Binance Futures Trading Bot

## Overview

This implementation plan breaks down the trading bot into discrete, manageable tasks. Each task builds incrementally on previous work, with property-based tests integrated throughout to validate correctness. The implementation follows a bottom-up approach: data layer → indicators → strategy → risk management → execution → UI.

## Tasks

- [x] 1. Project Setup and Configuration Management
  - Create project directory structure (src/, tests/, config/, logs/)
  - Set up Python virtual environment and install dependencies (python-binance, pandas, numpy, pandas-ta, hypothesis, pytest, rich, pynput)
  - Create Config class to load and validate configuration from config.json and environment variables
  - Implement configuration validation with clear error messages for invalid parameters
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 15.1_

- [x] 1.1 Write property test for configuration validation
  - **Property 38: Configuration Validation**
  - **Validates: Requirements 14.2**

- [x] 1.2 Write property test for default configuration values
  - **Property 40: Default Configuration Values**
  - **Validates: Requirements 14.5**

- [x] 1.3 Write unit test for invalid configuration rejection
  - Test specific invalid config scenarios (negative risk, invalid mode, etc.)
  - **Property 39: Invalid Configuration Rejection**
  - **Validates: Requirements 14.3**

- [x] 2. Data Models and Core Types
  - Create Candle dataclass with timestamp, OHLCV fields
  - Create Position dataclass with entry, stops, PnL tracking
  - Create Trade dataclass with entry/exit details and exit reason
  - Create Signal dataclass with type, timestamp, price, indicators snapshot
  - Create IndicatorState dataclass to hold all indicator values
  - Create PerformanceMetrics dataclass for backtest results
  - _Requirements: 2.5, 13.1_

- [x] 2.1 Write property test for trade log completeness
  - **Property 7: Trade Log Completeness**
  - **Validates: Requirements 2.5**

- [x] 3. Historical Data Fetcher
  - Implement DataManager class with Binance client integration
  - Implement fetch_historical_data() to retrieve 90 days of 15m klines
  - Add data validation to detect and report gaps in historical data
  - Implement candle buffer management (circular buffer for memory efficiency)
  - _Requirements: 1.1, 1.2_

- [x] 3.1 Write property test for historical data completeness
  - **Property 1: Historical Data Completeness**
  - **Validates: Requirements 1.2**

- [x] 4. Technical Indicator Calculator
  - Implement IndicatorCalculator class with static methods
  - Implement calculate_vwap() anchored to weekly open timestamp
  - Implement calculate_atr() using 14-period EMA of true range
  - Implement calculate_adx() using standard 14-period ADX formula
  - Implement calculate_rvol() as current volume / 20-period average
  - Implement calculate_squeeze_momentum() using LazyBear methodology (Bollinger Bands + Keltner Channels)
  - Implement determine_trend() using price vs VWAP and momentum
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1_

- [x] 4.1 Write property test for VWAP calculation
  - **Property 8: VWAP Calculation Accuracy**
  - **Validates: Requirements 3.1**

- [x] 4.2 Write property test for ATR calculation
  - **Property 11: ATR Calculation Accuracy**
  - **Validates: Requirements 3.4**

- [x] 4.3 Write property test for ADX calculation
  - **Property 10: ADX Calculation Accuracy**
  - **Validates: Requirements 3.3**

- [x] 4.4 Write property test for RVOL calculation
  - **Property 12: RVOL Calculation Accuracy**
  - **Validates: Requirements 3.5**

- [x] 4.5 Write property test for Squeeze Momentum calculation
  - **Property 9: Squeeze Momentum Calculation**
  - **Validates: Requirements 3.2**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Strategy Engine and Signal Generation
  - Implement StrategyEngine class with indicator calculator
  - Implement update_indicators() to recalculate all indicators on new candles
  - Implement check_long_entry() validating all 5 conditions (price > VWAP, 1h bullish, squeeze green, ADX > 20, RVOL > 1.2)
  - Implement check_short_entry() validating all 5 conditions (price < VWAP, 1h bearish, squeeze maroon, ADX > 20, RVOL > 1.2)
  - Implement get_indicator_snapshot() for logging and display
  - Add logic to skip signal generation when insufficient data available
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 3.6_

- [x] 6.1 Write property test for long entry signal validity
  - **Property 16: Long Entry Signal Validity**
  - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

- [x] 6.2 Write property test for short entry signal validity
  - **Property 17: Short Entry Signal Validity**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [x] 6.3 Write property test for signal completeness
  - **Property 18: Signal Completeness**
  - **Validates: Requirements 5.6, 6.6**

- [x] 6.4 Write property test for bullish trend signal filtering
  - **Property 14: Bullish Trend Signal Filtering**
  - **Validates: Requirements 4.2**

- [x] 6.5 Write property test for bearish trend signal filtering
  - **Property 15: Bearish Trend Signal Filtering**
  - **Validates: Requirements 4.3**

- [x] 6.6 Write property test for trend direction consistency
  - **Property 13: Trend Direction Consistency**
  - **Validates: Requirements 4.1, 4.4**

- [x] 7. Position Sizing and Risk Calculations
  - Implement PositionSizer class
  - Implement calculate_position_size() using 1% risk rule with 2x ATR stop
  - Account for 3x leverage in position size calculation
  - Implement calculate_trailing_stop() at 1.5x ATR from current price
  - Add validation for Binance minimum order size requirements
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 7.1 Write property test for position size risk calculation
  - **Property 19: Position Size Risk Calculation**
  - **Validates: Requirements 7.1**

- [x] 7.2 Write property test for stop-loss distance calculation
  - **Property 20: Stop-Loss Distance Calculation**
  - **Validates: Requirements 7.2**

- [x] 7.3 Write property test for leverage factor in position sizing
  - **Property 21: Leverage Factor in Position Sizing**
  - **Validates: Requirements 7.3**

- [x] 7.4 Write property test for position size recalculation
  - **Property 22: Position Size Recalculation on Balance Change**
  - **Validates: Requirements 7.4**

- [x] 7.5 Write property test for minimum order size validation
  - **Property 23: Minimum Order Size Validation**
  - **Validates: Requirements 7.5**

- [x] 8. Risk Manager and Stop-Loss Logic
  - Implement RiskManager class with position tracking
  - Implement open_position() to create positions with calculated stops
  - Implement update_stops() to manage trailing stop-loss (only tighten, never widen)
  - Implement check_stop_hit() to detect stop-loss triggers
  - Implement close_position() to finalize trades with exit reason
  - Implement close_all_positions() for panic close functionality
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 10.1, 10.2, 10.3_

- [x] 8.1 Write property test for initial stop-loss placement
  - **Property 24: Initial Stop-Loss Placement**
  - **Validates: Requirements 8.1**

- [x] 8.2 Write property test for trailing stop behavior
  - **Property 25: Trailing Stop Activation and Updates**
  - **Validates: Requirements 8.2, 8.3, 8.5**

- [x] 8.3 Write property test for stop-loss trigger execution
  - **Property 26: Stop-Loss Trigger Execution**
  - **Validates: Requirements 8.4**

- [x] 8.4 Write property test for panic close completeness
  - **Property 29: Panic Close Completeness**
  - **Validates: Requirements 10.1, 10.2, 10.3**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Order Executor and Binance API Integration
  - Implement OrderExecutor class with Binance client
  - Implement set_leverage() to configure 3x leverage
  - Implement set_margin_type() to use ISOLATED margin
  - Implement place_market_order() with retry logic (3 attempts, exponential backoff)
  - Implement place_stop_loss_order() for stop management
  - Implement cancel_order() for order cancellation
  - Implement get_account_balance() to fetch USDT balance
  - Add margin availability validation before order placement
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 10.1 Write property test for position configuration consistency
  - **Property 27: Position Configuration Consistency**
  - **Validates: Requirements 9.1, 9.2, 9.3**

- [x] 10.2 Write property test for margin availability validation
  - **Property 28: Margin Availability Validation**
  - **Validates: Requirements 9.4, 9.5**

- [x] 10.3 Write property test for order retry logic
  - **Property 32: Order Retry Logic**
  - **Validates: Requirements 11.3**

- [x] 10.4 Write property test for order completeness
  - **Property 31: Order Completeness**
  - **Validates: Requirements 11.2**

- [x] 10.5 Write unit tests for order execution scenarios
  - Test successful order placement
  - Test order failure and retry
  - Test fill verification
  - _Requirements: 11.1, 11.4, 11.5_

- [x] 11. WebSocket Data Streaming
  - Implement start_websocket_streams() for 15m and 1h candles
  - Implement on_candle_update() callback to update candle buffers
  - Implement reconnect_websocket() with exponential backoff (max 5 attempts)
  - Add WebSocket connection health monitoring
  - _Requirements: 1.3, 1.4, 16.1_

- [x] 11.1 Write property test for WebSocket reconnection backoff
  - **Property 2: WebSocket Reconnection Backoff**
  - **Validates: Requirements 1.4**

- [x] 11.2 Write property test for WebSocket reconnection on disconnect
  - **Property 44: WebSocket Reconnection on Disconnect**
  - **Validates: Requirements 16.1**

- [x] 12. Backtest Engine
  - Implement BacktestEngine class with strategy and risk manager
  - Implement run_backtest() to iterate through historical candles
  - Implement simulate_trade_execution() with realistic fill logic (within candle high/low)
  - Implement apply_fees_and_slippage() (0.05% fee, 0.02% slippage)
  - Implement calculate_metrics() for ROI, drawdown, profit factor, win rate, Sharpe ratio
  - Track equity curve throughout backtest
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 12.1 Write property test for trade execution costs
  - **Property 4: Trade Execution Costs**
  - **Validates: Requirements 2.1, 2.2**

- [x] 12.2 Write property test for backtest metrics completeness
  - **Property 5: Backtest Metrics Completeness**
  - **Validates: Requirements 2.3**

- [x] 12.3 Write property test for realistic fill simulation
  - **Property 6: Realistic Fill Simulation**
  - **Validates: Requirements 2.4**

- [x] 12.4 Write unit tests for backtest scenarios
  - Test backtest with winning trades
  - Test backtest with losing trades
  - Test backtest with mixed results
  - Verify metrics calculations
  - _Requirements: 2.3_

- [ ] 13. Logging and Persistence
  - Implement trade logging to local file with all required fields
  - Implement error logging with stack traces
  - Implement performance metrics saving to binance_results.json
  - Implement API key redaction in all log outputs
  - Add log file rotation (daily)
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 15.2_

- [x] 13.1 Write property test for trade logging completeness
  - **Property 35: Trade Logging Completeness**
  - **Validates: Requirements 13.1**

- [x] 13.2 Write property test for error logging with stack traces
  - **Property 36: Error Logging with Stack Traces**
  - **Validates: Requirements 13.3**

- [x] 13.3 Write property test for backtest results persistence
  - **Property 37: Backtest Results Persistence**
  - **Validates: Requirements 13.4**

- [x] 13.4 Write property test for API key security
  - **Property 41: API Key Security**
  - **Validates: Requirements 15.2**

- [ ] 14. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Terminal UI Dashboard
  - Implement UIDisplay class using Rich library
  - Implement render_dashboard() showing PnL, win rate, trend status, RVOL, ADX
  - Implement display_backtest_results() for backtest metrics
  - Implement show_notification() for alerts and messages
  - Implement show_panic_confirmation() for panic close feedback
  - Add color coding for status changes (green for profit, red for loss, etc.)
  - Update dashboard at 1Hz refresh rate
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8_

- [ ] 16. Main Trading Bot Orchestration
  - Implement TradingBot main class
  - Implement mode selection logic (BACKTEST, PAPER, LIVE)
  - Implement main event loop for real-time trading
  - Integrate keyboard listener for panic close (Escape key)
  - Implement graceful shutdown with position cleanup
  - Wire all components together (data → strategy → risk → execution → UI)
  - _Requirements: 1.5, 10.4_

- [x] 16.1 Write property test for mode configuration validity
  - **Property 3: Mode Configuration Validity**
  - **Validates: Requirements 1.5**

- [x] 17. API Security and Authentication
  - Implement API key loading from environment variables
  - Implement API authentication validation at startup
  - Implement API permission validation before trading
  - Implement HTTPS protocol enforcement for all API calls
  - Add clear error messages for authentication failures
  - _Requirements: 15.1, 15.3, 15.4, 15.5_

- [x] 17.1 Write property test for API permission validation
  - **Property 42: API Permission Validation**
  - **Validates: Requirements 15.4**

- [x] 17.2 Write property test for HTTPS protocol enforcement
  - **Property 43: HTTPS Protocol Enforcement**
  - **Validates: Requirements 15.5**

- [x] 17.3 Write unit test for authentication failure handling
  - Test API authentication failure scenario
  - Verify system refuses to start
  - _Requirements: 15.3_

- [x] 18. System Health Monitoring
  - Implement health check system (60-second intervals)
  - Implement API rate limit monitoring and throttling
  - Implement critical error notification system
  - Add memory usage monitoring with warnings at 80%
  - _Requirements: 16.2, 16.3, 16.4, 16.5_

- [x] 18.1 Write property test for API rate limit respect
  - **Property 45: API Rate Limit Respect**
  - **Validates: Requirements 16.2**

- [x] 18.2 Write property test for critical error notification
  - **Property 46: Critical Error Notification**
  - **Validates: Requirements 16.4**

- [x] 18.3 Write property test for health check periodicity
  - **Property 47: Health Check Periodicity**
  - **Validates: Requirements 16.5**

- [x] 19. Integration and End-to-End Testing
  - Create example config.json with documentation
  - Test full backtest mode with 90 days of BTC data
  - Test paper trading mode with live WebSocket data
  - Verify panic close works correctly
  - Verify all logs are written correctly
  - Test error scenarios (network failure, insufficient margin, etc.)
  - _Requirements: All_

- [x] 20. Final Checkpoint and Documentation
  - Ensure all tests pass
  - Create README.md with setup instructions
  - Document configuration parameters
  - Document how to run in each mode (BACKTEST, PAPER, LIVE)
  - Document safety features and risk controls
  - Ask the user if questions arise before deployment

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation builds bottom-up: data → indicators → strategy → risk → execution → UI
- All property tests should run with minimum 100 iterations
- Each property test must include a comment tag: `# Feature: binance-futures-bot, Property {N}: {title}`
