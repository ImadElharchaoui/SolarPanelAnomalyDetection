"""
label_real_data.py
==================
Reads  : resource/TrueDataUnstructured.json   (raw datalogger dumps)
Writes : resource/TrueSamples.csv             (labelled 30-day samples)

Fault detection logic follows the
"Solar Street Light — Datalogger Fault Detection Reference"
internal document dated April 16 2026.

Each sample (one datalogger JSON object with a "daily" array) is analysed
as a whole and assigned exactly ONE label.  Priority (most unambiguous
first):
    F-05 → F-01 → F-06b → F-06a → F-03 → F-02 → F-04 → Normal
"""

import json
import os
import re

import numpy as np
import pandas as pd


# ====================================================================== #
#  JSON PARSING                                                          #
# ====================================================================== #

def extract_all_samples(content: str) -> list:
    """
    Return a list of raw sample dicts from the JSON file.
    Handles: a JSON array, a single object, or concatenated objects.
    """
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        print("Standard JSON parsing failed — using robust extraction …")

    # Fallback: find every top-level {"datalogger" … } block
    starts = [m.start() for m in re.finditer(r'\{"datalogger"', content)]
    samples = []
    for s in starts:
        depth = 0
        for i in range(s, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        samples.append(json.loads(content[s:i + 1]))
                    except Exception:
                        pass
                    break
    return samples


# ====================================================================== #
#  SAMPLE → DATAFRAME                                                    #
# ====================================================================== #

def sample_to_dataframe(sample: dict, sample_id: str) -> pd.DataFrame | None:
    """
    Convert one datalogger object into a tidy DataFrame.
    Returns None when there are fewer than 15 usable days.
    """
    datalogger = sample.get("datalogger", {})
    daily_list = datalogger.get("daily", [])

    if len(daily_list) < 15:
        return None

    rows = []
    for d in daily_list:
        flags = d.get("flags", {})
        rows.append({
            "Sample_ID":    sample_id,
            "Day":          d.get("day", 0),
            "VBat_Min_V":   d.get("vbat_min_mv", 0) / 1000.0,
            "VBat_Max_V":   d.get("vbat_max_mv", 0) / 1000.0,
            "Ah_Charge_Ah": d.get("ah_charge_mah", 0) / 1000.0,
            "Ah_Load_Ah":   d.get("ah_load_mah", 0) / 1000.0,
            "VPv_Max_V":    d.get("vpv_max_mv", 0) / 1000.0,
            "IPv_Max_A":    d.get("ipv_max_ma", 0) / 1000.0,
            "SOC_Pct":      d.get("soc_pct", 0) * 6.6,
            "Temp_Max_C":   d.get("ext_temp_max_c", 0),
            "Temp_Min_C":   d.get("ext_temp_min_c", 0),
            "Night_Min":    d.get("nightlength_min", 0),
            # keep controller flags — useful for F-01 / F-04
            "flag_ld":      bool(flags.get("ld", False)),    # load disconnection
            "flag_lsoc":    bool(flags.get("lsoc", False)),  # low SoC
            "flag_bov":     bool(flags.get("bov", False)),   # battery over-voltage
        })

    df = pd.DataFrame(rows).sort_values("Day").reset_index(drop=True)
    return df


# ====================================================================== #
#  FAULT DETECTION (per-sample, one label)                               #
# ====================================================================== #

# ---- tuneable thresholds (from PDF + domain knowledge) ----------------
VBAT_LOW_THRESHOLD       = 11.5   # V  — deep-discharge cut-off
SOC_PEAK_THRESHOLD       = 80.0   # %  — expected daily SoC peak
CHARGE_NEAR_ZERO         = 0.5    # Ah — "no meaningful charge"
DELTA_SOC_FLAT           = 3.0    # %  — "SoC did not move"
TEMP_OVERTEMP            = 45.0   # °C — F-06b trigger
CHARGE_DROP_RATIO        = 0.70   # current day < 70% of previous day
SOC_TREND_SLOPE          = -0.3   # %/day — F-06a declining SoC
CHARGE_TREND_SLOPE       = -0.05  # Ah/day — F-06a shortening charge
SOC_LOW_THRESHOLD        = 30.0   # %  — "chronically low SoC"
PV_CURRENT_LOW           = 2.0    # A  — "low PV current"
WARM_DAY_TEMP            = 25.0   # °C — proxy: clear sky
SOC_STD_STABLE           = 8.0    # %  — night SoC "abnormally stable"
LOAD_HIGH_THRESHOLD      = 8.0    # Ah — "high nightly load"


def detect_fault(df: pd.DataFrame) -> str:
    """
    Analyse the full sample window and return exactly one fault label.
    Priority: F-05 → F-01 → F-06b → F-06a → F-03 → F-02 → F-04 → Normal
    """
    n = len(df)

    # ── F-05  Burnt Fuse / Total Power Loss ───────────────────────────
    # PDF: "All telemetry channels return null, zero, or last-known value
    #        for 24 h or more … Persistent zero on all channels for
    #        multiple cycles strongly indicates fuse failure."
    all_zero = (
        (df["Ah_Charge_Ah"] == 0).all()
        and (df["Ah_Load_Ah"] == 0).all()
        and (df["SOC_Pct"] == 0).all()
    )
    if all_zero:
        return "F-05 Burnt Fuse / Total Power Loss"

    # ── F-01  Controller Bug Upon Battery Depletion ───────────────────
    # PDF: "FLAG if Vbat ≤ low_threshold AND load_disconnected during
    #        Night N, AND ΔSoC ≈ 0 throughout the following day window."
    f01_hits = 0
    for i in range(1, n):
        prev = df.iloc[i - 1]
        cur  = df.iloc[i]

        battery_depleted = prev["VBat_Min_V"] < VBAT_LOW_THRESHOLD
        load_disconnected = prev["flag_ld"]             # ld flag on night N
        pv_available      = cur["VPv_Max_V"] > 12.0     # sun is there
        charge_absent     = cur["Ah_Charge_Ah"] < CHARGE_NEAR_ZERO
        soc_flat          = abs(cur["SOC_Pct"] - prev["SOC_Pct"]) < DELTA_SOC_FLAT

        if battery_depleted and (load_disconnected or prev["flag_lsoc"]):
            if pv_available and charge_absent and soc_flat:
                f01_hits += 1

    if f01_hits >= 1:
        return "F-01 Controller Bug Upon Battery Depletion"

    # ── F-06b  Battery Over-Temperature / Thermal Runaway Risk ────────
    # PDF: "FLAG if T_battery > 45 °C during charge phase AND
    #        charge_current drops anomalously."
    f06b_hits = 0
    for i in range(1, n):
        prev = df.iloc[i - 1]
        cur  = df.iloc[i]

        overtemp = cur["Temp_Max_C"] > TEMP_OVERTEMP
        charge_drop = (
            prev["Ah_Charge_Ah"] > CHARGE_NEAR_ZERO
            and cur["Ah_Charge_Ah"] < prev["Ah_Charge_Ah"] * CHARGE_DROP_RATIO
        )
        if overtemp and charge_drop:
            f06b_hits += 1

    if f06b_hits >= 2:
        return "F-06b Battery Over-Temperature / Thermal Runaway Risk"

    # ── F-06a  Battery End of Life / Accelerated Degradation ──────────
    # PDF: "FLAG via trend analysis over a rolling window (e.g. 30 days).
    #        Flag if SoC_peak_trend is declining AND
    #        nightly_discharge_rate is increasing."
    days          = np.arange(n)
    soc_values    = df["SOC_Pct"].values.astype(float)
    charge_values = df["Ah_Charge_Ah"].values.astype(float)

    soc_slope    = np.polyfit(days, soc_values,    1)[0]
    charge_slope = np.polyfit(days, charge_values, 1)[0]

    if soc_slope < SOC_TREND_SLOPE and charge_slope < CHARGE_TREND_SLOPE:
        return "F-06a Battery End of Life / Accelerated Degradation"

    # ── pre-compute shared metrics for F-02 / F-03 ────────────────────
    low_soc_days = (df["SOC_Pct"]   < SOC_LOW_THRESHOLD).sum()
    low_pv_days  = (df["IPv_Max_A"] < PV_CURRENT_LOW).sum()
    pv_low_ratio = low_pv_days / n
    soc_peak     = df["SOC_Pct"].max()

    # ── F-03  Low Battery SoC — PV Module or Connection Issue ─────────
    # PDF: "FLAG if PV_current < baseline AND SoC_peak < threshold
    #        AND weather = clear_sky."
    # Proxy: warm days → likely clear sky.
    warm_days = (df["Temp_Max_C"] > WARM_DAY_TEMP).sum()

    if (low_soc_days >= n * 0.5
            and pv_low_ratio >= 0.5
            and warm_days >= n * 0.5
            and soc_peak < SOC_PEAK_THRESHOLD):
        return "F-03 Low Battery SoC — PV Module or Connection Issue"

    # ── F-02  Low Battery SoC — Weather Conditions ────────────────────
    # PDF: "FLAG if PV_current < sunny_day_baseline AND SoC_peak <
    #        threshold AND weather_data confirms overcast/rain."
    # Proxy: cool/mild days → likely overcast.
    cool_days = (df["Temp_Max_C"] <= WARM_DAY_TEMP).sum()

    if (low_soc_days >= n * 0.5
            and pv_low_ratio >= 0.5
            and cool_days >= n * 0.4
            and soc_peak < SOC_PEAK_THRESHOLD):
        return "F-02 Low Battery SoC — Weather Conditions"

    # ── F-04  LED Blinking / Load Oscillation ─────────────────────────
    # PDF: "FLAG if … ΔSoC_night < expected_discharge_range while
    #        load events are logged.  A significant downward discrepancy
    #        [in nightly consumption] combined with SoC stability is the
    #        key indicator."
    high_load_days = (df["Ah_Load_Ah"] > LOAD_HIGH_THRESHOLD).sum()
    soc_std        = df["SOC_Pct"].std()

    if high_load_days >= n * 0.4 and soc_std < SOC_STD_STABLE:
        return "F-04 LED Blinking / Load Oscillation"

    # ── Normal ────────────────────────────────────────────────────────
    return "Normal Status"


# ====================================================================== #
#  PIPELINE                                                              #
# ====================================================================== #

def run(input_file: str, output_file: str):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    raw_samples = extract_all_samples(content)
    print(f"Found {len(raw_samples)} potential samples. Processing …")

    results: list[pd.DataFrame] = []

    for i, sample in enumerate(raw_samples):
        sid = f"Sample_{i + 1}"
        df = sample_to_dataframe(sample, sid)

        if df is None:
            print(f"  [{sid}] Skipped — fewer than 15 days of data.")
            continue

        label = detect_fault(df)

        # Drop internal flag columns before export (not model features)
        df = df.drop(columns=["flag_ld", "flag_lsoc", "flag_bov"])
        df["Fault_Label"] = label
        results.append(df)
        print(f"  [{sid}] {len(df):>3d} days -> {label}")

    if not results:
        print("No valid samples with ≥15 days found.")
        return

    combined = pd.concat(results, ignore_index=True)
    combined.to_csv(output_file, index=False)
    print(f"\nProcessed {len(results)} samples -> {len(combined)} rows")
    print(f"Output saved to: {output_file}")

    # ── summary ───────────────────────────────────────────────────────
    print("\n--- Label Distribution ---")
    dist = (combined.groupby("Fault_Label")["Sample_ID"]
                    .nunique()
                    .sort_values(ascending=False))
    for label, count in dist.items():
        print(f"  {label:<60s} {count:>4d} samples")
    print(f"  {'TOTAL':<60s} {dist.sum():>4d} samples")


# ====================================================================== #
#  ENTRY POINT                                                           #
# ====================================================================== #

if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..")
    INPUT_FILE  = os.path.join(base, "resource", "TrueDataUnstructured.json")
    OUTPUT_FILE = os.path.join(base, "resource", "TrueSamples.csv")

    run(INPUT_FILE, OUTPUT_FILE)
