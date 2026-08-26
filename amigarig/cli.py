from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import platformdirs
import yaml

from .config.build import Registries, assemble, env_overrides, _set_dotted
from .config.registry import load_yaml_file
from .errors import AmigarigError
from .log import logger, set_verbosity
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
    return load_yaml_file(path)


def load_project_local(cwd: Path) -> dict:
    return load_yaml_if_present(cwd / PROJECT_LOCAL_FILENAME)


def relativize_binary(binary: str, project_dir: Path) -> str:
    """Strip `project_dir` from an absolute binary path so it lands
    correctly under "cd Project:" in the startup-sequence. Amiga side only
    ever sees `project_dir` mounted as project: (the current directory by
    default, or wherever --project-dir/project.dir points), so an absolute
    host path is meaningless there -- e.g. project_dir=/data/Coding/x,
    "/data/Coding/x/bin/game" becomes "bin/game". Paths already relative
    are passed through untouched (resolved against `project_dir` by
    AmigaOS at boot time, not by amigarig).
    """
    path = Path(binary)
    if not path.is_absolute():
        return binary
    try:
        rel = path.resolve().relative_to(project_dir.resolve())
    except ValueError:
        raise SystemExit(
            f"binary '{binary}' is not inside '{project_dir}' (mounted as "
            "project:); pass a path relative to it"
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
        "--project-dir",
        default=None,
        help="directory to mount as project: instead of the current directory "
        "(relative paths are resolved against the current directory); "
        "binary is resolved relative to this directory too. Also settable "
        "as project.dir in config; this flag takes priority. Lets you "
        "run from a repo root with the build output mounted as project: "
        "without cd'ing into it first, e.g. --project-dir build game",
    )
    parser.add_argument(
        "--set", action="append", default=[], metavar="key=value", dest="overrides"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="repeatable. -v: also print copy: files, exec: commands, the "
        "backend launch command, and rigged/built-target summaries. -vv: "
        "also trace config loading/merging (which YAML files were read, "
        "which machine/workbench/boot/run profiles were selected). Also "
        "settable as verbose: <0|1|2> (or a bool, as shorthand for 0/1) in "
        "config -- the higher of the two wins, this flag only ever raises it",
    )
    parser.add_argument(
        "binary",
        nargs="?",
        default=None,
        help="startup-sequence launch line; omit to just rig the configured "
        "target(s) (ADF/dir artifacts) and stop -- no startup-sequence, no "
        "fs-uae/vamos launched",
    )
    parser.add_argument("args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)
    # CLI-only for now, so -vv can trace the config loading/merging that's
    # about to happen below; re-applied below once verbose: from config is
    # also known, in case config asks for more than the CLI did.
    set_verbosity(args.verbose)

    try:
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
        project_dir_opt = args.project_dir or merged.get("project", {}).get("dir")
        project_dir = (
            Path(project_dir_opt).expanduser().resolve() if project_dir_opt else Path.cwd()
        )
        binary = (
            relativize_binary(args.binary, project_dir) if args.binary is not None else None
        )
        config_verbosity = merged.get("verbose", 0)
        if isinstance(config_verbosity, bool):
            config_verbosity = 1 if config_verbosity else 0
        set_verbosity(max(args.verbose, int(config_verbosity)))

        return run(merged, fsuae_binary, binary, args.args, project_dir=project_dir)
    except AmigarigError as e:
        logger.error(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
