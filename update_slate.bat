@echo off
title CBB Slate Downloader
cls

echo ===========================================
echo    CBB DAILY SLATE MANAGER
echo ===========================================
echo.
echo [0] Today
echo [1] Tomorrow
echo [2] Two Days Out
echo.
set /p days="Enter day offset (0, 1, or 2): "

echo.
echo 📡 Running Scraper...
python "C:\Users\Brody\Desktop\cbb-sharp-data\get_slate.py" %days%

echo.
echo 🚀 Pushing to GitHub...
git add active_slate.csv
git commit -m "Update slate for offset %days%"
git push

echo.
echo ===========================================
echo ✅ Task Complete! active_slate.csv is Live.
echo ===========================================
pause