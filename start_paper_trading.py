#!/usr/bin/env python3
"""
Start Paper Trading Script

This script starts the trading bot in PAPER mode.
- Connects to Binance for live data
- Simulates order execution (no real trades)
- Displays real-time dashboard
- Press ESC to panic close all positions

IMPORTANT:
- Make sure your API keys are configured in config/config.json
- The bot will run continuously until you stop it
- Monitor the dashboard and logs regularly
- Start with small position sizes (current: 1% risk per trade)
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.trading_bot import TradingBot
from src.config import Config
from src.logger import get_logger

def main():
    """Start paper trading."""
    print("=" * 70)
    print("BINANCE FUTURES TRADING BOT - PAPER TRADING MODE")
    print("=" * 70)
    print()
    print("⚠️  PAPER TRADING MODE")
    print("   - Uses LIVE market data from Binance")
    print("   - Simulates order execution (NO REAL TRADES)")
    print("   - Tracks performance as if trading live")
    print()
    print("📊 Configuration:")
    
    try:
        # Load configuration from file
        config = Config.load_from_file("config/config.json")
        
        print(f"   - Symbol: {config.symbol}")
        print(f"   - Risk per trade: {config.risk_per_trade * 100}%")
        print(f"   - Leverage: {config.leverage}x")
        print(f"   - Entry timeframe: {config.timeframe_entry}")
        print(f"   - Filter timeframe: {config.timeframe_filter}")
        print()
        
        # Verify mode
        if config.run_mode != "PAPER":
            print(f"❌ ERROR: run_mode is set to '{config.run_mode}'")
            print("   Please set run_mode to 'PAPER' in config/config.json")
            return 1
        
        # Verify API keys
        if not config.api_key or not config.api_secret:
            print("❌ ERROR: API keys not configured")
            print("   Please add your Binance API keys to config/config.json")
            print()
            print("   Get API keys from:")
            print("   - Testnet: https://testnet.binancefuture.com/")
            print("   - Mainnet: https://www.binance.com/")
            return 1
        
        print("✅ Configuration validated")
        print()
        print("🚀 Starting paper trading...")
        print()
        print("Controls:")
        print("   - Press ESC to panic close all positions and stop")
        print("   - Monitor logs in logs/ directory")
        print("   - Dashboard updates in real-time")
        print()
        print("=" * 70)
        print()
        
        # Initialize logger
        logger = get_logger()
        logger.log_system_event("Starting paper trading mode", "INFO")
        
        # Create and run trading bot
        bot = TradingBot(config)
        bot.start()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user (Ctrl+C)")
        print("Shutting down gracefully...")
        return 0
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
