@echo off
schtasks /Delete /TN "V3D PreMarket Master" /F
schtasks /Delete /TN "V3D EndOfDay Shutdown" /F
pause
