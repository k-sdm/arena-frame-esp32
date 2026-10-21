"""Arena Frame on an ESP32-S3: pull a block from an Are.na channel and show it.

Port of the Pi frame's scheduler loop. Config lives in config.json on the device:
    {"ssid": "...", "password": "...", "channel": "slug", "token": null,
     "order": "newest", "refresh_minutes": 60, "proxy": true}

Position in the channel is kept in state.json, so each run moves one block along in
the chosen order; the order or channel changing resets it.
"""
import gc
import json
import random
import time

import arena
import inky
import render
import wifi

CONFIG = "config.json"
STATE = "state.json"


def load(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {} if default is None else default


def save(path, data):
    f = open(path, "w")
    try:
        f.write(json.dumps(data))
    finally:
        f.close()


def next_index(state, cfg):
    """Where to read next, resetting when the channel or order changed."""
    if state.get("channel") != cfg["channel"] or state.get("order") != cfg.get("order", "newest"):
        return 0
    return state.get("index", 0)


def channel_line(info):
    """Are.na/owner/channel. v3 calls the channel's owner "owner", with name and slug."""
    owner = info.get("owner") or {}
    who = owner.get("name") or owner.get("username") or owner.get("slug") or ""
    title = info.get("title") or info.get("slug") or ""
    return "/".join(p for p in ("Are.na", who, title) if p)


def show_block(display, block, info, cfg):
    """Compose a block on the portrait canvas, rotate it and push it. Returns what was shown."""
    dark = cfg.get("dark_mode", False)
    show_title = cfg.get("show_title", True)
    show_info = cfg.get("show_info", True)
    title = arena.block_title(block)
    channel = channel_line(info)
    url = arena.image_url(block)
    kind = "text"
    if url:
        try:
            import image
            reserve = render.overlay_height(title, channel, show_title, show_info)
            buf, image_h = image.render(url, cfg.get("proxy", True), dark,
                                        render.CANVAS_H - reserve)
            render.overlay(render.canvas_from(buf), title, channel, dark, show_title, show_info, image_h)
            kind = "image"
        except Exception as e:
            print("image failed:", e)
            buf, _ = render.text_page(title, "Image failed: %s" % e, channel, dark, show_title, show_info)
            kind = "image-failed"
    else:
        buf, _ = render.text_page(title, arena.block_text(block), channel, dark, show_title, show_info)
    display.show(render.to_native(buf))
    return kind


def run_once():
    cfg = load(CONFIG)
    panel = cfg.get("panel", inky.DEFAULT_PANEL)
    render.configure(panel)
    display = inky.get(panel)
    if not cfg.get("ssid") or not cfg.get("channel"):
        buf, _ = render.message("Add wifi and channel in the setup page")
        display.show(render.to_native(buf))
        return
    print("wifi:", wifi.connect(cfg["ssid"], cfg["password"]))
    slug, token = cfg["channel"], cfg.get("token")
    order = cfg.get("order", "newest")
    state = load(STATE, {})
    index = next_index(state, cfg)
    try:
        info = arena.channel(slug, token)
        if order == "random":
            _b, total, _i = arena.block_at(slug, 0, token)
            index = random.randrange(total) if total else 0
        block, total, index = arena.block_at(slug, index, token, oldest_first=(order == "oldest"))
    except Exception as e:
        buf, _ = render.message(str(e), cfg.get("dark_mode", False))
        display.show(render.to_native(buf))
        raise
    gc.collect()
    if block is None:
        buf, _ = render.message("Channel %s has no blocks" % slug)
        display.show(render.to_native(buf))
        return
    print("block %s (%s) at %d of %d" % (block.get("id"), block.get("type"), index + 1, total))
    kind = show_block(display, block, info, cfg)
    save(STATE, {"channel": slug, "order": order, "index": (index + 1) % (total or 1),
                 "last_id": block.get("id"), "total": total, "shown": kind})
    print("shown:", kind)


def main():
    while True:
        try:
            run_once()
        except Exception as e:
            print("error:", e)
        minutes = load(CONFIG).get("refresh_minutes", 60)
        print("sleeping %d min" % minutes)
        time.sleep(minutes * 60)


if __name__ == "__main__":
    main()
