"""The viewer: reading a Transcript, and correcting it.

The Transcript comes first, at reading width. Everything else on the page is
there to serve reading it: the player above, the speakers beside it, and the
tools out of the way until they are wanted.
"""

from __future__ import annotations

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import assistant, audit
from core.jobs import Segment
from core.media_access import media_root
from core.recordings import Recording

log = logging.getLogger("transcribe.viewer")

# One colour per Speaker, used for the name and the bar beside the row, so
# that the same person is the same colour everywhere. They
# are the stylesheet's own tokens rather than fixed colours, because each one
# has a light and a dark value and a person may be reading in either.
SPEAKER_COLOURS = [
    "var(--sp1)",
    "var(--sp2)",
    "var(--sp3)",
    "var(--sp4)",
    "var(--sp5)",
    "var(--sp6)",
    "var(--sp7)",
    "var(--sp8)",
]


def colour_for(index: int) -> str:
    return SPEAKER_COLOURS[index % len(SPEAKER_COLOURS)]


def open_recording(request: HttpRequest, recording_id) -> Recording | None:
    """The Recording, if this person may open it, with the Admin row written.

    An Admin may open anybody's material, and every opening writes a row
    naming the Admin, the item, and the owner. The banner on the page says the
    same thing to the Admin.
    """
    recording = Recording.objects.filter(pk=recording_id).select_related("user").first()
    if recording is None:
        return None

    # A Recording in a Case the Retention policy has put in the Recycle bin is
    # nobody's to open, an Admin's included, until the Case is restored.
    from core import cases

    if not cases.reachable(recording):
        return None

    if recording.user_id == request.user.pk:
        audit.write(
            audit.Category.RECORDINGS,
            "Recording opened",
            actor=request.user,
            request=request,
            object_type="recording",
            object_id=recording.pk,
            object_label=recording.original_filename,
        )
        return recording

    if not request.user.is_admin:
        return None

    audit.write(
        audit.Category.ADMIN,
        "another user's item opened",
        actor=request.user,
        request=request,
        affected_user=recording.user,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        item="recording",
    )
    return recording


@login_required
def viewer(request: HttpRequest, recording_id) -> HttpResponse:
    """The page itself."""
    recording = open_recording(request, recording_id)
    if recording is None:
        return redirect(reverse("home"))

    from core import cases, exports

    # Opening a Recording in a Case is use of that Case, so its Retention
    # clock moves. An Admin looking into somebody else's does not count.
    cases.used(recording, by=request.user)

    transcript = getattr(recording, "transcript", None)
    # Ready, not merely present: the copy is written under another name until
    # it is whole, and the flag is set only once the waveform is there too.
    # Recognition finishes before the copy does, so a page opened in between
    # shows "Preparing video" and asks again until this says yes.
    playback = recording.playback_path() if recording.playback_ready else None

    speakers = []
    if transcript is not None:
        # order_by("speaker") is not for the order: it clears the Segment's own
        # ordering, which is by start and id. Without that, Django puts those
        # two columns in the SELECT to order by them, DISTINCT then sees every
        # row as different, and the panel shows one chip per segment instead of
        # one per speaker.
        names = list(
            transcript.segments.filter(same_as_other_side=False)
            .exclude(speaker="")
            .order_by("speaker")
            .values_list("speaker", flat=True)
            .distinct()
        )
        from core import people

        speakers = [
            {
                "name": name,
                "colour": colour_for(number),
                # The Role badge, inside a Case, when the name is a Person's.
                "role": people.role_of(recording, name),
            }
            for number, name in enumerate(names)
        ]

    job = recording.jobs.order_by("-created").first()

    return render(
        request,
        "viewer.html",
        {
            "page": "viewer",
            "recording": recording,
            # Which of the AI assistant's three features the page offers;
            # the panels' contents come from the assistant's own endpoint.
            "assistant": assistant.features(),
            # The Case's People, for the rename box to offer; none in a Workspace.
            "people": _people_of(recording),
            "speaker_roles": _roles_if_in_a_case(recording),
            # The rest of the case, so somebody working through a matter moves
            # between its recordings without going back to the case page.
            "in_case": _the_rest_of_the_case(recording),
            "transcript": transcript,
            "speakers": speakers,
            "language_name": (
                exports.language_name(transcript.language)
                if transcript is not None
                else ""
            ),
            "sides": list(recording.sides.all()),
            "job": job,
            "is_someone_elses": recording.user_id != request.user.pk,
            "being_replaced": being_replaced(recording),
            "media_url": (
                f"{media_root(recording)}/{playback.name}" if playback else ""
            ),
            # While the copy is still being written there is no file to judge
            # by, so the overlay's word comes from the probe: "Preparing
            # video" for a recording with a picture, and not "audio".
            "is_video": (
                bool(playback and playback.suffix == ".mp4")
                or (playback is None and _expects_video(recording))
            ),
            "waveform_url": (
                f"{media_root(recording)}/waveform.json"
                if recording.playback_ready and recording.waveform_path.exists()
                else ""
            ),
            "frame_rate": frame_rate(recording),
        },
    )


@login_required
def segments(request: HttpRequest, recording_id) -> JsonResponse:
    """The Transcript itself, as the page reads it."""
    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None or (
        recording.user_id != request.user.pk and not request.user.is_admin
    ):
        return JsonResponse({"error": "no such recording"}, status=404)

    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return JsonResponse({"segments": []})

    return JsonResponse(
        {
            "word_timestamps": transcript.word_timestamps,
            "word_timestamps_reason": transcript.word_timestamps_reason,
            # What both Sides of a call said together: shown once, named for
            # both, and counted here so the page can say so plainly.
            "shared_segments": transcript.shared_segments,
            "segments": [
                {
                    "id": segment.pk,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "speaker": segment.speaker,
                    "corrected": segment.corrected,
                    "words": segment.words or [],
                }
                # The second copy of what both Sides heard is kept in the
                # database and left out of the reading, so the announcement at
                # the head of a call is read once rather than twice.
                for segment in transcript.segments.filter(same_as_other_side=False)
            ],
        }
    )


def being_replaced(recording) -> bool:
    """Whether a Process again is running against this Recording.

    While it is, the old Transcript is readable and nothing else: a correction
    to text that is about to be replaced would be lost without anybody being
    told.
    """
    from core.jobs import JobState

    return recording.jobs.filter(
        state__in=JobState.LIVE, batch__is_reprocessing=True
    ).exists()


@login_required
@require_POST
def correct(request: HttpRequest, recording_id, segment_id) -> JsonResponse:
    """Change one Segment's text.

    The audit row says which Segment and when, and never what it said before
    or after: the text of a correction is on the never-logged list, like the
    Transcript it belongs to.
    """
    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None or (
        recording.user_id != request.user.pk and not request.user.is_admin
    ):
        return JsonResponse({"error": "no such recording"}, status=404)

    from core import cases

    cases.used(recording, by=request.user)

    if being_replaced(recording):
        return JsonResponse(
            {
                "error": "This transcript is being replaced, so it cannot be "
                "corrected until the new one lands."
            },
            status=409,
        )

    segment = Segment.objects.filter(
        pk=segment_id, transcript__recording=recording
    ).first()
    if segment is None:
        return JsonResponse({"error": "no such segment"}, status=404)

    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "that could not be read"}, status=400)

    segment.text = (wanted.get("text") or "").strip()
    segment.corrected = True
    segment.save(update_fields=["text", "corrected"])

    audit.write(
        audit.Category.EDITS,
        "Segment corrected",
        actor=request.user,
        request=request,
        affected_user=(
            recording.user if recording.user_id != request.user.pk else None
        ),
        object_type="segment",
        object_id=segment.pk,
        object_label=f"{segment.start:.1f}-{segment.end:.1f}",
    )
    return JsonResponse({"corrected": True})


@login_required
@require_POST
def speakers(request: HttpRequest, recording_id) -> JsonResponse:
    """Rename a Speaker, or merge one into another.

    Renaming applies to every Segment of that Speaker; merging relabels every
    Segment of the merged one. Neither row holds a name, because a Speaker's
    name is on the never-logged list.
    """
    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None or (
        recording.user_id != request.user.pk and not request.user.is_admin
    ):
        return JsonResponse({"error": "no such recording"}, status=404)

    from core import cases

    cases.used(recording, by=request.user)

    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return JsonResponse({"error": "there is no transcript yet"}, status=404)
    if being_replaced(recording):
        return JsonResponse(
            {
                "error": "This transcript is being replaced, so its speakers "
                "cannot be changed until the new one lands."
            },
            status=409,
        )

    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "that could not be read"}, status=400)

    was = (wanted.get("from") or "").strip()
    now = (wanted.get("to") or "").strip()
    if not was or not now:
        return JsonResponse({"error": "both names are needed"}, status=400)

    merging = transcript.segments.filter(speaker=now).exists()
    changed = transcript.segments.filter(speaker=was).update(speaker=now)
    # Inside a Case, a name means a person: the new name joins or makes one.
    from core import people

    people.on_named(
        recording, now, by=request.user, how="named in the viewer", request=request
    )

    audit.write(
        audit.Category.EDITS,
        "Speakers merged" if merging else "Speaker renamed",
        actor=request.user,
        request=request,
        affected_user=(
            recording.user if recording.user_id != request.user.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        segments_changed=changed,
    )
    return JsonResponse({"changed": changed, "merged": merging})


@login_required
def media_state(request: HttpRequest, recording_id) -> JsonResponse:
    """Whether the Playback copy is ready yet, for a page that opened before it was.

    Asked every five seconds by a viewer showing "Preparing video", so it
    writes no audit row: an Admin's opening was recorded when the page was
    opened, and a poll is not another opening.
    """
    from core import cases

    recording = Recording.objects.filter(pk=recording_id).select_related("user").first()
    if (
        recording is None
        or not cases.reachable(recording)
        or (recording.user_id != request.user.pk and not request.user.is_admin)
    ):
        return JsonResponse({"error": "no such recording"}, status=404)
    return JsonResponse({"ready": recording.playback_ready})


@login_required
def details(request: HttpRequest, recording_id) -> JsonResponse:
    """The Provenance: where a Recording came from and how it was processed.

    The same facts the Word export prints on its last pages, as name and value
    pairs, and never a word of the Transcript.
    """
    from core import exports

    recording = (
        Recording.objects.filter(pk=recording_id).select_related("user", "case").first()
    )
    if recording is None or (
        recording.user_id != request.user.pk and not request.user.is_admin
    ):
        return JsonResponse({"error": "no such recording"}, status=404)

    transcript = getattr(recording, "transcript", None)
    probe = recording.probe or {}

    # A Recording in a Case says so first, because it is the fact that decides
    # whether it survives the sign-out.
    in_a_case = []
    if recording.case_id:
        in_a_case = [("Case", recording.case.name)]
        if recording.recording_type:
            in_a_case.append(("Recording type", recording.recording_type))
        if recording.description:
            in_a_case.append(("Description", recording.description))

    rows = [
        *in_a_case,
        ("Original name", recording.original_filename),
        ("Size", f"{recording.size_bytes / 1024 / 1024:.1f} MB"),
        ("SHA-256", recording.sha256),
        (
            "Uploaded by",
            f"{recording.user.username} on {recording.created:%d %B %Y %H:%M}",
        ),
        ("Length", exports.clock(recording.duration_seconds or 0)),
        ("Container", probe.get("format_name", "")),
        (
            "Frame rate",
            f"{frame_rate(recording):g} per second" if _has_video(recording) else "",
        ),
        ("Sound sources found", str(recording.tracks_found)),
        ("Distinct sources", str(recording.tracks_distinct)),
        (
            "Two-channel call",
            "yes, one side per party" if recording.is_two_channel_call else "no",
        ),
        (
            "Sides",
            # A Recording with one side has nobody to name, so it reads as a
            # count rather than as "side 1".
            ", ".join(one.name for one in recording.sides.all() if one.name)
            or str(recording.sides.count() or 1),
        ),
        (
            "Preprocessing",
            f"{recording.preprocessing.title()}, loudness normalised "
            "(linear, -16 LUFS)",
        ),
    ]

    if transcript is not None:
        runs = list((transcript.provenance or {}).values())
        used = (runs[0].get("settings_used") if runs else {}) or {}
        service = (runs[0].get("service") if runs else {}) or {}
        timings = (runs[0].get("timings_seconds") if runs else {}) or {}
        rows += [
            ("Model", used.get("model", "")),
            ("Model revision", used.get("model_revision", "")),
            ("Task", f"{used.get('task_run', '')} ({used.get('task_reason', '')})"),
            ("Language", exports.language_name(transcript.language)),
            (
                "Word timing",
                "yes"
                if transcript.word_timestamps
                else f"no ({transcript.word_timestamps_reason or 'not available'})",
            ),
            ("Diarization", "yes" if used.get("diarize") else "no"),
            (
                "Speaker hint",
                str(recording.speakers_exactly or recording.speakers_between or "none"),
            ),
            (
                "Vocabulary",
                f"{used.get('vocabulary_terms_used', 0)} of "
                f"{used.get('vocabulary_terms_given', 0)} terms used"
                if used.get("vocabulary_terms_given")
                else "none given",
            ),
            (
                "Service version",
                (service.get("versions") or {}).get("service", "")
                or service.get("version", ""),
            ),
            (
                "Processing time",
                _plainly(timings.get("total", 0)) if timings else "",
            ),
            ("Processed", f"{transcript.created:%d %B %Y %H:%M}"),
            ("Segments", str(transcript.segments.count())),
        ]

    # One line per Clip that exists now; a deleted Clip simply drops out.
    for clip in recording.clips.all():
        rows.append(
            (
                f"Clip: {clip.title}",
                f"{exports.clock(clip.start)} to {exports.clock(clip.end)}, "
                f"{'captions burned, ' if clip.burn_captions else ''}"
                f"{'excerpt' if clip.include_excerpt else 'no excerpt'}"
                + (f", rendered {clip.rendered:%d %b %H:%M}" if clip.rendered else ""),
            )
        )

    return JsonResponse(
        {"rows": [[name, value] for name, value in rows if str(value).strip()]}
    )


def _plainly(seconds: float) -> str:
    """A duration a person reads, in the units that suit its size."""
    seconds = float(seconds or 0)
    if seconds < 1:
        return "under a second"
    if seconds < 90:
        return f"{seconds:.0f} second{'' if round(seconds) == 1 else 's'}"
    minutes = seconds / 60
    return f"{minutes:.0f} minute{'' if round(minutes) == 1 else 's'}"


def _the_rest_of_the_case(recording) -> list:
    """Every Recording in this one's Case, in the order the Case page lists them.

    Empty for a Recording in no Case, and empty while Folder management is
    off, so the rail simply is not drawn.
    """
    from core import cases, exports

    if not recording.case_id or not cases.folder_management_on():
        return []

    rows = []
    for one in recording.case.recordings.order_by("-created"):
        job = one.jobs.order_by("-created").first()
        rows.append(
            {
                "recording": one,
                "here": one.pk == recording.pk,
                "length": exports.clock(one.duration_seconds or 0),
                "ready": hasattr(one, "transcript"),
                "in_the_queue": bool(job is not None and job.is_live),
                "failed": one.media_state in ("failed", "rejected"),
            }
        )
    return rows


def _people_of(recording) -> list[dict]:
    from core import people

    if not people._in_a_case(recording):
        return []
    return [
        {"name": one.name, "role": one.role, "count": len(one.recordings())}
        for one in recording.case.people.all()
    ]


def _roles_if_in_a_case(recording) -> list[str]:
    from core import people

    return people.roles() if people._in_a_case(recording) else []


def _has_video(recording) -> bool:
    playback = recording.playback_path()
    return bool(playback and playback.suffix == ".mp4")


def _expects_video(recording) -> bool:
    """Whether the recording has a picture, from the probe, before any copy exists."""
    from core import media

    try:
        return media.video_stream(recording.probe or {}) is not None
    except Exception:  # noqa: BLE001 - an odd probe is not a reason to fail the page
        return False


def frame_rate(recording) -> float:
    """The frame rate the viewer steps by, from the Provenance.

    An audio-only Recording has none, and the viewer steps a tenth of a second
    instead.
    """
    for stream in (recording.probe or {}).get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or ""
        if "/" in rate:
            over, under = rate.split("/", 1)
            try:
                if float(under):
                    return float(over) / float(under)
            except ValueError:
                pass
    return 0.0
