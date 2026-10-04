"""The Team, Assigned to and Reviewed (Phase 9 chapter 3).

A Case's Team is everyone with it: the Owner first, then each Collaborator,
with when they last opened it and how many recordings are assigned to them,
reviewed by them and noted by them; one list seen by all of them. An Owner
may mark a Collaborator "also an owner", so they may add people and assign
as the Owner does; nothing is narrower than a Collaborator.

A Recording in a Case may carry one assignee from the Team: set on one row,
on ticked rows, or by Divide among, which deals the unassigned recordings
evenly, oldest added first. Assigned says who, never whether.

Reviewed is the one mark of completion, made by the assignee (or an owner for
anyone) on purpose, after one question, and taken back when wrong. A new
assignee clears it. Nothing is overdue: a recording assigned and not yet
reviewed is work, not a warning.

Every change is one audit row, naming the username and the cause and never a
title or a note. The audit log is the history; there is no history table.
"""

from __future__ import annotations

import uuid

from django.db.models import Q
from django.utils import timezone

from core import audit

CATEGORY = audit.Category.CASES

ONE = "one"
TICKED = "ticked"
DIVIDED = "divided"


# Who may ---------------------------------------------------------------------------


def may_mark(recording, user) -> bool:
    """Who may mark a recording reviewed, or take the mark back: its assignee,
    and whoever may assign (the Owner, an also-owner, an Admin)."""
    if recording.case is None:
        return False
    if recording.assigned_to_id == user.pk:
        return True
    return recording.case.may_direct(user)


def is_on_the_team(case, person) -> bool:
    from core import sharing

    if case.owner_id == person.pk:
        return True
    return sharing.on() and sharing.is_collaborator(case, person)


# The Team ---------------------------------------------------------------------------


def person_counts(case) -> dict:
    """By user id: how many of the case's recordings are assigned to them,
    reviewed under their assignment, and noted by them (distinct recordings)."""
    from core.jobs import Segment
    from core.notes import MomentNote

    counts: dict = {}

    def row(user_id):
        return counts.setdefault(user_id, {"assigned": 0, "reviewed": 0, "noted": 0})

    for user_id, reviewed in case.recordings.filter(
        assigned_to__isnull=False
    ).values_list("assigned_to_id", "reviewed_on"):
        row(user_id)["assigned"] += 1
        if reviewed is not None:
            row(user_id)["reviewed"] += 1
    noted: dict = {}
    for user_id, recording_id in (
        Segment.objects.filter(
            transcript__recording__case=case,
            same_as_other_side=False,
            note_by__isnull=False,
        )
        .exclude(note="")
        .values_list("note_by_id", "transcript__recording_id")
    ):
        noted.setdefault(user_id, set()).add(recording_id)
    for user_id, recording_id in MomentNote.objects.filter(
        recording__case=case, note_by__isnull=False
    ).values_list("note_by_id", "recording_id"):
        noted.setdefault(user_id, set()).add(recording_id)
    for user_id, recordings in noted.items():
        row(user_id)["noted"] = len(recordings)
    return counts


def team(case, viewer=None, names: dict | None = None) -> list[dict]:
    """The Team block's rows: the Owner first, then each Collaborator."""
    from core import sharing

    counts = person_counts(case)
    if names is None:
        names = names_for(case)
    empty = {"assigned": 0, "reviewed": 0, "noted": 0}
    rows = [
        {
            "person": case.owner,
            "name": names.get(case.owner.pk, case.owner.shown_name),
            "share": None,
            "role": "owner",
            "status": "" if case.owner.status == "active" else case.owner.status,
            "last_opened": None,
            "is_you": viewer is not None and case.owner_id == viewer.pk,
            **counts.get(case.owner_id, empty),
        }
    ]
    if sharing.on():
        for share in sharing.collaborators(case):
            rows.append(
                {
                    "person": share.person,
                    "name": names.get(share.person_id, share.person.shown_name),
                    "share": share,
                    "role": "also-owner" if share.also_owner else "collaborator",
                    "status": share.status,
                    "last_opened": share.last_opened,
                    "is_you": viewer is not None and share.person_id == viewer.pk,
                    **counts.get(share.person_id, empty),
                }
            )
    return rows


def set_also_owner(share, wanted: bool, *, by, request=None) -> None:
    """The one mark an Owner may put on a Share (or take off)."""
    if bool(share.also_owner) == bool(wanted):
        return
    share.also_owner = bool(wanted)
    share.save(update_fields=["also_owner"])
    audit.write(
        CATEGORY,
        "case owner added" if wanted else "case owner removed",
        actor=by,
        request=request,
        affected_user=share.case.owner if share.case.owner_id != by.pk else None,
        object_type="case",
        object_id=share.case.pk,
        object_label=share.case.name,
        collaborator=share.person.username,
    )


# Assigning --------------------------------------------------------------------------


def _row(event: str, recording, actor, request=None, **details) -> None:
    case = recording.case
    audit.write(
        CATEGORY,
        event,
        actor=actor,
        request=request,
        affected_user=(
            case.owner if actor is not None and case.owner_id != actor.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        **details,
    )


def assign(recording, person, *, by, request=None, cause: str = ONE, **more) -> bool:
    """Give one recording to one team member; None or the same person is no
    change. A new assignee clears the Reviewed mark, which was the old one's.
    Returns whether anything changed."""
    if person is not None and recording.assigned_to_id == person.pk:
        return False
    if person is None:
        return unassign(recording, by=by, request=request, cause="owner")
    recording.assigned_to = person
    recording.assigned_by = by
    recording.assigned_on = timezone.now()
    # The old assignee's mark goes with them, whatever this copy of the row
    # believed.
    recording.reviewed_by = None
    recording.reviewed_on = None
    recording.reviewed_nothing_to_note = False
    recording.save(
        update_fields=[
            "assigned_to",
            "assigned_by",
            "assigned_on",
            "reviewed_by",
            "reviewed_on",
            "reviewed_nothing_to_note",
        ]
    )
    _row(
        "recording assigned",
        recording,
        by,
        request,
        to=person.username,
        cause=cause,
        **more,
    )
    return True


def unassign(recording, *, by, request=None, cause: str = "owner") -> bool:
    if recording.assigned_to_id is None:
        return False
    recording.assigned_to = None
    recording.assigned_by = None
    recording.assigned_on = None
    recording.save(update_fields=["assigned_to", "assigned_by", "assigned_on"])
    _row("recording unassigned", recording, by, request, cause=cause)
    return True


def divide(case, people, *, by, request=None) -> dict:
    """Deal the case's unassigned recordings, oldest added first, one to each
    of the people in turn; the remainder goes to the first. Nothing anybody
    assigned is moved. Returns the count each person got, by username."""
    people = [one for one in people if is_on_the_team(case, one)]
    counts = {one.username: 0 for one in people}
    if not people:
        return counts
    batch = uuid.uuid4().hex[:12]
    waiting = list(case.recordings.filter(assigned_to__isnull=True).order_by("created"))
    for index, recording in enumerate(waiting):
        person = people[index % len(people)]
        assign(recording, person, by=by, request=request, cause=DIVIDED, divide=batch)
        counts[person.username] += 1
    return counts


def clear_for(case, person, *, by, request=None, cause: str) -> int:
    """Every assignment this person holds in the case, cleared (their Share
    revoked, say). Returns how many."""
    cleared = 0
    for recording in case.recordings.filter(assigned_to=person):
        if unassign(recording, by=by, request=request, cause=cause):
            cleared += 1
    return cleared


# Reviewed ---------------------------------------------------------------------------


def mark_reviewed(
    recording, *, by, request=None, nothing_to_note: bool = False
) -> None:
    recording.reviewed_by = by
    recording.reviewed_on = timezone.now()
    recording.reviewed_nothing_to_note = bool(nothing_to_note)
    recording.save(
        update_fields=["reviewed_by", "reviewed_on", "reviewed_nothing_to_note"]
    )
    _row(
        "recording marked reviewed",
        recording,
        by,
        request,
        cause="assignee" if recording.assigned_to_id == by.pk else "owner",
        nothing_to_note=bool(nothing_to_note),
    )


def unmark_reviewed(recording, *, by, request=None) -> None:
    if recording.reviewed_on is None:
        return
    recording.reviewed_by = None
    recording.reviewed_on = None
    recording.reviewed_nothing_to_note = False
    recording.save(
        update_fields=["reviewed_by", "reviewed_on", "reviewed_nothing_to_note"]
    )
    _row(
        "recording marked not reviewed",
        recording,
        by,
        request,
        cause="assignee" if recording.assigned_to_id == by.pk else "owner",
    )


def reviewed_words(recording, user) -> str:
    """The pill's words: "Reviewed by you, 4 Oct"; nothing when not reviewed."""
    if recording.reviewed_on is None:
        return ""
    if recording.reviewed_by_id is None:
        return f"Reviewed, {recording.reviewed_on:%d %b}"
    who = (
        "you"
        if recording.reviewed_by_id == user.pk
        else recording.reviewed_by.shown_name
    )
    return f"Reviewed by {who}, {recording.reviewed_on:%d %b}"


def next_for(user, recording):
    """The person's next assigned recording in the same case not yet reviewed,
    oldest added first after this one, else the earliest; None when none."""
    mine = recording.case.recordings.filter(
        assigned_to=user, reviewed_on__isnull=True
    ).exclude(pk=recording.pk)
    after = mine.filter(created__gt=recording.created).order_by("created").first()
    return after or mine.order_by("created").first()


def my_notes_on(recording, user) -> int:
    """How many notes this person left on the recording, for the question."""
    from core.jobs import Segment
    from core.notes import MomentNote

    transcript = getattr(recording, "transcript", None)
    lines = 0
    if transcript is not None:
        lines = (
            Segment.objects.filter(transcript=transcript, note_by=user)
            .exclude(note="")
            .count()
        )
    return lines + MomentNote.objects.filter(recording=recording, note_by=user).count()


# The words ---------------------------------------------------------------------------


def case_counts(case) -> dict:
    """For the Dashboard line: recordings, assigned, reviewed."""
    rows = case.recordings
    return {
        "recordings": rows.count(),
        "assigned": rows.filter(assigned_to__isnull=False).count(),
        "reviewed": rows.filter(reviewed_on__isnull=False).count(),
    }


def yours(case, user) -> dict:
    """For Home and the Dashboard line: "6 of 80 left for you"."""
    mine = case.recordings.filter(assigned_to=user)
    total = mine.count()
    return {"total": total, "left": mine.filter(reviewed_on__isnull=True).count()}


def filtered(rows, who: str, state: str, viewer) -> list:
    """The Recordings tab's rows narrowed by the pills: who is me, nobody or a
    username; state is reviewed or unreviewed."""
    out = rows
    if who == "me":
        out = [one for one in out if one.assigned_to_id == viewer.pk]
    elif who == "nobody":
        out = [one for one in out if one.assigned_to_id is None]
    elif who:
        out = [
            one
            for one in out
            if one.assigned_to_id is not None and one.assigned_to.username == who
        ]
    if state == "reviewed":
        out = [one for one in out if one.reviewed_on is not None]
    elif state == "unreviewed":
        out = [one for one in out if one.reviewed_on is None]
    return out


def team_members(case) -> list:
    """The people a recording may be assigned to: the Owner and the Collaborators."""
    from core import sharing

    people = [case.owner]
    if sharing.on():
        people += [share.person for share in sharing.collaborators(case)]
    return people


def names_for(case) -> dict:
    """Each team member's name as the pages show it (v1.121.3): the shown
    name, with the username beside it when another member shares that name,
    so an Assigned to column never reads the same name twice for two people."""
    people = team_members(case)
    counts: dict = {}
    for one in people:
        counts[one.shown_name] = counts.get(one.shown_name, 0) + 1
    return {
        one.pk: (
            f"{one.shown_name} ({one.username})"
            if counts[one.shown_name] > 1
            else one.shown_name
        )
        for one in people
    }


def find_member(case, typed: str):
    """A team member by username or shown name, or None."""
    wanted = (typed or "").strip().casefold()
    if not wanted:
        return None
    for person in team_members(case):
        if wanted in (person.username.casefold(), person.shown_name.casefold()):
            return person
    return None


def with_assignee_q(user) -> Q:
    return Q(assigned_to=user)
