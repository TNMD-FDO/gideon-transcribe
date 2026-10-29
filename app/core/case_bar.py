"""The case bar (v1.171.0; the drawing docs/spec/mockups/phase-10-case-bar.html).

The Case page's tabs, drawn from one helper, so that every page that
belongs to a Case shows them at its top: the case's name, then the tabs in
the order the case page has them, each with its count, the tab the page
lives under lit and the page's own name after it. The case page draws its
own bar from the same helper, so there is one bar and not two that drift
apart. A page opened in a window of its own shows none, as it shows no rail.

The counts are a handful of cheap count queries; nothing here is stored.
"""

from __future__ import annotations

from django.urls import reverse

from core import documents, incidents, notes, proposals, settings_store


def _tab(key: str, name: str, icon: str, url: str, count=None, on: str = "") -> dict:
    return {
        "key": key,
        "name": name,
        "icon": icon,
        "url": url,
        "count": count,
        "count_shown": count is not None,
        "on": key == on,
    }


def bar(case, *, on: str, here: str = "", counts: dict | None = None) -> dict:
    """The bar for a page of the case: `on` is the tab the page lives under
    (the case page passes the tab it shows), `here` the page's own name,
    empty on the case page itself. The case page hands the counts it has
    already gathered in `counts`, so it asks nothing twice; a deeper page
    gives none and the helper counts."""
    given = counts or {}

    def count(key: str, ask):
        return given[key] if key in given else ask()

    base = reverse("case", args=[case.pk])
    tabs = [
        _tab(
            "recordings",
            "Recordings",
            "play",
            base,
            count("recordings", lambda: case.recordings.count()),
            on,
        ),
        _tab("search", "Search", "search", f"{base}?tab=search", None, on),
    ]
    if proposals.tab_offered():
        tabs.append(
            _tab(
                "proposed",
                "Proposed events",
                "note",
                f"{base}?tab=proposed",
                count(
                    "proposed",
                    lambda: proposals.Proposal.objects.filter(
                        case=case, state=proposals.WAITING
                    ).count(),
                ),
                on,
            )
        )
    tabs.append(
        _tab(
            "notes",
            "Notes",
            "note",
            f"{base}?tab=notes",
            count("notes", lambda: notes.count(case)),
            on,
        )
    )
    if documents.on():
        tabs.append(
            _tab(
                "documents",
                "Documents",
                "document",
                f"{base}?tab=documents",
                count("documents", lambda: documents.count(case)),
                on,
            )
        )
    if incidents.on():
        tabs.append(
            _tab(
                "incidents",
                "Incidents",
                "camera",
                f"{base}?tab=incidents",
                count(
                    "incidents",
                    lambda: incidents.Incident.objects.filter(case=case).count(),
                ),
                on,
            )
        )
    if settings_store.get("clips_available"):
        from core.case_pages import _clips_count

        tabs.append(
            _tab(
                "clips",
                "Clips",
                "clip",
                f"{base}?tab=clips",
                count("clips", lambda: _clips_count(case)),
                on,
            )
        )
    named = count("speakers", lambda: case.people.count())
    tabs.append(
        _tab(
            "speakers",
            "Speakers",
            "people",
            f"{base}?tab=speakers",
            named if named else "0 named",
            on,
        )
    )
    tabs.append(_tab("details", "Details", "info", f"{base}?tab=details", None, on))
    return {
        "name": case.name,
        "url": base,
        "cases_url": reverse("cases"),
        "on": on,
        "here": here,
        "tabs": tabs,
    }
