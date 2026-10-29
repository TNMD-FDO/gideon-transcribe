"""Bulk transcription (Phase 8 chapter 13, amended v1.173.0).

One page for the errand of getting transcripts of a set of files and
nothing else: the drop, two options, Start; then the same page is the
batch, and ends as the download. Under it a Batch like any other, this
session only and never in a Case, so nothing here is a new kind of thing:
the upload's own submit makes the Batch, the batch page's own state feed
drives the page while it runs, and the download is the batch's zip. The
one-unfinished-batch rule holds, so the drop is not offered while one runs.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core import (
    home,
    pieces,
    quota_raises,
    settings_store,
    translation,
    uploads,
    whisperx,
)
from core.recordings import Batch

LINE = "Files in, transcripts out, nothing kept"


@login_required
def page(request: HttpRequest) -> HttpResponse:
    """The drop, or this session's batch where it stands, or its download."""
    from core.pages import standing_line

    running = Batch.unfinished_for(request.user)
    ready = home.ready_batches(request.user)
    shown = running if running is not None else (ready[0]["batch"] if ready else None)
    # The batches of this session that finished earlier and still wait for
    # Done with these, under the one the page shows.
    others = [one for one in ready if shown is None or one["batch"].pk != shown.pk]
    state = "running" if running is not None else ("ready" if shown else "drop")
    service_is_up = whisperx.is_alive()
    installed = pieces.transcription_installed()
    disk_is_low = uploads.free_disk_bytes() < settings_store.minimum_free_disk_bytes()
    return render(
        request,
        "bulk.html",
        {
            "page": "bulk",
            "line": LINE,
            "shown": shown,
            "state": state,
            "others": others,
            "standing_line": standing_line(),
            "storage_warning": uploads.storage_warning(request.user),
            "quota_notice": quota_raises.notice(request.user),
            "service_is_up": service_is_up,
            "transcription_installed": installed,
            # The drop is not offered while uploading is paused, as the upload
            # page pauses it; a batch already running is shown regardless.
            "paused": disk_is_low or (installed and not service_is_up),
            # Translate to English greys as the upload page greys it (ADR 0026).
            "translation_offered": translation.offered(),
            "recogniser": settings_store.recogniser(),
            "limits": {
                "largest_file": uploads.as_gb(settings_store.largest_file_bytes()),
                "longest_hours": settings_store.longest_recording_seconds() // 3600,
                "files_per_batch": settings_store.files_per_batch(),
            },
            "disk_is_low": disk_is_low,
            "disk_free_gb": uploads.as_gb(uploads.free_disk_bytes()),
            "disk_floor_gb": settings_store.get("minimum_free_disk_gb"),
        },
    )
