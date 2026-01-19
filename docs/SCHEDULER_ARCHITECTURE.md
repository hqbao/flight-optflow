# System Architecture & Scheduler Documentation

## 1. Dual-Core Priority Scheduler

The system uses a custom `modules/scheduler` to manage task execution across both ESP32 cores. It is designed to allow high-frequency control loops (1kHz) to preempt lower-frequency tasks (Telemetry, Logging, Camera).

### Frequency Bands

The scheduler is divided into two priority bands per core:

**1. High-Band (Priority 22)**
*   **Base Tick**: 1ms (1000 Hz) via Hardware Timer (GPTimer)
*   **Interrupts**: Preempts everything except IDLE and Wi-Fi/BT tasks.
*   **Frequencies**:
    *   `1000 Hz`: (Reserved for Rate Controller)
    *   `500 Hz`: (Reserved for Attitude Estimation)
    *   `250 Hz`: (Reserved for Position Estimation)
    *   `100 Hz`: (Reserved for RC Input)
    *   `50 Hz - 1 Hz`: (Available for high-precision low-frequency tasks)

**2. Low-Band (Priority 10)**
*   **Base Tick**: 20ms (50 Hz) Triggered by High-Band logic
*   **Behavior**: Runs when High-Band is idle.
*   **Frequencies**:
    *   `50 Hz`: **Active**: Range Finder (`modules/range_finder`)
    *   `25 Hz`: **Active**: Optical Flow Camera Trigger (`modules/camera`)
    *   `10 Hz`: **Active**: Telemetry Streaming (`main.c`)
    *   `5 Hz`: (Reserved for Battery Check)
    *   `1 Hz`: (Reserved for LED Heartbeat)

### PubSub Topics
To use these frequencies, subscribe to the corresponding topic in `pubsub.h`. 
Note: Low frequencies (<= 50Hz) are available on both High Priority (HP) and Low Priority (LP) bands. HP is strictly timed; LP runs when CPU is free.

| Frequency | Core 0 Topic (HP / LP) | Core 1 Topic (HP / LP) |
| :--- | :--- | :--- |
| **1000 Hz** | `SCHEDULER_CORE0_HP_1000HZ` | `SCHEDULER_CORE1_HP_1000HZ` |
| **500 Hz** | `SCHEDULER_CORE0_HP_500HZ` | `SCHEDULER_CORE1_HP_500HZ` |
| **250 Hz** | `SCHEDULER_CORE0_HP_250HZ` | `SCHEDULER_CORE1_HP_250HZ` |
| **100 Hz** | `SCHEDULER_CORE0_HP_100HZ` | `SCHEDULER_CORE1_HP_100HZ` |
| **50 Hz** | `SCHEDULER_CORE0_HP_50HZ` / `_LP_50HZ` | `SCHEDULER_CORE1_HP_50HZ` / `_LP_50HZ` |
| **25 Hz** | `SCHEDULER_CORE0_HP_25HZ` / `_LP_25HZ` | `SCHEDULER_CORE1_HP_25HZ` / `_LP_25HZ` |
| **10 Hz** | `SCHEDULER_CORE0_HP_10HZ` / `_LP_10HZ` | `SCHEDULER_CORE1_HP_10HZ` / `_LP_10HZ` |
| **5 Hz** | `SCHEDULER_CORE0_HP_5HZ` / `_LP_5HZ` | `SCHEDULER_CORE1_HP_5HZ` / `_LP_5HZ` |
| **1 Hz** | `SCHEDULER_CORE0_HP_1HZ` / `_LP_1HZ` | `SCHEDULER_CORE1_HP_1HZ` / `_LP_1HZ` |

---

## 2. Camera Subsystem

The camera module (`modules/camera`) is configured to run synchronously with the scheduler to ensure flight stability.

### Configuration
*   **Trigger Source**: `SCHEDULER_CORE0_HP_25HZ` (25 FPS, High Priority Band)
    *   Running on **Core 0** as requested.
*   **Wait Mode**: `ulTaskNotifyTake(pdTRUE, portMAX_DELAY)` waits for scheduler event.
*   **Grab Mode**: `CAMERA_GRAB_LATEST`
    *   Why? This ensures that when the 25Hz trigger fires, we fetch the *newest* complete frame from the DMA buffer, minimizing motion-to-photon latency for Optical Flow calculations.
*   **Task Priority**: **20**
    *   This is strictly **lower** than the High-Band Scheduler (22).
    *   **Result**: Flight control tasks (Core 0) will preempt camera processing.

### Electrical Settings
*   **XCLK**: 20 MHz
    *   Reduced from 24MHz to improve signal integrity and reduce `EV-VSYNC-OVF` errors.
    *   20MHz is sufficient for significantly >30FPS at QVGA resolution.
