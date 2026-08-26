from pathlib import Path

import pytest

from amigarig.assigns import AssignTable
from amigarig.backends import RunContext
from amigarig.backends import vamos as vamos_backend
from amigarig.disktargets import Target


def _ctx(tmp_path, **overrides):
    boot_dir = tmp_path / "boot"
    boot_dir.mkdir(exist_ok=True)
    assigns = AssignTable({"boot": str(boot_dir)})
    boot = Target("boot", "mounted_dir", boot_dir, None, False, True)
    defaults = dict(
        merged_config={},
        assigns=assigns,
        boot=boot,
        project=None,
        fsuae_binary="/usr/bin/fs-uae",
        binary="bin/game",
        args=["-x"],
    )
    defaults.update(overrides)
    return RunContext(**defaults)


def test_run_calls_vamos_main_with_expected_binary_and_args(tmp_path, monkeypatch):
    captured = {}

    def fake_main(cfg_dict=None, args=None):
        captured["cfg_dict"] = cfg_dict
        captured["args"] = args
        return 0

    monkeypatch.setattr("amitools.vamos.main.main", fake_main)

    ctx = _ctx(tmp_path)
    result = vamos_backend.run(ctx)

    assert result == 0
    # binary/args go via vamos' own CLI-style args (its argparser requires
    # "bin" positionally), not cfg_dict -- passing args=[] there always
    # fails with "the following arguments are required: bin".
    assert captured["args"] == ["project:bin/game", "-x"]
    assert "process" not in captured["cfg_dict"]


def test_run_maps_directory_assigns_to_volumes(tmp_path, monkeypatch):
    captured = {}

    def fake_main(cfg_dict=None, args=None):
        captured["cfg_dict"] = cfg_dict
        return 0

    monkeypatch.setattr("amitools.vamos.main.main", fake_main)

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    boot_dir = tmp_path / "boot"
    boot_dir.mkdir(exist_ok=True)
    assigns = AssignTable({"boot": str(boot_dir), "project": str(project_dir)})
    boot = Target("boot", "mounted_dir", boot_dir, None, False, True)
    project = Target("project", "mounted_dir", project_dir, None, True, True)

    ctx = _ctx(tmp_path, assigns=assigns, boot=boot, project=project)
    vamos_backend.run(ctx)

    volumes = captured["cfg_dict"]["volumes"]
    assert f"boot:{boot_dir}" in volumes
    assert f"project:{project_dir}" in volumes


def test_run_skips_image_assigns_with_a_warning(tmp_path, monkeypatch, log_messages):
    monkeypatch.setattr("amitools.vamos.main.main", lambda cfg_dict=None, args=None: 0)

    boot_dir = tmp_path / "boot"
    boot_dir.mkdir(exist_ok=True)
    assigns = AssignTable({"boot": str(boot_dir), "project": "/"})
    boot = Target("boot", "mounted_dir", boot_dir, None, False, True)
    project = Target("project", "image", tmp_path / "project.adf", None, True, True)

    ctx = _ctx(tmp_path, assigns=assigns, boot=boot, project=project)
    vamos_backend.run(ctx)

    out = "\n".join(log_messages)
    assert "project:" in out
    assert "not a directory" in out or "image" in out


def test_run_rejects_image_boot_target(tmp_path):
    boot = Target("boot", "image", tmp_path / "boot.adf", None, True, True)
    ctx = _ctx(tmp_path, boot=boot)
    with pytest.raises(ValueError, match="harddrive"):
        vamos_backend.run(ctx)
