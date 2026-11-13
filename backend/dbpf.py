"""DBPF package reader backed by :mod:`sims4_sdk.core.dbpf`.

The studio historically shipped its own DBPF parser.  It now delegates the
binary work to the bundled SDK and keeps this small compatibility layer so the
rest of the studio (catalog scan, images, household templates) can keep using
``package.entries`` / ``iter_type`` / ``read_entry``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .sdk import SDK_AVAILABLE

if SDK_AVAILABLE:
    from sims4_sdk.core import DBPF as _SDKDBPF
    from sims4_sdk.core import DBPFError as _SDKDBPFError
    from sims4_sdk.core import ResourceEntry as _SDKEntry
else:  # pragma: no cover
    _SDKDBPF = None  # type: ignore[assignment]
    _SDKEntry = None  # type: ignore[assignment]

    class _SDKDBPFError(Exception):
        pass


DBPF_MAGIC = b"DBPF"


@dataclass
class Entry:
    type: int
    group: int
    instance: int
    offset: int
    size: int
    decompressed_size: int
    compressed: bool
    index: int


class DBPFError(_SDKDBPFError):
    pass


class DBPF:
    """Read-only DBPF package."""

    def __init__(self, path: str | Path):
        if _SDKDBPF is None:
            raise DBPFError("SimsDataSDK is not available")
        self.path = Path(path)
        try:
            self._sdk = _SDKDBPF(self.path)
        except _SDKDBPFError as exc:
            raise DBPFError(str(exc)) from exc
        self._sdk_entries: list = list(self._sdk.entries)
        self.entries: list[Entry] = [
            Entry(
                type=raw.key.type_id,
                group=raw.key.group,
                instance=raw.key.instance,
                offset=raw.offset,
                size=raw.size,
                decompressed_size=raw.mem_size,
                compressed=raw.compressed,
                index=index,
            )
            for index, raw in enumerate(self._sdk_entries)
        ]
        self.index_version = getattr(self._sdk.header, "minor_version", 0)

    # ------------------------------------------------------------------- data
    def read_entry(self, entry: Entry) -> bytes:
        raw = self._sdk_entries[entry.index]
        try:
            return self._sdk.read_resource(raw)
        except _SDKDBPFError as exc:
            raise DBPFError(str(exc)) from exc

    def read_all(self) -> list[tuple[Entry, bytes]]:
        out = []
        for e in self.entries:
            try:
                out.append((e, self.read_entry(e)))
            except Exception:
                continue
        return out

    def iter_type(self, rtype: int) -> Iterator[tuple[Entry, bytes]]:
        for e in self.entries:
            if e.type != rtype:
                continue
            try:
                yield e, self.read_entry(e)
            except Exception:
                continue

    def find_first(self, rtype: int) -> tuple[Entry, bytes] | None:
        for item in self.iter_type(rtype):
            return item
        return None


# Common Sims 4 resource type ids
TYPES = {
    "thumbnail": 0x00000000,
    "simdata": 0x545AC67A,
    "stbl": 0x220557DA,
    "png": 0x2F7D0004,
    "dds": 0x00B2D882,
    "jpeg": 0x00000000,
    "namemap": 0x0166038C,
}
