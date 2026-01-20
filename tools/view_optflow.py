#!/usr/bin/env python3
"""
Optical Flow Visualizer
Reads optical flow data from flight-optflow ESP32-S3 via serial monitor logs
Displays real-time flow vectors and statistics
"""

import serial
import serial.tools.list_ports
import re
import threading
import queue
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow
from matplotlib.widgets import Button
import time
from collections import deque

# --- Configuration ---
SERIAL_PORT = None
BAUD_RATE = 115200  # ESP32 monitor baud rate
MOVING_AVG_WINDOW = 10  # Number of samples for moving average

# Auto-detect serial port
ports = serial.tools.list_ports.comports()
for port, desc, hwid in sorted(ports):
    if 'usbmodem' in port or 'usbserial' in port or 'SLAB' in port:
        SERIAL_PORT = port
        break

if SERIAL_PORT is None:
    print('No serial port found. Please configure manually.')
    SERIAL_PORT = '/dev/cu.usbmodem1101'  # Default

print(f"Connecting to {SERIAL_PORT} at {BAUD_RATE} baud...")
print("")
print("=" * 60)
print("ATTITUDE COMPENSATION TEST PROCEDURE:")
print("=" * 60)
print("1. Place sensor LEVEL on table, keep still for 5 seconds")
print("   -> Watch 'Avg DX/DY' values (should be near 0)")
print("")
print("2. SLOWLY tilt forward ~10 degrees, hold for 3 seconds")
print("   -> If compensation works: Avg DX/DY stay near 0")
print("   -> If not working: Avg DY will spike to ~40-60mm")
print("")
print("3. SLOWLY tilt backward ~10 degrees, hold for 3 seconds")
print("   -> Avg DY should stay near 0 (opposite direction)")
print("")
print("4. SLOWLY tilt left/right ~10 degrees")
print("   -> Avg DX should stay near 0")
print("=" * 60)
print("")

# --- Global State ---
data_queue = queue.Queue(maxsize=1)  # Only keep latest sample for real-time response
history_length = 50
flow_history = deque(maxlen=history_length)
dx_window = deque(maxlen=MOVING_AVG_WINDOW)
dy_window = deque(maxlen=MOVING_AVG_WINDOW)

# Statistics
total_samples = 0
avg_dx = 0
avg_dy = 0
avg_quality = 0
avg_fps = 0

# --- Serial Reader ---
def serial_reader():
    """Parse ESP_LOGI output from telemetry.c"""
    global total_samples, avg_dx, avg_dy, avg_quality, avg_fps
    
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"Connected to {SERIAL_PORT}")
            
            # Pattern: OF: dx=-0.12 	dy=0.34 	qual=56 	RF: dist=1234.5 	Freq: 24.8 Hz
            pattern = re.compile(
                r'OF:\s+dx=([-\d.]+)\s+dy=([-\d.]+)\s+qual=(\d+)\s+RF:\s+dist=([\d.]+)\s+Freq:\s+([\d.]+)\s+Hz'
            )
            
            while True:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    match = pattern.search(line)
                    if match:
                        dx = float(match.group(1))
                        dy = float(match.group(2))
                        quality = int(match.group(3))
                        distance = float(match.group(4))
                        fps = float(match.group(5))
                        
                        # Update statistics
                        total_samples += 1
                        alpha = 0.1  # Moving average factor
                        avg_dx = avg_dx * (1 - alpha) + dx * alpha
                        avg_dy = avg_dy * (1 - alpha) + dy * alpha
                        
                        # Add to moving average windows
                        dx_window.append(dx)
                        dy_window.append(dy)
                        avg_quality = avg_quality * (1 - alpha) + quality * alpha
                        avg_fps = avg_fps * (1 - alpha) + fps * alpha
                        
                        data = {
                            'dx': dx,
                            'dy': dy,
                            'quality': quality,
                            'distance': distance,
                            'fps': fps,
                            'timestamp': time.time()
                        }
                        
                        # Drop old data if queue is full for real-time response
                        if data_queue.full():
                            try:
                                data_queue.get_nowait()
                            except queue.Empty:
                                pass
                        data_queue.put(data)
                        flow_history.append((dx, dy, quality))
                        
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"Parse error: {e}")
                    continue
                    
    except Exception as e:
        print(f"Serial error: {e}")

# --- GUI ---
def main():
    global flow_history, total_samples, avg_dx, avg_dy, avg_quality, avg_fps
    
    # Start serial reader thread
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))
    
    # Main flow vector display (large)
    ax_main = plt.subplot2grid((3, 3), (0, 0), colspan=2, rowspan=2)
    ax_main.set_xlim(-50, 50)
    ax_main.set_ylim(-50, 50)
    ax_main.set_xlabel('X Flow (mm)')
    ax_main.set_ylabel('Y Flow (mm)')
    ax_main.set_title('Optical Flow Vector (Real-Time)', fontsize=14, fontweight='bold')
    ax_main.grid(True, alpha=0.3)
    ax_main.axhline(0, color='k', linewidth=0.5)
    ax_main.axvline(0, color='k', linewidth=0.5)
    
    # Current vector arrow
    current_arrow = None
    
    # History trail
    trail_line, = ax_main.plot([], [], 'b-', alpha=0.3, linewidth=1, label='Trail')
    trail_scatter = ax_main.scatter([], [], c=[], cmap='viridis', s=20, alpha=0.6, vmin=0, vmax=100)
    
    # Time series plots
    ax_dx = plt.subplot2grid((3, 3), (0, 2))
    ax_dx.set_title('DX (mm) vs Time')
    ax_dx.set_ylim(-50, 50)
    ax_dx.grid(True, alpha=0.3)
    line_dx, = ax_dx.plot([], [], 'r-', linewidth=2)
    
    ax_dy = plt.subplot2grid((3, 3), (1, 2))
    ax_dy.set_title('DY (mm) vs Time')
    ax_dy.set_ylim(-50, 50)
    ax_dy.grid(True, alpha=0.3)
    line_dy, = ax_dy.plot([], [], 'g-', linewidth=2)
    
    ax_qual = plt.subplot2grid((3, 3), (2, 0))
    ax_qual.set_title('Quality vs Time')
    ax_qual.set_xlabel('Sample')
    ax_qual.set_ylim(0, 100)
    ax_qual.grid(True, alpha=0.3)
    line_qual, = ax_qual.plot([], [], 'orange', linewidth=2)
    
    # Statistics display
    ax_stats = plt.subplot2grid((3, 3), (2, 1), colspan=2)
    ax_stats.axis('off')
    stats_text = ax_stats.text(0.1, 0.5, '', fontsize=12, family='monospace',
                               verticalalignment='center',
                               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Control buttons
    plt.subplots_adjust(bottom=0.12, right=0.95, top=0.95, left=0.08, hspace=0.3, wspace=0.3)
    
    ax_clear = plt.axes([0.35, 0.02, 0.12, 0.05])
    btn_clear = Button(ax_clear, 'Clear History')
    
    ax_scale = plt.axes([0.5, 0.02, 0.12, 0.05])
    btn_scale = Button(ax_scale, 'Auto Scale')
    
    scale_mode = [False]  # Use list for mutability in closure
    
    def clear_history(event):
        flow_history.clear()
        print("History cleared")
    
    def toggle_scale(event):
        scale_mode[0] = not scale_mode[0]
        btn_scale.label.set_text('Fixed Scale' if scale_mode[0] else 'Auto Scale')
        print(f"Scale mode: {'Auto' if scale_mode[0] else 'Fixed'}")
    
    btn_clear.on_clicked(clear_history)
    btn_scale.on_clicked(toggle_scale)
    
    # Animation update function
    def update(frame):
        nonlocal current_arrow
        
        # Get only the latest data (discard any buffered old samples)
        latest_data = None
        while not data_queue.empty():
            try:
                latest_data = data_queue.get_nowait()
            except queue.Empty:
                break
        
        if latest_data is None:
            return
        
        dx = latest_data['dx']
        dy = latest_data['dy']
        quality = latest_data['quality']
        distance = latest_data['distance']
        fps = latest_data['fps']
        
        # Update main arrow - safely remove old one
        if current_arrow is not None:
            try:
                current_arrow.remove()
            except (ValueError, AttributeError):
                pass  # Arrow already removed or invalid
            current_arrow = None
        
        # Arrow color based on quality
        color = 'green' if quality > 50 else 'orange' if quality > 20 else 'red'
        arrow_width = 0.3 + (quality / 100.0) * 0.5  # Thickness indicates quality
        
        if abs(dx) > 0.1 or abs(dy) > 0.1:  # Only draw if significant movement
            current_arrow = FancyArrow(0, 0, dx, dy,
                                      width=arrow_width,
                                      head_width=arrow_width*3,
                                      head_length=3,
                                      fc=color, ec='black',
                                      alpha=0.8, length_includes_head=True)
            ax_main.add_patch(current_arrow)
        
        # Update trail
        if len(flow_history) > 1:
            dx_hist = [f[0] for f in flow_history]
            dy_hist = [f[1] for f in flow_history]
            qual_hist = [f[2] for f in flow_history]
            
            trail_line.set_data(dx_hist, dy_hist)
            trail_scatter.set_offsets(np.c_[dx_hist, dy_hist])
            trail_scatter.set_array(np.array(qual_hist))
        
        # Auto scale if enabled
        if scale_mode[0] and len(flow_history) > 5:
            dx_vals = [f[0] for f in flow_history]
            dy_vals = [f[1] for f in flow_history]
            max_range = max(max(abs(min(dx_vals)), abs(max(dx_vals))),
                          max(abs(min(dy_vals)), abs(max(dy_vals)))) * 1.2
            max_range = max(max_range, 5)  # Minimum range
            ax_main.set_xlim(-max_range, max_range)
            ax_main.set_ylim(-max_range, max_range)
        
        # Update time series
        if len(flow_history) > 1:
            x_range = list(range(len(flow_history)))
            dx_series = [f[0] for f in flow_history]
            dy_series = [f[1] for f in flow_history]
            qual_series = [f[2] for f in flow_history]
            
            line_dx.set_data(x_range, dx_series)
            ax_dx.set_xlim(0, max(len(flow_history), 10))
            
            line_dy.set_data(x_range, dy_series)
            ax_dy.set_xlim(0, max(len(flow_history), 10))
            
            line_qual.set_data(x_range, qual_series)
            ax_qual.set_xlim(0, max(len(flow_history), 10))
        
        # Update statistics
        magnitude = np.sqrt(dx**2 + dy**2)
        direction = np.degrees(np.arctan2(dy, dx)) if magnitude > 0.1 else 0
        
        # Calculate moving averages from windows
        ma_dx = np.mean(dx_window) if len(dx_window) > 0 else 0
        ma_dy = np.mean(dy_window) if len(dy_window) > 0 else 0
        ma_mag = np.sqrt(ma_dx**2 + ma_dy**2)
        
        stats_str = (
            f"CURRENT: DX={dx:+6.2f}  DY={dy:+6.2f}  Q={quality:3d}\n"
            f"                                        \n"
            f"Moving Avg ({MOVING_AVG_WINDOW} samples):\n"
            f"  DX = {ma_dx:+7.2f} mm\n"
            f"  DY = {ma_dy:+7.2f} mm\n"
            f"  MAG = {ma_mag:6.2f} mm\n"
            f"                                        \n"
            f"Expected if compensation works:\n"
            f"  Level: DX,DY ≈ ±2mm\n"
            f"  Tilted 10°: DX,DY still ≈ ±2mm\n"
            f"                                        \n"
            f"Samples: {total_samples}  FPS: {fps:.1f}"
        )
        
        stats_text.set_text(stats_str)
    
    # Start animation at 50Hz for smooth real-time updates (faster than data rate)
    from matplotlib.animation import FuncAnimation
    anim = FuncAnimation(fig, update, interval=20, blit=False)  # 20ms = 50Hz
    
    plt.show()

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════════╗
║          OPTICAL FLOW VISUALIZER - flight-optflow             ║
╚═══════════════════════════════════════════════════════════════╝

Instructions:
  1. Connect flight-optflow ESP32-S3 via USB
  2. Ensure flight-controller is sending attitude vectors
  3. Monitor will display real-time flow vectors
  4. Green arrows = high quality, Red = low quality
  5. Arrow thickness indicates tracking confidence

Controls:
  - Clear History: Reset trail visualization
  - Auto Scale: Toggle between fixed/auto axis scaling
  - Close window to exit

Interpretation:
  - DX/DY: Movement in mm (compensated for tilt)
  - Quality: Feature tracking confidence (0-100)
  - Distance: Range finder altitude in mm
  - FPS: Frame processing rate

""")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down...")
