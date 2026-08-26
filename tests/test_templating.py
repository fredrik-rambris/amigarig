from amigarig.assigns import AssignTable
from amigarig.templating import build_environment, render_env


def test_render_env_expands_config_lookup():
    result = render_env(
        {"CPU": "{{ config.fsuae.cpu }}"}, config={"fsuae": {"cpu": "68030"}}, assigns=AssignTable()
    )
    assert result == {"CPU": "68030"}


def test_render_env_assign_global_expands_assign():
    assigns = AssignTable({"wb": "/opt/workbench"})
    result = render_env({"WB": "{{ assign('wb:') }}"}, config={}, assigns=assigns)
    assert result == {"WB": "/opt/workbench"}


def test_render_env_leaves_plain_values_untouched():
    result = render_env({"FOO": "bar"}, config={}, assigns=AssignTable())
    assert result == {"FOO": "bar"}


def test_render_env_empty_dict():
    assert render_env({}, config={}, assigns=AssignTable()) == {}


def _render(template: str, **context) -> str:
    return build_environment(AssignTable()).from_string(template).render(**context)


def test_stem_filter_strips_extension():
    assert _render("{{ binary | stem }}", binary="something.Asc") == "something"


def test_stem_filter_drops_directory_prefix():
    assert _render("{{ binary | stem }}", binary="bin/game.Asc") == "game"


def test_stem_filter_no_extension_unchanged():
    assert _render("{{ binary | stem }}", binary="something") == "something"


def test_stem_filter_only_strips_last_suffix():
    assert _render("{{ binary | stem }}", binary="a.tar.gz") == "a.tar"


def test_suffix_filter_returns_extension_with_dot():
    assert _render("{{ binary | suffix }}", binary="something.Asc") == ".Asc"


def test_suffix_filter_no_extension_is_empty():
    assert _render("{{ binary | suffix }}", binary="something") == ""
