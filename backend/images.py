"""Decode Tray ``.sgi`` / ``.hhi`` artwork and cache browser-friendly files.

The bundled SDK parses Maxis JPEGs and their embedded ALFA/ALFJ alpha segments.
Some Tray wrappers use a slightly different 16-byte marker than the SDK currently
accepts, so a small XOR-wrapper fallback is kept here (see
``docs/sdk-migration.md``).  The decoded JPEG/alpha split always comes from the
SDK's ``Artwork`` model.
"""
from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

from .sdk import SDK_AVAILABLE
from .settings import DATA_DIR, paths

if SDK_AVAILABLE:
    from sims4_sdk.save.artwork import Artwork, ArtworkError, decode_artwork, read_tray_image
else:  # pragma: no cover
    Artwork = object  # type: ignore[assignment]
    ArtworkError = ValueError  # type: ignore[assignment]

    def decode_artwork(data: bytes):  # type: ignore[no-redef]
        raise ArtworkError("SimsDataSDK is not available")

    def read_tray_image(path):  # type: ignore[no-redef]
        raise ArtworkError("SimsDataSDK is not available")


CACHE_DIR = DATA_DIR / "image_cache"
CACHE_DIR.mkdir(exist_ok=True)

XOR_KEY = bytes.fromhex("4125e6cd47bab21a")
INSTANCE_RE = re.compile(r"^0x[0-9a-fA-F]{16}$")
PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _decode_wrapper(data: bytes) -> "Artwork":
    """Fallback for Tray wrapper variants the SDK's marker check rejects."""
    payload = data
    if not data[:3] == b"\xff\xd8\xff":
        if len(data) > 24 and int.from_bytes(data[:4], "little") == len(data) - 24:
            payload = bytes(byte ^ XOR_KEY[index % len(XOR_KEY)] for index, byte in enumerate(data[24:]))
        else:
            raise ArtworkError("unsupported Tray image wrapper")
    try:
        return decode_artwork(payload)
    except ArtworkError:
        # A few portrait JPEGs omit their EOI marker; browsers still render
        # them, so preserve the historical pass-through behaviour.
        if payload.startswith(b"\xff\xd8"):
            return Artwork(jpeg=payload)
        raise


def read_artwork(path: Path) -> "Artwork":
    try:
        return read_tray_image(path)
    except Exception:
        return _decode_wrapper(path.read_bytes())


def _png_chunks(data: bytes):
    pos = 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        yield kind, payload
        pos += 12 + length


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _mask_to_alpha_png(mask_png: bytes, crisp: bool = False) -> bytes | None:
    """Convert a grayscale mask PNG into an RGBA PNG whose alpha is the mask."""
    try:
        width = height = 0
        bit_depth = color_type = 0
        raw = bytearray()
        for kind, payload in _png_chunks(mask_png):
            if kind == b"IHDR":
                width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
            elif kind == b"IDAT":
                raw.extend(payload)
        if not width or bit_depth != 8 or color_type != 0:
            return None
        pixels = zlib.decompress(bytes(raw))
        channels = 1
        stride = width
        prev = bytearray(stride)
        rows = []
        pos = 0
        for _ in range(height):
            f = pixels[pos]
            pos += 1
            line = bytearray(pixels[pos : pos + stride])
            pos += stride
            if f == 1:
                for i in range(1, stride):
                    line[i] = (line[i] + line[i - 1]) & 0xFF
            elif f == 2:
                for i in range(stride):
                    line[i] = (line[i] + prev[i]) & 0xFF
            elif f == 3:
                for i in range(stride):
                    left = line[i - 1] if i else 0
                    line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
            elif f == 4:
                for i in range(stride):
                    left = line[i - 1] if i else 0
                    up_left = prev[i - 1] if i else 0
                    line[i] = (line[i] + _paeth(left, prev[i], up_left)) & 0xFF
            rows.append(line)
            prev = line

        def alpha(value: int) -> int:
            if not crisp:
                return value
            if value < 80:
                return 0
            if value > 170:
                return 255
            return int((value - 80) * 255 / 90)

        out = bytearray()
        for line in rows:
            out.append(0)
            for value in line:
                out.extend((255, 255, 255, alpha(value)))
        compressed = zlib.compress(bytes(out), 6)

        def chunk(tag: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
        return PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    except (zlib.error, struct.error, ValueError):
        return None


_INDEX: dict[str, tuple[float, dict[str, Path]]] = {}


def _index(kind: str) -> dict[str, Path]:
    if not paths.tray or not paths.tray.is_dir():
        return {}
    try:
        mtime = paths.tray.stat().st_mtime
    except OSError:
        return {}
    cached = _INDEX.get(kind)
    if cached and cached[0] == mtime:
        return cached[1]
    suffix = ".sgi" if kind == "sim" else ".hhi"
    found: dict[str, Path] = {}
    try:
        for p in paths.tray.iterdir():
            if not p.is_file() or p.suffix.lower() != suffix:
                continue
            instance = p.stem.split("!")[-1]
            current = found.get(instance)
            try:
                if current is None or p.stat().st_size > current.stat().st_size:
                    found[instance] = p
            except OSError:
                continue
    except OSError:
        return {}
    _INDEX[kind] = (mtime, found)
    return found


def image_path(instance: str, kind: str) -> Path | None:
    """Return a cached JPEG for a Tray sim (`kind='sim'`) or household."""
    if not INSTANCE_RE.match(instance or ""):
        return None
    kind = "sim" if kind == "sim" else "household"
    source = _index(kind).get(instance)
    if source is None:
        return None
    try:
        mtime = source.stat().st_mtime
    except OSError:
        return None
    target = CACHE_DIR / f"{instance}_{kind}.jpg"
    if target.is_file():
        try:
            if target.stat().st_mtime >= mtime:
                return target
        except OSError:
            pass
    try:
        artwork = read_artwork(source)
    except (ArtworkError, OSError, ValueError):
        return None
    if not artwork.jpeg:
        return None
    target.write_bytes(artwork.jpeg)
    return target


def has_image(instance: str, kind: str) -> bool:
    if not INSTANCE_RE.match(instance or ""):
        return False
    return instance in _index("sim" if kind == "sim" else "household")


def png_path(instance: str, kind: str) -> Path | None:
    """Convert Tray artwork with its embedded alpha to a cached SDK PNG."""
    if not INSTANCE_RE.fullmatch(instance or ""):
        return None
    kind = "sim" if kind == "sim" else "household"
    source = _index(kind).get(instance)
    if source is None:
        return None
    return _artwork_png_path(source, CACHE_DIR / f"{instance}_{kind}_sdk.png", tray=True)


def _artwork_png_path(source: Path, target: Path, *, tray: bool = False) -> Path | None:
    try:
        if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
            return target
        artwork = read_artwork(source) if tray else decode_artwork(source.read_bytes())
        target.write_bytes(artwork.to_png())
        return target
    except (ArtworkError, OSError, ValueError, ImportError):
        return None


def premade_png_path(template: str) -> Path | None:
    template = (template or "").lower().removeprefix("0x").zfill(16)
    if len(template) != 16 or not all(c in "0123456789abcdef" for c in template):
        return None
    source = DATA_DIR / "premade_images" / f"{template}.jpg"
    if not source.is_file():
        return None
    return _artwork_png_path(source, source.with_name(f"{template}_sdk.png"))


def mask_path(instance: str, kind: str) -> Path | None:
    kind = "sim" if kind == "sim" else "household"
    target = CACHE_DIR / f"{instance}_{kind}_mask.png"
    if target.is_file():
        return target
    source = _index(kind).get(instance)
    if source is None:
        return None
    try:
        artwork = read_artwork(source)
    except (ArtworkError, OSError, ValueError):
        return None
    if not artwork.alpha_mask or artwork.alpha_format != "png":
        return None
    alpha = _mask_to_alpha_png(artwork.alpha_mask, crisp=(kind == "sim"))
    if not alpha:
        return None
    target.write_bytes(alpha)
    return target


def premade_mask_path(template: str) -> Path | None:
    template = (template or "").lower().removeprefix("0x").zfill(16)
    if not all(c in "0123456789abcdef" for c in template):
        return None
    source = DATA_DIR / "premade_images" / f"{template}.jpg"
    if not source.is_file():
        return None
    target = DATA_DIR / "premade_images" / f"{template}_mask.png"
    if target.is_file():
        return target
    try:
        artwork = decode_artwork(source.read_bytes())
    except (ArtworkError, OSError, ValueError):
        return None
    if not artwork.alpha_mask or artwork.alpha_format != "png":
        return None
    alpha = _mask_to_alpha_png(artwork.alpha_mask)
    if not alpha:
        return None
    target.write_bytes(alpha)
    return target


def mask_url(instance: str, kind: str) -> str:
    return f"/api/tray/image_mask?kind={kind}&instance={instance}"


def has_mask(instance: str, kind: str) -> bool:
    """True when the Tray image carries an embedded PNG alpha mask."""
    kind = "sim" if kind == "sim" else "household"
    if not INSTANCE_RE.match(instance or ""):
        return False
    source = _index(kind).get(instance)
    if source is None:
        return False
    try:
        artwork = read_artwork(source)
    except (ArtworkError, OSError, ValueError):
        return False
    return bool(artwork.alpha_mask and artwork.alpha_format == "png")


def mask_url_if_any(instance: str, kind: str) -> str:
    if png_path(instance, kind) is not None:
        return ""
    return mask_url(instance, kind) if has_mask(instance, kind) else ""


def premade_mask_url(template: str) -> str:
    return f"/api/premade/mask?template={template}"


def premade_mask_url_if_any(template: str) -> str:
    clean = (template or "").lower().removeprefix("0x").zfill(16)
    if premade_png_path(clean) is not None:
        return ""
    return premade_mask_url(clean) if premade_mask_path(clean) else ""


def sim_image_url(sim_id) -> str:
    if not sim_id:
        return ""
    return f"/api/tray/image?kind=sim&instance=0x{sim_id:016x}&format=png"


def household_image_url(ident: str) -> str:
    if not ident:
        return ""
    return f"/api/tray/image?kind=household&instance={ident}&format=png"
