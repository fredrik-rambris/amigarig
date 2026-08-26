"""Shared Jinja setup for config-driven templating.

Used for `exec:` item `env:` values (execspec.py) and `startup:` line
rendering (startup.py) -- `exec:`'s `cmd`/`cwd` are deliberately *not*
templated, to keep exec predictable; `cwd` gets the usual assign-string
resolution instead (AssignTable.resolve).

Every template renders with the merged config available as `config` (so
e.g. `"{{ config.fsuae.cpu }}"` works for nested lookups -- Jinja falls
back to item access for plain dicts, no special config wrapper needed) and
a registered `assign` global function that expands an amigarig assign to
its real host path, e.g. `"{{ assign('wb:') }}"`.

Also registers a few small filters:
- `amigaquote` (AmigaDOS CLI quoting -- not shell quoting), e.g.
  `"{{ some_value | amigaquote }}"`.
- `stem`/`suffix` (`pathlib.PurePosixPath` semantics -- binary/args are
  always posix-style, see `cli.py`'s `relativize_binary`), e.g. given
  `binary = "something.Asc"`: `"{{ binary | stem }}"` -> `"something"`,
  `"{{ binary | suffix }}"` -> `".Asc"`. Like `Path.stem`/`Path.suffix`,
  only the last dotted component is treated as the extension
  (`"a.tar.gz" | stem` -> `"a.tar"`), and a directory prefix is dropped
  too (`"bin/game.Asc" | stem` -> `"game"`).
"""
from __future__ import annotations

from pathlib import PurePosixPath

import jinja2

from .assigns import AssignTable


def amigaquote(value) -> str:
    """AmigaDOS-style quoting: `*` and `"` are escaped (`**`, `*"`); the
    result is wrapped in double quotes if it contains whitespace, a `"`,
    or is empty -- AmigaDOS' own CLI quoting rules, not shell quoting."""
    s = value if isinstance(value, str) else str(value)
    escaped = s.replace("*", "**").replace('"', '*"')
    needs_quotes = s == "" or any(c.isspace() for c in s) or '"' in s
    return f'"{escaped}"' if needs_quotes else escaped


def build_environment(assigns: AssignTable) -> jinja2.Environment:
    env = jinja2.Environment()
    env.globals["assign"] = lambda ref: str(assigns.resolve(ref))
    env.filters["amigaquote"] = amigaquote
    env.filters["stem"] = lambda value: PurePosixPath(value).stem
    env.filters["suffix"] = lambda value: PurePosixPath(value).suffix
    return env


def render_env(env: dict[str, str], *, config: dict, assigns: AssignTable) -> dict[str, str]:
    jinja_env = build_environment(assigns)
    return {key: jinja_env.from_string(value).render(config=config) for key, value in env.items()}
