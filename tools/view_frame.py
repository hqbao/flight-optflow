#!/usr/bin/env python3
"""
Camera Frame Viewer — flight-optflow ESP32-S3
Displays live 64x64 grayscale frames transmitted over USB serial.

Requires: --frame-tx 1 at build time:
  cd flight-optflow/base/boards/s3v1 && ./build.sh --frame-tx 1
"""

import serial
import serial.tools.list_ports
import numpy as np
import matplotlib
import sys
matplotlib.use('macosx' if sys.platform == 'darwin' else 'TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
import queue
import threading
import time

# ── Theme (matches flight-controller tools) ──────────────────────────────────
BG_COLOR      = '#1e1e1e'
PANEL_COLOR   = '#252526'
TEXT_COLOR    = '#cccccc'
DIM_TEXT      = '#888888'
GRID_COLOR    = '#3c3c3c'
BTN_COLOR     = '#333333'
BTN_HOVER     = '#444444'

COLOR_HIST    = '#5599ff'
COLOR_MEAN    = '#ffa726'
COLOR_FPS     = '#4fc3f7'

# ── Configuration ─────────────────────────────────────────────────────────────
BAUD_RATE = 115200
ANIM_MS   = 80   # ~12 Hz refresh

# ── Serial auto-detect ───────────────────────────────────────────────────────
def find_serial_port():
    for port, desc, hwid in sorted(serial.tools.list_ports.comports()):
        if any(k in port for k in ('usbmodem', 'usbserial', 'SLAB', 'ttyACM', 'ttyUSB', 'COM')):
            return port
    return '/dev/cu.usbmodem1101'

# ── Global state ──────────────────────────────────────────────────────────────
g_frame_queue = queue.Queue(maxsize=4)
g_crop_info = ''
g_stats = {
    'frames': 0,
    'last_ts': 0,
    'fps': 0.0,
    'width': 64,
    'height': 64,
}
g_display_fps = 0.0
g_fps_ts = 0.0
g_fps_count = 0

# ── Serial reader thread ─────────────────────────────────────────────────────
MARKER = b'FRAME_BIN '

def serial_reader(port):
    """Raw byte-buffer reader — handles sync and binary data containing 0x0A."""
    global g_crop_info

    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                print(f"[serial] connected to {port}")
                buf = b''

                while True:
                    # Read whatever is available (at least 1 byte)
                    chunk = ser.read(ser.in_waiting or 1)
                    if not chunk:
                        continue
                    buf += chunk

                    # Process all complete frames in buffer
                    while True:
                        idx = buf.find(MARKER)
                        if idx < 0:
                            # Keep tail in case marker is split across reads
                            if len(buf) > len(MARKER):
                                buf = buf[-(len(MARKER) - 1):]
                            break

                        # Discard everything before marker
                        buf = buf[idx:]

                        # Find end of header line
                        nl = buf.find(b'\n')
                        if nl < 0:
                            break  # need more data for complete header

                        header = buf[:nl].decode('utf-8', errors='ignore')
                        buf = buf[nl + 1:]

                        parts = header.split()
                        if len(parts) < 4:
                            continue

                        try:
                            width = int(parts[1])
                            height = int(parts[2])
                            timestamp = int(parts[3])
                        except (ValueError, IndexError):
                            continue

                        total = width * height
                        if total <= 0 or total > 65536:
                            continue

                        # Read remaining frame bytes if needed
                        while len(buf) < total:
                            more = ser.read(min(total - len(buf), 4096))
                            if not more:
                                break
                            buf += more

                        if len(buf) < total:
                            continue  # timeout — discard partial

                        frame_bytes = buf[:total]
                        buf = buf[total:]

                        frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape((height, width))

                        # FPS from sensor timestamps
                        if g_stats['last_ts'] > 0:
                            dt = (timestamp - g_stats['last_ts']) / 1e6
                            if dt > 0:
                                g_stats['fps'] = g_stats['fps'] * 0.7 + (1.0 / dt) * 0.3

                        g_stats['last_ts'] = timestamp
                        g_stats['frames'] += 1
                        g_stats['width'] = width
                        g_stats['height'] = height

                        if g_frame_queue.full():
                            try:
                                g_frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        g_frame_queue.put(frame)

        except serial.SerialException as e:
            print(f"[serial] {e} — retrying in 2s")
            time.sleep(2)
        except Exception as e:
            print(f"[serial] unexpected: {e}")
            time.sleep(1)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global g_display_fps, g_fps_ts, g_fps_count

    port = find_serial_port()
    print(f"Using serial port: {port}")

    t = threading.Thread(target=serial_reader, args=(port,), daemon=True)
    t.start()

    # ── Figure layout ─────────────────────────────────────────────────────────
    plt.rcParams.update({
        'figure.facecolor': BG_COLOR,
        'axes.facecolor':   PANEL_COLOR,
        'text.color':       TEXT_COLOR,
    })

    fig = plt.figure(figsize=(14, 7))
    fig.canvas.manager.set_window_title('Camera Frame Viewer — flight-optflow')

    # Image (large, left), histogram (top-right), stats (bottom-right)
    ax_img  = fig.add_axes([0.03, 0.08, 0.55, 0.86])
    ax_hist = fig.add_axes([0.64, 0.52, 0.34, 0.42])
    ax_info = fig.add_axes([0.64, 0.08, 0.34, 0.38])

    # ── Image panel ───────────────────────────────────────────────────────────
    ax_img.set_facecolor('#000000')
    ax_img.set_title('Live Camera Frame (64\u00d764)', fontsize=10, fontweight='bold',
                     color=TEXT_COLOR, loc='left', pad=6)
    ax_img.axis('off')
    im = ax_img.imshow(np.zeros((64, 64), dtype=np.uint8), cmap='gray',
                       vmin=0, vmax=255, interpolation='nearest', aspect='equal')

    # Crop info overlay (bottom of image)
    crop_text = ax_img.text(0.02, 0.02, '', transform=ax_img.transAxes,
                            fontfamily='monospace', fontsize=7, color='#ffcc00',
                            va='bottom',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='#000000', alpha=0.7))

    # ── Histogram panel ───────────────────────────────────────────────────────
    ax_hist.set_facecolor(PANEL_COLOR)
    ax_hist.set_title('Pixel Distribution', fontsize=10, fontweight='bold',
                      color=COLOR_HIST, loc='left', pad=6)
    ax_hist.set_xlabel('Intensity', fontsize=8, color=DIM_TEXT)
    ax_hist.set_ylabel('Count', fontsize=8, color=DIM_TEXT)
    ax_hist.set_xlim(0, 255)
    ax_hist.tick_params(colors=DIM_TEXT, labelsize=7)
    ax_hist.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.3, linestyle=':')
    for spine in ax_hist.spines.values():
        spine.set_color(GRID_COLOR)

    # Pre-create bar container (fast update via set_height)
    hist_x = np.arange(256)
    hist_bars = ax_hist.bar(hist_x, np.zeros(256), width=1.0, color=COLOR_HIST, alpha=0.7)

    # Mean line
    mean_line = ax_hist.axvline(128, color=COLOR_MEAN, linewidth=1.5, linestyle='--', alpha=0.8)
    mean_label = ax_hist.text(0.98, 0.92, '', transform=ax_hist.transAxes,
                              fontfamily='monospace', fontsize=8, fontweight='bold',
                              color=COLOR_MEAN, ha='right', va='top')

    # ── Info panel ────────────────────────────────────────────────────────────
    ax_info.set_facecolor(PANEL_COLOR)
    ax_info.axis('off')
    for spine in ax_info.spines.values():
        spine.set_color(GRID_COLOR)

    info_text = ax_info.text(0.08, 0.92, '', fontfamily='monospace', fontsize=10,
                             color=TEXT_COLOR, va='top', transform=ax_info.transAxes,
                             linespacing=1.8)

    # ── Clear button ──────────────────────────────────────────────────────────
    ax_btn = fig.add_axes([0.005, 0.005, 0.08, 0.04])
    btn_clear = Button(ax_btn, 'Reset', color=BTN_COLOR, hovercolor=BTN_HOVER)
    btn_clear.label.set_fontsize(8)
    btn_clear.label.set_color(TEXT_COLOR)

    def on_reset(event):
        g_stats['frames'] = 0
        g_stats['fps'] = 0.0
        g_stats['last_ts'] = 0

    btn_clear.on_clicked(on_reset)

    # ── Animation ─────────────────────────────────────────────────────────────
    def update(frame_num):
        global g_display_fps, g_fps_ts, g_fps_count

        current_frame = None
        while not g_frame_queue.empty():
            try:
                current_frame = g_frame_queue.get_nowait()
            except queue.Empty:
                break

        if current_frame is None:
            return

        # Image
        im.set_data(current_frame)

        # Crop overlay
        crop_text.set_text(g_crop_info)

        # Statistics
        mean_val = float(np.mean(current_frame))
        std_val  = float(np.std(current_frame))
        min_val  = int(np.min(current_frame))
        max_val  = int(np.max(current_frame))

        # Histogram
        hist, _ = np.histogram(current_frame.flatten(), bins=256, range=(0, 256))
        for bar, h in zip(hist_bars, hist):
            bar.set_height(h)
        h_max = int(hist.max())
        ax_hist.set_ylim(0, max(h_max * 1.15, 10))

        mean_line.set_xdata([mean_val, mean_val])
        mean_label.set_text(f"\u03bc={mean_val:.0f}")

        # UI FPS
        now = time.time()
        g_fps_count += 1
        if now - g_fps_ts >= 1.0:
            g_display_fps = g_fps_count / (now - g_fps_ts)
            g_fps_count = 0
            g_fps_ts = now

        # Info text
        info_text.set_text(
            f"  FRAME\n"
            f"  Size     {g_stats['width']}\u00d7{g_stats['height']}\n"
            f"  Count    {g_stats['frames']}\n"
            f"  Sensor   {g_stats['fps']:.1f} Hz\n"
            f"  UI FPS   {g_display_fps:.0f}\n"
            f"\n"
            f"  PIXELS\n"
            f"  Mean     {mean_val:.1f}\n"
            f"  Std      {std_val:.1f}\n"
            f"  Range    {min_val} \u2013 {max_val}"
        )

    anim = FuncAnimation(fig, update, interval=ANIM_MS,
                         blit=False, cache_frame_data=False)
    plt.show()

# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Camera Frame Viewer \u2014 flight-optflow")
    print("Build with: ./build.sh --frame-tx 1")
    print()
    main()
