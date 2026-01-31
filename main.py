#!/usr/bin/env python3
"""Main entry point for Binance Futures Trading Bot.

This script loads configuration and starts the trading bot in the configured mode.

Usage:
    python main.py

Configuration is loaded from config/config.json and environment variables.
See config/config.template.json for available options.
"""

from src.trading_bot import main

if __name__ == "__main__":
    main()
