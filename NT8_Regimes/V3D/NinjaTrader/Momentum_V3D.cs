// CC BY-NC 4.0
// Momentum_V3D.cs — V3D Institutional Regime Matrix
// Bot 2: Momentum — TREND_COMPRESSION (primary), TREND_EXPANSION (secondary)
//
// Signal architecture: Wilder DI cross + CI/ADX dual-confirmation gate + slope-based exit.
// Regime: reads {symbol}_RegimeMatrix_Latest.csv via header-driven parser + FileSystemWatcher.
// Direction: reads AllowLong / AllowShort from HUD at submission time. No static parameters.
// Sizing: MaxContracts calculated from ATR/Apex $1,500 ceiling, then scaled by MomoSizePct from HUD.
// Chart: 1-minute candles. Calculate = OnPriceChange.

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.Strategies;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class Momentum_V3D : Strategy
    {
        // =========================================================================
        // ENUMS
        // =========================================================================
        public enum ExitSlopeMode { None, Simple, Hysteresis }

        // =========================================================================
        // PARAMETERS — grouped exactly as displayed in NT8 strategy dialog
        // =========================================================================

        // --- 1. Regime ---
        [NinjaScriptProperty]
        [Display(Name = "Data Folder Path", GroupName = "1. Regime", Order = 0)]
        public string DataFolderPath { get; set; } = @"C:\Users\Valued Customer\NT8_Regimes\V3D";

        // --- 2. Risk ---
        [NinjaScriptProperty, Range(0.1, 5.0)]
        [Display(Name = "ATR Stop Multiplier", GroupName = "2. Risk", Order = 0)]
        public double AtrStopMult { get; set; } = 0.75;

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "ATR Period", GroupName = "2. Risk", Order = 1)]
        public int AtrPeriod { get; set; } = 14;

        [NinjaScriptProperty, Range(0, int.MaxValue)]
        [Display(Name = "Min Stop (ticks)", GroupName = "2. Risk", Order = 2)]
        public int MinStopTicks { get; set; } = 4;

        [NinjaScriptProperty, Range(0.1, 5.0)]
        [Display(Name = "Risk:Reward", GroupName = "2. Risk", Order = 3)]
        public double RiskReward { get; set; } = 1.5;

        // Per-instrument tick values for Apex $1,500 max-contract calc.
        // Set to instrument tick value in dollars (NQ=$5, ES=$12.50, MNQ=$0.50, MES=$1.25).
        [NinjaScriptProperty, Range(0.01, 100.0)]
        [Display(Name = "Tick Value ($)", Description = "NQ=5.00  ES=12.50  MNQ=0.50  MES=1.25", GroupName = "2. Risk", Order = 4)]
        public double TickValueDollars { get; set; } = 5.00;

        // --- 3. Signal / CI-ADX ---
        [NinjaScriptProperty, Range(2, 200)]
        [Display(Name = "CI Period", GroupName = "3. Signal", Order = 0)]
        public int CiPeriod { get; set; } = 14;

        [NinjaScriptProperty, Range(1, int.MaxValue)]
        [Display(Name = "ADX Period", GroupName = "3. Signal", Order = 1)]
        public int AdxPeriod { get; set; } = 14;

        // Regime-adaptive CI ceiling: TREND_COMPRESSION allows higher choppiness.
        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "CI Max — Compression", Description = "TREND_COMPRESSION: CI ≤ this value", GroupName = "3. Signal", Order = 2)]
        public double CiMaxCompression { get; set; } = 58.0;

        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "CI Max — Expansion", Description = "TREND_EXPANSION (secondary): CI ≤ this value", GroupName = "3. Signal", Order = 3)]
        public double CiMaxExpansion { get; set; } = 50.0;

        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "ADX Entry Threshold", GroupName = "3. Signal", Order = 4)]
        public double AdxEntryThreshold { get; set; } = 18.0;

        // Velocity secondary gate: if Velocity3P_ATR >= this, ADX floor drops by 2.
        [NinjaScriptProperty, Range(0.0, 5.0)]
        [Display(Name = "Velocity ADX Relief Threshold", Description = "Strong velocity lowers ADX floor by 2 pts", GroupName = "3. Signal", Order = 5)]
        public double VelocityReliefThreshold { get; set; } = 0.85;

        // --- 4. Exit ---
        [NinjaScriptProperty]
        [Display(Name = "Slope Exit Mode", GroupName = "4. Exit", Order = 0)]
        public ExitSlopeMode SlopeExit { get; set; } = ExitSlopeMode.Hysteresis;

        [NinjaScriptProperty, Range(0, 1000)]
        [Display(Name = "Min Hold Bars", GroupName = "4. Exit", Order = 1)]
        public int MinHoldBars { get; set; } = 2;

        [NinjaScriptProperty, Range(1, 50)]
        [Display(Name = "CI Slope Bars (Simple)", GroupName = "4. Exit", Order = 2)]
        public int CiSlopeBarsExit { get; set; } = 5;

        [NinjaScriptProperty, Range(1, 50)]
        [Display(Name = "ADX Slope Bars (Simple)", GroupName = "4. Exit", Order = 3)]
        public int AdxSlopeBarsExit { get; set; } = 5;

        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "Min CI Rise (Simple)", GroupName = "4. Exit", Order = 4)]
        public double CiRiseMinExit { get; set; } = 2.0;

        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "Min ADX Drop (Simple)", GroupName = "4. Exit", Order = 5)]
        public double AdxDropMinExit { get; set; } = 2.0;

        [NinjaScriptProperty, Range(1, 50)]
        [Display(Name = "Hysteresis Consecutive Fails", GroupName = "4. Exit", Order = 6)]
        public int HystConsecutive { get; set; } = 2;

        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "CI Rise Per Bar (Hysteresis)", GroupName = "4. Exit", Order = 7)]
        public double HystCiRisePerBar { get; set; } = 0.5;

        [NinjaScriptProperty, Range(0.0, 100.0)]
        [Display(Name = "ADX Drop Per Bar (Hysteresis)", GroupName = "4. Exit", Order = 8)]
        public double HystAdxDropPerBar { get; set; } = 0.5;

        // --- 5. Guards ---
        [NinjaScriptProperty, Range(0, 10)]
        [Display(Name = "Max Consecutive Losses", GroupName = "5. Guards", Order = 0)]
        public int MaxConsecutiveLosses { get; set; } = 2;

        // --- 6. Time ---
        [NinjaScriptProperty]
        [Display(Name = "Enable Time Filter", GroupName = "6. Time", Order = 0)]
        public bool EnableTimeFilter { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Start Time (HHmmss)", GroupName = "6. Time", Order = 1)]
        public int StartTime { get; set; } = 93500;

        [NinjaScriptProperty]
        [Display(Name = "End Time (HHmmss)", GroupName = "6. Time", Order = 2)]
        public int EndTime { get; set; } = 155500;

        // =========================================================================
        // REGIME STATE — read from RegimeMatrix_Latest.csv
        // =========================================================================
        private string matrixFile       = "";
        private string leaderSymbol     = "";
        private DateTime lastFileWriteUtc = DateTime.MinValue;
        private DateTime lastFileCheck    = DateTime.MinValue;
        private const int MinCheckSeconds = 15;
        private FileSystemWatcher regimeWatcher;
        private readonly object fileLock = new object();

        // Parsed regime columns (volatile for cross-thread safety from watcher)
        private volatile string  finalRegime      = "UNKNOWN";
        private volatile string  finalDirection   = "UNKNOWN";
        private volatile int     regimeConfidence = 0;
        private          double  conflictScore    = 1.0;
        private volatile bool    allowLong        = false;
        private volatile bool    allowShort       = false;
        private volatile int     momoSizePct      = 0;
        private volatile bool    staleDataFlag    = true;
        private          double  velocity3P       = 0.0;
        private volatile int     stateAgeBars     = 0;
        private volatile bool    parseFailed      = true;
        private volatile int     suggestedAdxMin  = 18; // from HMM output in Latest.csv

        // Header index map
        private Dictionary<string, int> headerIdx = new Dictionary<string, int>();

        // =========================================================================
        // INDICATORS
        // =========================================================================
        private ATR atrStop;
        private ADX adx;

        // CI internals (Wilder/manual — no built-in CI in NT8)
        private Series<double> trSeries;
        private SUM  sumTr;
        private MAX  maxHigh;
        private MIN  minLow;
        private Series<double> ci;

        // DI+ / DI- (Wilder smoothing — own series for accuracy)
        private Series<double> dmPlus, dmMinus;
        private Series<double> sumDmPlus, sumDmMinus, sumTrDI;
        private Series<double> diPlusSeries, diMinusSeries;

        // =========================================================================
        // RUNTIME STATE
        // =========================================================================
        private int  consecutiveLosers = 0;
        private int  lastTradeCount    = 0;
        private int  hystFailCount     = 0;

        // =========================================================================
        // HELPERS
        // =========================================================================
        private double RT(double p) => Instrument.MasterInstrument.RoundToTickSize(p);

        private string GetLeaderSymbol(string sym)
        {
            if (string.IsNullOrEmpty(sym)) return sym;
            sym = sym.Trim().ToUpper();
            if (sym == "MES") return "ES";
            if (sym == "MNQ") return "NQ";
            if (sym == "MGC") return "GC";
            if (sym == "MCL") return "CL";
            return sym;
        }

        private bool IsInTime()
        {
            if (!EnableTimeFilter) return true;
            int t = ToTime(Time[0]);
            return t >= StartTime && t <= EndTime;
        }

        // Apex $1,500 ceiling contract calculator
        private int CalcMaxContracts()
        {
            double atrVal = atrStop[0];
            if (atrVal <= 0) return 1;
            double dollarRiskPerContract = (atrVal * AtrStopMult) / TickSize * TickValueDollars;
            if (dollarRiskPerContract <= 0) return 1;
            return Math.Max(1, (int)(1500.0 / dollarRiskPerContract));
        }

        private int ScaleByConfidence(int maxQty, int sizePct)
        {
            return Math.Max(1, (int)Math.Floor(maxQty * sizePct / 100.0));
        }

        // =========================================================================
        // LIFECYCLE
        // =========================================================================
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name                         = "Momentum_V3D";
                Calculate                    = Calculate.OnPriceChange;
                EntriesPerDirection          = 1;
                EntryHandling                = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds    = 30;
                RealtimeErrorHandling        = RealtimeErrorHandling.IgnoreAllErrors;
                TraceOrders                  = false;
            }
            else if (State == State.DataLoaded)
            {
                leaderSymbol = GetLeaderSymbol(Instrument.MasterInstrument.Name);
                matrixFile   = Path.Combine(DataFolderPath, leaderSymbol + "_RegimeMatrix_Latest.csv");

                adx     = ADX(AdxPeriod);
                atrStop = ATR(AtrPeriod);

                // CI internals
                trSeries = new Series<double>(this);
                sumTr    = SUM(trSeries, CiPeriod);
                maxHigh  = MAX(High, CiPeriod);
                minLow   = MIN(Low,  CiPeriod);
                ci       = new Series<double>(this);

                // DI internals
                dmPlus       = new Series<double>(this);
                dmMinus      = new Series<double>(this);
                sumDmPlus    = new Series<double>(this);
                sumDmMinus   = new Series<double>(this);
                sumTrDI      = new Series<double>(this);
                diPlusSeries = new Series<double>(this);
                diMinusSeries= new Series<double>(this);

                SetupFileWatcher();

                lastTradeCount = SystemPerformance.AllTrades.Count;
            }
            else if (State == State.Terminated)
            {
                TeardownFileWatcher();
            }
        }

        // =========================================================================
        // FILE WATCHER — triggers async re-read on any write to Latest.csv
        // =========================================================================
        private void SetupFileWatcher()
        {
            try
            {
                string dir  = Path.GetDirectoryName(matrixFile);
                string file = Path.GetFileName(matrixFile);
                if (!Directory.Exists(dir)) return;
                regimeWatcher = new FileSystemWatcher(dir, file)
                {
                    NotifyFilter         = NotifyFilters.LastWrite,
                    EnableRaisingEvents  = true
                };
                regimeWatcher.Changed += (s, e) => ThreadPool.QueueUserWorkItem(_ => ReadLatestRow());
                ReadLatestRow(); // initial load
            }
            catch { }
        }

        private void TeardownFileWatcher()
        {
            try
            {
                if (regimeWatcher != null)
                {
                    regimeWatcher.EnableRaisingEvents = false;
                    regimeWatcher.Dispose();
                    regimeWatcher = null;
                }
            }
            catch { }
        }

        // =========================================================================
        // REGIME FILE READER — header-driven, atomic-rename safe
        // =========================================================================
        private void RefreshRegimeState()
        {
            if ((DateTime.Now - lastFileCheck).TotalSeconds < MinCheckSeconds) return;
            try
            {
                DateTime wt = File.GetLastWriteTimeUtc(matrixFile);
                if (wt <= lastFileWriteUtc) { lastFileCheck = DateTime.Now; return; }
                ReadLatestRow();
                lastFileWriteUtc = wt;
                lastFileCheck    = DateTime.Now;
            }
            catch { }
        }

        private void ReadLatestRow()
        {
            for (int attempt = 0; attempt < 3; attempt++)
            {
                try
                {
                    string[] lines;
                    lock (fileLock)
                    {
                        using (var fs = new FileStream(matrixFile, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                        using (var sr = new StreamReader(fs))
                            lines = sr.ReadToEnd().Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
                    }

                    if (lines.Length < 2) { parseFailed = true; return; }

                    // Build header map once (or if it changed)
                    if (headerIdx.Count == 0)
                    {
                        string[] hdr = lines[0].Split(',');
                        headerIdx.Clear();
                        for (int i = 0; i < hdr.Length; i++)
                            headerIdx[hdr[i].Trim()] = i;
                    }

                    string[] row = lines[lines.Length - 1].Split(',');

                    finalRegime      = Get(row, "FinalRegime");
                    finalDirection   = Get(row, "FinalDirection");
                    conflictScore    = GetD(row, "ConflictScore");
                    regimeConfidence = (int)GetD(row, "RegimeConfidence");
                    allowLong        = GetI(row, "AllowLong")  == 1;
                    allowShort       = GetI(row, "AllowShort") == 1;
                    momoSizePct      = GetIAny(row, "MomoSizePct", "AllowMomo_SizePct");
                    staleDataFlag    = GetI(row, "StaleDataFlag") == 1;
                    velocity3P       = GetD(row, "Velocity3P_ATR");
                    stateAgeBars     = GetI(row, "StateAgeBars");
                    suggestedAdxMin  = GetI(row, "SuggestedAdxMin"); // from HMM column in Latest
                    parseFailed      = false;
                    return;
                }
                catch { Thread.Sleep(20); }
            }
            parseFailed = true;
        }

        private string Get(string[] row, string col)
        {
            int i; return headerIdx.TryGetValue(col, out i) && i < row.Length ? row[i].Trim() : "";
        }
        private double GetD(string[] row, string col)
        {
            double v; return double.TryParse(Get(row, col), out v) ? v : 0.0;
        }
        private int GetI(string[] row, string col)
        {
            int v; return int.TryParse(Get(row, col), out v) ? v : 0;
        }
        private int GetIAny(string[] row, params string[] cols)
        {
            foreach (string col in cols)
            {
                int v;
                string raw = Get(row, col);
                if (!string.IsNullOrEmpty(raw) && int.TryParse(raw, out v))
                    return v;
            }
            return 0;
        }

        // =========================================================================
        // REGIME GATE — is this bot permitted to trade right now?
        // =========================================================================
        private bool IsRegimeAllowed()
        {
            if (parseFailed || staleDataFlag) return false;
            return finalRegime == "TREND_COMPRESSION" || finalRegime == "TREND_EXPANSION";
        }

        // CI ceiling is regime-adaptive
        private double ActiveCiMax()
        {
            return finalRegime == "TREND_EXPANSION" ? CiMaxExpansion : CiMaxCompression;
        }

        // ADX floor: velocity relief lowers it by 2 when momentum is strong
        private double ActiveAdxFloor()
        {
            double floor = Math.Max(AdxEntryThreshold, suggestedAdxMin > 0 ? (double)suggestedAdxMin : AdxEntryThreshold);
            if (Math.Abs(velocity3P) >= VelocityReliefThreshold) floor -= 2.0;
            return floor;
        }

        // =========================================================================
        // CONSECUTIVE LOSER TRACKING
        // =========================================================================
        protected override void OnExecutionUpdate(
            Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            int tc = SystemPerformance.AllTrades.Count;
            if (tc > lastTradeCount)
            {
                var last = SystemPerformance.AllTrades[tc - 1];
                if (last.ProfitCurrency < 0) consecutiveLosers++;
                else                         consecutiveLosers = 0;
                lastTradeCount = tc;
            }
        }

        // Reset consecutive losers on new session and on regime change
        private string lastRegimeSeen = "";
        private void CheckSessionReset()
        {
            if (Bars.IsFirstBarOfSession)
                consecutiveLosers = 0;

            if (finalRegime != lastRegimeSeen)
            {
                consecutiveLosers = 0;
                lastRegimeSeen    = finalRegime;
            }
        }

        // =========================================================================
        // MAIN BAR UPDATE
        // =========================================================================
        protected override void OnBarUpdate()
        {
            if (CurrentBar < 2) return;

            int warmup = Math.Max(AdxPeriod, Math.Max(CiPeriod, AtrPeriod)) + 4;
            if (CurrentBar < warmup) return;

            // --- Refresh regime from file (timestamp-guarded) ---
            RefreshRegimeState();
            CheckSessionReset();

            // --- Compute CI ---
            double trBar = Math.Max(High[0] - Low[0],
                           Math.Max(Math.Abs(High[0] - Close[1]),
                                    Math.Abs(Low[0]  - Close[1])));
            trSeries[0] = trBar;
            double range   = maxHigh[0] - minLow[0];
            double sumTrVal= Math.Max(1e-9, sumTr[0]);
            double denom   = Math.Log10(Math.Max(2, CiPeriod));
            double numer   = (range <= 1e-9) ? 1.0 : (sumTrVal / Math.Max(1e-9, range));
            ci[0] = Math.Max(0.0, Math.Min(100.0,
                    100.0 * Math.Log10(numer) / denom));

            // --- Compute Wilder DI ---
            double h0 = High[0], l0 = Low[0], h1 = High[1], l1 = Low[1], c1 = Close[1];
            double tr2 = Math.Max(h0 - l0, Math.Max(Math.Abs(h0 - c1), Math.Abs(l0 - c1)));
            double up   = h0 - h1;
            double down = l1 - l0;
            double dmp  = (up   > 0 && up   > down) ? up   : 0;
            double dmn  = (down > 0 && down > up)   ? down : 0;

            if (CurrentBar < AdxPeriod)
            {
                sumTrDI[0]    = sumTrDI[1]    + tr2;
                sumDmPlus[0]  = sumDmPlus[1]  + dmp;
                sumDmMinus[0] = sumDmMinus[1] + dmn;
            }
            else
            {
                sumTrDI[0]    = sumTrDI[1]    - (sumTrDI[1]    / AdxPeriod) + tr2;
                sumDmPlus[0]  = sumDmPlus[1]  - (sumDmPlus[1]  / AdxPeriod) + dmp;
                sumDmMinus[0] = sumDmMinus[1] - (sumDmMinus[1] / AdxPeriod) + dmn;
            }
            double sTr         = sumTrDI[0].ApproxCompare(0) == 0 ? 1e-9 : sumTrDI[0];
            diPlusSeries[0]    = 100.0 * (sumDmPlus[0]  / sTr);
            diMinusSeries[0]   = 100.0 * (sumDmMinus[0] / sTr);

            bool crossUp   = CrossAbove(diPlusSeries, diMinusSeries, 1);
            bool crossDown = CrossBelow(diPlusSeries, diMinusSeries, 1);

            // --- Gu5 circuit breaker exit (fires before entries) ---
            ApplyCircuitBreakerExit(crossDown, crossUp);

            // --- Regime-TRANSITION immediate exit ---
            if (Position.MarketPosition != MarketPosition.Flat && finalRegime == "TRANSITION")
            {
                if (Position.MarketPosition == MarketPosition.Long)  ExitLong ("TransitionExit", LEntry);
                else                                                  ExitShort("TransitionExit", SEntry);
                return;
            }

            // --- ENTRY logic ---
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                if (!IsRegimeAllowed())         return;
                if (consecutiveLosers >= MaxConsecutiveLosses) return;
                if (!IsInTime())                return;
                if (parseFailed || staleDataFlag) return;

                double ciMax   = ActiveCiMax();
                double adxFloor= ActiveAdxFloor();

                bool ciOk  = ci[0]  <= ciMax;
                bool adxOk = adx[0] >= adxFloor;

                if (ciOk && adxOk)
                {
                    if (crossUp  && allowLong)  SubmitLongWithStops();
                    if (crossDown && allowShort) SubmitShortWithStops();
                }
            }

            // --- SLOPE exit logic ---
            if (Position.MarketPosition != MarketPosition.Flat)
            {
                string ent = Position.MarketPosition == MarketPosition.Long ? LEntry : SEntry;
                int bse = BarsSinceEntryExecution(0, ent, 0);
                if (bse < MinHoldBars) return;

                bool exitNow = false;

                if (SlopeExit == ExitSlopeMode.Simple && CurrentBar > Math.Max(CiSlopeBarsExit, AdxSlopeBarsExit))
                {
                    double ciRise  = ci[0]  - ci[CiSlopeBarsExit];
                    double adxDrop = adx[AdxSlopeBarsExit] - adx[0];
                    exitNow = ciRise >= CiRiseMinExit || adxDrop >= AdxDropMinExit;
                }
                else if (SlopeExit == ExitSlopeMode.Hysteresis && CurrentBar > 1)
                {
                    double ciBar  = ci[0]  - ci[1];
                    double adxBar = adx[1] - adx[0];
                    bool thisFail = ciBar >= HystCiRisePerBar || adxBar >= HystAdxDropPerBar;
                    if (thisFail) hystFailCount++;
                    else          hystFailCount = Math.Max(0, hystFailCount - 1);
                    exitNow = hystFailCount >= HystConsecutive;
                }

                if (exitNow)
                {
                    if (Position.MarketPosition == MarketPosition.Long)  ExitLong ("SlopeX", LEntry);
                    else                                                  ExitShort("SlopeX", SEntry);
                    hystFailCount = 0;
                }
            }
        }

        // =========================================================================
        // CIRCUIT BREAKER — fires on ADX/DI signal deterioration
        // =========================================================================
        private void ApplyCircuitBreakerExit(bool crossDown, bool crossUp)
        {
            if (Position.MarketPosition == MarketPosition.Long)
            {
                // Exit if DI cross turns against long OR regime is TRANSITION
                if (crossDown || finalRegime == "TRANSITION")
                {
                    ExitLong("CircuitBreaker", LEntry);
                    hystFailCount = 0;
                }
            }
            else if (Position.MarketPosition == MarketPosition.Short)
            {
                if (crossUp || finalRegime == "TRANSITION")
                {
                    ExitShort("CircuitBreaker", SEntry);
                    hystFailCount = 0;
                }
            }
        }

        // =========================================================================
        // ORDER SUBMISSION — HUD-gated, Apex-sized, confidence-scaled
        // =========================================================================
        private const string LEntry = "MomoL";
        private const string SEntry = "MomoS";

        private void SubmitLongWithStops()
        {
            // Re-verify HUD permission at moment of submission
            if (!allowLong || staleDataFlag || parseFailed) return;

            int maxContracts = CalcMaxContracts();
            int qty          = ScaleByConfidence(maxContracts, momoSizePct > 0 ? momoSizePct : 50);
            if (qty < 1) return;

            double risk = Math.Max(AtrStopMult * atrStop[0], MinStopTicks * TickSize);
            double stp  = RT(Close[0] - risk);
            double tgt  = RT(Close[0] + risk * RiskReward);

            SetStopLoss(LEntry, CalculationMode.Price, stp, false);
            SetProfitTarget(LEntry, CalculationMode.Price, tgt);
            EnterLong(qty, LEntry);
        }

        private void SubmitShortWithStops()
        {
            if (!allowShort || staleDataFlag || parseFailed) return;

            int maxContracts = CalcMaxContracts();
            int qty          = ScaleByConfidence(maxContracts, momoSizePct > 0 ? momoSizePct : 50);
            if (qty < 1) return;

            double risk = Math.Max(AtrStopMult * atrStop[0], MinStopTicks * TickSize);
            double stp  = RT(Close[0] + risk);
            double tgt  = RT(Close[0] - risk * RiskReward);

            SetStopLoss(SEntry, CalculationMode.Price, stp, false);
            SetProfitTarget(SEntry, CalculationMode.Price, tgt);
            EnterShort(qty, SEntry);
        }
    }
}
