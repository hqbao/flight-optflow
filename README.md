# Flight Optflow

An ESP-IDF application for the ESP32-S3 that performs optical flow calculations using the `optflow` library and VL53L1X time-of-flight sensor. Serves as the standalone optical flow sensor module for the main Flight Controller.

## Overview

- **Camera:** OV2640/OV5640 module → 64×64 grayscale @ 25 Hz
- **Range Sensor:** VL53L1X time-of-flight (altitude)
- **Output:** Flow vector (dx, dy), surface quality, altitude via UART at 38400 baud
- **MCU:** ESP32-S3

## Project Structure

```
flight-optflow/
├── base/
│   ├── boards/
│   │   └── s3v1/              # ESP32-S3 board config & entry point
│   └── foundation/            # Platform abstraction, pub/sub, messages
├── libs/
│   ├── optflow/               # Pre-compiled optical flow library
│   ├── utils/                 # Utility functions
│   └── vl53l1x/              # VL53L1X ToF sensor driver
├── modules/
│   ├── camera/                # Camera capture, publishes SENSOR_CAMERA_FRAME
│   ├── optical_flow/          # Flow calculation, publishes SENSOR_OPTFLOW
│   ├── range_finder/          # VL53L1X driver, publishes SENSOR_RANGE
│   ├── scheduler/             # Dual-core priority-based scheduler
│   └── telemetry/             # Aggregates flow + range → UART output
├── tools/
│   ├── view_frame.py          # Camera frame viewer
│   ├── view_optflow.py        # Optical flow vector viewer
│   └── visualize_flow.py      # Real-time flow visualization
└── docs/
    └── SCHEDULER_ARCHITECTURE.md
```

## Architecture

### Event-Driven Pub/Sub
All inter-module communication uses publish-subscribe — no direct function calls between modules.

### Data Flow
1. **Scheduler** triggers camera capture at 25 Hz
2. **Camera** → publishes `SENSOR_CAMERA_FRAME`
3. **Optical Flow** → subscribes to frame, calculates flow → publishes `SENSOR_OPTFLOW`
4. **Range Finder** → reads VL53L1X periodically → publishes `SENSOR_RANGE`
5. **Telemetry** → subscribes to flow + range → sends UART packet to flight controller

### Dual-Core Threading
| Core | Tasks |
|------|-------|
| **Core 0** | Camera driver (hardware interrupts), low-priority scheduler, WiFi |
| **Core 1** | Optical flow calculation (dense math), range finder I2C |

Camera processing runs at Priority 20, below flight control at Priority 22.

## Dependencies

The `optflow` library must be built and published before building this project:
```bash
cd ../optflow/build-esp32s3
./build.sh    # Compiles and copies to flight-optflow/libs/optflow/
```

## Build & Flash

### Setup Environment
```bash
. $HOME/esp/esp-idf/export.sh
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

## Visualization Tools

```bash
pip install matplotlib pyserial
```

| Tool | Purpose |
|------|---------|
| `tools/view_frame.py` | View raw camera frames |
| `tools/view_optflow.py` | View optical flow vectors |
| `tools/visualize_flow.py` | Real-time dx, dy, quality plots |

## Coding Rules

1. **No cross-module includes** — modules communicate only via pub/sub
2. **Shared structs** in `base/foundation/messages.h`
3. **Topics** in `base/foundation/pubsub.h`
4. **Hardware config** in `base/boards/s3v1/board_config/platform.h`
5. **No module-level logging** — centralized in telemetry module

## Related Projects

| Project | Description |
|---------|-------------|
| [`../optflow/`](../optflow/) | Optical flow library source |
| [`../flight-controller/`](../flight-controller/) | Main flight controller (consumes flow data) |
| [`../robotkit/`](../robotkit/) | Math and fusion library |

## License

Proprietary. See LICENSE file for details.
