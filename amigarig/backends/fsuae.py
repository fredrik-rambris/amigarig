"""fs-uae backend: builds the fs-uae argv and spawns it as a subprocess.

Boots a full synthetic machine off the assembled boot: target -- this is
the original, and default, amigarig behavior.
"""
from __future__ import annotations

import os

from ..fsuae import build_argv, resolve_fsuae_paths


def run(ctx) -> int:
    fsuae_opts = resolve_fsuae_paths(ctx.merged_config.get("fsuae", {}), ctx.assigns)
    argv = build_argv(ctx.fsuae_binary, fsuae_opts, ctx.boot, ctx.project)

    if ctx.verbose:
        print(f"exec: {argv}")

    print(
        "Connect to port 1234 for logs"
        if "serial_port" in ctx.merged_config.get("fsuae", {})
        else ""
    )
    return os.spawnvp(os.P_WAIT, ctx.fsuae_binary, argv)
