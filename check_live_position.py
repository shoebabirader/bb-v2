"""Check the actual live position details."""

import json
from pathlib import Path

# Try to find any recent position data
print("Checking for position data...")

# Check if there's a state file or recent trade log
trades_log = Path("logs/trades.log")
if trades_log.exists():
    with open(trades_log, 'r') as f:
        lines = f.readlines()
        if lines:
            last_line = lines[-1]
            print(f"\nLast trade log entry:")
            print(last_line)
            
            # Try to parse it
            if "TRADE_EXECUTED" in last_line:
                try:
                    json_start = last_line.index('{')
                    json_str = last_line[json_start:]
                    trade_data = json.loads(json_str)
                    print(f"\nParsed trade data:")
                    print(f"  Side: {trade_data.get('side')}")
                    print(f"  Entry: ${trade_data.get('entry_price')}")
                    print(f"  Exit: ${trade_data.get('exit_price')}")
                    print(f"  PnL: ${trade_data.get('pnl')}")
                except:
                    print("Could not parse trade data")

print("\n" + "="*50)
print("CURRENT MARKET PRICE: $1.6124")
print("="*50)
print("\nIf your bot shows a SHORT position at ~$1.62:")
print("  Expected PnL: POSITIVE (price went down)")
print("  Profit per unit: ~$0.0076")
print("\nIf PnL shows $0.00, the WebSocket might not be updating.")
print("Try restarting the bot to refresh the connection.")
