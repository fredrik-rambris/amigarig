"""Copy-item handlers: expand one resolved item into zero or more concrete writes."""
from __future__ import annotations

from dataclasses import dataclass

from .copyspec import ResolvedCopyItem
from .fsutil import CaseInsensitiveResolver


@dataclass
class HandlerContext:
    ci: CaseInsensitiveResolver


def copy(item: ResolvedCopyItem, ctx: HandlerContext) -> list[ResolvedCopyItem]:
    return [item]


def copy_font(item: ResolvedCopyItem, ctx: HandlerContext) -> list[ResolvedCopyItem]:
    """`Garamond/9` -> the bitmap file itself, plus the sibling `Garamond.font`."""
    font_name_source = item.source.parent.name
    fonts_root_source = item.source.parent.parent
    font_file_source = ctx.ci.resolve(fonts_root_source, f"{font_name_source}.font")

    results = [item]
    if font_file_source is not None and font_file_source.exists():
        font_name_dest = item.dest.parent.name
        fonts_root_dest = item.dest.parent.parent
        results.append(
            ResolvedCopyItem(
                source=font_file_source,
                dest=fonts_root_dest / f"{font_name_dest}.font",
            )
        )
    return results


def copy_icons(item: ResolvedCopyItem, ctx: HandlerContext) -> list[ResolvedCopyItem]:
    """If `<source>.info` exists, copy it alongside as `<dest>.info`."""
    icon_source = ctx.ci.resolve(item.source.parent, item.source.name + ".info")
    results = [item]
    if icon_source is not None and icon_source.exists():
        results.append(
            ResolvedCopyItem(
                source=icon_source,
                dest=item.dest.with_name(item.dest.name + ".info"),
            )
        )
    return results


HANDLERS = {
    "copy": copy,
    "copy_font": copy_font,
    "copy_icons": copy_icons,
}


def run_handlers(
    item: ResolvedCopyItem, handler_names: list[str], ctx: HandlerContext
) -> list[ResolvedCopyItem]:
    names = handler_names or ["copy"]
    items = [item]
    for name in names:
        handler = HANDLERS[name]
        items = [expanded for i in items for expanded in handler(i, ctx)]
    return items
