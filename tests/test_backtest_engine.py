"""Tests for BacktestEngine class."""

import pytest
from hypothesis import given, strategies as st, settings
from src.backtest_engine import BacktestEngine
from src.config import Config
from src.strategy import StrategyEngine
from src.risk_manager import RiskManager
from src.position_sizer import PositionSizer
from src.models import Candle, Signal


class TestBacktestEngine:
    """Test suite for BacktestEngine property-based tests."""
    
    # Feature: binance-futures-bot, Property 4: Trade Execution Costs
    @settings(max_examples=100)
    @given(
        price=st.floats(min_value=100.0, max_value=100000.0),
        side=st.sampled_from(["BUY", "SELL"])
    )
    def test_trade_execution_costs_property(self, price, side):
        """For any simulated trade in backtest mode, the final execution price 
        should reflect exactly 0.05% trading fee and 0.02% slippage applied 
        in the correct direction.
        
        **Validates: Requirements 2.1, 2.2**
        """
        # Create fresh instances for each test
        config = Config()
        config.symbol = "BTCUSDT"
        config.risk_per_trade = 0.01
        config.leverage = 3
        config.trading_fee = 0.0005  # 0.05%
        config.slippage = 0.0002     # 0.02%
        
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        # Apply fees and slippage
        adjusted_price = backtest_engine.apply_fees_and_slippage(price, side)
        
        # Calculate expected total cost
        expected_total_cost = backtest_engine.config.trading_fee + backtest_engine.config.slippage
        
        if side == "BUY":
            # For buys, price should increase
            expected_price = price * (1 + expected_total_cost)
            assert adjusted_price > price, "Buy price should increase with fees and slippage"
        else:  # SELL
            # For sells, price should decrease
            expected_price = price * (1 - expected_total_cost)
            assert adjusted_price < price, "Sell price should decrease with fees and slippage"
        
        # Check that the adjustment is exactly the expected amount
        # Allow small floating point error
        assert abs(adjusted_price - expected_price) < 0.01, \
            f"Price adjustment should be exactly {expected_total_cost * 100}%"
        
        # Verify the exact percentages
        if side == "BUY":
            actual_cost_pct = (adjusted_price - price) / price
        else:
            actual_cost_pct = (price - adjusted_price) / price
        
        # Should be exactly 0.05% + 0.02% = 0.07%
        expected_cost_pct = 0.0005 + 0.0002  # 0.07%
        assert abs(actual_cost_pct - expected_cost_pct) < 1e-6, \
            f"Total cost should be exactly 0.07%, got {actual_cost_pct * 100}%"
    
    # Feature: binance-futures-bot, Property 5: Backtest Metrics Completeness
    @settings(max_examples=100)
    @given(
        num_winning_trades=st.integers(min_value=1, max_value=50),
        num_losing_trades=st.integers(min_value=0, max_value=50),
        initial_balance=st.floats(min_value=1000.0, max_value=100000.0)
    )
    def test_backtest_metrics_completeness_property(
        self, 
        num_winning_trades, 
        num_losing_trades,
        initial_balance
    ):
        """For any completed backtest with at least one trade, the results 
        should include calculated values for ROI, Maximum Drawdown, Profit Factor, 
        Win Rate, and Total Trades.
        
        **Validates: Requirements 2.3**
        """
        from src.models import Trade
        import time
        
        # Create fresh instances
        config = Config()
        config.symbol = "BTCUSDT"
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        # Set initial balance
        backtest_engine.initial_balance = initial_balance
        backtest_engine.current_balance = initial_balance
        
        # Create winning trades
        for i in range(num_winning_trades):
            trade = Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=50000.0,
                exit_price=51000.0,
                quantity=0.1,
                pnl=100.0,  # Positive PnL
                pnl_percent=2.0,
                entry_time=int(time.time() * 1000),
                exit_time=int(time.time() * 1000) + 3600000,
                exit_reason="TRAILING_STOP"
            )
            backtest_engine.trades.append(trade)
        
        # Create losing trades
        for i in range(num_losing_trades):
            trade = Trade(
                symbol="BTCUSDT",
                side="SHORT",
                entry_price=50000.0,
                exit_price=50500.0,
                quantity=0.1,
                pnl=-50.0,  # Negative PnL
                pnl_percent=-1.0,
                entry_time=int(time.time() * 1000),
                exit_time=int(time.time() * 1000) + 3600000,
                exit_reason="STOP_LOSS"
            )
            backtest_engine.trades.append(trade)
        
        # Create equity curve
        backtest_engine.equity_curve = [initial_balance]
        
        # Calculate metrics
        metrics = backtest_engine.calculate_metrics()
        
        # Verify all required metrics are present
        required_keys = [
            'total_trades',
            'winning_trades',
            'losing_trades',
            'win_rate',
            'total_pnl',
            'roi',
            'max_drawdown',
            'profit_factor',
            'sharpe_ratio'
        ]
        
        for key in required_keys:
            assert key in metrics, f"Missing required metric: {key}"
            assert metrics[key] is not None, f"Metric {key} should not be None"
        
        # Verify correctness of basic metrics
        assert metrics['total_trades'] == num_winning_trades + num_losing_trades
        assert metrics['winning_trades'] == num_winning_trades
        assert metrics['losing_trades'] == num_losing_trades
        
        # Verify win rate calculation
        expected_win_rate = (num_winning_trades / (num_winning_trades + num_losing_trades)) * 100
        assert abs(metrics['win_rate'] - expected_win_rate) < 0.01
        
        # Verify total PnL
        expected_pnl = num_winning_trades * 100.0 + num_losing_trades * (-50.0)
        assert abs(metrics['total_pnl'] - expected_pnl) < 0.01
        
        # Verify ROI is calculated
        expected_roi = (expected_pnl / initial_balance) * 100
        assert abs(metrics['roi'] - expected_roi) < 0.01
    
    # Feature: binance-futures-bot, Property 6: Realistic Fill Simulation
    @settings(max_examples=100)
    @given(
        open_price=st.floats(min_value=1000.0, max_value=100000.0),
        high_offset=st.floats(min_value=0.0, max_value=5000.0),
        low_offset=st.floats(min_value=0.0, max_value=5000.0),
        close_offset=st.floats(min_value=-2500.0, max_value=2500.0),
        signal_type=st.sampled_from(["LONG_ENTRY", "SHORT_ENTRY", "EXIT"]),
        is_long=st.booleans()
    )
    def test_realistic_fill_simulation_property(
        self,
        open_price,
        high_offset,
        low_offset,
        close_offset,
        signal_type,
        is_long
    ):
        """For any simulated order fill, the fill price should be within the 
        candle's high-low range and respect the order direction (buys at ask, 
        sells at bid).
        
        **Validates: Requirements 2.4**
        """
        # Create fresh instances
        config = Config()
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        # Create a candle with valid OHLC relationships
        high = open_price + high_offset
        low = open_price - low_offset
        close = open_price + close_offset
        
        # Ensure close is within high/low range
        close = max(low, min(high, close))
        
        candle = Candle(
            timestamp=1000000,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=100.0
        )
        
        # Simulate trade execution
        fill_price = backtest_engine.simulate_trade_execution(
            signal_type,
            candle,
            is_long
        )
        
        # Verify fill price is within candle range
        assert fill_price >= candle.low, \
            f"Fill price {fill_price} should be >= candle low {candle.low}"
        assert fill_price <= candle.high, \
            f"Fill price {fill_price} should be <= candle high {candle.high}"
        
        # For entry signals, should use open price
        if signal_type in ["LONG_ENTRY", "SHORT_ENTRY"]:
            assert fill_price == candle.open, \
                f"Entry fills should use candle open price"
        
        # For exit signals, verify realistic fill based on direction
        if signal_type == "EXIT":
            if is_long:
                # Long exits (stop-loss) should be between low and close
                assert candle.low <= fill_price <= candle.close, \
                    f"Long exit should be between low and close"
            else:
                # Short exits (stop-loss) should be between close and high
                assert candle.close <= fill_price <= candle.high, \
                    f"Short exit should be between close and high"


class TestBacktestEngineUnit:
    """Unit tests for BacktestEngine."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        config = Config()
        config.symbol = "BTCUSDT"
        config.risk_per_trade = 0.01
        config.leverage = 3
        config.stop_loss_atr_multiplier = 2.0
        config.trailing_stop_atr_multiplier = 1.5
        config.atr_period = 14
        config.adx_period = 14
        config.adx_threshold = 20.0
        config.rvol_period = 20
        config.rvol_threshold = 1.2
        config.trading_fee = 0.0005
        config.slippage = 0.0002
        return config
    
    @pytest.fixture
    def strategy(self, config):
        """Create a test strategy engine."""
        return StrategyEngine(config)
    
    @pytest.fixture
    def position_sizer(self, config):
        """Create a test position sizer."""
        return PositionSizer(config)
    
    @pytest.fixture
    def risk_manager(self, config, position_sizer):
        """Create a test risk manager."""
        return RiskManager(config, position_sizer)
    
    @pytest.fixture
    def backtest_engine(self, config, strategy, risk_manager):
        """Create a test backtest engine."""
        return BacktestEngine(config, strategy, risk_manager)
    
    def test_apply_fees_and_slippage_buy(self, backtest_engine):
        """Test that fees and slippage are correctly applied to buy orders."""
        price = 50000.0
        adjusted = backtest_engine.apply_fees_and_slippage(price, "BUY")
        
        # Should increase by 0.07%
        expected = price * 1.0007
        assert abs(adjusted - expected) < 0.01
        assert adjusted > price
    
    def test_apply_fees_and_slippage_sell(self, backtest_engine):
        """Test that fees and slippage are correctly applied to sell orders."""
        price = 50000.0
        adjusted = backtest_engine.apply_fees_and_slippage(price, "SELL")
        
        # Should decrease by 0.07%
        expected = price * 0.9993
        assert abs(adjusted - expected) < 0.01
        assert adjusted < price
    
    def test_apply_fees_and_slippage_invalid_side(self, backtest_engine):
        """Test that invalid side raises ValueError."""
        with pytest.raises(ValueError, match="side must be 'BUY' or 'SELL'"):
            backtest_engine.apply_fees_and_slippage(50000.0, "INVALID")
    
    def test_apply_fees_and_slippage_invalid_price(self, backtest_engine):
        """Test that invalid price raises ValueError."""
        with pytest.raises(ValueError, match="price must be positive"):
            backtest_engine.apply_fees_and_slippage(-100.0, "BUY")
        
        with pytest.raises(ValueError, match="price must be positive"):
            backtest_engine.apply_fees_and_slippage(0.0, "BUY")
    
    def test_simulate_trade_execution_long_entry(self, backtest_engine):
        """Test simulation of long entry execution."""
        candle = Candle(
            timestamp=1000000,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=100.0
        )
        
        fill_price = backtest_engine.simulate_trade_execution(
            "LONG_ENTRY",
            candle,
            is_long=True
        )
        
        # Should use candle open
        assert fill_price == candle.open
    
    def test_simulate_trade_execution_short_entry(self, backtest_engine):
        """Test simulation of short entry execution."""
        candle = Candle(
            timestamp=1000000,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=100.0
        )
        
        fill_price = backtest_engine.simulate_trade_execution(
            "SHORT_ENTRY",
            candle,
            is_long=False
        )
        
        # Should use candle open
        assert fill_price == candle.open
    
    def test_simulate_trade_execution_long_exit(self, backtest_engine):
        """Test simulation of long exit (stop-loss) execution."""
        candle = Candle(
            timestamp=1000000,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=100.0
        )
        
        fill_price = backtest_engine.simulate_trade_execution(
            "EXIT",
            candle,
            is_long=True
        )
        
        # Should be between low and close, closer to low
        assert candle.low <= fill_price <= candle.close
    
    def test_simulate_trade_execution_short_exit(self, backtest_engine):
        """Test simulation of short exit (stop-loss) execution."""
        candle = Candle(
            timestamp=1000000,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=100.0
        )
        
        fill_price = backtest_engine.simulate_trade_execution(
            "EXIT",
            candle,
            is_long=False
        )
        
        # Should be between close and high, closer to high
        assert candle.close <= fill_price <= candle.high
    
    def test_calculate_metrics_no_trades(self, backtest_engine):
        """Test metrics calculation with no trades."""
        backtest_engine.trades = []
        backtest_engine.initial_balance = 10000.0
        
        metrics = backtest_engine.calculate_metrics()
        
        assert metrics['total_trades'] == 0
        assert metrics['winning_trades'] == 0
        assert metrics['losing_trades'] == 0
        assert metrics['win_rate'] == 0.0
        assert metrics['total_pnl'] == 0.0
        assert metrics['roi'] == 0.0
    
    def test_calculate_max_drawdown_empty(self, backtest_engine):
        """Test max drawdown calculation with empty equity curve."""
        backtest_engine.equity_curve = []
        
        drawdown = backtest_engine._calculate_max_drawdown()
        
        assert drawdown == 0.0
    
    def test_calculate_max_drawdown_no_drawdown(self, backtest_engine):
        """Test max drawdown calculation with no drawdown."""
        backtest_engine.equity_curve = [10000, 10100, 10200, 10300]
        
        drawdown = backtest_engine._calculate_max_drawdown()
        
        assert drawdown == 0.0
    
    def test_calculate_max_drawdown_with_drawdown(self, backtest_engine):
        """Test max drawdown calculation with drawdown."""
        backtest_engine.equity_curve = [10000, 10500, 10200, 9800, 10100]
        
        drawdown = backtest_engine._calculate_max_drawdown()
        
        # Peak was 10500, lowest after peak was 9800
        # Drawdown = 10500 - 9800 = 700
        assert drawdown == 700.0
    
    def test_calculate_sharpe_ratio_insufficient_trades(self, backtest_engine):
        """Test Sharpe ratio calculation with insufficient trades."""
        backtest_engine.trades = []
        
        sharpe = backtest_engine._calculate_sharpe_ratio()
        
        assert sharpe == 0.0
    
    def test_backtest_with_winning_trades(self):
        """Test backtest with winning trades scenario."""
        from src.models import Trade
        import time
        
        config = Config()
        config.symbol = "BTCUSDT"
        config.trading_fee = 0.0005
        config.slippage = 0.0002
        
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        # Set initial balance
        backtest_engine.initial_balance = 10000.0
        
        # Create winning trades
        for i in range(5):
            trade = Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=50000.0,
                exit_price=51000.0,
                quantity=0.1,
                pnl=100.0,
                pnl_percent=2.0,
                entry_time=int(time.time() * 1000),
                exit_time=int(time.time() * 1000) + 3600000,
                exit_reason="TRAILING_STOP"
            )
            backtest_engine.trades.append(trade)
        
        backtest_engine.equity_curve = [10000, 10100, 10200, 10300, 10400, 10500]
        
        metrics = backtest_engine.calculate_metrics()
        
        assert metrics['total_trades'] == 5
        assert metrics['winning_trades'] == 5
        assert metrics['losing_trades'] == 0
        assert metrics['win_rate'] == 100.0
        assert metrics['total_pnl'] == 500.0
        assert metrics['roi'] == 5.0
        assert metrics['profit_factor'] == 0.0  # No losses
    
    def test_backtest_with_losing_trades(self):
        """Test backtest with losing trades scenario."""
        from src.models import Trade
        import time
        
        config = Config()
        config.symbol = "BTCUSDT"
        config.trading_fee = 0.0005
        config.slippage = 0.0002
        
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        # Set initial balance
        backtest_engine.initial_balance = 10000.0
        
        # Create losing trades
        for i in range(3):
            trade = Trade(
                symbol="BTCUSDT",
                side="SHORT",
                entry_price=50000.0,
                exit_price=50500.0,
                quantity=0.1,
                pnl=-50.0,
                pnl_percent=-1.0,
                entry_time=int(time.time() * 1000),
                exit_time=int(time.time() * 1000) + 3600000,
                exit_reason="STOP_LOSS"
            )
            backtest_engine.trades.append(trade)
        
        backtest_engine.equity_curve = [10000, 9950, 9900, 9850]
        
        metrics = backtest_engine.calculate_metrics()
        
        assert metrics['total_trades'] == 3
        assert metrics['winning_trades'] == 0
        assert metrics['losing_trades'] == 3
        assert metrics['win_rate'] == 0.0
        assert metrics['total_pnl'] == -150.0
        assert metrics['roi'] == -1.5
        assert metrics['profit_factor'] == 0.0  # No wins
    
    def test_backtest_with_mixed_results(self):
        """Test backtest with mixed winning and losing trades."""
        from src.models import Trade
        import time
        
        config = Config()
        config.symbol = "BTCUSDT"
        config.trading_fee = 0.0005
        config.slippage = 0.0002
        
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        # Set initial balance
        backtest_engine.initial_balance = 10000.0
        
        # Create 3 winning trades
        for i in range(3):
            trade = Trade(
                symbol="BTCUSDT",
                side="LONG",
                entry_price=50000.0,
                exit_price=51000.0,
                quantity=0.1,
                pnl=100.0,
                pnl_percent=2.0,
                entry_time=int(time.time() * 1000),
                exit_time=int(time.time() * 1000) + 3600000,
                exit_reason="TRAILING_STOP"
            )
            backtest_engine.trades.append(trade)
        
        # Create 2 losing trades
        for i in range(2):
            trade = Trade(
                symbol="BTCUSDT",
                side="SHORT",
                entry_price=50000.0,
                exit_price=50500.0,
                quantity=0.1,
                pnl=-50.0,
                pnl_percent=-1.0,
                entry_time=int(time.time() * 1000),
                exit_time=int(time.time() * 1000) + 3600000,
                exit_reason="STOP_LOSS"
            )
            backtest_engine.trades.append(trade)
        
        backtest_engine.equity_curve = [10000, 10100, 10200, 10300, 10250, 10200]
        
        metrics = backtest_engine.calculate_metrics()
        
        # Verify metrics calculations
        assert metrics['total_trades'] == 5
        assert metrics['winning_trades'] == 3
        assert metrics['losing_trades'] == 2
        assert metrics['win_rate'] == 60.0
        assert metrics['total_pnl'] == 200.0  # 3*100 - 2*50
        assert metrics['roi'] == 2.0
        
        # Profit factor = gross profit / gross loss = 300 / 100 = 3.0
        assert abs(metrics['profit_factor'] - 3.0) < 0.01
        
        # Verify average win/loss
        assert metrics['average_win'] == 100.0
        assert metrics['average_loss'] == -50.0
        assert metrics['largest_win'] == 100.0
        assert metrics['largest_loss'] == -50.0
    
    def test_verify_metrics_calculations(self):
        """Test that metrics are calculated correctly."""
        from src.models import Trade
        import time
        
        config = Config()
        strategy = StrategyEngine(config)
        position_sizer = PositionSizer(config)
        risk_manager = RiskManager(config, position_sizer)
        backtest_engine = BacktestEngine(config, strategy, risk_manager)
        
        backtest_engine.initial_balance = 10000.0
        
        # Create specific trades to test calculations
        trades = [
            Trade("BTCUSDT", "LONG", 50000, 51000, 0.1, 100, 2.0, 
                  int(time.time() * 1000), int(time.time() * 1000) + 3600000, "TRAILING_STOP"),
            Trade("BTCUSDT", "SHORT", 50000, 50500, 0.1, -50, -1.0,
                  int(time.time() * 1000), int(time.time() * 1000) + 7200000, "STOP_LOSS"),
            Trade("BTCUSDT", "LONG", 51000, 52000, 0.1, 100, 2.0,
                  int(time.time() * 1000), int(time.time() * 1000) + 10800000, "TRAILING_STOP"),
        ]
        
        backtest_engine.trades = trades
        backtest_engine.equity_curve = [10000, 10100, 10050, 10150]
        
        metrics = backtest_engine.calculate_metrics()
        
        # Verify all calculations
        assert metrics['total_trades'] == 3
        assert metrics['winning_trades'] == 2
        assert metrics['losing_trades'] == 1
        assert abs(metrics['win_rate'] - 66.67) < 0.1
        assert metrics['total_pnl'] == 150.0
        assert metrics['roi'] == 1.5
        
        # Max drawdown: peak 10100, trough 10050 = 50
        assert metrics['max_drawdown'] == 50.0
        
        # Profit factor: 200 / 50 = 4.0
        assert abs(metrics['profit_factor'] - 4.0) < 0.01
        
        # Average trade duration
        assert metrics['average_trade_duration'] > 0
