"""The fictional office a workstation is filled with for a walk of the pages
(docs/local-walk.md): it seeds an empty database once, refuses a database
with anybody in it, and leaves nothing behind when it fails."""

from __future__ import annotations

from io import StringIO

import pytest
from core.assistant import Suggestion
from core.cases import Case
from core.clips import Clip
from core.incidents import Incident
from core.models import User
from core.recordings import Recording
from django.core.management import call_command


@pytest.mark.django_db
def test_the_seed_fills_an_empty_database_once(settings, tmp_path):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    said = StringIO()
    call_command("seed_demo", password="a-password-for-the-walk", stdout=said)
    assert "Seeded: 2 people, 3 cases, 12 recordings" in said.getvalue()
    assert User.objects.count() == 2 and Case.objects.count() == 3
    assert Recording.objects.count() == 12 and Incident.objects.count() == 1
    assert Clip.objects.count() == 3 and Suggestion.objects.count() == 4
    assert Incident.objects.get().cameras.count() == 3
    # Nothing in it is anybody's: the names are the seed's own.
    assert set(User.objects.values_list("username", flat=True)) == {"test", "pat"}
    # A second run touches nothing.
    again = StringIO()
    call_command("seed_demo", password="another", stdout=again)
    assert "nothing seeded" in again.getvalue() and User.objects.count() == 2


@pytest.mark.django_db
def test_the_seed_needs_a_password(settings, tmp_path):
    with pytest.raises(Exception, match="password"):
        call_command("seed_demo", password="")
    assert not User.objects.exists()
    # From a file, so that it sits in no command line.
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    kept = tmp_path / "seed-password"
    kept.write_text("from-a-file\n", encoding="utf-8")
    call_command("seed_demo", password_file=str(kept))
    assert User.objects.get(username="test").check_password("from-a-file")
