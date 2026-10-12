"""Bitmap fonts built from ABC Areal by esp32/build_font.py.

File layout: b"FNT1", height, first char, glyph count, then per glyph a width byte
followed by `height` rows of ceil(width/8) bytes, MSB first.
"""

SPACING = 1


class Font:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        if self.data[:4] != b"FNT1":
            raise ValueError("not a font file: %s" % path)
        self.height = self.data[4]
        self.first = self.data[5]
        self.count = self.data[6]
        self.index = []
        pos = 7
        for _ in range(self.count):
            width = self.data[pos]
            self.index.append((pos + 1, width))
            pos += 1 + ((width + 7) // 8) * self.height

    def _glyph(self, ch):
        i = ord(ch) - self.first
        if i < 0 or i >= self.count:
            i = ord("?") - self.first
        return self.index[i]

    def width(self, text):
        return sum(self._glyph(c)[1] + SPACING for c in text)

    def draw(self, fb, text, x, y, ink, dim=False):
        """Draw text with its top-left at (x, y). Returns the width drawn.

        dim draws every other pixel in a checkerboard, which reads as light grey —
        the panel has six inks and no greys.
        """
        data = self.data
        start = x
        for ch in text:
            base, w = self._glyph(ch)
            row_bytes = (w + 7) // 8
            for row in range(self.height):
                off = base + row * row_bytes
                py = y + row
                for cx in range(w):
                    if data[off + (cx >> 3)] & (0x80 >> (cx & 7)):
                        px = x + cx
                        if dim and ((px ^ py) & 1):
                            continue
                        fb.pixel(px, py, ink)
            x += w + SPACING
        return x - start


_CACHE = {}


def get(name):
    """Fonts: 'b26' (titles), 'r20' (body), 'r14' (channel line)."""
    if name not in _CACHE:
        _CACHE[name] = Font("fonts/areal_%s.bin" % name)
    return _CACHE[name]
