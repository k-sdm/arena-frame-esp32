#!/usr/bin/env python3
"""Render a TTF into a compact 1bpp bitmap font the ESP32 can draw.

Format: b"FNT1", height, first char, count, then per glyph: width byte followed by
height rows of ceil(width/8) bytes, MSB first.
"""
import pathlib
import sys
from PIL import Image, ImageDraw, ImageFont

FIRST, LAST = 32, 126


def build(ttf_path, size, out_path, variation=None):
    font = ImageFont.truetype(ttf_path, size)
    if variation:
        try:
            font.set_variation_by_name(variation)
        except Exception as e:
            print("  (no variation %r: %s)" % (variation, e))
    ascent, descent = font.getmetrics()
    height = ascent + descent
    glyphs = []
    for code in range(FIRST, LAST + 1):
        ch = chr(code)
        width = max(1, round(font.getlength(ch)))
        img = Image.new("1", (width, height), 0)
        ImageDraw.Draw(img).text((0, ascent), ch, font=font, fill=1, anchor="ls")
        row_bytes = (width + 7) // 8
        data = bytearray()
        px = img.load()
        for y in range(height):
            bits = bytearray(row_bytes)
            for x in range(width):
                if px[x, y]:
                    bits[x >> 3] |= 0x80 >> (x & 7)
            data += bits
        glyphs.append((width, bytes(data)))
    out = bytearray(b"FNT1")
    out += bytes([height, FIRST, len(glyphs)])
    for width, data in glyphs:
        out += bytes([width]) + data
    pathlib.Path(out_path).write_bytes(out)
    print("  %s: %d px tall, %d glyphs, %d bytes" % (pathlib.Path(out_path).name, height, len(glyphs), len(out)))


if __name__ == "__main__":
    src = sys.argv[1]
    for size, name, variation in ((28, "areal_28.bin", "Regular"), (14, "areal_14.bin", "Regular")):
        build(src, size, pathlib.Path(sys.argv[2]) / name, variation)
