"""Are.na image -> a 4bpp frame for the Inky panel.

Fetch (optionally through a resizing proxy), decode the JPEG, then in one pass:
scale to the canvas width, dither to the panel's six inks with Floyd-Steinberg, and
rotate into the panel's landscape orientation. The frame hangs portrait, so the
canvas is 480 x 800 and portrait (px, py) maps to native (py, 479 - px).

The palette is Pimoroni's: pure RGB blended halfway with the inks they measured off
the panel (saturation 0.5 in inky_e673.set_image), which is what keeps photos from
going muddy. Index order matches theirs, remapped to the panel's RAM codes.
"""
import gc
import requests

from inky import W, H, BUF_LEN

CANVAS_W, CANVAS_H = H, W          # portrait: 480 x 800
PROXY = "https://wsrv.nl/?url=%s&w=%d&h=%d&fit=inside&output=jpg&q=85"

#        black        white           yellow         red           blue          green
PALETTE = bytes((0, 0, 0, 208, 210, 210, 232, 223, 36, 206, 36, 38, 31, 30, 175, 29, 173, 35))
CODES = bytes((0, 1, 2, 3, 5, 6))  # panel RAM codes; 4 is unused on this panel


def _quote(url):
    out = []
    for ch in url:
        if ch.isalpha() or ch.isdigit() or ch in "-_.~":
            out.append(ch)
        else:
            out.append("%%%02X" % ord(ch))
    return "".join(out)


def fetch(url, proxy=True, w=CANVAS_W, h=1600):
    """Image bytes, scaled to the canvas width by the proxy when enabled.

    The proxy also converts PNG (most Are.na blocks) to JPEG, which the decoder needs.
    """
    if proxy:
        url = PROXY % (_quote(url), w, h)
    r = requests.get(url)
    try:
        if r.status_code != 200:
            raise RuntimeError("image fetch returned %d" % r.status_code)
        return r.content
    finally:
        r.close()


def decode(data):
    """(rgb888 buffer, width, height) for JPEG bytes.

    decode() returns the frame; decode_into() only exists in newer builds than the
    firmware here (jpeg 1.0.0), so use whichever this board has.
    """
    import jpeg
    decoder = jpeg.Decoder(pixel_format="RGB888")
    info = decoder.get_img_info(data)
    w, h = int(info[0]), int(info[1])
    if hasattr(decoder, "decode_into"):
        buf = bytearray(w * h * 3)
        decoder.decode_into(data, buf)
        return buf, w, h
    return decoder.decode(data), w, h


@micropython.viper
def _dither(src: ptr8, sw: int, sh: int, dst: ptr8, dw: int, dh: int,
            px0: int, py0: int, err: ptr32, stride: int, pal: ptr8, codes: ptr8):
    """Scale, Floyd-Steinberg dither to the six inks, rotate and pack, in one pass.

    Errors are carried at 1/256 so the integer maths doesn't lose them.
    """
    for y in range(dh):
        cur = (y & 1) * stride
        nxt = ((y + 1) & 1) * stride
        i = 0
        while i < stride:                       # clear the row we accumulate into
            err[nxt + i] = 0
            i += 1
        row = ((y * sh) // dh) * sw * 3
        prow = (py0 + y) * 240          # portrait canvas: 480 px wide, 2 px per byte
        for x in range(dw):
            si = row + ((x * sw) // dw) * 3
            idx = cur + (x + 1) * 3
            r = int(src[si]) + (err[idx] >> 8)
            g = int(src[si + 1]) + (err[idx + 1] >> 8)
            b = int(src[si + 2]) + (err[idx + 2] >> 8)
            if r < 0:
                r = 0
            if r > 255:
                r = 255
            if g < 0:
                g = 0
            if g > 255:
                g = 255
            if b < 0:
                b = 0
            if b > 255:
                b = 255
            best = 0
            bestd = 1000000             # past the largest possible distance (3 * 255^2)
            k = 0
            while k < 6:
                p = k * 3
                dr = r - int(pal[p])
                dg = g - int(pal[p + 1])
                db = b - int(pal[p + 2])
                d = dr * dr + dg * dg + db * db
                if d < bestd:
                    bestd = d
                    best = k
                k += 1
            p = best * 3
            er = (r - int(pal[p])) << 8
            eg = (g - int(pal[p + 1])) << 8
            eb = (b - int(pal[p + 2])) << 8
            n = cur + (x + 2) * 3                       # 7/16 to the right
            err[n] = err[n] + ((er * 7) >> 4)
            err[n + 1] = err[n + 1] + ((eg * 7) >> 4)
            err[n + 2] = err[n + 2] + ((eb * 7) >> 4)
            n = nxt + x * 3                             # 3/16 below left
            err[n] = err[n] + ((er * 3) >> 4)
            err[n + 1] = err[n + 1] + ((eg * 3) >> 4)
            err[n + 2] = err[n + 2] + ((eb * 3) >> 4)
            n = nxt + (x + 1) * 3                       # 5/16 below
            err[n] = err[n] + ((er * 5) >> 4)
            err[n + 1] = err[n + 1] + ((eg * 5) >> 4)
            err[n + 2] = err[n + 2] + ((eb * 5) >> 4)
            n = nxt + (x + 2) * 3                       # 1/16 below right
            err[n] = err[n] + (er >> 4)
            err[n + 1] = err[n + 1] + (eg >> 4)
            err[n + 2] = err[n + 2] + (eb >> 4)
            code = int(codes[best])
            px = px0 + x
            off = prow + (px >> 1)
            v = int(dst[off])
            if px & 1:
                dst[off] = (v & 0xF0) | code
            else:
                dst[off] = (v & 0x0F) | (code << 4)


def render(url, proxy=True, dark=False, max_h=CANVAS_H):
    """Fetch an image onto a portrait canvas: full width, top-aligned.

    Returns (canvas, image height) so the caption can sit directly under it.
    """
    data = fetch(url, proxy)
    gc.collect()
    rgb, sw, sh = decode(data)
    del data
    gc.collect()
    frame = bytearray((b"\x00" if dark else b"\x11") * BUF_LEN)
    dw = CANVAS_W                                   # fill the width
    dh = sh * dw // sw                              # height follows the aspect ratio
    if dh > max_h:                                  # too tall: height drives the fit instead
        dh = max_h
        dw = sw * dh // sh
    px0 = (CANVAS_W - dw) // 2                      # centred when narrower than the canvas
    stride = (dw + 3) * 3
    err = bytearray(stride * 2 * 4)
    _dither(rgb, sw, sh, frame, dw, dh, px0, 0, err, stride, PALETTE, CODES)
    del rgb, err
    gc.collect()
    return frame, dh
