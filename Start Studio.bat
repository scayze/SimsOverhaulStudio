@echo off
title Sim Overhaul Studio - KEEP THIS WINDOW OPEN
cd /d "%~dp0"
set PYTHONUTF8=1
echo ============================================================
echo   SIM OVERHAUL STUDIO
echo ============================================================
echo.
echo   Starting the local studio server...
echo   Keep this black window open while you use the studio.
echo   Closing it stops the studio (the app window then says
echo   "Cannot fetch" until you run this file again).
echo.

where py >nul 2>nul
if %errorlevel%==0 goto use_py
where python >nul 2>nul
if %errorlevel%==0 goto use_python
echo   ERROR: Python was not found.
echo   Install Python 3 from https://python.org and try again.
goto end

:use_py
py -3 app.py
goto end

:use_python
python app.py
goto end

:end
echo.
echo ============================================================
echo   The studio server has stopped.
echo   Run this file again to restart it.
echo ============================================================
pause
