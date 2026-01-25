# Testing Protocol - MANDATORY BEFORE USER VERIFICATION

## Rule: ALWAYS verify changes work before asking user to test

### Pre-Delivery Checklist

#### 1. Code Compilation ✓
```bash
cd /Users/bao/skydev/flight-optflow/base/boards/s3v1
source /Users/bao/skydev-research/esp/esp-idf/export.sh 2>/dev/null
idf.py build
# Must succeed with no errors
```

#### 2. Python Syntax Validation ✓
```bash
python3 -m py_compile tools/view_optflow.py
python3 -m py_compile tools/view_frame.py
# Must complete without syntax errors
```

#### 3. Live Data Stream Test ✓
```bash
python3 -c "
import serial, re, time
s = serial.Serial('/dev/cu.usbmodem1101', 115200, timeout=2)
time.sleep(1)
pattern = re.compile(r'OF:\s+dx=([-\d.]+)\s+dy=([-\d.]+)')
samples = [pattern.search(s.readline().decode('utf-8', errors='ignore')) for _ in range(20)]
valid = [m for m in samples if m]
print(f'Valid samples: {len(valid)}/20')
assert len(valid) >= 10, 'Insufficient data rate'
"
# Must receive at least 10 valid samples in 20 reads
```

#### 4. Integration Verification ✓
- [ ] ESP32 builds successfully
- [ ] Python tools have no syntax errors  
- [ ] Serial data streaming at expected rate (~25Hz)
- [ ] Data format matches parser expectations
- [ ] No runtime exceptions in test run

### Only After ALL Checks Pass:
✅ Present working solution to user with confidence
✅ Provide exact command to run
✅ Include expected behavior description

### NEVER:
❌ Ask user to test without running verification yourself
❌ Make assumptions about compatibility
❌ Skip syntax checking Python code
❌ Assume serial data format without verification

---

## Current System Status (2026-01-20)

### Hardware
- **Flight Controller**: STM32H7 @ /Users/bao/skydev/flight-controller
- **Optical Flow**: ESP32-S3 (Seeed XIAO) @ /Users/bao/skydev/flight-optflow  
- **Serial Port**: /dev/cu.usbmodem1101 @ 115200 baud
- **Camera**: OV2640 QVGA (320x240) → 64x64 center crop
- **Range Finder**: VL53L1X

### Communication Protocol
- **Optical Flow**: 'db' protocol, 22 bytes, 25Hz from ESP32→STM32
- **Debug Logs**: ESP_LOGI format via USB-Serial-JTAG

### Working Configuration
- Camera: Simple center crop (no attitude compensation)
- Frame size: 64x64 grayscale from center of 320x240 QVGA
- Optical flow: Lucas-Kanade dense flow algorithm
- Update rate: ~25Hz

### Test Commands
```bash
# View optical flow data
python3 flight-optflow/tools/view_optflow.py /dev/cu.usbmodem1101

# View camera frames (when ENABLE_FRAME_TRANSMISSION=1 in camera.c)
cd flight-controller/base/boards/h7v1/Debug
make clean && make -j8
```

### Known Issues
- None currently (as of last successful verification)

---

**This protocol must be followed for every code change before user interaction.**
