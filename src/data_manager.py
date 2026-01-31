"""Data management for historical and real-time market data."""

from typing import List, Optional, Callable
from datetime import datetime, timedelta
from collections import deque
import time
import logging
import threading

from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance import ThreadedWebsocketManager

from src.models import Candle
from src.config import Config

# Configure logging
logger = logging.getLogger(__name__)


class DataManager:
    """Manages historical and real-time market data from Binance.
    
    Handles:
    - Fetching historical kline data for backtesting
    - Managing WebSocket connections for real-time data
    - Validating data completeness and detecting gaps
    - Maintaining circular buffers for memory efficiency
    """
    
    def __init__(self, config: Config, client: Optional[Client] = None):
        """Initialize DataManager.
        
        Args:
            config: Configuration object
            client: Binance API client (optional, created if not provided)
        """
        self.config = config
        self.client = client
        
        # Circular buffers for candle data (max 500 candles each)
        self.candles_15m: deque = deque(maxlen=500)
        self.candles_1h: deque = deque(maxlen=500)
        
        # WebSocket manager
        self.websocket_manager: Optional[ThreadedWebsocketManager] = None
        self._ws_connected = False
        self._ws_reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_lock = threading.Lock()
        
        # WebSocket stream keys
        self._stream_keys = {
            '15m': None,
            '1h': None
        }
        
        # Callback for candle updates (can be set externally)
        self.on_candle_callback: Optional[Callable[[Candle, str], None]] = None
    
    def fetch_historical_data(self, days: int = 90, timeframe: str = "15m") -> List[Candle]:
        """Fetch historical kline data from Binance.
        
        Args:
            days: Number of days of historical data to fetch
            timeframe: Timeframe for candles (e.g., "15m", "1h")
            
        Returns:
            List of Candle objects sorted by timestamp
            
        Raises:
            ValueError: If data contains gaps or is incomplete
            BinanceAPIException: If API request fails
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot fetch historical data.")
        
        # Calculate start time
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Convert to milliseconds
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        # Fetch klines from Binance
        try:
            klines = self.client.get_historical_klines(
                symbol=self.config.symbol,
                interval=self._convert_timeframe_to_binance_interval(timeframe),
                start_str=start_ms,
                end_str=end_ms
            )
        except BinanceAPIException as e:
            raise BinanceAPIException(f"Failed to fetch historical data: {e}")
        
        # Convert to Candle objects
        candles = []
        for kline in klines:
            candle = Candle(
                timestamp=int(kline[0]),
                open=float(kline[1]),
                high=float(kline[2]),
                low=float(kline[3]),
                close=float(kline[4]),
                volume=float(kline[5])
            )
            candles.append(candle)
        
        # Validate data completeness
        self._validate_data_completeness(candles, timeframe)
        
        # Store in appropriate buffer
        if timeframe == "15m":
            self.candles_15m.extend(candles)
        elif timeframe == "1h":
            self.candles_1h.extend(candles)
        
        return candles
    
    def _convert_timeframe_to_binance_interval(self, timeframe: str) -> str:
        """Convert timeframe string to Binance interval constant.
        
        Args:
            timeframe: Timeframe string (e.g., "15m", "1h")
            
        Returns:
            Binance interval constant (e.g., Client.KLINE_INTERVAL_15MINUTE)
        """
        interval_map = {
            "1m": Client.KLINE_INTERVAL_1MINUTE,
            "3m": Client.KLINE_INTERVAL_3MINUTE,
            "5m": Client.KLINE_INTERVAL_5MINUTE,
            "15m": Client.KLINE_INTERVAL_15MINUTE,
            "30m": Client.KLINE_INTERVAL_30MINUTE,
            "1h": Client.KLINE_INTERVAL_1HOUR,
            "2h": Client.KLINE_INTERVAL_2HOUR,
            "4h": Client.KLINE_INTERVAL_4HOUR,
            "6h": Client.KLINE_INTERVAL_6HOUR,
            "8h": Client.KLINE_INTERVAL_8HOUR,
            "12h": Client.KLINE_INTERVAL_12HOUR,
            "1d": Client.KLINE_INTERVAL_1DAY,
        }
        
        if timeframe not in interval_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        return interval_map[timeframe]
    
    def _get_timeframe_milliseconds(self, timeframe: str) -> int:
        """Get the duration of a timeframe in milliseconds.
        
        Args:
            timeframe: Timeframe string (e.g., "15m", "1h")
            
        Returns:
            Duration in milliseconds
        """
        timeframe_ms = {
            "1m": 60 * 1000,
            "3m": 3 * 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
            "30m": 30 * 60 * 1000,
            "1h": 60 * 60 * 1000,
            "2h": 2 * 60 * 60 * 1000,
            "4h": 4 * 60 * 60 * 1000,
            "6h": 6 * 60 * 60 * 1000,
            "8h": 8 * 60 * 60 * 1000,
            "12h": 12 * 60 * 60 * 1000,
            "1d": 24 * 60 * 60 * 1000,
        }
        
        if timeframe not in timeframe_ms:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        return timeframe_ms[timeframe]
    
    def _validate_data_completeness(self, candles: List[Candle], timeframe: str) -> None:
        """Validate that candle data contains no gaps.
        
        Args:
            candles: List of Candle objects to validate
            timeframe: Expected timeframe between candles
            
        Raises:
            ValueError: If data contains gaps larger than the timeframe interval
        """
        if len(candles) < 2:
            return  # Not enough data to validate gaps
        
        expected_interval_ms = self._get_timeframe_milliseconds(timeframe)
        
        # Allow 10% tolerance for timing variations
        max_allowed_gap = expected_interval_ms * 1.1
        
        gaps = []
        for i in range(1, len(candles)):
            time_diff = candles[i].timestamp - candles[i-1].timestamp
            
            if time_diff > max_allowed_gap:
                gaps.append({
                    'index': i,
                    'prev_timestamp': candles[i-1].timestamp,
                    'curr_timestamp': candles[i].timestamp,
                    'gap_ms': time_diff,
                    'expected_ms': expected_interval_ms
                })
        
        if gaps:
            gap_details = "\n".join([
                f"  Gap at index {g['index']}: {g['gap_ms']}ms "
                f"(expected {g['expected_ms']}ms) between "
                f"{datetime.fromtimestamp(g['prev_timestamp']/1000)} and "
                f"{datetime.fromtimestamp(g['curr_timestamp']/1000)}"
                for g in gaps[:5]  # Show first 5 gaps
            ])
            
            raise ValueError(
                f"Historical data contains {len(gaps)} gap(s) larger than "
                f"the {timeframe} interval:\n{gap_details}"
            )
    
    def get_latest_candles(self, timeframe: str, count: int) -> List[Candle]:
        """Retrieve most recent candles for indicator calculation.
        
        Args:
            timeframe: Timeframe to retrieve ("15m" or "1h")
            count: Number of candles to retrieve
            
        Returns:
            List of most recent Candle objects
        """
        if timeframe == "15m":
            buffer = self.candles_15m
        elif timeframe == "1h":
            buffer = self.candles_1h
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        
        # Return last 'count' candles
        if len(buffer) < count:
            return list(buffer)
        else:
            return list(buffer)[-count:]
    
    def start_websocket_streams(self):
        """Initialize WebSocket connections for real-time data.
        
        Establishes WebSocket connections for both 15m and 1h kline streams.
        Automatically handles connection management and reconnection.
        
        Raises:
            ValueError: If Binance client is not initialized
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot start WebSocket streams.")
        
        # Initialize WebSocket manager if not already created
        if self.websocket_manager is None:
            self.websocket_manager = ThreadedWebsocketManager(
                api_key=self.config.api_key,
                api_secret=self.config.api_secret
            )
            self.websocket_manager.start()
            logger.info("WebSocket manager started")
        
        # Start 15m kline stream
        self._stream_keys['15m'] = self.websocket_manager.start_kline_socket(
            callback=lambda msg: self._handle_kline_message(msg, '15m'),
            symbol=self.config.symbol.lower(),
            interval=Client.KLINE_INTERVAL_15MINUTE
        )
        logger.info(f"Started 15m kline stream for {self.config.symbol}")
        
        # Start 1h kline stream
        self._stream_keys['1h'] = self.websocket_manager.start_kline_socket(
            callback=lambda msg: self._handle_kline_message(msg, '1h'),
            symbol=self.config.symbol.lower(),
            interval=Client.KLINE_INTERVAL_1HOUR
        )
        logger.info(f"Started 1h kline stream for {self.config.symbol}")
        
        self._ws_connected = True
        self._ws_reconnect_attempts = 0
    
    def _handle_kline_message(self, msg: dict, timeframe: str):
        """Handle incoming kline WebSocket message.
        
        Args:
            msg: WebSocket message containing kline data
            timeframe: Timeframe of the kline ('15m' or '1h')
        """
        try:
            # Check if message contains error
            if 'e' in msg and msg['e'] == 'error':
                logger.error(f"WebSocket error for {timeframe}: {msg}")
                self._handle_websocket_disconnect()
                return
            
            # Extract kline data
            if 'k' not in msg:
                logger.warning(f"Received message without kline data: {msg}")
                return
            
            kline = msg['k']
            
            # Only process closed candles
            if not kline['x']:
                return
            
            # Create Candle object
            candle = Candle(
                timestamp=int(kline['t']),
                open=float(kline['o']),
                high=float(kline['h']),
                low=float(kline['l']),
                close=float(kline['c']),
                volume=float(kline['v'])
            )
            
            # Update candle buffer
            self.on_candle_update(candle, timeframe)
            
        except Exception as e:
            logger.error(f"Error processing kline message for {timeframe}: {e}")
    
    def _handle_websocket_disconnect(self):
        """Handle WebSocket disconnection event.
        
        Triggers reconnection logic with exponential backoff.
        """
        logger.warning("WebSocket disconnection detected")
        self._ws_connected = False
        self.reconnect_websocket()
    
    def on_candle_update(self, candle: Candle, timeframe: str):
        """Callback for new candle data from WebSocket.
        
        Updates the appropriate candle buffer and calls external callback if set.
        
        Args:
            candle: New candle data
            timeframe: Timeframe of the candle ('15m' or '1h')
        """
        # Add to appropriate buffer
        if timeframe == '15m':
            self.candles_15m.append(candle)
            logger.debug(f"Added 15m candle: timestamp={candle.timestamp}, close={candle.close}")
        elif timeframe == '1h':
            self.candles_1h.append(candle)
            logger.debug(f"Added 1h candle: timestamp={candle.timestamp}, close={candle.close}")
        else:
            logger.warning(f"Unknown timeframe: {timeframe}")
            return
        
        # Call external callback if set
        if self.on_candle_callback is not None:
            try:
                self.on_candle_callback(candle, timeframe)
            except Exception as e:
                logger.error(f"Error in candle callback: {e}")
    
    def reconnect_websocket(self):
        """Handle WebSocket reconnection with exponential backoff.
        
        Attempts to reconnect up to 5 times with exponentially increasing delays.
        Uses thread lock to prevent multiple simultaneous reconnection attempts.
        
        Returns:
            bool: True if reconnection successful, False otherwise
        """
        with self._reconnect_lock:
            # Check if already connected
            if self._ws_connected:
                logger.info("WebSocket already connected, skipping reconnection")
                return True
            
            # Check if max attempts reached
            if self._ws_reconnect_attempts >= self._max_reconnect_attempts:
                logger.error(f"Max reconnection attempts ({self._max_reconnect_attempts}) reached. Giving up.")
                return False
            
            self._ws_reconnect_attempts += 1
            
            # Calculate exponential backoff delay: 2^(attempt-1) seconds
            # Attempt 1: 1s, Attempt 2: 2s, Attempt 3: 4s, Attempt 4: 8s, Attempt 5: 16s
            delay = 2 ** (self._ws_reconnect_attempts - 1)
            
            logger.info(
                f"Reconnection attempt {self._ws_reconnect_attempts}/{self._max_reconnect_attempts} "
                f"after {delay}s delay"
            )
            
            # Wait with exponential backoff
            time.sleep(delay)
            
            try:
                # Stop existing WebSocket manager if it exists
                if self.websocket_manager is not None:
                    try:
                        self.websocket_manager.stop()
                        logger.info("Stopped existing WebSocket manager")
                    except Exception as e:
                        logger.warning(f"Error stopping WebSocket manager: {e}")
                    
                    self.websocket_manager = None
                
                # Restart WebSocket streams
                self.start_websocket_streams()
                
                logger.info("WebSocket reconnection successful")
                return True
                
            except Exception as e:
                logger.error(f"Reconnection attempt {self._ws_reconnect_attempts} failed: {e}")
                
                # If not at max attempts, try again
                if self._ws_reconnect_attempts < self._max_reconnect_attempts:
                    return self.reconnect_websocket()
                else:
                    return False
    
    def stop_websocket_streams(self):
        """Stop WebSocket streams and clean up resources.
        
        Should be called during graceful shutdown.
        """
        if self.websocket_manager is not None:
            try:
                self.websocket_manager.stop()
                logger.info("WebSocket streams stopped")
            except Exception as e:
                logger.error(f"Error stopping WebSocket streams: {e}")
            finally:
                self.websocket_manager = None
                self._ws_connected = False
    
    def is_websocket_connected(self) -> bool:
        """Check if WebSocket is currently connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self._ws_connected
    
    def get_reconnect_attempts(self) -> int:
        """Get the current number of reconnection attempts.
        
        Returns:
            int: Number of reconnection attempts made
        """
        return self._ws_reconnect_attempts
