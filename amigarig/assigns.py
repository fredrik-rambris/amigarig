"""Amiga-style logical assigns: name: -> path (possibly another assign)."""
from __future__ import annotations

from pathlib import Path


class AssignError(ValueError):
    pass


class AssignTable:
    def __init__(self, assigns: dict[str, str] | None = None):
        self._assigns = dict(assigns or {})

    def set(self, name: str, target: str) -> None:
        self._assigns[name] = target

    def names(self) -> list[str]:
        return list(self._assigns)

    def resolve(self, path: str) -> Path:
        return self._resolve(path, visited=())

    def _resolve(self, path: str, visited: tuple[str, ...]) -> Path:
        if path.startswith("/"):
            return Path(path)

        prefix, sep, rest = path.partition(":")
        if not sep:
            # no assign prefix at all -- treat as relative to cwd
            return Path(path)

        if prefix not in self._assigns:
            raise AssignError(f"unknown assign '{prefix}:' in path '{path}'")
        if prefix in visited:
            chain = " -> ".join(visited + (prefix,))
            raise AssignError(f"assign cycle detected: {chain}")

        target = self._assigns[prefix]
        base = self._resolve(target, visited + (prefix,))
        return base / rest if rest else base
