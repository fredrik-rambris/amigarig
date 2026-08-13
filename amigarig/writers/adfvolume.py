"""Writes resolved copy items into an Amiga disk image (ADF/HDF) via amitools.fs.

Uses amitools as a library (ADFSVolume / BlkDevFactory), the same classes
xdftool's CLI is built on top of -- lifted from amitools/tools/xdftool.py's
CreateCmd/WriteCmd/MakeDirCmd handlers rather than shelling out to xdftool.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from amitools.fs.ADFSVolume import ADFSVolume
from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
from amitools.fs.FSString import FSString

from ..copyspec import ResolvedCopyItem


def _fs(s: str) -> FSString:
    return FSString(s)


class ADFVolumeWriter:
    def __init__(self, image_path: Path, volume_name: str, size_options: dict | None = None):
        self.image_path = Path(image_path)
        self.image_path.parent.mkdir(parents=True, exist_ok=True)
        self.blkdev = BlkDevFactory().create(
            str(self.image_path), options=size_options, force=True
        )
        self.vol = ADFSVolume(self.blkdev)
        self.vol.create(_fs(volume_name))
        self._known_dirs: set[str] = set()

    def _ensure_dir(self, ami_dir: str) -> None:
        if not ami_dir or ami_dir in self._known_dirs:
            return
        parts = PurePosixPath(ami_dir).parts
        current = ""
        for part in parts:
            current = f"{current}/{part}" if current else part
            if current in self._known_dirs:
                continue
            if self.vol.get_dir_path_name(_fs(current)) is None:
                self.vol.create_dir(_fs(current))
            self._known_dirs.add(current)

    @staticmethod
    def _to_ami_path(dest: Path) -> tuple[str, str]:
        """Volume-relative dest -> (ami_dir, file_name).

        `dest` is a plain Path built by joining onto a virtual root assign
        (e.g. `boot:` pointed at Path("/") for image targets) -- it is never
        a real host path here, just a container for relative structure, so
        any leading "/" is stripped before splitting into an AmigaDOS path.
        """
        rel = dest.as_posix().lstrip("/")
        parent, _, name = rel.rpartition("/")
        return parent, name

    def write(self, item: ResolvedCopyItem) -> None:
        if item.source.is_dir():
            for child in sorted(item.source.rglob("*")):
                if child.is_file():
                    rel = child.relative_to(item.source)
                    self._write_file(item.dest / rel, child.read_bytes())
        else:
            self._write_file(item.dest, item.source.read_bytes())

    def _write_file(self, dest: Path, data: bytes) -> None:
        ami_dir, file_name = self._to_ami_path(dest)
        self._ensure_dir(ami_dir)
        self.vol.write_file(data, _fs(ami_dir), _fs(file_name))

    def write_bytes(self, dest: Path, data: bytes) -> None:
        self._write_file(dest, data)

    def finalize(self) -> None:
        self.vol.close()
        self.blkdev.close()
