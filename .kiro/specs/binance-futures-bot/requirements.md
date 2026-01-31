# Requirements Document

## Introduction

This document specifies the requirements for a production-grade, bi-directional (Long/Short) trading bot for Binance Futures. The system is designed to run on a local machine with a high-fidelity backtesting module, real-time execution capabilities, and comprehensive risk management features.

## Glossary

- **Trading_Bot**: The complete automated trading system
- **Backtest_Engine**: Component that simulates historical trading performance
- **Position_Manager**: Component responsible for position sizing and risk calculations
- **Signal_Generator**: Component that generates buy/sell signals based on technical indicators
- **Order_Executor**: Component that places and manages orders on Binance Futures
- **Risk_Manager**: Component that enforces risk limits and stop-loss rules
- **Dashboard**: Terminal-based user interface displaying system status
- **VWAP**: Volume Weighted Average Price anchored to weekly open
- **Squeeze_Momentum**: LazyBear's Squeeze Momentum Indicator
- **ADX**: Average Directional Index (trend strength indicator)
- **RVOL**: Relative Volume (current volume vs average volume)
- **ATR**: Average True Range (volatility measure)

## Requirements

### Requirement 1: Data Architecture and Historical Data Management

**User Story:** As a trader, I want to access both historical and real-time market data, so that I can backtest strategies and execute live trades.

#### Acceptance Criteria

1. WHEN the system initializes in BACKTEST mode, THE Backtest_Engine SHALL fetch 90 days of 15-minute historical kline data using the Binance API
2. WHEN fetching historical data, THE Backtest_Engine SHALL validate that the data is complete and contains no gaps
3. WHEN the system operates in PAPER or LIVE mode, THE Trading_Bot SHALL establish WebSocket connections for real-time 15-minute and 1-hour candle data
4. WHEN a WebSocket connection fails, THE Trading_Bot SHALL attempt reconnection with exponential backoff up to 5 attempts
5. THE Trading_Bot SHALL support three operational modes: BACKTEST, PAPER, and LIVE, selectable via configuration

### Requirement 2: Backtesting Engine with Realistic Simulation

**User Story:** As a trader, I want to backtest my strategy with realistic market conditions, so that I can evaluate performance before risking real capital.

#### Acceptance Criteria

1. WHEN executing a simulated trade, THE Backtest_Engine SHALL apply a 0.05% trading fee to each transaction
2. WHEN executing a simulated trade, THE Backtest_Engine SHALL apply 0.02% slippage to simulate market impact
3. WHEN a backtest completes, THE Backtest_Engine SHALL calculate and report ROI, Maximum Drawdown, Profit Factor, Win Rate, and Total Trades
4. WHEN simulating order fills, THE Backtest_Engine SHALL use realistic fill logic based on candle high/low prices
5. THE Backtest_Engine SHALL maintain a trade history log with entry price, exit price, PnL, and timestamp for each trade

### Requirement 3: Technical Indicator Calculation

**User Story:** As a trader, I want accurate technical indicators calculated in real-time, so that the system can generate reliable trading signals.

#### Acceptance Criteria

1. THE Signal_Generator SHALL calculate Anchored VWAP from the most recent weekly open timestamp
2. THE Signal_Generator SHALL calculate Squeeze Momentum Indicator using LazyBear's methodology with Bollinger Bands and Keltner Channels
3. THE Signal_Generator SHALL calculate ADX with a 14-period lookback
4. THE Signal_Generator SHALL calculate ATR with a 14-period lookback
5. THE Signal_Generator SHALL calculate RVOL as the ratio of current volume to the 20-period average volume
6. WHEN indicator data is insufficient, THE Signal_Generator SHALL wait until enough historical data is available before generating signals

### Requirement 4: Multi-Timeframe Trend Analysis

**User Story:** As a trader, I want the system to analyze trends across multiple timeframes, so that I only take trades aligned with the broader market direction.

#### Acceptance Criteria

1. THE Signal_Generator SHALL determine 1-hour trend direction using price position relative to VWAP and momentum indicators
2. WHEN the 1-hour trend is bullish, THE Signal_Generator SHALL only generate long entry signals on the 15-minute timeframe
3. WHEN the 1-hour trend is bearish, THE Signal_Generator SHALL only generate short entry signals on the 15-minute timeframe
4. THE Signal_Generator SHALL update trend direction on each new 1-hour candle close
5. WHEN trend direction changes, THE Signal_Generator SHALL log the trend change event

### Requirement 5: Long Entry Signal Generation

**User Story:** As a trader, I want the system to identify high-probability long entry opportunities, so that I can profit from upward price movements.

#### Acceptance Criteria

1. WHEN generating a long signal, THE Signal_Generator SHALL verify that 15-minute price is above VWAP
2. WHEN generating a long signal, THE Signal_Generator SHALL verify that the 1-hour trend is bullish
3. WHEN generating a long signal, THE Signal_Generator SHALL verify that Squeeze Momentum releases green (positive momentum)
4. WHEN generating a long signal, THE Signal_Generator SHALL verify that ADX is greater than 20
5. WHEN generating a long signal, THE Signal_Generator SHALL verify that RVOL is greater than 1.2
6. WHEN all long entry conditions are met, THE Signal_Generator SHALL emit a LONG_ENTRY signal with entry price and timestamp

### Requirement 6: Short Entry Signal Generation

**User Story:** As a trader, I want the system to identify high-probability short entry opportunities, so that I can profit from downward price movements.

#### Acceptance Criteria

1. WHEN generating a short signal, THE Signal_Generator SHALL verify that 15-minute price is below VWAP
2. WHEN generating a short signal, THE Signal_Generator SHALL verify that the 1-hour trend is bearish
3. WHEN generating a short signal, THE Signal_Generator SHALL verify that Squeeze Momentum releases maroon (negative momentum)
4. WHEN generating a short signal, THE Signal_Generator SHALL verify that ADX is greater than 20
5. WHEN generating a short signal, THE Signal_Generator SHALL verify that RVOL is greater than 1.2
6. WHEN all short entry conditions are met, THE Signal_Generator SHALL emit a SHORT_ENTRY signal with entry price and timestamp

### Requirement 7: Dynamic Position Sizing and Risk Management

**User Story:** As a trader, I want the system to automatically calculate position sizes based on my risk tolerance, so that I never risk more than I'm comfortable losing.

#### Acceptance Criteria

1. WHEN calculating position size, THE Position_Manager SHALL risk exactly 1% of the current wallet balance per trade
2. WHEN calculating position size, THE Position_Manager SHALL use 2x ATR as the stop-loss distance
3. WHEN calculating position size, THE Position_Manager SHALL account for 3x isolated leverage
4. WHEN wallet balance changes, THE Position_Manager SHALL recalculate position sizes for new trades
5. THE Position_Manager SHALL validate that the calculated position size meets Binance minimum order requirements

### Requirement 8: Stop-Loss and Take-Profit Management

**User Story:** As a trader, I want automated stop-loss and take-profit management, so that I can protect profits and limit losses without manual intervention.

#### Acceptance Criteria

1. WHEN a position is opened, THE Risk_Manager SHALL place a stop-loss order at 2x ATR from the entry price
2. WHEN a position moves into profit, THE Risk_Manager SHALL activate a trailing stop-loss at 1.5x ATR from the current price
3. WHEN price moves favorably, THE Risk_Manager SHALL update the trailing stop-loss to lock in profits
4. WHEN a stop-loss is triggered, THE Order_Executor SHALL close the position immediately at market price
5. THE Risk_Manager SHALL never widen a stop-loss once it has been set

### Requirement 9: Leverage and Margin Management

**User Story:** As a trader, I want the system to use isolated leverage safely, so that a single bad trade cannot liquidate my entire account.

#### Acceptance Criteria

1. THE Order_Executor SHALL set leverage to 3x for all positions
2. THE Order_Executor SHALL use isolated margin mode for all positions
3. THE Order_Executor SHALL never use cross-margin mode
4. WHEN placing an order, THE Order_Executor SHALL verify that sufficient margin is available
5. IF insufficient margin is available, THE Order_Executor SHALL reject the trade and log a warning

### Requirement 10: Emergency Position Management

**User Story:** As a trader, I want an emergency panic button, so that I can immediately exit all positions if something goes wrong.

#### Acceptance Criteria

1. WHEN the user presses the Escape key, THE Trading_Bot SHALL immediately flatten all open positions at market price
2. WHEN the panic close is triggered, THE Trading_Bot SHALL cancel all pending orders
3. WHEN the panic close is triggered, THE Trading_Bot SHALL stop generating new signals
4. WHEN the panic close completes, THE Trading_Bot SHALL display a confirmation message and halt execution
5. THE Trading_Bot SHALL respond to the panic close command within 500 milliseconds

### Requirement 11: Order Execution and Management

**User Story:** As a trader, I want reliable order execution with proper error handling, so that my trades are executed as intended.

#### Acceptance Criteria

1. WHEN a signal is generated, THE Order_Executor SHALL place a market order on Binance Futures
2. WHEN placing an order, THE Order_Executor SHALL include stop-loss and take-profit parameters
3. IF an order fails, THE Order_Executor SHALL retry up to 3 times with exponential backoff
4. IF an order fails after retries, THE Order_Executor SHALL log the error and alert the user
5. WHEN an order is filled, THE Order_Executor SHALL verify the fill price and update position tracking

### Requirement 12: Terminal Dashboard and Real-Time Monitoring

**User Story:** As a trader, I want a clean terminal interface showing key metrics, so that I can monitor system performance at a glance.

#### Acceptance Criteria

1. THE Dashboard SHALL display current unrealized PnL for open positions
2. THE Dashboard SHALL display cumulative realized PnL since system start
3. THE Dashboard SHALL display current win rate as a percentage
4. THE Dashboard SHALL display current 1-hour and 15-minute trend status
5. THE Dashboard SHALL display current RVOL level
6. THE Dashboard SHALL display current ADX value
7. THE Dashboard SHALL refresh at least once per second
8. THE Dashboard SHALL use color coding to highlight important status changes

### Requirement 13: Logging and Performance Tracking

**User Story:** As a trader, I want comprehensive logging of all trades and system events, so that I can analyze performance and debug issues.

#### Acceptance Criteria

1. WHEN a trade is executed, THE Trading_Bot SHALL log entry price, exit price, PnL, and timestamp to a local file
2. WHEN the system shuts down, THE Trading_Bot SHALL save all performance metrics to binance_results.json
3. THE Trading_Bot SHALL log all errors with stack traces to a separate error log file
4. WHEN in BACKTEST mode, THE Trading_Bot SHALL save backtest results including ROI, Max Drawdown, Profit Factor, Win Rate, and Total Trades
5. THE Trading_Bot SHALL rotate log files daily to prevent excessive file sizes

### Requirement 14: Configuration Management

**User Story:** As a trader, I want to configure system parameters without modifying code, so that I can easily adjust settings and test different configurations.

#### Acceptance Criteria

1. THE Trading_Bot SHALL load configuration from a config.json file at startup
2. THE Trading_Bot SHALL validate all configuration parameters before starting
3. IF configuration is invalid, THE Trading_Bot SHALL display clear error messages and refuse to start
4. THE Trading_Bot SHALL support configuration of API keys, trading pair, timeframes, risk percentage, and leverage
5. WHERE configuration parameters are missing, THE Trading_Bot SHALL use documented default values

### Requirement 15: API Authentication and Security

**User Story:** As a trader, I want secure API key management, so that my credentials are protected.

#### Acceptance Criteria

1. THE Trading_Bot SHALL load API keys from environment variables or a secure configuration file
2. THE Trading_Bot SHALL never log or display API keys in plain text
3. WHEN API authentication fails, THE Trading_Bot SHALL display an error and refuse to start
4. THE Trading_Bot SHALL validate API key permissions before executing trades
5. THE Trading_Bot SHALL use HTTPS for all API communications

### Requirement 16: System Health Monitoring

**User Story:** As a trader, I want the system to monitor its own health, so that I'm alerted to potential issues before they cause problems.

#### Acceptance Criteria

1. THE Trading_Bot SHALL monitor WebSocket connection status and reconnect if disconnected
2. THE Trading_Bot SHALL monitor API rate limits and throttle requests if approaching limits
3. THE Trading_Bot SHALL monitor system memory usage and log warnings if usage exceeds 80%
4. WHEN critical errors occur, THE Trading_Bot SHALL send notifications to the user
5. THE Trading_Bot SHALL perform a health check every 60 seconds and log the results
