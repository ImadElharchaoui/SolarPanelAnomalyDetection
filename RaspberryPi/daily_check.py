import os
import sys
import json
import sqlite3
import argparse
import pickle
import traceback
import warnings
import smtplib
from email.mime.text import MIMEText
from email.header import Header
import pandas as pd
import numpy as np
import torch
import torch.nn as nn

# Suppress warnings (like PyTorch's LSTM single-layer dropout warning)
warnings.filterwarnings("ignore", category=UserWarning)

# Configure output encoding to prevent crashes on terminals with limited character sets (like Windows CP1252)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

#  MODEL ARCHITECTURE DEFINITION (must match training & app.py exactly) 

class ImprovedLSTMClassifier(nn.Module):
    def __init__(self, input_size, hidden_size=128, num_classes=8, dropout_rate=0.4):
        super().__init__()
        
        # Two-layer LSTM
        self.lstm1 = nn.LSTM(input_size, hidden_size, batch_first=True, dropout=dropout_rate)
        self.lstm2 = nn.LSTM(hidden_size, hidden_size//2, batch_first=True, dropout=dropout_rate)
        self.attention_weight = nn.Linear(hidden_size//2, 1)
        
        # Dense layers with batch norm and dropout
        self.fc1 = nn.Linear(hidden_size//2, 64)
        self.bn1 = nn.BatchNorm1d(64)
        self.dropout1 = nn.Dropout(dropout_rate)
        
        self.fc2 = nn.Linear(64, 32)
        self.bn2 = nn.BatchNorm1d(32)
        self.dropout2 = nn.Dropout(dropout_rate)
        
        self.fc3 = nn.Linear(32, num_classes)

    def forward(self, x):
        # x shape: (batch, seq_len, features)
        lstm_out1, _ = self.lstm1(x)
        lstm_out2, _ = self.lstm2(lstm_out1)
        
        # Use last timestep
        last_hidden = lstm_out2[:, -1, :]  # (batch, hidden_size//2)
        
        # Dense layers with batch norm (in eval mode, works with batch size 1)
        x = self.fc1(last_hidden)
        x = self.bn1(x)
        x = torch.relu(x)
        x = self.dropout1(x)
        
        x = self.fc2(x)
        x = self.bn2(x)
        x = torch.relu(x)
        x = self.dropout2(x)
        
        return self.fc3(x)

#  ANOMALY RECOMMENDATIONS MAP

RECOMMENDATIONS = {
    "Normal Status": "Normal Status: Balanced charge/discharge cycles. No maintenance action required.",
    "F-01 Controller Bug": "Controller Bug: Controller lockup preventing charge recovery. Perform hardware power cycle or update firmware.",
    "F-02 Low SoC (Weather)": "Low SoC (Weather): Battery depletion due to cloud/overcast. System recovers automatically. Monitor weather patterns.",
    "F-03 PV Issue": "PV Issue: Low solar current under warm/sunny skies. Clean panel surface, check wiring, inspect shadowing.",
    "F-04 Load Oscillation": "Load Oscillation: LED driver/control loop blinking anomalies. Inspect LED driver outputs and load terminals.",
    "F-05 Total Power Loss": "Total Power Loss: Telemetry values flat zero (e.g. fuse failure). Replace blown battery fuse and inspect main wires.",
    "F-06a Battery Aging Trend": "Battery Aging: Declining daily SoC peaks and capacity EOL. Schedule battery module replacement.",
    "F-06b Thermal Risk": "Thermal Risk: Battery temp >45°C during active charging phase. URGENT: Disconnect system; inspect thermal cooling."
}

#  SQLITE HISTORY STORE

def init_db(db_path):
    """Initializes the SQLite database that tracks daily data per ESP32."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_number TEXT NOT NULL,
            day INTEGER NOT NULL,
            vbat_min_v REAL,
            vbat_max_v REAL,
            ah_charge_ah REAL,
            ah_load_ah REAL,
            vpv_max_v REAL,
            ipv_max_a REAL,
            soc_pct REAL,
            temp_max_c REAL,
            temp_min_c REAL,
            night_min REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(serial_number, day)
        )
    """)
    conn.commit()
    return conn

#  PARSING & NORMALIZATION PIPELINE

def load_parsed_json(logs_input):
    """Loads parsed JSON from either a file path or a raw JSON string."""
    # Check if input is a valid file path
    if os.path.exists(logs_input):
        with open(logs_input, "r", encoding="utf-8") as f:
            return json.load(f)
    
    # Try parsing directly as JSON string
    try:
        return json.loads(logs_input)
    except json.JSONDecodeError:
        raise ValueError(
            f"Logs input is not a valid file path and cannot be parsed as a JSON string.\n"
            f"Input received: {logs_input[:100]}..."
        )

def process_parsed_data(json_data):
    """
    Normalizes the parsed JSON telemetry to align with the model features.
    Supports:
      - Pipeline's original nested datalogger-daily structure
      - Flat daily lists/dictionaries
      - Custom camelCase/Caps variants
    """
    daily_list = []
    is_nested = False
    
    if isinstance(json_data, dict):
        if "datalogger" in json_data:
            datalogger = json_data.get("datalogger", {})
            daily_list = datalogger.get("daily", [])
            is_nested = True
        elif "telemetry" in json_data:
            # Handle minimal parser output
            telemetry = json_data.get("telemetry", {})
            general = telemetry.get("general", {})
            battery = telemetry.get("battery", {})
            pv = telemetry.get("pv", {})
            load = telemetry.get("load", {})
            
            record = {
                "day": general.get("controller_op_days", 1),
                "vbat_min_v": battery.get("voltage_min_v", battery.get("voltage_v", 0.0)),
                "vbat_max_v": battery.get("voltage_max_v", battery.get("voltage_v", 0.0)),
                "ah_charge_ah": battery.get("charge_ah", 0.0),
                "ah_load_ah": load.get("load_ah", 0.0),
                "vpv_max_v": pv.get("voltage_max_v", pv.get("voltage_v", 0.0)),
                "ipv_max_a": pv.get("current_max_a", pv.get("current_a", 0.0)),
                "soc_pct": battery.get("soc_pct", 0.0),
                "text_max_c": general.get("external_temp_max_c", general.get("external_temp_c", 0.0)),
                "text_min_c": general.get("external_temp_min_c", general.get("external_temp_c", 0.0)),
                "night_h": load.get("night_hours", 10.0)
            }
            daily_list = [record]
        else:
            # Treated as a single day's dictionary
            daily_list = [json_data]
    elif isinstance(json_data, list):
        daily_list = json_data
    else:
        raise ValueError("Invalid JSON log format. Must be list or dictionary.")

    if not daily_list:
        raise ValueError("No daily records found in the parsed logs.")
        
    rows = []
    for d in daily_list:
        if is_nested:
            rows.append({
                "VBat_Min_V":   float(d.get("vbat_min_mv", 0)) / 1000.0,
                "VBat_Max_V":   float(d.get("vbat_max_mv", 0)) / 1000.0,
                "Ah_Charge_Ah": float(d.get("ah_charge_mah", 0)) / 1000.0,
                "Ah_Load_Ah":   float(d.get("ah_load_mah", 0)) / 1000.0,
                "VPv_Max_V":    float(d.get("vpv_max_mv", 0)) / 1000.0,
                "IPv_Max_A":    float(d.get("ipv_max_ma", 0)) / 1000.0,
                "SOC_Pct":      float(d.get("soc_pct", 0)) * 6.6,
                "Temp_Max_C":   float(d.get("ext_temp_max_c", 0)),
                "Temp_Min_C":   float(d.get("ext_temp_min_c", 0)),
                "Night_Min":    float(d.get("nightlength_min", 0)),
            })
        else:
            # Flat mapping with fallback support for different styles
            # e.g., vbat_min_v, VBat_Min_V, vbat_min_mv, etc.
            
            # Helper to get float from multiple key options
            def get_val(keys, default=0.0):
                for key in keys:
                    if key in d and d[key] is not None:
                        return float(d[key])
                return default
            
            vbat_min = get_val(["vbat_min_v", "VBat_Min_V"])
            if vbat_min == 0.0 and "vbat_min_mv" in d:
                vbat_min = float(d["vbat_min_mv"]) / 1000.0
                
            vbat_max = get_val(["vbat_max_v", "VBat_Max_V"])
            if vbat_max == 0.0 and "vbat_max_mv" in d:
                vbat_max = float(d["vbat_max_mv"]) / 1000.0
                
            ah_charge = get_val(["ah_charge_ah", "Ah_Charge_Ah"])
            if ah_charge == 0.0 and "ah_charge_mah" in d:
                ah_charge = float(d["ah_charge_mah"]) / 1000.0
                
            ah_load = get_val(["ah_load_ah", "Ah_Load_Ah"])
            if ah_load == 0.0 and "ah_load_mah" in d:
                ah_load = float(d["ah_load_mah"]) / 1000.0
                
            vpv_max = get_val(["vpv_max_v", "VPv_Max_V"])
            if vpv_max == 0.0 and "vpv_max_mv" in d:
                vpv_max = float(d["vpv_max_mv"]) / 1000.0
                
            ipv_max = get_val(["ipv_max_a", "IPv_Max_A"])
            if ipv_max == 0.0 and "ipv_max_ma" in d:
                ipv_max = float(d["ipv_max_ma"]) / 1000.0
                
            soc = get_val(["soc_pct", "SOC_Pct"])
            # Apply scaling if it is in old raw range [0-15] which represents [0-100%]
            if "soc_pct" in d and get_val(["soc_pct"]) <= 15.1 and is_nested:
                soc = get_val(["soc_pct"]) * 6.6
                
            temp_max = get_val(["temp_max_c", "Temp_Max_C", "text_max_c", "ext_temp_max_c"])
            temp_min = get_val(["temp_min_c", "Temp_Min_C", "text_min_c", "ext_temp_min_c"])
            
            # Night length in minutes
            night_min = 0.0
            if "night_h" in d:
                night_min = float(d["night_h"]) * 60.0
            elif "nightlength_min" in d:
                night_min = float(d["nightlength_min"])
            else:
                night_min = get_val(["Night_Min", "night_min"], 600.0)

            rows.append({
                "VBat_Min_V":   vbat_min,
                "VBat_Max_V":   vbat_max,
                "Ah_Charge_Ah": ah_charge,
                "Ah_Load_Ah":   ah_load,
                "VPv_Max_V":    vpv_max,
                "IPv_Max_A":    ipv_max,
                "SOC_Pct":      soc,
                "Temp_Max_C":   temp_max,
                "Temp_Min_C":   temp_min,
                "Night_Min":    night_min
            })
            
    return pd.DataFrame(rows)

#  MODEL CACHING & RETRIEVAL

_CACHED_MODEL = None
_CACHED_SCALER = None
_CACHED_LABEL_ENCODER = None
_CACHED_FEATURE_COLUMNS = None
_CACHED_MODEL_DIR = None

def get_model_artifacts(model_dir=None):
    """
    Retrieves and caches model artifacts. Prevents loading weight files 
    multiple times when run_daily_check is called repeatedly.
    """
    global _CACHED_MODEL, _CACHED_SCALER, _CACHED_LABEL_ENCODER, _CACHED_FEATURE_COLUMNS, _CACHED_MODEL_DIR
    
    # 1. Search for directory if not specified
    if not model_dir:
        print(os.path.join(os.path.dirname(__file__), "models"))
        possible_dirs = [
           os.path.abspath(os.path.join(os.path.dirname(__file__), "models"))
        ]
        for d in possible_dirs:
            if os.path.exists(os.path.join(d, "lstm_fault_detector.pth")):
                model_dir = d
                break
        
        # If still not found, default to local models directory
        if not model_dir:
            model_dir = os.path.join(os.path.dirname(__file__), "models")
                
    if not os.path.exists(model_dir):
        raise FileNotFoundError(
            "Model directory not found. Please place model files in './models' "
            "or specify the path."
        )
        
    model_dir = os.path.abspath(model_dir)
    
    # 2. Return cached artifacts if same directory is requested
    if _CACHED_MODEL is not None and model_dir == _CACHED_MODEL_DIR:
        return _CACHED_MODEL, _CACHED_SCALER, _CACHED_LABEL_ENCODER, _CACHED_FEATURE_COLUMNS
        
    # 3. Load from disk
    with open(os.path.join(model_dir, "model_config.pkl"), "rb") as f:
        config = pickle.load(f)
    with open(os.path.join(model_dir, "scaler.pkl"), "rb") as f:
        scaler = pickle.load(f)
    with open(os.path.join(model_dir, "label_encoder.pkl"), "rb") as f:
        le = pickle.load(f)
    with open(os.path.join(model_dir, "feature_columns.pkl"), "rb") as f:
        feature_columns = pickle.load(f)
        
    model = ImprovedLSTMClassifier(
        input_size=config['input_size'],
        hidden_size=config['hidden_size'],
        num_classes=config['num_classes'],
        dropout_rate=config['dropout_rate']
    )
    model.load_state_dict(torch.load(os.path.join(model_dir, "lstm_fault_detector.pth"), map_location=torch.device('cpu')))
    model.eval()
    
    # Cache variables
    _CACHED_MODEL = model
    _CACHED_SCALER = scaler
    _CACHED_LABEL_ENCODER = le
    _CACHED_FEATURE_COLUMNS = feature_columns
    _CACHED_MODEL_DIR = model_dir
    
    return model, scaler, le, feature_columns

#  EXPOSED LIBRARY FUNCTION

def run_daily_check(daily_data, serial_number, db_path=None, model_dir=None, clear_history=False):
    """
    Evaluates daily telemetry logs for a specific ESP32 datalogger.
    Can be imported by other Python scripts:
        from daily_check import run_daily_check
        result = run_daily_check(daily_dict, "ESP32_01")
        
    Args:
        daily_data (dict, list, str): Parsed daily log. Can be a python dictionary representing
                                      one day, a list of daily dictionaries, a JSON string, or
                                      a file path to a JSON file.
        serial_number (str): Unique serial number identifying the ESP32.
        db_path (str, optional): Path to the SQLite history DB. Defaults to device_history.db.
        model_dir (str, optional): Path to the folder containing model files.
        clear_history (bool, optional): Clear device history in DB before processing.
        
    Returns:
        dict: Inference results containing predicted status, confidence score, and recommendations.
    """
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), "device_history.db")
        
    # Load model and configurations (from lazy caching)
    model, scaler, le, feature_columns = get_model_artifacts(model_dir)
    
    # Initialize SQLite database
    conn = init_db(db_path)
    cursor = conn.cursor()
    
    # Clear history if requested
    if clear_history:
        cursor.execute("DELETE FROM device_history WHERE serial_number = ?", (serial_number,))
        conn.commit()
        
    # Resolve input data (string could be file path or raw JSON string)
    if isinstance(daily_data, str):
        parsed_json = load_parsed_json(daily_data)
    else:
        parsed_json = daily_data
        
    # Normalize features
    df_new = process_parsed_data(parsed_json)
    
    # Retrieve current max day for sequence index calculations
    cursor.execute("SELECT MAX(day) FROM device_history WHERE serial_number = ?", (serial_number,))
    result = cursor.fetchone()
    max_day = result[0] if result and result[0] is not None else 0
    
    # Insert new daily records
    inserted_count = 0
    for idx, row in df_new.iterrows():
        max_day += 1
        cursor.execute("""
            INSERT OR REPLACE INTO device_history (
                serial_number, day, vbat_min_v, vbat_max_v, ah_charge_ah,
                ah_load_ah, vpv_max_v, ipv_max_a, soc_pct, temp_max_c,
                temp_min_c, night_min
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            serial_number, max_day,
            row["VBat_Min_V"], row["VBat_Max_V"], row["Ah_Charge_Ah"],
            row["Ah_Load_Ah"], row["VPv_Max_V"], row["IPv_Max_A"],
            row["SOC_Pct"], row["Temp_Max_C"], row["Temp_Min_C"],
            row["Night_Min"]
        ))
        inserted_count += 1
    conn.commit()
    
    # Retrieve last 30 daily records (chronological order)
    cursor.execute(f"""
        SELECT VBat_Min_V, VBat_Max_V, Ah_Charge_Ah, Ah_Load_Ah, VPv_Max_V,
               IPv_Max_A, SOC_Pct, Temp_Max_C, Temp_Min_C, Night_Min
        FROM device_history
        WHERE serial_number = ?
        ORDER BY day DESC
        LIMIT 30
    """, (serial_number,))
    
    db_rows = cursor.fetchall()
    conn.close()
    
    cols = ['VBat_Min_V', 'VBat_Max_V', 'Ah_Charge_Ah', 'Ah_Load_Ah', 'VPv_Max_V',
            'IPv_Max_A', 'SOC_Pct', 'Temp_Max_C', 'Temp_Min_C', 'Night_Min']
    df_seq = pd.DataFrame(db_rows, columns=cols)
    
    # Reverse rows to get ascending chronological order (oldest to newest)
    df_seq = df_seq.iloc[::-1].reset_index(drop=True)
    actual_sequence_len = len(df_seq)
    
    # Ensure correct columns order
    df_seq = df_seq.reindex(columns=feature_columns, fill_value=0.0)
    
    # Pad sequence if < 30 days
    seq_len = 30
    padded_days = 0
    if len(df_seq) < seq_len:
        padded_days = seq_len - len(df_seq)
        padding = pd.DataFrame(0.0, index=range(padded_days), columns=df_seq.columns)
        df_seq = pd.concat([padding, df_seq], ignore_index=True)
        
    # Scale and reshape sequence for PyTorch model (batch_size=1, seq_len=30, features=10)
    X_scaled = scaler.transform(df_seq.values)
    X_seq = X_scaled.reshape(1, seq_len, -1)
    
    # Run Model Inference
    with torch.no_grad():
        outputs = model(torch.tensor(X_seq, dtype=torch.float32))
        probs = torch.softmax(outputs, dim=1).numpy()[0]
        
    pred_idx = int(np.argmax(probs))
    pred_label = le.classes_[pred_idx]
    confidence = float(probs[pred_idx])
    
    # Construct output breakdown
    probabilities = {le.classes_[i]: float(probs[i]) for i in range(len(probs))}
    recommendation = RECOMMENDATIONS.get(pred_label, "No standard recommendation available for this status.")
    
    return {
        "device": {
            "serial_number": serial_number,
            "total_historical_days": max_day,
            "new_records_inserted": inserted_count,
            "sequence_days_retrieved": actual_sequence_len,
            "sequence_days_padded": padded_days
        },
        "prediction": {
            "anomaly_label": pred_label,
            "confidence": confidence,
            "probabilities": probabilities,
            "corrective_action": recommendation
        }
    }

#  SMTP EMAIL ALERT HELPER

def send_anomaly_email(result, recipient, sender, server, port, username, password):
    """Sends an email notification when a device anomaly is detected."""
    device = result["device"]
    pred = result["prediction"]
    
    subject = f" [SOLAR SYSTEM ALERT] Anomaly Detected on Device {device['serial_number']}"
    
    body = f"""Solar Panel Anomaly Detection Alert
======================================
Device Serial Number: {device['serial_number']}
Total Recorded Days:  {device['total_historical_days']}
Inference Sequence:   {device['sequence_days_retrieved']}/30 days (Padded: {device['sequence_days_padded']} days)

--------------------------------------
PREDICTED STATUS:  {pred['anomaly_label']}
CONFIDENCE LEVEL:  {pred['confidence'] * 100:.2f}%
--------------------------------------

CORRECTIVE ACTION RECOMMENDATION:
{pred['corrective_action']}

--------------------------------------
Probability Breakdown:
"""
    for label, prob in sorted(pred['probabilities'].items(), key=lambda x: x[1], reverse=True):
        body += f"  - {label:<25} : {prob * 100:>6.2f}%\n"
        
    body += "\nThis is an automated diagnostic alert. Please inspect the device coordinates as soon as possible."
    
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = recipient
    
    try:
        print(f"[SMTP] Connecting to server {server}:{port}...")
        if int(port) == 465:
            smtp = smtplib.SMTP_SSL(server, port, timeout=10)
        else:
            smtp = smtplib.SMTP(server, port, timeout=10)
            smtp.starttls()
            
        if username and password:
            print("[SMTP] Authenticating...")
            smtp.login(username, password)
            
        print(f"[SMTP] Sending alert email to {recipient}...")
        smtp.sendmail(sender, [recipient], msg.as_string())
        smtp.quit()
        print("[SMTP] ✓ Alert email sent successfully.")
        return True
    except Exception as e:
        print(f"[SMTP] ERROR: Failed to send email alert: {e}", file=sys.stderr)
        return False

#  MAIN CLI PIPELINE WRAPPER

def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Daily Check Utility for Solar Panel Anomaly Detection."
    )
    parser.add_argument(
        "daily_logs",
        type=str,
        help="Path to the daily parsed log JSON file, or a direct JSON string."
    )
    parser.add_argument(
        "serial_number",
        type=str,
        help="Unique serial number of the ESP32 logger."
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Path to the SQLite database to store device telemetry history."
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default=None,
        help="Path to directory containing model weights/pkl configs."
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear historical data stored in database for this serial number before processing."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in machine-readable JSON format instead of a styled console report."
    )
    parser.add_argument(
        "--email-alert",
        action="store_true",
        default=os.environ.get("EMAIL_ALERT", "false").lower() in ("true", "1", "yes"),
        help="Enable email alerts on anomaly detection (also configurable via EMAIL_ALERT env)."
    )
    parser.add_argument(
        "--smtp-server",
        type=str,
        default=os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        help="SMTP server host (defaults to SMTP_SERVER env or smtp.gmail.com)."
    )
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=int(os.environ.get("SMTP_PORT", 587)),
        help="SMTP server port (defaults to SMTP_PORT env or 587)."
    )
    parser.add_argument(
        "--smtp-user",
        type=str,
        default=os.environ.get("SMTP_USER", ""),
        help="SMTP username (defaults to SMTP_USER env)."
    )
    parser.add_argument(
        "--smtp-password",
        type=str,
        default=os.environ.get("SMTP_PASSWORD", ""),
        help="SMTP password (defaults to SMTP_PASSWORD env)."
    )
    parser.add_argument(
        "--smtp-sender",
        type=str,
        default=os.environ.get("SMTP_SENDER", ""),
        help="SMTP sender email address (defaults to SMTP_SENDER env)."
    )
    parser.add_argument(
        "--email-recipient",
        type=str,
        default=os.environ.get("EMAIL_RECIPIENT", ""),
        help="Recipient email address (defaults to EMAIL_RECIPIENT env)."
    )
    
    args = parser.parse_args()
    
    try:
        result = run_daily_check(
            daily_data=args.daily_logs,
            serial_number=args.serial_number,
            db_path=args.db_path,
            model_dir=args.model_dir,
            clear_history=args.clear_history
        )
    except Exception as e:
        error_msg = f"Check failed: {e}"
        if args.json:
            print(json.dumps({"error": error_msg, "trace": traceback.format_exc()}))
        else:
            print(error_msg, file=sys.stderr)
            traceback.print_exc()
        sys.exit(1)
        
    # Output results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Styled Console Report Mode
        device = result["device"]
        prediction = result["prediction"]
        
        print("=" * 60)
        print("SOLAR STREET LIGHT ANOMALY DETECTION - DAILY CHECK")
        print("=" * 60)
        print(f"Device Serial Number: {device['serial_number']}")
        print(f"Total Recorded Days:   {device['total_historical_days']} day(s)")
        print(f"New Days Processed:   {device['new_records_inserted']} day(s)")
        print(f"Sequence Length:      {device['sequence_days_retrieved']}/30 days (Padded: {device['sequence_days_padded']} days)")
        print("-" * 60)
        print(f"PREDICTED STATUS:     \033[1m{prediction['anomaly_label']}\033[0m")
        print(f"CONFIDENCE LEVEL:     {prediction['confidence'] * 100:.2f}%")
        print("-" * 60)
        print(f"CORRECTIVE RECOMMENDATION:\n{prediction['corrective_action']}")
        print("-" * 60)
        print("Status Class Probability Breakdown:")
        for label, prob in sorted(prediction['probabilities'].items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(prob * 20)
            print(f"  - {label:<25} : {prob * 100:>6.2f}% {bar}")
        print("=" * 60)
        
    # SMTP email alert dispatch check
    if args.email_alert and result["prediction"]["anomaly_label"] != "Normal Status":
        if not args.email_recipient or not args.smtp_sender:
            print("[SMTP] WARNING: Email alert is enabled but recipient or sender is not set. Email alert skipped.", file=sys.stderr)
        else:
            send_anomaly_email(
                result=result,
                recipient=args.email_recipient,
                sender=args.smtp_sender,
                server=args.smtp_server,
                port=args.smtp_port,
                username=args.smtp_user,
                password=args.smtp_password
            )

if __name__ == "__main__":
    main()
