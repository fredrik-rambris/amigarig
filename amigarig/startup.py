"""Renders the s/startup-sequence file from merged `boot.startup` items.

`startup` is a plain mergeable list (subject to the same `+startup`
append rule as any other list-valued key). "Conditional" lines are just a
question of which config layer contributes them.

Each item is either a bare string (line = itself, priority =
DEFAULT_PRIORITY) or a mapping `{text, priority}` where `text` is a
string or flat list of strings (a block sharing one priority) -- see
`normalize_startup_item`. `+startup` still controls which layer's items
make it into the merged list (and breaks ties, since the final sort is
stable); the numeric priority then decides final line order, low to
high, once every layer has contributed.

Rendering goes through the same Jinja setup as `exec:`'s `env:` values
(see templating.py): `{{ binary }}`/`{{ args }}` for the launch line
(`args` is already shell-quoted and space-joined, matching the CLI's own
argv), `argsarr` for the raw, un-joined argv list when a line needs to
process args individually (e.g. `{{ argsarr | map('amigaquote') | join(' ') }}`),
`config`/`assign(...)` available too for the rare case a line needs a
config value or a real host path. Jinja's `{{ }}`/`{% %}` delimiters
were also chosen over the previous `str.format()` because they almost
never collide with real AmigaDOS script content, unlike bare `{`/`}`.
"""
from __future__ import annotations

import shlex
from pathlib import Path

from .assigns import AssignTable
from .templating import build_environment

DEFAULT_PRIORITY = 50


def normalize_startup_item(raw) -> tuple[list[str], int]:
    """Bare string or {text, priority} mapping -> (lines, priority).

    `text` may be a single string or a flat list of strings (a block of
    lines sharing one priority) -- no nesting: every element must itself
    be a plain string.
    """
    if isinstance(raw, str):
        return [raw], DEFAULT_PRIORITY
    if isinstance(raw, dict):
        text = raw["text"]
        priority = raw.get("priority", DEFAULT_PRIORITY)
        if isinstance(text, str):
            return [text], priority
        if isinstance(text, list):
            for line in text:
                if not isinstance(line, str):
                    raise TypeError(
                        f"startup 'text' list items must be strings, got {line!r}"
                    )
            return list(text), priority
        raise TypeError(f"startup 'text' must be a string or list of strings, got {text!r}")
    raise TypeError(f"startup item must be a string or mapping, got {raw!r}")


def resolve_startup_lines(items: list) -> list[str]:
    """Normalize every `startup:` item and stable-sort by priority (low to
    high), preserving merge/append order among equal priorities."""
    normalized = [normalize_startup_item(item) for item in items]
    normalized.sort(key=lambda pair: pair[1])
    return [line for lines, _priority in normalized for line in lines]


def render_startup_sequence(
    lines: list[str],
    binary: str,
    args: list[str],
    *,
    config: dict | None = None,
    assigns: AssignTable | None = None,
) -> str:
    launch_args = " ".join(shlex.quote(a) for a in args) if args else ""
    jinja_env = build_environment(assigns or AssignTable())
    rendered = [
        jinja_env.from_string(line).render(
            binary=binary, args=launch_args, argsarr=args, config=config or {}
        )
        for line in lines
    ]
    return "\n".join(rendered) + "\n"


def write_startup_sequence(
    target,
    items: list,
    binary: str,
    args: list[str],
    *,
    config: dict | None = None,
    assigns: AssignTable | None = None,
) -> None:
    if not items:
        # startup: [] -- caller is expected to supply s/startup-sequence via copy: instead
        return
    lines = resolve_startup_lines(items)
    content = render_startup_sequence(lines, binary, args, config=config, assigns=assigns)
    target.writer.write_bytes(target.root_path / "s" / "startup-sequence", content.encode())
