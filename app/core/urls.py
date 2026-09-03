"""The pages and endpoints the app answers."""

from django.urls import path

from core import views

urlpatterns = [
    path("healthz", views.healthz, name="healthz"),
    path("", views.home, name="home"),
    path("sign-in", views.sign_in, name="sign-in"),
    path("sign-out", views.sign_out, name="sign-out"),
]
