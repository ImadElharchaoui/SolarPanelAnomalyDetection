# Solar Panel Anomaly Detection - Central Web Pipeline

This directory houses the central server application, comprising a Flask web server, an API endpoints engine, and a premium single-page web dashboard interface.

---

## 📂 Web App Architecture

```text
PipeLine/
│
├── requirements.txt         # Server-side Python packages (Flask, PyTorch, etc.)
├── app.py                   # Flask server backend, APIs, and active-learning logic
├── pipeline.db              # SQLite Database (User tables, run logs, correction logs)
│
├── parser/                  # Parser Executables directory (used for raw logs parsing)
│   ├── parser.exe           # Windows Compiled Parser
│   └── parser-linux         # Linux Compiled Parser
│
├── models/                  # PyTorch model weights & scaling configurations
│   ├── lstm_fault_detector.pth
│   ├── model_config.pkl
│   ├── scaler.pkl
│   ├── label_encoder.pkl
│   └── feature_columns.pkl
│
└── templates/
    └── index.html           # Single-page glassmorphic user dashboard UI
```

---

## ⚙️ Flask API Service Endpoints

The Flask server provides core endpoints for data ingestion, user authorization, and system auditing:

### 1. Authentication & Security
* `POST /login`: Log in and retrieve cookies. Expects JSON `{ "username": "...", "password": "..." }`.
* `POST /logout`: Clears the current login session.
* `GET /me`: Queries current session credentials.
* `GET /users` & `POST /users`: (Admin-only) Fetch or create technician accounts.
* `DELETE /users/<user_id>`: (Admin-only) Deletes a technician account.

### 2. Analysis Ingestion
* `POST /upload`: Expects a multi-part form file upload (`.log` or `.json`).
  * Triggers the C++ log parser to extract structured metrics.
  * Aligns telemetry with training configurations.
  * Evaluates telemetry sequence through rolling 30-day windows.
  * Logs transaction metrics in `pipeline.db` and returns a JSON payload containing telemetry arrays (voltage, SoC, current, temperature) and model predictions history.
* `GET /history`: Retrieves the audit list of previously analyzed log entries (filtered by technician, or full list for administrators).

### 3. Active Learning & Fine-Tuning
* `POST /api/correct`: Allows technicians to submit corrective feedback for incorrect predictions.
  * **Payload**:
    ```json
    {
      "wrong_prediction": "F-03 PV Issue",
      "correct_label": "Normal Status",
      "sequence": [[12.5, 13.6, ...], ...],  // 30x10 floats array (optional)
      "learning_rate": 0.0001
    }
    ```
  * **Mechanism**: Performs a **single forward+backward propagation pass** in-memory to adjust PyTorch model weights towards the correct classification.
  * **Update persistence**: Saves the updated weights to `lstm_fault_detector.pth` and increments the model version index in `pipeline.db`.
* `GET /api/corrections`: (Admin-only) Audits all classification adjustments made by operators.

### 4. Edge Sync Server
* `GET /api/model/version`: Public endpoint returning the current integer model version.
* `GET /api/model/download`: Public endpoint streaming the latest `lstm_fault_detector.pth` file.

---

## 🎨 Interactive Dashboard Frontend (`index.html`)

The frontend is a single-page HTML5 workspace designed with a custom glassmorphic theme.

* **UI Features**:
  * **Interactive Login Overlay**: Dark blur overlay protecting sensitive metrics.
  * **Drag-and-Drop Log Upload Zone**: File selector drop-zone with visual status feedback.
  * **Dynamic Charting Panel**: Renders time-series charts using **Chart.js** displaying:
    * Battery Voltage ($V_{bat}$ Max vs Min)
    * Charge current ($I_{PV}$) and energy ($Ah_{Charge}$)
    * Temperature limits ($Temp$ Max vs Min)
    * State of Charge ($SoC$) trend
  * **Classification Breakdowns**: Multi-colored probability indicator bars for each anomaly state.
  * **Technician Corrections Console**: Interface to override classifications and submit corrective feedback instantly to the active learning pipeline.
  * **Auditing Tables**: Renders historical runs and correction logs.

---

## 🚀 Running the Server Locally

### 1. Virtual Environment Activation
Open your terminal and navigate to the project directory:
* **Windows**:
  ```cmd
  .\PipeLine\.venv\Scripts\activate
  ```
* **Linux/macOS**:
  ```bash
  source PipeLine/.venv/bin/activate
  ```

### 2. Run Flask App
Launch the Flask development server:
```bash
python PipeLine/app.py
```
By default, the server runs on **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.
> [!NOTE]
> Ensure the C++ parser binaries in `PipeLine/parser/` have execution permissions on Linux/macOS systems (`chmod +x parser-linux`).
