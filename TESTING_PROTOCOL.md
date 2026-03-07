# Testing Protocol

## Rule: ALWAYS verify changes work before asking user to test

### Pre-Delivery Checklist

#### 1. Code Compilation ✓
```bash
source ~/skydev-research/esp/esp-idf/export.sh
cd /Users/bao/skydev/flight-optflow/base/boards/s3v1
idf.py build
# Must succeed with no errors
```

#### 2. Python Syntax Validation ✓
```bash
python3 -m py_compile tools/view_optflow.py
python3 -m py_compile tools/view_frame.py
python3 -m py_compile tools/visualize_flow.py
# Must complete without syntax errors
```

#### 3. Flash & Monitor ✓
```bash
idf.py -p /dev/cu.usbmodem* flash monitor
# Verify:
#   - Boot completes without panics
#   - All modules initialize (Camera, Optical Flow, Range Finder, Scheduler)
#   - Telemetry lines appear at ~25 Hz when ENABLE_DEBUG_LOGGING=1
```

#### 4. Live Data Stream Test ✓
```bash
python3 -c "
import serial, time
s = serial.Serial('/dev/cu.usbmodem31201', 115200, timeout=2)
time.sleep(2)
for i in range(20):
    line = s.readline().decode('utf-8', errors='ignore').strip()
    if line: print(line)
s.close()
"
# Must receive telemetry lines with OF: dx=... dy=... qual=... RF: dist=...
```

#### 5. Integration Verification ✓
- [ ] ESP32 builds successfully (no errors, no new warnings)
- [ ] Python tools pass syntax check
- [ ] Serial data streaming at expected rate (~25 Hz average)
- [ ] UART binary protocol intact (flight controller receives data)
- [ ] No runtime panics or watchdog resets

### Only After ALL Checks Pass:
✅ Present working solution to user with confidence
✅ Provide exact commands to reproduce
✅ Include expected behavior description

### NEVER:
❌ Ask user to test without running verification yourself
❌ Make assumptions about serial port paths (check with `ls /dev/cu.usb*`)
❌ Skip syntax checking Python code
❌ Assume data format without verifying against telemetry.c protocol
