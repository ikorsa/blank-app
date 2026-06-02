@echo off
setlocal

REM Usage:
REM   scripts\update_vps.bat user@server [branch]
REM Example:
REM   scripts\update_vps.bat ikorsa@1.2.3.4 main

if "%~1"=="" (
  echo Usage: %~nx0 user@server [branch]
  exit /b 1
)

set "REMOTE=%~1"
set "BRANCH=%~2"
if "%BRANCH%"=="" set "BRANCH=main"

echo Deploying branch %BRANCH% to %REMOTE%
ssh %REMOTE% "cd /opt/anamnes && chmod +x scripts/update_vps.sh && ./scripts/update_vps.sh %BRANCH%"

if errorlevel 1 (
  echo Deployment failed
  exit /b 1
)

echo Deployment done
endlocal
