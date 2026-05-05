# ValueAreaBackfillReporter Setup

## Purpose

`ValueAreaBackfillReporter.cs` backfills the regime seed files:

- `C:\Users\Valued Customer\NT8_Regimes\Exports\ValueArea_ES.csv`
- `C:\Users\Valued Customer\NT8_Regimes\Exports\ValueArea_NQ.csv`

It appends missing historical rows only. Existing dates are skipped.

## Best Chart Setup

- Instrument: `ES 06-26` or `NQ 06-26`
- Bars: `1 Minute`
- Trading hours: `CME US Index Futures ETH`
- Days to load: as many as NT8/data provider allows
- Apply indicator: `Value Area Backfill Reporter`

Run it once on an ES chart and once on an NQ chart.

## Session Assumptions

- RTH value area window: `09:30` through `16:00`
- Overnight window: prior `18:00` through current `09:29`
- Time basis: the chart timestamps should be Eastern Time, matching the existing regime builders.

If the chart is RTH-only, the reporter can still export value area rows, but `ONHigh` and `ONLow` fall back to that day's RTH high/low. ETH is strongly preferred.

## Output Columns

```csv
Date,Symbol,POC,VAH,VAL,DailyVolume,ONHigh,ONLow
```

The value area is estimated from loaded intraday bars by distributing each bar's volume across its tick range. This is more useful than daily OHLC approximation, but still not identical to a true tick-level exchange volume profile.
