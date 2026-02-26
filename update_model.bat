@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\Brody\Desktop\cbb-sharp-data"

title CBB Data Master Sync (NO SLATE)
color 0A

echo ===========================================================
echo        COLLEGE BASKETBALL DATA MASTER SYNC (AUTO)
echo                 (VEGAS = SLATE)
echo ===========================================================
echo.

:: ------------------------------------------------------------
:: [0/3] Git sync FIRST (so pull/rebase never fails after writes)
:: ------------------------------------------------------------
echo [0/3] 🔄 Syncing with GitHub (pull first)...

git diff --quiet
set DIRTY=0
if errorlevel 1 set DIRTY=1

git diff --cached --quiet
if errorlevel 1 set DIRTY=1

if "!DIRTY!"=="1" (
  echo 🧷 Working tree dirty — stashing changes...
  git stash push -u -m "auto-stash before daily sync"
)

git pull --rebase origin main
if errorlevel 1 (
  echo ❌ git pull --rebase failed. Resolve manually.
  pause
  exit /b 1
)

if "!DIRTY!"=="1" (
  echo 🧷 Restoring stashed changes...
  git stash pop
)

echo ✅ Git sync complete.
echo.

:: -------------------------
:: [1/3] KenPom (and Players if your scraper writes them)
:: -------------------------
echo [1/3] 📈 Updating KenPom...
python scraper.py
if %errorlevel% neq 0 (
  echo ❌ KenPom scrape failed.
  pause
  exit /b 1
)

:: -------------------------
:: [2/3] Vegas
:: -------------------------
echo [2/3] 🎰 Fetching Live Vegas Odds...
python vegas_odds.py
if %errorlevel% neq 0 (
  echo ❌ Vegas Odds failed.
  pause
  exit /b 1
)

:: -------------------------
:: [3/3] Commit + Push
:: -------------------------
echo.
echo [3/3] 🚀 Committing + pushing changes...

if exist kenpom_live.csv git add kenpom_live.csv
if exist vegas_odds.csv git add vegas_odds.csv
if exist player_stats.csv git add player_stats.csv

git diff --cached --quiet
if %errorlevel%==0 (
  echo ✅ No changes detected. Nothing to push.
  goto :done
)

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set d=%%c-%%a-%%b
for /f "tokens=1-2 delims=:." %%a in ("%time%") do set t=%%a%%b

git commit -m "Daily Data Update: %d% %t%"
git push origin main

:done
echo.
echo ✅ DATA SYNC COMPLETE
echo Vegas acts as the slate (filter by Commence_Time).
pause