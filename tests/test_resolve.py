import pytest

from amigarig.config.registry import Registry
from amigarig.config.resolve import resolve_chain


def make_registry(tmp_path, files: dict[str, str]):
    for name, content in files.items():
        (tmp_path / f"{name}.yaml").write_text(content)
    return Registry(tmp_path)


def test_single_inheritance(tmp_path):
    reg = make_registry(
        tmp_path,
        {
            "base": "fsuae:\n  accuracy: 1\n",
            "child": "extends: base\nfsuae:\n  cpu: 68020\n",
        },
    )
    result = resolve_chain(reg, "child")
    assert result == {"fsuae": {"accuracy": 1, "cpu": 68020}}


def test_multiple_inheritance_order(tmp_path):
    reg = make_registry(
        tmp_path,
        {
            "a": "fsuae:\n  chipset: aga\n",
            "b": "fsuae:\n  kickstart_file: kick31.rom\n",
            "child": "extends: [a, b]\nfsuae:\n  cpu: 68030\n",
        },
    )
    result = resolve_chain(reg, "child")
    assert result == {
        "fsuae": {"chipset": "aga", "kickstart_file": "kick31.rom", "cpu": 68030}
    }


def test_cycle_detection(tmp_path):
    reg = make_registry(
        tmp_path,
        {
            "a": "extends: b\n",
            "b": "extends: a\n",
        },
    )
    with pytest.raises(ValueError, match="cycle"):
        resolve_chain(reg, "a")
