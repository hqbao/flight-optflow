# Flight Optflow Architecture

## Overview
This project is an optical flow sensor module for flight controllers. It runs on the ESP32-S3 and uses a camera (OV7725/OV2640/etc) and a Time-of-Flight sensor (VL53L1X) to estimate velocity (flow) and distance.

The system is designed with a strict **Event-Driven PubSub Architecture** to ensure modularity and decoupling.

## "Rules for AI" (Coding Standards)
**All AI agents modifying this codebase must adhere to these rules:**

1.  **Strict Decoupling**: 
    -   Modules must **NEVER** include headers from other modules (e.g., `optical_flow.c` cannot include `camera.h`).
    -   Direct function calls between modules are **forbidden**.
    -   Communication must occur exclusively via the PubSub system.

2.  **Shared Data Support**:
    -   All shared data structures (message payloads) must be defined in `base/foundation/messages.h`.
    -   All PubSub topics must be defined in `base/foundation/pubsub.h`.

3.  **Module Structure**:
    -   Each module resides in `modules/<name>/`.
    -   Each module has a public header `<name>.h` exposing only its setup function (e.g., `void camera_setup(void);`).
    -   Initialization is performed in `main.c`.

4.  **Logging**:
    -   Modules should not contain their own logging logic.
    -   Debug logging is centralized in `modules/telemetry` (for now) or a dedicated logger, controllable via `#define ENABLE_DEBUG_LOGGING` in `platform.h`.

5.  **Configuration**:
    -   Hardware-specific pinouts and feature flags (e.g., `ENABLE_RANGE_FINDER`) are located in `base/boards/s3v1/platform.h`.

## System Components

### Foundation (`base/foundation/`)
-   **PubSub**: A lightweight publish-subscribe system used for all inter-module communication.
-   **Messages**: Central repository for data types (`optical_flow_result_t`, `camera_frame_t`, etc.).

### Modules (`modules/`)
-   **Camera**: Captures frames. Publishes `SENSOR_CAMERA_FRAME` to a shared memory buffer. Runs on **Core 0** (Driver requirement).
-   **Optical Flow**: Consumes frame data, calculates flow (dx, dy). Publishes `SENSOR_OPTFLOW`. Calculation runs on **Core 1** (Heavy math).
-   **Range Finder**: Reads VL53L1X distance. Publishes `SENSOR_RANGE`.
-   **Telemetry**: Aggregates `SENSOR_OPTFLOW` and `SENSOR_RANGE` and sends the data over UART to the flight controller (MSP/MSPv2-like protocol). Also handles debug printing.
-   **Scheduler**: Manages periodic tasks on both cores.

### Hardware Abstraction (`base/boards/`)
-   **Platform**: Defines GPIO mappings and enable/disable macros for hardware features.

## Data Flow
1.  **Scheduler** triggers camera capture.
2.  **Camera** captures frame -> Publishes `SENSOR_CAMERA_FRAME`.
3.  **Optical Flow** subscribes to frame -> Calculates flow -> Publishes `SENSOR_OPTFLOW`.
4.  **Range Finder** (Periodically triggered) -> Reads sensor -> Publishes `SENSOR_RANGE`.
5.  **Telemetry** subscribes to `SENSOR_OPTFLOW` & `SENSOR_RANGE` -> Sends UART packet.

## Threading Model
-   **Core 0**:
    -   Wifi/Networking (system default)
    -   Camera Driver (Hardware Interrupts)
    -   Scheduler Low Priority
-   **Core 1**:
    -   Optical Flow Calculation (Dense Math)
    -   Range Finder I2C
