import serial
import serial.tools.list_ports
import struct
import threading
import queue
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
from matplotlib.animation import FuncAnimation
import time

"""
MicoAir MTF-02P Optical Flow & Range Sensor Viewer

Connects directly to the MTF-02P sensor via USB-UART and decodes
MSPv2 protocol frames in real time.

MSPv2 PROTOCOL:
  Header:  '$' 'X' '<'  (0x24 0x58 0x3C)
  Frame:   header(3) | flag(1) | function(2 LE) | payload_size(2 LE) | payload(N) | crc8(1)
  CRC:     DVB-S2 CRC8 over flag..payload (polynomial 0xD5)

  MSP2_SENSOR_RANGEFINDER (0x1F01) — 5 bytes:
    uint8_t  quality        Range quality (0-255)
    int32_t  distance_mm    Distance in mm

  MSP2_SENSOR_OPTIC_FLOW (0x1F02) — 9 bytes:
    uint8_t  quality        Flow quality (0-255)
    int32_t  motion_x       Motion delta X
    int32_t  motion_y       Motion delta Y

Layout (4 panels):
  Top:     Optical Flow Motion X/Y (time series)
  Middle:  Range Distance (time series)
  Bottom left:  Quality indicators (time series)
  Bottom right: 2D flow vector trail (X vs Y)

Usage:
  python3 optflow_micoair_view.py
"""

# --- Configuration ---
SERIAL_PORT = None
BAUD_RATE = 115200

# MSPv2 constants
MSP2_SENSOR_RANGEFINDER = 0x1F01
MSP2_SENSOR_OPTIC_FLOW  = 0x1F02
MSP_MAX_PAYLOAD = 256

HISTORY_LEN = 500    # ~50s at 10 Hz
TRAIL_LEN = 100      # 2D trail points

# --- UI Colors ---
BG_COLOR       = '#1e1e1e'
TEXT_COLOR     = '#cccccc'
DIM_TEXT       = '#888888'
GRID_COLOR     = '#3c3c3c'
BTN_GREEN      = '#2d5a2d'
BTN_GREEN_HOV  = '#3d7a3d'

COLOR_FLOW_X   = '#4fc3f7'  # Cyan
COLOR_FLOW_Y   = '#ff8a65'  # Orange
COLOR_DIST     = '#66bb6a'  # Green
COLOR_RQUAL    = '#ffa726'  # Amber
COLOR_FQUAL    = '#ab47bc'  # Purple
COLOR_TRAIL    = '#e0e0e0'  # Light gray
COLOR_TRAIL_HD = '#ff5252'  # Red head dot

# --- Auto-detect serial port ---
ports = serial.tools.list_ports.comports()
print("Scanning for serial ports...")
for port, desc, hwid in sorted(ports):
    if any(x in port for x in ['usbmodem', 'usbserial', 'SLAB_USBtoUART',
                                'ttyACM', 'ttyUSB', 'CP210']):
        SERIAL_PORT = port
        print(f"  \u2713 Auto-selected: {port} ({desc})")
        break
    else:
        print(f"  \u00b7 Skipped: {port} ({desc})")

if not SERIAL_PORT:
    print("  \u2717 No compatible serial port found. Showing empty UI.")

# --- Global State ---
data_queue = queue.Queue()
g_serial = None
g_packet_count = 0
g_error_count = 0


def crc8_dvb_s2(crc, byte):
    """DVB-S2 CRC8 used by MSPv2."""
    crc ^= byte
    for _ in range(8):
        if crc & 0x80:
            crc = ((crc << 1) ^ 0xD5) & 0xFF
        else:
            crc = (crc << 1) & 0xFF
    return crc


def mspv2_crc(data):
    """Compute CRC8 over bytes."""
    crc = 0
    for b in data:
        crc = crc8_dvb_s2(crc, b)
    return crc


# Latest combined state from both MSP messages
g_range_data = {'quality': 0, 'distance_mm': 0}
g_flow_data = {'quality': 0, 'motion_x': 0, 'motion_y': 0}


def serial_reader():
    """Background thread: reads MSPv2 frames from the MTF-02P sensor."""
    global g_serial, g_packet_count, g_error_count
    if not SERIAL_PORT:
        return
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(0.2)
        ser.reset_input_buffer()
        g_serial = ser
        print(f"  \u2713 Connected to {SERIAL_PORT} @ {BAUD_RATE}")

        # MSPv2 state machine:
        # 0=sync '$', 1=sync 'X', 2=sync '<', 3=flag, 4=func_lo, 5=func_hi,
        # 6=size_lo, 7=size_hi, 8=payload, 9=crc
        state = 0
        flag = 0
        func_id = 0
        payload_size = 0
        payload_cnt = 0
        payload_buf = bytearray()
        crc_buf = bytearray()  # bytes covered by CRC: flag..payload

        while True:
            raw = ser.read(1)
            if not raw:
                continue
            b = raw[0]

            if state == 0:
                if b == 0x24:  # '$'
                    state = 1
            elif state == 1:
                if b == 0x58:  # 'X'
                    state = 2
                else:
                    state = 0
            elif state == 2:
                if b == 0x3C:  # '<'
                    state = 3
                    crc_buf = bytearray()
                    payload_buf = bytearray()
                else:
                    state = 0
            elif state == 3:  # flag
                flag = b
                crc_buf.append(b)
                state = 4
            elif state == 4:  # function ID low byte
                func_id = b
                crc_buf.append(b)
                state = 5
            elif state == 5:  # function ID high byte
                func_id |= (b << 8)
                crc_buf.append(b)
                state = 6
            elif state == 6:  # payload size low byte
                payload_size = b
                crc_buf.append(b)
                state = 7
            elif state == 7:  # payload size high byte
                payload_size |= (b << 8)
                crc_buf.append(b)
                payload_cnt = 0
                if payload_size == 0:
                    state = 9
                elif payload_size > MSP_MAX_PAYLOAD:
                    state = 0
                    g_error_count += 1
                else:
                    state = 8
            elif state == 8:  # payload
                payload_buf.append(b)
                crc_buf.append(b)
                payload_cnt += 1
                if payload_cnt == payload_size:
                    state = 9
            elif state == 9:  # CRC
                state = 0
                expected_crc = mspv2_crc(crc_buf)
                if expected_crc != b:
                    g_error_count += 1
                    continue

                g_packet_count += 1

                if func_id == MSP2_SENSOR_RANGEFINDER and payload_size >= 5:
                    quality = payload_buf[0]
                    distance_mm = struct.unpack_from('<i', payload_buf, 1)[0]
                    g_range_data['quality'] = quality
                    g_range_data['distance_mm'] = distance_mm

                elif func_id == MSP2_SENSOR_OPTIC_FLOW and payload_size >= 9:
                    quality = payload_buf[0]
                    motion_x = struct.unpack_from('<i', payload_buf, 1)[0]
                    motion_y = struct.unpack_from('<i', payload_buf, 5)[0]
                    g_flow_data['quality'] = quality
                    g_flow_data['motion_x'] = motion_x
                    g_flow_data['motion_y'] = motion_y

                    # Push combined snapshot to queue on every flow update
                    data_queue.put({
                        'motion_x': g_flow_data['motion_x'],
                        'motion_y': g_flow_data['motion_y'],
                        'flow_quality': g_flow_data['quality'],
                        'distance_mm': g_range_data['distance_mm'],
                        'range_quality': g_range_data['quality'],
                    })
            else:
                state = 0

    except Exception as e:
        print(f"  \u2717 Serial error: {e}")
    finally:
        if g_serial and g_serial.is_open:
            g_serial.close()


def main():
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()

    plt.style.use('dark_background')
    plt.rcParams.update({
        'figure.facecolor': BG_COLOR,
        'axes.facecolor': BG_COLOR,
        'axes.edgecolor': GRID_COLOR,
        'axes.labelcolor': TEXT_COLOR,
        'text.color': TEXT_COLOR,
        'xtick.color': DIM_TEXT,
        'ytick.color': DIM_TEXT,
        'grid.color': GRID_COLOR,
    })

    fig = plt.figure(figsize=(14, 9))
    fig.patch.set_facecolor(BG_COLOR)
    fig.suptitle('MicoAir MTF-02P — Optical Flow & Range Sensor',
                 fontsize=14, color=TEXT_COLOR, fontweight='bold', y=0.99)

    # 3 rows: flow vel, distance, bottom row split into quality + 2D trail
    gs = fig.add_gridspec(3, 2, left=0.07, right=0.96, top=0.93, bottom=0.08,
                          hspace=0.45, wspace=0.25,
                          height_ratios=[1, 1, 1])

    ax_flow = fig.add_subplot(gs[0, :])      # Full width — flow velocity
    ax_dist = fig.add_subplot(gs[1, :])      # Full width — distance
    ax_qual = fig.add_subplot(gs[2, 0])      # Bottom left — quality
    ax_trail = fig.add_subplot(gs[2, 1])     # Bottom right — 2D trail

    # =========================================================================
    # Flow Velocity
    # =========================================================================
    ax_flow.set_title('Optical Flow Velocity', color=COLOR_FLOW_X,
                      fontsize=10, fontweight='bold', pad=6)
    ax_flow.set_ylabel('Motion Delta', fontsize=8)
    ax_flow.grid(True, alpha=0.2, linestyle=':')
    ax_flow.tick_params(labelsize=7)
    ax_flow.axhline(0, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    line_fx, = ax_flow.plot([], [], '-', color=COLOR_FLOW_X, linewidth=1.2,
                            label='motion_x')
    line_fy, = ax_flow.plot([], [], '-', color=COLOR_FLOW_Y, linewidth=1.2,
                            label='motion_y')
    ax_flow.legend(loc='upper left', fontsize=7, framealpha=0.3)
    val_text_flow = ax_flow.text(
        0.98, 0.92, '', transform=ax_flow.transAxes,
        fontsize=8, ha='right', va='top', fontfamily='monospace',
        color=TEXT_COLOR)

    # =========================================================================
    # Distance
    # =========================================================================
    ax_dist.set_title('Range Distance', color=COLOR_DIST,
                      fontsize=10, fontweight='bold', pad=6)
    ax_dist.set_ylabel('Distance (m)', fontsize=8)
    ax_dist.grid(True, alpha=0.2, linestyle=':')
    ax_dist.tick_params(labelsize=7)
    line_dist, = ax_dist.plot([], [], '-', color=COLOR_DIST, linewidth=1.5,
                              label='Distance')
    ax_dist.legend(loc='upper left', fontsize=7, framealpha=0.3)
    val_text_dist = ax_dist.text(
        0.98, 0.92, '', transform=ax_dist.transAxes,
        fontsize=8, ha='right', va='top', fontfamily='monospace',
        color=TEXT_COLOR)

    # =========================================================================
    # Quality / Strength
    # =========================================================================
    ax_qual.set_title('Quality (0-255)', color=TEXT_COLOR,
                      fontsize=10, fontweight='bold', pad=6)
    ax_qual.set_ylabel('Value', fontsize=8)
    ax_qual.set_xlabel('Time (s)', fontsize=8)
    ax_qual.grid(True, alpha=0.2, linestyle=':')
    ax_qual.tick_params(labelsize=7)
    line_fqual, = ax_qual.plot([], [], '-', color=COLOR_FQUAL, linewidth=1.2,
                               label='Flow Quality')
    line_str, = ax_qual.plot([], [], '-', color=COLOR_RQUAL, linewidth=1.2,
                             label='Range Quality')
    ax_qual.legend(loc='upper left', fontsize=7, framealpha=0.3)
    val_text_qual = ax_qual.text(
        0.98, 0.92, '', transform=ax_qual.transAxes,
        fontsize=8, ha='right', va='top', fontfamily='monospace',
        color=TEXT_COLOR)

    # =========================================================================
    # 2D Flow Trail
    # =========================================================================
    ax_trail.set_title('Flow Vector (X vs Y)', color=TEXT_COLOR,
                       fontsize=10, fontweight='bold', pad=6)
    ax_trail.set_xlabel('motion_x', fontsize=8)
    ax_trail.set_ylabel('motion_y', fontsize=8)
    ax_trail.grid(True, alpha=0.2, linestyle=':')
    ax_trail.tick_params(labelsize=7)
    ax_trail.set_aspect('equal', adjustable='datalim')
    ax_trail.axhline(0, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    ax_trail.axvline(0, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    line_trail, = ax_trail.plot([], [], '-', color=COLOR_TRAIL, linewidth=0.8,
                                alpha=0.4)
    dot_head, = ax_trail.plot([], [], 'o', color=COLOR_TRAIL_HD, markersize=6)

    # =========================================================================
    # History buffers
    # =========================================================================
    hist = {
        't': [], 'fx': [], 'fy': [], 'dist': [],
        'rqual': [], 'fqual': [],
        'trail_x': [], 'trail_y': [],
    }
    t0 = [None]

    # =========================================================================
    # Status bar
    # =========================================================================
    status_text = fig.text(0.50, 0.02, '', fontsize=8, ha='center',
                           color=DIM_TEXT, fontfamily='monospace')
    hz_text = fig.text(0.96, 0.02, '', fontsize=8, ha='right', color=DIM_TEXT)

    # =========================================================================
    # Clear button
    # =========================================================================
    ax_clear_btn = fig.add_axes([0.005, 0.005, 0.08, 0.04])
    btn_clear = Button(ax_clear_btn, 'Clear',
                       color=BTN_GREEN, hovercolor=BTN_GREEN_HOV)
    btn_clear.label.set_color(TEXT_COLOR)
    btn_clear.label.set_fontsize(8)

    def on_clear(event):
        for k in hist:
            hist[k].clear()
        t0[0] = None

    btn_clear.on_clicked(on_clear)

    # =========================================================================
    # Animation loop
    # =========================================================================
    frame_count = [0]
    last_hz_time = [time.time()]
    last_hz_packets = [0]

    def update(frame_num):
        updated = []
        latest = None

        while not data_queue.empty():
            try:
                latest = data_queue.get_nowait()
            except queue.Empty:
                break

        if latest is None:
            return updated

        now = time.time()
        if t0[0] is None:
            t0[0] = now
        t = now - t0[0]

        fx = latest['motion_x']
        fy = latest['motion_y']
        dist_m = latest['distance_mm'] / 1000.0  # mm -> m
        rqual = latest['range_quality']
        fqual = latest['flow_quality']

        hist['t'].append(t)
        hist['fx'].append(fx)
        hist['fy'].append(fy)
        hist['dist'].append(dist_m)
        hist['rqual'].append(rqual)
        hist['fqual'].append(fqual)
        hist['trail_x'].append(fx)
        hist['trail_y'].append(fy)

        if len(hist['t']) > HISTORY_LEN:
            for k in ('t', 'fx', 'fy', 'dist', 'rqual', 'fqual'):
                hist[k] = hist[k][-HISTORY_LEN:]
        if len(hist['trail_x']) > TRAIL_LEN:
            hist['trail_x'] = hist['trail_x'][-TRAIL_LEN:]
            hist['trail_y'] = hist['trail_y'][-TRAIL_LEN:]

        ta = np.array(hist['t'])

        # =================================================================
        # Flow Velocity
        # =================================================================
        line_fx.set_data(ta, hist['fx'])
        line_fy.set_data(ta, hist['fy'])
        val_text_flow.set_text(
            f'x:{fx:+6d}  y:{fy:+6d}  q:{fqual}')
        if len(ta) > 1:
            ax_flow.set_xlim(ta[0], ta[-1] + 0.1)
            d = np.array(hist['fx'] + hist['fy'])
            dmin, dmax = d.min(), d.max()
            m = max(5, (dmax - dmin) * 0.15)
            ax_flow.set_ylim(dmin - m, dmax + m)
        updated.extend([line_fx, line_fy])

        # =================================================================
        # Distance
        # =================================================================
        line_dist.set_data(ta, hist['dist'])
        val_text_dist.set_text(
            f'{dist_m:.3f} m  ({latest["distance_mm"]} mm)  q:{rqual}')
        if len(ta) > 1:
            ax_dist.set_xlim(ta[0], ta[-1] + 0.1)
            d = np.array(hist['dist'])
            dmin, dmax = d.min(), d.max()
            m = max(0.05, (dmax - dmin) * 0.15)
            ax_dist.set_ylim(max(0, dmin - m), dmax + m)
        updated.extend([line_dist])

        # =================================================================
        # Quality / Strength
        # =================================================================
        line_fqual.set_data(ta, hist['fqual'])
        line_str.set_data(ta, hist['rqual'])
        val_text_qual.set_text(f'flow_q:{fqual}  range_q:{rqual}')
        if len(ta) > 1:
            ax_qual.set_xlim(ta[0], ta[-1] + 0.1)
            d = np.array(hist['fqual'] + hist['rqual'])
            dmin, dmax = d.min(), d.max()
            m = max(5, (dmax - dmin) * 0.15)
            ax_qual.set_ylim(max(0, dmin - m), dmax + m)
        updated.extend([line_fqual, line_str])

        # =================================================================
        # 2D Flow Trail
        # =================================================================
        line_trail.set_data(hist['trail_x'], hist['trail_y'])
        dot_head.set_data([fx], [fy])
        if len(hist['trail_x']) > 1:
            tx = np.array(hist['trail_x'])
            ty = np.array(hist['trail_y'])
            all_vals = np.concatenate([tx, ty])
            vmin, vmax = all_vals.min(), all_vals.max()
            pad = max(5, (vmax - vmin) * 0.2)
            lim = max(abs(vmin - pad), abs(vmax + pad))
            ax_trail.set_xlim(-lim, lim)
            ax_trail.set_ylim(-lim, lim)
        updated.extend([line_trail, dot_head])

        # =================================================================
        # Status bar
        # =================================================================
        status_text.set_text(
            f'pkts:{g_packet_count}  errs:{g_error_count}')
        updated.append(status_text)

        # Data rate
        frame_count[0] += 1
        elapsed = now - last_hz_time[0]
        if elapsed >= 1.0:
            pkt_diff = g_packet_count - last_hz_packets[0]
            hz = pkt_diff / elapsed
            hz_text.set_text(f'{hz:.0f} Hz')
            frame_count[0] = 0
            last_hz_time[0] = now
            last_hz_packets[0] = g_packet_count
            updated.append(hz_text)

        return updated

    ani = FuncAnimation(fig, update, interval=40, blit=False,
                        cache_frame_data=False)
    plt.show()


if __name__ == '__main__':
    main()
