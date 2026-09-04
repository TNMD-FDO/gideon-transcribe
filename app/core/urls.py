"""The pages and endpoints the app answers."""

from django.urls import path

from core import (
    clip_pages,
    exports,
    media_access,
    pages,
    panel,
    panel_pages,
    uploads,
    viewer,
    views,
)

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
        "recording/<uuid:recording_id>/details",
        viewer.details,
        name="details",
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
    # Clips: a chosen span of a Recording, as a file for outside the app.
    path("clips", clip_pages.clips_page, name="clips"),
    path("clips/download", clip_pages.download_all_clips, name="download-clips"),
    path(
        "recording/<uuid:recording_id>/clips",
        clip_pages.clips_of,
        name="clips-of",
    ),
    path(
        "recording/<uuid:recording_id>/clips/save",
        clip_pages.save_clip,
        name="save-clip",
    ),
    path("clip/<uuid:clip_id>", clip_pages.change_clip, name="change-clip"),
    path(
        "clip/<uuid:clip_id>/rerender",
        clip_pages.rerender_clip,
        name="rerender-clip",
    ),
    path("clip/<uuid:clip_id>/delete", clip_pages.delete_clip, name="delete-clip"),
    path(
        "clip/<uuid:clip_id>/download",
        clip_pages.download_clip,
        name="download-clip",
    ),
    # Caddy asks this before it serves a Playback copy, a waveform, or a Clip.
    path("media-auth", media_access.may_serve, name="media-auth"),
    # The Admin panel. Users never see any of it.
    path("panel/", panel.panel, name="panel"),
    path("panel/status", panel_pages.status, name="panel-status"),
    path("panel/status/lines", panel_pages.status_lines, name="panel-status-lines"),
    path("panel/queue", panel_pages.queue_page, name="panel-queue"),
    path("panel/queue/state", panel_pages.queue_state, name="panel-queue-state"),
    path(
        "panel/queue/<uuid:job_id>/cancel",
        panel_pages.cancel_job,
        name="panel-cancel-job",
    ),
    path("panel/users", panel_pages.users, name="panel-users"),
    path("panel/users/<str:username>", panel_pages.user_action, name="panel-user"),
    path(
        "panel/users/<str:username>/workspace",
        panel_pages.workspace,
        name="panel-workspace",
    ),
    path(
        "panel/users/<str:username>/local",
        panel_pages.local_admin_action,
        name="panel-local-admin",
    ),
    path(
        "panel/local-admin",
        panel_pages.create_local_admin,
        name="panel-create-local-admin",
    ),
    path(
        "panel/directory/test",
        panel_pages.test_directory,
        name="panel-test-directory",
    ),
    path(
        "panel/directory/check",
        panel_pages.check_directory_now,
        name="panel-check-directory",
    ),
    path("panel/audit", panel_pages.audit_log, name="panel-audit"),
    path("panel/audit/check", panel_pages.integrity_check, name="panel-integrity"),
    path("panel/installation", panel_pages.installation, name="panel-installation"),
    path("panel/settings/<str:page>", panel.settings_page, name="panel-settings"),
    path("panel/settings/<str:page>/edit", panel.edit, name="panel-edit"),
    path("panel/apply", panel.apply, name="panel-apply"),
    path("panel/cancel", panel.cancel_all, name="panel-cancel"),
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-out", views.sign_out, name="sign-out"),
]
