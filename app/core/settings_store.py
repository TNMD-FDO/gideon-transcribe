"""Admin settings: the ones an Admin changes in the panel, not in a file.

`.env` holds what an office cannot change without a restart, such as the
hostname and the folders. These are the other kind: an Admin changes them
while the app runs and they take effect on the next thing that reads them.

Every row here is the admin settings catalogue's, with its name, its help, its
default, and the "When changed" line the panel prints beneath the control, so
that the panel has nothing of its own to say about a setting and the two
cannot drift apart. Phase 2 rows are absent rather than greyed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.db import models

# The kinds of setting. A kind decides how it is stored, how it is checked,
# and which control the panel draws.
NUMBER = "number"
TOGGLE = "toggle"
CHOICE = "choice"
TEXT = "text"

# The panel's Settings pages, in the order the rail lists them.
FEATURES = "features"
LIMITS = "limits"
TRANSCRIPTION = "transcription"
ASSISTANT = "assistant"
NOTICES = "notices"
SIGN_IN = "sign-in"
AUDIT = "audit"

PAGES = [
    (FEATURES, "Features"),
    (LIMITS, "Limits"),
    (TRANSCRIPTION, "Transcription defaults"),
    (ASSISTANT, "AI assistant"),
    (NOTICES, "Notices"),
    (SIGN_IN, "Sign-in and directory"),
    (AUDIT, "Audit log"),
]


@dataclass(frozen=True)
class Definition:
    """One setting: what it is, what it may be, and what it starts as."""

    key: str
    page: str
    name: str
    kind: str
    default: object
    what_it_does: str
    when_changed: str
    least: int | None = None
    most: int | None = None
    unit: str = ""
    choices: tuple = ()
    lines: int = 3
    # Vocabulary is content, so its audit row says only that it changed.
    content: bool = False
    aliases: tuple = field(default=(), repr=False)


def _rows() -> list[Definition]:
    return [
        # Features -------------------------------------------------------------
        Definition(
            key="diarization_available",
            page=FEATURES,
            name="Diarization available",
            kind=TOGGLE,
            default=True,
            what_it_does=(
                "Users may separate a Recording into Speakers, with a "
                "speaker-count hint."
            ),
            when_changed=(
                "Off hides the Diarization choice on the Upload page. "
                "Recordings already processed keep their Speakers, and Jobs "
                "already in the line run as they were submitted."
            ),
        ),
        Definition(
            key="translation_available",
            page=FEATURES,
            name="Translation available",
            kind=TOGGLE,
            default=True,
            what_it_does='Users may ask for "Translate to English".',
            when_changed=(
                "Off hides the choice. A Recording holding more than one "
                "language is then transcribed in its winning language with a "
                "warning, whatever the mixed-language setting says."
            ),
        ),
        Definition(
            key="clips_available",
            page=FEATURES,
            name="Clips available",
            kind=TOGGLE,
            default=True,
            what_it_does=(
                "Users may save a chosen span of a Recording as a playable "
                "file, a Clip."
            ),
            when_changed=(
                "Off hides New Clip and the Clips sheet, hides the Clips page "
                "in the navigation, and drops Clips from the sign-out dialog "
                'and "Download everything". Clip files already made stay '
                "until their Recording goes."
            ),
        ),
        # Limits ---------------------------------------------------------------
        Definition(
            key="largest_file_gb",
            page=LIMITS,
            name="Largest file",
            kind=NUMBER,
            default=10,
            least=1,
            most=100,
            unit="GB",
            what_it_does=(
                "The biggest single upload accepted; larger is refused. A "
                "six-hour body-worn camera export is about 13 GB, so an "
                "office with those raises it."
            ),
            when_changed="The next upload.",
        ),
        Definition(
            key="longest_recording_minutes",
            page=LIMITS,
            name="Longest Recording",
            kind=NUMBER,
            default=6 * 60,
            least=60,
            most=8 * 60,
            unit="minutes",
            what_it_does=(
                "Longer Recordings are refused when the file is inspected. "
                "The WhisperX service refuses anything over eight hours "
                "whatever this says."
            ),
            when_changed="The next upload.",
        ),
        Definition(
            key="longest_clip_minutes",
            page=LIMITS,
            name="Longest Clip",
            kind=NUMBER,
            default=30,
            least=1,
            most=8 * 60,
            unit="minutes",
            what_it_does="How long a Clip a person may save.",
            when_changed="The next Clip saved.",
        ),
        Definition(
            key="files_per_batch",
            page=LIMITS,
            name="Files per Batch",
            kind=NUMBER,
            default=25,
            least=1,
            most=200,
            unit="files",
            what_it_does=(
                "The only size rule for a Batch. Setting it to 1 makes every "
                "Batch a single file, so there is no separate bulk-upload "
                "switch."
            ),
            when_changed="The next Batch.",
        ),
        Definition(
            key="default_quota_gb",
            page=LIMITS,
            name="Default Workspace quota per user",
            kind=NUMBER,
            default=50,
            least=1,
            most=5000,
            unit="GB",
            what_it_does=(
                "Everything on disk for a person's recordings counts towards "
                "it. A per-person override on the Users page wins."
            ),
            when_changed="The next upload. Nothing already stored is touched.",
        ),
        Definition(
            key="minimum_free_disk_gb",
            page=LIMITS,
            name="Minimum free disk space",
            kind=NUMBER,
            default=200,
            least=10,
            most=10000,
            unit="GB",
            what_it_does=(
                "Uploads are refused below it. Nothing already stored is "
                "discarded to make room."
            ),
            when_changed=(
                "At once. The Status page turns amber under twice this figure "
                "and red under it."
            ),
        ),
        # Transcription defaults -----------------------------------------------
        Definition(
            key="model",
            page=TRANSCRIPTION,
            name="Model",
            kind=CHOICE,
            default="large-v3-turbo",
            choices=("large-v3-turbo", "large-v3"),
            what_it_does=(
                "The model every Run asks for. Users cannot change it and the "
                "Upload page does not show it."
            ),
            when_changed=(
                "The next Run. The service swaps models once, in under a "
                "minute."
            ),
        ),
        Definition(
            key="diarize_by_default",
            page=TRANSCRIPTION,
            name="Diarization ticked by default",
            kind=TOGGLE,
            default=True,
            what_it_does='The Upload page\'s "Diarize" checkbox starts ticked.',
            when_changed="The next Upload page opened.",
        ),
        Definition(
            key="translate_by_default",
            page=TRANSCRIPTION,
            name='"Translate to English" ticked by default',
            kind=TOGGLE,
            default=False,
            what_it_does=(
                "For an office whose Recordings are mostly not in English."
            ),
            when_changed="The next Upload page opened.",
        ),
        Definition(
            key="translate_mixed",
            page=TRANSCRIPTION,
            name="Translate mixed-language Recordings to English automatically",
            kind=TOGGLE,
            default=True,
            what_it_does=(
                "A Recording holding more than one language is translated "
                "wholesale to English."
            ),
            when_changed=(
                "Off: such a Recording is transcribed in its winning language "
                "with a warning. The next Run."
            ),
        ),
        Definition(
            key="office_vocabulary",
            page=TRANSCRIPTION,
            name="Office Vocabulary",
            kind=TEXT,
            default="",
            lines=8,
            content=True,
            what_it_does=(
                "One name or term per line, sent with every Run ahead of the "
                "Batch's own Vocabulary. The service's prompt is short, so a "
                "long list is cut from the end and the Batch's list wins."
            ),
            when_changed=(
                "The next Run. The audit row says only that it changed, "
                "because a Vocabulary is content."
            ),
        ),
        Definition(
            key="preprocessing",
            page=TRANSCRIPTION,
            name="Preprocessing profile",
            kind=CHOICE,
            default="standard",
            choices=("standard", "off"),
            what_it_does="The audio clean-up before recognition.",
            when_changed=(
                "The next media job. It is recorded in every Provenance."
            ),
        ),
        # AI assistant ---------------------------------------------------------
        Definition(
            key="assistant_available",
            page=ASSISTANT,
            name="AI assistant",
            kind=TOGGLE,
            default=False,
            what_it_does=(
                "The master switch. It starts Off until an engine answers."
            ),
            when_changed=(
                "Off hides Summary, Chat, and Suggest names everywhere. "
                "Existing Summaries and Chats are hidden, not deleted."
            ),
        ),
        Definition(
            key="chat_available",
            page=ASSISTANT,
            name="Chat",
            kind=TOGGLE,
            default=True,
            what_it_does="Asking questions of one Transcript.",
            when_changed="Off hides Chat; existing Chats are hidden, not deleted.",
        ),
        Definition(
            key="summary_available",
            page=ASSISTANT,
            name="Summary",
            kind=TOGGLE,
            default=True,
            what_it_does="Writing a Summary of one Transcript.",
            when_changed=(
                "Off hides Summary; existing Summaries are hidden, not deleted."
            ),
        ),
        Definition(
            key="suggestions_available",
            page=ASSISTANT,
            name="Speaker suggestions",
            kind=TOGGLE,
            default=True,
            what_it_does="Suggesting who each Speaker is, from the talk.",
            when_changed="Off hides Suggest names.",
        ),
        Definition(
            key="assistant_thinks",
            page=ASSISTANT,
            name="Let the model think before answering",
            kind=TOGGLE,
            default=False,
            what_it_does="Slower, sometimes better.",
            when_changed=(
                "On doubles the time limits: Chat 4 minutes, Summary 10, "
                "suggestions 6. The next call."
            ),
        ),
        Definition(
            key="engine_address",
            page=ASSISTANT,
            name="Engine address",
            kind=TEXT,
            default="http://vllm:8000/v1",
            lines=1,
            what_it_does=(
                "The engine's base URL. Test connection lists the models and "
                "runs one tiny completion."
            ),
            when_changed="The next call.",
        ),
        Definition(
            key="engine_model",
            page=ASSISTANT,
            name="Model name",
            kind=TEXT,
            default="local-engine",
            lines=1,
            what_it_does=(
                "The served name the engine expects. An office on a Shared "
                "engine enters that engine's served name here."
            ),
            when_changed="The next call.",
        ),
        Definition(
            key="engine_display_name",
            page=ASSISTANT,
            name="Model display name",
            kind=TEXT,
            default="",
            lines=1,
            what_it_does=(
                "What {model} prints in the AI notice. Empty means the served "
                "name."
            ),
            when_changed="The next Summary or Chat shown or exported.",
        ),
        # Notices --------------------------------------------------------------
        Definition(
            key="transcription_notice",
            page=NOTICES,
            name="Transcription notice",
            kind=TEXT,
            default=(
                "Automatic transcription by Whisper {model}. Corrections made "
                "by staff are marked. This is not a certified transcript."
            ),
            what_it_does=(
                "Printed on every export of a Transcript that was not "
                "translated. {model} is filled from the Provenance."
            ),
            when_changed="The next export.",
        ),
        Definition(
            key="translation_notice",
            page=NOTICES,
            name="Translation notice",
            kind=TEXT,
            default=(
                "Machine translation to English from {language} by Whisper "
                "{model}. The original-language text was not kept. This is "
                "not a certified translation."
            ),
            what_it_does=(
                "Printed on every export of a translated Transcript, and "
                "never on Captions. {language} and {model} are filled from "
                "the Provenance."
            ),
            when_changed="The next export.",
        ),
        Definition(
            key="ai_notice",
            page=NOTICES,
            name="AI notice",
            kind=TEXT,
            default=(
                "AI-generated and unverified. Check against the recording "
                "before relying on it. Written by {model} on {date}."
            ),
            what_it_does=(
                "Shown at the top of every Summary and Chat and printed on "
                "their exports."
            ),
            when_changed="The next Summary or Chat shown or exported.",
        ),
        Definition(
            key="sign_in_notice",
            page=NOTICES,
            name="Sign-in page notice",
            kind=TEXT,
            default="",
            lines=2,
            what_it_does=(
                "A short text under the sign-in form, for an authorised-use "
                "line or a support line. Empty hides it."
            ),
            when_changed="The next sign-in page shown.",
        ),
        # Sign-in and directory ------------------------------------------------
        Definition(
            key="idle_timeout_minutes",
            page=SIGN_IN,
            name="Idle timeout",
            kind=NUMBER,
            default=8 * 60,
            least=60,
            most=24 * 60,
            unit="minutes",
            what_it_does=(
                "How long a Login session may sit idle before it ends. This "
                "is also the Workspace's lifetime: recordings and transcripts "
                "are removed when a session ends. The grace period after a "
                "session's last Job equals it."
            ),
            when_changed=(
                "The next request of every open session. The fifteen-minute "
                "warning stands."
            ),
        ),
        Definition(
            key="directory_check_hour",
            page=SIGN_IN,
            name="Directory check time",
            kind=NUMBER,
            default=3,
            least=0,
            most=23,
            unit="o'clock",
            what_it_does=(
                "The hour, office time, of the nightly comparison of accounts "
                "against the directory."
            ),
            when_changed="The next night.",
        ),
        # Audit log ------------------------------------------------------------
        Definition(
            key="audit_retention_months",
            page=AUDIT,
            name="Audit log retention",
            kind=NUMBER,
            default=3,
            least=1,
            most=120,
            unit="months",
            what_it_does=(
                "How long an audit row is kept. Three months is enough to "
                "troubleshoot with. An office that wants a longer record of "
                "who opened whose material raises it, and the admin guide "
                "says plainly that an Admin access is forgotten after this."
            ),
            when_changed=(
                "The next sweep. Shortening it removes rows the same night."
            ),
        ),
    ]


DEFINITIONS = {one.key: one for one in _rows()}


def page_settings(page: str) -> list[Definition]:
    return [one for one in DEFINITIONS.values() if one.page == page]


class Setting(models.Model):
    """One stored value. Anything not stored is at its default.

    Numbers and toggles are kept in `value` and text in `text`, so that a
    number is a number in the database and a query about one does not have to
    parse it back out of a string.
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.IntegerField(null=True, blank=True)
    text = models.TextField(blank=True, default="")
    changed = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key} = {self.value if self.text == '' else self.text!r}"


def definition(key: str) -> Definition:
    try:
        return DEFINITIONS[key]
    except KeyError:
        raise KeyError(f"there is no setting called {key!r}") from None


def get(key: str):
    """What this setting is now, which is its default until somebody moves it."""
    known = definition(key)
    stored = Setting.objects.filter(key=key).first()
    if stored is None:
        return known.default

    if known.kind == NUMBER:
        return known.default if stored.value is None else stored.value
    if known.kind == TOGGLE:
        return known.default if stored.value is None else bool(stored.value)
    return stored.text


def check(key: str, value):
    """The value this setting would take, or a refusal saying why not.

    Checked here rather than in a form, so that every way of reaching a
    setting, panel or command line or test, is held to the same rule.
    """
    known = definition(key)

    if known.kind == NUMBER:
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{known.name} is a number, and {value!r} is not"
            ) from None
        if not known.least <= number <= known.most:
            raise ValueError(
                f"{known.name} may be from {known.least} to {known.most} "
                f"{known.unit}, and {number} is outside that"
            )
        return number

    if known.kind == TOGGLE:
        if isinstance(value, str):
            return value.lower() in ("1", "true", "on", "yes")
        return bool(value)

    if known.kind == CHOICE:
        wanted = str(value)
        if wanted not in known.choices:
            raise ValueError(
                f"{known.name} may be {' or '.join(known.choices)}, and "
                f"{wanted!r} is none of them"
            )
        return wanted

    return str(value)


def set_to(key: str, value) -> None:
    """Move a setting, refusing anything outside what it may be."""
    known = definition(key)
    wanted = check(key, value)

    if known.kind in (NUMBER, TOGGLE):
        Setting.objects.update_or_create(
            key=key, defaults={"value": int(wanted), "text": ""}
        )
    else:
        Setting.objects.update_or_create(
            key=key, defaults={"value": None, "text": wanted}
        )


def shown(key: str, value=None) -> str:
    """A value as a person reads it, for the tray and the audit row."""
    known = definition(key)
    if value is None:
        value = get(key)
    if known.kind == TOGGLE:
        return "On" if value else "Off"
    if known.kind == NUMBER:
        return f"{value} {known.unit}".strip()
    if known.kind == TEXT and known.content:
        return "(changed)"
    return str(value) if str(value) else "(empty)"


def is_at_default(key: str) -> bool:
    return get(key) == definition(key).default


# What the rest of the app asks for, in the units it works in ------------------

GB = 1024**3


def idle_timeout() -> timedelta:
    return timedelta(minutes=get("idle_timeout_minutes"))


def audit_retention_months() -> int:
    return get("audit_retention_months")


def largest_file_bytes() -> int:
    return get("largest_file_gb") * GB


def longest_recording_seconds() -> int:
    return get("longest_recording_minutes") * 60


def longest_clip_seconds() -> int:
    return get("longest_clip_minutes") * 60


def files_per_batch() -> int:
    return get("files_per_batch")


def default_quota_bytes() -> int:
    return get("default_quota_gb") * GB


def minimum_free_disk_bytes() -> int:
    return get("minimum_free_disk_gb") * GB
