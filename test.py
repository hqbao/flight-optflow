import math
import time
import matplotlib.pyplot as plt
import queue
from threading import Thread
from serial import Serial
import numpy as np
from matplotlib import animation
import serial.tools.list_ports

g_baud_rate = 19200
g_serial_port = None
ports = serial.tools.list_ports.comports()
for port, desc, hwid in sorted(ports):
  print("{}: {} [{}]".format(port, desc, hwid))
  if port.startswith('/dev/cu.usbmodem') or port.startswith('/dev/cu.usbserial') or port.startswith('/dev/cu.SLAB_USBtoUART'):
    g_serial_port = port

if g_serial_port is None:
  print('No serial port found')
  exit()

max_win_size = 64
g_line = np.linspace(start=0, stop=1, num=max_win_size)
g_val1 = np.zeros(max_win_size, int)
g_val2 = np.zeros(max_win_size, int)
g_val3 = np.zeros(max_win_size, int)
g_val4 = np.zeros(max_win_size, int)
g_val5 = np.zeros(max_win_size, int)
g_val6 = np.zeros(max_win_size, int)
g_cur_idx = 0

g_clazz = 0x00
g_clazz_id = 0x00

def run_db_reader(in_queue):
  while True:
    try:
      stream = Serial(g_serial_port, g_baud_rate, timeout=2)
      msg = b''
      while True:
        try:
          byte = stream.read(1)
          if len(byte) != 1:  continue
          # print(byte.decode("utf-8"), end='')

          msg += byte
          if byte == b'$':
            frame = msg.decode('utf-8')
            msg = b''
            nums = frame.split('\t', 9)
            # print(nums)
            if len(nums) == 10:
              in_queue.put((int(nums[0]), int(nums[1]), int(float(nums[8])*57.2957795131)))
        except Exception as e:
          stream.close()
          break
    except Exception as e:
      pass

    time.sleep(1)

def run_parser(out_queue):
  global g_val1, g_val2, g_val3, g_cur_idx
  x = 0
  y = 0
  while True:
    try:
      dx, dy, yaw = out_queue.get(timeout=0.001)
      x += dx
      y += dy
      print("{}\t{}\t{}\t{}\t{}".format(dx, dy, yaw, x, y))
      g_val1[g_cur_idx] = dx
      g_val2[g_cur_idx] = dy
      g_val3[g_cur_idx] = yaw
      g_cur_idx += 1
      if (g_cur_idx >= max_win_size): 
        g_cur_idx = 0

    except queue.Empty:
      pass

queue1 = queue.Queue()
in_thread1 = Thread(target=run_db_reader, args=(queue1,))
in_thread1.start()

in_thread2 = Thread(target=run_parser, args=(queue1,))
in_thread2.start()

fig, ax = plt.subplots(1, 1, figsize=(6, 6))

def animate(i):
  global g_line, g_val1, g_val2, g_val3

  ax.cla() # clear the previous image

  val1 = np.concatenate((g_val1[g_cur_idx:], g_val1[:g_cur_idx]))
  val2 = np.concatenate((g_val2[g_cur_idx:], g_val2[:g_cur_idx]))
  val3 = np.concatenate((g_val3[g_cur_idx:], g_val3[:g_cur_idx]))
  ax.plot(g_line, val1, color='blue')
  ax.plot(g_line, val2, color='red')
  ax.plot(g_line, val3, color='green')
  # ax.set_ylim([-2000, 2000])

anim = animation.FuncAnimation(fig, animate, frames=len(g_line) + 1, interval=1, blit=False)
plt.show()


