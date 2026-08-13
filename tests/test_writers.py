from pathlib import Path

from amigarig.copyspec import ResolvedCopyItem
from amigarig.writers.hostdir import HostDirWriter
from amigarig.writers.adfvolume import ADFVolumeWriter


def test_hostdir_writer_copies_file(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("hello")
    root = tmp_path / "root"
    writer = HostDirWriter(root)
    writer.write(ResolvedCopyItem(source=src, dest=root / "sub" / "dest.txt"))
    assert (root / "sub" / "dest.txt").read_text() == "hello"


def test_hostdir_writer_write_bytes(tmp_path):
    root = tmp_path / "root"
    writer = HostDirWriter(root)
    writer.write_bytes(root / "s" / "startup-sequence", b"cd Project:\n")
    assert (root / "s" / "startup-sequence").read_bytes() == b"cd Project:\n"


def test_adfvolume_writer_roundtrip(tmp_path):
    image = tmp_path / "test.adf"
    writer = ADFVolumeWriter(image, "Project")

    src = tmp_path / "Level1"
    src.write_bytes(b"level data")
    writer.write(ResolvedCopyItem(source=src, dest=Path("/levels/Level1")))
    writer.write_bytes(Path("/s/startup-sequence"), b"cd Project:\n")
    writer.finalize()

    assert image.exists()

    # read back via the same amitools classes to confirm real content
    from amitools.fs.ADFSVolume import ADFSVolume
    from amitools.fs.blkdev.BlkDevFactory import BlkDevFactory
    from amitools.fs.FSString import FSString

    blkdev = BlkDevFactory().open(str(image), read_only=True)
    vol = ADFSVolume(blkdev)
    vol.open()
    assert vol.read_file(FSString("levels/Level1")) == b"level data"
    assert vol.read_file(FSString("s/startup-sequence")) == b"cd Project:\n"
    vol.close()
    blkdev.close()
