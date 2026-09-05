"""The icon set on a page: {% icon "play" %}.

One sprite of line icons (templates/icons.html) is included once in every
page's body. This tag draws one of them, by the name of what it means, sized
to the text beside it and hidden from screen readers, since the word next to
it carries the meaning. A name the sprite does not have raises at render
time, in tests, rather than drawing nothing on a page.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from django import template
from django.utils.html import format_html

register = template.Library()

SPRITE = Path(__file__).resolve().parent.parent.parent / "templates" / "icons.html"


@lru_cache(maxsize=1)
def names() -> frozenset[str]:
    """Every symbol id in the sprite, without its i- prefix."""
    text = SPRITE.read_text(encoding="utf-8")
    return frozenset(re.findall(r'id="i-([a-z0-9-]+)"', text))


@register.simple_tag
def icon(name: str, extra_class: str = "") -> str:
    if name not in names():
        raise template.TemplateSyntaxError(f"there is no icon called {name!r}")
    classes = f"i {extra_class}".strip()
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false">'
        '<use href="#i-{}"></use></svg>',
        classes,
        name,
    )
