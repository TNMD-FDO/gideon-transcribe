"""Vision on the office's terms (Phase 4 chapter 5, v1.54.0).

The picture step of a video (the scan, the stamp, the record, the Digest;
`assistant.prepare`) runs when the office says: the moment each transcript
lands, overnight in a window, or only when an Admin allows it. A person
chooses it with the upload page's tick; anyone with a case may queue its
videos for tonight; only an Admin starts the work by day, on the case page
or by allowing a request. The pages say the state in one family of words.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from django.db import models
from django.utils import timezone

from core import assistant, audit, settings_store

log = logging.getLogger("transcribe.vision")

# A transcript waiting for the window; beside assistant's QUEUED, PREPARING,
# DONE and FAILED in the same field.
TONIGHT = "tonight"
NOT_REACHED = "not_reached"

LANDS = settings_store.VISION_LANDS
OVERNIGHT = settings_store.VISION_OVERNIGHT
ASKED = settings_store.VISION_ASKED


# The model ----------------------------------------------------------------------


class VisionRequest(models.Model):
    """What a person with a case makes when they ask for its vision now: who,
    for which case or video, when, an optional line of why, and what an Admin
    decided. A row, never a mail alone, so the Panel shows what is waiting."""

    WAITING, ALLOWED, DECLINED = "waiting", "allowed", "declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="vision_requests"
    )
    recording = models.ForeignKey(
        "core.Recording",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="vision_requests",
    )
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="vision_requests"
    )
    asked_at = models.DateTimeField(auto_now_add=True)
    # Content: never logged, never in a row.
    why = models.CharField(max_length=200, blank=True, default="")
    state = models.CharField(max_length=10, default=WAITING)
    decided_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vision_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    line = models.CharField(max_length=200, blank=True, default="")
    # When the asker was told the work is done, so they are told once.
    done_mailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["asked_at"]

    @property
    def what(self) -> str:
        """The case or the video, as a message names it."""
        if self.recording_id is not None:
            return self.recording.title
        return f"the case {self.case.name}"

    def transcripts(self) -> list:
        """The transcripts the request is for, as they stand now."""
        from core.jobs import Transcript

        rows = Transcript.objects.filter(recording__case=self.case).select_related(
            "recording"
        )
        if self.recording_id is not None:
            rows = rows.filter(recording=self.recording)
        return [one for one in rows if eligible(one.recording)]


# The position -------------------------------------------------------------------


def position() -> str:
    return settings_store.vision_runs()


def eligible(recording) -> bool:
    """A recording the picture step can run on at all."""
    return assistant.record_on() and assistant.has_picture(recording)


def scheduled() -> bool:
    """Whether vision waits for the night or for an Admin rather than running
    as each transcript lands."""
    return position() != LANDS


def window() -> tuple[dt.time, dt.time]:
    start, end = settings_store.vision_window()
    return _clock(start), _clock(end)


def _clock(text: str) -> dt.time:
    hours, minutes = text.split(":")
    return dt.time(int(hours), int(minutes))


def window_words() -> str:
    start, end = settings_store.vision_window()
    return f"between {start} and {end}"


def in_window(now=None) -> bool:
    """Whether the server's clock is inside the night's window; a window may
    cross midnight."""
    moment = timezone.localtime(now or timezone.now()).time()
    start, end = window()
    if start <= end:
        return start <= moment < end
    return moment >= start or moment < end


def just_closed(now=None, minutes: int = 3) -> bool:
    """Whether the window closed within the last few minutes."""
    moment = timezone.localtime(now or timezone.now())
    _, end = window()
    closed = moment.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    return closed <= moment < closed + dt.timedelta(minutes=minutes)


# What the transcript lands into -----------------------------------------------------


def on_transcript(recording) -> bool:
    """A video's transcript has landed: queued now, marked for tonight, or
    left for an Admin, by the tick and the office's position."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None or not eligible(recording):
        return False
    if not recording.vision_wanted:
        return False
    where = position()
    if where == LANDS:
        return assistant.queue_preparation(recording)
    if recording.case_id is None:
        # A session's recordings are gone before tonight (chapter 5).
        return False
    if where == OVERNIGHT:
        mark_tonight(transcript)
        return True
    return False


def mark_tonight(transcript, reason: str = "") -> None:
    transcript.prepare_state = TONIGHT
    transcript.prepare_reason = reason
    transcript.prepare_done = 0
    transcript.prepare_total = 0
    transcript.save(
        update_fields=[
            "prepare_state",
            "prepare_reason",
            "prepare_done",
            "prepare_total",
        ]
    )


def back_to_tonight(transcript) -> None:
    """The engine went away during the night: the video waits for the next
    window rather than failing."""
    mark_tonight(transcript, NOT_REACHED)


def waiting_tonight():
    from core.jobs import Transcript

    return (
        Transcript.objects.filter(prepare_state=TONIGHT, recording__case__isnull=False)
        .select_related("recording")
        .order_by("created")
    )


def ahead_of(transcript) -> int:
    return waiting_tonight().filter(created__lt=transcript.created).count()


def busy() -> bool:
    """Whether a video is being enriched now, in the vision lane."""
    from core.jobs import Transcript

    return Transcript.objects.filter(
        prepare_state__in=(assistant.QUEUED, assistant.PREPARING)
    ).exists()


def mind_the_night(now=None) -> str:
    """Every minute: inside the window, the oldest video marked tonight is
    queued when none is being enriched; outside it, the ones still waiting
    are marked not reached, so their rows say so. Returns what it did."""
    if position() != OVERNIGHT or not assistant.record_on():
        return "off"
    if not in_window(now):
        # In the minutes after the window closes, the videos still waiting
        # are marked not reached, so their rows say so until tonight.
        if just_closed(now):
            waiting_tonight().exclude(prepare_reason=NOT_REACHED).update(
                prepare_reason=NOT_REACHED
            )
        return "outside"
    if busy():
        return "busy"
    first = waiting_tonight().first()
    if first is None:
        return "nothing"
    assistant.queue_preparation(first.recording)
    return "queued"


# What a person or an Admin presses --------------------------------------------------


def _log_queued(recording, *, by, how: str) -> None:
    audit.write(
        audit.Category.RECORDINGS,
        "Vision queued",
        actor=by,
        affected_user=(
            recording.user if by is not None and recording.user_id != by.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        how=how,
    )


def unenriched(case, recording=None) -> list:
    """The case's videos a press would enrich: not enriched, not at it, and
    not waiting for tonight."""
    from core.jobs import Transcript

    rows = Transcript.objects.filter(recording__case=case).select_related("recording")
    if recording is not None:
        rows = rows.filter(recording=recording)
    found = []
    for transcript in rows:
        if transcript.prepare_state in (assistant.QUEUED, assistant.PREPARING, TONIGHT):
            continue
        if eligible(transcript.recording) and not assistant.prepared(transcript):
            found.append(transcript)
    return found


def enrich_tonight(case, *, by, recording=None) -> int:
    """Anyone with the case: the videos wait for the window."""
    count = 0
    for transcript in unenriched(case, recording):
        mark_tonight(transcript)
        transcript.recording.vision_wanted = True
        transcript.recording.save(update_fields=["vision_wanted"])
        _log_queued(transcript.recording, by=by, how="tonight")
        count += 1
    return count


def enrich_now(case, *, by, recording=None, how: str = "now") -> int:
    """An Admin's: the work queued now, whatever the position."""
    count = 0
    rows = unenriched(case, recording)
    rows += [
        one
        for one in waiting_tonight().filter(recording__case=case)
        if recording is None or one.recording_id == recording.pk
    ]
    for transcript in rows:
        transcript.recording.vision_wanted = True
        transcript.recording.save(update_fields=["vision_wanted"])
        if assistant.queue_preparation(transcript.recording):
            _log_queued(transcript.recording, by=by, how=how)
            count += 1
    return count


def open_request(case, recording=None):
    """The request waiting on this case, or on this video, if any."""
    rows = VisionRequest.objects.filter(case=case, state=VisionRequest.WAITING)
    if recording is not None:
        rows = rows.filter(models.Q(recording=recording) | models.Q(recording=None))
    return rows.first()


def last_declined(case, recording=None):
    rows = VisionRequest.objects.filter(case=case, state=VisionRequest.DECLINED)
    if recording is not None:
        rows = rows.filter(models.Q(recording=recording) | models.Q(recording=None))
    return rows.order_by("-decided_at").first()


def ask(case, *, by, recording=None, why: str = "") -> VisionRequest | None:
    """A request for now, one open at a time per case or video; the Admins
    are mailed."""
    from core import mail

    if open_request(case, recording) is not None:
        return None
    request = VisionRequest.objects.create(
        case=case, recording=recording, asked_by=by, why=why.strip()[:200]
    )
    audit.write(
        audit.Category.RECORDINGS,
        "Vision requested",
        actor=by,
        object_type="recording" if recording is not None else "case",
        object_id=recording.pk if recording is not None else case.pk,
        object_label=(
            recording.original_filename if recording is not None else case.name
        ),
    )
    mail.vision_requested(request)
    return request


def estimate_words(transcripts) -> str:
    seconds = sum(
        assistant.prepare_plan(one.recording, one)["seconds"] for one in transcripts
    )
    return assistant.about(seconds)


def allow(request: VisionRequest, *, by, line: str = "") -> int:
    from core import mail

    request.state = VisionRequest.ALLOWED
    request.decided_by = by
    request.decided_at = timezone.now()
    request.line = line.strip()[:200]
    request.save(update_fields=["state", "decided_by", "decided_at", "line"])
    count = enrich_now(request.case, by=by, recording=request.recording, how="allowed")
    audit.write(
        audit.Category.RECORDINGS,
        "Vision allowed",
        actor=by,
        affected_user=request.asked_by if request.asked_by_id != by.pk else None,
        object_type="recording" if request.recording_id else "case",
        object_id=request.recording_id or request.case_id,
        object_label=request.what,
        videos=count,
    )
    mail.vision_allowed(request)
    if count == 0:
        note_progress_for_request(request)
    return count


def decline(request: VisionRequest, *, by, line: str = "") -> None:
    request.state = VisionRequest.DECLINED
    request.decided_by = by
    request.decided_at = timezone.now()
    request.line = line.strip()[:200]
    request.save(update_fields=["state", "decided_by", "decided_at", "line"])
    audit.write(
        audit.Category.RECORDINGS,
        "Vision declined",
        actor=by,
        affected_user=request.asked_by if request.asked_by_id != by.pk else None,
        object_type="recording" if request.recording_id else "case",
        object_id=request.recording_id or request.case_id,
        object_label=request.what,
    )


def requests_waiting():
    return VisionRequest.objects.filter(state=VisionRequest.WAITING).select_related(
        "case", "recording", "asked_by"
    )


# What the pages say ---------------------------------------------------------------


def words(transcript) -> tuple[str, str]:
    """The Vision column's words and the pill's tone, in the one family the
    chapter fixes; nothing for sound alone."""
    if transcript is None:
        return "", ""
    recording = transcript.recording
    if not eligible(recording):
        return "", ""
    state = transcript.prepare_state
    if state == assistant.DONE:
        return "Enriched with vision", "ok"
    if state in (assistant.QUEUED, assistant.PREPARING):
        left = assistant.seconds_left(transcript)
        count = (
            f"{transcript.prepare_done} of {transcript.prepare_total}, "
            if transcript.prepare_total
            else ""
        )
        return f"Enriching now, {count}{assistant.about(left)}".strip(), "warn"
    if state == TONIGHT:
        said = "Enriching tonight"
        ahead = ahead_of(transcript)
        if ahead:
            said += f", {ahead} ahead of it"
        if transcript.prepare_reason == NOT_REACHED:
            said = "Not reached last night; tonight again"
        return said, ""
    if state == assistant.FAILED:
        why = assistant.what_to_say(transcript.prepare_reason)
        return "Not enriched: " + why, "danger"
    if recording.case_id is not None:
        if open_request(recording.case, recording) is not None:
            return "Requested now, waiting for an Admin", "warn"
        declined = last_declined(recording.case, recording)
        if declined is not None and declined.decided_at is not None:
            said = "Not yet enriched with vision; the request was declined"
            if declined.line:
                said += f": {declined.line}"
            return said, ""
    return "Not yet enriched with vision", ""


def offers(case, *, user) -> dict:
    """Which buttons the case page shows, by the position and the person."""
    where = position()
    on = assistant.record_on() and settings_store.get("moments_available")
    return {
        "tonight": bool(on and where == OVERNIGHT),
        "ask": bool(on and where in (OVERNIGHT, ASKED)),
        "now": bool(on and user.is_admin),
        "window": window_words(),
    }


def line(case) -> str:
    """The case page's line about its videos not yet enriched, or nothing."""
    waiting = unenriched(case)
    if not waiting:
        return ""
    count = f"{len(waiting)} video{'' if len(waiting) == 1 else 's'}"
    return f"{count} not yet enriched with vision"


def tick(user) -> dict:
    """What the upload page offers: the tick, its start, and its caption."""
    on = bool(settings_store.get("moments_available") and assistant.record_on())
    where = position()
    if where == LANDS:
        caption = (
            "The picture is described and joined to the words as each transcript lands."
        )
    elif where == OVERNIGHT:
        caption = (
            "The picture is described and joined to the words tonight, "
            f"{window_words()}. You get an email when it is done."
        )
    else:
        caption = "Vision runs when an Admin allows it for a case."
    return {
        "offered": on and where != ASKED,
        "ticked": settings_store.vision_tick_default(),
        "needs_case": where != LANDS,
        "caption": caption,
        "session_line": (
            "Vision runs tonight and needs a case; a session's recordings are gone "
            "by then. Put it in a case to enrich it."
            if where == OVERNIGHT
            else ""
        ),
    }


# The mail -------------------------------------------------------------------------


def note_progress(recording) -> None:
    """Called when a video's enrichment ends: the batch's second message, and
    the requests it answers."""
    from core import mail

    try:
        batch = recording.batch
    except Exception:  # noqa: BLE001 - a Recording with no Batch has no mail
        batch = None
    if (
        batch is not None
        and batch.email_when_done
        and batch.vision
        and scheduled()
        and batch.vision_mail_sent_at is None
    ):
        videos = [
            one
            for one in batch.recordings.all()
            if one.vision_wanted and one.case_id is not None and eligible(one)
        ]
        if videos and all(_ended(one) for one in videos):
            batch.vision_mail_sent_at = timezone.now()
            batch.save(update_fields=["vision_mail_sent_at"])
            mail.vision_done(batch.user, videos, where=batch, link_case=videos[0].case)
    if recording.case_id is not None:
        for request in VisionRequest.objects.filter(
            case=recording.case, state=VisionRequest.ALLOWED, done_mailed_at=None
        ).filter(models.Q(recording=recording) | models.Q(recording=None)):
            note_progress_for_request(request)


def note_progress_for_request(request: VisionRequest) -> None:
    from core import mail

    videos = [one.recording for one in request.transcripts()]
    if videos and not all(_ended(one) for one in videos):
        return
    request.done_mailed_at = timezone.now()
    request.save(update_fields=["done_mailed_at"])
    mail.vision_done(request.asked_by, videos, where=request, link_case=request.case)


def _ended(recording) -> bool:
    transcript = getattr(recording, "transcript", None)
    return transcript is not None and transcript.prepare_state in (
        assistant.DONE,
        assistant.FAILED,
    )
