# Flight Optflow

Optical flow sensor module for drones. Runs on ESP32-S3 with an OV2640 camera and VL53L1X time-of-flight sensor. Streams flow vectors and altitude to the flight controller over UART.

## Overview

| Component | Detail |
|-----------|--------|
| **Camera** | OV2640 QVGA (320×240) → 64×64 grayscale @ 25 Hz |
| **Range Sensor** | VL53L1X time-of-flight @ 50 Hz (altitude) |
| **Algorithm** | Lucas-Kanade dense optical flow |
| **Output** | `dx_rad`, `dy_rad`, surface quality, altitude via UART @ 38400 baud |
| **MCU** | ESP32-S3 (dual-core, 240 MHz, 8 MB PSRAM) |

## Project Structure

```
flight-optflow/
├── base/
│   ├── boards/
│   │   └── s3v1/              # ESP32-S3 board: main.c, platform.h, sdkconfig
│   └── foundation/            # Platform abstraction, pub/sub, messages
├── libs/
│   ├── optflow/               # Pre-compiled optical flow library
│   ├── utils/                 # Image utilities (crop, resize)
│   └── vl53l1x/               # VL53L1X ToF sensor driver
├── modules/
│   ├── camera/                # OV2640 capture → publishes SENSOR_CAMERA_FRAME
│   ├── optical_flow/          # Lucas-Kanade flow → publishes SENSOR_OPTFLOW
│   ├── range_finder/          # VL53L1X polling → publishes SENSOR_RANGE
│   ├── scheduler/             # Dual-core priority-based scheduler (GPTimer 1kHz)
│   └── telemetry/             # Aggregates flow + range → UART binary packet
├── tools/
│   ├── view_frame.py          # Camera frame viewer
│   ├── view_optflow.py        # Optical flow vector viewer
│   └── optflow_micoair_view.py # MicoAir MTF-02 optical flow viewer
└── docs/
    └── SCHEDULER_ARCHITECTURE.md
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

### Data Flow
```
Scheduler 25Hz → Camera (Core 0) → Optical Flow (Core 1) → Telemetry → UART
                                    Range Finder (Core 1) ──────────────┘
```

1. **Scheduler** triggers `SCHEDULER_CORE0_HP_25HZ` every 40ms
2. **Camera** captures QVGA → crops/resizes to 64×64 → publishes `SENSOR_CAMERA_FRAME`
3. **Optical Flow** runs dense flow on Core 1 → publishes `SENSOR_OPTFLOW`
4. **Range Finder** polls VL53L1X at 50Hz on Core 1 → publishes `SENSOR_RANGE`
5. **Telemetry** subscribes to flow + range → sends binary `'db'` packet over UART

### Threading Model

| Core | Task | Priority | Purpose |
|------|------|----------|---------|
| 0 | `sched_c0_h` | 22 | High-band scheduler |
| 0 | `camera_task` | 20 | Camera capture + image processing |
| 0 | `sched_c0_l` | 10 | Low-band scheduler |
| 1 | `sched_c1_h` | 22 | High-band scheduler |
| 1 | `optflow_task` | 20 | Optical flow calculation |
| 1 | `sched_c1_l` | 10 | Low-band scheduler + range finder |

### Camera Modes

Controlled by `OPTFLOW_METHOD_CROP` in `platform.h`:

| Mode | Setting | FOV | Best For |
|------|---------|-----|----------|
| Center Crop | `=1` | 13.2° (5× zoom) | Hover, slow flight |
| Full Resize | `=0` | 49.5° (bilinear) | Fast flight, wide view |

### Cross-Core Frame Protection

Optical flow uses `atomic_bool g_processing_busy` to prevent frame buffer tearing. If Core 1 is still processing when a new frame arrives on Core 0, the frame is dropped. This ensures the average rate stays at 25 fps while individual `dt` values may vary (30–75ms).

## Dependencies

The `optflow` library must be built before this project:
```bash
cd ../optflow/build-esp32s3
./build.sh    # Compiles and copies to flight-optflow/libs/optflow/
```

## Build & Flash

### Setup Environment

Requires [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/) (Espressif IoT Development Framework).

```bash
source ~/skydev-research/esp/esp-idf/export.sh
```

### Build
```bash
cd base/boards/s3v1
./build.sh                              # Build with defaults
./build.sh --camera-dir 1               # Upward-facing camera
./build.sh --rangefinder 0              # Disable range finder
./build.sh --crop 1 --debug-log 1       # Center crop + debug logging
./build.sh --clean                      # Full clean rebuild
./build.sh --help                       # Show all options
```

### Flash & Monitor
```bash
./build-flash.sh                                    # Build + flash + monitor
./build-flash.sh --camera-dir 1                     # Upward camera, flash + monitor
./build-flash.sh --port /dev/cu.usbmodem1101        # Specify serial port
```

Or manually:
```bash
idf.py -p /dev/cu.usbmodem* flash monitor
```

## Configuration

Key settings in `base/boards/s3v1/board_config/platform.h`.
These can be overridden at build time via `build.sh` flags (no need to edit the header):

| Define | Default | Build Flag | Purpose |
|--------|---------|------------|---------|
| `ENABLE_RANGE_FINDER` | `1` | `--rangefinder 0\|1` | Enable/disable VL53L1X |
| `CAMERA_DIRECTION` | `0` | `--camera-dir 0\|1` | 0=downward, 1=upward |
| `OPTFLOW_METHOD_CROP` | `0` | `--crop 0\|1` | 0=resize (wide FOV), 1=crop (zoom) |
| `ENABLE_DEBUG_LOGGING` | `0` | `--debug-log 0\|1` | Enable telemetry `ESP_LOGI` output |
| `ENABLE_FRAME_TRANSMISSION` | `0` | `--frame-tx 0\|1` | Stream raw camera frames over USB for `view_frame.py` |

## UART Protocol

Binary `'db'` framed packet (22 bytes total):
```
['d']['b'][0x01][direction][len_lo][len_hi][dx_i32][dy_i32][z_i32][quality_i32][ck_a][ck_b]
```
- `dx`/`dy`: radians × 100,000 as int32
- `z`: range in mm as int32
- `quality`: clarity × 10 as int32
- Checksum: UBX-style Fletcher-8
- Note: `dx` is negated to match flight controller body frame

## Visualization Tools

```bash
pip install matplotlib pyserial numpy
```

| Tool | Purpose | Firmware Requirement |
|------|---------|---------------------|
| `tools/view_optflow.py` | Live optical flow vectors, quality, range finder | `--debug-log 1` |
| `tools/view_frame.py` | Live 64×64 camera frame viewer with histogram | `--frame-tx 1` |
| `tools/optflow_micoair_view.py` | Live optical flow viewer for MicoAir MTF-02 module | `--debug-log 1` |

### view_optflow.py — Optical Flow Viewer

Displays real-time flow dx/dy, surface quality, and range finder data parsed from `ESP_LOGI` debug output.

```bash
# 1. Build & flash with debug logging enabled
cd base/boards/s3v1
./build-flash.sh --debug-log 1

# 2. Close any serial monitor (idf.py monitor, screen, etc.)

# 3. Run the viewer
python3 tools/view_optflow.py
```

### view_frame.py — Camera Frame Viewer

Displays live 64×64 grayscale camera frames streamed as raw bytes over USB serial. Includes pixel histogram and frame statistics.

**Important:** Frame transmission reduces optical flow rate from 25 Hz to ~5 Hz because raw pixel data (4 KB/frame) saturates the USB CDC link. Use for debugging only — disable for flight.

```bash
# 1. Build & flash with frame transmission enabled
cd base/boards/s3v1
./build-flash.sh --frame-tx 1

# 2. Close the serial monitor (Ctrl+] or close the terminal)
#    The monitor and view_frame.py cannot share the same serial port.

# 3. Run the viewer
python3 tools/view_frame.py

# 4. When done, rebuild without --frame-tx to restore full 25 Hz performance
./build-flash.sh
```

Frame protocol over USB serial:
```
FRAME_BIN <width> <height> <timestamp_us>\n<raw_bytes>
```
Where `<raw_bytes>` is `width × height` bytes of grayscale pixel data (no delimiter after binary data).

## Coding Rules

1. **No cross-module includes** — modules communicate only via pub/sub
2. **Shared structs** in `base/foundation/messages.h`
3. **Topics** in `base/foundation/pubsub.h`
4. **Hardware config** in `base/boards/s3v1/board_config/platform.h`
5. **File-scope `static`** for module state (not function-scope)

## Related Projects

| Project | Description |
|---------|-------------|
| [flight-controller](https://github.com/hqbao/flight-controller) | Main flight controller (consumes flow data) |
| [flight-vision](https://github.com/hqbao/flight-vision) | OAK-D W visual navigation module |
| robotkit | Math, sensor fusion, PID library |
| optflow | Optical flow library (Lucas-Kanade dense) |

## License

Proprietary. See LICENSE file for details.
