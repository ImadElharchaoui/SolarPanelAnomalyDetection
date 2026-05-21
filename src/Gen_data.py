"""
Gen_data.py — Realistic Synthetic Anomaly Generator
=====================================================
KEY CHANGE: instead of building data from fake baselines,
we load REAL normal sequences from TrueSamples.csv and
inject fault signatures into copies of them.

This ensures the training data shares the same feature
distribution as the real validation data.
"""

import pandas as pd
import numpy as np
import random
import os

# ==========================================
# GLOBAL SETTINGS
# ==========================================
N_SAMPLES_PER_TYPE = 2000
OUTPUT_FILE = "resource/GenData_Samples.csv"
TRUE_DATA_PATH = "resource/TrueSamples.csv"


def load_real_normal_sequences(path: str, sample_size: int = 30) -> list:
    """
    Load real 'Normal Status' 30-day sequences from TrueSamples.csv.
    Returns a list of DataFrames, each with exactly `sample_size` rows.
    """
    df = pd.read_csv(path)
    normal = df[df["Fault_Label"] == "Normal Status"]

    sequences = []
    for _, group in normal.groupby("Sample_ID"):
        if len(group) == sample_size:
            # Keep only numeric feature columns (drop Sample_ID, Fault_Label)
            feat = group[["Day", "VBat_Min_V", "VBat_Max_V", "Ah_Charge_Ah",
                          "Ah_Load_Ah", "VPv_Max_V", "IPv_Max_A", "SOC_Pct",
                          "Temp_Max_C", "Temp_Min_C", "Night_Min"]].copy()
            feat = feat.reset_index(drop=True)
            # Ensure all numeric columns are float to avoid int/float conflicts
            for c in feat.columns:
                if c != "Day":
                    feat[c] = feat[c].astype(float)
            sequences.append(feat)

    if not sequences:
        raise RuntimeError(f"No valid Normal 30-day sequences found in {path}")

    return sequences


def pick_base_sequence(pool: list) -> pd.DataFrame:
    """Return a deep copy of a random real normal sequence."""
    return pool[random.randint(0, len(pool) - 1)].copy()


# ==========================================
# FAULT INJECTION FUNCTIONS
# ==========================================
# Each takes a real normal DataFrame and mutates it
# to simulate the fault pattern described in the PDF.

def inject_normal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normal — add small random noise so the model sees
    realistic normal variation, not identical copies.
    """
    for col in ["VBat_Min_V", "VBat_Max_V", "Ah_Charge_Ah", "Ah_Load_Ah",
                "VPv_Max_V", "IPv_Max_A", "SOC_Pct"]:
        noise = np.random.normal(0, df[col].std() * 0.05, size=len(df))
        df[col] = df[col] + noise
    return df


def inject_f01(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-01 Controller Bug Upon Battery Depletion
    Night N: battery drops to minimum, load disconnection.
    Day N+1 onward: charge ≈ 0 despite sun, SOC flat.
    """
    trigger_day = random.randint(3, 12)

    # Night N: force battery depletion
    df.loc[trigger_day, "VBat_Min_V"] = random.uniform(10.0, 11.2)
    df.loc[trigger_day, "SOC_Pct"] = random.uniform(0, 4)

    # Day N+1 onward: controller locked, no charge
    for d in range(trigger_day + 1, len(df)):
        df.loc[d, "Ah_Charge_Ah"] = random.uniform(0, 0.3)
        # SOC stays flat (tiny random walk around previous value)
        prev_soc = df.loc[d - 1, "SOC_Pct"]
        df.loc[d, "SOC_Pct"] = max(0, prev_soc + random.uniform(-1, 1))
        # VPv still present (sun is shining)
        # keep existing VPv_Max_V and IPv_Max_A from real data

    return df


def inject_f02(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-02 Low Battery SoC — Weather Conditions
    Prolonged low PV current due to bad weather -> chronically low SOC.
    """
    for d in range(len(df)):
        # Reduce PV current significantly (overcast/rain)
        df.loc[d, "IPv_Max_A"] *= random.uniform(0.1, 0.35)
        df.loc[d, "Ah_Charge_Ah"] *= random.uniform(0.15, 0.4)
        # SOC drops over time
        if d > 0:
            prev_soc = df.loc[d - 1, "SOC_Pct"]
            delta = random.uniform(-4, -0.5)
            df.loc[d, "SOC_Pct"] = max(0, min(100, prev_soc + delta))

    return df


def inject_f03(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-03 Low Battery SoC — PV Module or Connection Issue
    PV current is low DESPITE warm/sunny conditions.
    """
    for d in range(len(df)):
        # Drastically cut PV current (hardware fault)
        df.loc[d, "IPv_Max_A"] *= random.uniform(0.05, 0.3)
        df.loc[d, "VPv_Max_V"] *= random.uniform(0.6, 0.85)
        df.loc[d, "Ah_Charge_Ah"] *= random.uniform(0.1, 0.35)
        # Keep warm temperatures (clear sky proxy)
        df.loc[d, "Temp_Max_C"] = max(df.loc[d, "Temp_Max_C"],
                                       random.uniform(26, 38))
        # SOC declines
        if d > 0:
            prev_soc = df.loc[d - 1, "SOC_Pct"]
            delta = random.uniform(-5, -1)
            df.loc[d, "SOC_Pct"] = max(0, min(100, prev_soc + delta))

    return df


def inject_f04(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-04 LED Blinking / Load Oscillation
    High load events logged, but SOC abnormally stable (load oscillation).
    """
    # Inflate nightly load
    for d in range(len(df)):
        df.loc[d, "Ah_Load_Ah"] = random.uniform(9, 25)

    # Make SOC abnormally stable (std < 8)
    base_soc = df["SOC_Pct"].iloc[0]
    for d in range(len(df)):
        df.loc[d, "SOC_Pct"] = base_soc + random.uniform(-3, 3)

    return df


def inject_f05(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-05 Burnt Fuse / Total Power Loss
    All channels zero for the entire window.
    But we keep realistic temperatures (physical environment still exists).
    """
    for col in ["Ah_Charge_Ah", "Ah_Load_Ah", "SOC_Pct",
                "IPv_Max_A", "VPv_Max_V"]:
        df[col] = 0.0

    # Battery voltage drops to 0 over first few days
    for d in range(len(df)):
        decay = max(0, 1.0 - d * 0.15)
        df.loc[d, "VBat_Min_V"] *= decay
        df.loc[d, "VBat_Max_V"] *= decay

    return df


def inject_f06a(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-06a Battery End of Life / Accelerated Degradation
    SOC trend declining, charge capacity shrinking over the window.
    """
    for d in range(len(df)):
        aging = 1.0 - (d / len(df)) * random.uniform(0.25, 0.5)
        df.loc[d, "Ah_Charge_Ah"] *= aging
        # SOC declines steadily
        if d > 0:
            prev_soc = df.loc[d - 1, "SOC_Pct"]
            delta = random.uniform(-2.5, -0.3)
            df.loc[d, "SOC_Pct"] = max(0, min(100, prev_soc + delta))

    return df


def inject_f06b(df: pd.DataFrame) -> pd.DataFrame:
    """
    F-06b Battery Over-Temperature / Thermal Runaway Risk
    Temperature spikes > 45°C during charge, charge current drops.
    """
    spike_days = sorted(random.sample(range(len(df)), k=min(8, len(df))))

    for d in spike_days:
        df.loc[d, "Temp_Max_C"] = random.uniform(46, 62)
        df.loc[d, "Temp_Min_C"] = random.uniform(35, 45)
        # Charge drops when overtemp
        df.loc[d, "Ah_Charge_Ah"] *= random.uniform(0.1, 0.4)
        df.loc[d, "IPv_Max_A"] *= random.uniform(0.1, 0.3)

    return df


# ==========================================
# MAP: fault name -> injector function
# ==========================================
FAULT_INJECTORS = {
    "Normal Status":              inject_normal,
    "F-01 Controller Bug":        inject_f01,
    "F-02 Low SoC (Weather)":     inject_f02,
    "F-03 PV Issue":              inject_f03,
    "F-04 Load Oscillation":      inject_f04,
    "F-05 Total Power Loss":      inject_f05,
    "F-06a Battery Aging Trend":  inject_f06a,
    "F-06b Thermal Risk":         inject_f06b,
}


# ==========================================
# MAIN
# ==========================================

def run_generation():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    true_path = os.path.join(base_dir, TRUE_DATA_PATH)
    out_path = os.path.join(base_dir, OUTPUT_FILE)

    print("[1/3] Loading real normal sequences …")
    pool = load_real_normal_sequences(true_path)
    print(f"      Found {len(pool)} valid 30-day normal sequences.")

    all_samples = []
    print(f"[2/3] Generating {N_SAMPLES_PER_TYPE} samples per fault …")

    for fault_label, injector in FAULT_INJECTORS.items():
        for i in range(N_SAMPLES_PER_TYPE):
            base = pick_base_sequence(pool)
            modified = injector(base)
            modified["Fault_Label"] = fault_label
            modified["Sample_ID"] = f"{fault_label.split()[0]}_{i + 1}"
            all_samples.append(modified)

        print(f"      {fault_label}: {N_SAMPLES_PER_TYPE} samples")

    full_df = pd.concat(all_samples, ignore_index=True)

    columns_order = ["Sample_ID", "Day", "VBat_Min_V", "VBat_Max_V",
                     "Ah_Charge_Ah", "Ah_Load_Ah", "VPv_Max_V", "IPv_Max_A",
                     "SOC_Pct", "Temp_Max_C", "Temp_Min_C", "Night_Min",
                     "Fault_Label"]
    full_df = full_df[columns_order]

    print(f"[3/3] Done. Total rows: {len(full_df)}")
    full_df.to_csv(out_path, index=False)
    return full_df


if __name__ == "__main__":
    df = run_generation()
    print("\nPreview:")
    print(df.head(10))
