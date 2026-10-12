"""Are.na API v3 client — the parts of sources/arena.py the frame needs.

v3 returns {"data": [...], "meta": {...}}; channel contents default to newest first
(sort=position_desc), sort=position_asc gives oldest first. Max 100 per page.
"""
import requests

API = "https://api.are.na/v3"
PER_PAGE = 20
SUPPORTED = ("Image", "Text", "Link", "Attachment", "Media")


def _get(path, token=None, **params):
    url = API + path
    if params:
        url += "?" + "&".join("%s=%s" % (k, v) for k, v in params.items())
    headers = {"User-Agent": "ArenaFrame-ESP32/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = requests.get(url, headers=headers)
    try:
        if r.status_code == 404:
            raise RuntimeError("channel not found")
        if r.status_code in (401, 403):
            raise RuntimeError("unauthorised — private channel needs a token")
        if r.status_code != 200:
            raise RuntimeError("are.na returned %d" % r.status_code)
        return r.json()
    finally:
        r.close()


def channel(slug, token=None):
    """Channel metadata: title, user, length."""
    d = _get("/channels/" + slug, token)
    return d.get("data", d)


def contents(slug, token=None, page=1, per=PER_PAGE, oldest_first=False):
    """One page of blocks, newest first unless oldest_first."""
    d = _get("/channels/%s/contents" % slug, token, per=per, page=page,
             sort="position_asc" if oldest_first else "position_desc")
    blocks = [b for b in d.get("data", []) if b.get("base_type") == "Block"]
    return blocks, d.get("meta", {})


def image_url(block):
    """Image URL for a block, or None.

    v3 puts variants (square, small, medium, large) under "image", each a dict with
    "src"; image["src"] is the original, which can be many megabytes.
    """
    img = block.get("image") or {}
    for key in ("large", "medium", "small"):
        variant = img.get(key)
        if isinstance(variant, dict) and variant.get("src"):
            return variant["src"]
    return img.get("src")


def block_text(block):
    """What to show for a non-image block. v3 descriptions are {"markdown", "html"}."""
    for key in ("content", "description", "title"):
        value = block.get(key)
        if isinstance(value, dict):
            value = value.get("markdown") or value.get("html")
        if value:
            return value
    return ""


def block_title(block):
    return block.get("title") or block.get("generated_title") or ""


def block_at(slug, index, token=None, oldest_first=False):
    """(block, channel length, index actually used) — one block by position.

    Asks for a single-item page so the device never holds a whole channel: with per=1
    the page number is the position and total_pages is the channel length.
    """
    blocks, meta = contents(slug, token, page=index + 1, per=1, oldest_first=oldest_first)
    total = meta.get("total_pages") or meta.get("length") or 0
    if not blocks:                                   # past the end: wrap to the start
        blocks, meta = contents(slug, token, page=1, per=1, oldest_first=oldest_first)
        index = 0
        total = meta.get("total_pages") or meta.get("length") or len(blocks)
    return (blocks[0] if blocks else None), total, index
