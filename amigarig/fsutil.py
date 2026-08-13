"""Case-insensitive filesystem resolution (Amiga is case-insensitive, Linux isn't)."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


class CaseInsensitiveResolver:
    """Resolves path components under a base directory case-insensitively,
    one segment at a time, caching each directory listing since the same
    Workbench tree gets probed repeatedly per run."""

    def __init__(self):
        self._listing_cache: dict[Path, dict[str, str]] = {}

    def _listing(self, directory: Path) -> dict[str, str]:
        cached = self._listing_cache.get(directory)
        if cached is not None:
            return cached
        listing: dict[str, str] = {}
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    listing.setdefault(entry.name.lower(), entry.name)
        except (FileNotFoundError, NotADirectoryError):
            pass
        self._listing_cache[directory] = listing
        return listing

    def resolve(self, base: Path, *components: str) -> Path | None:
        current = Path(base)
        for raw_component in components:
            for part in PurePosixPath(raw_component).parts:
                listing = self._listing(current)
                real_name = listing.get(part.lower())
                if real_name is None:
                    return None
                current = current / real_name
        return current

    def exists(self, base: Path, *components: str) -> bool:
        resolved = self.resolve(base, *components)
        return resolved is not None and resolved.exists()


ci_resolve = CaseInsensitiveResolver()
