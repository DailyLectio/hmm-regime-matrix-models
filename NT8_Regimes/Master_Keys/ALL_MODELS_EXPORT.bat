@echo off
setlocal
cd /d "C:\Users\Valued Customer\NT8_Regimes"
python "Scripts\eod_export.py" --date today
endlocal
