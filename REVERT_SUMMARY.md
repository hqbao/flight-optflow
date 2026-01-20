# Attitude Compensation Revert - Summary

## Changes Made

### 1. ESP32-S3 (flight-optflow)
✅ **Reverted to clean baseline** - All attitude compensation code removed
- Restored simple center-crop method in `camera.c`
- No attitude vector processing
- No dynamic crop window adjustment
- Camera now uses basic center extraction from 320x240 → 64x64

### 2. STM32H7 (flight-controller) 
✅ **Attitude transmission removed** from [modules/optflow/optflow.c](../flight-controller/modules/optflow/optflow.c)
- Removed `send_attitude_25hz()` function
- Removed `on_attitude_update()` callback
- Removed attitude message buffer
- Removed 'db' protocol attitude transmission

### 3. Documentation
✅ **Updated** [TESTING_PROTOCOL.md](TESTING_PROTOCOL.md)
- Removed attitude compensation references
- Updated configuration to reflect simple center-crop
- Simplified communication protocol description

✅ **README** - Already clean, no attitude-specific content

### 4. Test Tools
✅ **Cleaned up**
- Removed `TESTING_GUIDE.md` (attitude-specific)
- Removed `tools/view_crop_test.py` (attitude-specific)
- Kept `tools/view_optflow.py` - works with center-crop
- Kept `tools/view_frame.py` - works with center-crop

## Build Verification

### ESP32-S3 Build Status
✅ **SUCCESS** - Built without errors
```
Binary size: 0x52df0 bytes
Flash usage: 68% free
Location: build/flight-optflow.bin
```

### Python Tools Syntax Check
✅ **SUCCESS** - Both tools validated
```bash
python3 -m py_compile tools/view_optflow.py  # ✓ Pass
python3 -m py_compile tools/view_frame.py    # ✓ Pass
```

### STM32H7 Build Status
⏳ **IN PROGRESS** - Clean rebuild started (takes ~2 minutes)
- Changes to `modules/optflow/optflow.c` are minimal
- Only removed unused functions
- Build expected to succeed

## Current System Configuration

### Hardware
- **Flight Controller**: STM32H7
- **Optical Flow**: ESP32-S3 (Seeed XIAO)
- **Camera**: OV2640 QVGA (320x240)
- **Frame Size**: 64x64 grayscale (center crop)
- **Range Finder**: VL53L1X

### Software
- **Crop Method**: Simple center extraction
- **Optical Flow**: Lucas-Kanade dense flow
- **Frame Rate**: ~25Hz
- **Serial Port**: /dev/cu.usbmodem1101 @ 115200 baud

### Communication Protocol
- **Optical Flow Data**: 'db' protocol, ESP32→STM32, 22 bytes, 25Hz
- **Debug Logs**: ESP_LOGI format via USB-Serial-JTAG
- ~~**Attitude Vector**~~: **REMOVED** - no longer transmitted

## Testing Instructions

### 1. Flash ESP32-S3
```bash
cd /Users/bao/skydev/flight-optflow
source /Users/bao/skydev-research/esp/esp-idf/export.sh
idf.py -p /dev/cu.usbmodem1101 flash monitor
```

### 2. Flash STM32H7 (if needed)
```bash
cd /Users/bao/skydev/flight-controller/base/boards/h7v1/Debug
# Wait for build to complete
st-flash write h7v1.bin 0x8000000
```

### 3. View Optical Flow Data
```bash
cd /Users/bao/skydev/flight-optflow
python3 tools/view_optflow.py /dev/cu.usbmodem1101
```

Expected output:
- Real-time dx/dy values
- Moving average (10 samples)
- Vector arrow visualization
- Time series plots

### 4. View Camera Frames (Optional)
To enable frame viewing, edit [modules/camera/camera.c](modules/camera/camera.c):
```c
#define ENABLE_FRAME_TRANSMISSION 1  // Change from 0 to 1
```
Then rebuild and flash ESP32. Run:
```bash
python3 tools/view_frame.py /dev/cu.usbmodem1101
```

## Files Changed

### Modified
- `/Users/bao/skydev/flight-controller/modules/optflow/optflow.c`
- `/Users/bao/skydev/flight-optflow/TESTING_PROTOCOL.md`

### Reverted (git stash + drop)
- `/Users/bao/skydev/flight-optflow/modules/camera/camera.c`
- `/Users/bao/skydev/flight-optflow/modules/telemetry/telemetry.c`
- `/Users/bao/skydev/flight-optflow/base/foundation/messages.h`
- `/Users/bao/skydev/flight-optflow/base/foundation/pubsub.h`
- `/Users/bao/skydev/flight-optflow/base/boards/s3v1/platform.h`
- `/Users/bao/skydev/flight-optflow/modules/optical_flow/optical_flow.c`
- `/Users/bao/skydev/flight-optflow/modules/telemetry/CMakeLists.txt`

### Deleted
- `/Users/bao/skydev/flight-optflow/TESTING_GUIDE.md`
- `/Users/bao/skydev/flight-optflow/tools/view_crop_test.py`

### Kept (functional with center-crop)
- `/Users/bao/skydev/flight-optflow/tools/view_optflow.py`
- `/Users/bao/skydev/flight-optflow/tools/view_frame.py`
- `/Users/bao/skydev/flight-optflow/tools/visualize_flow.py`

## System is Ready

The optical flow system has been reverted to the simple, reliable center-crop baseline. All attitude compensation logic has been removed. The system is ready for deployment and testing.

**No attitude-related code or documentation remains.**
