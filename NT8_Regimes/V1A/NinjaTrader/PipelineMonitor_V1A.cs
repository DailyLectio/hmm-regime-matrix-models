// PipelineMonitor_V1A.cs
// Lightweight V1A/V1B infrastructure health HUD.
// Load once on a V1A leader/support chart. Do not add to every strategy tab.

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.IO;
using System.Text;
using System.Windows.Media;
using NinjaTrader.Data;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class PipelineMonitor_V1A : Indicator
    {
        [NinjaScriptProperty]
        [Display(Name = "Data Folder Path", Description = "Base NT8_Regimes folder.", GroupName = "Pipeline Monitor", Order = 0)]
        public string DataFolderPath { get; set; } = @"C:\Users\Valued Customer\NT8_Regimes";

        [NinjaScriptProperty]
        [Display(Name = "Refresh Seconds", Description = "How often to re-check files.", GroupName = "Pipeline Monitor", Order = 1)]
        public int RefreshSeconds { get; set; } = 30;

        [NinjaScriptProperty]
        [Display(Name = "Footprint History Start Date", Description = "Informational display only.", GroupName = "Pipeline Monitor", Order = 2)]
        public string FootprintHistoryStartDate { get; set; } = "2024-06-01";

        [NinjaScriptProperty]
        [Display(Name = "Write HUD History CSV", Description = "Append one V1A/V1B HUD telemetry row per chart bar.", GroupName = "History Export", Order = 0)]
        public bool WriteHudHistoryCsv { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "HUD History Folder", Description = "Blank = V1A\\History\\HUD_Reads.", GroupName = "History Export", Order = 1)]
        public string HudHistoryFolder { get; set; } = "";

        private readonly SimpleFont panelFont = new SimpleFont("Consolas", 12);
        private DateTime lastCheck = DateTime.MinValue;
        private int lastHistoryWriteBar = -1;

        private string liveStatus = "CHECKING";
        private string valueAreaStatus = "CHECKING";
        private string footprintStatus = "CHECKING";
        private string biasStatus = "CHECKING";
        private string tradeLogStatus = "CHECKING";
        private string playbookStatus = "N/A";
        private string macroHudStatus = "N/A";
        private string hmmHudStatus = "N/A";
        private string v3cFinalRegime = "UNKNOWN";
        private string v3cFinalDirection = "UNKNOWN";
        private string v3cSnapshotTimestamp = "";
        private string v3dFinalRegime = "UNKNOWN";
        private string v3dFinalDirection = "UNKNOWN";
        private string v3dTimestampET = "";

        private Brush liveBrush = Brushes.Gray;
        private Brush valueAreaBrush = Brushes.Gray;
        private Brush footprintBrush = Brushes.Gray;
        private Brush biasBrush = Brushes.Gray;
        private Brush tradeLogBrush = Brushes.Gray;
        private Brush panelBrush = Brushes.DimGray;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "V1A/V1B pipeline health monitor. Load once on a leader/support chart.";
                Name = "PipelineMonitor_V1A";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                PaintPriceMarkers = false;
                IsSuspendedWhileInactive = true;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1)
                return;

            if ((DateTime.Now - lastCheck).TotalSeconds >= Math.Max(5, RefreshSeconds))
            {
                lastCheck = DateTime.Now;
                RefreshStatus();
            }

            WriteHudHistoryRow();
            DrawPanel();
        }

        private void RefreshStatus()
        {
            string livePath = Path.Combine(DataFolderPath, @"Exports\NQ_1min_export.txt");
            string valueAreaPath = Path.Combine(DataFolderPath, @"Exports\ValueArea_NQ.csv");
            string footprintPath = Path.Combine(DataFolderPath, @"Active\Footprint_Export.csv");
            string tradeLogDir = Path.Combine(DataFolderPath, @"V1A\TradeLog");

            double liveAge = FileAgeMinutes(livePath);
            if (liveAge < 3)
            {
                liveStatus = "LIVE " + AgeStr(liveAge);
                liveBrush = Brushes.LimeGreen;
            }
            else if (liveAge < 10)
            {
                liveStatus = "WARN " + AgeStr(liveAge);
                liveBrush = Brushes.Gold;
            }
            else
            {
                liveStatus = liveAge >= 9999 ? "MISSING" : "DOWN " + AgeStr(liveAge);
                liveBrush = Brushes.OrangeRed;
            }

            DateTime vaDate = LastCsvDate(valueAreaPath);
            if (vaDate.Date == DateTime.Today)
            {
                valueAreaStatus = "TODAY";
                valueAreaBrush = Brushes.LimeGreen;
            }
            else if (vaDate.Date == DateTime.Today.AddDays(-1))
            {
                valueAreaStatus = "YESTERDAY";
                valueAreaBrush = Brushes.Gold;
            }
            else
            {
                valueAreaStatus = vaDate == DateTime.MinValue ? "MISSING" : vaDate.ToString("yyyy-MM-dd");
                valueAreaBrush = Brushes.OrangeRed;
            }

            int footprintRows = HasDataRows(footprintPath) ? 1 : 0;
            double footprintAge = FileAgeMinutes(footprintPath);
            if (footprintRows > 0 && File.GetLastWriteTime(footprintPath).Date == DateTime.Today)
            {
                footprintStatus = "LIVE Jun 2024+";
                footprintBrush = Brushes.LimeGreen;
            }
            else if (footprintRows > 0)
            {
                footprintStatus = "STALE " + AgeStr(footprintAge);
                footprintBrush = Brushes.Gold;
            }
            else
            {
                footprintStatus = "MISSING/EMPTY";
                footprintBrush = Brushes.OrangeRed;
            }

            try
            {
                string bias = HUDMessenger.CurrentDailyBias;
                biasStatus = string.IsNullOrWhiteSpace(bias) ? "N/A" : bias.Trim();
                biasBrush = biasStatus == "N/A" ? Brushes.Gray : Brushes.DeepSkyBlue;
                playbookStatus = string.IsNullOrWhiteSpace(HUDMessenger.CurrentPlaybook) ? "N/A" : HUDMessenger.CurrentPlaybook.Trim();
                macroHudStatus = string.IsNullOrWhiteSpace(HUDMessenger.CurrentMacroRegime) ? "N/A" : HUDMessenger.CurrentMacroRegime.Trim();
                hmmHudStatus = string.IsNullOrWhiteSpace(HUDMessenger.CurrentHMMRegime) ? "N/A" : HUDMessenger.CurrentHMMRegime.Trim();
            }
            catch
            {
                biasStatus = "N/A";
                biasBrush = Brushes.Gray;
                playbookStatus = "N/A";
                macroHudStatus = "N/A";
                hmmHudStatus = "N/A";
            }

            DateTime tradeLogDate = LatestFileDate(tradeLogDir, "*.csv");
            if (tradeLogDate.Date == DateTime.Today)
            {
                tradeLogStatus = "TODAY";
                tradeLogBrush = Brushes.LimeGreen;
            }
            else if (tradeLogDate.Date == DateTime.Today.AddDays(-1))
            {
                tradeLogStatus = "YESTERDAY";
                tradeLogBrush = Brushes.Gold;
            }
            else
            {
                tradeLogStatus = "NO SESSION LOG";
                tradeLogBrush = Brushes.OrangeRed;
            }

            panelBrush = liveBrush == Brushes.OrangeRed || valueAreaBrush == Brushes.OrangeRed ||
                         footprintBrush == Brushes.OrangeRed || tradeLogBrush == Brushes.OrangeRed
                         ? Brushes.DarkRed
                         : liveBrush == Brushes.Gold || valueAreaBrush == Brushes.Gold ||
                           footprintBrush == Brushes.Gold || tradeLogBrush == Brushes.Gold
                           ? Brushes.DarkGoldenrod
                           : Brushes.DarkGreen;

            RefreshCrossModelRegimes();
        }

        private void DrawPanel()
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("V1A PIPELINE MONITOR");
            sb.AppendLine(StatusDot(liveBrush) + " LIVE FEED    " + liveStatus);
            sb.AppendLine(StatusDot(valueAreaBrush) + " VALUE AREA   " + valueAreaStatus);
            sb.AppendLine(StatusDot(footprintBrush) + " FOOTPRINT    " + footprintStatus);
            sb.AppendLine(StatusDot(biasBrush) + " BIAS         " + biasStatus);
            sb.AppendLine("[I] V1A/B HUD   PB:" + playbookStatus + " M:" + macroHudStatus + " H:" + hmmHudStatus);
            sb.AppendLine("[I] V3C/V3D     " + v3cFinalRegime + " / " + v3dFinalRegime);
            sb.AppendLine(StatusDot(tradeLogBrush) + " TRADE LOG    " + tradeLogStatus);

            Draw.TextFixed(this, "PipelineMonitorV1A_Status", sb.ToString(), TextPosition.TopLeft,
                Brushes.White, panelFont, Brushes.Transparent, panelBrush, 80);
        }

        private string StatusDot(Brush brush)
        {
            if (brush == Brushes.LimeGreen) return "[G]";
            if (brush == Brushes.Gold) return "[Y]";
            if (brush == Brushes.OrangeRed) return "[R]";
            return "[I]";
        }

        private double FileAgeMinutes(string path)
        {
            if (!File.Exists(path))
                return 9999;

            return (DateTime.Now - File.GetLastWriteTime(path)).TotalMinutes;
        }

        private string AgeStr(double mins)
        {
            if (mins >= 9999) return "MISSING";
            if (mins < 1) return "<1m";
            if (mins < 60) return ((int)mins).ToString() + "m";
            return ((int)(mins / 60)).ToString() + "h " + ((int)(mins % 60)).ToString() + "m";
        }

        private bool HasDataRows(string path)
        {
            if (!File.Exists(path))
                return false;

            try
            {
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (StreamReader sr = new StreamReader(fs))
                {
                    int nonEmpty = 0;
                    while (!sr.EndOfStream && nonEmpty < 3)
                    {
                        string line = sr.ReadLine();
                        if (!string.IsNullOrWhiteSpace(line))
                            nonEmpty++;
                    }

                    return nonEmpty >= 2;
                }
            }
            catch
            {
                return false;
            }
        }

        private DateTime LastCsvDate(string path)
        {
            if (!File.Exists(path))
                return DateTime.MinValue;

            try
            {
                string last = "";
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (StreamReader sr = new StreamReader(fs))
                {
                    string line;
                    while ((line = sr.ReadLine()) != null)
                        if (!string.IsNullOrWhiteSpace(line))
                            last = line;
                }

                if (string.IsNullOrWhiteSpace(last) || last.IndexOf(',') < 0)
                    return DateTime.MinValue;

                string first = last.Split(',')[0].Trim();
                DateTime dt;
                return DateTime.TryParse(first, out dt) ? dt : DateTime.MinValue;
            }
            catch
            {
                return DateTime.MinValue;
            }
        }

        private DateTime LatestFileDate(string dir, string pattern)
        {
            if (!Directory.Exists(dir))
                return DateTime.MinValue;

            DateTime latest = DateTime.MinValue;
            foreach (string file in Directory.GetFiles(dir, pattern))
            {
                DateTime t = File.GetLastWriteTime(file);
                if (t > latest)
                    latest = t;
            }

            return latest;
        }

        private void RefreshCrossModelRegimes()
        {
            string sym = GetLeaderSymbol(Instrument.MasterInstrument.Name.ToUpper());

            string v3cPath = Path.Combine(DataFolderPath, "V3C", sym + "_Regimes_V3C_Latest.csv");
            var v3c = ReadLastCsvRow(v3cPath);
            v3cFinalRegime = Get(v3c, "FinalRegime", "UNKNOWN");
            v3cFinalDirection = Get(v3c, "FinalDirection", "UNKNOWN");
            v3cSnapshotTimestamp = Get(v3c, "SnapshotTimestamp", "");

            string v3dPath = Path.Combine(DataFolderPath, "V3D", sym + "_RegimeMatrix_Latest.csv");
            var v3d = ReadLastCsvRow(v3dPath);
            v3dFinalRegime = Get(v3d, "FinalRegime", "UNKNOWN");
            v3dFinalDirection = Get(v3d, "FinalDirection", "UNKNOWN");
            v3dTimestampET = Get(v3d, "TimestampET", "");
        }

        private void WriteHudHistoryRow()
        {
            if (!WriteHudHistoryCsv || CurrentBar < 1 || lastHistoryWriteBar == CurrentBar)
                return;

            lastHistoryWriteBar = CurrentBar;

            try
            {
                string sym = GetLeaderSymbol(Instrument.MasterInstrument.Name.ToUpper());
                string folder = string.IsNullOrWhiteSpace(HudHistoryFolder)
                    ? Path.Combine(DataFolderPath, "V1A", "History", "HUD_Reads")
                    : HudHistoryFolder;
                Directory.CreateDirectory(folder);

                string path = Path.Combine(folder, sym + "_V1AB_HUD_ReadHistory_" + Time[0].ToString("yyyyMMdd") + ".csv");
                bool exists = File.Exists(path);
                if (!exists)
                {
                    File.AppendAllText(path,
                        "TaxonomyVersion,Model,Symbol,Time,Account,Phase,EntryRegime,Dir,Result,Exit,NetPnL,HudReadTimestampLocal,BarTimestamp,CurrentBar,ChartSymbol,LeaderSymbol,V1ABOperatingModel,V1ABDailyBias,V1ABPlaybook,V1ABMacroRegime,V1ABHMMRegime,LiveFeedStatus,ValueAreaStatus,FootprintStatus,TradeLogStatus,ScannerABSFresh,ScannerABSAgeMin,ScannerDDFresh,ScannerDDAgeMin,ScannerTFFresh,ScannerTFAgeMin,ScannerDTFresh,ScannerDTAgeMin,ScannerDEIAFresh,ScannerDEIAAgeMin,ScannerEEMDFFresh,ScannerEEMDFAgeMin,V3CFinalRegime,V3CFinalDirection,V3CSnapshotTimestamp,V3DFinalRegime,V3DFinalDirection,V3DTimestampET\n");
                }

                string line = string.Join(",",
                    Csv("HUD_TAXONOMY_V1"),
                    Csv("V1A_V1B_PIPELINE"),
                    Csv(sym),
                    Csv(Time[0].ToString("HH:mm")),
                    Csv(""),
                    Csv(PhaseForTime(Time[0])),
                    Csv("SELF_GATED_NO_MATRIX_REGIME"),
                    Csv(""),
                    Csv(""),
                    Csv(""),
                    Csv(""),
                    Csv(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")),
                    Csv(Time[0].ToString("yyyy-MM-dd HH:mm:ss")),
                    Csv(CurrentBar.ToString()),
                    Csv(Instrument.MasterInstrument.Name),
                    Csv(sym),
                    Csv("V1A/V1B_SELF_GATED_NO_MATRIX_REGIME"),
                    Csv(biasStatus),
                    Csv(playbookStatus),
                    Csv(macroHudStatus),
                    Csv(hmmHudStatus),
                    Csv(liveStatus),
                    Csv(valueAreaStatus),
                    Csv(footprintStatus),
                    Csv(tradeLogStatus),
                    Csv(IsSignalFreshText("Scanner_ABS", 3)),
                    Csv(SignalAgeText("Scanner_ABS")),
                    Csv(IsSignalFreshText("Scanner_DD", 3)),
                    Csv(SignalAgeText("Scanner_DD")),
                    Csv(IsSignalFreshText("Scanner_TF", 3)),
                    Csv(SignalAgeText("Scanner_TF")),
                    Csv(IsSignalFreshText("Scanner_DT", 1)),
                    Csv(SignalAgeText("Scanner_DT")),
                    Csv(IsSignalFreshText("Scanner_DEIA", 1)),
                    Csv(SignalAgeText("Scanner_DEIA")),
                    Csv(IsSignalFreshText("Scanner_EEMDF", 1)),
                    Csv(SignalAgeText("Scanner_EEMDF")),
                    Csv(v3cFinalRegime),
                    Csv(v3cFinalDirection),
                    Csv(v3cSnapshotTimestamp),
                    Csv(v3dFinalRegime),
                    Csv(v3dFinalDirection),
                    Csv(v3dTimestampET));

                File.AppendAllText(path, line + "\n");
            }
            catch (Exception ex)
            {
                Print("PipelineMonitor_V1A HUD history write error: " + ex.Message);
            }
        }

        private string IsSignalFreshText(string key, double maxMinutes)
        {
            try
            {
                return HUDMessengerV1B.IsSignalFresh(key, Time[0], maxMinutes).ToString();
            }
            catch
            {
                return "False";
            }
        }

        private string SignalAgeText(string key)
        {
            try
            {
                DateTime t;
                if (!HUDMessengerV1B.SharedSignalMap.TryGetValue(key, out t) || t == DateTime.MinValue)
                    return "";
                double age = (Time[0] - t).TotalMinutes;
                return age.ToString("F2");
            }
            catch
            {
                return "";
            }
        }

        private Dictionary<string, string> ReadLastCsvRow(string path)
        {
            var row = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            if (!File.Exists(path))
                return row;

            try
            {
                string header = "";
                string last = "";
                using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (StreamReader sr = new StreamReader(fs))
                {
                    header = sr.ReadLine();
                    string line;
                    while ((line = sr.ReadLine()) != null)
                        if (!string.IsNullOrWhiteSpace(line))
                            last = line;
                }

                if (string.IsNullOrWhiteSpace(header) || string.IsNullOrWhiteSpace(last))
                    return row;

                string[] headers = SplitCsvLine(header);
                string[] values = SplitCsvLine(last);
                for (int i = 0; i < headers.Length && i < values.Length; i++)
                    if (!row.ContainsKey(headers[i].Trim()))
                        row.Add(headers[i].Trim(), values[i].Trim());
            }
            catch
            {
            }

            return row;
        }

        private string[] SplitCsvLine(string line)
        {
            System.Collections.Generic.List<string> result = new System.Collections.Generic.List<string>();
            bool inQuotes = false;
            string current = "";

            for (int i = 0; i < line.Length; i++)
            {
                char c = line[i];
                if (c == '"')
                {
                    if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
                    {
                        current += '"';
                        i++;
                    }
                    else
                    {
                        inQuotes = !inQuotes;
                    }
                }
                else if (c == ',' && !inQuotes)
                {
                    result.Add(current);
                    current = "";
                }
                else
                {
                    current += c;
                }
            }

            result.Add(current);
            return result.ToArray();
        }

        private string Get(Dictionary<string, string> row, string key, string fallback)
        {
            if (row != null && row.ContainsKey(key))
                return row[key];
            return fallback;
        }

        private string Csv(string value)
        {
            if (value == null)
                value = "";
            return "\"" + value.Replace("\"", "\"\"") + "\"";
        }

        private string PhaseForTime(DateTime t)
        {
            int hm = t.Hour * 100 + t.Minute;
            if (hm < 930) return "PREMARKET";
            if (hm < 945) return "OPENING_AUCTION";
            if (hm < 1010) return "EARLY_TEST";
            if (hm < 1030) return "END_FIRST_WINDOW";
            if (hm < 1100) return "PRE_IB_MATURATION";
            if (hm < 1200) return "MID_MORNING_DISCOVERY";
            if (hm < 1300) return "LUNCH_AUCTION";
            if (hm < 1400) return "POST_LUNCH_ROTATION";
            if (hm < 1530) return "AFTERNOON_TREND_TEST";
            if (hm < 1600) return "LATE_DAY_CONVICTION";
            return "CASH_CLOSE";
        }

        private string GetLeaderSymbol(string sym)
        {
            if (sym.Contains("MNQ")) return "NQ";
            if (sym.Contains("MES")) return "ES";
            if (sym.Contains("NQ")) return "NQ";
            if (sym.Contains("ES")) return "ES";
            return sym;
        }
    }
}
