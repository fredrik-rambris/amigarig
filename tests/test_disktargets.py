from amigarig.assigns import AssignTable
from amigarig.disktargets import Target, run_copy
from amigarig.writers.hostdir import HostDirWriter


def _make_boot_target(tmp_path):
    boot_dir = tmp_path / "boot"
    return Target("boot", "mounted_dir", boot_dir, HostDirWriter(boot_dir), True, True)


def test_run_copy_verbose_prints_source_and_dest(tmp_path, capsys):
    wb = tmp_path / "wb"
    (wb / "c").mkdir(parents=True)
    (wb / "c" / "Copy").write_text("bin")

    assigns = AssignTable({"wb": str(wb), "boot": str(tmp_path / "boot")})
    targets = {"boot": _make_boot_target(tmp_path)}
    copy_types = {"c": {"src": "wb:c", "dest": "boot:c"}}

    run_copy({"c": ["Copy"]}, copy_types, targets, assigns, verbose=True)

    out = capsys.readouterr().out
    assert str(wb / "c" / "Copy") in out
    assert "boot" in out


def test_run_copy_not_verbose_prints_nothing(tmp_path, capsys):
    wb = tmp_path / "wb"
    (wb / "c").mkdir(parents=True)
    (wb / "c" / "Copy").write_text("bin")

    assigns = AssignTable({"wb": str(wb), "boot": str(tmp_path / "boot")})
    targets = {"boot": _make_boot_target(tmp_path)}
    copy_types = {"c": {"src": "wb:c", "dest": "boot:c"}}

    run_copy({"c": ["Copy"]}, copy_types, targets, assigns)

    assert capsys.readouterr().out == ""
