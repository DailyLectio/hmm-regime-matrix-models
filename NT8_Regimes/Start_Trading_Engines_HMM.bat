@echo off
title Trinity Command Center
color 0B

:: Launch the HMM Watchdog
start "HMM Watchdog" cmd /c "python "C:\Users\Valued Customer\NT8_Regimes\HMM_Watchdog.py" ^& pause"

:: Launch the Macro Supervisor
start "Macro Supervisor" cmd /c "python "C:\Users\Valued Customer\NT8_Regimes\MacroSupervisor.py" ^& pause"

echo Trinity Engines Active.
exit