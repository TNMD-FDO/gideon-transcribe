"""Incidents (Phase 6 chapter 1): the cameras of one event, on one clock.

An Incident is a named group of a Case's videos that ran at the same time.
Each camera in it is placed on the Incident clock, the time of day the
cameras burn into their pictures: from its checked stamp, from its sound
matched against a placed camera, from the time its file carries, or by a
person's hand, and the page says which. The Wall plays the placed cameras in
step in the browser; nothing here re-encodes or stores a file. Everything an
Incident is, is rows: this module's two tables and the stamp on the
Recording.

The words are the glossary's: Incident, Incident clock, Placed, Wall. The
pages say camera for a video in an Incident.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from core import audit, settings_store

log = logging.getLogger("transcribe.incidents")

CATEGORY = audit.Category.CASES

# How a camera came to sit where it does (the Placed pill).
NOT_PLACED = ""
CLOCK = "clock"
CLOCK_UNCHECKED = "clock_unchecked"
SOUND = "sound"
FILE = "file"
HAND = "hand"
# The app's best guess for a camera with no clock (v1.60.0): its file's time
# when the Incident has a clock and the file carries one, else the
# Incident's start. On the wall, marked Not synced yet, until Sync fixes it.
GUESS = "guess"

PLACED_WORDS = {
    NOT_PLACED: "Not synced yet",
    GUESS: "Not synced yet",
    CLOCK: "From its clock, checked",
    CLOCK_UNCHECKED: "From its clock, unchecked",
    SOUND: "Matched by sound",
    FILE: "From its file, unchecked",
    HAND: "Synced by hand",
}
PLACED_TONES = {
    NOT_PLACED: "warn",
    GUESS: "warn",
    CLOCK: "ok",
    CLOCK_UNCHECKED: "warn",
    SOUND: "ok",
    FILE: "warn",
    HAND: "",
}
# The states a person has settled, as against the app's guess.
SYNCED = (CLOCK, CLOCK_UNCHECKED, SOUND, FILE, HAND)

# The sound match's states, on the camera row while one runs.
MATCH_QUEUED = "queued"
MATCH_RUNNING = "running"
MATCH_DONE = "done"
MATCH_FAILED = "failed"

# A match this strong is applied; a weaker one is shown and left to the
# person. Left to the build by the chapter; the research note records the
# probe that set it.
STRONG_MATCH = 1.5

# How an Incident came to be.
FROM_OFFER = "offer"
BY_HAND = "hand"

DAY = 86400.0


# The switches --------------------------------------------------------------------


def on() -> bool:
    """Incidents as a whole: inside Cases, and the office's own switch."""
    from core import cases

    return bool(cases.folder_management_on() and settings_store.get("incidents"))


def proposed_on() -> bool:
    return bool(on() and settings_store.get("incidents_proposed"))


def wall_size() -> int:
    return int(settings_store.get("incidents_wall"))


def most_cameras() -> int:
    return int(settings_store.get("incidents_most_cameras"))


def stamp_early_on() -> bool:
    from core import assistant

    return bool(
        on() and assistant.stamp_on() and settings_store.get("incidents_stamp_early")
    )


def sound_match_on() -> bool:
    return bool(on() and settings_store.get("incidents_sound_match"))


# The rows -------------------------------------------------------------------------


class Incident(models.Model):
    """One event's cameras in one Case, on one clock."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="incidents"
    )
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created = models.DateTimeField(auto_now_add=True)
    # From the case page's offer, or New incident.
    how = models.CharField(max_length=10, default=BY_HAND)
    # The Incident clock: the second of the day that a camera's starts_at of
    # zero falls on, from the first camera placed from a checked stamp, with
    # the date as that stamp printed it. Null while no camera has a clock, in
    # which case the page counts from the first camera.
    clock_zero = models.FloatField(null=True, blank=True)
    clock_date = models.CharField(max_length=40, blank=True, default="")
    # The camera rows on the Wall, in order, once a person has swapped one;
    # empty means the clock's order.
    wall = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["created"]

    def __str__(self) -> str:
        return self.name

    def has_clock(self) -> bool:
        return self.clock_zero is not None

    def url(self) -> str:
        return reverse("incident", args=[self.case_id, self.pk])


class IncidentCamera(models.Model):
    """One video in an Incident, and where it sits on the clock."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        Incident, on_delete=models.CASCADE, related_name="cameras"
    )
    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="incident_cameras"
    )
    # Seconds on the Incident clock at which this camera starts; null while
    # not placed.
    starts_at = models.FloatField(null=True, blank=True)
    placed = models.CharField(max_length=20, blank=True, default=NOT_PLACED)
    placed_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    placed_at = models.DateTimeField(null=True, blank=True)
    # The sound match, while one runs and after: against which camera, what
    # it found, and how clearly.
    match_state = models.CharField(max_length=10, blank=True, default="")
    match_against = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    match_lag = models.FloatField(null=True, blank=True)
    match_strength = models.FloatField(null=True, blank=True)
    match_reason = models.CharField(max_length=60, blank=True, default="")
    added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "recording"], name="one_camera_per_recording"
            )
        ]

    def __str__(self) -> str:
        return self.recording.title

    def is_placed(self) -> bool:
        """On the clock, by a person's or the app's doing: on the wall."""
        return self.starts_at is not None and self.placed != NOT_PLACED

    def is_synced(self) -> bool:
        """Settled, as against the app's guess."""
        return self.starts_at is not None and self.placed in SYNCED

    def length(self) -> float:
        return float(self.recording.duration_seconds or 0.0)

    def ends_at(self) -> float | None:
        return None if self.starts_at is None else self.starts_at + self.length()

    def camera_id(self) -> str:
        """The id the camera burned into its picture, else the recording's title."""
        stamp = self.recording.stamp or {}
        return (stamp.get("camera") or "").strip() or self.recording.title


# The stamp, as a clock -------------------------------------------------------


def is_video(recording) -> bool:
    """A recording with a picture, from the copy when there is one, else the probe."""
    from core import media

    playback = recording.playback_path()
    if playback is not None:
        return playback.suffix == ".mp4"
    try:
        return media.video_stream(recording.probe or {}) is not None
    except Exception:  # noqa: BLE001 - an odd probe is not a picture
        return False


def clock_zero_of(recording) -> float | None:
    """The second of the day the recording started at, by its stamp; else None."""
    from core import prompts

    stamp = recording.stamp or {}
    if not stamp.get("time"):
        return None
    seconds = prompts.clock_seconds(stamp.get("time", ""))
    if seconds is None:
        return None
    return float((seconds - int(float(stamp.get("at", 0.0)))) % DAY)


def stamp_checked(recording) -> bool:
    return bool((recording.stamp or {}).get("checked"))


def stamp_words(recording) -> tuple[str, str]:
    """The case page's Clock in the picture cell: the words and the pill's tone."""
    if not is_video(recording):
        return "", ""
    stamp = recording.stamp
    if stamp is None:
        return "not read yet", ""
    if not stamp.get("time"):
        # Many videos carry no clock; that is not a fault, so nothing shows.
        return "", ""
    date = (stamp.get("date") or "").strip()
    when = f"{date} {stamp['time']}".strip()
    return (
        (f"{when}, checked", "ok")
        if stamp.get("checked")
        else (f"{when}, unchecked", "warn")
    )


def hms(seconds: float) -> str:
    seconds = int(round(seconds)) % int(DAY)
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def elapsed(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def time_of_day(incident: Incident, at: float) -> str:
    """The clock's words at `at` seconds into the Incident."""
    if incident.clock_zero is None:
        return elapsed(at)
    return hms(incident.clock_zero + at)


def _wrapped(seconds: float) -> float:
    """A difference of clock times, taken the short way round midnight."""
    while seconds < -DAY / 2:
        seconds += DAY
    while seconds > DAY / 2:
        seconds -= DAY
    return seconds


def file_time_of(recording) -> tuple[str, float | None]:
    """The moment the file says recording began, in the office's own time.

    Cameras write it in UTC into the container; the probe keeps it. Shown as
    the clock would show it, and offered as a way to place the camera, marked
    unchecked because nobody has checked it against the picture.
    """
    tags = ((recording.probe or {}).get("format") or {}).get("tags") or {}
    text = tags.get("creation_time") or ""
    if not text:
        return "", None
    try:
        when = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return "", None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    local = timezone.localtime(when)
    return local.strftime("%d %b %Y %H:%M:%S"), float(
        local.hour * 3600 + local.minute * 60 + local.second
    )


# The offer -----------------------------------------------------------------------


def _span(recording):
    """(date, start, end) on the clock for a video with a checked stamp, else None."""
    if not is_video(recording) or not stamp_checked(recording):
        return None
    zero = clock_zero_of(recording)
    if zero is None:
        return None
    date = ((recording.stamp or {}).get("date") or "").strip()
    return date, zero, zero + float(recording.duration_seconds or 0.0)


def _chained(spans: list) -> list[list]:
    """Recordings whose spans overlap, chained into groups.

    Takes [(recording, date, start, end)]; a group is two or more.
    """
    groups: list[list] = []
    for date in sorted({one[1] for one in spans}):
        todays = sorted((one for one in spans if one[1] == date), key=lambda o: o[2])
        current: list = []
        reach = None
        for item in todays:
            if current and reach is not None and item[2] <= reach:
                current.append(item)
                reach = max(reach, item[3])
            else:
                if len(current) > 1:
                    groups.append(current)
                current = [item]
                reach = item[3]
        if len(current) > 1:
            groups.append(current)
    return groups


def _new_key(recordings) -> str:
    return "new:" + ",".join(sorted(str(one.pk) for one in recordings))


def _add_key(incident: Incident, recording) -> str:
    return f"add:{incident.pk}:{recording.pk}"


def offers(case) -> list[dict]:
    """What the case page offers: groups to make, and videos to add to an Incident."""
    if not proposed_on():
        return []
    declined = set(case.declined_offers or [])
    in_one = set(
        IncidentCamera.objects.filter(incident__case=case).values_list(
            "recording_id", flat=True
        )
    )
    loose = [one for one in case.recordings.all() if one.pk not in in_one]
    spans = []
    for recording in loose:
        span = _span(recording)
        if span is not None:
            spans.append((recording, *span))
    offered: list[dict] = []
    incidents = list(case.incidents.all())
    # A video that ran during an existing Incident is offered to it first.
    taken: set = set()
    for incident in incidents:
        low, high = span_of(incident)
        if low is None or not incident.has_clock():
            continue
        for recording, date, start, end in spans:
            if date != incident.clock_date or recording.pk in taken:
                continue
            # Where this video would sit on the Incident's clock, and
            # whether that overlaps what is placed already.
            sits = _wrapped(start - incident.clock_zero)
            if sits <= high and sits + (end - start) >= low:
                key = _add_key(incident, recording)
                taken.add(recording.pk)
                if key in declined:
                    continue
                offered.append(
                    {
                        "kind": "add",
                        "key": key,
                        "incident": incident,
                        "recording": recording,
                        "line": (f"1 more video ran during {incident.name}. Add it?"),
                    }
                )
    rest = [one for one in spans if one[0].pk not in taken]
    limit = most_cameras()
    for group in _chained(rest):
        recordings = [one[0] for one in group]
        more = len(recordings) > limit
        recordings = recordings[:limit]
        key = _new_key(recordings)
        if key in declined:
            continue
        date = group[0][1]
        line = f"{len(recordings)} videos ran at the same time on {date}."
        if more:
            line += (
                f" The first {limit} by their clocks are offered; "
                f"an incident holds at most {limit}."
            )
        offered.append(
            {
                "kind": "new",
                "key": key,
                "recordings": recordings,
                "date": date,
                "line": line + " Make them an incident?",
            }
        )
    return offered


def decline(case, key: str) -> None:
    """Not these: the offer with this key is not shown again."""
    declined = list(case.declined_offers or [])
    if key not in declined:
        declined.append(key)
        case.declined_offers = declined
        case.save(update_fields=["declined_offers"])


# Making and changing an Incident ------------------------------------------------


def make(case, name: str, recordings, *, by, how: str = BY_HAND, request=None):
    """A new Incident with these videos, the clocked ones placed at once."""
    recordings = list(recordings)[: most_cameras()]
    with transaction.atomic():
        incident = Incident.objects.create(
            case=case,
            name=(name or "").strip()[:200] or "Incident",
            created_by=by,
            how=how,
        )
        _add(incident, recordings, by=by)
    audit.write(
        CATEGORY,
        "incident made",
        actor=by,
        affected_user=case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        request=request,
        case=case.name,
        how=how,
        cameras=len(recordings),
    )
    from core import cases

    cases.note_activity(case, by=by)
    return incident


def _add(incident: Incident, recordings, *, by) -> list[IncidentCamera]:
    """Add cameras and place from their clocks, the checked ones first."""
    made = []
    for recording in recordings:
        camera, _ = IncidentCamera.objects.get_or_create(
            incident=incident, recording=recording
        )
        made.append(camera)
    ordered = sorted(
        made,
        key=lambda one: (
            0 if stamp_checked(one.recording) else 1,
            clock_zero_of(one.recording) or 0.0,
        ),
    )
    for camera in ordered:
        if clock_zero_of(camera.recording) is not None and not camera.is_placed():
            place_from_clock(camera, by=by, quietly=True)
    for camera in ordered:
        if not camera.is_placed():
            guess(camera)
    return made


def guess(camera: IncidentCamera) -> None:
    """The app's best guess for a camera with no clock: on the wall, marked
    Not synced yet, so Sync has something to nudge."""
    incident = camera.incident
    _, second = file_time_of(camera.recording)
    if incident.clock_zero is not None and second is not None:
        starts_at = _wrapped(second - incident.clock_zero)
    else:
        low, _ = span_of(incident)
        starts_at = low if low is not None else 0.0
    camera.starts_at = float(starts_at)
    camera.placed = GUESS
    camera.save(update_fields=["starts_at", "placed"])


def guess_the_unplaced(incident: Incident) -> None:
    """Cameras added before v1.60.0 with no place yet get the guess when the
    page next draws them."""
    for camera in incident.cameras.all():
        if not camera.is_placed():
            guess(camera)


def add_cameras(incident: Incident, recordings, *, by, request=None) -> int:
    recordings = [
        one
        for one in recordings
        if not IncidentCamera.objects.filter(incident=incident, recording=one).exists()
    ]
    room = most_cameras() - incident.cameras.count()
    recordings = recordings[: max(0, room)]
    if not recordings:
        return 0
    _add(incident, recordings, by=by)
    _changed(incident, by, request, what="cameras added", count=len(recordings))
    return len(recordings)


def remove_camera(camera: IncidentCamera, *, by, request=None) -> None:
    incident = camera.incident
    camera.delete()
    _changed(incident, by, request, what="camera removed")


def rename(incident: Incident, name: str, *, by, request=None) -> None:
    incident.name = (name or "").strip()[:200] or incident.name
    incident.save(update_fields=["name"])
    _changed(incident, by, request, what="renamed")


def _changed(incident: Incident, by, request, **details) -> None:
    audit.write(
        CATEGORY,
        "incident changed",
        actor=by,
        affected_user=incident.case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        request=request,
        case=incident.case.name,
        **details,
    )
    from core import cases

    cases.note_activity(incident.case, by=by)


def delete(incident: Incident, *, by, request=None) -> None:
    """The Incident, its placements and nothing else: never a recording."""
    case = incident.case
    name = incident.name
    incident.delete()
    audit.write(
        CATEGORY,
        "incident deleted",
        actor=by,
        affected_user=case.owner,
        object_type="incident",
        object_label=name,
        request=request,
        case=case.name,
    )


def left_the_case(recording) -> None:
    """A recording deleted or moved out leaves its Incident."""
    IncidentCamera.objects.filter(recording=recording).delete()


# Placing ----------------------------------------------------------------------------


def _placed(
    camera: IncidentCamera, how: str, starts_at: float, *, by, request, quietly
):
    camera.starts_at = float(starts_at)
    camera.placed = how
    camera.placed_by = by
    camera.placed_at = timezone.now()
    camera.save(update_fields=["starts_at", "placed", "placed_by", "placed_at"])
    if not quietly:
        audit.write(
            CATEGORY,
            "camera placed",
            actor=by,
            affected_user=camera.incident.case.owner,
            object_type="recording",
            object_id=camera.recording_id,
            object_label=camera.recording.title,
            request=request,
            incident=camera.incident.name,
            how=how,
        )
        from core import cases

        cases.note_activity(camera.incident.case, by=by)


def place_from_clock(
    camera: IncidentCamera, *, by, request=None, quietly: bool = False
) -> bool:
    """From the stamp; the first checked clock sets the Incident's."""
    zero = clock_zero_of(camera.recording)
    if zero is None:
        return False
    incident = camera.incident
    checked = stamp_checked(camera.recording)
    if incident.clock_zero is None:
        if not checked:
            # An unchecked clock places the camera but does not become the
            # Incident's clock; with nothing else to go by it starts at zero.
            _placed(
                camera, CLOCK_UNCHECKED, 0.0, by=by, request=request, quietly=quietly
            )
            return True
        incident.clock_zero = zero
        incident.clock_date = ((camera.recording.stamp or {}).get("date") or "").strip()
        incident.save(update_fields=["clock_zero", "clock_date"])
        _placed(camera, CLOCK, 0.0, by=by, request=request, quietly=quietly)
        return True
    _placed(
        camera,
        CLOCK if checked else CLOCK_UNCHECKED,
        _wrapped(zero - incident.clock_zero),
        by=by,
        request=request,
        quietly=quietly,
    )
    return True


def place_from_file(camera: IncidentCamera, *, by, request=None) -> bool:
    """From the time the file carries; needs the Incident to have a clock."""
    incident = camera.incident
    _, second = file_time_of(camera.recording)
    if second is None or incident.clock_zero is None:
        return False
    _placed(
        camera,
        FILE,
        _wrapped(second - incident.clock_zero),
        by=by,
        request=request,
        quietly=False,
    )
    return True


def place_by_hand(
    camera: IncidentCamera, starts_at: float, *, by, request=None
) -> None:
    _placed(camera, HAND, starts_at, by=by, request=request, quietly=False)


def apply_match(camera: IncidentCamera, *, by, request=None) -> bool:
    """A finished sound match, taken: the camera sits its lag after the other."""
    against = camera.match_against
    if camera.match_state != MATCH_DONE or camera.match_lag is None or against is None:
        return False
    if not against.is_synced():
        return False
    _placed(
        camera,
        SOUND,
        against.starts_at + camera.match_lag,
        by=by,
        request=request,
        quietly=False,
    )
    return True


def ask_for_match(camera: IncidentCamera, against: IncidentCamera, *, by) -> bool:
    """Queue the sound match on the media worker."""
    if not sound_match_on() or not against.is_synced() or against.pk == camera.pk:
        return False
    camera.match_state = MATCH_QUEUED
    camera.match_against = against
    camera.match_lag = None
    camera.match_strength = None
    camera.match_reason = ""
    camera.save(
        update_fields=[
            "match_state",
            "match_against",
            "match_lag",
            "match_strength",
            "match_reason",
        ]
    )
    from core import tasks

    transaction.on_commit(lambda: tasks.match_sound.defer(camera_id=str(camera.pk)))
    return True


def run_match(camera: IncidentCamera) -> None:
    """The worker's side: compare the two ASR audio files and keep the result."""
    from core import sound_match

    against = camera.match_against
    camera.match_state = MATCH_RUNNING
    camera.save(update_fields=["match_state"])
    try:
        if against is None:
            raise sound_match.NoMatch("no camera to match against")
        mine = _first_side_audio(camera.recording)
        theirs = _first_side_audio(against.recording)
        expected = None
        _, my_file = file_time_of(camera.recording)
        _, their_file = file_time_of(against.recording)
        if my_file is not None and their_file is not None:
            expected = _wrapped(my_file - their_file)
        found = sound_match.lag_between(theirs, mine, expected=expected)
    except sound_match.NoMatch as why:
        camera.match_state = MATCH_FAILED
        camera.match_reason = str(why)[:60]
        camera.save(update_fields=["match_state", "match_reason"])
        return
    except Exception as why:  # noqa: BLE001 - the page says it failed, the log says why
        log.warning("the sound match of camera %s failed: %s", camera.pk, why)
        camera.match_state = MATCH_FAILED
        camera.match_reason = "the match failed"
        camera.save(update_fields=["match_state", "match_reason"])
        return
    camera.match_state = MATCH_DONE
    camera.match_lag = found.lag
    camera.match_strength = found.strength
    camera.match_reason = ""
    camera.save(
        update_fields=["match_state", "match_lag", "match_strength", "match_reason"]
    )
    if found.strength >= STRONG_MATCH:
        apply_match(camera, by=camera.placed_by)


def _first_side_audio(recording):
    from core import sound_match

    side = recording.sides.order_by("number").first()
    path = side.asr_path if side is not None else None
    if path is None or not path.exists():
        raise sound_match.NoMatch("no sound to compare")
    return path


# The clock's words and the page's state ----------------------------------------------


def span_of(incident: Incident) -> tuple[float | None, float | None]:
    """Where the placed cameras start and end on the Incident clock."""
    starts = [one.starts_at for one in incident.cameras.all() if one.is_placed()]
    ends = [one.ends_at() for one in incident.cameras.all() if one.is_placed()]
    if not starts:
        return None, None
    return min(starts), max(ends)


def span_words(incident: Incident) -> str:
    low, high = span_of(incident)
    if low is None:
        return "no camera placed"
    if incident.clock_zero is None:
        return f"{elapsed(high - low)} from the first camera; no camera clock"
    date = f"{incident.clock_date} " if incident.clock_date else ""
    return f"{date}{time_of_day(incident, low)} to {time_of_day(incident, high)}"


def placed_words(incident: Incident) -> tuple[str, str]:
    cameras = list(incident.cameras.all())
    synced = sum(1 for one in cameras if one.is_synced())
    if not cameras:
        return "no cameras", "warn"
    words = f"{synced} of {len(cameras)} synced"
    return words, "ok" if synced == len(cameras) else "warn"


def strip_rows(case) -> list[dict]:
    """The case page's Incidents strip, one line per Incident."""
    rows = []
    for incident in case.incidents.all():
        words, tone = placed_words(incident)
        rows.append(
            {
                "incident": incident,
                "cameras": incident.cameras.count(),
                "span": span_words(incident),
                "placed": words,
                "tone": tone,
                "events": incident.events.count(),
                "url": incident.url(),
            }
        )
    return rows


def incident_of(recording) -> IncidentCamera | None:
    return (
        IncidentCamera.objects.filter(recording=recording)
        .select_related("incident")
        .first()
    )


def link_for(recording) -> dict | None:
    """All cameras: where the Incident page opens for this recording, or None."""
    if not on():
        return None
    camera = incident_of(recording)
    if camera is None or not camera.is_placed():
        return None
    # A guessed camera is on the wall but not in step: All cameras waits.
    if not camera.is_synced():
        return None
    return {
        "url": camera.incident.url(),
        "starts_at": camera.starts_at,
        "name": camera.incident.name,
    }


def all_cameras_url(recording, seconds: float) -> str:
    """The Incident page at this recording's moment, or ""."""
    link = link_for(recording)
    if link is None:
        return ""
    return f"{link['url']}?t={link['starts_at'] + float(seconds):.2f}"


def wall_of(incident: Incident) -> list[IncidentCamera]:
    """The cameras on the Wall, in the person's order or the clock's."""
    placed = sorted(
        (one for one in incident.cameras.all() if one.is_placed()),
        key=lambda one: (one.starts_at, one.added),
    )
    by_id = {str(one.pk): one for one in placed}
    chosen = [by_id[key] for key in (incident.wall or []) if key in by_id]
    for one in placed:
        if one not in chosen:
            chosen.append(one)
    return chosen[: wall_size()]


def set_wall(incident: Incident, camera_ids: list[str]) -> None:
    incident.wall = [str(one) for one in camera_ids][: wall_size()]
    incident.save(update_fields=["wall"])


# The stamp, read early ------------------------------------------------------------


def wants_early_stamp(recording) -> bool:
    return bool(
        recording.case_id
        and recording.playback_ready
        and recording.stamp is None
        and is_video(recording)
        and stamp_early_on()
    )


def after_playback(recording) -> None:
    """The playback copy landed: read the stamp now, when the office says so."""
    if not wants_early_stamp(recording):
        return
    from core import engine, tasks

    if not engine.is_reachable():
        return
    tasks.read_stamp_early.defer(recording_id=str(recording.pk))


def read_early(recording) -> None:
    """The task's side."""
    from core import assistant

    recording.refresh_from_db()
    if recording.stamp is not None or not is_video(recording):
        return
    assistant.read_stamp(recording, asked_by=None)
