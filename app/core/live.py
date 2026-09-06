"""Live recording: a Recording made in the browser (Phase 3, Live recording).

The Record page records; the browser hands the audio to the server in pieces
as it goes, through the upload sidecar, as an upload of unknown length; when
the recording ends the pieces are one file and the pipeline takes it from
there, at the front of the service's line. Nothing rougher than the finished
Transcript is ever shown, and nothing leaves the building.

A Live recording is a Recording: it joins a Case as it starts, and every rule
about a Recording in a Case applies. This module holds what is particular to
it: the setting, the start, the end, and the words the page reads while the
Transcript is on its way.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from django.conf import settings as django_settings
from django.utils import timezone

from core import audit, cases, settings_store
from core.recordings import Batch, MediaState, Recording

log = logging.getLogger(__name__)

# The service's priority for a Live recording: ahead of every uploaded one.
PRIORITY = 100

# What the browser records in, and the piece it sends.
MIME = "audio/webm"
FILENAME_SUFFIX = ".webm"

# Until twenty jobs have been measured, the published figure: about sixty
# times real time.
ASSUMED_SPEED = 60.0
SPEED_WINDOW = 20


def on() -> bool:
    """Whether the Record page exists: the setting, under Folder management."""
    return cases.folder_management_on() and bool(settings_store.get("live_recording"))


def longest_seconds() -> int:
    return int(settings_store.get("live_longest_minutes") or 180) * 60


class Refused(Exception):
    """Why a recording may not start, in the person's words."""


def start(
    user,
    case,
    *,
    recording_type: str = "",
    title: str = "",
    language: str = "",
    translate: bool = False,
    browser: str = "",
    with_computer: bool = False,
    request=None,
) -> Recording:
    """Make the Recording a Live recording will become, before a byte arrives.

    Its own Batch, marked live so it never holds up the person's uploads; in
    the Case from the first moment; Uploading until the recording ends. The
    room checked is the Case owner's, as for an upload into the Case.
    """
    from core import uploads

    if not on():
        raise Refused("Live recording is off.")
    if not case.member(user) and not getattr(user, "is_admin", False):
        raise Refused("That case is not yours to record into.")
    if uploads.free_disk_bytes() < settings_store.minimum_free_disk_bytes():
        raise Refused("The server is low on space, so nothing can be recorded. Ask IT.")
    owner = case.owner
    if uploads.room_left(owner) <= 0:
        whose = "Your" if owner.pk == user.pk else f"{owner.shown_name}'s"
        raise Refused(f"{whose} storage space is full, so nothing can be recorded.")

    when = timezone.localtime(timezone.now())
    title = (title or "").strip()[:300] or (
        f"{recording_type or 'Recording'} {when:%d %b %Y %H:%M}"
    )
    sources = ["microphone", "computer"] if with_computer else ["microphone"]
    batch = Batch.objects.create(user=user, is_live=True)
    recording = Recording.objects.create(
        batch=batch,
        user=user,
        case=case,
        recording_type=(recording_type or "").strip()[:60],
        title=title,
        original_filename=f"{title[:200]}{FILENAME_SUFFIX}",
        media_state=MediaState.UPLOADING,
        spoken_language=(language or "")[:10],
        translate=bool(translate),
        diarize=True,
        preprocessing="standard",
        live={
            "started": when.isoformat(),
            "sources": sources,
            "browser": (browser or "")[:120],
            "pauses": [],
            "ended": "",
        },
    )
    audit.write(
        audit.Category.RECORDINGS,
        "Live recording started",
        actor=user,
        request=request,
        affected_user=owner if owner.pk != user.pk else None,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        case=case.name,
        sources=sources,
        language=language or "auto",
        translate=bool(translate),
    )
    cases.note_activity(case, by=user)
    return recording


def note_upload(recording: Recording, tus_id: str) -> None:
    """The sidecar upload this recording's pieces go into, remembered."""
    live = dict(recording.live or {})
    live["tus_id"] = (tus_id or "")[:80]
    recording.live = live
    recording.save(update_fields=["live"])


def ended(
    recording: Recording,
    *,
    how: str,
    pauses: list | None = None,
    seconds: float | None = None,
    computer_ended_at: float | None = None,
    taps: list | None = None,
    marks: list | None = None,
    request=None,
) -> None:
    """The recording has ended: by Stop, the limit, the disk, or the page closing.

    Whatever arrived is the Recording. When the sidecar has already finished
    the upload, the pipeline is on its way and this only writes the facts
    down; when it has not (the page closed, the browser died), the pieces on
    the server are taken as the file and the pipeline starts from them.
    """
    live = dict(recording.live or {})
    if live.get("ended"):
        return
    live["ended"] = how if how in ("stop", "limit", "closed", "disk") else "closed"
    live["ended_at"] = timezone.localtime(timezone.now()).isoformat()
    live["pauses"] = [
        {"at": float(one.get("at", 0)), "seconds": float(one.get("seconds", 0))}
        for one in (pauses or [])
        if isinstance(one, dict)
    ][:200]
    if seconds is not None:
        live["seconds"] = round(float(seconds), 1)
    if computer_ended_at is not None:
        live["computer_ended_at"] = round(float(computer_ended_at), 1)
    recording.live = live
    recording.speaker_taps = _clean_taps(taps)
    recording.marks = _clean_marks(marks)
    recording.save(update_fields=["live", "speaker_taps", "marks"])

    if recording.media_state == MediaState.UPLOADING and how != "stop":
        _take_what_arrived(recording)

    audit.write(
        audit.Category.RECORDINGS,
        "Live recording finished",
        actor=request.user if request is not None and how == "stop" else None,
        system=None if request is not None and how == "stop" else "record page",
        request=request,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        how=live["ended"],
        seconds=live.get("seconds"),
        pauses=len(live["pauses"]),
        taps=len(recording.speaker_taps),
        marks=len(recording.marks),
    )


def _clean_taps(taps) -> list:
    """The taps as moments and names, in time order, at most five hundred."""
    kept = []
    for one in taps or []:
        if not isinstance(one, dict):
            continue
        name = str(one.get("name") or "").strip()[:60]
        try:
            at = max(0.0, float(one.get("at", 0)))
        except (TypeError, ValueError):
            continue
        if name:
            kept.append({"at": round(at, 1), "name": name})
    kept.sort(key=lambda one: one["at"])
    return kept[:500]


def _clean_marks(marks) -> list:
    kept = []
    for one in marks or []:
        if not isinstance(one, dict):
            continue
        try:
            at = max(0.0, float(one.get("at", 0)))
        except (TypeError, ValueError):
            continue
        kept.append(
            {"at": round(at, 1), "word": str(one.get("word") or "").strip()[:80]}
        )
    kept.sort(key=lambda one: one["at"])
    return kept[:500]


# Speaker names from the taps ------------------------------------------------------


def name_from_taps(recording: Recording, transcript) -> int:
    """Give each diarized Speaker the name whose taps cover most of its speech.

    A tap covers from its moment to the next tap's. For a one-channel
    Recording every Segment counts; for a Two-channel call only the first
    Side's, the microphone's, since the far side of a call was not in the
    room to be tapped. A label nobody's taps cover keeps its name. Each
    naming is the ordinary rename, and a tapped person who is not yet a
    Person of the Case becomes one.
    """
    taps = recording.speaker_taps or []
    if not taps or transcript is None:
        return 0
    from core import people

    spans = []
    for index, tap in enumerate(taps):
        until = taps[index + 1]["at"] if index + 1 < len(taps) else float("inf")
        spans.append((tap["at"], until, tap["name"]))

    segments = transcript.segments.all()
    if recording.is_two_channel_call:
        first = recording.sides.order_by("number").first()
        segments = segments.filter(side=first) if first is not None else segments

    coverage: dict[str, dict[str, float]] = {}
    for segment in segments:
        label = segment.speaker_label or segment.speaker
        if not label:
            continue
        for start, until, name in spans:
            overlap = min(segment.end, until) - max(segment.start, start)
            if overlap > 0:
                coverage.setdefault(label, {}).setdefault(name, 0.0)
                coverage[label][name] += overlap

    named = 0
    for label, by_name in coverage.items():
        name = max(by_name.items(), key=lambda pair: pair[1])[0]
        changed = (
            segments.filter(speaker_label=label)
            .exclude(speaker=name)
            .update(speaker=name)
        )
        if changed:
            named += 1
            people.on_named(recording, name, by=recording.user, how="named from taps")
    if named:
        audit.write(
            audit.Category.EDITS,
            "Speakers named from taps",
            system="record page",
            affected_user=recording.user,
            object_type="recording",
            object_id=recording.pk,
            object_label=recording.original_filename,
            labels_named=named,
        )
        live = dict(recording.live or {})
        live["named_from_taps"] = named
        recording.live = live
        recording.save(update_fields=["live"])
    return named


def people_expected(case) -> list[str]:
    """The Case's People, for the Record page's buttons."""
    return list(case.people.order_by("name").values_list("name", flat=True))


def _take_what_arrived(recording: Recording) -> None:
    """The sidecar's partial file becomes the Recording's original.

    The browser did not finish the upload (the page closed, the computer
    slept). The pieces that reached the sidecar are on its disk under the
    upload's id; they are moved into place and the pipeline starts, as the
    post-finish hook would have done. Nothing arrived at all is a Recording
    with nothing in it, which is marked failed and says why.
    """
    from core.tasks import prepare_recording

    tus_id = (recording.live or {}).get("tus_id", "")
    arrived = Path(django_settings.UPLOADS_DIR) / tus_id if tus_id else None
    if arrived is None or not arrived.exists() or arrived.stat().st_size == 0:
        recording.media_state = MediaState.FAILED
        recording.failure_message = "The recording ended before any sound arrived."
        recording.save(update_fields=["media_state", "failure_message"])
        return
    recording.folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(arrived), recording.original_path)
    (arrived.parent / f"{tus_id}.info").unlink(missing_ok=True)
    recording.size_bytes = recording.original_path.stat().st_size
    recording.media_state = MediaState.CHECKING
    recording.save(update_fields=["size_bytes", "media_state"])
    prepare_recording.defer(recording_id=str(recording.pk))
    log.info(
        "live recording %s ended early; %d bytes taken",
        recording.pk,
        recording.size_bytes,
    )


# The queue line -------------------------------------------------------------------


def measured_speed() -> float:
    """Audio seconds per second of transcription, over the last twenty jobs."""
    from core.jobs import Job, JobState

    audio = 0.0
    took = 0.0
    for job in (
        Job.objects.filter(state=JobState.DONE, finished__isnull=False)
        .select_related("recording")
        .order_by("-created")[:SPEED_WINDOW]
    ):
        length = job.recording.duration_seconds or 0
        seconds = (job.finished - job.created).total_seconds()
        if length > 0 and seconds > 0:
            audio += length
            took += seconds
    return audio / took if took > 0 and audio > 0 else ASSUMED_SPEED


def line_for(recording: Recording) -> dict:
    """Where a Recording stands, in words, for the page and the Case row.

    "state" is one of recording, preparing, queued, transcribing, ready,
    failed; "says" is the sentence a person reads.
    """
    from core.jobs import JobState

    if hasattr(recording, "transcript"):
        return {"state": "ready", "says": "Ready."}
    if recording.media_state in (MediaState.FAILED, MediaState.REJECTED):
        return {
            "state": "failed",
            "says": recording.failure_message or "The recording could not be used.",
        }
    if recording.media_state == MediaState.UPLOADING:
        return {"state": "recording", "says": "Recording."}
    job = recording.jobs.order_by("-created").first()
    if job is None or job.state not in (JobState.QUEUED, JobState.RUNNING):
        return {"state": "preparing", "says": "Preparing the sound."}
    run = job.runs.order_by("side__number").first()
    if job.state == JobState.RUNNING or (run is not None and run.state == "running"):
        return {"state": "transcribing", "says": "Transcribing."}
    ahead = run.position if run is not None and run.position is not None else 0
    minutes_ahead = (
        run.audio_minutes_ahead if run is not None and run.audio_minutes_ahead else 0.0
    )
    own = (recording.duration_seconds or 0) / 60.0
    wait = (minutes_ahead + own) / measured_speed()
    about = max(1, int(wait) + (1 if wait > int(wait) else 0))
    minutes = f"{about} minute{'s' if about != 1 else ''}"
    if ahead <= 0:
        return {"state": "queued", "says": f"Next in line, about {minutes}."}
    return {
        "state": "queued",
        "says": f"{ahead} recording{'s' if ahead != 1 else ''} ahead, about {minutes}.",
    }


# The Provenance --------------------------------------------------------------------

ENDINGS = {
    "stop": "ended by Stop",
    "limit": "stopped at the longest allowed length",
    "closed": "ended when the page closed, with what had been sent",
    "disk": "ended when the server stopped taking it",
    "": "still recording",
}


def provenance_rows(recording) -> list[tuple[str, str]]:
    """What the Details panel and the Word export say about a Live recording."""
    facts = recording.live or {}
    if not facts:
        return []
    sources = facts.get("sources") or ["microphone"]
    said = (
        "the microphone"
        if sources == ["microphone"]
        else "the microphone and the computer's sound"
    )
    ending = ENDINGS.get(facts.get("ended", ""), "ended")
    rows = [("Recorded live", f"On the Record page, from {said}; {ending}")]
    if facts.get("named_from_taps"):
        count = facts["named_from_taps"]
        rows.append(
            ("Speakers named from taps", f"{count} speaker{'s' if count != 1 else ''}")
        )
    if recording.marks:
        count = len(recording.marks)
        rows.append(("Marks", f"{count} mark{'s' if count != 1 else ''}"))
    if facts.get("computer_ended_at") is not None:
        at = facts["computer_ended_at"]
        rows.append(
            (
                "The computer's sound",
                f"stopped at {int(at // 60)}:{int(at % 60):02d}; the microphone "
                "alone after that",
            )
        )
    if facts.get("browser"):
        rows.append(("Recorded with", facts["browser"][:80]))
    pauses = facts.get("pauses") or []
    if pauses:
        rows.append(
            (
                "Pauses",
                "; ".join(
                    f"at {int(one['at'] // 60)}:{int(one['at'] % 60):02d} for "
                    f"{int(one['seconds'])} s"
                    for one in pauses
                ),
            )
        )
    return rows
