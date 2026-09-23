"""What the app answers, at the top level."""

from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
]

# The pages that fail well (Phase 8 chapter 7): the app's own frame for an
# address with nothing behind it and for the server's own failure.
handler404 = "core.views.gone"
handler500 = "core.views.failed"
