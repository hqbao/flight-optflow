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

- `main/`: Application source code.
    - `main.c`: Main entry point, initializes camera, sensors, and runs optical flow loop.
- `components/`: Local components.
    - `optflow/`: **Auto-generated**. Contains the pre-compiled library and headers.
    - `vl53l1x/`: Driver for the ToF sensor.
