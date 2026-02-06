@echo off
chcp 65001 > nul
echo ================================================================================
echo POLYMARKET ARBITRAGE BOT - STARTING
echo ================================================================================
echo.
echo Checking configuration...
python test_comprehensive.py
echo.
echo ================================================================================
echo Starting bot in DRY RUN mode...
echo Press Ctrl+C to stop
echo ================================================================================
echo.
python src/main_orchestrator.py
