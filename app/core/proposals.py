"""Proposed events as moments on a Recording (Phase 10 chapter 4, v1.168.0).

A Proposal is a moment on one Recording with a sentence and a why, made by
the assistant's judgement, the watch-phrase search, a Look for run or the
comparison, kept in a list of its own and touching nothing until a person
accepts it. Accepting writes a Note on that Recording at the line being
spoken, or at the moment when nothing was said, in the acceptor's name. A
Note already follows its Recording everywhere: onto the case's chronology
and onto every Incident the Recording is a synced camera of (Phase 8
chapter 11). So an accepted proposal appears wherever it should with nothing
else kept, and the note carries one small thing, `note_from`, saying what it
came from, so the source, the why and the AI notice survive.

Until v1.167.0 a proposal was an Event row with `proposed` set, on an
Incident, and Accept made it an Event of its own source. The rows waiting on
the upgrade stay as they are until accepted or dismissed (the maintainer's
word, 2026-10-29); Accept on one of them writes a note too, and the row
goes. Every run from v1.168.0 writes Proposal rows.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core import audit, incidents

WAITING = "waiting"
ACCEPTED = "accepted"
DISMISSED = "dismissed"

# The words a note's origin shows: on the recording page, the Notes tab, the
# chronology's source pill and the exports.
FROM_PROPOSAL = "from a proposed event"
FROM_REPORT = "from the report"


class Proposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="proposals"
    )
    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="proposals"
    )
    # The Incident it was proposed for, when a run on an incident made it;
    # kept as a name when the incident goes.
    incident = models.ForeignKey(
        "core.Incident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposals",
    )
    # Seconds into the recording, never a clock: the case's chronology and
    # each incident place it by the clock the recording already has.
    at = models.FloatField()
    until = models.FloatField(null=True, blank=True)
    text = models.CharField(max_length=500)
    why = models.CharField(max_length=300, blank=True, default="")
    rests_on = models.CharField(max_length=500, blank=True, default="")
    # assistant, watch, looked, report: the chronology's own source words.
    source = models.CharField(max_length=10)
    state = models.CharField(max_length=10, default=WAITING)
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    made = models.DateTimeField(default=timezone.now)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided = models.DateTimeField(null=True, blank=True)
    # The note it became: on a line, or at a moment.
    note_segment = models.ForeignKey(
        "core.Segment", on_delete=models.SET_NULL, null=True, blank=True
    )
    note_moment = models.ForeignKey(
        "core.MomentNote", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["recording_id", "at", "made"]

    def __str__(self) -> str:
        return f"proposal on {self.recording_id} at {self.at:.1f}"

    def at_on(self, camera) -> float:
        """The moment on an incident's clock, through one of its cameras."""
        return camera.starts_at + self.at

    def origin(self) -> dict:
        """What the note it becomes says it came from."""
        return {
            "kind": "proposal",
            "source": self.source,
            "why": self.why,
            "rests_on": self.rests_on,
            "proposal": str(self.pk),
            "words": origin_words(self.source),
        }


def origin_words(source: str, *, page: int | None = None, n: int | None = None) -> str:
    """The short words a note shows for where it came from."""
    if source == "report":
        return f"{FROM_REPORT}, page {page}, paragraph {n}" if page else FROM_REPORT
    if source == "watch":
        return f"{FROM_PROPOSAL} (a watch phrase)"
    if source == "looked":
        return f"{FROM_PROPOSAL} (looked for)"
    return FROM_PROPOSAL


def is_assistants(origin: dict | None) -> bool:
    """Whether a note's origin is the assistant's words, for the AI notice:
    its judgement or a Look for, never the app's own watch-phrase search."""
    return bool(origin) and origin.get("source") in ("assistant", "looked", "report")


def waiting(incident, cameras=None) -> list:
    """The Proposal rows waiting on an incident, each with the camera it sits
    on; one whose camera is gone or no longer synced is left out. The
    incident's cameras may be given, already read."""
    cameras = {
        one.recording_id: one
        for one in (
            incident.cameras.select_related("recording") if cameras is None else cameras
        )
        if one.is_synced()
    }
    rows = []
    for one in Proposal.objects.filter(incident=incident, state=WAITING).select_related(
        "recording", "proposed_by"
    ):
        camera = cameras.get(one.recording_id)
        if camera is not None:
            rows.append((one, camera))
    return rows


def waiting_count(incident) -> int:
    """Both kinds, until the old rows are gone."""
    return (
        Proposal.objects.filter(incident=incident, state=WAITING).count()
        + incident.events.filter(proposed=True, dismissed=False).count()
    )


# Writing the note ------------------------------------------------------------------


def write_note(
    recording,
    seconds: float,
    text: str,
    *,
    origin: dict,
    by,
    request=None,
    segment=None,
):
    """The note a proposal or a finding becomes: on the line being spoken at
    the moment (the one it rested on when known), else at the moment. A line
    or moment already noted keeps its note, and the new words join it after a
    blank line. Returns ("line", segment) or ("moment", note)."""
    from core import notes

    transcript = getattr(recording, "transcript", None)
    if segment is None:
        segment = notes.spoken_at(transcript, seconds)
    if segment is not None:
        had = segment.note
        wanted = f"{had}\n\n{text}" if had else text
        notes.set_note(segment, wanted, by=by, request=request, where="proposal")
        segment.refresh_from_db(fields=["note"])
        if not had:
            segment.note_from = origin
            segment.save(update_fields=["note_from"])
            # The note events carry the origin's why and what it rests on.
            notes.reflect_line(segment)
        return "line", segment
    one = (
        notes.MomentNote.objects.filter(
            recording=recording,
            at__gte=seconds - notes.SAME_MOMENT,
            at__lte=seconds + notes.SAME_MOMENT,
        )
        .order_by("at")
        .first()
    )
    had = one.note if one is not None else ""
    wanted = f"{had}\n\n{text}" if had else text
    told = notes.note_at(
        recording, seconds, wanted, by=by, request=request, where="proposal"
    )
    one = notes.MomentNote.objects.get(pk=told["id"])
    if not had:
        one.note_from = origin
        one.save(update_fields=["note_from"])
        notes.reflect_moment(one)
    return "moment", one


# Accept and dismiss ----------------------------------------------------------------


def accept(proposal: Proposal, *, by, request=None):
    """One press: the sentence becomes a note on the recording in the
    acceptor's name; the proposal stays, marked accepted, pointing at it."""
    if proposal.state != WAITING:
        return proposal
    segment = None
    if proposal.rests_on and hasattr(proposal.recording, "transcript"):
        from core import notes

        segment = notes.spoken_at(proposal.recording.transcript, proposal.at)
    kind, home = write_note(
        proposal.recording,
        proposal.at,
        proposal.text,
        origin=proposal.origin(),
        by=by,
        request=request,
        segment=segment,
    )
    proposal.state = ACCEPTED
    proposal.decided_by = by
    proposal.decided = timezone.now()
    if kind == "line":
        proposal.note_segment = home
    else:
        proposal.note_moment = home
    proposal.save(
        update_fields=["state", "decided_by", "decided", "note_segment", "note_moment"]
    )
    _row(proposal, "proposal accepted", by, request, how=kind)
    return proposal


def dismiss(proposal: Proposal, *, by, request=None) -> None:
    """Put away: kept as dismissed so a later run does not offer it again."""
    if proposal.state != WAITING:
        return
    proposal.state = DISMISSED
    proposal.decided_by = by
    proposal.decided = timezone.now()
    proposal.save(update_fields=["state", "decided_by", "decided"])
    _row(proposal, "proposal dismissed", by, request)


def _row(proposal: Proposal, event: str, by, request, **details) -> None:
    audit.write(
        incidents.CATEGORY,
        event,
        actor=by,
        affected_user=proposal.case.owner,
        object_type="proposal",
        object_id=proposal.pk,
        object_label=(proposal.recording.title or proposal.recording.original_filename)[
            :200
        ],
        request=request,
        source=proposal.source,
        case=proposal.case.name,
        **({"incident": proposal.incident.name} if proposal.incident_id else {}),
        **details,
    )
    from core import cases

    cases.note_activity(proposal.case, by=by)


def accept_old(event, *, by, request=None):
    """An Event-row proposal from before v1.168.0, accepted: the note is
    written on its camera's recording at its moment and the row goes; the
    note event the chronology draws takes its place."""
    if not event.proposed:
        return event
    camera = event.camera
    if camera is None or not camera.is_synced():
        raise ValueError("Its camera is no longer synced, so there is no line for it.")
    seconds = max(0.0, event.at - camera.starts_at)
    origin = {
        "kind": "proposal",
        "source": event.source,
        "why": event.why,
        "rests_on": event.rests_on,
        "proposal": "",
        "words": origin_words(event.source),
    }
    write_note(
        camera.recording,
        seconds,
        event.text,
        origin=origin,
        by=by,
        request=request,
        segment=event.segment,
    )
    incident = event.incident
    event.delete()
    audit.write(
        incidents.CATEGORY,
        "proposal accepted",
        actor=by,
        affected_user=incident.case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        request=request,
        source=origin["source"],
        case=incident.case.name,
        incident=incident.name,
    )
    from core import cases

    cases.note_activity(incident.case, by=by)
    return event
