from amigarig.fsutil import CaseInsensitiveResolver


def test_resolves_exact_case(tmp_path):
    (tmp_path / "C").mkdir()
    (tmp_path / "C" / "Copy").write_text("copy binary")
    ci = CaseInsensitiveResolver()
    resolved = ci.resolve(tmp_path, "C/Copy")
    assert resolved == tmp_path / "C" / "Copy"


def test_resolves_different_case(tmp_path):
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "copy").write_text("copy binary")
    ci = CaseInsensitiveResolver()
    resolved = ci.resolve(tmp_path, "C/Copy")
    assert resolved == tmp_path / "c" / "copy"


def test_missing_returns_none(tmp_path):
    ci = CaseInsensitiveResolver()
    assert ci.resolve(tmp_path, "Nope") is None


def test_exists_helper(tmp_path):
    (tmp_path / "Fonts").mkdir()
    (tmp_path / "Fonts" / "Garamond.font").write_text("x")
    ci = CaseInsensitiveResolver()
    assert ci.exists(tmp_path, "fonts/garamond.font")
    assert not ci.exists(tmp_path, "fonts/missing.font")
