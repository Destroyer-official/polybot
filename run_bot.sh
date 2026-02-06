#!/bin/bash
# Simple script to run the Polymarket Arbitrage Bot

# Set PYTHONPATH to include current directory
export PYTHONPATH=$PYTHONPATH:.

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the bot
python3 src/main_orchestrator.py
