"""
test_daily_check_simulation.py – Simulates daily ESP32 telemetry checks
========================================================================

Reads a CSV file row by row (one row = one day) and feeds each day's data
into run_daily_check() with a configurable delay between days.

CSV must contain these columns:
    Ah_Charge_Ah, Ah_Load_Ah, Day, IPv_Max_A, Night_Min,
    SOC_Pct, Temp_Max_C, Temp_Min_C, VBat_Max_V, VBat_Min_V, VPv_Max_V

Usage:
    python test_daily_check_simulation.py
    python test_daily_check_simulation.py --csv path/to/data.csv --delay 2.0
    python test_daily_check_simulation.py --serial ESP32_TEST_02 --delay 0
    python test_daily_check_simulation.py --json
"""

import os
import sys
import time
import json
import argparse
import traceback
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these paths to match your environment
# ──────────────────────────────────────────────────────────────────────────────

# Path to the CSV file containing historical telemetry rows
CSV_FILE_PATH = os.path.join(os.path.dirname(__file__), "solar_telemetry.csv")

# Delay in seconds between each simulated day (0 = run as fast as possible)
DEFAULT_DELAY_SECONDS = 1.0

# Serial number used for all simulated records
DEFAULT_SERIAL_NUMBER = "ESP32_SIM_01"

# Path to SQLite DB (None = default next to daily_check.py)
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "sim_device_history.db")

# Path to model directory (None = auto-detect)
DEFAULT_MODEL_DIR = None

# ──────────────────────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = [
    "Ah_Charge_Ah", "Ah_Load_Ah", "Day", "IPv_Max_A", "Night_Min",
    "SOC_Pct", "Temp_Max_C", "Temp_Min_C", "VBat_Max_V", "VBat_Min_V", "VPv_Max_V"
]

# Map CSV column names → flat dict keys that process_parsed_data() understands
CSV_TO_FLAT = {
    "Ah_Charge_Ah": "Ah_Charge_Ah",
    "Ah_Load_Ah":   "Ah_Load_Ah",
    "IPv_Max_A":    "IPv_Max_A",
    "Night_Min":    "Night_Min",
    "SOC_Pct":      "SOC_Pct",
    "Temp_Max_C":   "Temp_Max_C",
    "Temp_Min_C":   "Temp_Min_C",
    "VBat_Max_V":   "VBat_Max_V",
    "VBat_Min_V":   "VBat_Min_V",
    "VPv_Max_V":    "VPv_Max_V",
}


def load_csv(path: str) -> pd.DataFrame:
    """Loads and validates the CSV file."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"CSV file not found: '{path}'\n"
            f"Set CSV_FILE_PATH at the top of this script or use --csv."
        )

    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {missing}\n"
            f"Found columns: {list(df.columns)}"
        )

    # Sort by Day column so simulation runs chronologically
    if "Day" in df.columns:
        df = df.sort_values("Day").reset_index(drop=True)

    return df


def row_to_daily_dict(row: pd.Series) -> dict:
    """
    Converts one CSV row into the flat dict format that
    run_daily_check / process_parsed_data accepts.
    """
    return {flat_key: float(row[csv_col])
            for csv_col, flat_key in CSV_TO_FLAT.items()
            if csv_col in row.index}


def print_result(day_num: int, csv_day: int, result: dict, json_mode: bool) -> None:
    """Prints inference result for one simulated day."""
    if json_mode:
        payload = {"sim_day": day_num, "csv_day": int(csv_day), **result}
        print(json.dumps(payload, indent=2))
        return

    device = result["device"]
    pred   = result["prediction"]
    label  = pred["anomaly_label"]
    conf   = pred["confidence"] * 100

    # Colour-code confidence
    if conf >= 80:
        conf_colour = "\033[92m"   # green
    elif conf >= 50:
        conf_colour = "\033[93m"   # yellow
    else:
        conf_colour = "\033[91m"   # red
    reset = "\033[0m"
    bold  = "\033[1m"

    print(f"\n{'─'*60}")
    print(f"  Simulation Day #{day_num:>3}  (CSV Day {csv_day})")
    print(f"{'─'*60}")
    print(f"  Device          : {device['serial_number']}")
    print(f"  History Days    : {device['total_historical_days']}")
    print(f"  Sequence        : {device['sequence_days_retrieved']}/30"
          f"  (padded {device['sequence_days_padded']})")
    print(f"  Prediction      : {bold}{label}{reset}")
    print(f"  Confidence      : {conf_colour}{conf:.1f}%{reset}")
    print(f"  Recommendation  : {pred['corrective_action'][:80]}{'…' if len(pred['corrective_action']) > 80 else ''}")

    # Mini probability bar chart (top 3)
    top3 = sorted(pred["probabilities"].items(), key=lambda x: x[1], reverse=True)[:3]
    print(f"  Top-3 classes   :")
    for lbl, prob in top3:
        bar = "█" * int(prob * 20)
        print(f"    {lbl:<28} {prob*100:>5.1f}% {bar}")


def run_simulation(
    csv_path: str,
    serial_number: str,
    db_path: str,
    model_dir: str,
    delay: float,
    json_mode: bool,
    clear_history: bool,
    max_days: int | None,
    start_day: int,
) -> None:
    """Main simulation loop."""

    # ── Import here so errors are surfaced cleanly ─────────────────────
    try:
        from daily_check import run_daily_check
    except ImportError as e:
        print(f"[ERROR] Cannot import daily_check: {e}", file=sys.stderr)
        print("Make sure daily_check.py is in the same directory.", file=sys.stderr)
        sys.exit(1)

    df = load_csv(csv_path)
    total_rows = len(df)

    if not json_mode:
        print("=" * 60)
        print("  SOLAR SYSTEM – DAILY CHECK SIMULATION")
        print("=" * 60)
        print(f"  CSV file        : {csv_path}")
        print(f"  Total CSV rows  : {total_rows}")
        print(f"  Serial number   : {serial_number}")
        print(f"  DB path         : {db_path}")
        print(f"  Delay           : {delay}s between days")
        print(f"  Start row       : {start_day}")
        print(f"  Max days        : {max_days or 'all'}")
        print(f"  Clear history   : {clear_history}")
        print("=" * 60)

    rows_to_process = df.iloc[start_day - 1:]
    if max_days:
        rows_to_process = rows_to_process.head(max_days)

    success_count = 0
    error_count   = 0
    results_log   = []

    for sim_day, (_, row) in enumerate(rows_to_process.iterrows(), start=start_day):
        csv_day = int(row.get("Day", sim_day))
        daily_dict = row_to_daily_dict(row)

        if not json_mode:
            print(f"\n[{time.strftime('%H:%M:%S')}] Processing day {sim_day}/{start_day + len(rows_to_process) - 1} "
                  f"(CSV Day {csv_day}) …", end="", flush=True)

        try:
            result = run_daily_check(
                daily_data=daily_dict,
                serial_number=serial_number,
                db_path=db_path,
                model_dir=model_dir,
                clear_history=(clear_history and sim_day == start_day),
            )
            success_count += 1
            results_log.append({
                "sim_day": sim_day,
                "csv_day": csv_day,
                "label": result["prediction"]["anomaly_label"],
                "confidence": round(result["prediction"]["confidence"], 4),
                "status": "ok",
            })
            print_result(sim_day, csv_day, result, json_mode)

        except Exception as e:
            error_count += 1
            results_log.append({
                "sim_day": sim_day,
                "csv_day": csv_day,
                "status": "error",
                "error": str(e),
            })
            if json_mode:
                print(json.dumps({
                    "sim_day": sim_day,
                    "csv_day": csv_day,
                    "status": "error",
                    "error": str(e),
                    "trace": traceback.format_exc(),
                }))
            else:
                print(f"\n  [ERROR] Day {sim_day}: {e}")
                traceback.print_exc()

        # Wait before the next day (skip on last iteration)
        if delay > 0 and sim_day < start_day + len(rows_to_process) - 1:
            if not json_mode:
                print(f"  ↳ Waiting {delay}s …", end="", flush=True)
            time.sleep(delay)

    # ── Summary ────────────────────────────────────────────────────────
    if not json_mode:
        print(f"\n\n{'='*60}")
        print(f"  SIMULATION COMPLETE")
        print(f"{'='*60}")
        print(f"  Days processed  : {success_count + error_count}")
        print(f"  Successful      : {success_count}")
        print(f"  Errors          : {error_count}")

        if results_log:
            labels = [r["label"] for r in results_log if r.get("label")]
            if labels:
                from collections import Counter
                counts = Counter(labels)
                print(f"\n  Prediction breakdown:")
                for lbl, cnt in counts.most_common():
                    pct = cnt / len(labels) * 100
                    print(f"    {lbl:<30} {cnt:>3}x  ({pct:.1f}%)")
        print(f"{'='*60}\n")
    else:
        print(json.dumps({
            "summary": {
                "total": success_count + error_count,
                "success": success_count,
                "errors": error_count,
            },
            "results": results_log,
        }, indent=2))


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Simulate daily ESP32 telemetry checks from a CSV file."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=CSV_FILE_PATH,
        help=f"Path to CSV telemetry file (default: {CSV_FILE_PATH})"
    )
    parser.add_argument(
        "--serial",
        type=str,
        default=DEFAULT_SERIAL_NUMBER,
        help=f"ESP32 serial number (default: {DEFAULT_SERIAL_NUMBER})"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite history DB"
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=DEFAULT_MODEL_DIR,
        help="Path to model directory (auto-detected if omitted)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Seconds to wait between days (default: {DEFAULT_DELAY_SECONDS}). Use 0 for no delay."
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=None,
        help="Maximum number of days to simulate (default: all rows)"
    )
    parser.add_argument(
        "--start-day",
        type=int,
        default=1,
        help="Start from this row number in the CSV (1-indexed, default: 1)"
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear DB history for this serial number before starting"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (machine-readable mode)"
    )

    args = parser.parse_args()

    run_simulation(
        csv_path=args.csv,
        serial_number=args.serial,
        db_path=args.db_path,
        model_dir=args.model_dir,
        delay=args.delay,
        json_mode=args.json,
        clear_history=args.clear_history,
        max_days=args.max_days,
        start_day=args.start_day,
    )


if __name__ == "__main__":
    main()