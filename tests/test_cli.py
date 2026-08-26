from pathlib import Path

import pytest

from amigarig.cli import main
from amigarig.copyspec import CopyError

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "configs"


def test_amigarig_error_prints_clean_message_not_traceback(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def fake_run(*a, **k):
        raise CopyError("copy.c: source 'utils:fix3d' does not exist (resolved to '/x')")

    monkeypatch.setattr("amigarig.cli.run", fake_run)

    result = main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert result == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "amigarig: error:" in captured.err
    assert "utils:fix3d" in captured.err


def test_non_amigarig_errors_still_raise(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def fake_run(*a, **k):
        raise ValueError("some unrelated bug")

    monkeypatch.setattr("amigarig.cli.run", fake_run)

    with pytest.raises(ValueError):
        main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])


def test_verbose_defaults_false_when_unset(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_run(*a, verbose, **k):
        seen["verbose"] = verbose
        return 0

    monkeypatch.setattr("amigarig.cli.run", fake_run)
    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert seen["verbose"] is False


def test_verbose_flag_forces_true(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_run(*a, verbose, **k):
        seen["verbose"] = verbose
        return 0

    monkeypatch.setattr("amigarig.cli.run", fake_run)
    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR), "-v"])

    assert seen["verbose"] is True


def test_verbose_true_from_project_local_config(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".amigarig.yaml").write_text("verbose: true\n")
    seen = {}

    def fake_run(*a, verbose, **k):
        seen["verbose"] = verbose
        return 0

    monkeypatch.setattr("amigarig.cli.run", fake_run)
    main(["--config", "a500", "--configs-dir", str(CONFIGS_DIR)])

    assert seen["verbose"] is True
