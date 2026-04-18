#!/usr/bin/env python3
"""
Optical Flow Visualizer — flight-optflow ESP32-S3
Reads ESP_LOGI debug output via USB serial monitor.

Requires: --debug-log 1 at build time:
  cd flight-optflow/base/boards/s3v1 && ./build.sh --debug-log 1
"""

import serial
import serial.tools.list_ports
import re
import threading
import queue
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
import time
from collections import deque

# ── Theme (matches flight-controller tools) ──────────────────────────────────
BG_COLOR      = '#1e1e1e'
PANEL_COLOR   = '#252526'
TEXT_COLOR    = '#cccccc'
DIM_TEXT      = '#888888'
GRID_COLOR    = '#3c3c3c'
BTN_COLOR     = '#333333'
BTN_HOVER     = '#444444'

COLOR_DX      = '#4fc3f7'   # Cyan
COLOR_DY      = '#81c784'   # Green
COLOR_QUALITY = '#ffa726'   # Orange
COLOR_RANGE   = '#ef5350'   # Red
COLOR_ARROW   = '#5599ff'   # Blue

# ── Configuration ─────────────────────────────────────────────────────────────
BAUD_RATE    = 115200
HISTORY_LEN  = 300          # ~30s at 10 Hz / ~12s at 25 Hz
ANIM_MS      = 40           # 25 Hz refresh

# ── Serial auto-detect ───────────────────────────────────────────────────────
def find_serial_port():
    for port, desc, hwid in sorted(serial.tools.list_ports.comports()):
        if any(k in port for k in ('usbmodem', 'usbserial', 'SLAB')):
            return port
    return '/dev/cu.usbmodem1101'

# ── Global state ──────────────────────────────────────────────────────────────
g_data_queue = queue.Queue(maxsize=4)

g_hist = {
    'time': deque(maxlen=HISTORY_LEN),
    'dx':   deque(maxlen=HISTORY_LEN),
    'dy':   deque(maxlen=HISTORY_LEN),
    'qual': deque(maxlen=HISTORY_LEN),
    'dist': deque(maxlen=HISTORY_LEN),
    'fps':  deque(maxlen=HISTORY_LEN),
}

g_t0 = None
g_fps_ts = 0.0
g_fps_count = 0
g_display_fps = 0.0

# ── Serial reader thread ─────────────────────────────────────────────────────
def serial_reader(port):
    """Parse ESP_LOGI lines from flight-optflow telemetry.c"""
    global g_t0

    # OF: dx=0.0012 	dy=-0.0034 rad 	qual=56 	RF: dist=1234.5 	Freq: 24.8 Hz 	dt: 40000
    pattern = re.compile(
        r'OF:\s+dx=([-\d.]+)\s+dy=([-\d.]+)\s+rad\s+'
        r'qual=(\d+)\s+RF:\s+dist=([\d.]+)\s+'
        r'Freq:\s+([\d.]+)\s+Hz'
    )

    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                print(f"[serial] connected to {port}")
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode('utf-8', errors='ignore').strip()
                    m = pattern.search(line)
                    if not m:
                        continue

                    now = time.time()
                    if g_t0 is None:
                        g_t0 = now

                    sample = {
                        't':    now - g_t0,
                        'dx':   float(m.group(1)),
                        'dy':   float(m.group(2)),
                        'qual': int(m.group(3)),
                        'dist': float(m.group(4)),
                        'fps':  float(m.group(5)),
                    }

                    if g_data_queue.full():
                        try:
                            g_data_queue.get_nowait()
                        except queue.Empty:
                            pass
                    g_data_queue.put(sample)

        except serial.SerialException as e:
            print(f"[serial] {e} — retrying in 2s")
            time.sleep(2)
        except Exception as e:
            print(f"[serial] unexpected: {e}")
            time.sleep(1)

# ── Helpers ───────────────────────────────────────────────────────────────────
def style_axis(ax, title, ylabel, title_color=TEXT_COLOR):
    ax.set_facecolor(PANEL_COLOR)
    ax.set_title(title, fontsize=10, fontweight='bold', color=title_color,
                 loc='left', pad=6)
    ax.set_ylabel(ylabel, fontsize=8, color=DIM_TEXT)
    ax.tick_params(colors=DIM_TEXT, labelsize=7)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.4, linestyle=':')
    ax.axhline(0, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)

def auto_ylim(ax, arrays, margin_frac=0.25, min_range=0.005):
    vals = np.concatenate([np.array(a) for a in arrays if len(a)])
    if len(vals) == 0:
        return
    lo, hi = float(vals.min()), float(vals.max())
    span = hi - lo
    if span < min_range:
        mid = (lo + hi) / 2
        lo, hi = mid - min_range / 2, mid + min_range / 2
        span = min_range
    m = span * margin_frac
    ax.set_ylim(lo - m, hi + m)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global g_fps_ts, g_fps_count, g_display_fps, g_t0

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

    fig = plt.figure(figsize=(15, 9))
    fig.canvas.manager.set_window_title('Optical Flow Visualizer — flight-optflow')

    # 4 time-series rows + vector panel + stats panel
    ax_dx   = fig.add_axes([0.07, 0.76, 0.58, 0.18])
    ax_dy   = fig.add_axes([0.07, 0.54, 0.58, 0.18])
    ax_qual = fig.add_axes([0.07, 0.32, 0.58, 0.18])
    ax_dist = fig.add_axes([0.07, 0.10, 0.58, 0.18])

    ax_vec  = fig.add_axes([0.72, 0.40, 0.26, 0.54])
    ax_info = fig.add_axes([0.72, 0.10, 0.26, 0.26])

    style_axis(ax_dx,   'Optical Flow DX', 'rad',  COLOR_DX)
    style_axis(ax_dy,   'Optical Flow DY', 'rad',  COLOR_DY)
    style_axis(ax_qual, 'Quality',         '',      COLOR_QUALITY)
    style_axis(ax_dist, 'Range Finder',    'mm',    COLOR_RANGE)
    ax_dist.set_xlabel('Time (s)', fontsize=8, color=DIM_TEXT)

    # Vector display
    ax_vec.set_facecolor(PANEL_COLOR)
    ax_vec.set_title('Flow Vector', fontsize=10, fontweight='bold',
                     color=COLOR_ARROW, loc='left', pad=6)
    ax_vec.set_aspect('equal')
    ax_vec.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.3, linestyle=':')
    ax_vec.axhline(0, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    ax_vec.axvline(0, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    ax_vec.set_xlabel('DY (rad)', fontsize=8, color=DIM_TEXT)
    ax_vec.set_ylabel('DX (rad)', fontsize=8, color=DIM_TEXT)
    ax_vec.tick_params(colors=DIM_TEXT, labelsize=7)
    for spine in ax_vec.spines.values():
        spine.set_color(GRID_COLOR)

    # Info panel
    ax_info.set_facecolor(PANEL_COLOR)
    ax_info.axis('off')
    for spine in ax_info.spines.values():
        spine.set_color(GRID_COLOR)

    # ── Plot lines ────────────────────────────────────────────────────────────
    line_dx,   = ax_dx.plot([], [], color=COLOR_DX, linewidth=1.2)
    line_dy,   = ax_dy.plot([], [], color=COLOR_DY, linewidth=1.2)
    line_qual, = ax_qual.plot([], [], color=COLOR_QUALITY, linewidth=1.2)
    line_dist, = ax_dist.plot([], [], color=COLOR_RANGE, linewidth=1.2)

    # Value labels (top-right of each axis)
    _tv = dict(fontfamily='monospace', fontsize=9, fontweight='bold', ha='right', va='top')
    txt_dx   = ax_dx.text(0.98, 0.92, '', color=COLOR_DX, transform=ax_dx.transAxes, **_tv)
    txt_dy   = ax_dy.text(0.98, 0.92, '', color=COLOR_DY, transform=ax_dy.transAxes, **_tv)
    txt_qual = ax_qual.text(0.98, 0.92, '', color=COLOR_QUALITY, transform=ax_qual.transAxes, **_tv)
    txt_dist = ax_dist.text(0.98, 0.92, '', color=COLOR_RANGE, transform=ax_dist.transAxes, **_tv)

    # Vector display elements
    trail_scatter = ax_vec.scatter([], [], c=[], cmap='coolwarm', s=12,
                                   alpha=0.4, vmin=0, vmax=100, zorder=1)
    arrow_line, = ax_vec.plot([], [], color=COLOR_ARROW, linewidth=2.5,
                              solid_capstyle='round', zorder=3)
    arrow_head, = ax_vec.plot([], [], 'o', color=COLOR_ARROW, markersize=7, zorder=4)

    # Info text
    info_text = ax_info.text(0.08, 0.92, '', fontfamily='monospace', fontsize=9,
                             color=TEXT_COLOR, va='top', transform=ax_info.transAxes,
                             linespacing=1.6)

    # ── Button ────────────────────────────────────────────────────────────────
    ax_btn_clear = fig.add_axes([0.005, 0.005, 0.08, 0.04])
    btn_clear = Button(ax_btn_clear, 'Clear', color=BTN_COLOR, hovercolor=BTN_HOVER)
    btn_clear.label.set_fontsize(8)
    btn_clear.label.set_color(TEXT_COLOR)

    def on_clear(event):
        global g_t0
        for v in g_hist.values():
            v.clear()
        g_t0 = None

    btn_clear.on_clicked(on_clear)

    # ── Animation ─────────────────────────────────────────────────────────────
    def update(frame):
        global g_fps_ts, g_fps_count, g_display_fps

        # Drain queue — append every sample to history
        latest = None
        while not g_data_queue.empty():
            try:
                latest = g_data_queue.get_nowait()
            except queue.Empty:
                break
            g_hist['time'].append(latest['t'])
            g_hist['dx'].append(latest['dx'])
            g_hist['dy'].append(latest['dy'])
            g_hist['qual'].append(latest['qual'])
            g_hist['dist'].append(latest['dist'])
            g_hist['fps'].append(latest['fps'])

        if latest is None:
            return

        n = len(g_hist['time'])
        if n < 2:
            return

        ta = np.array(g_hist['time'])

        # ── Time-series ───────────────────────────────────────────────────
        line_dx.set_data(ta, np.array(g_hist['dx']))
        line_dy.set_data(ta, np.array(g_hist['dy']))
        line_qual.set_data(ta, np.array(g_hist['qual']))
        line_dist.set_data(ta, np.array(g_hist['dist']))

        x0, x1 = ta[0], ta[-1] + 0.1
        for a in (ax_dx, ax_dy, ax_qual, ax_dist):
            a.set_xlim(x0, x1)

        auto_ylim(ax_dx,   [g_hist['dx']],   min_range=0.005)
        auto_ylim(ax_dy,   [g_hist['dy']],   min_range=0.005)
        auto_ylim(ax_qual, [g_hist['qual']], min_range=10)
        auto_ylim(ax_dist, [g_hist['dist']], min_range=50)

        txt_dx.set_text(f"{latest['dx']:+.4f} rad")
        txt_dy.set_text(f"{latest['dy']:+.4f} rad")
        txt_qual.set_text(f"{latest['qual']}")
        txt_dist.set_text(f"{latest['dist']:.0f} mm")

        # ── Vector display ────────────────────────────────────────────────
        dx_arr = np.array(g_hist['dx'])
        dy_arr = np.array(g_hist['dy'])
        q_arr  = np.array(g_hist['qual'])

        trail_scatter.set_offsets(np.c_[dy_arr, dx_arr])
        trail_scatter.set_array(q_arr)

        cx, cy = latest['dy'], latest['dx']
        arrow_line.set_data([0, cx], [0, cy])
        arrow_head.set_data([cx], [cy])

        all_v = np.concatenate([np.abs(dx_arr), np.abs(dy_arr)])
        vmax = max(float(all_v.max()) * 1.3, 0.005) if len(all_v) else 0.01
        ax_vec.set_xlim(-vmax, vmax)
        ax_vec.set_ylim(-vmax, vmax)

        # ── Info panel ────────────────────────────────────────────────────
        now = time.time()
        g_fps_count += 1
        if now - g_fps_ts >= 1.0:
            g_display_fps = g_fps_count / (now - g_fps_ts)
            g_fps_count = 0
            g_fps_ts = now

        mag = np.sqrt(cx**2 + cy**2)
        deg = np.degrees(np.arctan2(cy, cx)) if mag > 1e-6 else 0

        w = min(10, n)
        ma_dx = np.mean(list(g_hist['dx'])[-w:])
        ma_dy = np.mean(list(g_hist['dy'])[-w:])
        ma_mag = np.sqrt(ma_dx**2 + ma_dy**2)

        info_text.set_text(
            f"  CURRENT\n"
            f"  DX   {cx:+.4f} rad\n"
            f"  DY   {cy:+.4f} rad\n"
            f"  Mag  {mag:.4f} rad\n"
            f"  Dir  {deg:+.1f}\u00b0\n"
            f"\n"
            f"  AVERAGE (10)\n"
            f"  DX   {ma_dx:+.4f} rad\n"
            f"  DY   {ma_dy:+.4f} rad\n"
            f"  Mag  {ma_mag:.4f} rad\n"
            f"\n"
            f"  Sensor  {latest['fps']:.1f} Hz\n"
            f"  Range   {latest['dist']:.0f} mm\n"
            f"  Quality {latest['qual']}\n"
            f"  UI FPS  {g_display_fps:.0f}"
        )

    anim = FuncAnimation(fig, update, interval=ANIM_MS,
                         blit=False, cache_frame_data=False)
    plt.show()

# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Optical Flow Visualizer \u2014 flight-optflow")
    print("Build with: ./build.sh --debug-log 1")
    print()
    main()
