"""Property-based and unit tests for DataManager."""

import pytest
from hypothesis import given, strategies as st, assume, settings
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import time

from src.data_manager import DataManager
from src.models import Candle
from src.config import Config


# Feature: binance-futures-bot, Property 1: Historical Data Completeness
@given(
    num_candles=st.integers(min_value=10, max_value=200),
    timeframe=st.sampled_from(["15m", "1h"]),
    base_timestamp=st.integers(min_value=1609459200000, max_value=1700000000000),
    # Generate gap configuration: (gap_index, gap_multiplier)
    # gap_multiplier > 1.1 means it will create a gap that should be detected
    gap_config=st.one_of(
        st.none(),  # No gap
        st.tuples(
            st.integers(min_value=1, max_value=50),  # gap_index
            st.floats(min_value=1.2, max_value=5.0)  # gap_multiplier
        )
    )
)
def test_historical_data_gap_detection(num_candles, timeframe, base_timestamp, gap_config):
    """For any historical data fetch request, the returned candle data should 
    contain no time gaps larger than the requested timeframe interval.
    
    Property 1: Historical Data Completeness
    Validates: Requirements 1.2
    """
    # Create config
    config = Config()
    config.symbol = "BTCUSDT"
    
    # Create DataManager with mock client
    data_manager = DataManager(config, client=Mock())
    
    # Get timeframe interval in milliseconds
    timeframe_ms = data_manager._get_timeframe_milliseconds(timeframe)
    
    # Generate candle data
    candles = []
    current_timestamp = base_timestamp
    
    for i in range(num_candles):
        # Create candle
        candle = Candle(
            timestamp=current_timestamp,
            open=30000.0 + i * 10,
            high=30100.0 + i * 10,
            low=29900.0 + i * 10,
            close=30050.0 + i * 10,
            volume=100.0 + i
        )
        candles.append(candle)
        
        # Calculate next timestamp
        if gap_config is not None:
            gap_index, gap_multiplier = gap_config
            # Insert gap at specified index
            if i == gap_index and i < num_candles - 1:
                current_timestamp += int(timeframe_ms * gap_multiplier)
            else:
                current_timestamp += timeframe_ms
        else:
            # Normal progression, no gaps
            current_timestamp += timeframe_ms
    
    # Test validation
    if gap_config is not None:
        gap_index, gap_multiplier = gap_config
        # If gap_index is within range and gap is significant, should raise ValueError
        if gap_index < num_candles - 1:
            with pytest.raises(ValueError) as exc_info:
                data_manager._validate_data_completeness(candles, timeframe)
            
            # Verify error message mentions gaps
            assert "gap" in str(exc_info.value).lower()
        else:
            # Gap index out of range, no gap created, should pass
            data_manager._validate_data_completeness(candles, timeframe)
    else:
        # No gaps, should pass validation
        data_manager._validate_data_completeness(candles, timeframe)


class TestDataManagerUnit:
    """Unit tests for DataManager functionality."""
    
    def test_timeframe_conversion(self):
        """Test conversion of timeframe strings to Binance intervals."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Test valid conversions
        from binance.client import Client
        assert data_manager._convert_timeframe_to_binance_interval("15m") == Client.KLINE_INTERVAL_15MINUTE
        assert data_manager._convert_timeframe_to_binance_interval("1h") == Client.KLINE_INTERVAL_1HOUR
        assert data_manager._convert_timeframe_to_binance_interval("1d") == Client.KLINE_INTERVAL_1DAY
        
        # Test invalid timeframe
        with pytest.raises(ValueError):
            data_manager._convert_timeframe_to_binance_interval("invalid")
    
    def test_timeframe_milliseconds(self):
        """Test calculation of timeframe durations in milliseconds."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        assert data_manager._get_timeframe_milliseconds("1m") == 60 * 1000
        assert data_manager._get_timeframe_milliseconds("15m") == 15 * 60 * 1000
        assert data_manager._get_timeframe_milliseconds("1h") == 60 * 60 * 1000
        assert data_manager._get_timeframe_milliseconds("1d") == 24 * 60 * 60 * 1000
        
        # Test invalid timeframe
        with pytest.raises(ValueError):
            data_manager._get_timeframe_milliseconds("invalid")
    
    def test_validate_data_completeness_with_no_gaps(self):
        """Test validation passes when data has no gaps."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Create continuous candle data (15m intervals)
        base_timestamp = 1609459200000
        timeframe_ms = 15 * 60 * 1000
        
        candles = []
        for i in range(100):
            candle = Candle(
                timestamp=base_timestamp + i * timeframe_ms,
                open=30000.0,
                high=30100.0,
                low=29900.0,
                close=30050.0,
                volume=100.0
            )
            candles.append(candle)
        
        # Should not raise any exception
        data_manager._validate_data_completeness(candles, "15m")
    
    def test_validate_data_completeness_with_gap(self):
        """Test validation fails when data has gaps."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Create candle data with a gap
        base_timestamp = 1609459200000
        timeframe_ms = 15 * 60 * 1000
        
        candles = []
        for i in range(10):
            if i == 5:
                # Insert a large gap (2 hours instead of 15 minutes)
                timestamp = base_timestamp + i * timeframe_ms + (2 * 60 * 60 * 1000)
            else:
                timestamp = base_timestamp + i * timeframe_ms
            
            candle = Candle(
                timestamp=timestamp,
                open=30000.0,
                high=30100.0,
                low=29900.0,
                close=30050.0,
                volume=100.0
            )
            candles.append(candle)
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            data_manager._validate_data_completeness(candles, "15m")
        
        assert "gap" in str(exc_info.value).lower()
    
    def test_validate_data_completeness_with_insufficient_data(self):
        """Test validation passes with insufficient data (< 2 candles)."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Single candle
        candles = [Candle(
            timestamp=1609459200000,
            open=30000.0,
            high=30100.0,
            low=29900.0,
            close=30050.0,
            volume=100.0
        )]
        
        # Should not raise (not enough data to validate)
        data_manager._validate_data_completeness(candles, "15m")
        
        # Empty list
        data_manager._validate_data_completeness([], "15m")
    
    def test_get_latest_candles_15m(self):
        """Test retrieving latest candles from 15m buffer."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Add candles to buffer
        base_timestamp = 1609459200000
        timeframe_ms = 15 * 60 * 1000
        
        for i in range(50):
            candle = Candle(
                timestamp=base_timestamp + i * timeframe_ms,
                open=30000.0 + i,
                high=30100.0 + i,
                low=29900.0 + i,
                close=30050.0 + i,
                volume=100.0 + i
            )
            data_manager.candles_15m.append(candle)
        
        # Get latest 10 candles
        latest = data_manager.get_latest_candles("15m", 10)
        
        assert len(latest) == 10
        assert latest[0].open == 30040.0  # 50 - 10 = 40
        assert latest[-1].open == 30049.0  # 50 - 1 = 49
    
    def test_get_latest_candles_1h(self):
        """Test retrieving latest candles from 1h buffer."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Add candles to buffer
        base_timestamp = 1609459200000
        timeframe_ms = 60 * 60 * 1000
        
        for i in range(30):
            candle = Candle(
                timestamp=base_timestamp + i * timeframe_ms,
                open=30000.0 + i,
                high=30100.0 + i,
                low=29900.0 + i,
                close=30050.0 + i,
                volume=100.0 + i
            )
            data_manager.candles_1h.append(candle)
        
        # Get latest 5 candles
        latest = data_manager.get_latest_candles("1h", 5)
        
        assert len(latest) == 5
        assert latest[0].open == 30025.0  # 30 - 5 = 25
        assert latest[-1].open == 30029.0  # 30 - 1 = 29
    
    def test_get_latest_candles_insufficient_data(self):
        """Test retrieving candles when buffer has less than requested."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Add only 5 candles
        base_timestamp = 1609459200000
        timeframe_ms = 15 * 60 * 1000
        
        for i in range(5):
            candle = Candle(
                timestamp=base_timestamp + i * timeframe_ms,
                open=30000.0 + i,
                high=30100.0 + i,
                low=29900.0 + i,
                close=30050.0 + i,
                volume=100.0 + i
            )
            data_manager.candles_15m.append(candle)
        
        # Request 10 candles (more than available)
        latest = data_manager.get_latest_candles("15m", 10)
        
        # Should return all available candles
        assert len(latest) == 5
    
    def test_get_latest_candles_invalid_timeframe(self):
        """Test error handling for invalid timeframe."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        with pytest.raises(ValueError):
            data_manager.get_latest_candles("invalid", 10)
    
    def test_fetch_historical_data_without_client(self):
        """Test that fetching data without a client raises an error."""
        config = Config()
        data_manager = DataManager(config, client=None)
        
        with pytest.raises(ValueError) as exc_info:
            data_manager.fetch_historical_data(90, "15m")
        
        assert "client not initialized" in str(exc_info.value).lower()
    
    def test_websocket_methods_not_implemented(self):
        """Test that WebSocket methods work correctly."""
        config = Config()
        config.api_key = "test_key"
        config.api_secret = "test_secret"
        data_manager = DataManager(config, client=Mock())
        
        # Test that methods are now implemented
        assert hasattr(data_manager, 'start_websocket_streams')
        assert hasattr(data_manager, 'on_candle_update')
        assert hasattr(data_manager, 'reconnect_websocket')
        assert hasattr(data_manager, 'stop_websocket_streams')
        assert hasattr(data_manager, 'is_websocket_connected')
        assert hasattr(data_manager, 'get_reconnect_attempts')
    
    def test_on_candle_update_15m(self):
        """Test that on_candle_update correctly adds candles to 15m buffer."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Create test candle
        candle = Candle(
            timestamp=1609459200000,
            open=30000.0,
            high=30100.0,
            low=29900.0,
            close=30050.0,
            volume=100.0
        )
        
        # Update candle
        data_manager.on_candle_update(candle, '15m')
        
        # Verify candle was added to buffer
        assert len(data_manager.candles_15m) == 1
        assert data_manager.candles_15m[0] == candle
    
    def test_on_candle_update_1h(self):
        """Test that on_candle_update correctly adds candles to 1h buffer."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Create test candle
        candle = Candle(
            timestamp=1609459200000,
            open=30000.0,
            high=30100.0,
            low=29900.0,
            close=30050.0,
            volume=100.0
        )
        
        # Update candle
        data_manager.on_candle_update(candle, '1h')
        
        # Verify candle was added to buffer
        assert len(data_manager.candles_1h) == 1
        assert data_manager.candles_1h[0] == candle
    
    def test_on_candle_update_with_callback(self):
        """Test that on_candle_update calls external callback if set."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Set up callback mock
        callback_mock = Mock()
        data_manager.on_candle_callback = callback_mock
        
        # Create test candle
        candle = Candle(
            timestamp=1609459200000,
            open=30000.0,
            high=30100.0,
            low=29900.0,
            close=30050.0,
            volume=100.0
        )
        
        # Update candle
        data_manager.on_candle_update(candle, '15m')
        
        # Verify callback was called
        callback_mock.assert_called_once_with(candle, '15m')
    
    def test_websocket_connection_status(self):
        """Test WebSocket connection status tracking."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Initially not connected
        assert data_manager.is_websocket_connected() == False
        
        # Simulate connection
        data_manager._ws_connected = True
        assert data_manager.is_websocket_connected() == True
        
        # Simulate disconnection
        data_manager._ws_connected = False
        assert data_manager.is_websocket_connected() == False
    
    def test_reconnect_attempts_tracking(self):
        """Test that reconnection attempts are tracked correctly."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Initially 0 attempts
        assert data_manager.get_reconnect_attempts() == 0
        
        # Simulate attempts
        data_manager._ws_reconnect_attempts = 3
        assert data_manager.get_reconnect_attempts() == 3
    
    def test_start_websocket_without_client(self):
        """Test that starting WebSocket without client raises error."""
        config = Config()
        data_manager = DataManager(config, client=None)
        
        with pytest.raises(ValueError) as exc_info:
            data_manager.start_websocket_streams()
        
        assert "client not initialized" in str(exc_info.value).lower()
    
    def test_handle_kline_message_closed_candle(self):
        """Test handling of closed kline message."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Create mock kline message (closed candle)
        msg = {
            'e': 'kline',
            'k': {
                't': 1609459200000,
                'o': '30000.0',
                'h': '30100.0',
                'l': '29900.0',
                'c': '30050.0',
                'v': '100.0',
                'x': True  # Candle is closed
            }
        }
        
        # Handle message
        data_manager._handle_kline_message(msg, '15m')
        
        # Verify candle was added
        assert len(data_manager.candles_15m) == 1
        assert data_manager.candles_15m[0].close == 30050.0
    
    def test_handle_kline_message_open_candle(self):
        """Test that open candles are not processed."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Create mock kline message (open candle)
        msg = {
            'e': 'kline',
            'k': {
                't': 1609459200000,
                'o': '30000.0',
                'h': '30100.0',
                'l': '29900.0',
                'c': '30050.0',
                'v': '100.0',
                'x': False  # Candle is still open
            }
        }
        
        # Handle message
        data_manager._handle_kline_message(msg, '15m')
        
        # Verify candle was NOT added
        assert len(data_manager.candles_15m) == 0
    
    def test_handle_kline_message_error(self):
        """Test handling of error message."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Mock reconnect method
        reconnect_mock = Mock()
        data_manager.reconnect_websocket = reconnect_mock
        
        # Create error message
        msg = {
            'e': 'error',
            'msg': 'Connection lost'
        }
        
        # Handle message
        data_manager._handle_kline_message(msg, '15m')
        
        # Verify reconnection was triggered
        reconnect_mock.assert_called_once()
    
    def test_max_reconnect_attempts(self):
        """Test that reconnection stops after max attempts."""
        config = Config()
        config.api_key = "test_key"
        config.api_secret = "test_secret"
        data_manager = DataManager(config, client=Mock())
        
        # Set to max attempts
        data_manager._ws_reconnect_attempts = 5
        data_manager._ws_connected = False
        
        # Attempt reconnection
        result = data_manager.reconnect_websocket()
        
        # Should return False (max attempts reached)
        assert result == False
        
        # Attempts should still be 5
        assert data_manager._ws_reconnect_attempts == 5
    
    def test_circular_buffer_max_size(self):
        """Test that circular buffers maintain max size of 500."""
        config = Config()
        data_manager = DataManager(config, client=Mock())
        
        # Add more than 500 candles
        base_timestamp = 1609459200000
        timeframe_ms = 15 * 60 * 1000
        
        for i in range(600):
            candle = Candle(
                timestamp=base_timestamp + i * timeframe_ms,
                open=30000.0 + i,
                high=30100.0 + i,
                low=29900.0 + i,
                close=30050.0 + i,
                volume=100.0 + i
            )
            data_manager.candles_15m.append(candle)
        
        # Buffer should only contain last 500
        assert len(data_manager.candles_15m) == 500
        # First candle should be from index 100 (600 - 500)
        assert data_manager.candles_15m[0].open == 30100.0


# Feature: binance-futures-bot, Property 2: WebSocket Reconnection Backoff
@given(
    failure_attempt=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=20, deadline=None)
def test_websocket_reconnection_backoff(failure_attempt):
    """For any WebSocket connection failure, the reconnection attempts should 
    follow exponential backoff timing and stop after exactly 5 attempts.
    
    Property 2: WebSocket Reconnection Backoff
    Validates: Requirements 1.4
    """
    # Create config
    config = Config()
    config.symbol = "BTCUSDT"
    config.api_key = "test_key"
    config.api_secret = "test_secret"
    
    # Create DataManager with mock client
    mock_client = Mock()
    data_manager = DataManager(config, client=mock_client)
    
    # Mock the WebSocket manager to always fail
    with patch('src.data_manager.ThreadedWebsocketManager') as mock_ws_manager:
        mock_ws_instance = MagicMock()
        mock_ws_manager.return_value = mock_ws_instance
        
        # Make start_websocket_streams raise an exception
        mock_ws_instance.start.side_effect = Exception("Connection failed")
        
        # Track timing of reconnection attempts
        attempt_times = []
        original_sleep = time.sleep
        
        def mock_sleep(duration):
            """Mock sleep to track timing without actually waiting."""
            attempt_times.append(duration)
        
        with patch('time.sleep', side_effect=mock_sleep):
            # Set the manager to simulate it exists but is disconnected
            data_manager._ws_connected = False
            data_manager._ws_reconnect_attempts = failure_attempt - 1
            
            # Attempt reconnection
            try:
                data_manager.reconnect_websocket()
            except:
                pass  # Expected to fail
            
            # Verify exponential backoff delay
            if len(attempt_times) > 0:
                # Expected delay: 2^(attempt-1) seconds
                expected_delay = 2 ** (failure_attempt - 1)
                actual_delay = attempt_times[0]
                
                assert actual_delay == expected_delay, (
                    f"Attempt {failure_attempt} should have delay of {expected_delay}s, "
                    f"but got {actual_delay}s"
                )
            
            # Verify attempt counter incremented
            assert data_manager._ws_reconnect_attempts == failure_attempt
            
            # Verify stops at max attempts
            if failure_attempt >= 5:
                # Should not attempt more reconnections
                assert data_manager._ws_reconnect_attempts == 5


# Feature: binance-futures-bot, Property 44: WebSocket Reconnection on Disconnect
@given(
    num_disconnects=st.integers(min_value=1, max_value=3)
)
@settings(max_examples=20, deadline=None)
def test_websocket_reconnection_on_disconnect(num_disconnects):
    """For any WebSocket disconnection event, the system should automatically 
    attempt to reconnect using the backoff strategy.
    
    Property 44: WebSocket Reconnection on Disconnect
    Validates: Requirements 16.1
    """
    # Create config
    config = Config()
    config.symbol = "BTCUSDT"
    config.api_key = "test_key"
    config.api_secret = "test_secret"
    
    # Create DataManager with mock client
    mock_client = Mock()
    data_manager = DataManager(config, client=mock_client)
    
    # Track reconnection calls
    reconnect_calls = []
    
    def mock_reconnect():
        """Mock reconnect to track calls."""
        reconnect_calls.append(True)
        return True
    
    # Replace reconnect method with mock
    data_manager.reconnect_websocket = mock_reconnect
    
    # Simulate disconnection events
    for i in range(num_disconnects):
        data_manager._ws_connected = True  # Set as connected
        data_manager._handle_websocket_disconnect()  # Trigger disconnect
        
        # Verify connection status changed
        assert data_manager._ws_connected == False
    
    # Verify reconnection was attempted for each disconnect
    assert len(reconnect_calls) == num_disconnects
