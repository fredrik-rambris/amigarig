"""Renders the s/startup-sequence file from merged `boot.startup` lines.

No templating engine: `startup` is a plain mergeable list (subject to the
same `+startup` append rule as any other list-valued key), and the only
substitution needed is the launch line itself. "Conditional" lines are
just a question of which config layer contributes them.
"""
from __future__ import annotations

import shlex
from pathlib import Path


def render_startup_sequence(lines: list[str], binary: str, args: list[str]) -> str:
    launch_args = " ".join(shlex.quote(a) for a in args) if args else ""
    rendered = [line.format(binary=binary, args=launch_args) for line in lines]
    return "\n".join(rendered) + "\n"


def write_startup_sequence(target, lines: list[str], binary: str, args: list[str]) -> None:
    if not lines:
        # startup: [] -- caller is expected to supply s/startup-sequence via copy: instead
        return
    content = render_startup_sequence(lines, binary, args)
    target.writer.write_bytes(target.root_path / "s" / "startup-sequence", content.encode())
