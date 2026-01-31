# Design Document

## Overview

The Binance Futures Trading Bot is a production-grade, bi-directional automated trading system designed for local execution. The system implements a sophisticated multi-indicator strategy with comprehensive risk management, supporting three operational modes: backtesting, paper trading, and live trading.

The architecture follows a modular design with clear separation of concerns:
- **Data Layer**: Manages historical and real-time market data
- **Strategy Layer**: Implements technical indicators and signal generation
- **Execution Layer**: Handles order placement and position management
- **Risk Layer**: Enforces risk limits and stop-loss rules
- **UI Layer**: Provides real-time monitoring and control

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      Trading Bot Main                        │
│                    (Orchestration Layer)                     │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴───────┬───────────┬──────────┬──────────┐
       │               │           │          │          │
   ┌───▼────┐   ┌─────▼─────┐ ┌──▼────┐ ┌──▼─────┐ ┌──▼────┐
   │  Data  │   │ Strategy  │ │  Risk │ │ Order  │ │   UI  │
   │ Manager│   │  Engine   │ │Manager│ │Executor│ │Display│
   └───┬────┘   └─────┬─────┘ └──┬────┘ └──┬─────┘ └───────┘
       │              │           │          │
   ┌───▼────────┐ ┌──▼──────┐ ┌──▼────┐ ┌──▼─────────┐
   │ Historical │ │Technical│ │Position│ │  Binance   │
   │   Data     │ │Indicator│ │ Sizer  │ │   API      │
   │  Fetcher   │ │Calculator│ │        │ │  Client    │
   └────────────┘ └─────────┘ └────────┘ └────────────┘
```

### Component Responsibilities

**TradingBot (Main Orchestrator)**
- Initializes all subsystems based on RUN_MODE
- Coordinates data flow between components
- Handles keyboard input for panic close
- Manages system lifecycle and graceful shutdown

**DataManager**
- Fetches historical kline data for backtesting
- Manages WebSocket connections for real-time data
- Maintains synchronized 15m and 1h candle buffers
- Handles reconnection logic with exponential backoff

**StrategyEngine**
- Calculates all technical indicators (VWAP, Squeeze, ADX, ATR, RVOL)
- Determines multi-timeframe trend direction
- Generates LONG_ENTRY and SHORT_ENTRY signals
- Validates signal conditions before emission

**RiskManager**
- Calculates position sizes based on 1% risk rule
- Sets initial stop-loss at 2x ATR
- Manages trailing stop-loss at 1.5x ATR
- Monitors and updates stop levels on each candle

**OrderExecutor**
- Places market orders on Binance Futures
- Sets leverage to 3x isolated margin
- Implements retry logic for failed orders
- Verifies order fills and updates positions

**UIDisplay**
- Renders terminal dashboard with rich formatting
- Updates PnL, win rate, and indicator values
- Displays trend status and system health
- Provides visual feedback for user actions

## Components and Interfaces

### 1. Configuration Module

```python
class Config:
    # API Configuration
    api_key: str
    api_secret: str
    
    # Trading Parameters
    symbol: str = "BTCUSDT"
    timeframe_entry: str = "15m"
    timeframe_filter: str = "1h"
    
    # Risk Parameters
    risk_per_trade: float = 0.01  # 1%
    leverage: int = 3
    stop_loss_atr_multiplier: float = 2.0
    trailing_stop_atr_multiplier: float = 1.5
    
    # Indicator Parameters
    atr_period: int = 14
    adx_period: int = 14
    adx_threshold: float = 20.0
    rvol_period: int = 20
    rvol_threshold: float = 1.2
    
    # Backtest Parameters
    backtest_days: int = 90
    trading_fee: float = 0.0005  # 0.05%
    slippage: float = 0.0002     # 0.02%
    
    # System Parameters
    run_mode: str = "BACKTEST"  # BACKTEST, PAPER, LIVE
    log_file: str = "binance_results.json"
```

### 2. Data Models

```python
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    
class Position:
    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    leverage: int
    stop_loss: float
    trailing_stop: float
    entry_time: int
    unrealized_pnl: float
    
class Trade:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    entry_time: int
    exit_time: int
    exit_reason: str  # "STOP_LOSS", "TRAILING_STOP", "SIGNAL_EXIT", "PANIC"
    
class Signal:
    type: str  # "LONG_ENTRY", "SHORT_ENTRY", "EXIT"
    timestamp: int
    price: float
    indicators: dict  # Snapshot of indicator values
```

### 3. DataManager Interface

```python
class DataManager:
    def __init__(self, config: Config, client: BinanceClient):
        self.config = config
        self.client = client
        self.candles_15m: List[Candle] = []
        self.candles_1h: List[Candle] = []
        self.websocket_manager = None
        
    def fetch_historical_data(self, days: int) -> List[Candle]:
        """Fetch historical klines for backtesting"""
        
    def start_websocket_streams(self):
        """Initialize WebSocket connections for real-time data"""
        
    def on_candle_update(self, candle: Candle, timeframe: str):
        """Callback for new candle data"""
        
    def get_latest_candles(self, timeframe: str, count: int) -> List[Candle]:
        """Retrieve most recent candles for indicator calculation"""
        
    def reconnect_websocket(self):
        """Handle WebSocket reconnection with exponential backoff"""
```

### 4. IndicatorCalculator Interface

```python
class IndicatorCalculator:
    @staticmethod
    def calculate_vwap(candles: List[Candle], anchor_time: int) -> float:
        """Calculate VWAP anchored to weekly open"""
        
    @staticmethod
    def calculate_squeeze_momentum(candles: List[Candle]) -> dict:
        """Calculate Squeeze Momentum Indicator (LazyBear)
        Returns: {
            'value': float,
            'is_squeezed': bool,
            'color': str  # 'green', 'maroon', 'blue', 'gray'
        }"""
        
    @staticmethod
    def calculate_adx(candles: List[Candle], period: int = 14) -> float:
        """Calculate Average Directional Index"""
        
    @staticmethod
    def calculate_atr(candles: List[Candle], period: int = 14) -> float:
        """Calculate Average True Range"""
        
    @staticmethod
    def calculate_rvol(candles: List[Candle], period: int = 20) -> float:
        """Calculate Relative Volume"""
        
    @staticmethod
    def determine_trend(candles: List[Candle], vwap: float) -> str:
        """Determine trend direction: 'BULLISH', 'BEARISH', 'NEUTRAL'"""
```


### 5. StrategyEngine Interface

```python
class StrategyEngine:
    def __init__(self, config: Config, indicator_calc: IndicatorCalculator):
        self.config = config
        self.indicator_calc = indicator_calc
        self.current_indicators = {}
        
    def update_indicators(self, candles_15m: List[Candle], candles_1h: List[Candle]):
        """Recalculate all indicators with latest data"""
        
    def check_long_entry(self) -> Optional[Signal]:
        """Check if long entry conditions are met
        Conditions:
        - 15m price > VWAP
        - 1h trend is BULLISH
        - Squeeze releases green
        - ADX > 20
        - RVOL > 1.2
        """
        
    def check_short_entry(self) -> Optional[Signal]:
        """Check if short entry conditions are met
        Conditions:
        - 15m price < VWAP
        - 1h trend is BEARISH
        - Squeeze releases maroon
        - ADX > 20
        - RVOL > 1.2
        """
        
    def get_indicator_snapshot(self) -> dict:
        """Return current indicator values for logging/display"""
```

### 6. PositionSizer Interface

```python
class PositionSizer:
    def __init__(self, config: Config):
        self.config = config
        
    def calculate_position_size(
        self, 
        wallet_balance: float, 
        entry_price: float, 
        atr: float
    ) -> dict:
        """Calculate position size based on 1% risk rule
        Returns: {
            'quantity': float,
            'stop_loss_distance': float,
            'stop_loss_price': float,
            'margin_required': float
        }"""
        
    def calculate_trailing_stop(
        self, 
        position: Position, 
        current_price: float, 
        atr: float
    ) -> float:
        """Calculate trailing stop price at 1.5x ATR"""
```

### 7. RiskManager Interface

```python
class RiskManager:
    def __init__(self, config: Config, position_sizer: PositionSizer):
        self.config = config
        self.position_sizer = position_sizer
        self.active_positions: Dict[str, Position] = {}
        
    def open_position(
        self, 
        signal: Signal, 
        wallet_balance: float, 
        atr: float
    ) -> Position:
        """Create new position with calculated size and stops"""
        
    def update_stops(self, position: Position, current_price: float, atr: float):
        """Update trailing stop if price moves favorably"""
        
    def check_stop_hit(self, position: Position, current_price: float) -> bool:
        """Check if stop-loss or trailing stop is hit"""
        
    def close_position(self, position: Position, exit_price: float, reason: str) -> Trade:
        """Close position and return trade record"""
        
    def close_all_positions(self, current_price: float) -> List[Trade]:
        """Emergency close all positions (panic button)"""
```

### 8. OrderExecutor Interface

```python
class OrderExecutor:
    def __init__(self, config: Config, client: BinanceClient):
        self.config = config
        self.client = client
        
    def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for the trading pair"""
        
    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED"):
        """Set margin type to isolated"""
        
    def place_market_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float
    ) -> dict:
        """Place market order with retry logic"""
        
    def place_stop_loss_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float, 
        stop_price: float
    ) -> dict:
        """Place stop-loss order"""
        
    def cancel_order(self, symbol: str, order_id: int):
        """Cancel pending order"""
        
    def get_account_balance(self) -> float:
        """Get current USDT balance"""
```

### 9. BacktestEngine Interface

```python
class BacktestEngine:
    def __init__(self, config: Config, strategy: StrategyEngine, risk_mgr: RiskManager):
        self.config = config
        self.strategy = strategy
        self.risk_mgr = risk_mgr
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        
    def run_backtest(self, historical_data: List[Candle]) -> dict:
        """Execute backtest on historical data
        Returns: {
            'total_trades': int,
            'winning_trades': int,
            'losing_trades': int,
            'win_rate': float,
            'total_pnl': float,
            'roi': float,
            'max_drawdown': float,
            'profit_factor': float,
            'sharpe_ratio': float
        }"""
        
    def simulate_trade_execution(
        self, 
        signal: Signal, 
        candle: Candle
    ) -> float:
        """Simulate order fill with slippage"""
        
    def apply_fees_and_slippage(self, price: float, side: str) -> float:
        """Apply trading fees and slippage to execution price"""
        
    def calculate_metrics(self) -> dict:
        """Calculate performance metrics from trade history"""
```

### 10. UIDisplay Interface

```python
class UIDisplay:
    def __init__(self):
        self.console = Console()  # Rich console for terminal UI
        
    def render_dashboard(
        self, 
        positions: List[Position],
        trades: List[Trade],
        indicators: dict,
        wallet_balance: float
    ):
        """Render main dashboard with live updates"""
        
    def display_backtest_results(self, results: dict):
        """Display backtest performance metrics"""
        
    def show_notification(self, message: str, level: str = "INFO"):
        """Display notification message"""
        
    def show_panic_confirmation(self):
        """Display panic close confirmation"""
```

## Data Models

### Indicator State

The system maintains a comprehensive indicator state that is updated on each candle close:

```python
class IndicatorState:
    # VWAP
    vwap_15m: float
    vwap_1h: float
    weekly_anchor_time: int
    
    # Squeeze Momentum
    squeeze_value: float
    squeeze_color: str
    is_squeezed: bool
    previous_squeeze_color: str  # For detecting releases
    
    # Trend Indicators
    adx: float
    trend_1h: str  # "BULLISH", "BEARISH", "NEUTRAL"
    trend_15m: str
    
    # Volatility
    atr_15m: float
    atr_1h: float
    
    # Volume
    rvol: float
    
    # Price Context
    current_price: float
    price_vs_vwap: str  # "ABOVE", "BELOW"
```

### Performance Metrics

```python
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    total_pnl: float
    total_pnl_percent: float
    roi: float
    
    max_drawdown: float
    max_drawdown_percent: float
    
    profit_factor: float  # Gross profit / Gross loss
    sharpe_ratio: float
    
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    
    average_trade_duration: int  # seconds
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Historical Data Completeness
*For any* historical data fetch request, the returned candle data should contain no time gaps larger than the requested timeframe interval.
**Validates: Requirements 1.2**

### Property 2: WebSocket Reconnection Backoff
*For any* WebSocket connection failure, the reconnection attempts should follow exponential backoff timing and stop after exactly 5 attempts.
**Validates: Requirements 1.4**

### Property 3: Mode Configuration Validity
*For any* valid operational mode string ("BACKTEST", "PAPER", "LIVE"), the system should initialize successfully with the correct subsystems activated.
**Validates: Requirements 1.5**

### Property 4: Trade Execution Costs
*For any* simulated trade in backtest mode, the final execution price should reflect exactly 0.05% trading fee and 0.02% slippage applied in the correct direction.
**Validates: Requirements 2.1, 2.2**

### Property 5: Backtest Metrics Completeness
*For any* completed backtest with at least one trade, the results should include calculated values for ROI, Maximum Drawdown, Profit Factor, Win Rate, and Total Trades.
**Validates: Requirements 2.3**

### Property 6: Realistic Fill Simulation
*For any* simulated order fill, the fill price should be within the candle's high-low range and respect the order direction (buys at ask, sells at bid).
**Validates: Requirements 2.4**

### Property 7: Trade Log Completeness
*For any* executed trade, the trade history log should contain entry_price, exit_price, pnl, and timestamp fields with valid values.
**Validates: Requirements 2.5**

### Property 8: VWAP Calculation Accuracy
*For any* series of candles with a weekly anchor timestamp, the calculated VWAP should equal the cumulative (price × volume) divided by cumulative volume from the anchor point.
**Validates: Requirements 3.1**

### Property 9: Squeeze Momentum Calculation
*For any* candle series with sufficient data, the Squeeze Momentum indicator should correctly identify squeeze state (Bollinger Bands inside Keltner Channels) and momentum direction.
**Validates: Requirements 3.2**

### Property 10: ADX Calculation Accuracy
*For any* candle series with at least 14 periods, the calculated ADX should match the standard ADX formula using 14-period lookback.
**Validates: Requirements 3.3**

### Property 11: ATR Calculation Accuracy
*For any* candle series with at least 14 periods, the calculated ATR should equal the 14-period exponential moving average of true range values.
**Validates: Requirements 3.4**

### Property 12: RVOL Calculation Accuracy
*For any* candle series with at least 20 periods, the calculated RVOL should equal current volume divided by the 20-period average volume.
**Validates: Requirements 3.5**

### Property 13: Trend Direction Consistency
*For any* 1-hour candle data with VWAP and momentum indicators, the determined trend direction should remain consistent until the next 1-hour candle close.
**Validates: Requirements 4.1, 4.4**

### Property 14: Bullish Trend Signal Filtering
*For any* market state where the 1-hour trend is bullish, the Signal_Generator should only emit LONG_ENTRY signals and never emit SHORT_ENTRY signals.
**Validates: Requirements 4.2**

### Property 15: Bearish Trend Signal Filtering
*For any* market state where the 1-hour trend is bearish, the Signal_Generator should only emit SHORT_ENTRY signals and never emit LONG_ENTRY signals.
**Validates: Requirements 4.3**

### Property 16: Long Entry Signal Validity
*For any* LONG_ENTRY signal generated, all of the following conditions must be true: 15m price > VWAP, 1h trend is bullish, Squeeze releases green, ADX > 20, and RVOL > 1.2.
**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

### Property 17: Short Entry Signal Validity
*For any* SHORT_ENTRY signal generated, all of the following conditions must be true: 15m price < VWAP, 1h trend is bearish, Squeeze releases maroon, ADX > 20, and RVOL > 1.2.
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

### Property 18: Signal Completeness
*For any* entry signal (LONG or SHORT), the signal object should contain type, timestamp, price, and indicators fields with valid values.
**Validates: Requirements 5.6, 6.6**

### Property 19: Position Size Risk Calculation
*For any* position size calculation, the potential loss at the stop-loss price should equal exactly 1% of the current wallet balance.
**Validates: Requirements 7.1**

### Property 20: Stop-Loss Distance Calculation
*For any* new position, the stop-loss distance from entry price should equal exactly 2x the current ATR value.
**Validates: Requirements 7.2**

### Property 21: Leverage Factor in Position Sizing
*For any* position size calculation, the margin required should equal (position_value / leverage) where leverage is 3.
**Validates: Requirements 7.3**

### Property 22: Position Size Recalculation on Balance Change
*For any* wallet balance change, the next position size calculation should use the new balance value, resulting in a different position size if ATR remains constant.
**Validates: Requirements 7.4**

### Property 23: Minimum Order Size Validation
*For any* calculated position size, it should be validated against Binance's minimum order requirements before order placement.
**Validates: Requirements 7.5**

### Property 24: Initial Stop-Loss Placement
*For any* newly opened position, the initial stop-loss price should be exactly 2x ATR away from the entry price in the direction that limits loss.
**Validates: Requirements 8.1**

### Property 25: Trailing Stop Activation and Updates
*For any* position in profit, the trailing stop should be set at 1.5x ATR from current price, and should only move closer to current price (never farther away).
**Validates: Requirements 8.2, 8.3, 8.5**

### Property 26: Stop-Loss Trigger Execution
*For any* position where current price crosses the stop-loss level, the position should be closed immediately with exit_reason indicating stop trigger.
**Validates: Requirements 8.4**

### Property 27: Position Configuration Consistency
*For any* opened position, the leverage should be set to 3x and margin mode should be ISOLATED (never CROSS).
**Validates: Requirements 9.1, 9.2, 9.3**

### Property 28: Margin Availability Validation
*For any* order placement attempt, if available margin is less than required margin, the order should be rejected and a warning should be logged.
**Validates: Requirements 9.4, 9.5**

### Property 29: Panic Close Completeness
*For any* panic close trigger, all open positions should be closed, all pending orders should be cancelled, and no new signals should be generated afterward.
**Validates: Requirements 10.1, 10.2, 10.3**

### Property 30: Order Placement on Signal
*For any* valid entry signal, a market order should be placed on Binance Futures with the calculated position size.
**Validates: Requirements 11.1**

### Property 31: Order Completeness
*For any* market order placed, it should include stop-loss parameters calculated from the current ATR.
**Validates: Requirements 11.2**

### Property 32: Order Retry Logic
*For any* failed order placement, the system should retry up to 3 times with exponentially increasing delays between attempts.
**Validates: Requirements 11.3**

### Property 33: Order Failure Handling
*For any* order that fails after all retry attempts, an error should be logged with details and user should be alerted.
**Validates: Requirements 11.4**

### Property 34: Fill Verification and Position Update
*For any* filled order, the fill price should be verified against expected range and position tracking should be updated with actual fill details.
**Validates: Requirements 11.5**

### Property 35: Trade Logging Completeness
*For any* executed trade (entry and exit), a log entry should be created containing entry_price, exit_price, pnl, and timestamp.
**Validates: Requirements 13.1**

### Property 36: Error Logging with Stack Traces
*For any* error or exception, a log entry should be created in the error log file containing the error message and full stack trace.
**Validates: Requirements 13.3**

### Property 37: Backtest Results Persistence
*For any* completed backtest, the results file should contain all calculated metrics: ROI, Max Drawdown, Profit Factor, Win Rate, and Total Trades.
**Validates: Requirements 13.4**

### Property 38: Configuration Validation
*For any* configuration loaded at startup, all required parameters should be validated for type and range before the system proceeds to initialization.
**Validates: Requirements 14.2**

### Property 39: Invalid Configuration Rejection
*For any* configuration with invalid parameters, the system should refuse to start and display specific error messages indicating which parameters are invalid.
**Validates: Requirements 14.3**

### Property 40: Default Configuration Values
*For any* optional configuration parameter that is missing, the system should use a documented default value and log which defaults were applied.
**Validates: Requirements 14.5**

### Property 41: API Key Security
*For any* log entry or display output, API keys should never appear in plain text (should be redacted or masked).
**Validates: Requirements 15.2**

### Property 42: API Permission Validation
*For any* trading operation, the system should verify that the API key has the required permissions before attempting the operation.
**Validates: Requirements 15.4**

### Property 43: HTTPS Protocol Enforcement
*For any* API request to Binance, the request URL should use the HTTPS protocol.
**Validates: Requirements 15.5**

### Property 44: WebSocket Reconnection on Disconnect
*For any* WebSocket disconnection event, the system should automatically attempt to reconnect using the backoff strategy.
**Validates: Requirements 16.1**

### Property 45: API Rate Limit Respect
*For any* sequence of API requests, the request rate should never exceed Binance's documented rate limits, with throttling applied when approaching limits.
**Validates: Requirements 16.2**

### Property 46: Critical Error Notification
*For any* critical error (authentication failure, insufficient margin, API errors), a notification should be sent to the user through the UI.
**Validates: Requirements 16.4**

### Property 47: Health Check Periodicity
*For any* 60-second time window during system operation, exactly one health check should be performed and logged.
**Validates: Requirements 16.5**


## Error Handling

### Error Categories

**Network Errors**
- WebSocket disconnections: Automatic reconnection with exponential backoff
- API request failures: Retry up to 3 times with exponential backoff
- Timeout errors: Log and alert user, continue operation if non-critical

**Data Errors**
- Missing candle data: Wait for next update, do not generate signals
- Invalid indicator values (NaN, Inf): Skip signal generation for that period
- Data gaps in historical fetch: Retry fetch or alert user if persistent

**Trading Errors**
- Insufficient margin: Reject trade, log warning, continue monitoring
- Order placement failure: Retry with backoff, alert user if all retries fail
- Invalid position size: Log error, skip trade, alert user
- API permission errors: Stop trading operations, alert user immediately

**System Errors**
- Configuration errors: Refuse to start, display clear error messages
- API authentication failure: Refuse to start, display authentication error
- Critical exceptions: Log with stack trace, attempt graceful shutdown
- Memory issues: Log warning, continue if possible, shutdown if critical

### Error Recovery Strategies

**Transient Errors** (Network, temporary API issues)
- Implement exponential backoff retry logic
- Maximum 3-5 retry attempts depending on operation criticality
- Log each retry attempt with error details
- Continue operation after successful retry

**Persistent Errors** (Configuration, authentication)
- Do not retry automatically
- Display clear error message to user
- Provide guidance on how to fix the issue
- Refuse to start or halt operation

**Critical Errors** (Insufficient margin, API permissions)
- Stop generating new signals immediately
- Attempt to close existing positions safely
- Alert user through all available channels
- Log detailed error information for debugging

### Graceful Degradation

- If 1h data stream fails: Continue with last known 1h trend, alert user
- If 15m data stream fails: Stop generating signals, attempt reconnection
- If indicator calculation fails: Skip that signal generation cycle
- If order placement fails after retries: Log trade opportunity missed, continue monitoring

## Testing Strategy

### Dual Testing Approach

The system will be validated using both unit tests and property-based tests:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
- Specific indicator calculations with known inputs/outputs
- Edge cases like empty data, single candle, boundary values
- Error handling scenarios (network failures, invalid data)
- Integration points between components
- Configuration loading and validation

**Property Tests**: Verify universal properties across all inputs
- Indicator calculations hold mathematical properties
- Signal generation always validates all conditions
- Position sizing always risks exactly 1% of balance
- Stop-loss never widens once set
- All trades are logged with complete information

Both testing approaches are complementary and necessary for comprehensive coverage. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across the input space.

### Property-Based Testing Configuration

**Framework**: We will use **Hypothesis** for Python property-based testing

**Test Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: binance-futures-bot, Property {number}: {property_text}`

**Example Property Test Structure**:
```python
from hypothesis import given, strategies as st

# Feature: binance-futures-bot, Property 19: Position Size Risk Calculation
@given(
    wallet_balance=st.floats(min_value=100, max_value=100000),
    entry_price=st.floats(min_value=1, max_value=100000),
    atr=st.floats(min_value=0.01, max_value=1000)
)
def test_position_size_risks_exactly_one_percent(wallet_balance, entry_price, atr):
    """For any position size calculation, the potential loss at stop-loss 
    should equal exactly 1% of wallet balance"""
    position_sizer = PositionSizer(config)
    result = position_sizer.calculate_position_size(wallet_balance, entry_price, atr)
    
    stop_distance = result['stop_loss_distance']
    quantity = result['quantity']
    potential_loss = quantity * stop_distance
    
    expected_risk = wallet_balance * 0.01
    assert abs(potential_loss - expected_risk) < 0.01  # Allow small floating point error
```

### Testing Priorities

**Critical Path Testing** (Must have 100% coverage):
1. Signal generation logic (all entry conditions)
2. Position sizing and risk calculations
3. Stop-loss placement and trailing logic
4. Order execution and retry logic
5. Panic close functionality

**Important Path Testing** (Should have high coverage):
1. Indicator calculations (VWAP, Squeeze, ADX, ATR, RVOL)
2. Backtest engine simulation logic
3. Data fetching and WebSocket management
4. Configuration loading and validation
5. Error handling and recovery

**Supporting Path Testing** (Good to have):
1. UI rendering and display
2. Logging and file operations
3. Performance metrics calculation
4. Health monitoring

### Integration Testing

**Backtest Integration Tests**:
- Run full backtest on known historical data
- Verify metrics match expected values
- Test with various market conditions (trending, ranging, volatile)

**WebSocket Integration Tests**:
- Test connection establishment and data flow
- Test reconnection after simulated disconnection
- Verify data synchronization between timeframes

**API Integration Tests** (Paper trading mode):
- Test order placement without real money
- Verify API authentication and permissions
- Test rate limiting and throttling

### Manual Testing Checklist

Before production deployment:
- [ ] Verify API keys are correctly configured
- [ ] Run backtest on recent 90-day period
- [ ] Test panic close (Escape key) functionality
- [ ] Verify dashboard displays correctly
- [ ] Test paper trading mode for 24 hours
- [ ] Verify all logs are being written correctly
- [ ] Test with intentional network disconnection
- [ ] Verify stop-loss orders are placed correctly
- [ ] Test with insufficient margin scenario
- [ ] Verify leverage and margin mode settings

## Implementation Notes

### Technology Stack

**Core Language**: Python 3.9+

**Key Libraries**:
- `python-binance`: Binance API client
- `pandas`: Data manipulation and analysis
- `numpy`: Numerical calculations
- `ta-lib` or `pandas-ta`: Technical indicator calculations
- `hypothesis`: Property-based testing
- `pytest`: Unit testing framework
- `rich`: Terminal UI rendering
- `pynput`: Keyboard input handling
- `websockets`: WebSocket connections

### Performance Considerations

**Data Management**:
- Keep only necessary candle history in memory (e.g., last 200 candles)
- Use efficient data structures (pandas DataFrame with proper indexing)
- Implement circular buffers for real-time data streams

**Indicator Calculation**:
- Calculate indicators incrementally when possible
- Cache indicator values to avoid recalculation
- Use vectorized operations (numpy/pandas) for batch calculations

**Order Execution**:
- Implement async order placement to avoid blocking
- Use connection pooling for API requests
- Implement request queuing to respect rate limits

### Security Considerations

**API Key Management**:
- Store API keys in environment variables or encrypted config
- Never commit API keys to version control
- Use read-only API keys for backtesting/paper trading
- Implement API key rotation capability

**Risk Controls**:
- Hard-coded maximum position size limits
- Daily loss limits (optional configuration)
- Maximum number of concurrent positions
- Minimum time between trades (prevent overtrading)

### Deployment Considerations

**Local Execution**:
- System designed to run on local machine (Windows/Linux/Mac)
- No cloud dependencies required
- All data stored locally

**Monitoring**:
- Terminal dashboard for real-time monitoring
- Log files for historical analysis
- Optional: Telegram/Discord notifications for critical events

**Maintenance**:
- Daily log rotation to manage disk space
- Periodic backtest runs to validate strategy performance
- Regular review of trade logs and metrics
