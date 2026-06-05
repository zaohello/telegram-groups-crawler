@echo off
chcp 65001 >nul
echo Cleaning up data files...

del /q crawler_data.json 2>nul
del /q discovered_links.csv 2>nul
del /q resolve_progress.json 2>nul
del /q group_report.md 2>nul
del /q links_browser.html 2>nul
del /q links_for_telegram.txt 2>nul

echo.
echo Cleanup finished! Returned to default state.
pause
