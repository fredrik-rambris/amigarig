import os

from amigarig.runner import run


def test_rig_only_mode_builds_and_keeps_target_without_launching(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def fail_if_called(*a, **k):
        raise AssertionError("backend should not be invoked in rig-only mode")

    monkeypatch.setattr("amigarig.runner.get_backend", lambda name: fail_if_called)

    keep_dir = tmp_path / "artifact"
    merged_config = {
        "boot": {"type": "harddrive", "keep_as": str(keep_dir)},
        "project": {"type": "harddrive"},
    }

    result = run(merged_config, "/usr/bin/fs-uae", None, [])

    assert result == 0
    assert keep_dir.is_dir()
    # no startup-sequence should have been generated in rig-only mode
    assert not (keep_dir / "s" / "startup-sequence").exists()


def test_project_dir_overrides_cwd_for_project_mount(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    calls = []
    monkeypatch.setattr(
        "amigarig.runner.get_backend",
        lambda name: calls.append(name) or (lambda ctx: ctx.assigns.resolve("project:")),
    )

    keep_dir = tmp_path / "artifact"
    merged_config = {
        "boot": {"type": "harddrive", "keep_as": str(keep_dir)},
        "project": {"type": "harddrive"},
        "startup": ["cd Project:"],
    }

    result = run(
        merged_config, "/usr/bin/fs-uae", "game", [], project_dir=build_dir
    )

    assert result == build_dir


def test_project_dir_defaults_to_cwd_when_not_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "amigarig.runner.get_backend",
        lambda name: (lambda ctx: ctx.assigns.resolve("project:")),
    )

    keep_dir = tmp_path / "artifact"
    merged_config = {
        "boot": {"type": "harddrive", "keep_as": str(keep_dir)},
        "project": {"type": "harddrive"},
        "startup": ["cd Project:"],
    }

    result = run(merged_config, "/usr/bin/fs-uae", "game", [])

    assert result == tmp_path


def test_backend_dispatch_uses_configured_backend_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(
        "amigarig.runner.get_backend",
        lambda name: calls.append(name) or (lambda ctx: 0),
    )

    keep_dir = tmp_path / "artifact"
    merged_config = {
        "backend": "vamos",
        "boot": {"type": "harddrive", "keep_as": str(keep_dir)},
        "project": {"type": "harddrive"},
        "startup": ["cd Project:", "{{ binary }} {{ args }}"],
    }

    result = run(merged_config, "/usr/bin/fs-uae", "bin/game", [])

    assert result == 0
    assert calls == ["vamos"]


def test_exec_stages_run_init_then_before_then_after_around_backend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    order = []
    monkeypatch.setattr(
        "amigarig.runner.get_backend",
        lambda name: (lambda ctx: order.append("backend") or 0),
    )

    log = tmp_path / "log.txt"
    keep_dir = tmp_path / "artifact"
    merged_config = {
        "boot": {"type": "harddrive", "keep_as": str(keep_dir)},
        "project": {"type": "harddrive"},
        "startup": ["cd Project:", "{{ binary }} {{ args }}"],
        "exec": [
            {"stage": "after", "cmd": f"echo after >> {log}"},
            {"stage": "before", "cmd": f"echo before >> {log}"},
            {"stage": "init", "cmd": f"echo init >> {log}"},
        ],
    }

    result = run(merged_config, "/usr/bin/fs-uae", "bin/game", [])

    assert result == 0
    assert log.read_text().splitlines() == ["init", "before", "after"]
