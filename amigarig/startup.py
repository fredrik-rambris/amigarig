"""Renders the s/startup-sequence file from merged `boot.startup` items.

`startup` is a plain mergeable list (subject to the same `+startup`
append rule as any other list-valued key). "Conditional" lines are just a
question of which config layer contributes them.

Each item is either a bare string (line = itself, priority =
DEFAULT_PRIORITY, enabled) or a mapping `{text, priority, enabled, name}`
where `text` is a string or flat list of strings (a block sharing one
priority and one `enabled`) -- see `normalize_startup_item`. `+startup`
still controls which layer's items make it into the merged list (and
breaks ties, since the final sort is stable); the numeric priority then
decides final line order, low to high, once every layer has contributed.

`enabled` (default `true`) is a bool, or a Jinja string rendered with the
same `config`/`assign(...)` context as line content (see
`resolve_startup_lines`) -- e.g. `enabled: "{{ config.fsuae.chipset ==
'aga' }}"`. A disabled item's whole block is dropped before sorting/
rendering, same as it never having been in the list at all.

`name` (default: unset), if given, wraps the block in `;BEGIN <name>` /
`;END <name>` AmigaDOS comment lines -- purely cosmetic, for reading a
generated startup-sequence; has no effect on priority/enabled/rendering.

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
DEFAULT_ENABLED = True


def normalize_startup_item(raw) -> tuple[list[str], int, bool | str]:
    """Bare string or {text, priority, enabled, name} mapping -> (lines,
    priority, enabled). `enabled` is returned unevaluated (bool or Jinja
    string) -- see `_evaluate_enabled`.

    `text` may be a single string or a flat list of strings (a block of
    lines sharing one priority) -- no nesting: every element must itself
    be a plain string. `name` (default: unset), if given, wraps the block
    in `;BEGIN <name>` / `;END <name>` AmigaDOS comment lines -- purely
    cosmetic (for reading a generated startup-sequence), no effect on
    priority/enabled/rendering.
    """
    if isinstance(raw, str):
        return [raw], DEFAULT_PRIORITY, DEFAULT_ENABLED
    if isinstance(raw, dict):
        text = raw["text"]
        priority = raw.get("priority", DEFAULT_PRIORITY)
        enabled = raw.get("enabled", DEFAULT_ENABLED)
        name = raw.get("name")
        if not isinstance(enabled, (bool, str)):
            raise TypeError(f"startup 'enabled' must be a bool or string, got {enabled!r}")
        if name is not None and not isinstance(name, str):
            raise TypeError(f"startup 'name' must be a string, got {name!r}")
        if isinstance(text, str):
            lines = [text]
        elif isinstance(text, list):
            for line in text:
                if not isinstance(line, str):
                    raise TypeError(
                        f"startup 'text' list items must be strings, got {line!r}"
                    )
            lines = list(text)
        else:
            raise TypeError(f"startup 'text' must be a string or list of strings, got {text!r}")
        if name:
            lines = [f";BEGIN {name}", *lines, f";END {name}"]
        return lines, priority, enabled
    raise TypeError(f"startup item must be a string or mapping, got {raw!r}")


def _evaluate_enabled(enabled: bool | str, jinja_env, config: dict) -> bool:
    if isinstance(enabled, bool):
        return enabled
    rendered = jinja_env.from_string(enabled).render(config=config).strip()
    normalized = rendered.lower()
    if normalized in ("true", "1", "yes", "on"):
        return True
    if normalized in ("false", "0", "no", "off", ""):
        return False
    # anything else -- fall back to plain string truthiness
    return bool(rendered)


def resolve_startup_lines(
    items: list,
    *,
    config: dict | None = None,
    assigns: AssignTable | None = None,
) -> list[str]:
    """Normalize every `startup:` item, drop any whose `enabled` evaluates
    false, and stable-sort what's left by priority (low to high),
    preserving merge/append order among equal priorities."""
    jinja_env = build_environment(assigns or AssignTable())
    normalized = [normalize_startup_item(item) for item in items]
    active = [
        (lines, priority)
        for lines, priority, enabled in normalized
        if _evaluate_enabled(enabled, jinja_env, config or {})
    ]
    active.sort(key=lambda pair: pair[1])
    return [line for lines, _priority in active for line in lines]


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
    lines = resolve_startup_lines(items, config=config, assigns=assigns)
    content = render_startup_sequence(lines, binary, args, config=config, assigns=assigns)
    target.writer.write_bytes(target.root_path / "s" / "startup-sequence", content.encode())
