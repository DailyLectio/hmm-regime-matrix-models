# ES Continuous Stitch Audit

Requested range: 2023-06-01 through 2026-04-24.
Actual first bar from supplied files: 2023-06-01 04:01:00.
Actual last bar from supplied files: 2026-04-24 21:00:00.
Output file: C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw\ES\ES_Continuous_20230601_20260424.Last.txt

## Method
Parsed NinjaTrader 1-minute Last exports with schema `timestamp;open;high;low;close;volume`. The stitch uses non-overlapping front-contract windows: each contract is active until the first timestamp available in the next quarterly contract, then the next contract takes over. This avoids duplicate timestamps and avoids hidden old/new contract switching inside overlap periods. Output remains the same no-header semicolon format expected by NT-style raw data readers.

## Validation
- Source rows after date filter, before roll-window removal: 1,090,474
- Final stitched rows: 1,023,246
- Rows excluded by non-overlap roll windows: 67,228
- Duplicate timestamps in final output: 0

## Rows By Contract Used
- ES 06-23: 6,890 rows, 2023-06-01 04:01:00 to 2023-06-08 04:00:00
- ES 09-23: 88,646 rows, 2023-06-08 04:01:00 to 2023-09-07 04:01:00
- ES 12-23: 89,143 rows, 2023-09-07 04:02:00 to 2023-12-07 05:00:00
- ES 03-24: 86,367 rows, 2023-12-07 05:01:00 to 2024-03-07 05:00:00
- ES 06-24: 94,910 rows, 2024-03-07 05:01:00 to 2024-06-13 04:00:00
- ES 09-24: 88,631 rows, 2024-06-13 04:01:00 to 2024-09-12 04:00:00
- ES 12-24: 89,206 rows, 2024-09-12 04:01:00 to 2024-12-12 05:00:00
- ES 03-25: 85,711 rows, 2024-12-12 05:01:00 to 2025-03-13 04:00:00
- ES 06-25: 88,108 rows, 2025-03-13 04:01:00 to 2025-06-12 04:00:00
- ES 09-25: 88,754 rows, 2025-06-12 04:01:00 to 2025-09-11 04:00:00
- ES 12-25: 88,476 rows, 2025-09-11 04:01:00 to 2025-12-11 05:00:00
- ES 03-26: 85,088 rows, 2025-12-11 05:01:00 to 2026-03-12 04:00:00
- ES 06-26: 43,316 rows, 2026-03-12 04:01:00 to 2026-04-24 21:00:00

## Rows By Year
- 2023: 206,344 rows
- 2024: 354,734 rows
- 2025: 352,481 rows
- 2026: 109,687 rows

## Roll Gaps
- ES 06-23 -> ES 09-23 at 2023-06-08 04:01:00: 42.75 points (1.001%)
- ES 09-23 -> ES 12-23 at 2023-09-07 04:02:00: 49.50 points (1.108%)
- ES 12-23 -> ES 03-24 at 2023-12-07 05:01:00: 50.00 points (1.098%)
- ES 03-24 -> ES 06-24 at 2024-03-07 05:01:00: 62.25 points (1.220%)
- ES 06-24 -> ES 09-24 at 2024-06-13 04:01:00: 65.00 points (1.195%)
- ES 09-24 -> ES 12-24 at 2024-09-12 04:01:00: 59.50 points (1.069%)
- ES 12-24 -> ES 03-25 at 2024-12-12 05:01:00: 67.50 points (1.109%)
- ES 03-25 -> ES 06-25 at 2025-03-13 04:01:00: 51.50 points (0.922%)
- ES 06-25 -> ES 09-25 at 2025-06-12 04:01:00: 53.50 points (0.890%)
- ES 09-25 -> ES 12-25 at 2025-09-11 04:01:00: 54.75 points (0.836%)
- ES 12-25 -> ES 03-26 at 2025-12-11 05:01:00: 58.00 points (0.848%)
- ES 03-26 -> ES 06-26 at 2026-03-12 04:01:00: 49.50 points (0.737%)

## Large Chronological Gaps Over 18 Hours
- resumes 2023-06-03 16:47:00 on ES 06-23 after gap 0 days 19:47:00
- resumes 2023-06-04 16:24:00 on ES 06-23 after gap 0 days 23:37:00
- resumes 2023-06-11 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-06-18 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-06-25 16:01:00 on ES 09-23 after gap 1 days 19:01:00
- resumes 2023-07-02 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-07-09 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-07-16 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-07-23 08:20:00 on ES 09-23 after gap 1 days 11:20:00
- resumes 2023-07-30 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-08-06 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-08-13 22:01:00 on ES 09-23 after gap 2 days 01:01:00
- resumes 2023-08-27 18:29:00 on ES 09-23 after gap 1 days 21:29:00
- resumes 2023-09-03 22:01:00 on ES 09-23 after gap 1 days 21:29:00
- resumes 2023-09-09 23:51:00 on ES 12-23 after gap 1 days 02:51:00
- resumes 2023-09-10 22:01:00 on ES 12-23 after gap 0 days 20:27:00
- resumes 2023-09-17 13:54:00 on ES 12-23 after gap 1 days 16:54:00
- resumes 2023-09-24 22:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-10-01 22:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-10-08 22:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-10-15 04:33:00 on ES 12-23 after gap 1 days 07:33:00
- resumes 2023-10-22 22:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-10-29 22:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-11-05 07:01:00 on ES 12-23 after gap 1 days 10:01:00
- resumes 2023-11-12 15:36:00 on ES 12-23 after gap 0 days 19:32:00
- resumes 2023-11-19 23:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-11-26 23:01:00 on ES 12-23 after gap 2 days 04:46:00
- resumes 2023-12-03 23:01:00 on ES 12-23 after gap 2 days 01:01:00
- resumes 2023-12-10 03:31:00 on ES 03-24 after gap 1 days 05:31:00
- resumes 2023-12-17 21:46:00 on ES 03-24 after gap 1 days 23:46:00
- resumes 2023-12-25 23:01:00 on ES 03-24 after gap 3 days 01:01:00
- resumes 2023-12-30 22:13:00 on ES 03-24 after gap 1 days 00:13:00
- resumes 2023-12-31 17:08:00 on ES 03-24 after gap 0 days 18:55:00
- resumes 2024-01-01 23:01:00 on ES 03-24 after gap 1 days 05:53:00
- resumes 2024-01-07 15:21:00 on ES 03-24 after gap 1 days 17:21:00
- resumes 2024-01-14 14:13:00 on ES 03-24 after gap 0 days 22:22:00
- resumes 2024-01-20 17:00:00 on ES 03-24 after gap 0 days 19:00:00
- resumes 2024-01-21 23:01:00 on ES 03-24 after gap 1 days 04:02:00
- resumes 2024-01-27 23:35:00 on ES 03-24 after gap 1 days 01:33:00
- resumes 2024-02-03 16:21:00 on ES 03-24 after gap 0 days 18:21:00

## Companion Files
- Manifest: C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw\ES\ES_Continuous_20230601_20260424_Manifest.csv
- Roll windows: C:\Users\Valued Customer\NT8_Regimes\MacroRegime\data\raw\ES\ES_Continuous_20230601_20260424_RollWindows.csv