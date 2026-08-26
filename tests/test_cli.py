import logging
from pathlib import Path

import pytest

from amigarig.cli import main, relativize_binary
from amigarig.copyspec import CopyError
from amigarig.log import logger

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "configs"


def test_amigarig_error_prints_clean_message_not_traceback(monkeypatch, tmp_path, log_messages):
    monkeypatch.chdir(tmp_path)

    def fake_run(*a, **k):
        raise CopyError("copy.c: source 'utils:fix3d' does not exist (resolved to '/x')")

    monkeypatch.setattr("amigarig.cli.run", fake_run)

    result = main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert result == 1
    out = "\n".join(log_messages)
    assert "Traceback" not in out
    assert "error:" in out
    assert "utils:fix3d" in out


def test_non_amigarig_errors_still_raise(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_run(*a, **k):
        raise ValueError("some unrelated bug")

    monkeypatch.setattr("amigarig.cli.run", fake_run)

    with pytest.raises(ValueError):
        main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])


def test_verbosity_defaults_to_warning_when_unset(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("amigarig.cli.run", lambda *a, **k: 0)

    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert logger.getEffectiveLevel() == logging.WARNING


def test_single_v_flag_raises_to_info(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("amigarig.cli.run", lambda *a, **k: 0)

    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR), "-v"])

    assert logger.getEffectiveLevel() == logging.INFO


def test_double_v_flag_raises_to_debug(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("amigarig.cli.run", lambda *a, **k: 0)

    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR), "-vv"])

    assert logger.getEffectiveLevel() == logging.DEBUG


def test_verbose_true_from_project_local_config_means_info(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".amigarig.yaml").write_text("verbose: true\n")
    monkeypatch.setattr("amigarig.cli.run", lambda *a, **k: 0)

    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert logger.getEffectiveLevel() == logging.INFO


def test_verbose_2_from_config_means_debug(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".amigarig.yaml").write_text("verbose: 2\n")
    monkeypatch.setattr("amigarig.cli.run", lambda *a, **k: 0)

    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert logger.getEffectiveLevel() == logging.DEBUG


def test_relativize_binary_relative_path_passed_through(tmp_path):
    assert relativize_binary("game", tmp_path / "build") == "game"


def test_relativize_binary_absolute_path_under_project_dir(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    assert relativize_binary(str(build / "game"), build) == "game"


def test_relativize_binary_absolute_path_outside_project_dir_raises(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    elsewhere = tmp_path / "elsewhere" / "game"
    with pytest.raises(SystemExit):
        relativize_binary(str(elsewhere), build)


def test_project_dir_flag_passed_through_to_run(monkeypatch, tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_run(*a, project_dir, **k):
        seen["project_dir"] = project_dir
        return 0

    monkeypatch.setattr("amigarig.cli.run", fake_run)
    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR), "--project-dir", "build"])

    assert seen["project_dir"] == build.resolve()


def test_project_dir_defaults_to_cwd_when_unset(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_run(*a, project_dir, **k):
        seen["project_dir"] = project_dir
        return 0

    monkeypatch.setattr("amigarig.cli.run", fake_run)
    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert seen["project_dir"] == tmp_path


def test_project_dir_flag_takes_priority_over_config(monkeypatch, tmp_path):
    (tmp_path / "from-flag").mkdir()
    (tmp_path / "from-config").mkdir()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".amigarig.yaml").write_text("project:\n  dir: from-config\n")
    seen = {}

    def fake_run(*a, project_dir, **k):
        seen["project_dir"] = project_dir
        return 0

    monkeypatch.setattr("amigarig.cli.run", fake_run)
    main(
        ["--config", "a500", "--configs-dir", str(CONFIGS_DIR), "--project-dir", "from-flag"]
    )

    assert seen["project_dir"] == (tmp_path / "from-flag").resolve()


def test_cli_v_and_config_verbose_combine_as_max(monkeypatch, tmp_path):
    """-v (count 1) with config verbose: 2 ends up at the higher of the
    two (DEBUG), never lower -- the CLI flag only ever raises verbosity."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".amigarig.yaml").write_text("verbose: 2\n")
    monkeypatch.setattr("amigarig.cli.run", lambda *a, **k: 0)

    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR), "-v"])

    assert logger.getEffectiveLevel() == logging.DEBUG
