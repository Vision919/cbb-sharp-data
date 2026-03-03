@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\Brody\Desktop\cbb-sharp-data"

title CBB Data Master Sync (NO SLATE)
color 0A

echo ===========================================================
echo        COLLEGE BASKETBALL DATA MASTER SYNC (AUTO)
echo              (VEGAS = SLATE, TR STATS)
echo ===========================================================
echo.

:: ------------------------------------------------------------
:: [0/4] Git sync FIRST (so pull/rebase never fails after writes)
:: ------------------------------------------------------------
echo [0/4] 🔄 Syncing with GitHub (pull first)...

set DIRTY=0
git diff --quiet
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
:: [1/4] KenPom
:: -------------------------
echo [1/4] 📈 Updating KenPom...
call :runpy scraper.py "KenPom scrape"

:: -------------------------
:: [2/4] TeamRankings enrich (pace / 3P / turnover etc.)
:: -------------------------
echo [2/4] 📊 Updating TeamRankings stats...
if exist teamrankings_pull.py (
  call :runpy teamrankings_pull.py "TeamRankings pull"
) else (
  echo ⚠️ teamrankings_pull.py not found — skipping TR stats.
)

:: -------------------------
:: [3/4] Vegas
:: -------------------------
echo [3/4] 🎰 Fetching Live Vegas Odds...
call :runpy vegas_odds.py "Vegas Odds"

:: -------------------------
:: [4/4] Commit + Push
:: -------------------------
echo.
echo [4/4] 🚀 Committing + pushing changes...

if exist kenpom_live.csv git add kenpom_live.csv
if exist vegas_odds.csv git add vegas_odds.csv
if exist player_stats.csv git add player_stats.csv

:: If your TeamRankings script writes a CSV, add it here (common names)
if exist teamrankings_stats.csv git add teamrankings_stats.csv
if exist teamrankings_live.csv git add teamrankings_live.csv

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
exit /b 0

:: ------------------------------------------------------------
:: Helpers
:: ------------------------------------------------------------
:runpy
set SCRIPT=%~1
set LABEL=%~2

:: Use 'py' launcher if available (Windows default); fall back to python
where py >nul 2>&1
if %errorlevel%==0 (
  py "%SCRIPT%"
) else (
  python "%SCRIPT%"
)

if %errorlevel% neq 0 (
  echo ❌ %LABEL% failed.
  pause
  exit /b 1
)

echo ✅ %LABEL% complete.
echo.
goto :eof
BAT
