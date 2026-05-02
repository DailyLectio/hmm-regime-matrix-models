# V1B Architecture — Pre-Code Notes

## Conflict Analysis

### No conflicts found. Reasons:

1. OrderFlowSetupScanner writes ONLY to HUDMessenger.SharedSignalMap (timestamps)
   and HUDMessenger.CurrentDailyBias. The three V1A strategies do not currently
   read either of these. Adding reads is purely additive.

2. The Scanner fires at OnBarClose. Strategies reading timestamps via SharedSignalMap
   check freshness by elapsed minutes — no bar-index dependency.

3. KalmanPulse runs OnEachTick. The timestamp freshness check is identical —
   it reads Time[0] vs the stored DateTime, not CurrentBar. No conflict.

4. The A/B switch (RequireFootprintConfirmation bool) means V1A behavior is
   fully preserved when false. Both can run simultaneously on the same chart
   with different parameter sets for parallel testing.

---

## Gap: DEIA and EEMDF NOT Broadcast to HUDMessenger

The scanner currently broadcasts to SharedSignalMap:
  Scanner_SIB, Scanner_ABS, Scanner_DD, Scanner_TF, Scanner_DT

It does NOT broadcast:
  Scanner_DEIA, Scanner_EEMDF, Scanner_PAR, Scanner_DEB

### Required patch to OrderFlowSetupScanner.cs broadcast block (~line 266-276):

BEFORE:
    if (sig.Name.Contains("SIB")) HUDMessenger.SharedSignalMap["Scanner_SIB"] = Time[0];
    if (sig.Name.Contains("ABS")) HUDMessenger.SharedSignalMap["Scanner_ABS"] = Time[0];
    if (sig.Name.Contains("DD"))  HUDMessenger.SharedSignalMap["Scanner_DD"]  = Time[0];
    if (sig.Name.Contains("TF"))  HUDMessenger.SharedSignalMap["Scanner_TF"]  = Time[0];
    if (sig.Name.Contains("DT"))  HUDMessenger.SharedSignalMap["Scanner_DT"]  = Time[0];

AFTER (add 4 lines):
    if (sig.Name.Contains("SIB"))  HUDMessenger.SharedSignalMap["Scanner_SIB"]  = Time[0];
    if (sig.Name.Contains("ABS"))  HUDMessenger.SharedSignalMap["Scanner_ABS"]  = Time[0];
    if (sig.Name.Contains("DD"))   HUDMessenger.SharedSignalMap["Scanner_DD"]   = Time[0];
    if (sig.Name.Contains("TF"))   HUDMessenger.SharedSignalMap["Scanner_TF"]   = Time[0];
    if (sig.Name.Contains("DT"))   HUDMessenger.SharedSignalMap["Scanner_DT"]   = Time[0];
    if (sig.Name.Contains("DEIA")) HUDMessenger.SharedSignalMap["Scanner_DEIA"] = Time[0];   // ADD
    if (sig.Name.Contains("EEMDF"))HUDMessenger.SharedSignalMap["Scanner_EEMDF"]= Time[0];   // ADD
    if (sig.Name.Contains("PAR"))  HUDMessenger.SharedSignalMap["Scanner_PAR"]  = Time[0];   // ADD
    if (sig.Name.Contains("DEB"))  HUDMessenger.SharedSignalMap["Scanner_DEB"]  = Time[0];   // ADD

NOTE: "DEIA" must be checked BEFORE "DD" to prevent partial string match,
OR use sig.Name == "DEIA" instead of Contains. The current Contains("DD") check
would match "DEIA" if checked first. In the scanner source DEIA and DD are
separate signal names, so Contains("DD") does NOT match "DEIA" — safe as-is.

---

## Signal-to-Strategy Assignment Table

| Signal | Category | S1 VolState Fader | S2 KalmanPulse Fader | S3 CompositeEdge Momentum |
|--------|----------|-------------------|----------------------|--------------------------|
| ABS    | Reversal | Entry confirm     | Entry confirm        | —                        |
| DD     | Reversal | Entry confirm     | Entry confirm        | —                        |
| TF     | Reversal | Entry confirm     | Entry confirm        | —                        |
| DT     | Reversal | Kill switch       | Kill switch          | Kill switch (strong)     |
| SIB    | Continuation | —             | —                    | Entry confirm            |
| DEB    | Continuation | —             | —                    | Entry confirm            |
| PAR    | Continuation | —             | —                    | Entry confirm (pullback) |
| DEIA   | Extreme  | Kill switch       | Kill switch          | Kill switch              |
| EEMDF  | Extreme  | Kill switch       | Kill switch          | Kill switch              |

---

## Daily Bias Routing (HUDMessenger.CurrentDailyBias)

| Bias | Day Shape | S1 VolState (Fader) | S2 KalmanPulse (Fader) | S3 Momentum |
|------|-----------|---------------------|------------------------|-------------|
| D    | Rotation  | Both sides allowed  | Both sides allowed     | BLOCKED     |
| P    | Bull Trend| Long fades only     | Long fades only        | Long only   |
| b    | Bear Trend| Short fades only    | Short fades only       | Short only  |
| B    | Breakout  | BLOCKED             | BLOCKED                | Both sides  |
| (unset/unknown) | — | Both sides | Both sides          | Both sides  |

---

## A/B Test Parameters (same param controls the switch)

Parameter: RequireFootprintConfirmation (bool, default false)
  false = V1A behavior (all footprint gates pass automatically)
  true  = V1B behavior (entry requires fresh orderflow signal within window)

Both Kill Switch and Daily Bias Filter are independent bools that apply
regardless of A/B mode. This lets you test:
  - Pure V1A: RequireFootprint=false, EnableKillSwitch=false, EnableBiasFilter=false
  - V1A + Kill+Bias: RequireFootprint=false, EnableKillSwitch=true, EnableBiasFilter=true
  - Full V1B: RequireFootprint=true, EnableKillSwitch=true, EnableBiasFilter=true
