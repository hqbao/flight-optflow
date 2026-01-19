# Flight Optflow Application

This is an ESP-IDF application for the ESP32-S3/P4 that performs Optical Flow calculations using the `optflow` library and VL53L1X distance sensor. It serves as a standalone testbench for the optical flow subsystem used in the main Flight Controller.

## Overview

- **Sensors:** OV2640/OV5640 Camera Module and VL53L1X (ToF Distance)
- **Output:** Flow vector (dx, dy), Surface Quality, and Altitude (z) via UART/USB
- **Purpose:** Validate optical flow algorithms running on ESP32-S3 using camera input.

## Dependencies

- **Optflow Library**: This project relies on the pre-compiled `optflow` component.
    - The library must be built and published to `components/optflow/` **before** building this project.
    - See `../optflow/README.md` for instructions.

## Build Instructions

### 1. Setup Environment
Ensure you have the ESP-IDF environment activated:
```bash
. $HOME/esp/esp-idf/export.sh
```

### 2. Update Dependencies (Important)
If you have made changes to the `optflow` library, rebuild and publish it first:
```bash
cd ../optflow/build-esp32s3
./build.sh
cd ../../flight-optflow
```

### 3. Build the Project
```bash
idf.py set-target esp32s3
idf.py build
```

### 4. Flash and Monitor
```bash
idf.py -p <PORT> flash monitor
```
Replace `<PORT>` with your device port (e.g., `/dev/cu.usbmodem...`).

## Project Structure

- `docs/`: Technical documentation.
    - `SCHEDULER_ARCHITECTURE.md`: Detailed breakdown of the Dual-Core Scheduler and Camera timings.
- `main/`: Application source code.
    - `main.c`: Main entry point, initializes camera, sensors, and runs optical flow loop.
- `components/`: Local components.
    - `optflow/`: **Auto-generated**. Contains the pre-compiled library and headers.

## System Architecture

### 1. Scheduler
The system runs a **Dual-Core Priority-Based Scheduler** to separate 1kHz flight control loops from 25Hz/10Hz low-priority tasks.
- **High Priority (Core 0/1)**:
    - Fast: 1000, 500, 250, 100 Hz.
    - Slow: 50, 25, 10, 5, 1 Hz (High Precision).
- **Low Priority (Core 0/1)**:
    - Background: 50, 25, 10, 5, 1 Hz (Best Effort).

### 2. Camera & Optical Flow
- **Frame Rate**: locked to **25 Hz** via `SCHEDULER_CORE0_LP_25HZ`.
- **Latency**: Minimized using `CAMERA_GRAB_LATEST`.
- **Preemption**: Camera processing runs at Priority 20 (Lower than Flight Control at 22), ensuring the drone remains stable even during heavy image processing.
    - `vl53l1x/`: Driver for the ToF sensor.
