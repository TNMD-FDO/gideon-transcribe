"""The two hooks the upload sidecar calls, and the checks behind them.

Bytes never pass through Python. The sidecar receives them straight to disk and
asks the app two questions: may this upload start, and here is a finished one.
Everything the app decides about an upload is decided in those two answers.

The sidecar is on the app's own network and nothing else can reach it, so the
hook endpoint takes no token of its own; what it does take is a Login session,
because that is what says whose upload this is.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import timedelta
from http.cookies import SimpleCookie
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from core import settings_store
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Refusal

log = logging.getLogger("transcribe.uploads")

# Near enough to the limit to be worth saying so, and far enough that a person
# can act on it. A build constant, not a setting.
QUOTA_WARNING_SHARE = 0.80

# An upload that receives nothing for this long is dropped and its Recording
# removed, so an unfinished upload can never hold a person's one Batch open.
# A closed laptop must not stop somebody uploading tomorrow.
SILENCE_ALLOWED = timedelta(minutes=10)


@dataclass(frozen=True)
class Refused:
    """An upload the app will not take, with words and a reason class."""

    message: str
    reason_class: str


def used_bytes(user: User) -> int:
    """Everything on disk that counts against this person, which is their quota.

    Their Workspace, and their Cases whoever uploaded into them. A Case counts
    against its owner even while Folder management is off, because it is still
    on the disk.
    """
    from core.cases import Case

    # Workspace only here: a Recording in a Case is counted with the Case,
    # once, against whoever owns it rather than whoever uploaded it.
    mine = sum(
        recording.disk_bytes()
        for recording in user.recordings.filter(case__isnull=True)
    )
    theirs = sum(case.disk_bytes() for case in Case.objects.filter(owner=user))
    return mine + theirs


def quota_bytes(user: User) -> int:
    """This person's space: their own figure if an Admin set one, else the default."""
    if user.quota_gb:
        return user.quota_gb * settings_store.GB
    return settings_store.default_quota_bytes()


def free_disk_bytes() -> int:
    """What is left on the drive the App data folder lives on."""
    usage = shutil.disk_usage(settings.DATA_DIR)
    return usage.free


def as_gb(figure: int) -> str:
    return f"{figure / 1024**3:.0f} GB"


def as_size(figure: int) -> str:
    """A size in the unit that suits it, for a sentence somebody must trust.

    The quota is in whole gigabytes and says so, but a confirmation asking
    somebody to agree to losing three jail calls cannot tell them it is
    removing "0 GB" and expect to be believed.
    """
    if figure >= 1024**3:
        return f"{figure / 1024**3:.1f} GB"
    if figure >= 1024**2:
        return f"{figure / 1024**2:.0f} MB"
    if figure >= 1024:
        return f"{figure / 1024:.0f} KB"
    return f"{figure} bytes"


def room_left(user: User) -> int:
    """What this person may still add, in bytes; never below zero."""
    return max(0, quota_bytes(user) - used_bytes(user))


def check_before_upload(
    user: User, batch: Batch, size_bytes: int, files_in_batch: int, into=None
) -> Refused | None:
    """Everything the app can decide before a single byte arrives.

    Asked by the Upload page so a person is told early, and again by the
    sidecar's pre-create hook so the answer holds whatever the page did.

    `into` is the Case the file is going to, when known. A Recording added to
    somebody else's Case counts against that owner's space, so the space
    tested is theirs and the refusal names whose it is.
    """
    # The floor is tested with this file counted (v1.131.0): what is free
    # once it has arrived, not what is free now.
    if free_disk_bytes() - size_bytes < settings_store.minimum_free_disk_bytes():
        return Refused(Refusal.MESSAGES[Refusal.DISK_FULL], Refusal.DISK_FULL)

    largest = settings_store.largest_file_bytes()
    if size_bytes > largest:
        return Refused(
            Refusal.MESSAGES[Refusal.TOO_LARGE].format(limit=as_gb(largest)),
            Refusal.TOO_LARGE,
        )

    if size_bytes <= 0:
        return Refused(Refusal.MESSAGES[Refusal.EMPTY_FILE], Refusal.EMPTY_FILE)

    per_batch = settings_store.files_per_batch()
    if files_in_batch > per_batch:
        return Refused(
            Refusal.MESSAGES[Refusal.LIMIT_EXCEEDED].format(
                limit=per_batch, over=files_in_batch - per_batch
            ),
            Refusal.LIMIT_EXCEEDED,
        )

    whose = into.owner if into is not None and into.owner_id != user.pk else user
    quota = quota_bytes(whose)
    after = used_bytes(whose) + size_bytes
    if after > quota:
        if whose.pk != user.pk:
            message = Refusal.MESSAGES[Refusal.QUOTA_EXCEEDED_THEIRS].format(
                owner=whose.shown_name, used=as_gb(after), quota=as_gb(quota)
            )
        else:
            message = Refusal.MESSAGES[Refusal.QUOTA_EXCEEDED].format(
                used=as_gb(after), quota=as_gb(quota)
            )
        return Refused(message, Refusal.QUOTA_EXCEEDED)

    return None


def storage_warning(user: User, adding_bytes: int = 0) -> str | None:
    """The line shown near the limit, and nothing at all while there is room.

    People see no meter and no figure until it starts to matter, because a
    number that never changes is a number nobody reads.
    """
    quota = quota_bytes(user)
    after = used_bytes(user) + adding_bytes
    if after < quota * QUOTA_WARNING_SHARE:
        return None
    if after > quota:
        return None  # The refusal says it instead.
    # What is counted is said (v1.89.0): the figure is the person's
    # recordings in cases and in this session, not the session alone.
    return (
        f"Your recordings use {as_gb(after)} of your {as_gb(quota)}, in cases "
        "and this session."
    )


def in_flight() -> dict[str, tuple[int, float]]:
    """How far each upload has got, from the pieces on disk.

    The app is told when an upload starts and when it finishes, and nothing in
    between, which is what the contract asks of the sidecar. The pieces
    themselves are the record of what is happening: an .info file naming the
    Recording, and beside it the bytes so far.

    Returns, per Recording id: how many bytes have arrived, and how long ago
    the file last grew.
    """
    folder = Path(settings.UPLOADS_DIR)
    if not folder.is_dir():
        return {}

    now = time.time()
    found: dict[str, tuple[int, float]] = {}
    for info in folder.glob("*.info"):
        try:
            described = json.loads(info.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        recording = (described.get("MetaData") or {}).get("recording")
        if not recording:
            continue

        pieces = info.with_suffix("")
        try:
            state = pieces.stat()
        except OSError:
            found[recording] = (0, now - info.stat().st_mtime)
            continue
        found[recording] = (state.st_size, now - state.st_mtime)
    return found


def drop_abandoned() -> int:
    """Remove uploads that have gone quiet, and the Recordings waiting on them.

    Two ways an upload goes quiet: it started and stopped growing, or it never
    started at all because the browser gave up or the person closed the page.
    Both leave a Recording that would otherwise hold its owner's one Batch
    open for ever.
    """
    from core.recordings import MediaState, Recording

    arriving = in_flight()
    cutoff = timezone.now() - SILENCE_ALLOWED
    dropped = 0

    # Never a Live recording (v1.131.0): it is "uploading" from Record until
    # Stop, and a Pause stops its pieces; it has its own end (core.live).
    waiting = Recording.objects.filter(media_state=MediaState.UPLOADING).filter(
        Q(live__isnull=True) | Q(live={})
    )
    for recording in waiting:
        received, quiet_for = arriving.get(str(recording.pk), (None, None))

        if received is None:
            # Nothing on disk at all. Only old ones: a Recording made a moment
            # ago is one whose first byte has not arrived yet.
            if recording.created > cutoff:
                continue
        elif quiet_for < SILENCE_ALLOWED.total_seconds():
            continue

        log.info(
            "dropping the upload of recording %s: nothing received for ten minutes",
            recording.pk,
        )
        _remove_pieces(recording)
        recording.delete()
        dropped += 1

    return dropped


def _remove_pieces(recording) -> None:
    """Take the half-arrived bytes and the Recording's folder off the disk."""
    folder = Path(settings.UPLOADS_DIR)
    for info in folder.glob("*.info"):
        try:
            described = json.loads(info.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (described.get("MetaData") or {}).get("recording") == str(recording.pk):
            info.with_suffix("").unlink(missing_ok=True)
            info.unlink(missing_ok=True)

    shutil.rmtree(recording.folder, ignore_errors=True)


def _session_of(event: dict) -> LoginSession | None:
    """Whose upload this is, from the cookie on the original request.

    The sidecar passes the browser's own request headers to the hook, so the
    session comes from the cookie the browser already sent rather than from
    anything the page put in the upload's metadata. A credential in metadata
    would be written to disk beside the pieces and passed around with them.
    """
    headers = (event.get("HTTPRequest", {}) or {}).get("Header", {}) or {}
    raw = headers.get("Cookie") or headers.get("cookie") or []
    if isinstance(raw, str):
        raw = [raw]

    jar = SimpleCookie()
    for line in raw:
        jar.load(line)
    cookie = jar.get(settings.SESSION_COOKIE_NAME)
    if cookie is None:
        return None

    return (
        LoginSession.objects.filter(session_key=cookie.value, ended__isnull=True)
        .select_related("user")
        .first()
    )


# The sidecar names each upload by an id of its own making: letters, digits
# and a few plain marks, never a path. Anything else is not the sidecar's and
# is never joined onto a folder (v1.130.0).
UPLOAD_ID = re.compile(r"^[A-Za-z0-9+_-]{1,80}$")


def arrived_file(upload_id: str) -> Path | None:
    """The sidecar's file for an upload id, or None for an id that is not one.

    The id is accepted in the sidecar's own shape only, and the path it makes
    has to resolve to a file directly inside the uploads folder; a climbing
    id, an absolute one, or a folder is refused before anything is moved.
    """
    if not upload_id or not UPLOAD_ID.match(upload_id):
        return None
    folder = Path(settings.UPLOADS_DIR)
    arrived = folder / upload_id
    try:
        inside = arrived.resolve().parent == folder.resolve()
    except OSError:
        return None
    if not inside or not arrived.is_file():
        return None
    return arrived


def claim(recording: Recording) -> bool:
    """Take an uploading Recording for its finish: one taker, by one update.

    True for the caller that moved the row from Uploading to Checking; False
    for anybody who comes second, whose file has already been taken.
    """
    taken = Recording.objects.filter(
        pk=recording.pk, media_state=MediaState.UPLOADING
    ).update(media_state=MediaState.CHECKING)
    if taken:
        recording.media_state = MediaState.CHECKING
    return bool(taken)


def through_the_front_door(request: HttpRequest) -> bool:
    """Did this request come through Caddy rather than from the sidecar?

    The reverse proxy marks every request it forwards; the sidecar's hook call
    reaches the app on the project network directly and carries no such mark.
    The Caddyfile refuses the hook's path as well; this is the second lock.
    """
    return bool(
        request.headers.get("X-Forwarded-For")
        or request.headers.get("X-Forwarded-Host")
    )


@csrf_exempt
def hook(request: HttpRequest) -> JsonResponse:
    """The sidecar's two questions, on one endpoint.

    Answered with the shape tusd expects: a rejection carries an HTTP response
    for the browser, and everything else is an empty acceptance.
    """
    if request.method != "POST":
        return JsonResponse({}, status=405)
    if through_the_front_door(request):
        # Only the sidecar asks these questions; a browser is told nothing.
        return JsonResponse({}, status=404)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({}, status=400)

    name = request.headers.get("Hook-Name") or body.get("Type", "")
    event = body.get("Event", {}) or {}
    upload = event.get("Upload", {}) or {}
    metadata = upload.get("MetaData", {}) or {}

    if name == "pre-create":
        if (metadata.get("live") or "") == "1":
            return _pre_create_live(event, upload)
        return _pre_create(event, upload)
    if name == "post-finish":
        return _post_finish(event, upload, metadata)
    if name == "post-create" and (metadata.get("live") or "") == "1":
        return _post_create_live(event, upload, metadata)
    return JsonResponse({})


def _post_create_live(event: dict, upload: dict, metadata: dict) -> JsonResponse:
    """A Live recording's upload exists: its id is noted on the Recording here,
    by the sidecar (v1.132.0), as well as by the page, whose one-shot post
    could miss it and leave an early end with nothing to take."""
    from core import live

    session = _session_of(event)
    if session is None:
        return JsonResponse({})
    recording = Recording.objects.filter(
        pk=metadata.get("recording", ""),
        user=session.user,
        media_state=MediaState.UPLOADING,
    ).first()
    if recording is not None and recording.is_live:
        live.note_upload(recording, str(upload.get("ID") or ""))
    return JsonResponse({})


def _reject(message: str, reason_class: str) -> JsonResponse:
    log.info("an upload was refused before it started: %s", reason_class)
    return JsonResponse(
        {
            "RejectUpload": True,
            "HTTPResponse": {
                "StatusCode": 400,
                "Body": json.dumps({"error": message, "reason_class": reason_class}),
                "Header": {"Content-Type": "application/json"},
            },
        }
    )


def _pre_create(event: dict, upload: dict) -> JsonResponse:
    """May this upload start? Asked before a single byte is accepted."""
    session = _session_of(event)
    if session is None:
        return _reject("Your session has ended. Sign in again.", "no_session")

    batch = Batch.unfinished_for(session.user)
    if batch is None:
        return _reject(
            "There is no batch to upload into. Start again from the Upload page.",
            Refusal.BATCH_IN_PROGRESS,
        )

    # The Recording this upload is for was made at the Batch's start, with
    # its Case, so the space tested is that Case's owner's.
    recording = Recording.objects.filter(
        pk=(upload.get("MetaData") or {}).get("recording", ""), batch=batch
    ).first()
    refusal = check_before_upload(
        session.user,
        batch,
        int(upload.get("Size") or 0),
        # The rows were all made at the Batch's start, this one among them.
        batch.recordings.count(),
        into=recording.case if recording is not None else None,
    )
    if refusal is not None:
        return _reject(refusal.message, refusal.reason_class)

    return JsonResponse({})


def _pre_create_live(event: dict, upload: dict) -> JsonResponse:
    """May this Live recording's upload start? Its length is not yet known.

    The Recording was made by the Record page a moment ago, in its Case; the
    sidecar is told the upload's length only at the end. What can be checked
    is checked: the session, the Recording, the disk floor, and the Case
    owner's room against the longest recording the setting allows.
    """
    from core import live

    session = _session_of(event)
    if session is None:
        return _reject("Your session has ended. Sign in again.", "no_session")
    recording = Recording.objects.filter(
        pk=(upload.get("MetaData") or {}).get("recording", ""),
        user=session.user,
        media_state=MediaState.UPLOADING,
    ).first()
    if recording is None or not recording.is_live:
        return _reject("There is no recording to record into.", "no_recording")
    # Opus at the page's rate is about a quarter of a megabyte a minute.
    at_most = live.longest_seconds() // 60 * 256 * 1024
    if free_disk_bytes() - at_most < settings_store.minimum_free_disk_bytes():
        return _reject(Refusal.MESSAGES[Refusal.DISK_FULL], Refusal.DISK_FULL)
    whose = recording.case.owner if recording.case_id else session.user
    if used_bytes(whose) + at_most > quota_bytes(whose):
        message = (
            Refusal.MESSAGES[Refusal.QUOTA_EXCEEDED_THEIRS].format(
                owner=whose.shown_name,
                used=as_gb(used_bytes(whose) + at_most),
                quota=as_gb(quota_bytes(whose)),
            )
            if whose.pk != session.user.pk
            else Refusal.MESSAGES[Refusal.QUOTA_EXCEEDED].format(
                used=as_gb(used_bytes(whose) + at_most),
                quota=as_gb(quota_bytes(whose)),
            )
        )
        return _reject(message, Refusal.QUOTA_EXCEEDED)
    return JsonResponse({})


def _post_finish(event: dict, upload: dict, metadata: dict) -> JsonResponse:
    """The bytes are here. Move them in and start the pipeline."""
    from core.tasks import prepare_recording

    session = _session_of(event)
    if session is None:
        log.warning("an upload finished with no Login session behind it")
        return JsonResponse({})

    recording = Recording.objects.filter(
        pk=metadata.get("recording", ""), user=session.user
    ).first()
    if recording is None:
        log.warning("an upload finished for a recording that is not there")
        return JsonResponse({})
    # The row is claimed before the file is moved (v1.131.0): the Record
    # page's end and the sidecar's finish can land together, and only the one
    # that claims it takes the file; the other changes nothing.
    if not claim(recording):
        log.info("an upload finished for recording %s, already taken", recording.id)
        return JsonResponse({})

    arrived = arrived_file(str(upload.get("ID") or ""))
    if arrived is None:
        recording.media_state = MediaState.FAILED
        recording.failure_message = "The upload did not arrive."
        recording.save(update_fields=["media_state", "failure_message"])
        return JsonResponse({})

    if not take_in(recording, arrived):
        return JsonResponse({})
    prepare_recording.defer(recording_id=str(recording.pk))
    log.info("recording %s arrived and was given to the media worker", recording.id)
    return JsonResponse({})


def take_in(recording: Recording, arrived: Path) -> bool:
    """Move the sidecar's file into the Recording's folder, guarded (v1.132.0).

    A full disk or a vanished file had raised after the claim, answering the
    sidecar 500 and leaving the row "checking" for ever while the browser had
    already shown "Uploaded". The row is failed with a sentence instead, and
    the file is left for the sweep.
    """
    try:
        recording.folder.mkdir(parents=True, exist_ok=True)
        shutil.move(str(arrived), recording.original_path)
        arrived.with_name(f"{arrived.name}.info").unlink(missing_ok=True)
        recording.size_bytes = recording.original_path.stat().st_size
    except OSError:
        log.exception("the upload of recording %s could not be stored", recording.pk)
        recording.media_state = MediaState.FAILED
        recording.failure_message = "The upload could not be stored. Try again."
        recording.save(update_fields=["media_state", "failure_message"])
        return False
    recording.media_state = MediaState.CHECKING
    recording.save(update_fields=["size_bytes", "media_state"])
    return True


def finish_the_complete() -> int:
    """Uploads whose file is whole but whose finish never reached the app
    (v1.132.0): the sidecar's hook has a few quick retries and the app is
    away for a minute at every upgrade, so the minute sweep finishes them
    the way the hook would, rather than dropping them ten minutes later."""
    from core.tasks import prepare_recording

    folder = Path(settings.UPLOADS_DIR)
    if not folder.is_dir():
        return 0
    finished = 0
    for info in folder.glob("*.info"):
        try:
            described = json.loads(info.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        recording_id = (described.get("MetaData") or {}).get("recording")
        size = described.get("Size")
        if not recording_id or not isinstance(size, int) or size <= 0:
            continue
        pieces = info.with_suffix("")
        try:
            if pieces.stat().st_size < size:
                continue
        except OSError:
            continue
        recording = Recording.objects.filter(
            pk=recording_id, media_state=MediaState.UPLOADING
        ).first()
        if recording is None or recording.is_live:
            continue
        arrived = arrived_file(pieces.name)
        if arrived is None or not claim(recording):
            continue
        log.warning(
            "recording %s was uploaded whole but its finish never came; taken in",
            recording.pk,
        )
        if take_in(recording, arrived):
            prepare_recording.defer(recording_id=str(recording.pk))
            finished += 1
    return finished
