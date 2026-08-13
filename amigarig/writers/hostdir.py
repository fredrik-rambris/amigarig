"""Writes resolved copy items into a real host directory."""
from __future__ import annotations

import shutil
from pathlib import Path

from ..copyspec import ResolvedCopyItem


class HostDirWriter:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, item: ResolvedCopyItem) -> None:
        item.dest.parent.mkdir(parents=True, exist_ok=True)
        if item.source.is_dir():
            shutil.copytree(item.source, item.dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item.source, item.dest)

    def write_bytes(self, dest: Path, data: bytes) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def finalize(self) -> None:
        pass
