"""Taking a file from arrived to Ready, and saying why when it cannot be.

The order is fixed by the Media handling chapter: hash, probe and acceptance,
Sides, then the audio the service is sent. A Recording is Ready after that, and
the Playback copy and the waveform follow without holding recognition up.

Nothing is deleted because a step failed. A Recording that fails keeps
everything it has, says what went wrong in plain words, and offers Retry, so a
Retry can reuse the steps that already worked.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core import audit, media, settings_store
from core.models import User
from core.recordings import Batch, MediaState, Recording, Refusal, Side

log = logging.getLogger("transcribe.media")


def accept(
    user: User,
    batch: Batch,
    source: Path,
    original_filename: str,
    **choices,
) -> Recording:
    """Make the Recording and put the file where it belongs.

    The bytes are moved into the Recording's own folder, named by id and never
    by anything a person typed: no file name, user name, or title ever appears
    in a path.
    """
    recording = Recording.objects.create(
        batch=batch,
        user=user,
        title=Path(original_filename).stem or original_filename,
        original_filename=original_filename,
        size_bytes=source.stat().st_size,
        media_state=MediaState.CHECKING,
        **choices,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, recording.original_path)
    return recording


def prepare(recording: Recording) -> Recording:
    """Everything between arriving and Ready. Safe to run again after a failure."""
    try:
        _check(recording)
        _find_sides(recording)
        _make_asr_audio(recording)
    except media.MediaError as problem:
        return _failed(recording, problem)

    recording.media_state = MediaState.READY
    recording.save()
    _record_accepted(recording)
    log.info(
        "recording %s is ready: %.1f minutes, %d side(s)",
        recording.id,
        (recording.duration_seconds or 0) / 60,
        recording.sides.count(),
    )
    return recording


def _check(recording: Recording) -> None:
    """Hash it, look inside it, and decide whether it can be accepted at all."""
    recording.media_state = MediaState.CHECKING
    recording.save(update_fields=["media_state"])

    path = recording.original_path
    if not path.exists() or path.stat().st_size == 0:
        raise media.MediaError(Refusal.MESSAGES[Refusal.EMPTY_FILE], Refusal.EMPTY_FILE)

    recording.sha256 = media.hash_file(path)

    # The same file twice in the same place. Other people's files are never
    # looked at, so nobody learns what anybody else has uploaded, and the
    # refusal applies per destination: the same file in another Case is
    # allowed, because a Case is a different place to keep it.
    same_place = (
        Recording.objects.filter(case=recording.case)
        if recording.case_id
        else Recording.objects.filter(user=recording.user, case__isnull=True)
    )
    already = (
        same_place.filter(sha256=recording.sha256)
        .exclude(pk=recording.pk)
        .exclude(media_state=MediaState.REJECTED)
        .first()
    )
    if already is not None:
        raise media.MediaError(
            Refusal.MESSAGES[Refusal.ALREADY_UPLOADED].format(title=already.title),
            Refusal.ALREADY_UPLOADED,
        )

    probed = media.probe(path)
    recording.probe = probed.raw
    _keep_the_probe(recording, probed.raw)
    recording.duration_seconds = probed.duration_seconds
    recording.tracks_found = len(probed.tracks)

    if not probed.has_audio:
        raise media.MediaError(Refusal.MESSAGES[Refusal.NO_AUDIO], Refusal.NO_AUDIO)

    longest = settings_store.longest_recording_seconds()
    if probed.duration_seconds > longest:
        raise media.MediaError(
            Refusal.MESSAGES[Refusal.TOO_LONG].format(limit=_hours(longest)),
            Refusal.TOO_LONG,
        )

    media.test_decode(path, probed.best_track)
    recording.save()


def _find_sides(recording: Recording) -> None:
    """Work out what has to be transcribed separately.

    Most recordings are one Side. A file with genuinely different audio tracks
    is one Side per track, so nothing on any track is missed. A narrowband
    two-channel recording whose channels carry different things is a call, and
    each channel is a Side.
    """
    probed = media.probe(recording.original_path)
    track = probed.best_track

    recording.sides.all().delete()

    if track is not None and media.looks_like_a_call(recording.original_path, track):
        recording.is_two_channel_call = True
        recording.tracks_distinct = 1
        for number in (1, 2):
            Side.objects.create(
                recording=recording,
                number=number,
                kind=Side.CHANNEL,
                name=f"Side {number}",
            )
        log.info("recording %s is a two-channel call", recording.id)
    else:
        recording.is_two_channel_call = False
        recording.tracks_distinct = 1
        Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")

    recording.save()


def _make_asr_audio(recording: Recording) -> None:
    """One prepared file per Side, which is what the service is sent."""
    recording.media_state = MediaState.PREPARING
    recording.save(update_fields=["media_state"])

    probed = media.probe(recording.original_path)
    track = probed.best_track

    for side in recording.sides.all():
        channel = side.number - 1 if side.kind == Side.CHANNEL else None
        media.make_asr_audio(
            recording.original_path,
            side.asr_path,
            track,
            channel=channel,
            profile=recording.preprocessing,
        )


def make_playback(recording: Recording) -> Recording:
    """The Playback copy and the waveform, after the Recording is Ready.

    Recognition never waits for these: a Job can be at the WhisperX service
    while they are still being made, and the pages say "Preparing audio" or
    "Preparing video" until they are there.
    """
    try:
        probed = media.probe(recording.original_path)
        target = recording.folder / f"playback{media.playback_suffix(probed)}"
        media.make_playback_copy(
            recording.original_path, target, probed, recording.preprocessing
        )
        media.make_waveform(target, recording.waveform_path)
    except media.MediaError as problem:
        # A Recording without a Playback copy is still transcribable, so this
        # is not a failure of the Recording. The pages keep saying it is being
        # prepared, and the journal says what went wrong.
        log.warning(
            "the playback copy of recording %s could not be made: %s",
            recording.id,
            problem.message,
        )
        return recording

    recording.playback_ready = True
    recording.save(update_fields=["playback_ready"])
    log.info("recording %s can be played", recording.id)
    return recording


def _keep_the_probe(recording: Recording, raw: dict) -> None:
    """Write the raw ffprobe output beside the Recording's own bytes.

    It is on the database row as well, which is what the Details panel reads.
    It is on disk because the file set a Recording carries is fixed: original,
    probe.json, the ASR audio per Side, the playback copy, the waveform, and
    clips. In Phase 2 that set is what a Case keeps, and a file that was never
    written cannot be kept.
    """
    import json

    try:
        recording.folder.mkdir(parents=True, exist_ok=True)
        (recording.folder / "probe.json").write_text(
            json.dumps(raw, indent=2), encoding="utf-8"
        )
    except OSError:
        # The Recording is transcribable without it, and the same facts are on
        # its row, so this is worth a line in the journal and nothing more.
        log.warning(
            "the probe output of recording %s could not be written", recording.id
        )


def _failed(recording: Recording, problem: media.MediaError) -> Recording:
    """A refusal or a failure, said plainly, with nothing thrown away.

    A refusal is the file's own fault and the Recording never joins the
    person's list. A failure is the app's, and Retry is offered.
    """
    refused = problem.reason_class in Refusal.ALL
    recording.media_state = MediaState.REJECTED if refused else MediaState.FAILED
    recording.refusal_class = problem.reason_class
    recording.failure_message = problem.message
    recording.save()

    audit.write(
        audit.Category.RECORDINGS,
        "upload rejected" if refused else "upload accepted",
        actor=recording.user,
        outcome=audit.Outcome.FAILURE,
        reason_class=problem.reason_class,
        object_type="recording",
        object_id=recording.id,
        object_label=recording.original_filename,
    )
    log.info("recording %s refused: %s", recording.id, problem.reason_class)
    return recording


def _hours(seconds: float) -> str:
    hours = seconds / 3600
    whole = int(hours)
    return f"{whole} hour{'s' if whole != 1 else ''}"


def _record_accepted(recording: Recording) -> None:
    """The audit row for a Recording that got as far as Ready."""
    audit.write(
        audit.Category.RECORDINGS,
        "upload accepted",
        actor=recording.user,
        object_type="recording",
        object_id=recording.id,
        object_label=recording.original_filename,
        size_bytes=recording.size_bytes,
        duration_seconds=round(recording.duration_seconds or 0, 1),
        sha256=recording.sha256[:8],
        sides=recording.sides.count(),
        two_channel_call=recording.is_two_channel_call,
        tracks_found=recording.tracks_found,
    )
