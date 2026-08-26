import pytest

from amigarig.startup import (
    DEFAULT_PRIORITY,
    normalize_startup_item,
    render_startup_sequence,
    resolve_startup_lines,
    write_startup_sequence,
)


def test_normalize_bare_string_uses_default_priority():
    assert normalize_startup_item("cd Project:") == (["cd Project:"], DEFAULT_PRIORITY)


def test_normalize_mapping_with_scalar_text():
    assert normalize_startup_item({"text": "NoBorder", "priority": 10}) == (["NoBorder"], 10)


def test_normalize_mapping_missing_priority_defaults():
    assert normalize_startup_item({"text": "NoBorder"}) == (["NoBorder"], DEFAULT_PRIORITY)


def test_normalize_mapping_with_block_text():
    lines, priority = normalize_startup_item(
        {"text": ["Assign ENV: ENVARC:", "Assign T: RAM:T"], "priority": 20}
    )
    assert lines == ["Assign ENV: ENVARC:", "Assign T: RAM:T"]
    assert priority == 20


def test_normalize_rejects_nested_non_string_in_block():
    with pytest.raises(TypeError):
        normalize_startup_item({"text": ["ok", ["nested", "list"]]})


def test_normalize_rejects_bad_text_type():
    with pytest.raises(TypeError):
        normalize_startup_item({"text": 42})


def test_normalize_rejects_non_string_non_mapping():
    with pytest.raises(TypeError):
        normalize_startup_item(123)


def test_resolve_sorts_by_priority():
    items = [
        {"text": "late", "priority": 90},
        "default",
        {"text": "early", "priority": 10},
    ]
    assert resolve_startup_lines(items) == ["early", "default", "late"]


def test_resolve_is_stable_for_equal_priority():
    items = ["cd Project:", "NoBorder", {"text": "{binary} {args}", "priority": DEFAULT_PRIORITY}]
    assert resolve_startup_lines(items) == ["cd Project:", "NoBorder", "{binary} {args}"]


def test_resolve_matches_legacy_bare_string_list():
    items = ["cd Project:", "{binary} {args}"]
    assert resolve_startup_lines(items) == items


def test_resolve_expands_blocks_in_priority_order():
    items = [
        {"text": ["a", "b"], "priority": 10},
        {"text": "z", "priority": 90},
    ]
    assert resolve_startup_lines(items) == ["a", "b", "z"]


class FakeWriter:
    def __init__(self):
        self.writes = {}

    def write_bytes(self, path, content):
        self.writes[path] = content


class FakeTarget:
    def __init__(self, root_path):
        self.root_path = root_path
        self.writer = FakeWriter()


def test_write_startup_sequence_renders_priority_ordered_content(tmp_path):
    target = FakeTarget(tmp_path)
    items = [
        {"text": "{{ binary }} {{ args }}", "priority": 90},
        "cd Project:",
        {"text": "NoBorder"},
    ]

    write_startup_sequence(target, items, "bin/game", ["-x"])

    written = target.writer.writes[tmp_path / "s" / "startup-sequence"]
    assert written.decode() == "cd Project:\nNoBorder\nbin/game -x\n"


def test_write_startup_sequence_noop_when_empty(tmp_path):
    target = FakeTarget(tmp_path)
    write_startup_sequence(target, [], "bin/game", [])
    assert target.writer.writes == {}


def test_render_startup_sequence_unchanged_shape():
    content = render_startup_sequence(["cd Project:", "{{ binary }} {{ args }}"], "bin/game", ["a b"])
    assert content == "cd Project:\nbin/game 'a b'\n"


def test_render_startup_sequence_argsarr_is_raw_unjoined_list():
    content = render_startup_sequence(
        ["{{ argsarr | join(',') }}"], "bin/game", ["a b", "c"]
    )
    assert content == "a b,c\n"


def test_render_startup_sequence_amigaquote_filter():
    content = render_startup_sequence(
        ['{{ argsarr | map("amigaquote") | join(" ") }}'], "bin/game", ['has space', 'has"quote']
    )
    assert content == '"has space" "has*"quote"\n'


def test_render_startup_sequence_config_and_assign_available():
    from amigarig.assigns import AssignTable

    content = render_startup_sequence(
        ["{{ config.fsuae.cpu }} {{ assign('wb:') }}"],
        "bin/game",
        [],
        config={"fsuae": {"cpu": "68030"}},
        assigns=AssignTable({"wb": "/opt/workbench"}),
    )
    assert content == "68030 /opt/workbench\n"
