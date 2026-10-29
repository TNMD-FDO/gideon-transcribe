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


def accept(proposal: Proposal, *, by, request=None, text: str | None = None):
    """One press: the sentence becomes a note on the recording in the
    acceptor's name; the proposal stays, marked accepted, pointing at it.
    Accept and edit (v1.169.0) gives the words the person wrote instead."""
    if proposal.state != WAITING:
        return proposal
    words = " ".join(text.split()) if text else proposal.text
    segment = None
    if proposal.rests_on and hasattr(proposal.recording, "transcript"):
        from core import notes

        segment = notes.spoken_at(proposal.recording.transcript, proposal.at)
    kind, home = write_note(
        proposal.recording,
        proposal.at,
        words,
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


# The case's run and the tab (Phase 10 chapter 4, the second release, v1.169.0) --


class ProposalRun(models.Model):
    """Propose events over the whole case: one run at a time per Case, kept
    the way an Incident keeps its proposals_* columns, so the page has the
    same words and the same expectation."""

    case = models.OneToOneField(
        "core.Case", on_delete=models.CASCADE, related_name="proposal_run"
    )
    state = models.CharField(max_length=10, blank=True, default="")
    reason = models.CharField(max_length=40, blank=True, default="")
    at = models.DateTimeField(null=True, blank=True)
    by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    found = models.IntegerField(default=0)
    read = models.IntegerField(default=0)
    cut = models.IntegerField(default=0)
    watch = models.IntegerField(default=0)
    look_for = models.CharField(max_length=300, blank=True, default="")
    looked = models.BooleanField(default=False)
    expectation = models.JSONField(default=dict, blank=True)
    # When a full run (not a Look for) last finished: a recording whose
    # transcript landed since is "not yet read".
    full_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"proposal run on {self.case_id}"


def tab_offered() -> bool:
    """The Proposed events tab shows as the incident's button does: with the
    assistant's judgement on, or the watch phrases listed."""
    from core import incident_assistant, settings_store

    return incident_assistant.proposals_on() or bool(settings_store.watch_phrases())


def readable(case) -> list:
    """The case's recordings a run reads: those with a transcript."""
    return [
        one
        for one in case.recordings.select_related("transcript").order_by(
            "created", "title"
        )
        if hasattr(one, "transcript")
    ]


def run_possible(case) -> bool:
    return tab_offered() and bool(readable(case))


def ask_for_run(case, *, by, look_for: str = "") -> bool:
    """Propose events pressed on the case: one run at a time; the Look for is
    this run's alone, as the incident's is."""
    if not run_possible(case):
        return False
    from core import expectation, incident_assistant, sitting

    run, _made = ProposalRun.objects.get_or_create(case=case)
    if run.state in ("queued", "running"):
        return True
    run.state = "queued"
    run.reason = ""
    run.by = by
    run.look_for = " ".join(str(look_for or "").split())[:300]
    looking = bool(run.look_for) and incident_assistant.proposals_on()
    tokens = 0
    for one in readable(case):
        share = sitting._share_of_recording(one)
        tokens += share["record"] if share else 0
    run.expectation = expectation.note(
        "case_look_for" if looking else "case_events", tokens
    )
    run.save()
    from core import tasks

    tasks.propose_case_events.defer(case_id=str(case.pk))
    return True


class _Lone:
    """A recording read on its own, in the shape the proposer reads a camera
    (starts_at, length, camera_id): its times are its own, from zero."""

    def __init__(self, recording):
        self.recording = recording
        self.pk = recording.pk
        self.starts_at = 0.0

    def length(self) -> float:
        return float(self.recording.duration_seconds or 0.0)

    def ends_at(self) -> float:
        return self.length()

    def camera_id(self) -> str:
        return str((self.recording.stamp or {}).get("camera") or self.recording.title)


def _taken_on(recording, made: list[float]) -> list[float]:
    """The moments on a recording a new proposal must keep clear of: its
    notes, and every Proposal row on it, of either run and any state."""
    from core import notes

    transcript = getattr(recording, "transcript", None)
    taken = list(made)
    if transcript is not None:
        taken += [
            float(start)
            for start in transcript.segments.exclude(note="")
            .filter(same_as_other_side=False)
            .values_list("start", flat=True)
        ]
    taken += [one.at for one in notes.moments_of(recording)]
    taken += list(
        Proposal.objects.filter(recording=recording).values_list("at", flat=True)
    )
    return taken


def _known_on(recording, made: list) -> list[str]:
    """What a window's head lists for a recording: its notes and the
    proposals made so far on it, at their times into the recording."""
    from core import exports, notes

    rows = []
    transcript = getattr(recording, "transcript", None)
    if transcript is not None:
        for start, note in (
            transcript.segments.exclude(note="")
            .filter(same_as_other_side=False)
            .values_list("start", "note")
        ):
            rows.append((float(start), f"the office's note: {note}"))
    for one in notes.moments_of(recording):
        rows.append((one.at, f"the office's note: {one.note}"))
    for at, text in made:
        rows.append((at, text))
    return [f"{exports.clock(at)} {text}" for at, text in sorted(rows)]


def propose_for_case(case_id, attempt: int = 1) -> None:
    """The run over every recording of the case that has a transcript: the
    watch phrases first, by the app itself; then the engine's judgement, each
    recording in windows with a second look, the answers checked as the
    incident's run checks them (Phase 7 chapter 2). This run's own waiting
    rows are replaced; an incident's waiting rows and every dismissed row
    stay, and nothing is proposed within a few seconds of one, of a note, or
    of an accepted proposal. A Look for run proposes only what was looked
    for and replaces nothing."""
    import json
    import time

    from django.utils import timezone as tz

    from core import (
        assistant,
        engine,
        expectation,
        exports,
        incident_assistant,
        prompts,
        settings_store,
    )
    from core.assistant import DONE, FAILED, QUEUED, RUNNING, PromptTemplate
    from core.cases import Case

    case = Case.objects.filter(pk=case_id).select_related("owner").first()
    if case is None:
        return
    run = ProposalRun.objects.filter(case=case).select_related("by").first()
    if run is None or run.state not in (QUEUED, RUNNING):
        return
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.INCIDENT_EVENTS)
    templates_line = (
        f"ground-rules v{ground.version}; Proposed events v{template.version}"
    )
    run.state = RUNNING
    run.expectation = expectation.started(run.expectation)
    run.save(update_fields=["state", "expectation"])
    looked = bool(run.look_for) and incident_assistant.proposals_on()
    look_for = run.look_for if looked else ""
    usage = {"input_tokens": 0, "output_tokens": 0}
    model = ""
    calls = cut = windows = second_looks = watch_found = read = 0
    found = 0
    phrases = settings_store.watch_phrases()

    def finish(state: str, reason: str = "") -> None:
        run.state = state
        run.reason = reason
        run.at = tz.now()
        run.looked = looked
        if not looked:
            run.full_at = run.at
        run.found = found
        run.read = read
        run.cut = cut
        run.watch = watch_found
        run.look_for = ""
        run.save()
        if calls:
            audit.write(
                audit.Category.LLM,
                "AI assistant call",
                actor=run.by,
                outcome=(
                    audit.Outcome.SUCCESS if state == DONE else audit.Outcome.FAILURE
                ),
                reason_class="" if state == DONE else reason,
                affected_user=(
                    case.owner
                    if run.by is not None and case.owner_id != run.by.pk
                    else None
                ),
                object_type="case",
                object_id=case.pk,
                object_label=case.name,
                feature=incident_assistant.FEATURE_EVENTS,
                templates=templates_line,
                model=model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                duration_seconds=round(time.monotonic() - started, 1),
                calls=calls,
                cameras=read,
                found=found,
                cut_short=cut,
                windows=windows,
                second_looks=second_looks,
                watch_hits=watch_found,
                **expectation.for_audit(run.expectation),
                look_for=bool(look_for),
                looked=looked,
                case_run=True,
            )
        audit.write(
            incidents.CATEGORY,
            "events proposed",
            actor=run.by,
            affected_user=case.owner,
            object_type="case",
            object_id=case.pk,
            object_label=case.name,
            found=found,
            cameras=read,
            watch_hits=watch_found,
            windows=windows,
            whole_case=True,
        )

    def keep(lone: _Lone, source: str, fields: dict) -> None:
        Proposal.objects.create(
            case=case,
            recording=lone.recording,
            incident=None,
            at=fields["at"],
            until=fields.get("until"),
            text=fields["text"],
            why=fields.get("why", ""),
            rests_on=fields.get("rests_on", ""),
            source=source,
            proposed_by=run.by,
        )

    try:
        recordings = readable(case)
        if not recordings:
            raise engine.Problem(engine.ERROR, "no recording has a transcript")
        if not incident_assistant.proposals_on() and not phrases:
            raise engine.Problem(engine.ERROR, "proposals are off")
        if not looked:
            Proposal.objects.filter(
                case=case, incident__isnull=True, state=WAITING
            ).delete()
        made_on: dict = {}

        # The floor: the watch phrases, saved as they are found.
        for recording in [] if looked else recordings:
            lone = _Lone(recording)
            mine = made_on.setdefault(str(recording.pk), [])
            taken = _taken_on(recording, [at for at, _ in mine])
            for fields in incident_assistant.watch_hits(lone, phrases):
                if any(
                    abs(fields["at"] - other) < incident_assistant.NEAR_SECONDS
                    for other in taken
                ):
                    continue
                keep(lone, "watch", fields)
                mine.append((fields["at"], fields["text"]))
                taken.append(fields["at"])
                watch_found += 1
                found += 1

        if not incident_assistant.proposals_on():
            read = len(recordings)
            finish(DONE)
            return

        problem = assistant._unreachable()
        if problem:
            raise problem
        system = prompts.system_message(
            ground.text, template.text, prompts.INCIDENT_EVENTS_FORMAT
        )
        context = settings_store.incident_events_context()
        answer_cap = settings_store.incident_events_answer_cap()
        window_seconds = settings_store.incident_events_window()
        second = settings_store.second_look()
        schema = prompts.incident_events_schema()
        most = (
            incident_assistant.LOOK_MOST if looked else incident_assistant.WINDOW_MOST
        )
        for recording in recordings:
            lone = _Lone(recording)
            transcript = recording.transcript
            digest = assistant.digest_text(transcript) if assistant.digests_on() else ""
            if digest:
                body_lines = [line for line in digest.splitlines() if line.strip()]
                nature = (
                    "the record of this recording (a condensation of its words "
                    "and its picture)"
                )
            else:
                body_lines = prompts.render(prompts.lines_of(transcript)).splitlines()
                nature = "the transcript of this recording"
            if not body_lines:
                continue
            read += 1
            mine = made_on.setdefault(str(recording.pk), [])
            for window in incident_assistant._windows(body_lines, window_seconds):
                windows += 1
                kept_here = 0
                said: list[str] = []
                for look in ("first", "second"):
                    if kept_here >= most:
                        break
                    if look == "second" and (not second or looked):
                        break
                    taken = _taken_on(recording, [at for at, _ in mine])
                    head = prompts.case_events_input(
                        lone.camera_id(),
                        exports.clock(lone.length()),
                        nature,
                        _known_on(recording, mine),
                        context=context,
                        look_for=look_for,
                    )
                    for chunk in incident_assistant._chunks(
                        system, head, window, answer_cap
                    ):
                        given = incident_assistant._folded("\n".join(chunk))
                        user = head + "\n\n" + "\n".join(chunk)
                        if look == "second":
                            second_looks += 1
                            user += (
                                "\n\n"
                                + prompts.INCIDENT_EVENTS_SECOND_LOOK
                                + "\n\nYou proposed:\n"
                                + ("\n".join(said) or "none")
                            )
                        answer = engine.complete(
                            assistant._messages(system, user),
                            max_completion_tokens=assistant.cap(answer_cap),
                            thinking=False,
                            timeout=assistant.time_limit(
                                incident_assistant.FEATURE_EVENTS
                            ),
                            schema=schema,
                            **assistant.SUGGESTION_SAMPLING,
                        )
                        calls += 1
                        if answer.get("finish_reason") == "length":
                            cut += 1
                        model = answer.get("model", "") or model
                        usage["input_tokens"] += answer.get("input_tokens", 0) or 0
                        usage["output_tokens"] += answer.get("output_tokens", 0) or 0
                        try:
                            try:
                                parsed = json.loads(answer["text"])
                            except ValueError:
                                parsed = json.loads(
                                    prompts.salvage_json(answer["text"])
                                )
                            raw = (
                                parsed.get("events", [])
                                if isinstance(parsed, dict)
                                else []
                            )
                            if not isinstance(raw, list):
                                raise ValueError("not a list")
                        except (ValueError, AttributeError):
                            continue
                        for item in raw:
                            if kept_here >= most:
                                break
                            fields = incident_assistant._keep_proposal(
                                item, lone, given, taken
                            )
                            if fields is None:
                                continue
                            keep(lone, "looked" if looked else "assistant", fields)
                            mine.append((fields["at"], fields["text"]))
                            taken.append(fields["at"])
                            kept_here += 1
                            found += 1
                            said.append(f"{item.get('time', '')} {fields['text']}")
        finish(DONE)
    except engine.Problem as problem:
        finish(FAILED, problem.reason)


def run_json(case) -> dict:
    """The run's state for the tab: the button's line and whether to poll."""
    from django.utils import timezone as tz

    from core import assistant, expectation, incident_assistant

    run = ProposalRun.objects.filter(case=case).first()
    state = run.state if run else ""
    pending = Proposal.objects.filter(case=case, state=WAITING).count()
    words = ""
    if state == "queued":
        words = "Waiting for the engine..."
    elif state == "running":
        words = "Reading the recordings..."
    elif state == "done":
        when = tz.localtime(run.at).strftime("%H:%M") if run.at else ""
        if run.looked:
            words = (
                f"Looked on {run.read} recording{'' if run.read == 1 else 's'} at "
                f"{when}: {run.found} proposed"
                if run.found
                else f"Nothing found on what you looked for ({when})"
            )
        else:
            words = (
                f"Proposed {run.found} event{'' if run.found == 1 else 's'} at {when} "
                f"from {run.read} recording{'' if run.read == 1 else 's'}"
                if run.found
                else f"Nothing to propose ({when})"
            )
        if run.watch:
            words += f", {run.watch} from the watch phrases"
        if run.cut:
            words += (
                f"; {run.cut} answer{'' if run.cut == 1 else 's'} cut short, "
                "raise Proposed events answer cap"
            )
    elif state == "failed":
        words = assistant.what_to_say(run.reason)
    never_read = [
        (one.stamp or {}).get("camera") or one.title
        for one in readable(case)
        if run is None
        or run.full_at is None
        or (one.transcript.created and one.transcript.created > run.full_at)
    ]
    if never_read and state not in ("queued", "running"):
        shown = ", ".join(never_read[:4]) + (
            f" and {len(never_read) - 4} more" if len(never_read) > 4 else ""
        )
        words = (words + " " if words else "") + f"Not yet read: {shown}."
    return {
        "on": tab_offered(),
        "possible": run_possible(case),
        "state": state,
        "words": words,
        "pending": pending,
        "busy": state in ("queued", "running"),
        "never_read": len(never_read),
        "expectation": expectation.json_of(
            run.expectation if run else {}, state, "proposals"
        ),
        "assistant": incident_assistant.proposals_on(),
    }


def day_rows(case) -> list[dict]:
    """The case's proposals in the shape the chronology lays notes out in:
    the waiting and the accepted, never the dismissed; each with its why, its
    source words, what it became, and the incident it was proposed for."""
    from django.urls import reverse

    from core import notes

    rows = []
    for one in (
        Proposal.objects.filter(case=case)
        .exclude(state=DISMISSED)
        .select_related("recording", "incident", "proposed_by", "decided_by")
        .select_related("note_segment", "note_moment")
    ):
        became = ""
        note_url = ""
        if one.state == ACCEPTED:
            who = one.decided_by.shown_name if one.decided_by else "a person"
            when = notes.date_of(one.decided) if one.decided else ""
            became = f"a note on {_title(one.recording)} by {who}" + (
                f", {when}" if when else ""
            )
            note_url = (
                reverse("viewer", args=[one.recording_id]) + f"?t={one.at:.1f}&note=1"
            )
        rows.append(
            {
                "key": f"proposal:{one.pk}",
                "kind": "proposal",
                "id": str(one.pk),
                "recording": str(one.recording_id),
                "at": float(one.at),
                "text": one.text,
                "said": one.rests_on,
                "who": "",
                "to_check": False,
                "by": one.proposed_by.shown_name if one.proposed_by else "",
                "by_id": one.proposed_by_id,
                "when": notes.date_of(one.made),
                "why": one.why,
                "source": one.source,
                "source_words": source_words(one.source),
                "state": one.state,
                "became": became,
                "note_url": note_url,
                "for_incident": one.incident.name if one.incident_id else "",
            }
        )
    return rows


def _title(recording) -> str:
    return str((recording.stamp or {}).get("camera") or recording.title)


def source_words(source: str) -> str:
    return {
        "watch": "Watch phrase",
        "looked": "Looked for",
        "report": "From the report",
    }.get(source, "Proposed by the assistant")


def decide_all(case, action: str, *, by, request=None) -> int:
    """Accept all or Dismiss all on the tab: every waiting row of the case."""
    count = 0
    for one in list(
        Proposal.objects.filter(case=case, state=WAITING).select_related("recording")
    ):
        if action == "accept":
            accept(one, by=by, request=request)
        else:
            dismiss(one, by=by, request=request)
        count += 1
    return count
