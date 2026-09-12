"""The Speakers page: one Recording's Speakers, each a card, while it plays.

Phase 5, chapter 1. The page's one job is saying who each Speaker is. Every
number on it is worked out here from the Segments the Transcript already
holds: how many lines a Speaker has and how long they talk, the three
Samples to hear a voice by, and the hint that a small Speaker never talks
while a bigger one does. Nothing is stored for it, and every change the page
makes goes through the viewer's own routes.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from core import cases, viewer
from core.recordings import Recording

# Samples: up to three lines a Speaker spoke, one from each third of their
# lines, the one nearest four seconds long among those between two and eight
# seconds, and the longest of the third when none is.
SAMPLES = 3
SAMPLE_BEST = 4.0
SAMPLE_SHORTEST = 2.0
SAMPLE_LONGEST = 8.0
# Two lines that touch within this are not an overlap: the engine's edges
# are not that exact.
TOUCHING = 0.5
# With more Speakers than this, the ones who talk for under a minute fold into
# one Lane on the page.
MANY = 6
SMALL_SECONDS = 60.0


@dataclass
class Line:
    start: float
    end: float

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)


def is_named(name: str) -> bool:
    """A Speaker is named once its name is not the engine's own label."""
    from core.assistant import _is_a_label

    return bool(name) and not _is_a_label(name)


def pick_samples(lines: list[Line]) -> list[Line]:
    """The Samples of one Speaker, by the rule above; all of them when few."""
    if len(lines) <= SAMPLES:
        return list(lines)
    chosen = []
    step = len(lines) / SAMPLES
    for third in range(SAMPLES):
        part = lines[int(third * step) : int((third + 1) * step)] or [
            lines[min(len(lines) - 1, int(third * step))]
        ]
        fits = [one for one in part if SAMPLE_SHORTEST <= one.length <= SAMPLE_LONGEST]
        if fits:
            chosen.append(min(fits, key=lambda one: abs(one.length - SAMPLE_BEST)))
        else:
            chosen.append(max(part, key=lambda one: one.length))
    return chosen


def overlaps(mine: list[Line], theirs: list[Line]) -> bool:
    """Whether two Speakers ever talk at once, both lists in time order."""
    i = j = 0
    while i < len(mine) and j < len(theirs):
        shared = min(mine[i].end, theirs[j].end) - max(mine[i].start, theirs[j].start)
        if shared > TOUCHING:
            return True
        if mine[i].end < theirs[j].end:
            i += 1
        else:
            j += 1
    return False


def talking_text(seconds: float) -> str:
    whole = int(round(seconds))
    if whole < 60:
        return f"{whole} s"
    return f"{whole // 60} min {whole % 60:02d} s"


def short_clock(seconds: float) -> str:
    """A time as the page's script writes it: 0:07, and 1:02:07 past an hour."""
    whole = max(0, int(seconds or 0))
    minutes, rest = divmod(whole, 60)
    if minutes >= 60:
        return f"{minutes // 60}:{minutes % 60:02d}:{rest:02d}"
    return f"{minutes}:{rest:02d}"


def cards(transcript, speakers: list[dict]) -> list[dict]:
    """One card per Speaker, in the order they first spoke.

    `speakers` is the viewer's own list (name, colour, role), so a Speaker is
    the same colour here as on the recording page.
    """
    lines: dict[str, list[Line]] = {}
    labels: dict[str, str] = {}
    for start, end, name, label in (
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .order_by("start", "id")
        .values_list("start", "end", "speaker", "speaker_label")
    ):
        lines.setdefault(name, []).append(Line(start, end))
        labels.setdefault(name, label)

    looks = {one["name"]: one for one in speakers}
    made = []
    for name in sorted(lines, key=lambda one: lines[one][0].start):
        mine = lines[name]
        talking = sum(one.length for one in mine)
        # The fragment hint: never talks while another, bigger Speaker does.
        # Where several qualify, the one with the most lines is named.
        other = ""
        for candidate in sorted(lines, key=lambda one: -len(lines[one])):
            if candidate == name or len(lines[candidate]) <= len(mine):
                continue
            if not overlaps(mine, lines[candidate]):
                other = candidate
                break
        made.append(
            {
                "name": name,
                "colour": looks.get(name, {}).get("colour", ""),
                "role": looks.get(name, {}).get("role", ""),
                "label": labels.get(name, ""),
                "named": is_named(name),
                "lines": len(mine),
                "talking": round(talking, 1),
                "talking_text": talking_text(talking),
                "first": mine[0].start,
                "first_clock": short_clock(mine[0].start),
                "small": talking < SMALL_SECONDS,
                "samples": [
                    {
                        "start": one.start,
                        "end": one.end,
                        "clock": short_clock(one.start),
                    }
                    for one in pick_samples(mine)
                ],
                "hint_other": other,
            }
        )
    return made


def context(request: HttpRequest, recording: Recording, *, in_window: bool) -> dict:
    """What the page is drawn from, on its own or in a window."""
    page = viewer._page_context(request, recording)
    transcript = page["transcript"]
    made = cards(transcript, page["speakers"]) if transcript is not None else []
    named = sum(1 for one in made if one["named"])
    return {
        "page": "viewer",
        "in_window": in_window,
        "cards": made,
        "named": named,
        "total": len(made),
        "fold_small": len(made) > MANY,
        "back_url": reverse("viewer", args=[recording.pk]),
        "window_url": reverse("viewer-window", args=[recording.pk, "speakers"]),
        **page,
    }


@login_required
def page(request: HttpRequest, recording_id) -> HttpResponse:
    """The Speakers page of one Recording."""
    recording = viewer.open_recording(request, recording_id)
    if recording is None:
        return redirect(reverse("home"))
    cases.used(recording, by=request.user)
    return render(
        request, "speakers-page.html", context(request, recording, in_window=False)
    )


def route(request: HttpRequest, recording_id):
    """One address, two jobs: GET is the page, POST is the viewer's rename and merge."""
    if request.method == "POST":
        return viewer.speakers(request, recording_id)
    return page(request, recording_id)
