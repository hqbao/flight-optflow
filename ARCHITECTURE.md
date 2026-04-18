# Flight Optflow Architecture

## Overview

Optical flow sensor module for drone flight controllers. Runs on ESP32-S3, using an OV2640 camera and VL53L1X Time-of-Flight sensor to estimate angular displacement (flow) and altitude distance.

Designed with a strict **Event-Driven PubSub Architecture** — all inter-module communication goes through publish/subscribe, never direct function calls.

## Coding Standards

**All code modifications must follow these rules:**

1. **Strict Decoupling**
   - Modules must **never** include headers from other modules
   - No direct function calls between modules
   - All communication via PubSub (`publish()` / `subscribe()`)

2. **Shared Data**
   - Message structs: `base/foundation/messages.h`
   - Topic enums: `base/foundation/pubsub.h`

3. **Module Structure**
   - Each module lives in `modules/<name>/`
   - Public header exposes only `void <name>_setup(void);`
   - All setup calls happen in `main.c`
   - State uses file-scope `static` variables (not function-scope)

4. **Logging**
   - Debug logging controlled by `ENABLE_DEBUG_LOGGING` in `platform.h`
   - Runtime telemetry output centralized in `modules/telemetry/`

5. **Configuration**
   - Hardware pins and feature flags: `base/boards/s3v1/board_config/platform.h`
   - Frame transmission for debugging: `ENABLE_FRAME_TRANSMISSION` (build with `--frame-tx 1`)

## Data Flow

```
┌───────────┐   25 Hz Trigger    ┌────────┐   SENSOR_CAMERA_FRAME   ┌──────────────┐
│ Scheduler ├────────────────────►│ Camera ├─────────────────────────►│ Optical Flow │
│ (GPTimer) │  Core0 HP 25Hz     │(Core 0)│   (camera_frame_t)      │   (Core 1)   │
└───────────┘                    └────────┘                          └──────┬───────┘
                                                                           │
                                                           SENSOR_OPTFLOW  │
                                                    (optical_flow_result_t)│
                                                                           ▼
┌──────────────┐   SENSOR_RANGE                                    ┌───────────┐
│ Range Finder ├──────────────────────────────────────────────────►│ Telemetry │
│   (Core 1)   │   (range_finder_t)                                │  (UART)   │
└──────────────┘                                                   └───────────┘
```

1. **Scheduler** fires `SCHEDULER_CORE0_HP_25HZ` every 40ms
2. **Camera** receives trigger → captures QVGA frame → crops/resizes to 64×64 → publishes `SENSOR_CAMERA_FRAME`
3. **Optical Flow** receives frame (with atomic busy-guard to prevent tearing) → runs Lucas-Kanade dense flow on Core 1 → publishes `SENSOR_OPTFLOW`
4. **Range Finder** polls VL53L1X at 50Hz (`SCHEDULER_CORE1_LP_50HZ`) → publishes `SENSOR_RANGE`
5. **Telemetry** subscribes to both → sends binary packet over UART (38400 baud) to flight controller

## Module Details

### Camera (`modules/camera/`)
- **Trigger**: `SCHEDULER_CORE0_HP_25HZ` (High Priority band, Core 0)
- **Sensor**: OV2640 at QVGA (320×240), grayscale, XCLK=24 MHz
- **Grab Mode**: `CAMERA_GRAB_LATEST` — always fetches newest DMA frame to minimize latency
- **Frame Buffers**: 6 in PSRAM
- **Processing modes** (controlled by `OPTFLOW_METHOD_CROP` in `platform.h`):
  - `=1`: Center crop 64×64 from 320×240 (5× digital zoom, FOV=13.2°, high sensitivity for hover)
  - `=0`: Bilinear resize full 240×240 square → 64×64 (full FOV=49.5°, better for fast flight)
- **Task**: Priority 20 on Core 0, wakes via `xTaskNotifyGive`
- **Frame Transmission** (when `ENABLE_FRAME_TRANSMISSION=1`): After each capture, copies the 64×64 frame to a TX buffer and notifies `frame_tx_task` (priority 5, Core 0) which sends `FRAME_BIN <W> <H> <timestamp>\n<raw_bytes>` over `stdout` (USB CDC). This reduces optical flow throughput from 25 Hz to ~5 Hz due to USB serial bandwidth — use for debugging only.

### Optical Flow (`modules/optical_flow/`)
- **Input**: Subscribes to `SENSOR_CAMERA_FRAME`
- **Algorithm**: Lucas-Kanade dense optical flow (from `optflow` library)
- **Output**: `optical_flow_result_t` — `dx_rad`, `dy_rad` (angular displacement/frame), `clarity`, `quality`, `dt`
- **Cross-Core Safety**: Uses `atomic_bool g_processing_busy` — if Core 1 is still processing, the new frame from Core 0 is dropped
- **Task**: Priority 20 on Core 1

### Range Finder (`modules/range_finder/`)
- **Sensor**: VL53L1X Time-of-Flight (I2C at 400 kHz)
- **Trigger**: `SCHEDULER_CORE1_LP_50HZ` (Low Priority band, Core 1)
- **Mode**: Long distance, 20ms timing budget, 25ms inter-measurement period
- **Output**: `range_finder_t` — `distance_mm` and `status`
- **Conditional**: Disabled when `ENABLE_RANGE_FINDER=0` in `platform.h`

### Telemetry (`modules/telemetry/`)
- **Input**: Subscribes to `SENSOR_OPTFLOW` and `SENSOR_RANGE`
- **Debug Output**: `ESP_LOGI` with dx, dy, quality, distance, frequency (when `ENABLE_DEBUG_LOGGING=1`)
- **Binary Protocol**: Custom `'db'` framed packet over UART at 38400 baud:
  ```
  ['d']['b'][0x01][direction][len_lo][len_hi][dx_i32][dy_i32][z_i32][quality_i32][ck_a][ck_b]
  ```
  - `dx`/`dy`: radians × 100,000 as int32 (~0.00001 rad precision)
  - `z`: range in mm as int32
  - `quality`: clarity × 10 as int32
  - Checksum: UBX-style Fletcher-8 over bytes 2 through end of payload
  - Note: `dx` is negated in the protocol to match flight controller body frame

### Scheduler (`modules/scheduler/`)
- **Timer**: 1 MHz GPTimer with 1ms (1 kHz) alarm interrupt
- **Architecture**: 2 priority bands × 2 cores = 4 FreeRTOS tasks
  - High Band (Priority 22): ISR-driven 1ms tick, publishes 1000/500/250/100/50/25/10/5/1 Hz topics
  - Low Band (Priority 10): 20ms tick (notified by High Band), publishes 50/25/10/5/1 Hz topics
- See [docs/SCHEDULER_ARCHITECTURE.md](docs/SCHEDULER_ARCHITECTURE.md) for full topic table

## Threading Model

| Core | Task | Priority | Purpose |
|------|------|----------|---------|
| 0 | `sched_c0_h` | 22 | High-band scheduler (1ms tick) |
| 0 | `camera_task` | 20 | Camera capture + crop/resize |
| 0 | `sched_c0_l` | 10 | Low-band scheduler (20ms tick) |
| 0 | `frame_tx_task` | 5 | Raw frame USB transmission (only when `ENABLE_FRAME_TRANSMISSION=1`) |
| 0 | (system) | — | WiFi, networking |
| 1 | `sched_c1_h` | 22 | High-band scheduler (1ms tick) |
| 1 | `optflow_task` | 20 | Optical flow calculation (dense math) |
| 1 | `sched_c1_l` | 10 | Low-band scheduler + range finder callback |

## FPS vs dt

The scheduler triggers at exactly **25 Hz** (every 40ms). However, individual `dt` values in telemetry logs vary (30–75ms) because `dt` measures time between consecutive optflow task wake-ups, which depends on variable camera+processing latency. The **average** over any 240ms window is always 6 frames = 25 fps.

## Message Structs

Defined in `base/foundation/messages.h`:

| Struct | Fields | Topic |
|--------|--------|-------|
| `camera_frame_t` | `data[64×64]`, `timestamp` | `SENSOR_CAMERA_FRAME` |
| `optical_flow_result_t` | `dx_rad`, `dy_rad`, `rotation`, `clarity`, `quality`, `timestamp`, `dt` | `SENSOR_OPTFLOW` |
| `range_finder_t` | `distance_mm`, `status`, `timestamp` | `SENSOR_RANGE` |
