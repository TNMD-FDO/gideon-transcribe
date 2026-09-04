"""The pages and endpoints the app answers."""

from django.urls import path

from core import exports, media_access, pages, uploads, viewer, views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("", pages.recordings, name="home"),
    path("upload", pages.upload, name="upload"),
    path("upload/submit", pages.submit, name="submit"),
    path("batch/<uuid:batch_id>", pages.batch, name="batch"),
    path("batch/<uuid:batch_id>/state", pages.batch_state, name="batch-state"),
    path("batch/<uuid:batch_id>/cancel", pages.cancel_batch, name="cancel-batch"),
    path(
        "batch/<uuid:batch_id>/download",
        exports.batch_download,
        name="batch-download",
    ),
    # The upload sidecar's two questions. Reachable only from inside the
    # project's own network.
    path("upload-hook/", uploads.hook, name="upload-hook"),
    path("recording/<uuid:recording_id>", viewer.viewer, name="viewer"),
    path(
        "recording/<uuid:recording_id>/segments",
        viewer.segments,
        name="segments",
    ),
    path(
        "recording/<uuid:recording_id>/segment/<int:segment_id>",
        viewer.correct,
        name="correct",
    ),
    path(
        "recording/<uuid:recording_id>/speakers",
        viewer.speakers,
        name="speakers",
    ),
    # The three exports: Word, plain text, and Captions.
    path(
        "recording/<uuid:recording_id>/export/<str:shape>",
        exports.export,
        name="export",
    ),
    path(
        "recording/<uuid:recording_id>/delete",
        pages.delete_recording,
        name="delete-recording",
    ),
    # The sign-out dialog's two downloads, across the whole Workspace.
    path(
        "download/<str:shape>",
        exports.workspace_download,
        name="workspace-download",
    ),
    # Caddy asks this before it serves a Playback copy, a waveform, or a Clip.
    path("media-auth", media_access.may_serve, name="media-auth"),
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-out", views.sign_out, name="sign-out"),
]
