from pathlib import Path

from amigarig.assigns import AssignTable
from amigarig.copyspec import normalize_copy_item, resolve_copy_item
from amigarig.fsutil import CaseInsensitiveResolver


def test_normalize_bare_string():
    assert normalize_copy_item("Copy") == ("Copy", "Copy")


def test_normalize_mapping_defaults_destination_to_source_basename():
    assert normalize_copy_item({"source": "a/b"}) == ("a/b", "b")
    assert normalize_copy_item({"source": "project:build/libs/music.library"}) == (
        "project:build/libs/music.library",
        "music.library",
    )


def test_normalize_mapping_explicit_destination():
    assert normalize_copy_item({"source": "a", "destination": "b"}) == ("a", "b")


def test_normalize_bare_qualified_string_defaults_dest_to_basename():
    # regression: "amiga:system-configuration" used to become both source
    # AND destination verbatim, sending the item to whatever target the
    # "amiga:" prefix names instead of the copy type's normal boot:/project:
    # destination.
    assert normalize_copy_item("amiga:system-configuration") == (
        "amiga:system-configuration",
        "system-configuration",
    )
    assert normalize_copy_item("/abs/path/file.rom") == (
        "/abs/path/file.rom",
        "file.rom",
    )


def test_resolve_bare_item_against_type_defaults(tmp_path):
    wb = tmp_path / "wb31"
    (wb / "c").mkdir(parents=True)
    (wb / "c" / "copy").write_text("bin")
    boot = tmp_path / "boot"

    assigns = AssignTable({"wb": str(wb), "boot": str(boot)})
    ci = CaseInsensitiveResolver()

    item = resolve_copy_item("Copy", "wb:c", "boot:c", assigns, ci)
    assert item.source == wb / "c" / "copy"
    assert item.dest == boot / "c" / "Copy"


def test_resolve_item_with_independent_source_assign(tmp_path):
    project = tmp_path / "project"
    (project / "build" / "libs").mkdir(parents=True)
    (project / "build" / "libs" / "music.library").write_text("bin")
    boot = tmp_path / "boot"

    assigns = AssignTable({"project": str(project), "boot": str(boot)})
    ci = CaseInsensitiveResolver()

    item = resolve_copy_item(
        {"source": "project:build/libs/music.library"},
        "wb:libs",
        "boot:libs",
        assigns,
        ci,
    )
    assert item.source == project / "build" / "libs" / "music.library"
    assert item.dest == boot / "libs" / "music.library"
