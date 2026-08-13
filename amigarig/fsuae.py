"""Builds the fs-uae argv from the merged config's `fsuae:` namespace plus
the assembled disk targets."""
from __future__ import annotations

from .assigns import AssignTable
from .copyspec import resolve_ref
from .disktargets import Target
from .fsutil import CaseInsensitiveResolver

# fsuae.* keys that may hold an assign-qualified ("kickstart:kick31.rom") or
# absolute path rather than a literal fs-uae option value, and so need
# resolving through the assign table before being handed to fs-uae. Kept as
# an explicit list rather than scanning every value for ":" since values
# like serial_port ("tcp://127.0.0.1:1234") also contain ':' but aren't
# assign references.
PATH_LIKE_FSUAE_KEYS = {"kickstart_file"}


def resolve_fsuae_paths(fsuae_opts: dict, assigns: AssignTable) -> dict:
    ci = CaseInsensitiveResolver()
    resolved = dict(fsuae_opts)
    for key in PATH_LIKE_FSUAE_KEYS:
        value = resolved.get(key)
        if isinstance(value, str) and (value.startswith("/") or ":" in value):
            resolved[key] = str(resolve_ref(value, assigns, ci))
    return resolved


def build_argv(fsuae_binary: str, fsuae_opts: dict, boot: Target, project: Target | None) -> list[str]:
    argv = [fsuae_binary]

    if boot.kind == "mounted_dir":
        argv.append(f"--hard_drive_0={boot.path}")
        argv.append("--hard_drive_0_label=System")
    else:
        argv.append(f"--floppy_drive_0={boot.path}")

    if project is not None:
        if project.kind == "mounted_dir":
            argv.append(f"--hard_drive_1={project.path}")
            argv.append("--hard_drive_1_label=Project")
        else:
            argv.append(f"--floppy_drive_1={project.path}")

    for key, value in fsuae_opts.items():
        if value is None:
            continue
        if isinstance(value, bool):
            argv.append(f"--{key}={1 if value else 0}")
        else:
            argv.append(f"--{key}={value}")

    return argv
