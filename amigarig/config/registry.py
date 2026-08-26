"""Loads a directory of YAML config files into a name -> raw-dict registry."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..errors import AmigarigError


class ConfigNotFoundError(AmigarigError, KeyError):
    pass


class ConfigLoadError(AmigarigError):
    pass


def load_yaml_file(path: Path) -> dict:
    """Load one YAML file into a dict, raising `ConfigLoadError` (with the
    file path) on a parse error or a non-mapping top level, instead of a
    bare yaml.YAMLError traceback. A missing/empty file is `{}`."""
    try:
        with path.open() as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as e:
        raise ConfigLoadError(f"{path}: invalid YAML ({e})") from None
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigLoadError(f"{path}: top-level YAML must be a mapping")
    return data


class Registry:
    """A named collection of raw config dicts loaded from *.yaml files.

    Name is the filename without extension, e.g. configs/machine/a1200.yaml
    is registered as "a1200".
    """

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._raw: dict[str, dict] = {}
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.yaml")):
                self._raw[path.stem] = load_yaml_file(path)

    def __contains__(self, name: str) -> bool:
        return name in self._raw

    def get_raw(self, name: str) -> dict:
        try:
            return self._raw[name]
        except KeyError:
            raise ConfigNotFoundError(
                f"'{name}' not found in registry {self.directory}"
            ) from None

    def names(self) -> list[str]:
        return list(self._raw.keys())

    def register(self, name: str, data: dict) -> None:
        """Register a config dict at runtime (e.g. a project-local override)."""
        self._raw[name] = data

    @classmethod
    def union(cls, *directories: Path) -> "Registry":
        """Load multiple directories into a single namespace (used for
        machine/ + kickstart/, which freely `extends:` each other)."""
        registry = cls.__new__(cls)
        registry.directory = Path(directories[0]) if directories else Path(".")
        registry._raw = {}
        for directory in directories:
            sub = cls(directory)
            for name in sub.names():
                if name in registry._raw:
                    raise ValueError(f"duplicate config name '{name}' across {directories}")
                registry._raw[name] = sub.get_raw(name)
        return registry
