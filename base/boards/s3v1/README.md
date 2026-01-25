# S3 V1 Board Project

This directory contains the main project configuration for the ESP32-S3 Board V1.

## Structure
- **board_config/**: Contains the `platform.h` header with board-specific pinouts and settings. This component is exposed to all other modules.
- **main/**: The application entry point (`main.c`) which initializes the modules.
- **sdkconfig**: The ESP-IDF configuration for this specific board.

## Building
Run all `idf.py` commands from this directory:

```bash
idf.py build
idf.py -p <PORT> flash monitor
```
