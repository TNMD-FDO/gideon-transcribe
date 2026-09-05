"""What the templates must not do, checked without rendering any of them.

These are mistakes that compile, pass every other check, and show themselves
only as text on a page in front of somebody.
"""

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def every_template():
    return sorted(TEMPLATES.rglob("*.html"))


def test_there_are_templates_to_check():
    # A test that silently checks nothing is worse than no test.
    assert len(every_template()) > 5


def test_no_short_comment_spans_more_than_one_line():
    """Django's {# #} is one line only; a longer one prints itself on the page.

    This has happened twice: a note to the next reader appeared as text on the
    sign-out page, and the users page showed Admins a note about its quota
    form for as long as that note existed. A longer comment needs
    {% comment %} ... {% endcomment %}.
    """
    printed = []
    for template in every_template():
        text = template.read_text(encoding="utf-8")
        for match in re.finditer(r"\{#", text):
            rest = text[match.start() :]
            end = rest.find("\n")
            line = rest[: end if end != -1 else len(rest)]
            if "#}" not in line:
                number = text[: match.start()].count("\n") + 1
                printed.append(f"{template.name}:{number}: {line.strip()[:60]}")

    assert not printed, "these comments would print themselves:\n" + "\n".join(printed)


def test_every_block_tag_is_closed():
    """A stray {% if %} or {% for %} is a 500 on a page, not a lint error."""
    pairs = {
        "if": "endif",
        "for": "endfor",
        "block": "endblock",
        "comment": "endcomment",
        "with": "endwith",
        "spaceless": "endspaceless",
    }
    trouble = []
    for template in every_template():
        text = template.read_text(encoding="utf-8")
        stack = []
        for match in re.finditer(r"\{%-?\s*(\w+)", text):
            tag = match.group(1)
            if tag in pairs:
                stack.append((tag, text[: match.start()].count("\n") + 1))
            elif tag in pairs.values():
                wanted = [name for name, close in pairs.items() if close == tag][0]
                if not stack:
                    trouble.append(f"{template.name}: {tag} with nothing open")
                elif stack[-1][0] != wanted:
                    was, line = stack[-1]
                    trouble.append(
                        f"{template.name}: {tag} closes {was} opened at line {line}"
                    )
                    stack.pop()
                else:
                    stack.pop()
        for tag, line in stack:
            trouble.append(f"{template.name}:{line}: {tag} is never closed")

    assert not trouble, "\n".join(trouble)


# The finish: the icon set and the typeface ------------------------------------------

STATIC = Path(__file__).resolve().parent.parent / "static"


def sprite_names():
    text = (TEMPLATES / "icons.html").read_text(encoding="utf-8")
    return set(re.findall(r'id="i-([a-z0-9-]+)"', text))


def test_every_icon_a_page_or_script_asks_for_is_in_the_sprite():
    """A missing symbol draws nothing, silently, so the names are checked here."""
    have = sprite_names()
    assert len(have) > 20
    asked = set()
    for template in every_template():
        asked |= set(
            re.findall(r'\{% icon "([a-z0-9-]+)"', template.read_text(encoding="utf-8"))
        )
    for script in STATIC.glob("*.js"):
        text = script.read_text(encoding="utf-8")
        asked |= set(re.findall(r"#i-([a-z0-9-]+)", text))
        asked |= set(re.findall(r'icon\("([a-z0-9-]+)"\)', text))
    assert asked, "no page asks for an icon, which cannot be right"
    assert asked <= have, asked - have


def test_the_sprite_is_on_every_page_and_no_glyph_stands_for_an_icon():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert '{% include "icons.html" %}' in base
    assert 'class="brand"' in base and 'class="mark"' in base
    # The typewriter glyphs the icons replaced, which rendered differently on
    # every machine, are gone from the pages and the scripts.
    glyphs = [
        "✎",
        "&#9998;",
        "&#9654;",
        "&#8597;",
        "&#9662;",
        "&#9986;",
        "&#9776;",
        "&#8630;",
        "&#9789;",
        "&#10003;",
    ]
    for path in list(every_template()) + list(STATIC.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for glyph in glyphs:
            assert glyph not in text, f"{path.name} still draws {glyph}"


def test_the_typeface_ships_with_the_app_under_its_licence():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    for face in re.findall(r'url\("fonts/([^"]+)"\)', css):
        assert (STATIC / "fonts" / face).exists(), face
    assert '"IBM Plex Sans"' in css and '"IBM Plex Mono"' in css
    licence = (STATIC / "fonts" / "OFL-ibm-plex.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in licence and "IBM Corp" in licence
    # The stylesheet has no colour of its own outside the token blocks: every
    # rule reads a token. Hex colours may appear only in the :root palettes.
    body = css[css.index("/* The elements") :]
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", body.replace("#i-", "")), (
        "a colour written into a rule"
    )


def test_no_browser_pop_up_is_left_and_every_confirm_names_its_action():
    """The app's dialogs replaced the browser's; a template that asks first
    says what the action is, so the button in the dialog never just says OK."""
    for path in list(every_template()) + [
        p for p in STATIC.glob("*.js") if p.name != "ui.js"
    ]:
        text = path.read_text(encoding="utf-8")
        for bad in (
            "window.confirm(",
            "window.prompt(",
            "window.alert(",
            "return confirm(",
        ):
            assert bad not in text, f"{path.name} still uses {bad}"
    for template in every_template():
        text = template.read_text(encoding="utf-8")
        for match in re.finditer(r'data-confirm="', text):
            tail = text[match.start() : match.start() + 700]
            assert "data-confirm-ok=" in tail, (
                f"{template.name}: a confirm without its action word"
            )
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert "ui.js" in base and base.index("ui.js") < base.index("theme.js")


def test_every_list_page_has_an_empty_state_and_hints_can_be_dismissed():
    for name in (
        "recordings.html",
        "cases.html",
        "clips.html",
        "case.html",
        "recycle-bin.html",
    ):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert '{% include "empty.html"' in text, f"{name} has no empty state"
    for name in ("recordings.html", "case.html", "viewer.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        for match in re.finditer(r'class="hint" data-hint="([a-z-]+)"', text):
            block = text[match.start() : match.start() + 600]
            assert 'class="ghost tiny dismiss"' in block, (
                f"{name}: hint {match.group(1)} cannot be dismissed"
            )


def test_a_clip_span_is_read_as_clocks_and_words():
    """Raw seconds ("724.0s to 820.5s, 97s") are for machines; a person reads
    two clocks and a length in words."""
    from core.clip_pages import spell

    assert spell(45) == "45 s"
    assert spell(97.4) == "1 min 37 s"
    assert spell(120) == "2 min"
    assert spell(3720) == "1 h 2 min"
    clips = (TEMPLATES / "clips.html").read_text(encoding="utf-8")
    assert "floatformat:1 }}s" not in clips
    assert "{{ clip.span }}" in clips and "{{ clip.length }}" in clips


def test_the_users_table_fits_beside_its_pane():
    users = (TEMPLATES / "panel" / "users.html").read_text(encoding="utf-8")
    head = users[users.index("<thead>") : users.index("</thead>")]
    assert head.count("<th>") == 7
    assert 'colspan="7"' in users and 'colspan="10"' not in users


def test_every_template_that_draws_an_icon_loads_the_tag():
    """A template that uses {% icon %} without {% load icons %} compiles only
    when rendered, so the mistake reaches CI as a page that raises."""
    for template in every_template():
        text = template.read_text(encoding="utf-8")
        if "{% icon " in text and template.name != "icons.html":
            loads = re.findall(r"\{% load ([^%]*)%\}", text)
            assert any("icons" in one for one in loads), (
                f"{template.name} draws an icon without loading the tag"
            )
