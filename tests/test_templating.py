from amigarig.assigns import AssignTable
from amigarig.templating import render_env


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
