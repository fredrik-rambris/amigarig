"""exec: runs host-side commands around the run, for the rare-but-handy
cases plain config can't cover (generating a key file, fetching an asset,
post-run artifact capture, ...).

Each `exec:` item is a mapping:

    exec:
      - stage: init          # init | before | after (default: "before")
        cmd: "keygen > mykey"    # string -> a script: written to
                                  # $TMPDIR/.exec and run through $SHELL
                                  # (falling back to /bin/sh); or a list ->
                                  # exact argv, run directly, no shell
        cwd: project:keys        # resolved via the normal assign machinery
                                  # (AssignTable.resolve); default: the
                                  # invocation's own temp dir
        input: project:keys/seed.bin    # fed to stdin -- the non-shell
                                          # equivalent of `< file`
        output: project:keys/mykey      # captures stdout -- equivalent
                                          # of `> file`
        env:
          CPU: "{{ config.fsuae.cpu }}"   # Jinja-rendered, see templating.py
        failat: 1             # return code >= failat aborts the run

Stages: "init" runs very early, before any copy:/target building; "before"
runs just before the backend (emulator) launches; "after" runs once it
returns. `exec:` is an ordinary mergeable list (`+exec` appends, like
`copy:`/`startup:`), so items run in merge order within a stage.

Every invocation gets its own fresh temp dir (from the same factory that
mints target scratch dirs); TMPDIR is always set to it in the subprocess
environment, regardless of `cwd` -- so a script can drop generated files
there even when it cd's elsewhere to run.

`input`/`output` exist mainly for a list `cmd` (exact argv, no shell of
its own to do `<`/`>` with), though they work for a string `cmd` too.
Both are resolved the same way as `cwd` (AssignTable.resolve, no Jinja).
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Callable

from .assigns import AssignTable
from .templating import render_env

VALID_STAGES = ("init", "before", "after")
DEFAULT_STAGE = "before"
DEFAULT_FAILAT = 1


class ExecError(RuntimeError):
    pass


def normalize_exec_item(raw) -> dict:
    if not isinstance(raw, dict):
        raise TypeError(f"exec item must be a mapping, got {raw!r}")
    stage = raw.get("stage", DEFAULT_STAGE)
    if stage not in VALID_STAGES:
        raise ValueError(f"exec item has unknown stage {stage!r} (expected one of {VALID_STAGES})")
    cmd = raw.get("cmd")
    if isinstance(cmd, list):
        if not cmd or not all(isinstance(c, str) for c in cmd):
            raise TypeError(f"exec item 'cmd' list must be non-empty strings, got {cmd!r}")
    elif not isinstance(cmd, str) or not cmd:
        raise TypeError(f"exec item 'cmd' must be a non-empty string or list of strings, got {cmd!r}")
    return {
        "stage": stage,
        "cmd": cmd,
        "cwd": raw.get("cwd"),
        "input": raw.get("input"),
        "output": raw.get("output"),
        "env": raw.get("env", {}),
        "failat": raw.get("failat", DEFAULT_FAILAT),
    }


def run_exec_item(
    item: dict,
    *,
    assigns: AssignTable,
    config: dict,
    make_tmp_dir: Callable[[], Path],
) -> None:
    tmp_dir = make_tmp_dir()

    env = dict(os.environ)
    env["TMPDIR"] = str(tmp_dir)
    env.update(render_env(item["env"], config=config, assigns=assigns))

    cwd = assigns.resolve(item["cwd"]) if item["cwd"] else tmp_dir

    cmd = item["cmd"]
    if isinstance(cmd, str):
        script_path = tmp_dir / ".exec"
        script_path.write_text(cmd)
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        shell = os.environ.get("SHELL", "/bin/sh")
        argv = [shell, str(script_path)]
    else:
        # exact argv -- run directly, no shell involved
        argv = cmd

    input_path = assigns.resolve(item["input"]) if item["input"] else None
    output_path = assigns.resolve(item["output"]) if item["output"] else None

    stdin = open(input_path, "rb") if input_path else None
    stdout = open(output_path, "wb") if output_path else None
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, stdin=stdin, stdout=stdout)
    finally:
        if stdin is not None:
            stdin.close()
        if stdout is not None:
            stdout.close()

    if result.returncode >= item["failat"]:
        raise ExecError(
            f"exec ({item['stage']}) failed: {cmd!r} exited {result.returncode} "
            f"(failat={item['failat']})"
        )


def run_exec_stage(
    items: list,
    stage: str,
    *,
    assigns: AssignTable,
    config: dict,
    make_tmp_dir: Callable[[], Path],
) -> None:
    """Normalizes the whole list (so schema errors in a later stage's items
    surface immediately, even during an earlier stage) and runs just the
    ones for `stage`, in merge order."""
    normalized = [normalize_exec_item(raw) for raw in items]
    for exec_item in normalized:
        if exec_item["stage"] == stage:
            run_exec_item(exec_item, assigns=assigns, config=config, make_tmp_dir=make_tmp_dir)
