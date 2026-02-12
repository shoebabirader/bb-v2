# EC2 Deployment Guide - Trading Bot

## ✅ DEPLOYMENT COMPLETED!

Your trading bot has been successfully deployed to AWS EC2!

### EC2 Instance Details
- **Instance Type**: t3.micro
- **OS**: Ubuntu 24.04 (Noble)
- **Public IP**: 3.80.58.47
- **Public DNS**: ec2-3-80-58-47.compute-1.amazonaws.com
- **PEM Key**: BB.pem

### What's Been Installed
✅ System packages updated
✅ Python 3.12 with pip and venv
✅ Git, screen, build tools
✅ Repository cloned from GitHub
✅ Python virtual environment created
✅ All dependencies installed (pandas, numpy, python-binance, etc.)
✅ Config file uploaded
✅ Startup script created

---

## 🚀 HOW TO START THE BOT

### Option 1: Quick Test (Foreground)
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
source venv/bin/activate
python main.py
```
Press `Ctrl+C` to stop

### Option 2: Run in Background with Screen (RECOMMENDED)
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
screen -S trading-bot
source venv/bin/activate
python main.py
```

**To detach from screen** (leave bot running):
- Press `Ctrl+A` then `D`

**To reattach to screen** (view bot again):
```bash
ssh -i BB.pem ubuntu@3.80.58.47
screen -r trading-bot
```

**To stop the bot**:
- Reattach to screen: `screen -r trading-bot`
- Press `Ctrl+C`
- Exit screen: `exit`

### Option 3: Using the Startup Script
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
./ec2_start_bot.sh
```

---

## 📊 MONITORING THE BOT

### Check if bot is running
```bash
ssh -i BB.pem ubuntu@3.80.58.47 "ps aux | grep python"
```

### View live logs
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
tail -f logs/bot.log
```

### Check recent trades
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
tail -n 50 logs/bot.log | grep "Position opened"
```

### List all screen sessions
```bash
ssh -i BB.pem ubuntu@3.80.58.47
screen -ls
```

---

## 🔄 UPDATING THE BOT

### Pull latest code from GitHub
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
git pull origin main
```

### Update config file
```bash
# From your local machine (E:\bb)
scp -i BB.pem config/config.json ubuntu@3.80.58.47:~/bb-v2/config/
```

### Restart the bot after updates
1. Stop the bot (Ctrl+C or kill the screen session)
2. Start it again using one of the methods above

---

## ⚙️ CONFIGURATION

### Current Settings
- **Mode**: PAPER (simulated trading)
- **Balance**: $15.07 USDT
- **Risk per trade**: 3.2%
- **Leverage**: 5x
- **Symbols**: RIVERUSDT, HYPEUSDT, DOGEUSDT, XRPUSDT, ADAUSDT

### Switch to LIVE Trading
⚠️ **WARNING**: Only do this when you're ready for real trading!

1. Edit config on EC2:
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
nano config/config.json
```

2. Change `"run_mode": "PAPER"` to `"run_mode": "LIVE"`

3. Save (Ctrl+O, Enter) and exit (Ctrl+X)

4. Restart the bot

---

## 🛠️ TROUBLESHOOTING

### Bot not starting?
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
source venv/bin/activate
python main.py
# Check error messages
```

### Check API connection
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
source venv/bin/activate
python test_api_connection.py
```

### View full log file
```bash
ssh -i BB.pem ubuntu@3.80.58.47
cd bb-v2
less logs/bot.log
# Press 'q' to exit
```

### Kill stuck bot process
```bash
ssh -i BB.pem ubuntu@3.80.58.47
pkill -f "python main.py"
```

---

## 💾 BACKUP AND LOGS

### Download logs to local machine
```bash
# From your local machine (E:\bb)
scp -i BB.pem ubuntu@3.80.58.47:~/bb-v2/logs/bot.log ./logs/ec2_bot.log
scp -i BB.pem ubuntu@3.80.58.47:~/bb-v2/logs/trades.log ./logs/ec2_trades.log
```

### Download results
```bash
scp -i BB.pem ubuntu@3.80.58.47:~/bb-v2/binance_results.json ./ec2_results.json
```

---

## 🔐 SECURITY NOTES

1. **Never commit API keys to GitHub** - They're in .gitignore
2. **Keep BB.pem secure** - Don't share or commit it
3. **Monitor your trades** - Check regularly when in LIVE mode
4. **Set stop losses** - Already configured in config.json
5. **Start with PAPER mode** - Test thoroughly before going LIVE

---

## 📈 NEXT STEPS

1. ✅ Bot is deployed and ready
2. ⏭️ Test in PAPER mode for 24-48 hours
3. ⏭️ Monitor performance and adjust settings
4. ⏭️ When confident, switch to LIVE mode
5. ⏭️ Set up monitoring alerts (optional)

---

## 🆘 QUICK COMMANDS REFERENCE

```bash
# Connect to EC2
ssh -i BB.pem ubuntu@3.80.58.47

# Start bot in background
screen -S trading-bot
cd bb-v2 && source venv/bin/activate && python main.py
# Ctrl+A then D to detach

# Check bot status
screen -r trading-bot

# View logs
tail -f ~/bb-v2/logs/bot.log

# Stop bot
screen -r trading-bot
# Ctrl+C
# exit

# Update code
cd bb-v2 && git pull origin main

# Upload new config
# (from local machine)
scp -i BB.pem config/config.json ubuntu@3.80.58.47:~/bb-v2/config/
```

---

## 📞 SUPPORT

If you encounter issues:
1. Check logs: `tail -f ~/bb-v2/logs/bot.log`
2. Verify API keys are correct in config.json
3. Ensure sufficient balance in Binance account
4. Check internet connection on EC2

---

**Deployment Date**: February 12, 2026
**Status**: ✅ READY TO RUN
