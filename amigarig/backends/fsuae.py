"""fs-uae backend: builds the fs-uae argv and spawns it as a subprocess.

Boots a full synthetic machine off the assembled boot: target -- this is
the original, and default, amigarig behavior.
"""
from __future__ import annotations

import os

from ..fsuae import build_argv, resolve_fsuae_paths
from ..log import logger


def run(ctx) -> int:
    fsuae_opts = resolve_fsuae_paths(ctx.merged_config.get("fsuae", {}), ctx.assigns)
    argv = build_argv(ctx.fsuae_binary, fsuae_opts, ctx.boot, ctx.project)

    logger.debug(f"exec: {argv}")

    return os.spawnvp(os.P_WAIT, ctx.fsuae_binary, argv)
