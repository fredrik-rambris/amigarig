"""Shared logger for amigarig's own console output, prefixed "[amigarig] "
so it's easy to pick out from fs-uae/vamos/subprocess noise sharing the
same terminal. No timestamps/level names -- just the prefix.

INFO (the default) is amigarig's normal "here's what happened" output
(rigged targets, errors); DEBUG is `-v`/`--verbose`/`verbose: true`
territory (every file copied, every exec: command, the backend launch
line) -- see `set_verbose`. Everything goes to stderr, leaving stdout
free for anything a script might want to pipe.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("amigarig")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[amigarig] %(message)s"))
    logger.addHandler(_handler)


def set_verbose(verbose: bool) -> None:
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
