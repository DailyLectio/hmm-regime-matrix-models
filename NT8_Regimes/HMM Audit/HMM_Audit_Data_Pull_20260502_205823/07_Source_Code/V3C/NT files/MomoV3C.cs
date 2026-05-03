// CC BY-NC 4.0
#region Using
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.Data; // Added for BarsPeriodType
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    // CLASS NAME UPDATED TO BREAK LINK TO OLD BACKUP FILES
    public class Momo_V3C : Strategy 
    {
        // =========================================================================
        // 1. TRINITY COMMAND CENTER (The HUD Master Switch)
        // =========================================================================
        [NinjaScriptProperty]
        [Display(Name="1. Enable Trinity Filter", Description="If true, listens to the Regime HUD for permission.", GroupName="Trinity Command Center", Order=0)]
        public bool EnableTrinityFilter { get; set; } = true;

        // --- NEW V3 LANE SELECTOR ---
        public enum MomoHudLane { DefaultUniversal, EsOpenScalper, BracketSniper }

        [NinjaScriptProperty]
        [Display(Name="1b. Select HUD Lane", Description="Routes the strategy to a specific Regime Lane on the HUD.", GroupName="Trinity Command Center", Order=1)]
        public MomoHudLane SelectedHudLane { get; set; } = MomoHudLane.DefaultUniversal;

        [NinjaScriptProperty]
        [Display(Name="2. Fix HA Backtesting (Dual Series)", Description="If true, routes orders to a hidden Standard 1m chart to bypass synthetic HA fills.", GroupName="Trinity Command Center", Order=2)]
        public bool UseDualSeries { get; set; } = true;

        private int execSeries = 0; // 0 = Primary Chart, 1 = Secondary 1m Chart

        // The live permission slip linked to the V3C HUD Parking Garage
        private bool IsBotAllowedByTrinity()
        {
            if (!EnableTrinityFilter) return true;

            string chartSymbol = Instrument.MasterInstrument.Name;
            string leaderSymbol = GetLeaderSymbol(chartSymbol);

            Indicators.RegimeMatrixHUD_V3C hudInstance = null;

            // First try exact chart symbol, then leader symbol fallback.
            // Example: MNQ strategy can still use NQ V3C HUD if the HUD is registered under NQ.
            if (!Indicators.RegimeMatrixHUD_V3C.InstancesV3C.TryGetValue(chartSymbol, out hudInstance))
                Indicators.RegimeMatrixHUD_V3C.InstancesV3C.TryGetValue(leaderSymbol, out hudInstance);

            if (hudInstance != null)
            {
                if (SelectedHudLane == MomoHudLane.DefaultUniversal)
                    return hudInstance.IsMomoAllowed;
                else if (SelectedHudLane == MomoHudLane.EsOpenScalper)
                    return hudInstance.IsEsScalperAllowed;
                else if (SelectedHudLane == MomoHudLane.BracketSniper)
                    return hudInstance.IsBracketSniperAllowed;
            }

            // If we can't find the V3C HUD, block trades for safety.
            return false;
        }

        private bool IsLongAllowedByTrinity()
        {
            if (!EnableTrinityFilter) return true;

            string chartSymbol = Instrument.MasterInstrument.Name;
            string leaderSymbol = GetLeaderSymbol(chartSymbol);
            Indicators.RegimeMatrixHUD_V3C hudInstance = null;

            if (!Indicators.RegimeMatrixHUD_V3C.InstancesV3C.TryGetValue(chartSymbol, out hudInstance))
                Indicators.RegimeMatrixHUD_V3C.InstancesV3C.TryGetValue(leaderSymbol, out hudInstance);

            if (hudInstance == null)
                return false;

            if (SelectedHudLane == MomoHudLane.DefaultUniversal)
                return hudInstance.IsMomoLongAllowed;
            else if (SelectedHudLane == MomoHudLane.EsOpenScalper)
                return hudInstance.IsEsScalperAllowed && hudInstance.AllowLong;
            else if (SelectedHudLane == MomoHudLane.BracketSniper)
                return hudInstance.IsBracketSniperAllowed && hudInstance.AllowLong;

            return false;
        }

        private bool IsShortAllowedByTrinity()
        {
            if (!EnableTrinityFilter) return true;

            string chartSymbol = Instrument.MasterInstrument.Name;
            string leaderSymbol = GetLeaderSymbol(chartSymbol);
            Indicators.RegimeMatrixHUD_V3C hudInstance = null;

            if (!Indicators.RegimeMatrixHUD_V3C.InstancesV3C.TryGetValue(chartSymbol, out hudInstance))
