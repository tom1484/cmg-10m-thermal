# CMG-10m Thermal

Tools for CMG-10m's thermal system system ID. Includes a C implementation of the MCC 134 thermocouple interface and data fusion tool, and script for monitoring and controling experiment.

## Dependencies

### System Dependencies
- **libdaqhats** - MCC DAQ HAT library ([installation guide](https://github.com/mccdaq/daqhats))
- **libyaml-dev** - YAML parsing library
- **gcc** - GNU C compiler
- **make** - Build system

### Python Dependencies (for monitoring tool)
- **Python 3.8+** - Python interpreter
- **typer** - CLI framework (for monitor.py)
- **numpy** - Numerical computing (for monitor.py)
- **scipy** - Scientific computing (for monitor.py)

### Included (vendored)
- **cJSON** - JSON parsing/generation (single-file library)

## Installation

### 1. Install Dependencies

The installation script handles both system dependencies and Python virtual environment setup:

```bash
./install_deps.sh
```

This will:
- Install system packages (libyaml-dev)
- Clone and install daqhats library (if not already installed)
- Install Python dependencies from `requirements.txt`

### 2. Build

```bash
cd thermo-cli
make
```

#### Debug Mode

When compiled with `DEBUG=1`, the following features are enabled:

- **Debug symbols** - Include `-g` flag for debugging with gdb
- **Debug prints** - `DEBUG_PRINT()` macro outputs to stderr
- **Performance profiling** - `PROFILE_SCOPE()` macro measures execution time

### 3. Install System-wide

```bash
cd thermo-cli
sudo make install
```

This installs `thermo-cli` to `/usr/local/bin/`.

## Usage

### List Connected Boards

```bash
thermo-cli list
thermo-cli list --json
```

### Read Temperature

```bash
# Read temperature from address 0, channel 0 (default)
thermo-cli get --temp

# Specify address and channel
thermo-cli get --address 0 --channel 1 --tc-type K --temp

# Get multiple readings
thermo-cli get -a 0 -c 0 --temp --adc --cjc

# JSON output
thermo-cli get -a 0 -c 1 --temp --json

# Stream temperature readings at 2 Hz
thermo-cli get --temp --stream 2

# Stream with JSON output at 5 Hz
thermo-cli get -T -A --stream 5 --json

# Clean output mode (no alignment/formatting)
thermo-cli get --temp --clean
```

### Read from Multiple Channels (Config File)

```bash
# Create example config file
thermo-cli init-config --output sensors.yaml

# Read from multiple channels defined in config
thermo-cli get --config sensors.yaml --temp

# Multi-channel with JSON output
thermo-cli get -C sensors.yaml --temp --adc --json

# Stream from multiple channels
thermo-cli get --config sensors.yaml --temp --stream 5

# Multi-channel with all data types
thermo-cli get -C sensors.yaml -T -A -J --json
```

Example config file (`sensors.yaml`):
```yaml
sources:
  - key: BATTERY_TEMP
    address: 0
    channel: 0
    tc_type: K
    cal_slope: 1.0        # Optional: calibration slope (default: 0.999560)
    cal_offset: 0.0       # Optional: calibration offset (default: -38.955465)
    update_interval: 1    # Optional: update interval in seconds (default: 1)
  - key: MOTOR_TEMP
    address: 0
    channel: 1
    tc_type: K
  - key: AMBIENT_TEMP
    address: 0
    channel: 2
    tc_type: K
```

**Note:** Calibration coefficients and update interval specified in config files are applied once when the board is opened, providing persistent settings during the reading session.

Example multi-channel JSON output:
```json
[
  {
    "KEY": "BATTERY_TEMP",
    "ADDRESS": 0,
    "CHANNEL": 0,
    "TEMPERATURE": 32.123456,
    "ADC": 0.987654
  },
  {
    "KEY": "MOTOR_TEMP",
    "ADDRESS": 0,
    "CHANNEL": 1,
    "TEMPERATURE": 45.234567,
    "ADC": 1.234567
  },
  {
    "KEY": "AMBIENT_TEMP",
    "ADDRESS": 0,
    "CHANNEL": 2,
    "TEMPERATURE": 25.678901,
    "ADC": 0.765432
  }
]
```

Example multi-channel table output:
```
----------------------------------------
BATTERY_TEMP (Address: 0, Channel: 0):
    Temperature:  32.123456 °C
    ADC:          0.987654 V
----------------------------------------
MOTOR_TEMP (Address: 0, Channel: 1):
    Temperature:  45.234567 °C
    ADC:          1.234567 V
----------------------------------------
AMBIENT_TEMP (Address: 0, Channel: 2):
    Temperature:  25.678901 °C
    ADC:          0.765432 V
----------------------------------------
```

Example multi-channel stream output:
```
----------------------------------------
BATTERY_TEMP (Address: 0, Channel: 0):
    Serial:       XXXXXXXX
    ...
========================================
Streaming 3 sources at 1 Hz
========================================
BATTERY_TEMP (Address: 0, Channel: 0):
    Temperature:  32.123456 °C
    ADC:          0.987654 V
MOTOR_TEMP (Address: 0, Channel: 1):
    Temperature:  45.234567 °C
    ADC:          1.234567 V
AMBIENT_TEMP (Address: 0, Channel: 2):
    Temperature:  25.678901 °C
    ADC:          0.765432 V
----------------------------------------
BATTERY_TEMP (Address: 0, Channel: 0):
    Temperature:  32.345678 °C
    ADC:          0.998765 V
...
```

### Get Board Information

```bash
# Serial number
thermo-cli get --serial

# Calibration date
thermo-cli get --cali-date

# Calibration coefficients
thermo-cli get --channel 0 --cali-coeffs

# Update interval
thermo-cli get --update-interval
```

### Configure Channel

```bash
# Set calibration coefficients
thermo-cli set --address 0 --channel 0 --cali-slope 1.0 --cali-offset 0.0

# Set update interval
thermo-cli set --address 0 --update-interval 2
```

### Data Fusion (Inject into cmg-cli)

The `fuse` command spawns `cmg-cli` as a subprocess and injects thermal readings into the JSON output with timestamps.

#### Single source mode:
```bash
thermo-cli fuse --address 0 --channel 1 --key MOTOR_TEMP -- --power
```

#### Config file mode:
```bash
# Create example config
thermo-cli init-config --output my_config.yaml

# Use config for fusion
thermo-cli fuse --config my_config.yaml -- --actuator --stream 5
```

#### Custom timestamp format:
```bash
# Default ISO 8601 with microseconds
thermo-cli fuse -a 0 -c 0 -k MY_TEMP -- --power
# Output: {"...", "TIMESTAMP": "2026-01-15T14:30:45.123456", "THERMOCOUPLE": {"MY_TEMP": {"TEMP": 25.5, "ADC": 0.001234, "CJC": 23.5}}}

# Custom format (time only)
thermo-cli fuse -a 0 -c 0 -k MY_TEMP -T '%H:%M:%S.%f' -- --power
# Output: {"...", "TIMESTAMP": "14:30:45.123456", "THERMOCOUPLE": {"MY_TEMP": {"TEMP": 25.5, "ADC": 0.001234, "CJC": 23.5}}}
```

### Configuration Files

Generate example config:
```bash
thermo-cli init-config --output thermo_config.yaml
```

Example YAML config:
```yaml
sources:
- key: BATTERY_TEMP
  address: 0
  channel: 0
  tc_type: K
  cal_slope: 1.0
  cal_offset: 0.0
  update_interval: 1
- key: MOTOR_TEMP
  address: 0
  channel: 1
  tc_type: K
  cal_slope: 1.0
  cal_offset: 0.0
  update_interval: 1
- key: AMBIENT_TEMP
  address: 0
  channel: 2
  tc_type: K
  cal_slope: 1.0
  cal_offset: 0.0
  update_interval: 1
```

Example JSON config:
```bash
thermo-cli init-config --output thermo_config.json
```

### Quick Deployment

```bash
# Full deployment (sync, install deps, build, install)
python3 deploy.py pi@192.168.1.100 --password raspberry

# Update deployment (skip dependency installation for faster deploys)
python3 deploy.py pi@192.168.1.100 --password raspberry --update

# Custom remote path
python3 deploy.py pi@raspberrypi.local --password raspberry --remote-path /opt/cmg-thermal

# Debug build
python3 deploy.py pi@192.168.1.100 --password raspberry --debug
```

### Deployment Options

- `--password PASSWORD` - Remote sudo password (required for build/install)
- `--remote-path PATH` - Build path on remote host (default: `~/cmg-10m-thermal`)
- `--sync-only` - Only sync files, don't build or install
- `--build-only` - Build but don't install
- `--no-sync` - Skip file sync (build and install only)
- `--no-deps` - Skip dependency installation
- `--update` - Quick update mode (skip deps, faster for subsequent deploys)
- `--debug` - Build in debug mode

### What Gets Deployed

The deployment script syncs:
- `thermo-cli/` - C source code and build system
- `install_deps.sh` - Dependency installation script
- `requirements.txt` - Python dependencies
- `monitor.py` - Temperature monitoring tool
- `README.md` - Documentation

### Example Workflows

```bash
# Initial deployment
python3 deploy.py pi@192.168.1.100 --password raspberry

# Quick code update after changes
python3 deploy.py pi@192.168.1.100 --password raspberry --update

# Sync files only (for testing)
python3 deploy.py pi@192.168.1.100 --sync-only

# Build and test without installing
python3 deploy.py pi@192.168.1.100 --password raspberry --build-only
```

## Troubleshooting

### Permission denied

For hardware access, you may need to run with sudo or add your user to the `gpio` group:
```bash
sudo usermod -a -G gpio $USER
```

Then log out and back in.

## Support

For issues specific to:
- **This C implementation** - Open an issue in this repository
- **MCC 134 hardware** - See [MCC DAQ HAT documentation](https://github.com/mccdaq/daqhats)
- **DAQ HAT library** - See [daqhats repository](https://github.com/mccdaq/daqhats)
