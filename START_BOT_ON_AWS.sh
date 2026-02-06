#!/bin/bash
# Script to start the Polymarket Arbitrage Bot on AWS
# Run this script on your LOCAL machine (Windows/Mac/Linux)

echo "=========================================="
echo "Polymarket Arbitrage Bot - AWS Deployment"
echo "=========================================="
echo ""

# Check if money.pem exists
if [ ! -f "money.pem" ]; then
    echo "❌ ERROR: money.pem not found!"
    echo "Please make sure money.pem is in the current directory"
    exit 1
fi

# Set correct permissions for PEM file
chmod 400 money.pem

echo "✅ PEM file permissions set"
echo ""
echo "Connecting to AWS server..."
echo ""

# SSH to AWS and run the bot
ssh -i "money.pem" ubuntu@18.207.221.6 << 'ENDSSH'
    echo "=========================================="
    echo "Connected to AWS Server"
    echo "=========================================="
    echo ""
    
    # Navigate to bot directory
    cd ~/polybot || { echo "❌ ERROR: polybot directory not found!"; exit 1; }
    echo "✅ In polybot directory"
    
    # Check if .env exists
    if [ ! -f ".env" ]; then
        echo "❌ ERROR: .env file not found!"
        echo "Please create .env file with your configuration"
        exit 1
    fi
    echo "✅ .env file found"
    
    # Check if virtual environment exists
    if [ ! -d "venv" ]; then
        echo "❌ ERROR: Virtual environment not found!"
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    echo "✅ Virtual environment ready"
    
    # Activate virtual environment
    source venv/bin/activate
    echo "✅ Virtual environment activated"
    
    # Install/update dependencies
    echo ""
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
    echo "✅ Dependencies installed"
    
    # Check DRY_RUN setting
    echo ""
    echo "=========================================="
    echo "Configuration Check"
    echo "=========================================="
    DRY_RUN=$(grep "^DRY_RUN=" .env | cut -d'=' -f2)
    echo "DRY_RUN mode: $DRY_RUN"
    
    if [ "$DRY_RUN" = "true" ]; then
        echo "✅ SAFE MODE: No real transactions will occur"
    else
        echo "⚠️  LIVE MODE: Real transactions will occur!"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo "Aborted by user"
            exit 0
        fi
    fi
    
    echo ""
    echo "=========================================="
    echo "Starting Polymarket Arbitrage Bot"
    echo "=========================================="
    echo ""
    echo "Press Ctrl+C to stop the bot"
    echo ""
    
    # Run the bot
    ./run_bot.sh
ENDSSH

echo ""
echo "=========================================="
echo "Bot stopped or connection closed"
echo "=========================================="
