"""Tolerant protobuf helpers backed by :mod:`sims4_sdk.save.protobuf`.

Only the generic wire-format helpers remain here.  Save and Tray parsing use the
SDK's schema-driven readers directly (see ``backend/saves.py`` and
``backend/tray.py``); this module exists for the handful of supplemental
protobuf blocks the SDK does not model yet (pre-made secrets, dynasty seeds,
relationship tracker bits).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sdk import SDK_AVAILABLE

if SDK_AVAILABLE:
    from sims4_sdk.save.protobuf import ProtobufError as _SDKProtobufError
else:  # pragma: no cover
    _SDKProtobufError = ValueError


class ProtobufError(_SDKProtobufError):
    pass


def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 0
    start = pos
    while pos < len(buf) and shift < 70:
        byte = buf[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7
    raise ProtobufError(f"truncated varint at offset {start}")


def iter_fields(buf: bytes) -> list["Field"]:
    """Parse one protobuf message level, resynchronising on malformed data.

    The SDK's save decoder is strict (it must be, to avoid silent corruption).
    The supplemental household fields are read best-effort, so a bad byte in an
    unrelated nested block must not discard the whole message.
    """
    fields: list[Field] = []
    pos = 0
    end = len(buf)
    while pos < end:
        start = pos
        try:
            key, pos = read_varint(buf, pos)
        except ProtobufError:
            pos = start + 1
            continue
        number = key >> 3
        wire = key & 0x07
        if number == 0 or number > 200000:
            pos = start + 1
            continue
        if wire == 0:
            try:
                value, pos = read_varint(buf, pos)
            except ProtobufError:
                pos = start + 1
                continue
            fields.append(Field(number, wire, value))
        elif wire == 1:
            if pos + 8 > end:
                break
            fields.append(Field(number, wire, buf[pos:pos + 8]))
            pos += 8
        elif wire == 5:
            if pos + 4 > end:
                break
            fields.append(Field(number, wire, buf[pos:pos + 4]))
            pos += 4
        elif wire == 2:
            try:
                length, pos = read_varint(buf, pos)
            except ProtobufError:
                pos = start + 1
                continue
            if length < 0 or pos + length > end:
                pos = start + 1
                continue
            fields.append(Field(number, wire, buf[pos:pos + length]))
            pos += length
        else:
            pos = start + 1
    return fields


@dataclass
class Field:
    number: int
    wire: int
    value: Any

    @property
    def is_bytes(self) -> bool:
        return self.wire == 2

    def as_text(self) -> str | None:
        if not isinstance(self.value, bytes):
            return None
        try:
            text = self.value.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if not text:
            return None
        if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in text):
            return None
        if not any(ch.isalpha() for ch in text):
            return None
        return text


@dataclass
class SimName:
    first: str
    last: str
    first_field: int = 5
    last_field: int = 6
    extra: dict = field(default_factory=dict)


def extract_sim_names(data: bytes, max_depth: int = 18) -> list[SimName]:
    """Find messages that contain a pair of short string fields."""
    found: dict[tuple[str, str], SimName] = {}

    def walk(buf: bytes, depth: int) -> None:
        if depth > max_depth or not buf:
            return
        fields = iter_fields(buf)
        short: dict[int, str] = {}
        for f in fields:
            text = f.as_text()
            if text is not None and 1 <= len(text) <= 48:
                short.setdefault(f.number, text)

        if 5 in short and 6 in short:
            first, last = short[5], short[6]
            if _looks_like_name(first) and _looks_like_name(last):
                found.setdefault((first, last), SimName(first, last))

        for f in fields:
            if isinstance(f.value, bytes) and 4 < len(f.value) < 2_000_000:
                walk(f.value, depth + 1)

    walk(data, 0)
    return list(found.values())


def _looks_like_name(text: str) -> bool:
    if not text or len(text) > 48:
        return False
    if text.startswith(("0x", "http")):
        return False
    if not any(ch.isalpha() for ch in text):
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '-.æøåéèêëáàâäíìîïóòôöúùûüçñ")
    return all(ch in allowed for ch in text)


def fast_sim_names(data: bytes) -> list[SimName]:
    """Scan for the exact first_name/last_name protobuf pair.

    Kept for the supplemental readers that only need names; saves and Tray use
    the SDK's schema-driven models instead.
    """
    found: dict[tuple[str, str], SimName] = {}
    pos = 0
    length = len(data)
    while True:
        pos = data.find(b"\x2a", pos)
        if pos < 0:
            break
        if pos + 3 < length:
            l1 = data[pos + 1]
            if 2 <= l1 <= 40 and pos + 2 + l1 + 1 < length:
                end1 = pos + 2 + l1
                if data[end1] == 0x32:
                    l2 = data[end1 + 1]
                    if 2 <= l2 <= 40 and end1 + 2 + l2 <= length:
                        try:
                            first = data[pos + 2 : end1].decode("utf-8")
                            last = data[end1 + 2 : end1 + 2 + l2].decode("utf-8")
                        except UnicodeDecodeError:
                            first = last = ""
                        if _looks_like_name(first) and _looks_like_name(last):
                            found.setdefault((first, last), SimName(first, last))
        pos += 1
    return list(found.values())


def extract_strings(data: bytes, max_depth: int = 14, min_len: int = 3, max_len: int = 90) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def walk(buf: bytes, depth: int) -> None:
        if depth > max_depth:
            return
        for f in iter_fields(buf):
            if not isinstance(f.value, bytes):
                continue
            text = f.as_text()
            if text is not None and min_len <= len(text) <= max_len:
                if text not in seen:
                    seen.add(text)
                    out.append(text)
            elif 4 < len(f.value) < 2_000_000:
                walk(f.value, depth + 1)

    walk(data, 0)
    return out
