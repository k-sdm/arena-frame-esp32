# Inky Impression 7.3" Spectra 6 (EL673) test image from an ESP32-S3.
# Command sequence logged from Pimoroni's working driver on a Pi; no display library needed.
import time
from machine import Pin, SPI

SCK, MOSI, CS, DC, RST, BUSY = 12, 11, 10, 9, 8, 7
W, H = 800, 480                      # native landscape, 4 bits per pixel, 2 px per byte
BLACK, WHITE, YELLOW, RED, BLUE, GREEN = 0, 1, 2, 3, 5, 6
BARS = (BLACK, WHITE, YELLOW, RED, BLUE, GREEN)

spi = SPI(1, baudrate=4_000_000, polarity=0, phase=0,
          sck=Pin(SCK), mosi=Pin(MOSI), miso=None)
cs = Pin(CS, Pin.OUT, value=1)
dc = Pin(DC, Pin.OUT, value=0)
rst = Pin(RST, Pin.OUT, value=1)
busy = Pin(BUSY, Pin.IN)             # low = busy, high = idle


def cmd(c, data=None):
    cs(0); dc(0); spi.write(bytes([c]))
    if data:
        dc(1); spi.write(bytes(data))
    cs(1); dc(0)


def wait(timeout_ms=40000, label=""):
    t = time.ticks_ms()
    while busy.value() == 1:         # let BUSY assert first
        if time.ticks_diff(time.ticks_ms(), t) > 200:
            return 0
        time.sleep_ms(1)
    while busy.value() == 0:
        if time.ticks_diff(time.ticks_ms(), t) > timeout_ms:
            raise RuntimeError("display stayed busy: " + label)
        time.sleep_ms(5)
    return time.ticks_diff(time.ticks_ms(), t)


def init():
    rst(0); time.sleep_ms(30); rst(1); time.sleep_ms(30)
    wait(2000, "reset")
    for c, d in ((0xAA, (0x49, 0x55, 0x20, 0x08, 0x09, 0x18)), (0x01, (0x3F,)),
                 (0x00, (0x5F, 0x69)), (0x05, (0x40, 0x1F, 0x1F, 0x2C)),
                 (0x08, (0x6F, 0x1F, 0x1F, 0x22)), (0x06, (0x6F, 0x1F, 0x17, 0x17)),
                 (0x03, (0x00, 0x54, 0x00, 0x44)), (0x60, (0x02, 0x00)), (0x30, (0x08,)),
                 (0x50, (0x3F,)), (0x61, (0x03, 0x20, 0x01, 0xE0)), (0xE3, (0x2F,)),
                 (0x82, (0x01,))):
        cmd(c, d)


def test_row(y):
    """One row of the test image, packed 2 px per byte, high nibble first."""
    row = bytearray(W // 2)
    band = H // 3
    for i in range(W // 2):
        x = i * 2
        if y < band:                                  # vertical bars of all six inks
            a = b = BARS[min(x * len(BARS) // W, len(BARS) - 1)]
        elif y < 2 * band:                            # horizontal ink stripes
            a = b = BARS[min((y - band) * len(BARS) // band, len(BARS) - 1)]
        else:                                         # checkerboard over white
            a = BLACK if ((x // 40) + (y // 40)) % 2 else WHITE
            b = BLACK if (((x + 1) // 40) + (y // 40)) % 2 else WHITE
        if y < 4 or y >= H - 4 or x < 4 or x >= W - 6:  # black frame
            a = b = BLACK
        row[i] = (a << 4) | b
    return row


def show_test_image():
    print("init")
    init()
    print("sending", W * H // 2, "bytes")
    cs(0); dc(0); spi.write(bytes([0x10])); dc(1)     # DTM1, then the frame
    for y in range(H):
        spi.write(test_row(y))
    cs(1); dc(0)
    cmd(0x04)                                        # PON
    print("power on:", wait(5000, "power on"), "ms")
    cmd(0x06, (0x6F, 0x1F, 0x17, 0x49))              # BTST2 before refresh
    cmd(0x12, (0x00,))                               # DRF
    print("refreshing, ~30 s ...")
    print("refresh:", wait(40000, "refresh"), "ms")
    cmd(0x02, (0x00,))                               # POF
    wait(5000, "power off")
    cmd(0x00, (0x4F, 0x6E))                          # PSR, as the driver leaves it
    print("done")


show_test_image()
