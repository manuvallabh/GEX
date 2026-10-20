// LevelExporter.cs -- NinjaTrader 8 NinjaScript indicator.
//
// Writes a small JSON file every time a bar closes, with session
// POC/VAH/VAL (approximated from a price/volume histogram), cumulative
// delta (approximated from close-vs-open direction -- NOT true bid/ask
// delta), and overnight/session high-low. The Python side
// (connectors/ninja_connector.py) reads this file and reports it as
// "connected" as long as it's recently updated.
//
// CAVEAT: true order-flow delta needs bid/ask-tagged ticks, which this
// basic Indicator base class does not receive. For real delta, switch
// your chart's Data Series to "Volumetric" bars (Chart properties ->
// select BarsType: Volumetric) and read Bars.GetVolumetricBarsAt(...) /
// the volumetric bar's AskVolume/BidVolume properties instead of the
// Close-vs-Open approximation below (marked with TODO).
//
// Install: copy this file into
//   Documents\NinjaTrader 8\bin\Custom\Indicators\LevelExporter.cs
// then open NinjaScript Editor in NT8, compile (F5), and add
// "LevelExporter" to your ES chart.
//
// Output path must match connectors/ninja_connector.py's
// DEFAULT_EXPORT_PATH: Documents\NinjaTrader 8\bin\Custom\exports\levels.json

#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Globalization;
using System.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class LevelExporter : Indicator
    {
        private readonly Dictionary<double, double> volumeByPrice = new Dictionary<double, double>();
        private double cumulativeDelta;
        private double sessionHigh;
        private double sessionLow;
        private string exportDir;
        private string exportPath;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Exports session POC/VAH/VAL + approx cumulative delta to JSON for an external dashboard.";
                Name = "LevelExporter";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                DisplayInDataBox = false;
                PaintPriceMarkers = false;
                ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
            }
            else if (State == State.Configure)
            {
                string docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                exportDir = Path.Combine(docs, "NinjaTrader 8", "bin", "Custom", "exports");
                exportPath = Path.Combine(exportDir, "levels.json");
                Directory.CreateDirectory(exportDir);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1)
                return;

            if (Bars.IsFirstBarOfSession)
            {
                volumeByPrice.Clear();
                cumulativeDelta = 0;
                sessionHigh = High[0];
                sessionLow = Low[0];
            }

            sessionHigh = Math.Max(sessionHigh, High[0]);
            sessionLow = Math.Min(sessionLow, Low[0]);

            double px = Math.Round(Close[0], 2);
            if (!volumeByPrice.ContainsKey(px))
                volumeByPrice[px] = 0;
            volumeByPrice[px] += Volume[0];

            // TODO: replace with real bid/ask delta from Volumetric bars.
            if (Close[0] > Open[0])
                cumulativeDelta += Volume[0];
            else if (Close[0] < Open[0])
                cumulativeDelta -= Volume[0];

            if (volumeByPrice.Count == 0)
                return;

            var poc = volumeByPrice.OrderByDescending(kv => kv.Value).First();
            double totalVolume = volumeByPrice.Values.Sum();
            double targetVolume = totalVolume * 0.70;

            var sortedByPrice = volumeByPrice.Keys.OrderBy(k => k).ToList();
            double vah = poc.Key, val = poc.Key;
            double accumulated = poc.Value;
            int lowIdx = sortedByPrice.IndexOf(poc.Key);
            int highIdx = lowIdx;

            while (accumulated < targetVolume && (lowIdx > 0 || highIdx < sortedByPrice.Count - 1))
            {
                double volBelow = lowIdx > 0 ? volumeByPrice[sortedByPrice[lowIdx - 1]] : -1;
                double volAbove = highIdx < sortedByPrice.Count - 1 ? volumeByPrice[sortedByPrice[highIdx + 1]] : -1;

                if (volAbove >= volBelow && highIdx < sortedByPrice.Count - 1)
                {
                    highIdx++;
                    vah = sortedByPrice[highIdx];
                    accumulated += volAbove;
                }
                else if (lowIdx > 0)
                {
                    lowIdx--;
                    val = sortedByPrice[lowIdx];
                    accumulated += volBelow;
                }
                else
                {
                    break;
                }
            }

            WriteExport(poc.Key, vah, val, sessionHigh, sessionLow);
        }

        private void WriteExport(double poc, double vah, double val, double high, double low)
        {
            var inv = CultureInfo.InvariantCulture;
            string json = "{"
                + "\"generated_at_utc\":\"" + DateTime.UtcNow.ToString("o", inv) + "\","
                + "\"instrument\":\"" + Instrument.FullName + "\","
                + "\"last\":" + Close[0].ToString(inv) + ","
                + "\"session_high\":" + high.ToString(inv) + ","
                + "\"session_low\":" + low.ToString(inv) + ","
                + "\"poc\":" + poc.ToString(inv) + ","
                + "\"vah\":" + vah.ToString(inv) + ","
                + "\"val\":" + val.ToString(inv) + ","
                + "\"cumulative_delta_approx\":" + cumulativeDelta.ToString(inv)
                + "}";

            try
            {
                File.WriteAllText(exportPath, json);
            }
            catch (IOException)
            {
                // Another write in progress; next bar will retry.
            }
        }
    }
}
