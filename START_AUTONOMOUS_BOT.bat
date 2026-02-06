@echo off
REM Windows batch file to start the fully autonomous Polymarket bot
REM This bot handles everything automatically including cross-chain bridging

echo ================================================================================
echo FULLY AUTONOMOUS POLYMARKET ARBITRAGE BOT
echo ================================================================================
echo.
echo This bot will:
echo   - Check for USDC on Ethereum and Polygon
echo   - Automatically bridge from Ethereum to Polygon if needed
echo   - Start trading autonomously 24/7
echo   - Manage funds automatically
echo   - Execute trades without human intervention
echo.
echo ================================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo ERROR: .env file not found
    echo Please create .env file with your configuration
    echo See .env.example for template
    pause
    exit /b 1
)

REM Run the autonomous bot
echo Starting autonomous bot...
echo.
python test_autonomous_bot.py

REM If bot exits, show message
echo.
echo ================================================================================
echo Bot stopped
echo ================================================================================
pause
