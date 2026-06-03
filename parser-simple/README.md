# Minimal Solar Parser

A simplified MPPT solar charge controller parser that reads `.log` files and outputs JSON data. **No external dependencies required** — everything is downloaded automatically during the build.

## Features

- ✅ Parse Space telemetry lines from log files
- ✅ Output to JSON file
- ✅ No MQTT, protobuf, or system dependencies
- ✅ Cross-platform (Windows, Linux, macOS)
- ✅ Automatic dependency download

## Build Instructions

### Windows (MinGW64)

**Prerequisites:**
- MinGW64 with g++
- CMake 3.15+

**Steps:**
```bash
cd parser-simple
mkdir build
cd build
cmake -G "MinGW Makefiles" ..
cmake --build .
```

**Output:** `build/mppt_parser.exe`

### Linux/macOS

**Prerequisites:**
```bash
sudo apt-get install build-essential cmake  # Ubuntu/Debian
brew install cmake                           # macOS
```

**Steps:**
```bash
cd parser-simple
mkdir build
cd build
cmake ..
make
```

**Output:** `build/mppt_parser`

## Usage

```bash
./mppt_parser <logfile.txt> [output.json]
```

**Examples:**
```bash
# Parse log file, output to output.json
./mppt_parser data_log.txt

# Parse log file, output to custom file
./mppt_parser data_log.txt my_output.json
```

### Input Format

The parser reads **Space telemetry lines** from log files. Each line should start with a digit and contain semicolon-separated fields:

```
<field1>;<field2>;<field3>; ... ;<field42>;
```

### Output Format

JSON file with telemetry data:
```json
{
  "metadata": {
    "input_file": "data_log.txt",
    "lines_processed": 100,
    "telemetry_records_ok": 42,
    "telemetry_records_failed": 0,
    "has_telemetry": true,
    "has_eeprom": false
  },
  "telemetry": {
    "general": {
      "timestamp": 1234567890,
      "serial_number": "ABC123",
      "firmware_version": 5120,
      "internal_temp_c": 35,
      "external_temp_c": 25,
      "controller_op_days": 512,
      "hw_version": 3
    },
    "battery": {
      "voltage_v": 48.5,
      "soc_pct": 85,
      "charge_current_a": 12.5,
      "charge_power_w": 606,
      "charge_mode": "Float",
      "is_night": false,
      ...
    },
    ...
  }
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `cmake: command not found` | Install CMake (see Prerequisites) |
| `g++: command not found` | Install MinGW64 and add to PATH |
| Build fails with "json not found" | Internet connection needed for first build (downloads json.hpp) |
| File not found error | Check file path and permissions |

## What's Different from Full Parser

This minimal version:
- ✅ Parses Space (telemetry) lines only
- ❌ Does NOT parse EEPROM data
- ❌ Does NOT support MQTT output
- ❌ Does NOT require protobuf

Perfect for simple log file parsing and JSON export!

## Project Structure

```
parser-simple/
├── CMakeLists.txt          # Build configuration
├── include/
│   ├── types.h             # Data structures
│   ├── constants.h         # Protocol constants
│   ├── utils.h             # Utility functions
│   ├── lookups.h           # Enum->string conversions
│   ├── space_parser.h      # Telemetry parser
│   ├── json_builder.h      # JSON builder
│   └── eeprom_parser.h     # EEPROM parser (stub)
└── src/
    ├── main.cpp            # Main program
    ├── space_parser.cpp    # Telemetry parsing logic
    ├── json_builder.cpp    # JSON output logic
    └── eeprom_parser.cpp   # EEPROM stub
```
