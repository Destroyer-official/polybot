@echo off
REM Windows batch file to start the bot in fully autonomous mode

echo ================================================================================
echo POLYMARKET ARBITRAGE BOT - FULLY AUTONOMOUS MODE
echo ================================================================================
echo.
echo Starting bot in fully autonomous mode...
echo The bot will handle everything automatically:
echo   - Detect USDC on any network
echo   - Bridge to Polygon if needed
echo   - Start trading automatically
echo   - Manage funds automatically
echo.
echo Press Ctrl+C to stop the bot
echo ================================================================================
echo.

python START_BOT_AUTONOMOUS.py

pause
