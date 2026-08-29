@echo off
setlocal EnableExtensions
title DJI Clip Color installer
echo.
echo DJI Clip Color - installer
echo ==========================
echo.

set "SRC=%~dp0dji_clip_color.py"
set "DEST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
set "NAME=DJI Clip Color.py"

if exist "%SRC%" goto :copy_local

echo No local dji_clip_color.py - downloading from GitHub...
where curl >nul 2>&1
if errorlevel 1 goto :use_powershell_download
set "TMP=%TEMP%\dji_clip_color.py"
curl -fsSL "https://raw.githubusercontent.com/erik-sutton95/dji-clip-color/main/dji_clip_color.py" -o "%TMP%"
if errorlevel 1 goto :fail
set "SRC=%TMP%"
goto :copy_local

:use_powershell_download
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 goto :fail
goto :done

:copy_local
if not exist "%DEST%" mkdir "%DEST%"
if errorlevel 1 goto :fail
copy /Y "%SRC%" "%DEST%\%NAME%" >nul
if errorlevel 1 goto :fail

echo Installed:
echo   %DEST%\%NAME%
echo.
if exist "%ProgramFiles%\Blackmagic Design\DaVinci Resolve\Resolve.exe" (
  echo DaVinci Resolve found.
) else (
  echo Note: Resolve.exe was not in Program Files. The script is still installed.
)
echo.
echo Next:
echo   1. Restart DaVinci Resolve if it is already open.
echo   2. Import original MP4 / MOV takes (not .LRF / .XRF proxies).
echo   3. Select clips in the Media Pool.
echo   4. Workspace ^> Scripts ^> DJI Clip Color
echo   5. Customize Columns: add Color Space Notes or Keywords (search notes / keyword).
echo.
echo Clip colors:  Orange = D-Log2   Navy = D-Log   Pink = D-Log M   Teal = HLG
echo.
explorer /select,"%DEST%\%NAME%"
goto :done

:fail
echo.
echo Install failed.
if /I not "%~1"=="/nopause" pause
exit /b 1

:done
if /I not "%~1"=="/nopause" pause
exit /b 0
