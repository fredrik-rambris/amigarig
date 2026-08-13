"""Orchestrates: merged config -> assembled disk targets -> fs-uae argv -> exec."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .assigns import AssignTable
from .disktargets import Target, make_target, run_copy
from .fsuae import build_argv, resolve_fsuae_paths
from .startup import write_startup_sequence


def _tmp_dir_factory(root: Path):
    counter = {"n": 0}

    def make() -> Path:
        counter["n"] += 1
        path = root / f"t{counter['n']}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    return make


def run(merged_config: dict, fsuae_binary: str, binary: str, args: list[str]) -> int:
    assigns = AssignTable(merged_config.get("assigns", {}))
    assigns.set("project", os.getcwd())

    tmp_root = Path(tempfile.mkdtemp(prefix="amigarig-"))
    make_tmp_dir = _tmp_dir_factory(tmp_root)

    boot_cfg = merged_config.get("boot", {"type": "harddrive"})
    project_cfg = merged_config.get("project", {"type": "harddrive"})

    targets: dict[str, Target] = {}
    targets["boot"] = make_target("boot", boot_cfg, assigns, make_tmp_dir)

    project_target: Target | None = None
    if project_cfg.get("type", "harddrive") == "harddrive" and "project" not in merged_config.get(
        "copy", {}
    ):
        # plain directory mount, nothing to build
        project_target = Target("project", "mounted_dir", Path(os.getcwd()), None, True, True)
    else:
        targets["project"] = make_target("project", project_cfg, assigns, make_tmp_dir)
        project_target = targets["project"]

    try:
        copy_spec = merged_config.get("copy", {})
        copy_types = merged_config.get("copy_types", {})
        if copy_spec:
            run_copy(copy_spec, copy_types, targets, assigns)

        # must run before finalize(): image writers (ADFVolumeWriter) close
        # the volume in finalize() and cannot be written to afterwards
        write_startup_sequence(
            targets["boot"], merged_config.get("startup", []), binary, args
        )

        for target in targets.values():
            if target.writer is not None:
                target.writer.finalize()

        fsuae_opts = resolve_fsuae_paths(merged_config.get("fsuae", {}), assigns)
        argv = build_argv(fsuae_binary, fsuae_opts, targets["boot"], project_target)

        should_run = boot_cfg.get("run", True)
        if not should_run:
            print(f"Built boot target at {targets['boot'].path} (run: false, skipping fs-uae)")
            return 0

        print("Connect to port 1234 for logs" if "serial_port" in merged_config.get("fsuae", {}) else "")
        return os.spawnvp(os.P_WAIT, fsuae_binary, argv)
    finally:
        if not boot_cfg.get("keep_as") and targets["boot"].kind == "mounted_dir":
            shutil.rmtree(targets["boot"].path, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
