"""Deep-merge algorithm shared by every config registry.

Rules:
  - dict + dict            -> recursive merge, key by key (never wholesale replace)
  - list + list, same key  -> replace (last write wins)
  - "+key" in the higher layer -> append/extend the base's "key" list instead
    of replacing it (marker is stripped before comparison, dedup is left to
    the caller since identity depends on later resolution, not raw values)
  - "^key" in the higher layer -> prepend the override's list before the
    base's "key" list instead of replacing it (same stripping/dedup rules
    as "+key", just the other end)
  - scalar + scalar         -> replace
"""
from __future__ import annotations

from typing import Any

APPEND_PREFIX = "+"
PREPEND_PREFIX = "^"


def merge(base: Any, override: Any) -> Any:
    """Merge `override` on top of `base`, returning a new structure."""
    if isinstance(base, dict) and isinstance(override, dict):
        return _merge_dicts(base, override)
    if override is None:
        return base
    return override


def _merge_dicts(base: dict, override: dict) -> dict:
    result = dict(base)
    for raw_key, value in override.items():
        if isinstance(raw_key, str) and raw_key.startswith(APPEND_PREFIX):
            key = raw_key[len(APPEND_PREFIX):]
            existing = result.get(key)
            if existing is None:
                result[key] = list(value) if isinstance(value, list) else value
            elif isinstance(existing, list) and isinstance(value, list):
                result[key] = existing + value
            else:
                raise TypeError(
                    f"cannot append to key '{key}': base is {type(existing).__name__}, "
                    f"override is {type(value).__name__} (both must be lists)"
                )
            continue

        if isinstance(raw_key, str) and raw_key.startswith(PREPEND_PREFIX):
            key = raw_key[len(PREPEND_PREFIX):]
            existing = result.get(key)
            if existing is None:
                result[key] = list(value) if isinstance(value, list) else value
            elif isinstance(existing, list) and isinstance(value, list):
                result[key] = value + existing
            else:
                raise TypeError(
                    f"cannot prepend to key '{key}': base is {type(existing).__name__}, "
                    f"override is {type(value).__name__} (both must be lists)"
                )
            continue

        key = raw_key
        if key in result:
            result[key] = merge(result[key], value)
        else:
            # no base to merge against, but `value` may itself contain
            # "+nested" keys that still need normalizing to plain keys
            result[key] = merge({}, value) if isinstance(value, dict) else value
    return result


def merge_chain(layers: list) -> dict:
    """Merge a list of dicts left to right, lowest priority first."""
    result: dict = {}
    for layer in layers:
        result = merge(result, layer)
    return result
