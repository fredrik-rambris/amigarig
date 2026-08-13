"""Writer backends: turn a ResolvedCopyItem into bytes actually written somewhere."""
from __future__ import annotations

from typing import Protocol

from ..copyspec import ResolvedCopyItem


class Writer(Protocol):
    def write(self, item: ResolvedCopyItem) -> None: ...
    def write_bytes(self, dest, data: bytes) -> None: ...
    def finalize(self) -> None: ...
