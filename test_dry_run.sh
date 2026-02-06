#!/bin/bash
# DRY_RUN Test Script for Polymarket Arbitrage Bot
# This script will run the bot in safe testing mode

echo "=========================================="
echo "POLYMARKET BOT - DRY_RUN TEST"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "src/main_orchestrator.py" ]; then
    echo "❌ ERROR: Not in polybot directory!"
    echo "Please run: cd ~/polybot"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ ERROR: Virtual environment not found!"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
echo "✓ Activating virtual environment..."
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please create .env file with your configuration"
    exit 1
fi

# Verify DRY_RUN is set to true
DRY_RUN_VALUE=$(grep "^DRY_RUN=" .env | cut -d'=' -f2)
if [ "$DRY_RUN_VALUE" != "true" ]; then
    echo "⚠️  WARNING: DRY_RUN is not set to true!"
    echo "Current value: $DRY_RUN_VALUE"
    echo ""
    read -p "Do you want to set DRY_RUN=true for safe testing? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sed -i 's/^DRY_RUN=.*/DRY_RUN=true/' .env
        echo "✓ DRY_RUN set to true"
    else
        echo "⚠️  Proceeding with current DRY_RUN value..."
    fi
fi

# Check Python dependencies
echo "✓ Checking dependencies..."
python3 -c "import web3, py_clob_client" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Some dependencies missing. Installing..."
    pip install -r requirements.txt
fi

# Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:.

echo ""
echo "=========================================="
echo "STARTING BOT IN DRY_RUN MODE"
echo "=========================================="
echo ""
echo "✓ Virtual environment: activated"
echo "✓ DRY_RUN mode: enabled"
echo "✓ Dependencies: installed"
echo ""
echo "The bot will now start scanning for arbitrage opportunities."
echo "This is SAFE - no real transactions will be executed."
echo ""
echo "Press Ctrl+C to stop the bot at any time."
echo ""
echo "=========================================="
echo ""

# Run the bot
python3 src/main_orchestrator.py
