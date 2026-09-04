"""Who may hear a Recording, asked before Caddy serves a byte of it.

Playback copies, waveforms, and Clip files are served straight from disk by
Caddy, with range requests, because a multi-gigabyte stream must never pass
through Python. What does pass through Python is the question of whether this
Login session may have that file.

An Admin may open anybody's material (ADR 0004), and every time one does, a row
is written naming the Admin, the item, and the owner. That row and the banner
on the screen are the whole of the guard rails, so neither is optional.
"""

from __future__ import annotations

import logging
from urllib.parse import unquote, urlparse

from django.http import HttpRequest, HttpResponse

from core import audit
from core.recordings import Recording

log = logging.getLogger("transcribe.media")

# What may be asked for out of a Recording's folder. Anything else, including
# the uploaded bytes and the prepared audio, is never served: the uploaded
# original is not downloadable, and keeping the media means making a Clip.
SERVABLE = ("playback.mp4", "playback.m4a", "waveform.json")
CLIPS = "clips/"


def _wanted(request: HttpRequest) -> tuple[str, str, str] | None:
    """The holder and recording ids out of the path Caddy was asked for.

    The holder is the person whose Workspace it is, or the Case it is kept in,
    which is exactly the folder the file sits in on disk.

    The path arrives either as `/media/<holder>/<recording>/<file>` or with
    the prefix already stripped, because Caddy sorts the directives in a route
    and may run the strip before it asks. Both are read, so that the order of
    two lines in a Caddyfile cannot silently refuse every recording in the
    office.
    """
    path = request.headers.get("X-Forwarded-Uri") or request.META.get("PATH_INFO", "")
    path = unquote(urlparse(path).path)

    parts = [piece for piece in path.split("/") if piece]
    if parts and parts[0] in ("media", "case-media"):
        parts = parts[1:]

    # <user id or case id> / <recording id> / <file>
    if len(parts) < 3:
        return None
    return parts[0], parts[1], "/".join(parts[2:])


def media_root(recording) -> str:
    """The URL a Recording's files hang off, which follows where they live.

    Caddy is given two roots, `scratch/` and `cases/`, so the prefix says
    which. A Recording that moves into a Case changes prefix with its files
    and its old URL stops working, which is the intent.
    """
    if recording.case_id:
        return f"/case-media/{recording.case_id}/{recording.pk}"
    return f"/media/{recording.user_id}/{recording.pk}"


def holder_of(recording) -> str:
    """The folder a Recording's files sit in, named as the URL names it.

    Checked rather than trusted: a path claiming the wrong holder is refused,
    so a Recording moved into a Case cannot still be fetched by its old URL.
    """
    return str(recording.case_id) if recording.case_id else str(recording.user_id)


def may_serve(request: HttpRequest) -> HttpResponse:
    """Caddy's question: may this session have this file?

    Answered with nothing but a status. Caddy serves the bytes itself if the
    answer is yes.
    """
    if not request.user.is_authenticated:
        return HttpResponse(status=401)

    asked = _wanted(request)
    if asked is None:
        return HttpResponse(status=404)
    owner_id, recording_id, name = asked

    if name not in SERVABLE and not name.startswith(CLIPS):
        # The uploaded bytes and the audio the model heard are not for
        # anybody: what a person keeps, they keep as a Clip or an export.
        return HttpResponse(status=404)

    recording = Recording.objects.filter(pk=recording_id).select_related("user").first()
    if recording is None or holder_of(recording) != owner_id:
        return HttpResponse(status=404)

    # Nothing in a Case that is in the Recycle bin is served to anybody.
    from core import cases

    if not cases.reachable(recording):
        return HttpResponse(status=404)

    if recording.user_id == request.user.pk:
        return HttpResponse(status=200)

    if not request.user.is_admin:
        # Not theirs, and not an Admin. Told it is not there rather than that
        # they may not have it.
        return HttpResponse(status=404)

    audit.write(
        audit.Category.ADMIN,
        "Playback copy served to an Admin",
        actor=request.user,
        request=request,
        affected_user=recording.user,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        file=name,
    )
    return HttpResponse(status=200)
