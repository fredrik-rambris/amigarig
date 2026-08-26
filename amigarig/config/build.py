"""Top-level assembler: turns --config=<name> + overrides into one merged config.

Registries:
  - "profile"  = machine/*.yaml UNION kickstart/*.yaml -- these freely
    `extends:` each other (e.g. a1200 extends [aga, kickstart-30]).
  - "workbench" = workbench/*.yaml, its own extends chain, selected via the
    `workbench:` reference field (set by a kickstart profile, overridable).
  - "boot"     = boot/*.yaml, its own extends chain, selected by name.
  - "run"      = optional named presets tying machine/workbench/boot together.
"""
from __future__ import annotations

from pathlib import Path

from .merge import merge_chain
from .registry import Registry
from .resolve import flatten_chain, resolve_chain

# env var name -> dotted merged-config key
ENV_VAR_MAP = {
    "AMIGA_MODEL": "machine",
    "AMIGA_WORKBENCH": "workbench",
    # NOTE: kickstart is normally selected via the machine profile's own
    # `extends:` chain (e.g. a1200 extends [aga, kickstart-30]); this env var
    # is accepted but not yet wired to override that choice independently --
    # override `machine` (a full profile name) or edit configs for now.
    "AMIGA_KICKSTART": "kickstart",
    "AMIGA_FASTRAM": "fsuae.fast_memory",
    "AMIGA_CHIPRAM": "fsuae.chip_memory",
    "AMIGA_SLOWRAM": "fsuae.slow_memory",
}


class Registries:
    def __init__(self, configs_dir: Path):
        configs_dir = Path(configs_dir)
        self.profile = Registry.union(configs_dir / "machine", configs_dir / "kickstart")
        self.workbench = Registry(configs_dir / "workbench")
        self.boot = Registry(configs_dir / "boot")
        self.run = Registry(configs_dir / "run")


def _set_dotted(d: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    cur = d
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def env_overrides(env: dict) -> dict:
    overrides: dict = {}
    for var, dotted_key in ENV_VAR_MAP.items():
        if var in env:
            _set_dotted(overrides, dotted_key, env[var])
    return overrides


_SELECTOR_KEYS = ("machine", "workbench", "boot")


def _without_selector_keys(layer: dict) -> dict:
    return {k: v for k, v in layer.items() if k not in _SELECTOR_KEYS}


def assemble(
    registries: Registries,
    config_name: str,
    local_layer: dict | None = None,
    project_local: dict | None = None,
    env_layer: dict | None = None,
    cli_overrides: dict | None = None,
) -> dict:
    if config_name in registries.run:
        run_layers = flatten_chain(registries.run, config_name)
    else:
        run_layers = [{"machine": config_name}]
    run_profile = merge_chain(run_layers)  # merged only to peek at machine/workbench/boot below

    # env/cli can redirect which machine/workbench/boot profile to use, so
    # peek at them before resolving those chains
    early = merge_chain([env_layer or {}, cli_overrides or {}])

    machine_name = early.get("machine", run_profile.get("machine"))
    machine_layers = flatten_chain(registries.profile, machine_name) if machine_name else []
    machine_cfg = merge_chain(machine_layers)  # merged only to peek at `workbench:` below

    workbench_name = early.get(
        "workbench", run_profile.get("workbench", machine_cfg.get("workbench"))
    )
    workbench_layers = (
        flatten_chain(registries.workbench, workbench_name) if workbench_name else []
    )

    boot_name = early.get("boot", run_profile.get("boot", "minimal"))
    boot_layers = (
        flatten_chain(registries.boot, boot_name) if boot_name in registries.boot else []
    )

    # every category's raw, unmerged per-file layers are folded into one
    # flat, whole-config merge below -- NOT pre-merged per category first
    # (see resolve.py's flatten_chain docstring) -- so a "+key"/"^key" in
    # any file can append against whatever an earlier layer in *any*
    # category already contributed, not just its own extends chain.
    layers = [
        # machine-local facts (paths to your FS-UAE install, ROMs, Workbench
        # trees) come first -- lowest priority, so any profile can still
        # override an assign if it really needs to, but normally this is the
        # only place paths specific to *your* machine ever get written.
        local_layer or {},
        *machine_layers,
        *workbench_layers,
        *boot_layers,
        *(_without_selector_keys(layer) for layer in run_layers),
        project_local or {},
        env_layer or {},
        cli_overrides or {},
    ]
    return merge_chain(layers)
