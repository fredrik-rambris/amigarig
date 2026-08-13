from amigarig.assigns import AssignTable
from amigarig.fsuae import resolve_fsuae_paths, build_argv
from amigarig.disktargets import Target
from pathlib import Path


def test_resolve_fsuae_paths_leaves_non_path_values_alone(tmp_path):
    assigns = AssignTable({})
    opts = {"serial_port": "tcp://127.0.0.1:1234", "amiga_model": "A1200"}
    resolved = resolve_fsuae_paths(opts, assigns)
    assert resolved == opts


def test_resolve_fsuae_paths_resolves_kickstart_file(tmp_path):
    kickstart_dir = tmp_path / "kickstart"
    kickstart_dir.mkdir()
    (kickstart_dir / "kick31.rom").write_text("rom")

    assigns = AssignTable({"kickstart": str(kickstart_dir)})
    opts = {"kickstart_file": "kickstart:kick31.rom"}
    resolved = resolve_fsuae_paths(opts, assigns)
    assert resolved["kickstart_file"] == str(kickstart_dir / "kick31.rom")


def test_build_argv_includes_resolved_flags():
    boot = Target("boot", "mounted_dir", Path("/tmp/boot"), None, False, True)
    argv = build_argv("/usr/bin/fs-uae", {"kickstart_file": "/x/kick31.rom"}, boot, None)
    assert "--kickstart_file=/x/kick31.rom" in argv
    assert "--hard_drive_0=/tmp/boot" in argv
