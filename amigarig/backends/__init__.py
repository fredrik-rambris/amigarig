"""Backends: turn assembled disk targets + merged config into a launched
Amiga process (or nothing, for the "just rig it" build-only case).

Each backend module exposes `run(ctx: RunContext) -> int`, called only when
a `binary` was given -- rig-only mode never dispatches to a backend at all
(see runner.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..assigns import AssignTable
from ..disktargets import Target


@dataclass
class RunContext:
    merged_config: dict
    assigns: AssignTable
    boot: Target
    project: Target | None
    fsuae_binary: str
    binary: str
    args: list[str]
    verbose: bool = False


def get_backend(name: str):
    # imported lazily so `amitools.vamos` (a fairly heavy import) is only
    # ever pulled in when the vamos backend is actually selected
    if name == "fs-uae":
        from . import fsuae as fsuae_backend

        return fsuae_backend.run
    if name == "vamos":
        from . import vamos as vamos_backend

        return vamos_backend.run
    raise ValueError(f"unknown backend '{name}' (known: fs-uae, vamos)")
