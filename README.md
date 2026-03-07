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
│   └── visualize_flow.py      # Real-time flow visualization
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
```bash
source ~/skydev-research/esp/esp-idf/export.sh
```

### Build
```bash
cd base/boards/s3v1
idf.py build
```

### Flash & Monitor
```bash
idf.py -p /dev/cu.usbmodem* flash monitor
```

## Configuration

Key settings in `base/boards/s3v1/board_config/platform.h`:

| Define | Default | Purpose |
|--------|---------|---------|
| `ENABLE_RANGE_FINDER` | `1` | Enable/disable VL53L1X |
| `CAMERA_DIRECTION` | `0` | 0=downward, 1=upward |
| `OPTFLOW_METHOD_CROP` | `0` | 0=resize (wide FOV), 1=crop (zoom) |
| `ENABLE_DEBUG_LOGGING` | `0` | Enable telemetry `ESP_LOGI` output |

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
pip install matplotlib pyserial
```

| Tool | Purpose |
|------|---------|
| `tools/view_frame.py` | View raw 64×64 camera frames |
| `tools/view_optflow.py` | View optical flow vectors |
| `tools/visualize_flow.py` | Real-time dx, dy, quality plots |

## Coding Rules

1. **No cross-module includes** — modules communicate only via pub/sub
2. **Shared structs** in `base/foundation/messages.h`
3. **Topics** in `base/foundation/pubsub.h`
4. **Hardware config** in `base/boards/s3v1/board_config/platform.h`
5. **File-scope `static`** for module state (not function-scope)

## Related Projects

| Project | Description |
|---------|-------------|
| [`../optflow/`](../optflow/) | Optical flow library (Lucas-Kanade dense) |
| [`../flight-controller/`](../flight-controller/) | Main flight controller (consumes flow data) |
| [`../robotkit/`](../robotkit/) | Math, sensor fusion, PID library |

## License

Proprietary. See LICENSE file for details.
