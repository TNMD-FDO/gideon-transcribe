"""The pages and endpoints the app answers."""

from django.urls import path

from core import (
    assistant_pages,
    case_chat_pages,
    case_pages,
    clip_pages,
    exports,
    media_access,
    pages,
    panel,
    panel_pages,
    people_pages,
    template_pages,
    uploads,
    viewer,
    views,
)

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("", pages.recordings, name="home"),
    path("upload", pages.upload, name="upload"),
    # The user guide, rendered from docs/user-guide.md (ADR 0012).
    path("help/", pages.user_guide, name="help"),
    path("upload/submit", pages.submit, name="submit"),
    path("batch/<uuid:batch_id>", pages.batch, name="batch"),
    path("batch/<uuid:batch_id>/state", pages.batch_state, name="batch-state"),
    path("batch/<uuid:batch_id>/cancel", pages.cancel_batch, name="cancel-batch"),
    # Finishing with recordings without signing out, which is the loop an
    # office running batches actually works in.
    path("recordings/what-would-go", pages.what_would_be_cleared, name="what-would-go"),
    path("recordings/clear", pages.clear_recordings, name="clear-recordings"),
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
    # Whether the Playback copy is ready, for a viewer that opened before it was.
    path(
        "recording/<uuid:recording_id>/media",
        viewer.media_state,
        name="media-state",
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
    # Trying again, and processing again: each a Batch of one Recording.
    path("recording/<uuid:recording_id>/retry", pages.retry, name="retry"),
    path(
        "recording/<uuid:recording_id>/process-again",
        pages.process_again,
        name="process-again",
    ),
    # The AI assistant: one state answer the viewer polls, and one POST per
    # thing a person does. Every call runs on llm-worker; nothing here waits.
    path(
        "recording/<uuid:recording_id>/assistant",
        assistant_pages.state,
        name="assistant-state",
    ),
    path(
        "recording/<uuid:recording_id>/summaries",
        assistant_pages.new_summary,
        name="new-summary",
    ),
    path(
        "summary/<uuid:summary_id>/regenerate",
        assistant_pages.regenerate_summary,
        name="regenerate-summary",
    ),
    path(
        "summary/<uuid:summary_id>/delete",
        assistant_pages.delete_summary,
        name="delete-summary",
    ),
    path(
        "summary/<uuid:summary_id>/export",
        assistant_pages.export_summary,
        name="export-summary",
    ),
    path(
        "recording/<uuid:recording_id>/chats",
        assistant_pages.new_chat,
        name="new-chat",
    ),
    path("chat/<uuid:chat_id>/ask", assistant_pages.ask, name="ask"),
    path("chat/<uuid:chat_id>/delete", assistant_pages.delete_chat, name="delete-chat"),
    path("chat/<uuid:chat_id>/export", assistant_pages.export_chat, name="export-chat"),
    path(
        "recording/<uuid:recording_id>/suggest",
        assistant_pages.suggest,
        name="suggest-names",
    ),
    path(
        "suggestion/<uuid:suggestion_id>/<str:verdict>",
        assistant_pages.decide,
        name="decide-suggestion",
    ),
    # The sign-out dialog's two downloads, across the whole Workspace.
    path(
        "download/<str:shape>",
        exports.workspace_download,
        name="workspace-download",
    ),
    # Cases: where a Recording lives once somebody means to keep it. Every one
    # of these answers "not found" while Folder management is off.
    path("cases", case_pages.cases_page, name="cases"),
    path("cases/new", case_pages.new_case, name="new-case"),
    path("cases/where", case_pages.where_it_could_go, name="where-it-could-go"),
    # The Retention policy: Keep on a warned Case, and the Recycle bin where
    # the clock's deletions wait.
    path("cases/bin", case_pages.recycle_bin, name="recycle-bin"),
    path(
        "cases/bin/what-would-go",
        case_pages.bin_what_would_go,
        name="bin-what-would-go",
    ),
    path("cases/bin/empty", case_pages.empty_bin, name="empty-bin"),
    path("case/<uuid:case_id>/keep", case_pages.keep_case, name="keep-case"),
    path("case/<uuid:case_id>/restore", case_pages.restore_case, name="restore-case"),
    path("case/<uuid:case_id>/wipe", case_pages.wipe_case, name="wipe-case"),
    path("case/<uuid:case_id>", case_pages.case_page, name="case"),
    path("case/<uuid:case_id>/rename", case_pages.rename_case, name="rename-case"),
    # Sharing: the people a Case may be shared with, Share, Remove, Transfer.
    path("case/<uuid:case_id>/share/who", case_pages.share_who, name="share-who"),
    path("case/<uuid:case_id>/share", case_pages.share_case, name="share-case"),
    path("case/<uuid:case_id>/unshare", case_pages.unshare_case, name="unshare-case"),
    path(
        "case/<uuid:case_id>/transfer", case_pages.transfer_case, name="transfer-case"
    ),
    # The Speakers tab's acts: add a Person, and rename, edit, merge or delete one.
    path("case/<uuid:case_id>/people", people_pages.add_person, name="add-person"),
    # The Chat tab: the Case Chat's state, New chat, Ask, Delete, Export.
    path("case/<uuid:case_id>/chat", case_chat_pages.state, name="case-chat-state"),
    path("case/<uuid:case_id>/chats", case_chat_pages.new_chat, name="new-case-chat"),
    path("case-chat/<uuid:chat_id>/ask", case_chat_pages.ask, name="ask-case-chat"),
    path(
        "case-chat/<uuid:chat_id>/delete",
        case_chat_pages.delete_chat,
        name="delete-case-chat",
    ),
    path(
        "case-chat/<uuid:chat_id>/export",
        case_chat_pages.export,
        name="export-case-chat",
    ),
    path("person/<uuid:person_id>", people_pages.person_action, name="person-action"),
    path("case/<uuid:case_id>/delete", case_pages.delete_case, name="delete-case"),
    path(
        "case/<uuid:case_id>/what-would-go",
        case_pages.what_would_go,
        name="what-would-go",
    ),
    path("case/<uuid:case_id>/add", case_pages.add_recordings, name="add-recordings"),
    path(
        "case/<uuid:case_id>/download",
        case_pages.download_case,
        name="case-download",
    ),
    path(
        "case/<uuid:case_id>/download-clips",
        case_pages.download_case_clips,
        name="case-clips-download",
    ),
    path(
        "recording/<uuid:recording_id>/move",
        case_pages.move_to_case,
        name="move-to-case",
    ),
    path(
        "recording/<uuid:recording_id>/case-details",
        case_pages.set_details,
        name="case-details",
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
    path("panel/help", panel_pages.admin_guide, name="panel-help"),
    path("panel/assistant/test", panel_pages.test_engine, name="panel-test-engine"),
    path("panel/templates", template_pages.templates, name="panel-templates"),
    path("panel/appearance/logo", panel.logo, name="panel-logo"),
    path("panel/email/test", panel_pages.test_mail, name="panel-test-mail"),
    # The logo itself, for the sign-in page nobody has signed in to yet.
    path("branding/logo", views.logo, name="logo"),
    path(
        "panel/templates/prompt/<str:key>",
        template_pages.prompt_template,
        name="panel-prompt-template",
    ),
    path(
        "panel/templates/summary",
        template_pages.add_summary_template,
        name="panel-add-summary-template",
    ),
    path(
        "panel/templates/starters/<str:key>",
        template_pages.starter_questions,
        name="panel-starter-questions",
    ),
    path(
        "panel/templates/summary/<uuid:template_id>",
        template_pages.summary_template,
        name="panel-summary-template",
    ),
    path("panel/settings/<str:page>", panel.settings_page, name="panel-settings"),
    path("panel/settings/<str:page>/edit", panel.edit, name="panel-edit"),
    path("panel/apply", panel.apply, name="panel-apply"),
    path("panel/cancel", panel.cancel_all, name="panel-cancel"),
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-out", views.sign_out, name="sign-out"),
]
