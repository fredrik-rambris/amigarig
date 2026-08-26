"""Shared Jinja setup for config-driven templating.

Currently used only for `exec:` item `env:` values (see execspec.py) -- cmd
and cwd are deliberately *not* templated, to keep exec predictable; cwd
gets the usual assign-string resolution instead (AssignTable.resolve).

Every template renders with the merged config available as `config` (so
e.g. `"{{ config.fsuae.cpu }}"` works for nested lookups -- Jinja falls
back to item access for plain dicts, no special config wrapper needed) and
a registered `assign` global function that expands an amigarig assign to
its real host path, e.g. `"{{ assign('wb:') }}"`.
"""
from __future__ import annotations

import jinja2

from .assigns import AssignTable


def render_env(env: dict[str, str], *, config: dict, assigns: AssignTable) -> dict[str, str]:
    jinja_env = jinja2.Environment()
    jinja_env.globals["assign"] = lambda ref: str(assigns.resolve(ref))
    return {key: jinja_env.from_string(value).render(config=config) for key, value in env.items()}
