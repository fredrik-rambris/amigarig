"""Resolves an `extends:` chain within a single registry into one merged dict."""
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


def resolve_chain(registry: Registry, name: str, _visiting: tuple[str, ...] = ()) -> dict:
    """Resolve `name` in `registry`, following `extends:` (str or list, multiple
    inheritance allowed), merging parents left to right, most specific last."""
    if name in _visiting:
        cycle = " -> ".join(_visiting + (name,))
        raise ValueError(f"extends cycle detected: {cycle}")

    raw = registry.get_raw(name)
    parent_names = _as_list(raw.get(EXTENDS_KEY))

    layers = []
    for parent_name in parent_names:
        layers.append(resolve_chain(registry, parent_name, _visiting + (name,)))

    own = {k: v for k, v in raw.items() if k != EXTENDS_KEY}
    layers.append(own)
    return merge_chain(layers)
