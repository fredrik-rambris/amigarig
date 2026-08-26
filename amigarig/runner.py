"""Orchestrates: merged config -> assembled disk targets -> fs-uae argv -> exec."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .assigns import AssignTable
from .backends import RunContext, get_backend
from .disktargets import Target, make_target, run_copy
from .execspec import run_exec_stage
from .log import logger
from .startup import write_startup_sequence


def _tmp_dir_factory(root: Path):
    counter = {"n": 0}

    def make() -> Path:
        counter["n"] += 1
        path = root / f"t{counter['n']}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    return make


def run(
    merged_config: dict,
    fsuae_binary: str,
    binary: str | None,
    args: list[str],
    *,
    project_dir: Path | None = None,
) -> int:
    """`binary=None` means "rig-only": build + keep the configured targets
    (ADFs / directories) and stop -- no startup-sequence, no backend
    (fs-uae/vamos) launched at all. `boot.run: false` (build a target but
    still let a later CI step decide) is a separate, backend-level knob;
    this is the "there's nothing to launch" case.

    `project_dir` is what gets mounted as `project:` -- defaults to the
    current directory (cli.py resolves --project-dir/config's project.dir
    against it before calling in, so by the time it gets here it's
    already an absolute, resolved path)."""
    project_dir = Path(project_dir) if project_dir is not None else Path(os.getcwd())

    assigns = AssignTable(merged_config.get("assigns", {}))
    assigns.set("project", str(project_dir))

    tmp_root = Path(tempfile.mkdtemp(prefix="amigarig-"))
    make_tmp_dir = _tmp_dir_factory(tmp_root)

    exec_spec = merged_config.get("exec", [])
    boot_cfg = merged_config.get("boot", {"type": "harddrive"})
    project_cfg = merged_config.get("project", {"type": "harddrive"})

    targets: dict[str, Target] = {}
    try:
        # very early -- before any target/copy work, so it can generate
        # inputs (key files, fetched assets, ...) that copy: later depends on
        run_exec_stage(
            exec_spec, "init", assigns=assigns, config=merged_config, make_tmp_dir=make_tmp_dir
        )

        targets["boot"] = make_target("boot", boot_cfg, assigns, make_tmp_dir)

        project_target: Target | None = None
        if project_cfg.get(
            "type", "harddrive"
        ) == "harddrive" and "project" not in merged_config.get("copy", {}):
            # plain directory mount, nothing to build
            project_target = Target("project", "mounted_dir", project_dir, None, True, True)
        else:
            targets["project"] = make_target("project", project_cfg, assigns, make_tmp_dir)
            project_target = targets["project"]

        copy_spec = merged_config.get("copy", {})
        copy_types = merged_config.get("copy_types", {})
        if copy_spec:
            run_copy(copy_spec, copy_types, targets, assigns)

        # must run before finalize(): image writers (ADFVolumeWriter) close
        # the volume in finalize() and cannot be written to afterwards
        if binary is not None:
            write_startup_sequence(
                targets["boot"],
                merged_config.get("startup", []),
                binary,
                args,
                config=merged_config,
                assigns=assigns,
            )

        for target in targets.values():
            if target.writer is not None:
                target.writer.finalize()

        if binary is None:
            logger.info(f"Rigged boot target at {targets['boot'].path}")
            if project_target is not None and project_target.writer is not None:
                logger.info(f"Rigged project target at {project_target.path}")
            return 0

        should_run = boot_cfg.get("run", True)
        if not should_run:
            logger.info(
                f"Built boot target at {targets['boot'].path} (run: false, skipping backend)"
            )
            return 0

        run_exec_stage(
            exec_spec, "before", assigns=assigns, config=merged_config, make_tmp_dir=make_tmp_dir
        )

        backend_name = merged_config.get("backend", "fs-uae")
        backend = get_backend(backend_name)
        ctx = RunContext(
            merged_config=merged_config,
            assigns=assigns,
            boot=targets["boot"],
            project=project_target,
            fsuae_binary=fsuae_binary,
            binary=binary,
            args=args,
        )
        result = backend(ctx)

        run_exec_stage(
            exec_spec, "after", assigns=assigns, config=merged_config, make_tmp_dir=make_tmp_dir
        )
        return result
    finally:
        if "boot" in targets and not boot_cfg.get("keep_as") and targets["boot"].kind == "mounted_dir":
            shutil.rmtree(targets["boot"].path, ignore_errors=True)
        shutil.rmtree(tmp_root, ignore_errors=True)
