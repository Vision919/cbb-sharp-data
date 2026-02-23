@echo off
:: Forces the script to run in your project folder regardless of how it's opened
cd /d "C:\Users\Brody\Desktop\cbb-sharp-data"
title CBB Data Master Sync
color 0A

echo ===========================================================
echo             COLLEGE BASKETBALL DATA MASTER SYNC
echo ===========================================================
echo.

:: 1. Update Team Efficiency and Player Stats
echo [1/5] 📈 Scraping KenPom and Player Stats...
python scraper.py
if %errorlevel% neq 0 (echo ❌ Scraper failed! && pause && exit /b)

:: 2. Update Vegas Odds
echo [2/5] 🎰 Fetching Live Vegas Odds...
python vegas_odds.py
if %errorlevel% neq 0 (echo ❌ Vegas Odds failed!)

:: 3. Update the Slate (Asks you which day)
echo.
echo [3/5] 📅 Update Schedule Slate:
echo [0] Today
echo [1] Tomorrow
echo [2] Day After
set /p days="Choose day (0-2): "
python get_slate.py %days%

:: 4. Build the JSON Master Payload
echo.
echo [4/5] 📦 Packing everything into master_data.json...
python build_master.py

:: 5. Push to GitHub
echo.
echo [5/5] 🚀 Syncing with GitHub...
git add .
git commit -m "Full Intelligence Update: %date% %time%"
git push

echo.
echo ===========================================================
echo ✅ ALL SYSTEMS SYNCED! 
echo Give Claude the Master Link:
echo https://raw.githubusercontent.com/Vision919/cbb-sharp-data/main/master_data.json
echo ===========================================================
echo.
exit