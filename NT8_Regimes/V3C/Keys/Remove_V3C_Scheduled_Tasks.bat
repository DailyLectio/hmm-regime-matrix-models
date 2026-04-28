@echo off
setlocal EnableExtensions
title Remove V3C Scheduled Tasks
color 0C

schtasks /Delete /TN "V3C PreMarket Master" /F
schtasks /Delete /TN "V3C EndOfDay Shutdown" /F

echo.
echo V3C scheduled tasks removed if they existed.
pause
exit /b 0
