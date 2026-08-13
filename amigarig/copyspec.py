"""Normalizes copy: entries and resolves them to real filesystem paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .assigns import AssignTable
from .fsutil import CaseInsensitiveResolver


@dataclass(frozen=True)
class ResolvedCopyItem:
    source: Path
    dest: Path


def _is_qualified(value: str) -> bool:
    return value.startswith("/") or value.startswith("~") or ":" in value


def _basename(value: str) -> str:
    """Basename of a bare, absolute, or assign-qualified path string --
    strips any "prefix:" before taking the last path component, since
    PurePosixPath("amiga:system-configuration").name would otherwise
    return the whole string (":" isn't a path separator)."""
    if value.startswith("/"):
        return PurePosixPath(value).name
    _, _, rest = value.partition(":")
    return PurePosixPath(rest).name if rest else PurePosixPath(value).name


def normalize_copy_item(raw) -> tuple[str, str]:
    """Bare string or {source, destination} mapping -> (source_str, dest_str).

    A *qualified* source (absolute host path, or assign-qualified like
    "amiga:system-configuration") always defaults its destination to just
    the basename -- joined under the type's default dest root by the
    caller -- rather than reusing the qualified string itself, which would
    otherwise send the item to whatever target that string's own prefix
    names instead of the type's normal destination. Only a plain bare name
    (already relative to the type's default src/dest roots) reuses the same
    string for both sides.
    """
    if isinstance(raw, str):
        if _is_qualified(raw):
            return raw, _basename(raw)
        return raw, raw
    if isinstance(raw, dict):
        source = raw["source"]
        dest = raw.get("destination", _basename(source))
        return source, dest
    raise TypeError(f"copy item must be a string or mapping, got {raw!r}")


def resolve_ref(ref: str, assigns: AssignTable, ci: CaseInsensitiveResolver) -> Path:
    """Resolve an absolute host path or an assign-qualified ('wb:C') reference
    to a real, case-resolved Path."""
    if ref.startswith("/") or ref.startswith("~"):
        expanded = Path(ref).expanduser()
        parts = expanded.parts[1:]
        resolved = ci.resolve(Path(expanded.parts[0]), *parts)
        return resolved if resolved is not None else expanded

    prefix, sep, rest = ref.partition(":")
    if not sep:
        raise ValueError(f"'{ref}' is neither absolute nor assign-qualified (missing ':')")
    base = assigns.resolve(prefix + ":")
    if not rest:
        return base
    resolved = ci.resolve(base, rest)
    return resolved if resolved is not None else base / rest


def resolve_side(
    value: str,
    default_root: str,
    assigns: AssignTable,
    ci: CaseInsensitiveResolver,
    *,
    must_exist: bool,
) -> Path:
    if _is_qualified(value):
        return resolve_ref(value, assigns, ci)
    root = resolve_ref(default_root, assigns, ci)
    if must_exist:
        resolved = ci.resolve(root, value)
        if resolved is not None:
            return resolved
    return root / value


def resolve_copy_item(
    raw,
    type_src: str,
    type_dest: str,
    assigns: AssignTable,
    ci: CaseInsensitiveResolver,
) -> ResolvedCopyItem:
    source_str, dest_str = normalize_copy_item(raw)
    source = resolve_side(source_str, type_src, assigns, ci, must_exist=True)
    dest = resolve_side(dest_str, type_dest, assigns, ci, must_exist=False)
    return ResolvedCopyItem(source=source, dest=dest)
