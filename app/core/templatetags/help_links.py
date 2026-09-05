"""Where Help goes from each page.

Every page carries a Help link and a "?" that opens the guide beside the page.
Both go to the same place: the user guide, at the section about the page the
person is on, or the admin guide from the Panel. The section anchors are the
ids Python-Markdown gives the guide's headings (see core/guides.py), so this
table and the guide's headings have to agree; a test checks that they do.
"""

from django import template
from django.urls import reverse

register = template.Library()

# The page word each view puts in its context, and the user guide heading it
# is about. A page not listed here opens the guide at the top.
SECTIONS = {
    "recordings": "your-recordings",
    "upload": "uploading-a-batch",
    "viewer": "reading-a-transcript",
    "clips": "clips",
    "cases": "cases",
}


@register.simple_tag
def help_url(page) -> str:
    """The address Help opens from this page: the guide, at the right section."""
    if page == "panel":
        return reverse("panel-help")
    anchor = SECTIONS.get(page or "")
    return reverse("help") + (f"#{anchor}" if anchor else "")
