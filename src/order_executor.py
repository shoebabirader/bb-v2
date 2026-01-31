"""Order execution and Binance API integration for Binance Futures Trading Bot."""

import time
import logging
from typing import Optional, Dict, Any
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from src.config import Config


logger = logging.getLogger(__name__)


class OrderExecutor:
    """Handles order execution and Binance API interactions.
    
    Manages leverage configuration, margin type, order placement with retry logic,
    and account balance queries. Implements exponential backoff for failed requests.
    """
    
    def __init__(self, config: Config, client: Optional[Client] = None):
        """Initialize OrderExecutor with configuration and Binance client.
        
        Args:
            config: Configuration object with trading parameters
            client: Optional Binance client (if None, creates new client)
        """
        self.config = config
        
        # Create Binance client if not provided
        if client is None:
            if config.api_key and config.api_secret:
                # Enforce HTTPS protocol
                self.client = Client(config.api_key, config.api_secret)
                # Verify the API URL uses HTTPS
                if hasattr(self.client, 'API_URL') and not self.client.API_URL.startswith('https://'):
                    raise ValueError("API URL must use HTTPS protocol for security")
            else:
                # For backtest mode, client is not needed
                self.client = None
        else:
            self.client = client
            # Verify the API URL uses HTTPS for provided client
            if hasattr(self.client, 'API_URL') and not self.client.API_URL.startswith('https://'):
                raise ValueError("API URL must use HTTPS protocol for security")
        
        self.max_retries = 3
        self.base_backoff = 1.0  # seconds
        self._authenticated = False
        self._permissions_validated = False
    
    def validate_authentication(self) -> bool:
        """Validate API authentication at startup.
        
        Returns:
            True if authentication is valid, False otherwise
            
        Raises:
            ValueError: If client is not initialized
            BinanceAPIException: If authentication fails
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot validate authentication in BACKTEST mode.")
        
        try:
            # Test authentication by fetching account info
            logger.info("Validating API authentication...")
            account_info = self.client.futures_account()
            
            if account_info and 'assets' in account_info:
                self._authenticated = True
                logger.info("API authentication successful")
                return True
            else:
                logger.error("API authentication failed: Invalid response")
                return False
                
        except BinanceAPIException as e:
            logger.error(f"API authentication failed: {e}")
            if e.code in [-2014, -2015]:  # API key errors
                raise ValueError(
                    f"API authentication failed: {e.message}. "
                    "Please check your API key and secret."
                )
            raise
    
    def validate_permissions(self) -> bool:
        """Validate API key has required permissions for trading.
        
        Returns:
            True if permissions are valid, False otherwise
            
        Raises:
            ValueError: If client is not initialized or authentication not validated
            BinanceAPIException: If permission check fails
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot validate permissions in BACKTEST mode.")
        
        if not self._authenticated:
            raise ValueError("Must validate authentication before checking permissions")
        
        try:
            logger.info("Validating API permissions...")
            
            # Check if API key has futures trading permissions
            # Try to get account info (requires read permission)
            account_info = self.client.futures_account()
            
            # Try to get current open orders (requires read permission)
            open_orders = self.client.futures_get_open_orders()
            
            # For LIVE mode, we need trading permissions
            # We can't test this without actually placing an order,
            # so we check the API key restrictions
            api_key_permissions = self.client.get_account_api_permissions()
            
            # Check if futures trading is enabled
            if 'enableFutures' in api_key_permissions:
                if not api_key_permissions['enableFutures']:
                    logger.error("API key does not have futures trading enabled")
                    raise ValueError(
                        "API key does not have futures trading enabled. "
                        "Please enable futures trading for this API key."
                    )
            
            # Check if trading is enabled (not just read-only)
            if 'enableSpotAndMarginTrading' in api_key_permissions or 'enableFutures' in api_key_permissions:
                self._permissions_validated = True
                logger.info("API permissions validated successfully")
                return True
            else:
                logger.error("API key permissions insufficient for trading")
                return False
                
        except BinanceAPIException as e:
            logger.error(f"API permission validation failed: {e}")
            if e.code == -2015:  # Invalid API key
                raise ValueError(
                    "Invalid API key. Please check your API credentials."
                )
            raise
    
    def ensure_authenticated(self) -> None:
        """Ensure API is authenticated before trading operations.
        
        Raises:
            ValueError: If not authenticated
        """
        if self.client is not None and not self._authenticated:
            raise ValueError(
                "API not authenticated. Call validate_authentication() first."
            )
    
    def ensure_permissions_validated(self) -> None:
        """Ensure API permissions are validated before trading operations.
        
        Raises:
            ValueError: If permissions not validated
        """
        if self.client is not None and not self._permissions_validated:
            raise ValueError(
                "API permissions not validated. Call validate_permissions() first."
            )
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for the trading pair.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            leverage: Leverage multiplier (1-125)
            
        Returns:
            Response from Binance API
            
        Raises:
            BinanceAPIException: If API request fails
            ValueError: If client is not initialized
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot set leverage in BACKTEST mode.")
        
        # Ensure authenticated before making API calls
        self.ensure_authenticated()
        
        logger.info(f"Setting leverage to {leverage}x for {symbol}")
        
        try:
            response = self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
            logger.info(f"Leverage set successfully: {response}")
            return response
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage: {e}")
            raise
    
    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> Dict[str, Any]:
        """Set margin type for the trading pair.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            margin_type: Margin type ("ISOLATED" or "CROSSED")
            
        Returns:
            Response from Binance API
            
        Raises:
            BinanceAPIException: If API request fails
            ValueError: If client is not initialized or invalid margin type
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot set margin type in BACKTEST mode.")
        
        # Ensure authenticated before making API calls
        self.ensure_authenticated()
        
        if margin_type not in ["ISOLATED", "CROSSED"]:
            raise ValueError(f"Invalid margin type '{margin_type}'. Must be 'ISOLATED' or 'CROSSED'")
        
        logger.info(f"Setting margin type to {margin_type} for {symbol}")
        
        try:
            response = self.client.futures_change_margin_type(
                symbol=symbol,
                marginType=margin_type
            )
            logger.info(f"Margin type set successfully: {response}")
            return response
        except BinanceAPIException as e:
            # If margin type is already set, Binance returns error code -4046
            if e.code == -4046:
                logger.info(f"Margin type already set to {margin_type} for {symbol}")
                return {"code": -4046, "msg": "No need to change margin type."}
            else:
                logger.error(f"Failed to set margin type: {e}")
                raise
    
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """Place market order with retry logic.
        
        Implements exponential backoff retry strategy (3 attempts).
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            side: Order side ("BUY" or "SELL")
            quantity: Order quantity in base currency
            reduce_only: If True, order can only reduce position
            
        Returns:
            Order response from Binance API
            
        Raises:
            BinanceAPIException: If all retry attempts fail
            ValueError: If client is not initialized or invalid parameters
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot place orders in BACKTEST mode.")
        
        # Ensure authenticated and permissions validated before trading
        self.ensure_authenticated()
        self.ensure_permissions_validated()
        
        if side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid order side '{side}'. Must be 'BUY' or 'SELL'")
        
        if quantity <= 0:
            raise ValueError(f"Invalid quantity {quantity}. Must be positive")
        
        logger.info(f"Placing market {side} order for {quantity} {symbol}")
        
        for attempt in range(self.max_retries):
            try:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type="MARKET",
                    quantity=quantity,
                    reduceOnly=reduce_only
                )
                logger.info(f"Order placed successfully: {order}")
                return order
            
            except (BinanceAPIException, BinanceRequestException) as e:
                logger.warning(f"Order placement attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    # Calculate exponential backoff delay
                    backoff_delay = self.base_backoff * (2 ** attempt)
                    logger.info(f"Retrying in {backoff_delay} seconds...")
                    time.sleep(backoff_delay)
                else:
                    # All retries exhausted
                    logger.error(f"Order placement failed after {self.max_retries} attempts")
                    raise
    
    def place_stop_loss_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float
    ) -> Dict[str, Any]:
        """Place stop-loss order for position management.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            side: Order side ("BUY" for short positions, "SELL" for long positions)
            quantity: Order quantity in base currency
            stop_price: Stop trigger price
            
        Returns:
            Order response from Binance API
            
        Raises:
            BinanceAPIException: If API request fails
            ValueError: If client is not initialized or invalid parameters
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot place orders in BACKTEST mode.")
        
        if side not in ["BUY", "SELL"]:
            raise ValueError(f"Invalid order side '{side}'. Must be 'BUY' or 'SELL'")
        
        if quantity <= 0:
            raise ValueError(f"Invalid quantity {quantity}. Must be positive")
        
        if stop_price <= 0:
            raise ValueError(f"Invalid stop price {stop_price}. Must be positive")
        
        logger.info(f"Placing stop-loss {side} order at {stop_price} for {quantity} {symbol}")
        
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",
                stopPrice=stop_price,
                quantity=quantity,
                reduceOnly=True
            )
            logger.info(f"Stop-loss order placed successfully: {order}")
            return order
        
        except BinanceAPIException as e:
            logger.error(f"Failed to place stop-loss order: {e}")
            raise
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel pending order.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            order_id: Order ID to cancel
            
        Returns:
            Cancellation response from Binance API
            
        Raises:
            BinanceAPIException: If API request fails
            ValueError: If client is not initialized
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot cancel orders in BACKTEST mode.")
        
        logger.info(f"Cancelling order {order_id} for {symbol}")
        
        try:
            response = self.client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id
            )
            logger.info(f"Order cancelled successfully: {response}")
            return response
        
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel order: {e}")
            raise
    
    def get_account_balance(self) -> float:
        """Get current USDT balance from futures account.
        
        Returns:
            Available USDT balance
            
        Raises:
            BinanceAPIException: If API request fails
            ValueError: If client is not initialized
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot get balance in BACKTEST mode.")
        
        try:
            account_info = self.client.futures_account()
            
            # Find USDT balance
            for asset in account_info['assets']:
                if asset['asset'] == 'USDT':
                    available_balance = float(asset['availableBalance'])
                    logger.info(f"USDT balance: {available_balance}")
                    return available_balance
            
            # If USDT not found, return 0
            logger.warning("USDT balance not found in account")
            return 0.0
        
        except BinanceAPIException as e:
            logger.error(f"Failed to get account balance: {e}")
            raise
    
    def validate_margin_availability(
        self,
        symbol: str,
        required_margin: float
    ) -> bool:
        """Validate that sufficient margin is available for order.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            required_margin: Required margin for the order
            
        Returns:
            True if sufficient margin available, False otherwise
            
        Raises:
            ValueError: If client is not initialized
        """
        if self.client is None:
            raise ValueError("Binance client not initialized. Cannot validate margin in BACKTEST mode.")
        
        try:
            available_balance = self.get_account_balance()
            
            if available_balance >= required_margin:
                logger.info(f"Sufficient margin available: {available_balance} >= {required_margin}")
                return True
            else:
                logger.warning(
                    f"Insufficient margin: {available_balance} < {required_margin}. "
                    f"Trade rejected."
                )
                return False
        
        except BinanceAPIException as e:
            logger.error(f"Failed to validate margin availability: {e}")
            return False
