@echo off
chcp 65001 >nul
echo Checking logged in Telegram account...
echo.

python check_account.py

echo.
pause
