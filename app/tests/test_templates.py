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
