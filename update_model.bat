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

:: Make sure we're up to date first (prevents non-fast-forward push errors)
git pull --rebase origin main
if errorlevel 1 (
  echo ❌ git pull --rebase failed. Resolve git issues then rerun.
  exit /b 1
)

:: Add only files that exist (prevents pathspec failures)
if exist active_slate.csv git add active_slate.csv
if exist kenpom_live.csv git add kenpom_live.csv
if exist vegas_odds.csv git add vegas_odds.csv
if exist player_stats.csv git add player_stats.csv
if exist .gitattributes git add .gitattributes

:: If nothing changed, don't try to commit/push
git diff --cached --quiet
if %errorlevel%==0 (
  echo ✅ No CSV changes to commit. GitHub already has latest.
  goto :eof
)

:: Commit with a clean timestamp (no colons)
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set d=%%c-%%a-%%b
for /f "tokens=1-2 delims=:." %%a in ("%time%") do set t=%%a%%b

git commit -m "Daily CSV Update: %d% %t%"
if errorlevel 1 (
  echo ❌ git commit failed.
  exit /b 1
)

git push origin main
if errorlevel 1 (
  echo ❌ git push failed.
  exit /b 1
)

echo 🚀 CSVs pushed successfully.

echo.
echo ✅ ALL CSVs ARE LIVE!
echo You can now tell the GPT to "Run the Audit."
pause