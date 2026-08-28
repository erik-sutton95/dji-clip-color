@echo off
setlocal
set "TARGET=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\DJI Clip Color.py"
if exist "%TARGET%" (
  del /F /Q "%TARGET%"
  echo Removed %TARGET%
) else (
  echo Nothing to remove:
  echo   %TARGET%
)
if /I not "%~1"=="/nopause" pause
