"""Normalizes copy: entries and resolves them to real filesystem paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .assigns import AssignTable
from .errors import AmigarigError
from .fsutil import CaseInsensitiveResolver


class CopyError(AmigarigError):
    pass


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


def normalize_copy_item(raw) -> tuple[str | list[str], str, bool]:
    """Bare string or {source, destination, optional} mapping ->
    (source_str_or_list, dest_str, optional).

    A *qualified* source (absolute host path, or assign-qualified like
    "amiga:system-configuration") always defaults its destination to just
    the basename -- joined under the type's default dest root by the
    caller -- rather than reusing the qualified string itself, which would
    otherwise send the item to whatever target that string's own prefix
    names instead of the type's normal destination. Only a plain bare name
    (already relative to the type's default src/dest roots) reuses the same
    string for both sides.

    ``source`` may also be a list of candidate strings, tried in order
    until one resolves; the basename used for the default destination is
    taken from the first candidate.
    """
    if isinstance(raw, str):
        if _is_qualified(raw):
            return raw, _basename(raw), False
        return raw, raw, False
    if isinstance(raw, dict):
        source = raw["source"]
        first = source[0] if isinstance(source, list) else source
        dest = raw.get("destination", _basename(first))
        optional = bool(raw.get("optional", False))
        return source, dest, optional
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
        resolved = resolve_ref(value, assigns, ci)
        if must_exist and not resolved.exists():
            raise CopyError(f"source '{value}' does not exist (resolved to '{resolved}')")
        return resolved
    root = resolve_ref(default_root, assigns, ci)
    if must_exist:
        resolved = ci.resolve(root, value)
        if resolved is not None:
            return resolved
        raise CopyError(f"source '{value}' not found under '{default_root}' (looked in '{root}')")
    return root / value


def resolve_copy_item(
    raw,
    type_src: str,
    type_dest: str,
    assigns: AssignTable,
    ci: CaseInsensitiveResolver,
) -> ResolvedCopyItem | None:
    """Returns None if the item is optional and none of its candidate
    sources could be found."""
    source_val, dest_str, optional = normalize_copy_item(raw)
    candidates = source_val if isinstance(source_val, list) else [source_val]

    source = None
    last_error: CopyError | None = None
    for candidate in candidates:
        try:
            source = resolve_side(candidate, type_src, assigns, ci, must_exist=True)
            last_error = None
            break
        except CopyError as e:
            last_error = e

    if source is None:
        if optional:
            return None
        raise last_error

    dest = resolve_side(dest_str, type_dest, assigns, ci, must_exist=False)
    return ResolvedCopyItem(source=source, dest=dest)
