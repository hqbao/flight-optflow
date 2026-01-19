# Visualization tool for Optical Flow data
# Usage: python3 tools/visualize_flow.py

import serial
import serial.tools.list_ports
import re
import sys
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import collections

# Config
BAUD_RATE = 115200
HISTORY_LEN = 100

def find_esp32_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "USB" in p.description or "SLAB" in p.description or "CP210" in p.description:
            return p.device
    return None

def main():
    port = find_esp32_port()
    if not port:
        print("No ESP32 found!")
        sys.exit(1)
    
    print(f"Connecting to {port}...")
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
    except:
        print(f"Failed to open {port}")
        sys.exit(1)

    print("Reading Optical Flow Data... (Close window to stop)")

    # Data buffers
    dx_hist = collections.deque(maxlen=HISTORY_LEN)
    dy_hist = collections.deque(maxlen=HISTORY_LEN)
    qual_hist = collections.deque(maxlen=HISTORY_LEN)
    
    # Initialize with zeros
    for _ in range(HISTORY_LEN):
        dx_hist.append(0)
        dy_hist.append(0)
        qual_hist.append(0)

    # Regex for: OF: dx=0.00 	dy=0.00 	qual=0 	RF: dist=0.0 	Freq: 0.0 Hz
    pattern = re.compile(r"OF: dx=([-\d.]+) \tdy=([-\d.]+) \tqual=(\d+)")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    line_dx, = ax1.plot([], [], 'r-', label='DX (mm)')
    line_dy, = ax1.plot([], [], 'b-', label='DY (mm)')
    line_q, = ax2.plot([], [], 'g-', label='Quality')

    ax1.set_title("Optical Flow Motion")
    ax1.set_ylim(-50, 50)
    ax1.legend()
    ax1.grid(True)

    ax2.set_title("Surface Quality")
    ax2.set_ylim(0, 100)
    ax2.grid(True)

    def update(frame):
        # Read all available lines
        while ser.in_waiting:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                match = pattern.search(line)
                if match:
                    dx = float(match.group(1))
                    dy = float(match.group(2))
                    q = int(match.group(3))
                    
                    dx_hist.append(dx)
                    dy_hist.append(dy)
                    qual_hist.append(q)
            except:
                pass
        
        # Update plots
        x_axis = range(len(dx_hist))
        line_dx.set_data(x_axis, dx_hist)
        line_dy.set_data(x_axis, dy_hist)
        line_q.set_data(x_axis, qual_hist)
        
        ax1.set_xlim(0, len(dx_hist))
        ax2.set_xlim(0, len(dx_hist))
        
        return line_dx, line_dy, line_q

    ani = FuncAnimation(fig, update, interval=50, blit=False)
    plt.tight_layout()
    plt.show()
    ser.close()

if __name__ == "__main__":
    main()
