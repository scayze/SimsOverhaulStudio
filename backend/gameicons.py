"""Serve tuning icons extracted by SimsDataSDK as browser-friendly PNGs.

The SDK resolves and converts tuning icons to PNG. A local decoder remains as
a fallback for environments where the SDK conversion is unavailable.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

from . import sdk
from .settings import DATA_DIR

CACHE_DIR = DATA_DIR / "icon_cache"
CACHE_DIR.mkdir(exist_ok=True)
PNG_SIG = b"\x89PNG\r\n\x1a\n"
_READY = False


def _key_name(icon_key: str) -> str:
    return "".join(ch for ch in icon_key.lower() if ch in "0123456789abcdef")


def warm() -> None:
    """Build the SDK's image index once so the first catalog icon is instant."""
    global _READY
    workspace = sdk.workspace()
    if workspace is not None and workspace.installation is not None:
        try:
            workspace.installation.image_index()
        except Exception:
            return
        _READY = True


def icon_url(icon_key: str, fallback: str = "") -> str:
    from urllib.parse import quote

    url = f"/api/icon?key={quote(icon_key)}"
    if fallback:
        url += f"&fallback={quote(fallback, safe='')}"
    return url


def placeholder_path() -> Path:
    target = CACHE_DIR / "placeholder.png"
    if not target.is_file():
        target.write_bytes(_rgba_png(1, 1, b"\x00\x00\x00\x00"))
    return target


def icon_path(icon_key: str) -> Path | None:
    """Return a cached PNG for an SDK icon key, or ``None`` when unavailable."""
    if not icon_key:
        return None
    target = CACHE_DIR / f"sdk_{_key_name(icon_key)}.png"
    if target.is_file():
        return target
    if not _READY:
        # Avoid blocking the first catalog paint on the SDK's 10s image-index
        # scan; the app warms it in the background and the UI falls back to the
        # icon pack until then.
        return None
    workspace = sdk.workspace()
    if workspace is None:
        return None
    try:
        image = workspace.icon_for(icon_key)
    except Exception:
        return None
    if image is None or not image.data:
        return None
    try:
        png = image.to_png()
    except Exception:
        try:
            png = image.data if image.is_png else _dds_to_png(image.data)
        except Exception:
            return None
    if not png:
        return None
    target.write_bytes(png)
    return target


# ------------------------------------------------------------------ DDS/DXT
def _rgb565(value: int) -> tuple[int, int, int]:
    r = (value >> 11) & 0x1F
    g = (value >> 5) & 0x3F
    b = value & 0x1F
    return (
        (r << 3) | (r >> 2),
        (g << 2) | (g >> 4),
        (b << 3) | (b >> 2),
    )


def _dxt_colors(c0: int, c1: int, dxt1: bool) -> list[tuple[int, int, int, int]]:
    a = _rgb565(c0)
    b = _rgb565(c1)
    if not dxt1 or c0 > c1:
        return [
            (*a, 255),
            (*b, 255),
            (*( (2 * a[i] + b[i]) // 3 for i in range(3)), 255),
            (*( (a[i] + 2 * b[i]) // 3 for i in range(3)), 255),
        ]
    return [
        (*a, 255),
        (*b, 255),
        (*( (a[i] + b[i]) // 2 for i in range(3)), 255),
        (0, 0, 0, 0),
    ]


def _decode_dxt1(block: bytes, out: bytearray, width: int, x: int, y: int) -> None:
    c0, c1, indices = struct.unpack("<HHI", block)
    colors = _dxt_colors(c0, c1, True)
    for py in range(4):
        for px in range(4):
            if x + px >= width:
                continue
            index = (indices >> (2 * (py * 4 + px))) & 0x03
            r, g, b, a = colors[index]
            offset = ((y + py) * width + (x + px)) * 4
            out[offset:offset + 4] = bytes((r, g, b, a))


def _decode_dxt5(block: bytes, out: bytearray, width: int, x: int, y: int) -> None:
    a0, a1 = block[0], block[1]
    alpha_bits = int.from_bytes(block[2:8], "little")
    if a0 > a1:
        alphas = [a0, a1] + [
            ((7 - index) * a0 + index * a1) // 7 for index in range(1, 7)
        ]
    else:
        alphas = [a0, a1] + [
            ((5 - index) * a0 + index * a1) // 5 for index in range(1, 5)
        ] + [0, 255]
    c0, c1, indices = struct.unpack("<HHI", block[8:16])
    colors = _dxt_colors(c0, c1, False)
    for py in range(4):
        for px in range(4):
            if x + px >= width:
                continue
            pixel = py * 4 + px
            alpha = alphas[(alpha_bits >> (3 * pixel)) & 0x07]
            index = (indices >> (2 * pixel)) & 0x03
            r, g, b, _ = colors[index]
            offset = ((y + py) * width + (x + px)) * 4
            out[offset:offset + 4] = bytes((r, g, b, alpha))


def _dds_to_png(data: bytes) -> bytes | None:
    if len(data) < 128 or not data.startswith(b"DDS "):
        return None
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    fourcc = data[84:88].decode("ascii", "ignore").strip("\x00 ").upper()
    if not (0 < width <= 4096 and 0 < height <= 4096):
        return None
    body = data[128:]
    pixels = bytearray(width * height * 4)
    if fourcc in ("DXT1", "DXT3", "DXT5"):
        block_size = 8 if fourcc == "DXT1" else 16
        bw = (width + 3) // 4
        bh = (height + 3) // 4
        for by in range(bh):
            for bx in range(bw):
                offset = (by * bw + bx) * block_size
                block = body[offset:offset + block_size]
                if len(block) < block_size:
                    return None
                if fourcc == "DXT1":
                    _decode_dxt1(block, pixels, width, bx * 4, by * 4)
                elif fourcc == "DXT5":
                    _decode_dxt5(block, pixels, width, bx * 4, by * 4)
                else:
                    # DXT3: 8 bytes of explicit alpha then a DXT1 colour block.
                    alpha_bits = int.from_bytes(block[:8], "little")
                    c0, c1, indices = struct.unpack("<HHI", block[8:16])
                    colors = _dxt_colors(c0, c1, False)
                    for py in range(4):
                        for px in range(4):
                            if bx * 4 + px >= width or by * 4 + py >= height:
                                continue
                            pixel = py * 4 + px
                            alpha = ((alpha_bits >> (4 * pixel)) & 0x0F) * 17
                            index = (indices >> (2 * pixel)) & 0x03
                            r, g, b, _ = colors[index]
                            pos = ((by * 4 + py) * width + (bx * 4 + px)) * 4
                            pixels[pos:pos + 4] = bytes((r, g, b, alpha))
    else:
        # Uncompressed 32-bit DDS (BGRA/RGBA masks in the pixel-format block).
        size = width * height * 4
        if len(body) < size:
            return None
        try:
            flags = struct.unpack_from("<I", data, 80)[0]
            bit_count = struct.unpack_from("<I", data, 88)[0]
            masks = struct.unpack_from("<IIII", data, 92)
        except struct.error:
            return None
        if bit_count != 32 or not flags & 0x40:
            return None
        red_mask, green_mask, blue_mask, alpha_mask = masks

        def shift(mask: int) -> int:
            return (mask & -mask).bit_length() - 1 if mask else 0

        rs, gs, bs, as_ = shift(red_mask), shift(green_mask), shift(blue_mask), shift(alpha_mask)
        for index in range(width * height):
            value = int.from_bytes(body[index * 4:index * 4 + 4], "little")
            r = (value & red_mask) >> rs if red_mask else 255
            g = (value & green_mask) >> gs if green_mask else r
            b = (value & blue_mask) >> bs if blue_mask else r
            a = (value & alpha_mask) >> as_ if alpha_mask else 255
            pos = index * 4
            pixels[pos:pos + 4] = bytes((r, g, b, a))
    return _rgba_png(width, height, pixels)


def _rgba_png(width: int, height: int, pixels: bytes) -> bytes:
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride:(y + 1) * stride])

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_SIG
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
        + chunk(b"IEND", b"")
    )
