"""Drawing the page on a portrait canvas, then rotating it for the panel.

The frame hangs portrait, so everything is composed on a 480 x 800 canvas, exactly
like the Pi version, and rotated 90 degrees at the end: portrait (px, py) becomes
native (py, 479 - px). framebuf.GS4_HMSB packs two pixels per byte, high nibble
first — the panel's own layout — so no pixel conversion is needed, only the rotation.
"""
import framebuf

import font
from inky import W, H, BUF_LEN, BLACK, WHITE

CANVAS_W, CANVAS_H = H, W          # 480 x 800
ROW = CANVAS_W // 2                # bytes per portrait row
PAD = 24
LINE_GAP = 6
TITLE_GAP = 16
EDGE = 10          # channel line: padding from the left and bottom
CHANNEL_LINES = 2


def new_canvas(dark=False):
    buf = bytearray(BUF_LEN)
    fb = framebuf.FrameBuffer(buf, CANVAS_W, CANVAS_H, framebuf.GS4_HMSB)
    fb.fill(BLACK if dark else WHITE)
    return buf, fb


def colours(dark):
    """(ink, background) for the theme."""
    return (WHITE, BLACK) if dark else (BLACK, WHITE)


def wrap(f, text, max_w):
    """Word wrap to a pixel width."""
    lines, line = [], ""
    for word in str(text).split():
        trial = (line + " " + word).strip()
        if line and f.width(trial) > max_w:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def draw_lines(fb, f, lines, x, y, ink, max_lines=None):
    """Draw wrapped lines; returns the y below the last one."""
    for line in lines[:max_lines] if max_lines else lines:
        f.draw(fb, line, x, y, ink)
        y += f.height + LINE_GAP
    return y


def fit_text(f, text, max_w):
    """Trim to a pixel width, ending with an ellipsis when something was cut."""
    text = " ".join(str(text).split())
    if f.width(text) <= max_w:
        return text
    while text and f.width(text + "...") > max_w:
        text = text[:-1]
    return text.rstrip() + "..."


def wrap_channel(f, text, max_w, max_lines=CHANNEL_LINES):
    """Wrap Are.na/owner/channel over a couple of lines, breaking after slashes."""
    tokens = []
    for part in str(text).split(" "):
        chunk = ""
        for ch in part:
            chunk += ch
            if ch == "/":
                tokens.append(chunk)
                chunk = ""
        if chunk:
            tokens.append(chunk)
    lines, line = [], ""
    for token in tokens:
        sep = "" if (not line or line.endswith("/")) else " "
        trial = line + sep + token
        if line and f.width(trial) > max_w:
            lines.append(line)
            line = token
        else:
            line = trial
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit_text(f, lines[-1] + "...", max_w)
    return lines


def overlay_height(title, channel, show_title=True, show_info=True):
    """Pixels the overlay needs at the foot, so an image can be scaled to what's left."""
    height = 0
    if show_info and channel:
        f = font.get("b26")
        lines = wrap_channel(f, channel, CANVAS_W - 2 * EDGE)
        height += len(lines) * f.height + (len(lines) - 1) * LINE_GAP + EDGE * 2
    if show_title and title:
        height += font.get("r14").height + TITLE_GAP
    return height


def overlay(fb, title, channel, dark=False, show_title=True, show_info=True, image_bottom=0):
    """Block title centred under the image in grey; channel line bold along the bottom."""
    ink, bg = colours(dark)
    channel_font = font.get("b26")
    top = CANVAS_H
    if show_info and channel:
        lines = wrap_channel(channel_font, channel, CANVAS_W - 2 * EDGE)
        block = len(lines) * channel_font.height + (len(lines) - 1) * LINE_GAP
        top = CANVAS_H - EDGE - block
        fb.fill_rect(0, top - EDGE, CANVAS_W, CANVAS_H - top + EDGE, bg)
        y = top
        for line in lines:
            channel_font.draw(fb, line, EDGE, y, ink)
            y += channel_font.height + LINE_GAP
    if show_title and title:
        title_font = font.get("r14")
        y = image_bottom + TITLE_GAP
        limit = top - TITLE_GAP - title_font.height
        if y > limit:                       # image reaches the foot: sit just above the channel
            y = limit
            fb.fill_rect(0, y - TITLE_GAP // 2, CANVAS_W, title_font.height + TITLE_GAP, bg)
        text = fit_text(title_font, title, CANVAS_W - 2 * PAD)
        title_font.draw(fb, text, (CANVAS_W - title_font.width(text)) // 2, y, ink, dim=True)


def text_page(title, body, channel="", dark=False, show_title=True, show_info=True):
    """A text block: body text up top, then the same overlay as images get."""
    ink, _bg = colours(dark)
    buf, fb = new_canvas(dark)
    body_font = font.get("r20")
    max_w = CANVAS_W - 2 * PAD
    foot = overlay_height(title, channel, show_title, show_info) + PAD
    max_lines = max(1, (CANVAS_H - PAD - foot) // (body_font.height + LINE_GAP))
    lines = wrap(body_font, body, max_w)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fit_text(body_font, lines[-1] + " ...", max_w)
    y = draw_lines(fb, body_font, lines, PAD, PAD, ink)
    overlay(fb, title, channel, dark, show_title, show_info, image_bottom=y)
    return buf, fb


def message(text, dark=False):
    """Centred message — errors and status."""
    ink, _bg = colours(dark)
    buf, fb = new_canvas(dark)
    f = font.get("r20")
    lines = wrap(f, text, CANVAS_W - 2 * PAD)
    y = (CANVAS_H - len(lines) * (f.height + LINE_GAP)) // 2
    for line in lines:
        f.draw(fb, line, (CANVAS_W - f.width(line)) // 2, y, ink)
        y += f.height + LINE_GAP
    return buf, fb


def canvas_from(buf):
    """Wrap an existing portrait canvas so more can be drawn on it."""
    return framebuf.FrameBuffer(buf, CANVAS_W, CANVAS_H, framebuf.GS4_HMSB)


@micropython.viper
def _rotate(src: ptr8, dst: ptr8):
    """Portrait 480x800 -> native 800x480: native (nx, ny) = (py, 479 - px)."""
    for py in range(800):
        srow = py * 240
        half = py >> 1
        odd = py & 1
        for px in range(480):
            b = int(src[srow + (px >> 1)])
            if px & 1:
                code = b & 0x0F
            else:
                code = b >> 4
            off = (479 - px) * 400 + half
            v = int(dst[off])
            if odd:
                dst[off] = (v & 0xF0) | code
            else:
                dst[off] = (v & 0x0F) | (code << 4)


def to_native(portrait):
    """Rotate a portrait canvas into a frame the panel can take."""
    frame = bytearray(BUF_LEN)
    _rotate(portrait, frame)
    return frame
