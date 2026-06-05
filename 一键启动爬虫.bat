@echo off
chcp 65001 >nul
echo Starting Telegram Groups Crawler...
echo.

python scraper_upgraded.py

echo.
echo ========================================
echo Crawler finished running!
echo ========================================
pause
