"""Inky Impression panels driven over SPI from an ESP32-S3.

Three panels, selected by the `panel` setting:

  "7.3"   800 x 480   Spectra 6 (EL673)       tested on hardware
  "4.0"   600 x 400   Spectra 6 (E640)        same controller family, untested
  "13.3"  1600 x 1200 Spectra 6 (EL133UF1)    different controller, UNTESTED

Command sequences follow Pimoroni's drivers. The frame is 4 bits per pixel, two
pixels per byte, high nibble first — the same layout as framebuf.GS4_HMSB.

The 13.3" needs TWO chip-select lines (each controller drives half the panel) and
runs SPI at 10 MHz. The current carrier board has one CS, so it needs a second wire
before that panel can work.
"""
import time
from machine import Pin, SPI

BLACK, WHITE, YELLOW, RED, BLUE, GREEN = 0, 1, 2, 3, 5, 6
INKS = (BLACK, WHITE, YELLOW, RED, BLUE, GREEN)

# Pimoroni's saturation-0.5 blend of pure RGB with the inks measured off the panel.
PALETTE = bytes((0, 0, 0, 208, 210, 210, 232, 223, 36, 206, 36, 38, 31, 30, 175, 29, 173, 35))
CODES = bytes((0, 1, 2, 3, 5, 6))      # panel RAM codes; 4 is unused

#            width  height  TRES bytes                      BTST2 before refresh
PANELS = {
    "7.3": (800, 480, (0x03, 0x20, 0x01, 0xE0), (0x6F, 0x1F, 0x17, 0x49)),
    "4.0": (600, 400, (0x01, 0x90, 0x02, 0x58), (0x6F, 0x1F, 0x17, 0x47)),
    "13.3": (1600, 1200, None, None),   # handled by Inky13, which shares no commands
}
DEFAULT_PANEL = "7.3"
CHUNK = 4096


def panel_size(panel=DEFAULT_PANEL):
    spec = PANELS.get(panel) or PANELS[DEFAULT_PANEL]
    return spec[0], spec[1]


def buf_len(panel=DEFAULT_PANEL):
    w, h = panel_size(panel)
    return w * h // 2


class Inky:
    """7.3" and 4.0" Spectra 6 panels (EL673 / E640 command set)."""

    def __init__(self, panel=DEFAULT_PANEL, sck=12, mosi=11, cs=10, dc=9, rst=8, busy=7,
                 baudrate=4_000_000):
        if panel not in ("7.3", "4.0"):
            raise ValueError("Inky drives 7.3 and 4.0; use Inky13 for 13.3")
        self.panel = panel
        self.W, self.H, self._tres, self._btst2 = PANELS[panel]
        self.buf_len = self.W * self.H // 2
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
        for c, d in ((0xAA, (0x49, 0x55, 0x20, 0x08, 0x09, 0x18)), (0x01, (0x3F,)),
                     (0x00, (0x5F, 0x69)), (0x05, (0x40, 0x1F, 0x1F, 0x2C)),
                     (0x08, (0x6F, 0x1F, 0x1F, 0x22)), (0x06, (0x6F, 0x1F, 0x17, 0x17)),
                     (0x03, (0x00, 0x54, 0x00, 0x44)), (0x60, (0x02, 0x00)), (0x30, (0x08,)),
                     (0x50, (0x3F,)), (0x61, self._tres), (0xE3, (0x2F,)), (0x82, (0x01,))):
            self._cmd(c, d)

    def show(self, buf):
        """Send a full 4bpp frame and refresh. Returns refresh milliseconds."""
        if len(buf) != self.buf_len:
            raise ValueError("frame must be %d bytes for the %s panel" % (self.buf_len, self.panel))
        self.init()
        self.cs(0); self.dc(0); self.spi.write(b"\x10"); self.dc(1)
        mv = memoryview(buf)
        for i in range(0, self.buf_len, CHUNK):
            self.spi.write(mv[i:i + CHUNK])
        self.cs(1); self.dc(0)
        self._cmd(0x04)                                # PON
        self._wait(5000, "power on")
        self._cmd(0x06, self._btst2)                   # BTST2 before refresh
        self._cmd(0x12, (0x00,))                       # DRF
        ms = self._wait(40000, "refresh")
        self._cmd(0x02, (0x00,))                       # POF
        self._wait(5000, "power off")
        self._cmd(0x00, (0x4F, 0x6E))                  # PSR, as the driver leaves it
        return ms


class Inky13:
    """13.3" Spectra 6 (EL133UF1). UNTESTED — no panel to try it on.

    Two controllers split the panel down the middle: each takes 600 of the 1200
    columns, 1600 rows. Wire a second chip-select; the carrier board has only one.
    """

    def __init__(self, cs0=10, cs1=13, sck=12, mosi=11, dc=9, rst=8, busy=7,
                 baudrate=10_000_000, panel="13.3"):
        self.panel = panel
        self.W, self.H = 1600, 1200
        self.buf_len = self.W * self.H // 2
        self.spi = SPI(1, baudrate=baudrate, polarity=0, phase=0,
                       sck=Pin(sck), mosi=Pin(mosi), miso=None)
        self.cs0 = Pin(cs0, Pin.OUT, value=1)
        self.cs1 = Pin(cs1, Pin.OUT, value=1)
        self.dc = Pin(dc, Pin.OUT, value=0)
        self.rst = Pin(rst, Pin.OUT, value=1)
        self.busy = Pin(busy, Pin.IN)

    def _cmd(self, c, data=None, target=3):
        """target: 1 = first controller, 2 = second, 3 = both."""
        pins = [p for p, bit in ((self.cs0, 1), (self.cs1, 2)) if target & bit]
        for p in pins:
            p(0)
        self.dc(0); self.spi.write(bytes([c]))
        if data:
            self.dc(1); self.spi.write(bytes(data))
        for p in pins:
            p(1)
        self.dc(0)

    _wait = Inky._wait

    def init(self):
        self.rst(0); time.sleep_ms(30); self.rst(1); time.sleep_ms(300)
        self._wait(5000, "reset")
        self._cmd(0x74, (0x00, 0x0C, 0x0C, 0xD9, 0xDD, 0xDD, 0x15, 0x15, 0x55), 1)
        self._cmd(0xF0, (0x49, 0x55, 0x13, 0x5D, 0x05, 0x10))
        self._cmd(0x00, (0xDF, 0x6B))
        self._cmd(0xA5, (0x44, 0x54, 0x00), 1)
        self._cmd(0x30, (0x08,))
        self._cmd(0x50, (0x37,))
        self._cmd(0x60, (0x03, 0x03))
        self._cmd(0x03, (0x00, 0xC0, 0x03, 0xA8), 1)
        self._cmd(0x03, (0x00, 0xC0, 0x03, 0x9A), 2)
        self._cmd(0x86, (0x10,))
        self._cmd(0xE3, (0x22,))
        self._cmd(0xE0, (0x01,))
        self._cmd(0x61, (0x04, 0xB0, 0x03, 0x20))
        self._cmd(0xA4, (0x03, 0x00, 0x01, 0x03, 0x00, 0x03, 0x00, 0x00, 0x00), 1)
        self._cmd(0x01, (0x0F, 0x00, 0x28, 0x2C, 0x28, 0x38), 1)
        self._cmd(0xB6, (0x07,), 1)
        self._cmd(0x06, (0xE0, 0x20), 1)
        self._cmd(0xB7, (0x01,), 1)
        self._cmd(0x05, (0xE0, 0x20), 1)
        self._cmd(0xB0, (0x01,), 1)
        self._cmd(0xB1, (0x02,), 1)

    def _half(self, buf, target, right):
        """Send one controller its half: 600 of the 1200 columns, 1600 rows."""
        pin = self.cs1 if right else self.cs0
        row_bytes = self.H // 2              # 600 bytes per 1200-px row
        half = row_bytes // 2                # 300 bytes per controller
        pin(0); self.dc(0); self.spi.write(b"\x10"); self.dc(1)
        mv = memoryview(buf)
        for row in range(self.W):            # the panel is fed rotated: 1600 rows
            start = row * row_bytes + (half if right else 0)
            self.spi.write(mv[start:start + half])
        pin(1); self.dc(0)

    def show(self, buf):
        """buf is the portrait canvas (1200 x 1600), which is the order these controllers want."""
        if len(buf) != self.buf_len:
            raise ValueError("frame must be %d bytes" % self.buf_len)
        self.init()
        self._half(buf, 1, False)
        self._half(buf, 2, True)
        self._cmd(0x04)                      # PON
        self._wait(10000, "power on")
        self._cmd(0x12, (0x00,))             # DRF
        ms = self._wait(90000, "refresh")    # ~65 s on this panel
        self._cmd(0x02, (0x00,))             # POF
        self._wait(5000, "power off")
        return ms


def get(panel=DEFAULT_PANEL, **pins):
    """Driver for the configured panel."""
    if panel == "13.3":
        return Inky13(**pins)
    return Inky(panel, **pins)
