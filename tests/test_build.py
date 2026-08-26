from amigarig.config.build import Registries, assemble


def _write(directory, name, content):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yaml").write_text(content)


def test_plus_key_in_a_no_extends_leaf_still_appends_across_categories(tmp_path):
    """Regression: a workbench (or boot) config with no `extends:` of its
    own used to have its `+key` resolved in isolation by resolve_chain,
    silently losing the append and letting a later category's plain list
    replace it wholesale instead of extending it -- see the wb31.yaml /
    minimal.yaml case this was reported against."""
    _write(tmp_path / "machine", "m", "workbench: wb\n")
    _write(tmp_path / "kickstart", "unused", "{}\n")
    _write(tmp_path / "workbench", "wb", "copy:\n  c: [Assign, Copy]\n")
    _write(tmp_path / "boot", "minimal", "copy:\n  +c: [utils:UAEQuit]\n")
    _write(tmp_path / "run", "unused", "{}\n")

    registries = Registries(tmp_path)
    merged = assemble(registries, "m")

    assert merged["copy"]["c"] == ["Assign", "Copy", "utils:UAEQuit"]


def test_plus_key_still_appends_within_a_single_extends_chain(tmp_path):
    _write(tmp_path / "machine", "m", "workbench: wb\n")
    _write(tmp_path / "kickstart", "unused", "{}\n")
    _write(
        tmp_path / "workbench",
        "wbbase",
        "copy:\n  c: [Assign]\n",
    )
    _write(tmp_path / "workbench", "wb", "extends: wbbase\ncopy:\n  +c: [Copy]\n")
    _write(tmp_path / "boot", "minimal", "{}\n")
    _write(tmp_path / "run", "unused", "{}\n")

    registries = Registries(tmp_path)
    merged = assemble(registries, "m")

    assert merged["copy"]["c"] == ["Assign", "Copy"]


def test_run_profile_extends_chain_also_flattened(tmp_path):
    """A `run:` profile's own extends chain (and any +key it carries) must
    also survive into the final merge, not just machine/workbench/boot.
    base_run's `copy.c` is a *plain* key, so per the normal list+list =
    replace rule it replaces machine's [Assign] rather than appending to
    it; dev's `+c` then appends on top of that."""
    _write(tmp_path / "machine", "m", "copy:\n  c: [Assign]\n")
    _write(tmp_path / "kickstart", "unused", "{}\n")
    _write(tmp_path / "workbench", "unused", "{}\n")
    _write(tmp_path / "boot", "minimal", "{}\n")
    _write(tmp_path / "run", "base_run", "copy:\n  c: [FromBaseRun]\n")
    _write(
        tmp_path / "run",
        "dev",
        "extends: base_run\nmachine: m\ncopy:\n  +c: [FromDev]\n",
    )

    registries = Registries(tmp_path)
    merged = assemble(registries, "dev")

    assert merged["copy"]["c"] == ["FromBaseRun", "FromDev"]
