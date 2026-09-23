"""Phase 8 chapter 9, One sitting.

The rules checked here: the Cameras tab's bar says how full the sitting is,
in hours of camera, with a sentence for each zone; adding a camera is never
refused for size, and the dialog's bar reads as it will with the ticked
cameras in; a pin keeps a camera's picture in and writes its row; the
comparison and Gideon read the record fitted the same way and say what they
read; the Proposed events layer names cameras no run has read; the Status
page says where the engine's window came from and counts the readings
refused; the Engine window row greys while the engine reports its own.
"""

from __future__ import annotations

# ruff: noqa: F811 - the fixtures are imported by name, as pytest wants them
import pytest
from core import engine, incident_assistant, incidents, prompts, settings_store, sitting
from core.assistant import DigestPart
from core.audit import Row
from django.urls import reverse
from tests.test_incident_assistant import (  # noqa: F401 - fixtures
    a_case,
    cameras_of,
    incident,
    its_own_disk,
    no_tasks,
    person,
    signed_in,
    stamp,
    switched_on,
    video,
)


def long_digest(recording, parts: int = 40) -> None:
    transcript = recording.transcript
    transcript.digest_parts.all().delete()
    DigestPart.objects.create(
        transcript=transcript,
        number=1,
        text="\n".join(
            f"{n + 1}. [00:00:{10 + n:02d}]-[00:00:{14 + n:02d}] (both) A long "
            "description of the roadside and the two officers standing by the car."
            for n in range(parts)
        ),
        made_at=None,
    )


@pytest.mark.django_db
def test_the_bar_has_room_and_says_so(incident):
    told = sitting.json_for(incident)
    assert told["on"] and told["zone"] == "room"
    assert told["window"] == 131072 and told["window_source"] == "setting"
    assert told["figure"].endswith("hours' worth")
    assert "Room for about" in told["sentence"]
    assert [one["name"] for one in told["cameras"]] == ["BWC2-1", "BWC2-2"]
    assert all(one["read"] == "both" for one in told["cameras"])
    assert told["cameras"][0]["has_digest"] and not told["cameras"][1]["has_digest"]
    assert told["words_alone"] == [] and told["pinned"] == []


@pytest.mark.django_db
def test_the_bar_turns_amber_then_reads_the_longest_camera_by_words_alone(
    incident, person
):
    long_digest(cameras_of(incident)["BWC2-1"].recording)
    full = sitting.json_for(incident)
    need = full["need"]
    # Nearly full: the whole still fits, under the line.
    settings_store.set_to("engine_window_tokens", int(need / 0.9))
    told = sitting.json_for(incident)
    assert told["zone"] == "nearly" and told["sentence"].startswith("Nearly full.")
    assert told["words_alone"] == []
    # Over: the longest camera with a Digest is read by words alone.
    settings_store.set_to("engine_window_tokens", int(need * 0.8))
    told = sitting.json_for(incident)
    assert told["zone"] == "over"
    assert told["words_alone"] == ["BWC2-1"]
    assert told["shown"] == 1 and told["count"] == 2
    assert "More than one sitting" in told["sentence"]
    assert "read by its words alone" in told["sentence"]
    by_name = {one["name"]: one for one in told["cameras"]}
    assert by_name["BWC2-1"]["read"] == "words"
    assert by_name["BWC2-2"]["read"] == "both"
    # Pinned, it stays in, and nothing else can move: the sentence says so.
    incidents.pin(cameras_of(incident)["BWC2-1"], True, by=person)
    told = sitting.json_for(incident)
    assert told["pinned"] == ["BWC2-1"] and told["words_alone"] == []
    assert "leave a camera out" in told["sentence"]
    settings_store.set_to("engine_window_tokens", 131072)


@pytest.mark.django_db
def test_the_fit_moves_the_longest_unpinned_camera_first(incident, person):
    long_digest(cameras_of(incident)["BWC2-1"].recording)
    second = cameras_of(incident)["BWC2-2"].recording
    long_digest(second)
    second.duration_seconds = 3600.0
    second.save()
    system = "the rules"
    _, whole, _ = sitting.fit(
        incident, system=system, wrap=lambda body: body, answer_cap=10, window=10**9
    )
    # One token short of the whole: the longest camera moves to words alone.
    window = prompts.tokens(system) + prompts.tokens(whole) + 10 - 1
    record, user, alone = sitting.fit(
        incident, system=system, wrap=lambda body: body, answer_cap=10, window=window
    )
    assert alone[0] == "BWC2-2", "the longest camera goes first"
    assert "BWC2-2" in record["words_alone"]
    # Every camera by words alone and still too long: TooLong names the pins.
    incidents.pin(cameras_of(incident)["BWC2-2"], True, by=person)
    with pytest.raises(sitting.TooLong) as caught:
        sitting.fit(
            incident, system=system, wrap=lambda body: body, answer_cap=10, window=50
        )
    assert caught.value.pinned == ["BWC2-2"]
    assert caught.value.reason == engine.TOO_LONG


@pytest.mark.django_db
def test_the_page_carries_the_bar_the_pin_and_the_preview(
    client, incident, person, a_case
):
    signed_in(client, person)
    state = client.get(reverse("incident-state", args=[a_case.pk, incident.pk])).json()
    assert state["sitting"]["on"] and state["sitting"]["zone"] == "room"
    camera = cameras_of(incident)["BWC2-1"]
    act = reverse("incident-act", args=[a_case.pk, incident.pk])
    answer = client.post(act, {"action": "pin", "camera": str(camera.pk)}).json()
    assert answer["state"]["sitting"]["pinned"] == ["BWC2-1"]
    camera.refresh_from_db()
    assert camera.pinned
    row = Row.objects.filter(event="Camera pinned").first()
    assert row is not None and row.details["camera"] == "BWC2-1"
    answer = client.post(act, {"action": "unpin", "camera": str(camera.pk)}).json()
    assert answer["state"]["sitting"]["pinned"] == []
    # The dialog's bar with a third video ticked, not yet in the incident.
    third = video(
        person,
        a_case,
        "third",
        seconds=1200.0,
        stamp=stamp("22:10:00", "BWC2-3"),
        lines=((5.0, "Speaker 2", "Nothing to see here."),),
    )
    answer = client.post(
        act, {"action": "sitting_preview", "recordings": [str(third.pk)]}
    ).json()
    told = answer["sitting"]
    assert told["count"] == 3 and told["adding"][0]["name"] == "BWC2-3"
    assert told["sentence"].startswith("Still one sitting")
    assert incident.cameras.count() == 2, "a preview adds nothing"


@pytest.mark.django_db
def test_the_proposals_layer_names_the_cameras_no_run_has_read(incident):
    settings_store.set_to("incidents_propose", True)
    told = incident_assistant.proposals_json(incident)
    assert told["never_read"] == ["BWC2-1", "BWC2-2"]
    assert told["words"].startswith("Not yet read: BWC2-1, BWC2-2")


@pytest.mark.django_db
def test_the_read_words_say_what_was_read():
    assert (
        sitting.read_words(12, 12, [])
        == "everything said on 12 cameras and what they showed"
    )
    assert sitting.read_words(12, 7, ["a", "b", "c", "d", "e"]) == (
        "everything said on 12 cameras and what 7 of them showed; "
        "5 cameras by words alone"
    )


@pytest.mark.django_db
def test_the_status_page_says_where_the_window_came_from(client, person, monkeypatch):
    from core.audit import Category

    signed_in(client, person)
    monkeypatch.setattr(engine, "token_is_set", lambda: True)
    monkeypatch.setattr(
        engine, "served_models_and_windows", lambda: {"gideon-generator": 262144}
    )
    settings_store.set_to("engine_model", "gideon-generator")
    engine.check()
    Row.objects.create(
        category=Category.LLM,
        event="AI assistant call",
        reason_class="llm_too_long",
        details={},
    )
    told = client.get(reverse("panel-status-lines")).json()["assistant"]
    assert told["window"] == 262144
    assert "read from the engine" in told["window_says"]
    assert told["refused_words"].startswith("Readings refused as too long: 1 today")
    # The Engine window row greys with the engine's figure.
    page = client.get(reverse("panel-settings", args=["assistant"]))
    assert b"Read from the engine: 262,144 tokens" in page.content


# The sitting on the case page (Phase 8 chapter 10) -------------------------------


@pytest.mark.django_db
def test_the_shares_are_kept_on_the_cameras_and_refreshed_when_the_digest_is_newer(
    incident,
):
    from django.utils import timezone

    cameras = cameras_of(incident)
    assert all(one.record_made_at is None for one in cameras.values())
    told = sitting.json_for(incident)
    first = cameras_of(incident)["BWC2-1"]
    second = cameras_of(incident)["BWC2-2"]
    assert first.record_made_at is not None and first.record_tokens > 0
    assert first.record_tokens != first.words_tokens, "a Digest counts differently"
    assert second.record_tokens == second.words_tokens, "no Digest: the words"
    assert told["cameras"][0]["tokens"] == first.record_tokens
    # A newer Digest makes the share stale, and the next draw counts again.
    was = first.record_tokens
    DigestPart.objects.create(
        transcript=first.recording.transcript,
        number=2,
        text="3. [00:00:40]-[00:00:44] (both) A long extra part about the roadside.",
        made_at=timezone.now(),
    )
    sitting.json_for(incident)
    first.refresh_from_db()
    assert first.record_tokens > was


@pytest.mark.django_db
def test_the_offer_and_the_case_page_carry_the_bar(client, incident, person, a_case):
    settings_store.set_to("incidents_proposed", True)
    signed_in(client, person)
    # A third video with a checked clock that overlaps the incident: offered
    # to it, with the bar as the incident would read with it in.
    third = video(
        person,
        a_case,
        "third",
        seconds=900.0,
        stamp=stamp("21:58:00", "BWC2-3"),
        lines=((5.0, "Speaker 2", "Nothing to see here."),),
    )
    offered = incidents.offers(a_case)
    assert offered and offered[0]["kind"] == "add"
    told = offered[0]["sitting"]
    assert told["on"] and told["count"] == 3
    assert told["adding"][0]["name"] == "BWC2-3"
    assert told["short"].startswith("Room for about")
    # Two loose videos that overlap each other: offered as a new incident,
    # with the bar before the incident exists.
    for camera in incident.cameras.all():
        incidents.remove_camera(camera, by=person)
    fresh = incidents.offers(a_case)
    new = [one for one in fresh if one["kind"] == "new"]
    assert new and new[0]["sitting"]["on"]
    assert new[0]["sitting"]["count"] == len(new[0]["recordings"])
    assert new[0]["sitting"]["zone"] == "room"
    # The tab's rows carry the column and the offer carries the bar.
    incidents.make(a_case, "Again", [cameras_of_case(a_case)["first"]], by=person)
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=incidents")
    body = page.content.decode()
    assert "The assistant holds" in body
    assert "sitting-mini" in body and "hours&#x27; worth" in body
    assert third.pk  # the offer still stands, its bar drawn
    # Off when the assistant is off.
    settings_store.set_to("assistant_available", False)
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=incidents")
    assert "The assistant holds" not in page.content.decode()
    settings_store.set_to("assistant_available", True)


def cameras_of_case(case) -> dict:
    return {one.title: one for one in case.recordings.all()}
