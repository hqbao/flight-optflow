#!/usr/bin/env python3
"""
Frame Viewer - Visual verification of cropped frames
Receives frames from flight-optflow ESP32-S3 via serial monitor
Displays real-time grayscale images with attitude overlay
"""

import serial
import serial.tools.list_ports
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import queue
import threading
import time

# --- Configuration ---
SERIAL_PORT = None
BAUD_RATE = 115200

# Auto-detect serial port
ports = serial.tools.list_ports.comports()
for port, desc, hwid in sorted(ports):
    if 'usbmodem' in port or 'usbserial' in port or 'SLAB' in port:
        SERIAL_PORT = port
        break

if SERIAL_PORT is None:
    print('No serial port found. Please configure manually.')
    SERIAL_PORT = '/dev/cu.usbmodem1101'

print(f"Connecting to {SERIAL_PORT} at {BAUD_RATE} baud...")

# --- Global State ---
frame_queue = queue.Queue(maxsize=5)
crop_info = {'text': 'Waiting for data...'}
stats = {
    'frames_received': 0,
    'last_timestamp': 0,
    'fps': 0,
    'width': 64,
    'height': 64
}

# --- Serial Reader ---
def serial_reader():
    """Parse frame data from ESP32 output"""
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"Connected to {SERIAL_PORT}")
            print("Waiting for frames (make sure ENABLE_FRAME_TRANSMISSION=1)...")
            
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                # Capture CROP log messages
                if 'CROP:' in line and 'ATT[' in line:
                    try:
                        # Extract relevant info from log
                        # Format: I (123) CROP: ATT[x=+0.123 y=-0.045] -> OFF[x=+45 y=-17] -> POS[173,71] (center=128,88)
                        crop_part = line[line.index('CROP:'):] 
                        crop_info['text'] = crop_part
                    except:
                        pass
                
                if line.startswith('FRAME_BIN'):
                    try:
                        # Binary format: FRAME_BIN width height timestamp
                        parts = line.split()
                        width = int(parts[1])
                        height = int(parts[2])
                        timestamp = int(parts[3])
                        
                        # Read raw binary frame data
                        frame_bytes = ser.read(width * height)
                        
                        if len(frame_bytes) == width * height:
                            # Convert to numpy array
                            frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape((height, width))
                            
                            # Read trailing newline
                            ser.readline()
                            
                            # Calculate FPS
                            if stats['last_timestamp'] > 0:
                                dt = (timestamp - stats['last_timestamp']) / 1000000.0  # microseconds to seconds
                                if dt > 0:
                                    stats['fps'] = 1.0 / dt
                            
                            stats['last_timestamp'] = timestamp
                            stats['frames_received'] += 1
                            stats['width'] = width
                            stats['height'] = height
                            
                            # Add to queue (drop old if full)
                            if frame_queue.full():
                                try:
                                    frame_queue.get_nowait()
                                except queue.Empty:
                                    pass
                            frame_queue.put(frame)
                            
                    except Exception as e:
                        print(f"Parse error: {e}")
                        continue
                        
    except Exception as e:
        print(f"Serial error: {e}")

# --- GUI ---
def main():
    # Start serial reader thread
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    
    # Create figure
    fig, (ax_main, ax_hist) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Flight-Optflow Frame Viewer (64x64 Attitude-Compensated Crop)', 
                 fontsize=14, fontweight='bold')
    
    
    # Add crop info overlay at bottom
    crop_text = ax_main.text(0.02, 0.02, '', transform=ax_main.transAxes,
                             fontsize=9, verticalalignment='bottom',
                             bbox=dict(boxstyle='round', facecolor='blue', alpha=0.7),
                             color='yellow', family='monospace')
    # Main image display
    ax_main.set_title('Live Camera Frame')
    ax_main.axis('off')
    im = ax_main.imshow(np.zeros((64, 64)), cmap='gray', vmin=0, vmax=255, interpolation='nearest')
    
    # Add text overlay for stats
    stats_text = ax_main.text(0.02, 0.98, '', transform=ax_main.transAxes,
                              fontsize=10, verticalalignment='top',
                              bbox=dict(boxstyle='round', facecolor='black', alpha=0.7),
                              color='white', family='monospace')
    
    # Histogram
    ax_hist.set_title('Pixel Intensity Distribution')
    ax_hist.set_xlabel('Pixel Value (0-255)')
    ax_hist.set_ylabel('Count')
    ax_hist.set_xlim(0, 255)
    ax_hist.grid(True, alpha=0.3)
    hist_bars = ax_hist.bar(range(256), np.zeros(256), width=1, color='gray')
    
    plt.tight_layout()
    
    # Animation update function
    def update(frame_num):
        # Get latest frame
        current_frame = None
        while not frame_queue.empty():
            try:
                current_frame = frame_queue.get_nowait()
            except queue.Empty:
                break
        
        if current_frame is None:
            return
        
        # Update image
        im.set_data(current_frame)
        
        # Calculate statistics
        mean_val = np.mean(current_frame)
        std_val = np.std(current_frame)
        min_val = np.min(current_frame)
        max_val = np.max(current_frame)
        
        # Update stats text
        stats_str = (
            f"Frames: {stats['frames_received']}\n"
            f"FPS: {stats['fps']:.1f}\n"
            f"Size: {stats['width']}x{stats['height']}\n"
            f"\n"
            f"Mean: {mean_val:.1f}\n"
            f"Std:  {std_val:.1f}\n"
            f"Min:  {min_val}\n"
            f"Max:  {max_val}"
        )
        stats_text.set_text(stats_str)
        
        # Update crop info text
        crop_text.set_text(crop_info['text'])
        
        # Update histogram
        hist, bins = np.histogram(current_frame.flatten(), bins=256, range=(0, 256))
        for bar, h in zip(hist_bars, hist):
            bar.set_height(h)
        ax_hist.set_ylim(0, max(hist) * 1.1 if max(hist) > 0 else 100)
    
    # Start animation
    anim = FuncAnimation(fig, update, interval=100, blit=False, cache_frame_data=False)
    
    plt.show()

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════════════════╗
║          FRAME VIEWER - Visual Crop Verification              ║
╚═══════════════════════════════════════════════════════════════╝

This tool displays the actual 64x64 cropped frames from the camera.

SETUP REQUIRED:
  1. Open: flight-optflow/modules/camera/camera.c
  2. Set: #define ENABLE_FRAME_TRANSMISSION 1
  3. Rebuild and flash firmware
  4. Run this script

The viewer will show:
  - Left: Real-time grayscale camera image (64x64)
  - Right: Pixel intensity histogram
  - Stats: Frame count, FPS, mean/std/min/max values

Use this to verify:
  ✓ Crop window is capturing the right area
  ✓ Attitude compensation shifts the crop correctly
  ✓ Image quality is sufficient for optical flow
  ✓ Features are visible in the frame

NOTE: Frame transmission reduces performance (5Hz update rate)
      to avoid overwhelming the USB serial connection.
      Set ENABLE_FRAME_TRANSMISSION=0 when done testing.

Press Ctrl+C to exit.
""")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down...")
