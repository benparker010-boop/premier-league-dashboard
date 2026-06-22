@echo off
rem ===================================================================
rem  predict.bat  -  one-click World Cup predictor (double-click to run)
rem  Prompts for two team names and prints the prediction card, then
rem  keeps this window open so you can read it.
rem ===================================================================
setlocal
cd /d "%~dp0"

rem --- locate a Python interpreter, most reliable first -------------------
set "PY="
rem 1) the real CPython install (no Microsoft Store shim), any minor version
for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
)
rem 2) the py launcher
if not defined PY ( where py >nul 2>nul && set "PY=py" )
rem 3) plain python on PATH
if not defined PY ( where python >nul 2>nul && set "PY=python" )

if not defined PY (
    echo.
    echo Could not find Python on this PC. Install Python 3.11+ and try again.
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo   World Cup match predictor
echo ============================================================
echo.

rem --- ask for the two teams --------------------------------------------
set "HOME_TEAM="
set "AWAY_TEAM="
set /p "HOME_TEAM=Home / Team A (e.g. France): "
set /p "AWAY_TEAM=Away / Team B (e.g. Iraq): "

if not defined HOME_TEAM goto :listteams
if not defined AWAY_TEAM goto :listteams

rem --- optional extras ---------------------------------------------------
set "EXTRA="
set "ANS="
set /p "ANS=Force an early estimate if a team has under 2 games? (y/N): "
if /i "%ANS%"=="y" set "EXTRA=%EXTRA% --min-games 1"
set "ANS="
set /p "ANS=Also show live bookmaker odds? (y/N): "
if /i "%ANS%"=="y" set "EXTRA=%EXTRA% --odds"

echo.
echo ------------------------------------------------------------
"%PY%" "research\predict_fixture_live.py" "%HOME_TEAM%" "%AWAY_TEAM%"%EXTRA%
goto :done

:listteams
echo.
echo No teams entered - showing the teams the model knows instead:
echo.
"%PY%" "research\predict_fixture_live.py" --teams

:done
echo.
echo ------------------------------------------------------------
echo  Done. Close this window when finished.
echo ------------------------------------------------------------
pause >nul
endlocal
