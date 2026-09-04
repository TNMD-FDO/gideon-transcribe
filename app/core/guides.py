"""The two guides the app serves, rendered from the Markdown in docs/.

The user guide is at /help/ and the admin guide behind the Help link in the
Admin panel's rail. Both are the repository's own Markdown files, so the same
text is read on GitHub and inside the app, and nobody who uses the app needs
GitHub to read it.

They are rendered when the image is built, by the render_guides command, and
the result is kept beside the source as JSON. A guide that will not render
fails the build and never reaches a server. On a workstation there is no
rendered copy, so the Markdown is rendered on the way to the page instead;
the text is the same either way, which is the point (ADR 0012).

The HTML that comes out is marked safe for the template. It is this
repository's own Markdown and nothing a user typed, and Markdown is not run
over anything else.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import markdown
from django.conf import settings

USER = "user-guide"
ADMIN = "admin-guide"
NAMES = (USER, ADMIN)

# Headings two and three deep go in the contents list. The one top heading is
# the guide's title and the fourth level is too fine to navigate by.
CONTENTS_DEPTH = "2-3"


@dataclass(frozen=True)
class Guide:
    title: str
    contents: str
    body: str


def source_of(name: str) -> Path:
    return Path(settings.GUIDES_DIR) / f"{name}.md"


def rendered_of(name: str) -> Path:
    return Path(settings.GUIDES_DIR) / f"{name}.rendered.json"


def render(text: str) -> Guide:
    """Markdown to a Guide: its title, its contents list, and its body."""
    engine = markdown.Markdown(
        extensions=["toc", "tables", "fenced_code"],
        extension_configs={"toc": {"toc_depth": CONTENTS_DEPTH, "title": ""}},
    )
    body = engine.convert(text)
    return Guide(title=_title_of(text), contents=engine.toc, body=body)


def _title_of(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Guide"


def write_rendered(name: str) -> Path:
    """Render one guide and keep the result beside it, for the image."""
    guide = render(source_of(name).read_text(encoding="utf-8"))
    out = rendered_of(name)
    out.write_text(json.dumps(asdict(guide), ensure_ascii=False), encoding="utf-8")
    return out


def load(name: str) -> Guide:
    """The guide as the page shows it: the rendered copy, or rendered now."""
    if name not in NAMES:
        raise KeyError(name)
    kept = rendered_of(name)
    if kept.is_file():
        return Guide(**json.loads(kept.read_text(encoding="utf-8")))
    return render(source_of(name).read_text(encoding="utf-8"))
