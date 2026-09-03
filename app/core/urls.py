"""The pages and endpoints the app answers."""

from django.urls import path

from core import pages, uploads, views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("", pages.recordings, name="home"),
    path("upload", pages.upload, name="upload"),
    path("upload/submit", pages.submit, name="submit"),
    path("batch/<uuid:batch_id>", pages.batch, name="batch"),
    path("batch/<uuid:batch_id>/state", pages.batch_state, name="batch-state"),
    path("batch/<uuid:batch_id>/cancel", pages.cancel_batch, name="cancel-batch"),
    # The upload sidecar's two questions. Reachable only from inside the
    # project's own network.
    path("upload-hook/", uploads.hook, name="upload-hook"),
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-out", views.sign_out, name="sign-out"),
]
