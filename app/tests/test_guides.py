"""The three guides: they exist, they render, and the app serves two of them.

The user guide is served at /help/ and the admin guide behind the Help link in
the Admin panel, both rendered from the repository's own Markdown so that
nobody who uses the app needs GitHub to read it (ADR 0012). The install guide
is read from the repository only.

Most of this needs no database. The two page tests do, and run in CI.
"""

import re
from pathlib import Path

import pytest
from core import guides
from core.models import LoginSession, User
from django.urls import reverse

HERE = Path(__file__).resolve().parent.parent.parent
DOCS = HERE / "docs"
PASSWORD = "a-long-enough-password"

THE_THREE = ("user-guide.md", "admin-guide.md", "install.md")


def text_of(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


# The files -------------------------------------------------------------------


def test_the_three_guides_exist():
    for name in THE_THREE:
        assert (DOCS / name).is_file(), f"docs/{name} is missing"


def test_no_guide_uses_an_em_dash():
    # The house rule, and the guides are the most-read prose in the repository.
    for name in THE_THREE:
        assert "—" not in text_of(name), f"docs/{name} has an em dash"


def test_every_guide_opens_with_one_title_and_has_sections():
    for name in THE_THREE:
        lines = text_of(name).splitlines()
        assert lines[0].startswith("# "), f"docs/{name} does not open with a title"
        assert sum(1 for one in lines if one.startswith("# ")) == 1, name
        assert sum(1 for one in lines if one.startswith("## ")) >= 5, name


def test_the_admin_guide_covers_what_the_chapter_requires():
    # The chapter: the panel, the tray and its note, the catalogue, the
    # Installation page, the Sign-in page notice, and the wedged-job command.
    text = text_of("admin-guide.md")
    for wanted in (
        "The tray",
        "note for the audit log",
        "ADMIN-SETTINGS-CATALOGUE.md",
        "The Installation page",
        "Sign-in page notice",
        "stuck_jobs",
        "Integrity check",
        "Audit log retention",
        "docker compose restart caddy",
        "negative TTL",
    ):
        assert wanted in text, f"the admin guide does not mention {wanted!r}"


def test_the_user_guide_uses_the_glossary_s_page_names():
    text = text_of("user-guide.md")
    for wanted in (
        "Upload page",
        "Batch page",
        "Recordings page",
        "Clips page",
        "Cases page",
        "Done with these",
        "Clear my recordings",
        "Download all transcripts",
    ):
        assert wanted in text, f"the user guide does not mention {wanted!r}"


def test_the_install_guide_names_every_environment_key():
    # The appendix is every key with its meaning. A key an office can set
    # that the guide does not name is a key nobody knows exists.
    example = (HERE / ".env.example").read_text(encoding="utf-8")
    keys = set(re.findall(r"^#?\s?([A-Z][A-Z0-9_]+)=", example, re.M))
    text = text_of("install.md")
    missing = sorted(key for key in keys if f"`{key}`" not in text)
    assert not missing, "the install guide does not name these keys: " + ", ".join(
        missing
    )


def test_the_install_guide_has_the_chapter_s_fixed_parts():
    text = text_of("install.md")
    for wanted in (
        "./transcribe install",
        "./transcribe check",
        "./transcribe upgrade",
        "./transcribe rollback",
        "When it fails",
        "Uninstall",
        "github.com",
        "huggingface.co",
        "New-ADUser",
        "certreq",
        "useradd",
        "Nothing is ever pushed",
    ):
        assert wanted in text, f"the install guide does not have {wanted!r}"


# Rendering -------------------------------------------------------------------


def test_the_two_served_guides_render():
    for name in guides.NAMES:
        guide = guides.render(guides.source_of(name).read_text(encoding="utf-8"))
        assert guide.title
        assert "<h2" in guide.body
        assert "<ul>" in guide.contents and '<a href="#' in guide.contents


def test_rendering_gives_headings_ids_the_contents_point_at():
    guide = guides.render("# T\n\n## First part\n\ntext\n\n### Inside\n\nmore\n")
    assert 'id="first-part"' in guide.body
    assert 'href="#first-part"' in guide.contents
    assert 'href="#inside"' in guide.contents


def test_the_command_writes_the_rendered_copies(tmp_path, settings):
    from django.core.management import call_command

    for name in guides.NAMES:
        (tmp_path / f"{name}.md").write_text(
            f"# {name}\n\n## One\n\nwords\n", encoding="utf-8"
        )
    settings.GUIDES_DIR = tmp_path

    call_command("render_guides")

    for name in guides.NAMES:
        assert guides.rendered_of(name).is_file()
        loaded = guides.load(name)
        assert loaded.title == name
        assert "<h2" in loaded.body


def test_the_command_fails_the_build_when_a_guide_is_missing(tmp_path, settings):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    settings.GUIDES_DIR = tmp_path
    with pytest.raises(CommandError):
        call_command("render_guides")


# The build --------------------------------------------------------------------


def test_the_build_context_is_the_repository_root():
    compose = (HERE / "compose.yaml").read_text(encoding="utf-8")
    assert "context: ./app" not in compose
    # One image, four services: app, media-worker, worker, llm-worker.
    assert compose.count("dockerfile: app/Dockerfile") == 4

    dockerfile = (HERE / "app" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY app/ /opt/app/" in dockerfile
    assert "COPY docs/user-guide.md docs/admin-guide.md /opt/app/guides/" in dockerfile
    assert "render_guides" in dockerfile


def test_the_office_s_own_files_never_enter_the_build_context():
    """The context is the Install home on a server (ADR 0012).

    Nothing copies .env or the secrets into the image, but everything in the
    context reaches the Docker daemon unless the ignore file names it.
    """
    ignore = (HERE / ".dockerignore").read_text(encoding="utf-8").splitlines()
    named = {
        line.strip() for line in ignore if line.strip() and not line.startswith("#")
    }
    for must in (".env", "secrets/", "tls/", "ca/", "whisperx-service/"):
        assert must in named, f".dockerignore does not name {must}"
    assert not (HERE / "app" / ".dockerignore").exists(), (
        "app/.dockerignore is not read any more and would mislead"
    )


def test_the_help_links_are_on_the_pages():
    base = (HERE / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    # Help goes through the help_url tag, which lands on the section for the
    # page; the tag itself reverses the help route.
    assert "{% help_url page %}" in base
    panel = (HERE / "app" / "templates" / "panel" / "base.html").read_text(
        encoding="utf-8"
    )
    assert "{% url 'panel-help' %}" in panel


# The pages, which need a database ---------------------------------------------


@pytest.mark.django_db
def test_a_user_reads_the_user_guide_and_not_the_admin_one(client):
    person = User.objects.create_local_admin("pat", PASSWORD)
    person.is_local = False
    person.save()
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)

    answer = client.get(reverse("help"))
    assert answer.status_code == 200
    assert "Using Gideon Transcribe" in answer.content.decode()

    # Not an Admin, so the admin guide is not theirs to read.
    assert client.get(reverse("panel-help")).status_code in (302, 403)


@pytest.mark.django_db
def test_an_admin_reads_the_admin_guide(client):
    admin = User.objects.create_local_admin("adm", PASSWORD)
    client.force_login(admin)
    LoginSession.objects.create(user=admin, session_key=client.session.session_key)

    answer = client.get(reverse("panel-help"))
    assert answer.status_code == 200
    page = answer.content.decode()
    assert "The Admin guide" in page
    # It sits inside the panel, rail and all.
    assert "Back to your recordings" in page


def test_a_stranger_is_sent_to_sign_in(client):
    assert client.get(reverse("help")).status_code == 302
