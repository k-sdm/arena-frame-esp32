"""Inky Impression 7.3" Spectra 6 (EL673) driven over SPI from an ESP32-S3.

Command sequence taken from Pimoroni's driver, logged on a working Pi. Full refresh
only: ~29 s on the 2026 "AC waveform" panel. The frame is 4 bits per pixel, two
pixels per byte, high nibble first — the same layout as framebuf.GS4_HMSB.
"""
import time
from machine import Pin, SPI

W, H = 800, 480
BUF_LEN = W * H // 2
BLACK, WHITE, YELLOW, RED, BLUE, GREEN = 0, 1, 2, 3, 5, 6
INKS = (BLACK, WHITE, YELLOW, RED, BLUE, GREEN)
INK_RGB = ((0, 0, 0), (255, 255, 255), (255, 255, 0), (255, 0, 0), (0, 0, 255), (0, 255, 0))

_INIT = ((0xAA, (0x49, 0x55, 0x20, 0x08, 0x09, 0x18)), (0x01, (0x3F,)), (0x00, (0x5F, 0x69)),
         (0x05, (0x40, 0x1F, 0x1F, 0x2C)), (0x08, (0x6F, 0x1F, 0x1F, 0x22)),
         (0x06, (0x6F, 0x1F, 0x17, 0x17)), (0x03, (0x00, 0x54, 0x00, 0x44)),
         (0x60, (0x02, 0x00)), (0x30, (0x08,)), (0x50, (0x3F,)),
         (0x61, (0x03, 0x20, 0x01, 0xE0)), (0xE3, (0x2F,)), (0x82, (0x01,)))
CHUNK = 4096


class Inky:
    def __init__(self, sck=12, mosi=11, cs=10, dc=9, rst=8, busy=7, baudrate=4_000_000):
        self.spi = SPI(1, baudrate=baudrate, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=None)
        self.cs = Pin(cs, Pin.OUT, value=1)
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=1)
        self.busy = Pin(busy, Pin.IN)   # low = busy, high = idle

    def _cmd(self, c, data=None):
        self.cs(0); self.dc(0); self.spi.write(bytes([c]))
        if data:
            self.dc(1); self.spi.write(bytes(data))
        self.cs(1); self.dc(0)

    def _wait(self, timeout_ms=40000, label=""):
        t = time.ticks_ms()
        while self.busy.value() == 1:                 # let BUSY assert
            if time.ticks_diff(time.ticks_ms(), t) > 200:
                return 0
            time.sleep_ms(1)
        while self.busy.value() == 0:
            if time.ticks_diff(time.ticks_ms(), t) > timeout_ms:
                raise RuntimeError("display stayed busy: " + label)
            time.sleep_ms(5)
        return time.ticks_diff(time.ticks_ms(), t)

    def init(self):
        self.rst(0); time.sleep_ms(30); self.rst(1); time.sleep_ms(30)
        self._wait(2000, "reset")
        for c, d in _INIT:
            self._cmd(c, d)

    def show(self, buf):
        """Send a full 4bpp frame and refresh. Returns refresh milliseconds."""
        if len(buf) != BUF_LEN:
            raise ValueError("frame must be %d bytes" % BUF_LEN)
        self.init()
        self.cs(0); self.dc(0); self.spi.write(b"\x10"); self.dc(1)
        mv = memoryview(buf)
        for i in range(0, BUF_LEN, CHUNK):
            self.spi.write(mv[i:i + CHUNK])
        self.cs(1); self.dc(0)
        self._cmd(0x04)                                # PON
        self._wait(5000, "power on")
        self._cmd(0x06, (0x6F, 0x1F, 0x17, 0x49))      # BTST2 before refresh
        self._cmd(0x12, (0x00,))                       # DRF
        ms = self._wait(40000, "refresh")
        self._cmd(0x02, (0x00,))                       # POF
        self._wait(5000, "power off")
        self._cmd(0x00, (0x4F, 0x6E))                  # PSR, as the driver leaves it
        return ms
