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
echo [1/6] 📈 Scraping KenPom and Player Stats...
python scraper.py
if %errorlevel% neq 0 (echo ❌ Scraper failed! && pause && exit /b)

:: 2. Update Vegas Odds
echo [2/6] 🎰 Fetching Live Vegas Odds...
python vegas_odds.py
if %errorlevel% neq 0 (echo ❌ Vegas Odds failed! && pause && exit /b)

:: 3. Update the Slate (Asks you which day)
echo.
echo [3/6] 📅 Update Schedule Slate:
echo [0] Today
echo [1] Tomorrow
echo [2] Day After
set /p days="Choose day (0-2): "
python get_slate.py %days%
if %errorlevel% neq 0 (echo ❌ Slate update failed! && pause && exit /b)

:: 4. Push to GitHub
echo.
echo [5/6] 🚀 Syncing CSVs to GitHub...
git add active_slate.csv kenpom_live.csv vegas_odds.csv player_stats.csv sharp_cbb_live_engine.csv
git commit -m "Daily CSV Update: %date% %time%"
git push

echo.
echo ✅ ALL CSVs ARE LIVE!
echo You can now tell the GPT to "Run the Audit."
pause