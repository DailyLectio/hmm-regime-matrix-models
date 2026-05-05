# NQ Continuous Stitch Audit

Requested range: 2023-01-01 through 2026-04-24.
Actual first bar from supplied files: 2023-06-01 04:01:00.
Actual last bar from supplied files: 2026-04-24 21:00:00.
Output file: C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw\NQ\NQ_Continuous_20230101_20260424.Last.txt

## Method
Parsed NinjaTrader 1-minute Last exports with schema `timestamp;open;high;low;close;volume`. The stitch uses non-overlapping front-contract windows: each contract is active until the first timestamp available in the next quarterly contract, then the next contract takes over. This avoids duplicate timestamps and avoids hidden old/new contract switching inside overlap periods. Output remains the same no-header semicolon format expected by NT-style raw data readers.

## Validation
- Source rows after date filter, before roll-window removal: 1,070,079
- Final stitched rows: 1,021,666
- Rows excluded by non-overlap roll windows: 48,413
- Duplicate timestamps in final output: 0
- Important coverage gap: no supplied file contains data from 2023-01-01 through 2023-05-31. The first available NQ bar is 2023-06-01 04:01:00.

## Rows By Contract Used
- NQ 06-23: 6,897 rows, 2023-06-01 04:01:00 to 2023-06-08 04:02:00
- NQ 09-23: 88,573 rows, 2023-06-08 04:03:00 to 2023-09-07 04:04:00
- NQ 12-23: 89,034 rows, 2023-09-07 04:05:00 to 2023-12-07 05:00:00
- NQ 03-24: 86,223 rows, 2023-12-07 05:01:00 to 2024-03-07 05:07:00
- NQ 06-24: 94,730 rows, 2024-03-07 05:08:00 to 2024-06-13 04:00:00
- NQ 09-24: 88,688 rows, 2024-06-13 04:01:00 to 2024-09-12 04:01:00
- NQ 12-24: 89,094 rows, 2024-09-12 04:02:00 to 2024-12-12 05:00:00
- NQ 03-25: 85,480 rows, 2024-12-12 05:01:00 to 2025-03-13 04:00:00
- NQ 06-25: 87,799 rows, 2025-03-13 04:01:00 to 2025-06-12 04:01:00
- NQ 09-25: 88,482 rows, 2025-06-12 04:02:00 to 2025-09-11 04:16:00
- NQ 12-25: 87,976 rows, 2025-09-11 04:17:00 to 2025-12-11 05:00:00
- NQ 03-26: 85,815 rows, 2025-12-11 05:01:00 to 2026-03-12 04:00:00
- NQ 06-26: 42,875 rows, 2026-03-12 04:01:00 to 2026-04-24 21:00:00

## Rows By Year
- 2023: 205,977 rows
- 2024: 354,320 rows
- 2025: 350,989 rows
- 2026: 110,380 rows

## Roll Gaps
- NQ 06-23 -> NQ 09-23 at 2023-06-08 04:03:00: 170.75 points (1.193%)
- NQ 09-23 -> NQ 12-23 at 2023-09-07 04:05:00: 195.25 points (1.269%)
- NQ 12-23 -> NQ 03-24 at 2023-12-07 05:01:00: 202.75 points (1.282%)
- NQ 03-24 -> NQ 06-24 at 2024-03-07 05:08:00: 247.00 points (1.374%)
- NQ 06-24 -> NQ 09-24 at 2024-06-13 04:01:00: 261.25 points (1.330%)
- NQ 09-24 -> NQ 12-24 at 2024-09-12 04:02:00: 235.75 points (1.221%)
- NQ 12-24 -> NQ 03-25 at 2024-12-12 05:01:00: 272.50 points (1.252%)
- NQ 03-25 -> NQ 06-25 at 2025-03-13 04:01:00: 204.75 points (1.049%)
- NQ 06-25 -> NQ 09-25 at 2025-06-12 04:02:00: 225.75 points (1.035%)
- NQ 09-25 -> NQ 12-25 at 2025-09-11 04:17:00: 232.75 points (0.974%)
- NQ 12-25 -> NQ 03-26 at 2025-12-11 05:01:00: 253.25 points (0.993%)
- NQ 03-26 -> NQ 06-26 at 2026-03-12 04:01:00: 209.50 points (0.847%)

## Large Chronological Gaps Over 18 Hours
- resumes 2023-06-03 16:47:00 on NQ 06-23 after gap 0 days 19:47:00
- resumes 2023-06-04 16:24:00 on NQ 06-23 after gap 0 days 23:37:00
- resumes 2023-06-10 15:38:00 on NQ 09-23 after gap 0 days 18:38:00
- resumes 2023-06-11 22:01:00 on NQ 09-23 after gap 0 days 22:36:00
- resumes 2023-06-18 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-06-25 16:01:00 on NQ 09-23 after gap 1 days 19:01:00
- resumes 2023-07-02 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-07-09 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-07-16 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-07-23 08:20:00 on NQ 09-23 after gap 1 days 11:20:00
- resumes 2023-07-30 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-08-06 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-08-13 22:01:00 on NQ 09-23 after gap 2 days 01:01:00
- resumes 2023-08-20 05:02:00 on NQ 09-23 after gap 1 days 04:04:00
- resumes 2023-08-27 18:29:00 on NQ 09-23 after gap 1 days 21:29:00
- resumes 2023-09-03 22:01:00 on NQ 09-23 after gap 1 days 21:29:00
- resumes 2023-09-09 23:51:00 on NQ 12-23 after gap 1 days 02:51:00
- resumes 2023-09-10 22:01:00 on NQ 12-23 after gap 0 days 20:27:00
- resumes 2023-09-17 13:54:00 on NQ 12-23 after gap 1 days 16:54:00
- resumes 2023-09-24 22:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-10-01 22:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-10-08 22:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-10-15 04:33:00 on NQ 12-23 after gap 1 days 07:33:00
- resumes 2023-10-22 22:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-10-29 22:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-11-05 07:15:00 on NQ 12-23 after gap 1 days 10:15:00
- resumes 2023-11-12 23:01:00 on NQ 12-23 after gap 1 days 05:34:00
- resumes 2023-11-19 23:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-11-26 23:01:00 on NQ 12-23 after gap 2 days 04:46:00
- resumes 2023-12-03 23:01:00 on NQ 12-23 after gap 2 days 01:01:00
- resumes 2023-12-10 03:31:00 on NQ 03-24 after gap 1 days 05:31:00
- resumes 2023-12-17 21:46:00 on NQ 03-24 after gap 1 days 23:46:00
- resumes 2023-12-25 23:01:00 on NQ 03-24 after gap 3 days 01:01:00
- resumes 2023-12-31 17:08:00 on NQ 03-24 after gap 1 days 19:08:00
- resumes 2024-01-01 23:01:00 on NQ 03-24 after gap 1 days 05:53:00
- resumes 2024-01-07 23:01:00 on NQ 03-24 after gap 2 days 01:01:00
- resumes 2024-01-14 21:33:00 on NQ 03-24 after gap 1 days 05:42:00
- resumes 2024-01-20 17:00:00 on NQ 03-24 after gap 0 days 18:03:00
- resumes 2024-01-28 23:01:00 on NQ 03-24 after gap 2 days 01:01:00
- resumes 2024-02-03 16:21:00 on NQ 03-24 after gap 0 days 18:21:00

## Companion Files
- Manifest: C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw\NQ\NQ_Continuous_20230101_20260424_Manifest.csv
- Roll windows: C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw\NQ\NQ_Continuous_20230101_20260424_RollWindows.csv