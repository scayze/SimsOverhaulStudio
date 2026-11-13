"""EA RefPack decompressor, delegated to :mod:`sims4_sdk.core.refpack`."""
from __future__ import annotations

from .sdk import SDK_AVAILABLE

if SDK_AVAILABLE:
    from sims4_sdk.core.refpack import RefPackError
    from sims4_sdk.core.refpack import decompress as _sdk_decompress
    from sims4_sdk.core.refpack import is_refpack as _sdk_is_refpack
else:  # pragma: no cover

    class RefPackError(ValueError):
        pass

    def _sdk_is_refpack(data: bytes) -> bool:
        return False

    def _sdk_decompress(data: bytes) -> bytes:
        raise RefPackError("SimsDataSDK is not available")


def is_refpack(data: bytes) -> bool:
    return _sdk_is_refpack(data)


def decompress(data: bytes) -> bytes:
    """Decompress a RefPack stream, returning ``data`` unchanged if it is not one.

    The historical helper tolerated non-RefPack payloads because DBPF often sets
    the compressed flag on resources that are stored raw.  Callers rely on that
    behaviour, so the SDK error is converted into a pass-through here.
    """
    if not _sdk_is_refpack(data):
        return data
    try:
        return _sdk_decompress(data)
    except RefPackError:
        return data
