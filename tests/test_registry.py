import pytest

from amigarig.config.registry import ConfigLoadError, Registry, load_yaml_file


def test_load_yaml_file_missing_returns_content(tmp_path):
    path = tmp_path / "ok.yaml"
    path.write_text("fsuae:\n  cpu: 68030\n")
    assert load_yaml_file(path) == {"fsuae": {"cpu": 68030}}


def test_load_yaml_file_empty_returns_empty_dict(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("")
    assert load_yaml_file(path) == {}


def test_load_yaml_file_bad_syntax_raises_config_load_error(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("startup:\n  - priority: 10\n   - bad indent\n")

    with pytest.raises(ConfigLoadError, match="broken.yaml"):
        load_yaml_file(path)


def test_load_yaml_file_non_mapping_top_level_raises(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n")

    with pytest.raises(ConfigLoadError, match="mapping"):
        load_yaml_file(path)


def test_registry_raises_config_load_error_for_bad_file_in_directory(tmp_path):
    (tmp_path / "broken.yaml").write_text("a: [1, 2\n")

    with pytest.raises(ConfigLoadError):
        Registry(tmp_path)
