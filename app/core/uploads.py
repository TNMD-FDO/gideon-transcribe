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
import shutil
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core import settings_store
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Refusal

log = logging.getLogger("transcribe.uploads")

# Near enough to the limit to be worth saying so, and far enough that a person
# can act on it. A build constant, not a setting.
QUOTA_WARNING_SHARE = 0.80


@dataclass(frozen=True)
class Refused:
    """An upload the app will not take, with words and a reason class."""

    message: str
    reason_class: str


def used_bytes(user: User) -> int:
    """Everything on disk for this person's recordings, which is their quota."""
    return sum(recording.disk_bytes() for recording in user.recordings.all())


def quota_bytes(user: User) -> int:
    """This person's space. A per-person override will sit on the users list."""
    return settings_store.default_quota_bytes()


def free_disk_bytes() -> int:
    """What is left on the drive the App data folder lives on."""
    usage = shutil.disk_usage(settings.DATA_DIR)
    return usage.free


def as_gb(figure: int) -> str:
    return f"{figure / 1024**3:.0f} GB"


def check_before_upload(
    user: User, batch: Batch, size_bytes: int, files_in_batch: int
) -> Refused | None:
    """Everything the app can decide before a single byte arrives.

    Asked by the Upload page so a person is told early, and again by the
    sidecar's pre-create hook so the answer holds whatever the page did.
    """
    if free_disk_bytes() < settings_store.minimum_free_disk_bytes():
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

    quota = quota_bytes(user)
    after = used_bytes(user) + size_bytes
    if after > quota:
        return Refused(
            Refusal.MESSAGES[Refusal.QUOTA_EXCEEDED].format(
                used=as_gb(after), quota=as_gb(quota)
            ),
            Refusal.QUOTA_EXCEEDED,
        )

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
    return f"You are close to your storage space: {as_gb(after)} of {as_gb(quota)}"


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


@csrf_exempt
def hook(request: HttpRequest) -> JsonResponse:
    """The sidecar's two questions, on one endpoint.

    Answered with the shape tusd expects: a rejection carries an HTTP response
    for the browser, and everything else is an empty acceptance.
    """
    if request.method != "POST":
        return JsonResponse({}, status=405)

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({}, status=400)

    name = request.headers.get("Hook-Name") or body.get("Type", "")
    event = body.get("Event", {}) or {}
    upload = event.get("Upload", {}) or {}
    metadata = upload.get("MetaData", {}) or {}

    if name == "pre-create":
        return _pre_create(event, upload)
    if name == "post-finish":
        return _post_finish(event, upload, metadata)
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

    refusal = check_before_upload(
        session.user,
        batch,
        int(upload.get("Size") or 0),
        batch.recordings.count() + 1,
    )
    if refusal is not None:
        return _reject(refusal.message, refusal.reason_class)

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

    arrived = Path(settings.UPLOADS_DIR) / f"{upload.get('ID', '')}"
    if not arrived.exists():
        recording.media_state = MediaState.FAILED
        recording.failure_message = "The upload did not arrive."
        recording.save()
        return JsonResponse({})

    recording.folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(arrived), recording.original_path)
    (arrived.parent / f"{upload.get('ID', '')}.info").unlink(missing_ok=True)

    recording.size_bytes = recording.original_path.stat().st_size
    recording.media_state = MediaState.CHECKING
    recording.save()

    prepare_recording.defer(recording_id=str(recording.pk))
    log.info("recording %s arrived and was given to the media worker", recording.id)
    return JsonResponse({})
