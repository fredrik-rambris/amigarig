"""Resolves an `extends:` chain within a single registry, either as one
merged dict (`resolve_chain`) or as the ordered list of raw per-file layers
that went into it (`flatten_chain`).

`flatten_chain` exists because pre-merging a chain in isolation (as
`resolve_chain` does) consumes any unmatched `+key`/`^key` -- with no base
in that isolated chain to append to, `merge()` has to commit it to a plain
`key`, discarding the append intent for anything merged against it *later*
(e.g. a workbench chain's `copy.c` merged against a boot chain's `+c` at
the top-level `assemble()`). Callers that go on to merge a chain's result
against other chains (build.py's `assemble()`) should use `flatten_chain`
and fold its raw layers straight into one flat, whole-config `merge_chain`
call instead, so `+`/`^` only ever gets resolved once, at the very end,
against the true accumulated base."""
from __future__ import annotations

from .merge import merge_chain
from .registry import Registry

EXTENDS_KEY = "extends"


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def flatten_chain(
    registry: Registry, name: str, _visiting: tuple[str, ...] = ()
) -> list[tuple[str, dict]]:
    """Resolve `name`'s `extends:` chain (str or list, multiple inheritance
    allowed) into the ordered list of `(name, raw_dict)` layers that make it
    up, parents first, most specific (own) last -- unmerged, `+`/`^`
    prefixes intact. Each layer keeps the config name it came from (its
    registry filename minus `.yaml`) so callers can log/report provenance
    -- see `build.py`'s per-layer debug logging."""
    if name in _visiting:
        cycle = " -> ".join(_visiting + (name,))
        raise ValueError(f"extends cycle detected: {cycle}")

    raw = registry.get_raw(name)
    parent_names = _as_list(raw.get(EXTENDS_KEY))

    layers = []
    for parent_name in parent_names:
        layers.extend(flatten_chain(registry, parent_name, _visiting + (name,)))

    own = {k: v for k, v in raw.items() if k != EXTENDS_KEY}
    layers.append((name, own))
    return layers


def resolve_chain(registry: Registry, name: str) -> dict:
    """Resolve `name` in `registry` into one merged dict. Fine for reading a
    scalar (e.g. peeking at a machine profile's `workbench:` reference) --
    for anything that will itself be merged against other chains, use
    `flatten_chain` instead so `+key`/`^key` isn't resolved prematurely."""
    return merge_chain([layer for _, layer in flatten_chain(registry, name)])
