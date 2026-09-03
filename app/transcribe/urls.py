"""What the app answers, at the top level."""

from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
]
