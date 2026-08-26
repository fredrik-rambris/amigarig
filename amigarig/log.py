"""Shared logger for amigarig's own console output, prefixed "[amigarig] "
so it's easy to pick out from fs-uae/vamos/subprocess noise sharing the
same terminal. No timestamps/level names -- just the prefix. Everything
goes to stderr, leaving stdout free for anything a script might want to
pipe.

Verbosity is a 0/1/2 count (`-v` is repeatable, `verbose:` in config can
also be an int, or a bool as shorthand for 0/1) -- see `set_verbosity`:

  0 (default) -- WARNING: quiet, just warnings and errors.
  1 (-v)      -- INFO: adds copy: files, exec: commands, the backend
                 launch line, rigged/built-target summaries.
  2 (-vv)     -- DEBUG: adds config loading/merging detail (which YAML
                 files were read, which machine/workbench/boot/run
                 profiles were selected) -- for "why did the output come
                 out like that".
"""
from __future__ import annotations

import logging

logger = logging.getLogger("amigarig")
logger.setLevel(logging.WARNING)
logger.propagate = False

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[amigarig] %(message)s"))
    logger.addHandler(_handler)

_LEVELS_BY_VERBOSITY = [logging.WARNING, logging.INFO, logging.DEBUG]


def set_verbosity(count: int) -> None:
    """`count` is clamped to the highest defined level -- passing more `-v`
    than there are levels just stays at DEBUG, it doesn't error."""
    index = max(0, min(count, len(_LEVELS_BY_VERBOSITY) - 1))
    logger.setLevel(_LEVELS_BY_VERBOSITY[index])
