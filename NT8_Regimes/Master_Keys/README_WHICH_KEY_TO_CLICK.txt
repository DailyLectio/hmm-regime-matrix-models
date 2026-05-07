MASTER KEYS - CURRENT DAILY USE

START OF DAY
1. START_ALL_MODELS.bat

END OF DAY
1. EOD_ALL_MODELS.bat

DAILY REVIEW FILES
C:\Users\Valued Customer\NT8_Regimes\UNIFIED\AllModels_TradeLog_YYYYMMDD.csv
C:\Users\Valued Customer\NT8_Regimes\UNIFIED\Reports\Daily_Trade_Performance_YYYYMMDD.md

V3D TRADE SOURCE POLICY
- EOD_ALL_MODELS.bat uses Scripts\eod_export.py.
- V3D trade rows are read from V3D\TradeLog\V3D_INTERNAL_TradeLog.csv first.
- If the internal aggregate is not present yet, clean SimV3D_*_TradeLog.csv files are used.
- V3D\TradeLog\V3D_TradeLog.csv is legacy/contaminated and is skipped unless intentionally archived and regenerated.

ARCHIVE
Older multi-click keys and retired operator docs were moved to:
C:\Users\Valued Customer\NT8_Regimes\Archive\Master_Keys_Simplified_20260507_161245
