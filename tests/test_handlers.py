from amigarig.copyspec import ResolvedCopyItem
from amigarig.fsutil import CaseInsensitiveResolver
from amigarig.handlers import HandlerContext, copy_font, copy_icons, run_handlers


def test_copy_font_adds_sibling_font_file(tmp_path):
    fonts = tmp_path / "Fonts"
    (fonts / "Garamond").mkdir(parents=True)
    (fonts / "Garamond" / "9").write_text("bitmap")
    (fonts / "Garamond.font").write_text("header")

    dest_root = tmp_path / "boot" / "fonts"
    item = ResolvedCopyItem(
        source=fonts / "Garamond" / "9", dest=dest_root / "Garamond" / "9"
    )
    ctx = HandlerContext(ci=CaseInsensitiveResolver())
    results = copy_font(item, ctx)

    assert len(results) == 2
    assert results[0] == item
    assert results[1].source == fonts / "Garamond.font"
    assert results[1].dest == dest_root / "Garamond.font"


def test_copy_icons_adds_info_file_when_present(tmp_path):
    build = tmp_path / "build" / "bin"
    build.mkdir(parents=True)
    (build / "MyGame.exe").write_text("bin")
    (build / "MyGame.exe.info").write_text("icon")

    item = ResolvedCopyItem(source=build / "MyGame.exe", dest=tmp_path / "boot" / "MyGame")
    ctx = HandlerContext(ci=CaseInsensitiveResolver())
    results = copy_icons(item, ctx)

    assert len(results) == 2
    assert results[1].source == build / "MyGame.exe.info"
    assert results[1].dest == tmp_path / "boot" / "MyGame.info"


def test_copy_icons_no_icon_present(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "MyGame.exe").write_text("bin")

    item = ResolvedCopyItem(source=build / "MyGame.exe", dest=tmp_path / "boot" / "MyGame")
    ctx = HandlerContext(ci=CaseInsensitiveResolver())
    results = copy_icons(item, ctx)

    assert results == [item]


def test_run_handlers_chains_in_order(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    (build / "MyGame.exe").write_text("bin")
    (build / "MyGame.exe.info").write_text("icon")

    item = ResolvedCopyItem(source=build / "MyGame.exe", dest=tmp_path / "boot" / "MyGame")
    ctx = HandlerContext(ci=CaseInsensitiveResolver())
    results = run_handlers(item, ["copy", "copy_icons"], ctx)
    assert len(results) == 2
