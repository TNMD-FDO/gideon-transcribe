"""The Interpreter (Phase 3, chapter 3): a Session between a Visitor who speaks
another language and Staff, heard, translated, and kept.

A Session is a Live recording of the style "interpreter". While it runs the
page sends each Turn's audio on its own, the moment the person stops talking:
the media worker prepares it and hands it to the WhisperX service (the fast
lane when there is one), which writes the words as spoken and says which
language it heard; the LLM worker then asks the office's engine for the
translation into the other language. The page shows both. At Stop the whole
recording is the Recording, and its Transcript is built from the Turns, each
Segment carrying the words as heard and their translation.

This first slice is text only: the voices (chapter 3, "Voices") come next.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone

from core import audit, settings_store
from core.recordings import Recording

log = logging.getLogger("transcribe.interpreter")

STYLE = "interpreter"
VISITOR = "visitor"
STAFF = "staff"

# How long a Turn's transcription is waited for before it is given up on: a
# Turn is seconds of speech and the lane answers in about one, so a minute
# means the service is in trouble, not slow.
TURN_WAIT_SECONDS = 60
TURN_POLL_SECONDS = 0.5
# The translation is a sentence or two; a cap far above it, and short.
TRANSLATION_CAP = 800
TRANSLATION_TIMEOUT = 45
# A service that was away (restarting, mid-upgrade) is asked again a few
# times before a Turn is written off.
HEAR_TRIES = 4
HEAR_RETRY_SECONDS = 5
# What Whisper says when it hears nothing much: a short quiet clip comes back
# as thanks, in several languages, or as the sign-off of a video. A Turn
# whose whole text is one of these was nothing said, and is shown as such
# rather than translated. Compared with punctuation and case stripped.
HALLUCINATIONS = frozenset(
    {
        "thank you",
        "thanks",
        "thank you very much",
        "thanks for watching",
        "thank you for watching",
        "gracias",
        "muchas gracias",
        "subtitulos por la comunidad de amaracom",
        "subtitulos realizados por la comunidad de amaracom",
        "you",
        "bye",
        "okay",
        "ok",
        "hmm",
        "mm",
        "uh",
        "um",
        "si",
        "sí",
    }
)

# The languages the app can name on the page, by Whisper's code. English is
# Staff's and is never offered. The table the research note built
# (docs/research/interpreter-languages.md) says what each can do; the names
# are for the page, in English and as the Visitor would read them.
NAMES = {
    "es": ("Spanish", "Español"),
    "pt": ("Portuguese", "Português"),
    "fr": ("French", "Français"),
    "ht": ("Haitian Creole", "Kreyòl ayisyen"),
    "zh": ("Chinese (Mandarin)", "中文"),
    "yue": ("Cantonese", "廣東話"),
    "vi": ("Vietnamese", "Tiếng Việt"),
    "ar": ("Arabic", "العربية"),
    "ru": ("Russian", "Русский"),
    "uk": ("Ukrainian", "Українська"),
    "ko": ("Korean", "한국어"),
    "so": ("Somali", "Soomaali"),
    "sw": ("Swahili", "Kiswahili"),
    "am": ("Amharic", "አማርኛ"),
    "hi": ("Hindi", "हिन्दी"),
    "pa": ("Punjabi", "ਪੰਜਾਬੀ"),
    "tl": ("Tagalog", "Tagalog"),
    "de": ("German", "Deutsch"),
    "it": ("Italian", "Italiano"),
    "ja": ("Japanese", "日本語"),
    "fa": ("Persian", "فارسی"),
    "tr": ("Turkish", "Türkçe"),
    "pl": ("Polish", "Polski"),
    "ne": ("Nepali", "नेपाली"),
    "my": ("Burmese", "မြန်မာ"),
}

# The shipped notice, and its Spanish, so the first offered language reads it
# in its own words without an engine call. Other languages get the English
# and, when the engine is there, a translation asked for at the Session's
# start (a typed Turn of the notice's own kind).
SHIPPED_NOTICE = (
    "This computer is translating what we say to each other. It is not an "
    "interpreter, and it makes mistakes. A recording is kept."
)
SHIPPED_NOTICE_ES = (
    "Esta computadora está traduciendo lo que nos decimos. No es un intérprete "
    "y comete errores. Se guarda una grabación."
)
SHIPPED_PHRASES = (
    "Please wait a moment.",
    "We are arranging an interpreter.",
    "Do you understand?",
    "Please say that again.",
    "This conversation is being recorded.",
    "We are finished for today.",
)


class Turn(models.Model):
    """One stretch of speech by one Side of a Session: its language, what the
    app heard, and its translation."""

    HEARING = "hearing"
    TRANSLATING = "translating"
    DONE = "done"
    FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(
        Recording, on_delete=models.CASCADE, related_name="turns"
    )
    number = models.IntegerField()
    # Who spoke: "visitor" or "staff". Empty until the language heard says.
    side = models.CharField(max_length=10, blank=True, default="")
    # Typed rather than spoken: a name, a number, a quick phrase.
    typed = models.BooleanField(default=False)
    # Recorded seconds, as the page's clock counted them.
    start = models.FloatField(default=0.0)
    end = models.FloatField(default=0.0)
    language = models.CharField(max_length=10, blank=True, default="")
    heard = models.TextField(blank=True, default="")
    translation = models.TextField(blank=True, default="")
    state = models.CharField(max_length=12, default=HEARING)
    failure = models.CharField(max_length=60, blank=True, default="")
    service_job_id = models.CharField(max_length=64, blank=True, default="")
    lane = models.CharField(max_length=10, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]

    @property
    def audio_path(self) -> Path:
        return self.recording.folder / "turns" / f"{self.number:04d}.webm"

    @property
    def asr_path(self) -> Path:
        return self.recording.folder / "turns" / f"{self.number:04d}.wav"


# The setting and the languages ---------------------------------------------


def on() -> bool:
    """Interpreter On, under Live recording, with an engine to translate."""
    from core import engine, live

    return bool(live.on() and settings_store.get("interpreter") and engine.configured())


def languages_offered() -> list[dict]:
    """The office's ticks, as the page's list: code, English name, own name."""
    raw = settings_store.get("interpreter_languages") or ""
    codes = [one.strip().lower() for one in str(raw).splitlines() if one.strip()]
    offered = []
    for code in codes:
        if code == "en" or code in {one["code"] for one in offered}:
            continue
        name, own = NAMES.get(code, (code, code))
        offered.append({"code": code, "name": name, "own": own})
    return offered


def name_of(code: str) -> str:
    return NAMES.get(code, (code, code))[0] if code else ""


def notice_lines(language: str) -> list[str]:
    """The notice at the top of the page: the office's words, and the
    Visitor's language when the app has them without an engine call."""
    text = (settings_store.get("interpreter_notice") or SHIPPED_NOTICE).strip()
    lines = [text]
    if language == "es" and text == SHIPPED_NOTICE:
        lines.append(SHIPPED_NOTICE_ES)
    return lines


def phrases() -> list[str]:
    raw = settings_store.get("interpreter_phrases") or ""
    lines = [one.strip() for one in str(raw).splitlines() if one.strip()]
    return lines or list(SHIPPED_PHRASES)


def is_session(recording: Recording) -> bool:
    return bool((recording.live or {}).get("interpreter"))


def visitor_language(recording: Recording) -> str:
    return (recording.live or {}).get("visitor_language") or ""


# Starting -------------------------------------------------------------------


def start(user, case, *, language: str, title: str, browser: str, request=None):
    """A Session begins: a Live recording of the Interpreter style, with the
    Visitor's language chosen or left to be heard."""
    from core import live

    if not on():
        raise live.Refused("The Interpreter is off.")
    offered = {one["code"] for one in languages_offered()}
    language = (language or "").strip().lower()
    if language and language not in offered:
        raise live.Refused("That language is not one the office offers.")
    when = timezone.localtime(timezone.now())
    title = (title or "").strip() or (
        f"Interpreter, {name_of(language) or 'language to be heard'}, "
        f"{when:%d %b %Y %H:%M}"
    )
    recording = live.start(
        user,
        case,
        title=title,
        browser=browser,
        dictation=case is None,
        style=STYLE,
        request=request,
    )

    def mark(facts: dict):
        facts["interpreter"] = True
        facts["visitor_language"] = language
        facts["language_settled_by"] = "chosen" if language else ""

    live.change_live(recording, mark)
    return recording


# Turns arriving -------------------------------------------------------------


def turn_arrived(
    recording: Recording,
    *,
    start_at: float,
    end_at: float,
    side: str = "",
    audio: bytes | None = None,
    typed: str = "",
) -> Turn:
    """A Turn from the page: spoken (its audio, to be heard) or typed (its
    words, to be translated). Handed to the workers at once."""
    from core.tasks import hear_turn, translate_turn

    side = side if side in (VISITOR, STAFF) else ""
    number = (recording.turns.aggregate(models.Max("number"))["number__max"] or 0) + 1
    turn = Turn(
        recording=recording,
        number=number,
        side=side,
        start=round(float(start_at), 1),
        end=round(float(end_at), 1),
    )
    if typed:
        turn.typed = True
        turn.heard = typed.strip()[:2000]
        turn.side = side or STAFF
        turn.language = "en" if turn.side == STAFF else visitor_language(recording)
        turn.state = Turn.TRANSLATING
        turn.save()
        translate_turn.defer(turn_id=str(turn.pk))
        return turn
    turn.save()
    turn.audio_path.parent.mkdir(parents=True, exist_ok=True)
    turn.audio_path.write_bytes(audio or b"")
    hear_turn.defer(turn_id=str(turn.pk))
    return turn


def is_filler(text: str) -> bool:
    """Whether the words are one of Whisper's made-up thanks and sign-offs."""
    plain = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(plain.split()) in HALLUCINATIONS


def hear(turn: Turn, attempt: int = 1) -> Turn:
    """The media worker's part: prepare the Turn's audio, hand it to the
    service, wait for the words, and decide whose Turn it was."""
    from core import media, whisperx

    recording = turn.recording
    if not turn.audio_path.exists() or turn.audio_path.stat().st_size == 0:
        return _failed(turn, "no sound arrived")
    try:
        media.make_asr_audio(turn.audio_path, turn.asr_path, None)
    except media.MediaError as problem:
        return _failed(turn, problem.reason_class)

    chosen = visitor_language(recording)
    language = "en" if turn.side == STAFF else (chosen if turn.side == VISITOR else "")
    request = {
        "task": "transcribe",
        "language": language,
        "model": settings_store.get("model"),
        "diarize": False,
        "vocabulary": [],
        "context": "",
        "return_speaker_embeddings": False,
        "client_reference": str(turn.pk),
        "priority": 100,
    }
    lane = (
        whisperx.FAST
        if whisperx.fast_lane_configured() and whisperx.is_alive(whisperx.FAST)
        else ""
    )
    try:
        submitted = whisperx.submit(turn.asr_path, request, lane)
    except whisperx.ServiceError as problem:
        if problem.reason_class == "service_unreachable" and attempt < HEAR_TRIES:
            # The service is away for a moment: ask again shortly, and leave
            # the Turn as "hearing" so the page keeps waiting for it.
            from core.tasks import hear_turn

            hear_turn.configure(schedule_in={"seconds": HEAR_RETRY_SECONDS}).defer(
                turn_id=str(turn.pk), attempt=attempt + 1
            )
            log.info(
                "turn %d of %s: service away, asking again", turn.number, recording.pk
            )
            return turn
        return _failed(turn, problem.reason_class)
    turn.service_job_id = submitted.id
    turn.lane = lane
    turn.save(update_fields=["service_job_id", "lane"])

    result = _wait_for(turn)
    if result is None:
        return _failed(turn, "the service did not answer in time")

    text = " ".join(
        (one.get("text") or "").strip() for one in result.get("segments", [])
    ).strip()
    if is_filler(text):
        # Nothing was said; the engine made something up. Shown as nothing.
        text = ""
    heard_language = (result.get("language") or {}).get("detected") or language
    turn.heard = text
    turn.language = heard_language[:10]
    if not turn.side:
        # Nobody held a button: the language says who spoke.
        turn.side = STAFF if heard_language.startswith("en") else VISITOR
    if (
        turn.side == VISITOR
        and not chosen
        and heard_language
        and not (heard_language.startswith("en"))
    ):
        _settle_language(recording, heard_language, turn.number)
    if not text:
        turn.state = Turn.DONE
        turn.translation = ""
        turn.save()
        return turn
    turn.state = Turn.TRANSLATING
    turn.save()
    from core.tasks import translate_turn

    translate_turn.defer(turn_id=str(turn.pk))
    return turn


def _wait_for(turn: Turn) -> dict | None:
    from core import whisperx

    deadline = time.monotonic() + TURN_WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            states = {one["id"]: one for one in whisperx.jobs(turn.lane)}
        except whisperx.ServiceError:
            states = {}
        state = (states.get(turn.service_job_id) or {}).get("state")
        if state == "done":
            try:
                result = whisperx.result(turn.service_job_id, turn.lane)
            except whisperx.ServiceError:
                return None
            whisperx.delete(turn.service_job_id, turn.lane)
            return result
        if state in ("failed", "cancelled"):
            whisperx.delete(turn.service_job_id, turn.lane)
            return None
        time.sleep(TURN_POLL_SECONDS)
    return None


def _settle_language(recording: Recording, language: str, at_turn: int) -> None:
    """The app heard the Visitor's language rather than being told it."""
    from core import live

    def settle(facts: dict):
        if not facts.get("visitor_language"):
            facts["visitor_language"] = language
            facts["language_settled_by"] = "heard"

    live.change_live(recording, settle)
    audit.write(
        audit.Category.RECORDINGS,
        "Language settled",
        system="interpreter",
        affected_user=recording.user,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        language=language,
        at_turn=at_turn,
    )


def translate(turn: Turn) -> Turn:
    """The LLM worker's part: the other side's language, from the engine."""
    from core import engine, prompts

    recording = turn.recording
    visitor = visitor_language(recording)
    target = visitor if turn.side == STAFF else "en"
    if not target:
        # A Staff Turn before the Visitor's language is known: nothing to
        # translate into yet. Shown as heard; the page says so.
        turn.state = Turn.DONE
        turn.save(update_fields=["state"])
        return turn
    if not turn.heard.strip():
        turn.state = Turn.DONE
        turn.save(update_fields=["state"])
        return turn
    try:
        answer = engine.complete(
            [
                {
                    "role": "system",
                    "content": prompts.TRANSLATE.format(
                        target=name_of(target) if target != "en" else "English"
                    ),
                },
                {"role": "user", "content": turn.heard},
            ],
            max_completion_tokens=TRANSLATION_CAP,
            temperature=0.2,
            top_p=0.9,
            thinking=False,
            timeout=TRANSLATION_TIMEOUT,
        )
    except engine.Problem as problem:
        return _failed(turn, problem.reason_class)
    turn.translation = (answer.get("text") or "").strip()
    turn.state = Turn.DONE
    turn.save(update_fields=["translation", "state"])
    return turn


def _failed(turn: Turn, why: str) -> Turn:
    turn.state = Turn.FAILED
    turn.failure = (why or "failed")[:60]
    turn.save(update_fields=["state", "failure"])
    log.warning("turn %d of %s failed: %s", turn.number, turn.recording_id, why)
    return turn


# The page's rows -----------------------------------------------------------


def rows(recording: Recording, since: int = 0) -> list[dict]:
    """Every Turn after `since`, and every Turn still changing, for the page."""
    turns = recording.turns.filter(
        models.Q(number__gt=since) | ~models.Q(state=Turn.DONE)
    ).order_by("number")
    return [
        {
            "number": one.number,
            "side": one.side,
            "typed": one.typed,
            "start": one.start,
            "end": one.end,
            "language": one.language,
            "heard": one.heard,
            "translation": one.translation,
            "state": one.state,
            "failure": one.failure,
        }
        for one in turns
    ]


# At Stop -------------------------------------------------------------------


def finish(recording: Recording):
    """The Transcript of a Session: one Segment per Turn, the words as heard
    and their translation, the two Sides as the Speakers."""
    from core.jobs import Segment, Transcript

    Transcript.objects.filter(recording=recording).delete()
    turns = list(recording.turns.order_by("number"))
    language = visitor_language(recording)
    transcript = Transcript.objects.create(
        recording=recording,
        job=None,
        task_run="transcribe",
        task_reason="requested",
        language=language,
        language_probability=None,
        language_mixed=True,
        word_timestamps=False,
        word_timestamps_reason="turns",
        provenance={
            "interpreter": {
                "visitor_language": language,
                "settled_by": (recording.live or {}).get("language_settled_by", ""),
                "turns": len(turns),
                "typed": sum(1 for one in turns if one.typed),
                "failed": sum(1 for one in turns if one.state == Turn.FAILED),
            }
        },
    )
    side = recording.sides.order_by("number").first()
    Segment.objects.bulk_create(
        [
            Segment(
                transcript=transcript,
                side=side,
                start=one.start,
                end=max(one.end, one.start),
                text=one.heard or ("(typed)" if one.typed else "(nothing heard)"),
                speaker="Staff" if one.side == STAFF else "Visitor",
                speaker_label=one.side or "",
                words=[],
                language=one.language,
                translation=one.translation,
            )
            for one in turns
        ]
    )
    log.info("session %s finished: %d turns", recording.pk, len(turns))
    return transcript


def provenance_rows(recording: Recording) -> list[tuple[str, str]]:
    """What the Details panel and the Word export say about a Session."""
    if not is_session(recording):
        return []
    facts = recording.live or {}
    language = name_of(facts.get("visitor_language") or "") or "not settled"
    how = facts.get("language_settled_by") or ""
    rows_ = [
        (
            "Interpreted",
            f"a Session between a visitor speaking {language} and staff speaking "
            f"English; the language was {'chosen' if how == 'chosen' else 'heard'}. "
            "Machine translation, not an interpreter.",
        )
    ]
    count = recording.turns.count()
    if count:
        rows_.append(("Turns", f"{count}, each transcribed and translated as it ended"))
    return rows_
