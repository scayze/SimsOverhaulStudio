"""Extract the game's premade household composite thumbnails (read-only).

The Sims 4 ships a transparent-background group portrait for every premade
household as resource type 0x3BD45407, keyed by the household template instance
id. Several sizes are shipped per household; we keep the largest. The files are
JPEGs with an embedded ``ALFA`` PNG mask, the same format as Tray ``.hhi``.

Extracted JPEGs are cached under ``data/premade_images/<template_id>.jpg``.
The studio only ever reads from the game install; nothing is written there.
"""
from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

from .settings import APP_DIR

IMAGE_DIR = APP_DIR / "data" / "premade_images"
MANIFEST = IMAGE_DIR / "_extracted.json"
CROPS_FILE = IMAGE_DIR / "portrait_crops.json"
_CHECKED = {"done": False}
_CROPS: dict | None = None


def find_portraits(template_ids: set[int]) -> dict[int, bytes]:
    """Return SDK-indexed household artwork using game package precedence."""
    from . import sdk
    installation = sdk.installation()
    if installation is None:
        return {}
    from sims4_sdk.premade_artwork import PremadeCompositeIndex

    result = PremadeCompositeIndex(installation).read(template_ids)
    return {template_id: image.artwork.jpeg for template_id in template_ids
            if (image := result.largest(template_id)) is not None}


def ensure_premade_images(force: bool = False) -> dict:
    """Make sure every premade household in the dataset has a cached portrait.

    Only missing files are written on a normal run, so this is cheap after the
    first extraction. Returns a small summary used by the UI/status endpoint.
    """
    from .templatedata import load_complete_dataset

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    if _CHECKED["done"] and not force:
        ids = set()
        try:
            ids = set(json.loads(MANIFEST.read_text(encoding="utf-8")).get("template_ids", []))
        except (OSError, ValueError):
            pass
        return {"total": len(ids), "cached": sum(1 for t in ids if (IMAGE_DIR / f"{t:016x}.jpg").is_file()), "written": 0}
    dataset = load_complete_dataset()
    ids = {h["template_id"] for h in dataset.get("households", []) if h.get("template_id")}
    missing = {
        t for t in ids
        if force or not (IMAGE_DIR / f"{t:016x}.jpg").is_file()
    }
    written = 0
    _CHECKED["done"] = True
    found = 0
    if missing:
        portraits = find_portraits(missing)
        found = len(portraits)
        for template, data in portraits.items():
            target = IMAGE_DIR / f"{template:016x}.jpg"
            old = target.read_bytes() if target.is_file() else b""
            if force or len(data) > len(old):
                target.write_bytes(data)
                # Invalidate the cached alpha mask derived from the old JPEG.
                (IMAGE_DIR / f"{template:016x}_mask.png").unlink(missing_ok=True)
                written += 1
    try:
        MANIFEST.write_text(
            json.dumps({"template_ids": sorted(ids), "found": found}),
            encoding="utf-8",
        )
    except OSError:
        pass
    return {
        "total": len(ids),
        "cached": sum(1 for t in ids if (IMAGE_DIR / f"{t:016x}.jpg").is_file()),
        "written": written,
    }


# ---------------------------------------------------------------------------
# Per-sim portrait crops
# ---------------------------------------------------------------------------
def _png_chunks(data: bytes):
    pos = 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        yield data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        pos += 12 + length


def _alpha_grid(mask_png: bytes):
    w = h = ct = 0
    raw = bytearray()
    for kind, payload in _png_chunks(mask_png):
        if kind == b"IHDR":
            w, h, _bd, ct = struct.unpack(">IIBB", payload[:10])
        elif kind == b"IDAT":
            raw.extend(payload)
    chans = {0: 1, 2: 3, 4: 2, 6: 4}.get(ct, 1)
    stride = w * chans
    pixels = zlib.decompress(bytes(raw))
    prev = bytearray(stride)
    rows = []
    pos = 0
    for _ in range(h):
        f = pixels[pos]
        pos += 1
        line = bytearray(pixels[pos:pos + stride])
        pos += stride
        if f == 1:
            for i in range(chans, stride):
                line[i] = (line[i] + line[i - chans]) & 255
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                left = line[i - chans] if i >= chans else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i - chans] if i >= chans else 0
                b = prev[i]
                c = prev[i - chans] if i >= chans else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 255
        rows.append(line)
        prev = line
    return w, h, chans, rows


def _embedded_mask(jpeg: bytes) -> bytes | None:
    """Return the PNG alpha mask via the SDK's artwork decoder."""
    try:
        from sims4_sdk.save.artwork import decode_artwork

        artwork = decode_artwork(jpeg)
    except Exception:
        return None
    if artwork.alpha_mask and artwork.alpha_format == "png":
        return artwork.alpha_mask
    return None


def compute_crops(template: int, n_sims: int) -> list[list[int]] | None:
    """Split a household composite into one crop rectangle per sim.

    The game arranges household members side by side. We find the horizontal
    extent of the (alpha-masked) figures, divide it into evenly spaced columns
    and snap each boundary to the nearest low-alpha valley between sims.
    """
    jpg = IMAGE_DIR / f"{template:016x}.jpg"
    if not jpg.is_file() or n_sims < 1:
        return None
    try:
        mask = _embedded_mask(jpg.read_bytes())
        if not mask:
            return None
        w, h, chans, rows = _alpha_grid(mask)
    except (OSError, zlib.error, struct.error, ValueError):
        return None
    if not w or not h:
        return None
    col = [0] * w
    for row in rows:
        for x in range(w):
            col[x] += row[x * chans]
    mx = max(col) or 1
    win = 11
    sm = [sum(col[max(0, x - win):x + win + 1]) / len(col[max(0, x - win):x + win + 1]) for x in range(w)]
    thr = 0.035 * mx
    left = next((x for x in range(w) if sm[x] > thr), 0)
    right = next((x for x in range(w - 1, -1, -1) if sm[x] > thr), w - 1)
    if right - left < 80:
        left, right = 0, w - 1
    span = right - left
    if n_sims == 1:
        edges = [left, right]
    else:
        seg = span / n_sims
        splits = []
        for i in range(1, n_sims):
            target = left + i * seg
            lo = int(max(left + 8, target - seg * 0.45))
            hi = int(min(right - 8, target + seg * 0.45))
            if hi <= lo:
                splits.append(int(target))
            else:
                splits.append(min(range(lo, hi), key=lambda x: sm[x]))
        edges = [left] + splits + [right]
    crops = []
    for i in range(n_sims):
        x0, x1 = edges[i], edges[i + 1]
        ys = [y for y in range(h) if any(rows[y][x * chans] > 60 for x in range(x0, x1, 3))]
        y0 = max(0, min(ys) - 18) if ys else 0
        y1 = min(h, max(ys) + 18) if ys else h
        if y1 - y0 < 60:
            y0, y1 = 0, h
        crops.append([x0, y0, x1, y1])
    return crops


def build_crops(force: bool = False) -> dict:
    from .templatedata import load_complete_dataset

    if CROPS_FILE.is_file() and not force:
        try:
            return json.loads(CROPS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    dataset = load_complete_dataset()
    out = {}
    for hh in dataset.get("households", []):
        tpl = hh.get("template_id")
        sims = hh.get("sims", [])
        if not tpl or not sims:
            continue
        crops = compute_crops(tpl, len(sims))
        if crops:
            out[f"{tpl:016x}"] = crops
    try:
        CROPS_FILE.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass
    return out


def load_crops() -> dict:
    global _CROPS
    if _CROPS is not None:
        return _CROPS
    if not CROPS_FILE.is_file():
        _CROPS = build_crops()
        return _CROPS
    try:
        _CROPS = json.loads(CROPS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _CROPS = {}
    return _CROPS


def portrait_crop(template: str, index: int) -> list[int] | None:
    key = (template or "").lower().removeprefix("0x").zfill(16)
    crops = load_crops().get(key)
    if crops and 0 <= index < len(crops):
        return crops[index]
    return None


if __name__ == "__main__":
    print(ensure_premade_images(force=True))
    print("portrait crops", len(build_crops(force=True)))
