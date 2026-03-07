# Scheduler Architecture

## Dual-Core Priority Scheduler

The system uses `modules/scheduler` to manage periodic task execution across both ESP32-S3 cores. A single GPTimer fires at 1 kHz; the ISR notifies high-priority tasks on both cores. Low-priority tasks are triggered every 20ms by the high-priority task.

### Frequency Bands

Two priority bands per core (4 FreeRTOS tasks total):

**1. High-Band (Priority 22)**
- **Base Tick**: 1ms (1000 Hz) via GPTimer ISR
- **Behavior**: Preempts everything except Wi-Fi/BT system tasks
- **Frequencies**: 1000, 500, 250, 100, 50, 25, 10, 5, 1 Hz
- **Active subscribers**:
  - `SCHEDULER_CORE0_HP_25HZ` → Camera trigger (`modules/camera`)

**2. Low-Band (Priority 10)**
- **Base Tick**: 20ms (50 Hz), notified by High-Band every `tick % 20 == 0`
- **Behavior**: Runs when High-Band is idle
- **Frequencies**: 50, 25, 10, 5, 1 Hz
- **Active subscribers**:
  - `SCHEDULER_CORE1_LP_50HZ` → Range Finder (`modules/range_finder`)

### PubSub Topics

Subscribe to any frequency/core/band combination via `pubsub.h`:

| Frequency | Core 0 (HP / LP) | Core 1 (HP / LP) |
| :--- | :--- | :--- |
| **1000 Hz** | `SCHEDULER_CORE0_HP_1000HZ` | `SCHEDULER_CORE1_HP_1000HZ` |
| **500 Hz** | `SCHEDULER_CORE0_HP_500HZ` | `SCHEDULER_CORE1_HP_500HZ` |
| **250 Hz** | `SCHEDULER_CORE0_HP_250HZ` | `SCHEDULER_CORE1_HP_250HZ` |
| **100 Hz** | `SCHEDULER_CORE0_HP_100HZ` | `SCHEDULER_CORE1_HP_100HZ` |
| **50 Hz** | `_HP_50HZ` / `_LP_50HZ` | `_HP_50HZ` / `_LP_50HZ` |
| **25 Hz** | `_HP_25HZ` / `_LP_25HZ` | `_HP_25HZ` / `_LP_25HZ` |
| **10 Hz** | `_HP_10HZ` / `_LP_10HZ` | `_HP_10HZ` / `_LP_10HZ` |
| **5 Hz** | `_HP_5HZ` / `_LP_5HZ` | `_HP_5HZ` / `_LP_5HZ` |
| **1 Hz** | `_HP_1HZ` / `_LP_1HZ` | `_HP_1HZ` / `_LP_1HZ` |

HP bands are strictly ISR-timed (jitter < 1ms). LP bands run opportunistically when the CPU is free.

---

## Camera Subsystem

The camera module (`modules/camera`) is triggered by the High Priority scheduler to ensure consistent timing.

### Configuration
- **Trigger**: `SCHEDULER_CORE0_HP_25HZ` (High Priority, Core 0)
- **Task**: `camera_task` at Priority 20 on Core 0
- **Wait Mode**: `ulTaskNotifyTake(pdTRUE, portMAX_DELAY)` — sleeps until scheduler fires
- **Grab Mode**: `CAMERA_GRAB_LATEST` — fetches the newest DMA frame, minimizing motion-to-photon latency
- **Frame Buffers**: 6 in PSRAM

### Electrical Settings
- **XCLK**: 24 MHz — drives OV2640 at QVGA (320×240) grayscale
- **Frame Rate**: Camera hardware runs at >30 fps continuously; software triggers capture at 25 Hz

### Priority Design
- Camera task (20) is **lower** than the scheduler (22), so scheduler ticks are never blocked
- Camera task (20) is **equal** to the optflow task, but on different cores (Core 0 vs Core 1)

---

## Optical Flow Subsystem

- **Input**: Subscribes to `SENSOR_CAMERA_FRAME` (published by camera on Core 0)
- **Task**: `optflow_task` at Priority 20 on Core 1
- **Cross-Core Safety**: `atomic_bool g_processing_busy` prevents frame buffer overwrite during processing

---

## Range Finder Subsystem

- **Trigger**: `SCHEDULER_CORE1_LP_50HZ` (Low Priority, Core 1)
- **Sensor**: VL53L1X via I2C at 400 kHz
- **Behavior**: Non-blocking poll — checks `VL53L1_GetMeasurementDataReady()` each tick, publishes only when data is ready
