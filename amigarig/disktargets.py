"""Assembles the boot/project disk targets and drives copy: through them."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .assigns import AssignTable
from .copyspec import normalize_copy_item, resolve_copy_item, _is_qualified
from .fsutil import CaseInsensitiveResolver
from .handlers import HandlerContext, run_handlers
from .writers.hostdir import HostDirWriter
from .writers.adfvolume import ADFVolumeWriter


@dataclass
class Target:
    name: str
    kind: str  # "mounted_dir" | "image"
    path: Path
    writer: object
    keep: bool
    should_run: bool = True

    @property
    def root_path(self) -> Path:
        """Base path to join generated (non-copy:) content onto, e.g. the
        rendered startup-sequence -- the real dir for mounted_dir targets,
        the virtual "/" root for image targets (see ADFVolumeWriter)."""
        return self.path if self.kind == "mounted_dir" else Path("/")


def make_target(
    name: str,
    cfg: dict,
    assigns: AssignTable,
    make_tmp_dir: Callable[[], Path],
) -> Target:
    ttype = cfg.get("type", "harddrive")
    keep_as = cfg.get("keep_as")
    should_run = cfg.get("run", True)

    if ttype == "harddrive":
        if keep_as:
            path = Path(keep_as).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            keep = True
        else:
            path = make_tmp_dir()
            keep = False
        assigns.set(name, str(path))
        writer = HostDirWriter(path)
        return Target(name, "mounted_dir", path, writer, keep, should_run)

    # floppy / hdf image
    if keep_as:
        image_path = Path(keep_as).expanduser()
        keep = True
    else:
        image_path = make_tmp_dir() / f"{name}.adf"
        keep = False
    assigns.set(name, "/")  # virtual root: dest paths under this target become ami-paths
    volume_name = cfg.get("volume_name", name.capitalize())
    writer = ADFVolumeWriter(image_path, volume_name, cfg.get("blkdev_options"))
    return Target(name, "image", image_path, writer, keep, should_run)


def _dest_target_name(dest_str: str, type_dest_default: str) -> str:
    effective = dest_str if _is_qualified(dest_str) else type_dest_default
    prefix, sep, _ = effective.partition(":")
    if not sep:
        raise ValueError(f"destination '{effective}' has no assign prefix")
    return prefix


def run_copy(
    copy_spec: dict,
    copy_types: dict,
    targets: dict[str, Target],
    assigns: AssignTable,
) -> None:
    """copy_spec: {type_name: [raw_item, ...]}; copy_types: {type_name: {src, dest, handlers}}"""
    ci = CaseInsensitiveResolver()
    ctx = HandlerContext(ci=ci)

    for type_name, raw_items in copy_spec.items():
        type_cfg = copy_types.get(type_name)
        if type_cfg is None:
            raise KeyError(f"copy type '{type_name}' has no entry in copy_types")
        type_src = type_cfg["src"]
        type_dest = type_cfg["dest"]
        handler_names = type_cfg.get("handlers", ["copy"])

        for raw_item in raw_items:
            _, dest_str = normalize_copy_item(raw_item)
            target_name = _dest_target_name(dest_str, type_dest)
            target = targets.get(target_name)
            if target is None:
                raise KeyError(
                    f"copy type '{type_name}' writes to unknown target '{target_name}:'"
                )

            resolved = resolve_copy_item(raw_item, type_src, type_dest, assigns, ci)
            for expanded in run_handlers(resolved, handler_names, ctx):
                target.writer.write(expanded)
    # caller is responsible for calling target.writer.finalize() once all
    # writes (copy: entries + generated content like startup-sequence) are done
