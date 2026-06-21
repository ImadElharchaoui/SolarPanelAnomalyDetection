"""
scheduler.py – Raspberry Pi Orchestrator and Scheduler
=====================================================

Orchestrates the model synchronization and daily telemetry check tasks on the Raspberry Pi.
Supports two modes:
  - debugging  : Runs model sync every 2 minutes and daily check every 1 minute using test data.
  - production : Runs model sync weekly (7 days) and daily check daily (24 hours).

Usage:
    python scheduler.py --mode debugging --server-url http://<SERVER_IP>:5000
    python scheduler.py --mode production --server-url http://192.168.1.100:5000
"""

import os
import sys
import time
import argparse

# Ensure the module directory is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sync_model import sync_if_needed
from daily_check import run_daily_check

# Sample daily telemetry data sent every 1 minute in debugging/test mode
SAMPLE_DAILY_TELEMETRY = {
    "vbat_min_v": 12.2,
    "vbat_max_v": 14.1,
    "ah_charge_ah": 18.5,
    "ah_load_ah": 15.2,
    "vpv_max_v": 18.0,
    "ipv_max_a": 3.2,
    "soc_pct": 82.5,
    "temp_max_c": 32.0,
    "temp_min_c": 19.5,
    "night_h": 10.2
}


def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Scheduler Daemon for Solar Panel Anomaly Detection."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["production", "debugging"],
        default="production",
        help="Operating mode: 'production' or 'debugging'."
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://localhost:5000",
        help="Base URL of the web server for downloading updated models."
    )
    parser.add_argument(
        "--serial-number",
        type=str,
        default="ESP32_SN_TEST",
        help="Unique serial number of the ESP32 datalogger."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Local directory to store/load models. Defaults to 'models' relative to this script."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to SQLite database. Defaults to 'device_history.db' relative to this script."
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = args.model_dir or os.path.join(base_dir, "models")
    db_path = args.db_path or os.path.join(base_dir, "device_history.db")
    
    # Define intervals in seconds
    if args.mode == "debugging":
        sync_interval = 2 * 60        # 2 minutes
        check_interval = 1 * 60       # 1 minute
        print("Starting Scheduler in DEBUGGING mode:")
        print(f"  - Model sync interval: {sync_interval} seconds (2 min)")
        print(f"  - Daily check interval: {check_interval} seconds (1 min)")
    else:
        sync_interval = 7 * 24 * 3600 # 7 days (weekly)
        check_interval = 24 * 3600    # 24 hours (daily)
        print("Starting Scheduler in PRODUCTION mode:")
        print(f"  - Model sync interval: 1 week")
        print(f"  - Daily check interval: 24 hours")
        
    print(f"Configuration:")
    print(f"  - Server URL: {args.server_url}")
    print(f"  - Serial Number: {args.serial_number}")
    print(f"  - Model Directory: {model_dir}")
    print(f"  - Database Path: {db_path}")
    print("-" * 60)
    
    # We initialize the last run times to 0 so that they run immediately on startup
    last_sync_time = 0
    last_check_time = 0
    
    try:
        while True:
            now = time.time()
            
            # 1. Sync Model check
            if now - last_sync_time >= sync_interval:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Triggering model sync check...")
                try:
                    updated = sync_if_needed(args.server_url, model_dir)
                    print(f"  => Sync check done. Model updated: {updated}")
                except Exception as e:
                    print(f"  => Sync check failed: {e}", file=sys.stderr)
                last_sync_time = now
                
            # 2. Daily check analysis
            if now - last_check_time >= check_interval:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Triggering daily telemetry analysis...")
                try:
                    result = run_daily_check(
                        daily_data=SAMPLE_DAILY_TELEMETRY,
                        serial_number=args.serial_number,
                        db_path=db_path,
                        model_dir=model_dir
                    )
                    pred = result["prediction"]
                    device = result["device"]
                    print(f"  => Daily check successful.")
                    print(f"     Status: {pred['anomaly_label']} (Confidence: {pred['confidence']*100:.2f}%)")
                    print(f"     Action: {pred['corrective_action']}")
                    print(f"     Device: {device['serial_number']} (Total days in DB: {device['total_historical_days']})")
                except Exception as e:
                    print(f"  => Daily check failed: {e}", file=sys.stderr)
                last_check_time = now
                
            # Sleep briefly to avoid high CPU usage
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nScheduler stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
