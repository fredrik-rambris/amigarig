"""vamos backend: runs the binary directly through amitools' vamos, in
process (`amitools.vamos.main.main`), no subprocess, no CPU/chipset
emulation -- vamos emulates the AmigaOS API surface for a single process.

The boot: target is still built the same way as for fs-uae (copy: c/libs/
fonts/... via the normal handler pipeline) so behavior stays consistent
between backends -- vamos just doesn't read s/startup-sequence, it's not
booting Workbench, it launches `binary` directly. Leaving the generated
startup-sequence file on the target regardless is harmless.

Every amigarig assign that currently points at a real host directory
(mounted_dir target, or a plain host-path assign from config) is exposed
to vamos as an AmigaOS volume of the same name, so `copy_types` written
with fs-uae in mind (`wb:`, `boot:`, `project:`, ...) resolve the same way
for a binary running under vamos. Assigns pointing at an *image* target
(floppy/hdf, written via ADFVolumeWriter) can't be mapped this way --
vamos maps volumes straight to host directories, not amitools disk images
-- so those are skipped with a warning; use `type: harddrive` for any
target that needs to be reachable from a vamos run.
"""
from __future__ import annotations

import sys

from ..config.merge import merge_chain
from ..disktargets import Target


def _volume_specs(assigns, boot: Target, project: Target | None) -> list[str]:
    image_targets = {
        t.name for t in (boot, project) if t is not None and t.kind == "image"
    }
    specs = []
    for name in assigns.names():
        if name in image_targets:
            print(
                f"vamos backend: skipping '{name}:' -- it's a floppy/hdf image, "
                "not a directory vamos can mount as a volume",
                file=sys.stderr,
            )
            continue
        path = assigns.resolve(f"{name}:")
        if not path.is_dir():
            # not every assign resolves to a directory (e.g. a single ROM
            # file) -- only directories are meaningful as vamos volumes
            continue
        specs.append(f"{name}:{path}")
    return specs


def run(ctx) -> int:
    from amitools.vamos.main import main as vamos_main

    if ctx.boot.kind == "image":
        raise ValueError(
            "backend: vamos requires boot.type: harddrive (floppy/hdf boot "
            "targets aren't mountable as vamos volumes)"
        )

    volumes = _volume_specs(ctx.assigns, ctx.boot, ctx.project)

    cfg_dict = {
        # "volumes" is a top-level key in vamos' cfg schema (sibling of
        # "path"), not nested under "path" -- nesting it there means vamos
        # never sees the volumes at all, so any AmigaOS path pointing at one
        # (e.g. project:) fails to resolve.
        "volumes": volumes,
    }
    # allow escape-hatch overrides straight from config, e.g. vamos.process.stack
    cfg_dict = merge_chain([cfg_dict, ctx.merged_config.get("vamos", {})])

    # vamos' own arg parser requires "bin" (and takes "args" too) as
    # positionals -- passing args=[] leaves it with nothing to satisfy that
    # requirement even though cfg_dict never sets binary/args, so it always
    # errors out with "the following arguments are required: bin". Pass them
    # as vamos CLI args instead of via cfg_dict.
    vamos_args = [f"project:{ctx.binary}", *ctx.args]

    return vamos_main(cfg_dict=cfg_dict, args=vamos_args)
