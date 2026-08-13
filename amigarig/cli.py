from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import platformdirs
import yaml

from .config.build import Registries, assemble, env_overrides, _set_dotted
from .runner import run

# Standard per-user config location (~/.config/amigarig on Linux, the
# platform-correct equivalent elsewhere). This directory itself holds
# local.yaml plus the machine/kickstart/workbench/boot/run/ subdirectories --
# i.e. it *is* the configs dir, not a sibling of it. Override with
# AMIGARIG_CONFIG_DIR or --configs-dir (e.g. to point at this repo's
# checked-in configs/ during development).
DEFAULT_CONFIGS_DIR = os.environ.get(
    "AMIGARIG_CONFIG_DIR", platformdirs.user_config_dir("amigarig")
)
PROJECT_LOCAL_FILENAME = ".amigarig.yaml"
LOCAL_CONFIG_FILENAME = "local.yaml"


def parse_set_flags(pairs: list[str]) -> dict:
    overrides: dict = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--set expects key=value, got '{pair}'")
        _set_dotted(overrides, key, yaml.safe_load(value))
    return overrides


def load_yaml_if_present(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def load_project_local(cwd: Path) -> dict:
    return load_yaml_if_present(cwd / PROJECT_LOCAL_FILENAME)


def relativize_binary(binary: str, cwd: Path) -> str:
    """Strip cwd from an absolute binary path so it lands correctly under
    "cd Project:" in the startup-sequence. Amiga side only ever sees cwd
    mounted as project:, so an absolute host path is meaningless there --
    e.g. run from /data/Coding/acbmtoilbm, "/data/Coding/acbmtoilbm/bin/x"
    becomes "bin/x". Paths already relative are passed through untouched.
    """
    path = Path(binary)
    if not path.is_absolute():
        return binary
    try:
        rel = path.resolve().relative_to(cwd.resolve())
    except ValueError:
        raise SystemExit(
            f"binary '{binary}' is not inside the current directory "
            f"'{cwd}' (mounted as project:); pass a path relative to it"
        )
    return rel.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="amigarig")
    parser.add_argument("--config", required=True, help="run/machine profile name")
    parser.add_argument(
        "--configs-dir",
        default=DEFAULT_CONFIGS_DIR,
        help="directory containing local.yaml + machine/kickstart/workbench/boot/run/ "
        "(default: %(default)s, override via AMIGARIG_CONFIG_DIR too)",
    )
    parser.add_argument(
        "--fsuae-binary",
        default=None,
        help="defaults to fsuae_binary in <configs-dir>/local.yaml, then /usr/bin/fs-uae",
    )
    parser.add_argument(
        "--set", action="append", default=[], metavar="key=value", dest="overrides"
    )
    parser.add_argument("binary")
    parser.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    configs_dir = Path(args.configs_dir).expanduser()
    registries = Registries(configs_dir)
    local_layer = load_yaml_if_present(configs_dir / LOCAL_CONFIG_FILENAME)
    project_local = load_project_local(Path.cwd())
    env_layer = env_overrides(os.environ)
    cli_layer = parse_set_flags(args.overrides)

    merged = assemble(
        registries,
        args.config,
        local_layer=local_layer,
        project_local=project_local,
        env_layer=env_layer,
        cli_overrides=cli_layer,
    )

    fsuae_binary = (
        args.fsuae_binary or local_layer.get("fsuae_binary") or "/usr/bin/fs-uae"
    )
    fsuae_binary = str(Path(fsuae_binary).expanduser())
    binary = relativize_binary(args.binary, Path.cwd())
    return run(merged, fsuae_binary, binary, args.args)


if __name__ == "__main__":
    sys.exit(main())
