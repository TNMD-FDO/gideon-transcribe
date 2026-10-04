"""Names across many recordings (Phase 9 chapter 2): the Case vocabulary,
its spellings in Search, the names into recognition and Gideon, and a voice
named across the case."""

from __future__ import annotations

import pytest
from core import audit, case_chat, case_search, people, queue, vocabulary
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.people import CaseTerm, Person
from core.recordings import Batch, MediaState, Recording, Side
from django.urls import reverse

PASSWORD = "a long enough password 1"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


@pytest.fixture(autouse=True)
def cases_on(db):
    from core import settings_store

    settings_store.set_to("folder_management", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("vocab-owner", PASSWORD)


@pytest.fixture
def colleague(db):
    person = User.objects.create_local_admin("vocab-colleague", PASSWORD)
    person.is_local = False
    person.display_name = "D. Chen"
    person.save()
    return person


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Pike matter")


def a_call(owner, case, title, lines, two_channel=True):
    batch = Batch.objects.create(user=owner)
    recording = Recording.objects.create(
        batch=batch,
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.wav",
        media_state=MediaState.READY,
        recording_type="Jail call",
        is_two_channel_call=two_channel,
    )
    sides = {}
    if two_channel:
        sides = {n: Side.objects.create(recording=recording, number=n) for n in (1, 2)}
    transcript = Transcript.objects.create(recording=recording, language="en")
    at = 0
    for side_number, speaker, text in lines:
        Segment.objects.create(
            transcript=transcript,
            side=sides.get(side_number),
            start=at,
            end=at + 4,
            text=text,
            speaker=speaker,
            speaker_label=speaker,
        )
        at += 5
    return recording


def signed_in(client, person):
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)


# The list ------------------------------------------------------------------------


def test_spellings_are_parsed_trimmed_and_capped():
    assert vocabulary.parse_spellings(
        " voncaruther, van caruthers,, Voncaruther\n"
    ) == [
        "voncaruther",
        "van caruthers",
    ]
    assert len(vocabulary.parse_spellings(", ".join(str(n) for n in range(40)))) == 20
    assert vocabulary.parse_spellings("") == []


def test_people_are_entries_by_themselves_and_terms_follow(owner, a_case):
    person = Person.objects.create(case=a_case, name="Von Carutthers", role="Defendant")
    vocabulary.add_term(
        a_case, "Birch Road storage", "birch road storey, birchwood", by=owner
    )
    rows = vocabulary.entries(a_case)
    assert [(one["kind"], one["name"]) for one in rows] == [
        ("person", "Von Carutthers"),
        ("term", "Birch Road storage"),
    ]
    assert rows[0]["role"] == "Defendant"
    assert rows[1]["spellings"] == ["birch road storey", "birchwood"]
    # A name typed that is a Person's gains the spellings instead of a twin.
    vocabulary.add_term(a_case, "von carutthers", "voncaruther", by=owner)
    person.refresh_from_db()
    assert person.also_heard_as == ["voncaruther"]
    assert CaseTerm.objects.filter(case=a_case).count() == 1
    # A term typed twice gains the new spellings and stays one entry.
    vocabulary.add_term(a_case, "birch road storage", "the unit", by=owner)
    assert CaseTerm.objects.get(case=a_case).also_heard_as == [
        "birch road storey",
        "birchwood",
        "the unit",
    ]


def test_the_audit_rows_carry_counts_and_never_a_name(owner, a_case):
    vocabulary.add_term(a_case, "Dana Whitlock", "dana wit lock", by=owner)
    row = audit.Row.objects.filter(event="case vocabulary added").latest("at")
    assert row.details["entries"] == 1
    assert "Whitlock" not in str(row.details) and "wit lock" not in str(row.details)


# Into recognition ----------------------------------------------------------------


def test_the_names_go_with_the_recording_between_the_office_and_the_batch(
    owner, a_case
):
    from core import settings_store

    settings_store.set_to("office_vocabulary", "Harbour Street")
    Person.objects.create(case=a_case, name="Von Carutthers")
    vocabulary.add_term(a_case, "Birch Road storage", "birchwood", by=owner)
    call = a_call(owner, a_case, "Call 0417", [(1, "Side 1 Speaker 1", "Hey.")])
    call.vocabulary = ["Dana"]
    call.save()
    assert queue._case_vocabulary(call) == ["Von Carutthers", "Birch Road storage"]
    assert vocabulary.names_in(a_case) == ["Von Carutthers", "Birch Road storage"]
    # The Known names line reads the terms too.
    assert "Birch Road storage" in people.known_names(call)


# Into Search ----------------------------------------------------------------------


def test_a_listed_spelling_is_looked_for_as_a_phrase(owner, a_case):
    Person.objects.create(
        case=a_case,
        name="Von Carutthers",
        also_heard_as=["voncaruther", "van caruthers"],
    )
    assert vocabulary.heard_as(a_case, ["von", "carutthers"]) == [
        "voncarutthers",
        "voncaruther",
        "van caruthers",
        "vancaruthers",
    ]
    # Typed as a spelling, or joined, the name itself is looked for.
    assert "Von Carutthers" in vocabulary.heard_as(a_case, ["voncaruther"])
    assert "Von Carutthers" in vocabulary.heard_as(a_case, ["voncarutthers"])
    # A word that is no listed name brings nothing.
    assert vocabulary.heard_as(a_case, ["storage"]) == []


def test_search_lights_the_spelling_marked_also_heard_as(owner, a_case):
    Person.objects.create(
        case=a_case,
        name="Von Carutthers",
        also_heard_as=["voncaruther", "van caruthers"],
    )
    a_call(
        owner,
        a_case,
        "Call 0417",
        [
            (1, "Side 1 Speaker 1", "Is Von Carutthers still saying it was his?"),
            (1, "Side 1 Speaker 1", "Tell voncaruther I said it is fine."),
            (2, "Side 2 Speaker 1", "You talk to van caruthers or not?"),
            (2, "Side 2 Speaker 1", "Nothing about anybody here."),
        ],
    )
    found = case_search.search(a_case, "von carutthers")
    hits = [hit for group in found["groups"] for hit in group["hits"]]
    assert found["total"] == 3
    assert found["heard"] == 2
    assert "voncaruther" in found["heard_forms"]
    assert [hit["heard"] for hit in hits] == [False, True, True]
    assert "<mark>Von</mark> <mark>Carutthers</mark>" in str(hits[0]["text"])
    assert "<mark>voncaruther</mark>" in str(hits[1]["text"])
    assert "<mark>van caruthers</mark>" in str(hits[2]["text"])


def test_the_search_tab_says_so(owner, a_case, client):
    Person.objects.create(
        case=a_case, name="Von Carutthers", also_heard_as=["voncaruther"]
    )
    a_call(owner, a_case, "Call 0417", [(1, "Side 1 Speaker 1", "Tell voncaruther.")])
    signed_in(client, owner)
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=search&q=von+carutthers"
    ).content.decode()
    assert "also heard as" in page
    assert (
        "a spelling this case lists for the name (voncarutthers, voncaruther)" in page
    )


# Into Gideon ----------------------------------------------------------------------


def test_the_people_line_carries_the_spellings_and_the_places(owner, a_case):
    Person.objects.create(
        case=a_case,
        name="Von Carutthers",
        role="Defendant",
        also_heard_as=["voncaruther"],
    )
    vocabulary.add_term(a_case, "Birch Road storage", "birchwood", by=owner)
    assert case_chat.people_line(a_case) == (
        "People in this case: Von Carutthers (Defendant), also heard as voncaruther; "
        "places and other names: Birch Road storage, also heard as birchwood"
    )
    assert case_chat.people_line(Case.objects.create(owner=owner, name="Empty")) == (
        "People in this case: none yet"
    )


def test_the_case_chat_template_says_a_spelling_is_the_same_person():
    from core import prompts

    assert "also heard as is the same person or place" in prompts.CASE_CHAT
    assert (
        prompts.text_hash(prompts.CASE_CHAT)
        in prompts.SHIPPED_HISTORY["prompt:case_chat"]
    )


# A voice named across the case ---------------------------------------------------


def test_the_side_rule_names_that_side_on_every_call_and_the_next(owner, a_case):
    first = a_call(
        owner,
        a_case,
        "Call 0409",
        [(1, "Side 1 Speaker 1", "Hey."), (2, "Side 2 Speaker 1", "Hi.")],
    )
    by_hand = a_call(
        owner,
        a_case,
        "Call 0412",
        [(1, "Marcus", "Hey."), (2, "Side 2 Speaker 1", "Hi.")],
    )
    person, _ = people.join_or_create(a_case, "Pike", by=owner, how="test")

    named = vocabulary.set_side_rule(a_case, 1, person, by=owner)

    assert named == 1
    assert set(
        Segment.objects.filter(transcript__recording=first).values_list(
            "speaker", flat=True
        )
    ) == {"Pike", "Side 2 Speaker 1"}
    # A side named by hand keeps the hand's name.
    assert Segment.objects.filter(
        transcript__recording=by_hand, speaker="Marcus"
    ).exists()
    # The next call to land is named as it lands.
    later = a_call(
        owner,
        a_case,
        "Call 0433",
        [(1, "Side 1 Speaker 1", "Yo."), (2, "Side 2 Speaker 1", "Who is this?")],
    )
    vocabulary.on_transcript(later)
    assert (
        Segment.objects.filter(transcript__recording=later, speaker="Pike").count() == 1
    )
    # A single-channel recording is left alone.
    single = a_call(
        owner, a_case, "Interview", [(1, "Speaker 1", "Hello.")], two_channel=False
    )
    vocabulary.on_transcript(single)
    assert Segment.objects.filter(
        transcript__recording=single, speaker="Speaker 1"
    ).exists()
    row = audit.Row.objects.filter(event="side named across the case").latest("at")
    assert row.details["side"] == 1 and row.details["calls"] == 1
    assert "Pike" not in str(row.details)


def test_the_speakers_tab_offers_the_rule_and_the_pages_take_it(owner, a_case, client):
    a_call(owner, a_case, "Call 0409", [(1, "Side 1 Speaker 1", "Hey.")])
    signed_in(client, owner)
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=speakers"
    ).content.decode()
    assert "On every call in this case," in page
    answer = client.post(
        reverse("case-side-rule", args=[a_case.pk]), {"side": "1", "name": "Pike"}
    )
    assert answer.status_code == 302
    a_case.refresh_from_db()
    assert a_case.side_number == 1 and a_case.side_person.name == "Pike"
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=speakers"
    ).content.decode()
    assert "<b>Side 1</b> is <b>Pike</b>" in page
    assert "1 call named now" in page
    client.post(reverse("case-side-rule", args=[a_case.pk]), {"action": "remove"})
    a_case.refresh_from_db()
    assert a_case.side_number is None
    # The names stay as they were.
    assert Segment.objects.filter(speaker="Pike").exists()


# The block on the case page ---------------------------------------------------------


def test_anyone_with_the_case_adds_and_the_owner_removes(
    owner, colleague, a_case, client
):
    from core import settings_store
    from core.sharing import Share

    settings_store.set_to("sharing", True)
    Share.objects.create(case=a_case, person=colleague, added_by=owner)
    signed_in(client, colleague)
    answer = client.post(
        reverse("case-vocabulary", args=[a_case.pk]),
        {"action": "add", "term": "Birch Road storage", "spellings": "birchwood"},
    )
    assert answer.status_code == 302
    term = CaseTerm.objects.get(case=a_case)
    assert term.also_heard_as == ["birchwood"]
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert "Case vocabulary" in page and "also heard as birchwood" in page
    assert 'name="action" value="remove"' not in page
    # A collaborator may not remove.
    refused = client.post(
        reverse("case-vocabulary", args=[a_case.pk]),
        {"action": "remove", "id": term.pk},
    )
    assert refused.status_code == 404
    assert CaseTerm.objects.filter(case=a_case).exists()
    # The owner may.
    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'name="action" value="remove"' in page
    client.post(
        reverse("case-vocabulary", args=[a_case.pk]),
        {"action": "remove", "id": term.pk},
    )
    assert not CaseTerm.objects.filter(case=a_case).exists()
    assert audit.Row.objects.filter(event="case vocabulary removed").exists()


def test_the_upload_page_says_how_many_names_go_with_the_recordings(
    owner, a_case, client, monkeypatch
):
    from core import uploads, whisperx

    # The question is asked only while uploading is possible at all.
    monkeypatch.setattr(whisperx, "is_alive", lambda: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    Person.objects.create(case=a_case, name="Von Carutthers")
    vocabulary.add_term(a_case, "Birch Road storage", "", by=owner)
    signed_in(client, owner)
    page = client.get(reverse("upload")).content.decode()
    assert 'data-names="2"' in page
    assert 'id="case-names-line"' in page
