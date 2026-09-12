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
CASES = "cases"
APPEARANCE = "appearance"
EMAIL = "email"
# Not a Settings page: these rows are edited on the Templates page, at once,
# outside the tray, like the prompt templates beside them.
TEMPLATES = "templates"

# The Recording types the app ships with, one per line. A type an office
# removes stays on the Recordings that already hold it.
SHIPPED_RECORDING_TYPES = "\n".join(
    [
        "Body camera",
        "Jail call",
        "Interview",
        "Phone call",
        "Hearing",
        "Meeting",
        "Dictation",
        "Other",
    ]
)

PAGES = [
    (FEATURES, "Features"),
    (LIMITS, "Limits"),
    (TRANSCRIPTION, "Transcription defaults"),
    (ASSISTANT, "AI assistant"),
    (NOTICES, "Notices"),
    (SIGN_IN, "Sign-in and directory"),
    (AUDIT, "Audit log"),
    (CASES, "Cases"),
    (APPEARANCE, "Appearance"),
    (EMAIL, "Email"),
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
    # A toggle this setting is greyed under while that toggle is off. The
    # value is kept; only the control is closed, and the page says so.
    needs: str = ""
    # Greyed while mail is not configured (SMTP_HOST and MAIL_FROM in .env),
    # which no toggle can turn on. The value is kept, as under `needs`.
    needs_mail: bool = False
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
        # Cases ----------------------------------------------------------------
        Definition(
            key="folder_management",
            page=CASES,
            name="Folder management",
            kind=TOGGLE,
            default=False,
            what_it_does=(
                "Users may keep Recordings in Cases past sign-out. The app "
                "says cases to users, never folders."
            ),
            when_changed=(
                "At once. On: the Cases pages appear and paused Retention "
                "clocks resume. Off: every Case is hidden from everyone, "
                "Admins included, and kept; its Retention clock pauses; "
                "nothing is deleted."
            ),
        ),
        Definition(
            key="live_recording",
            page=FEATURES,
            name="Live recording",
            kind=TOGGLE,
            default=False,
            needs="folder_management",
            what_it_does=(
                "People may make a recording in the browser on an office "
                "computer, from the microphone, into a case; it is transcribed "
                "at the front of the queue when it ends."
            ),
            when_changed=(
                "At once. Off hides Record everywhere; a recording in "
                "progress finishes."
            ),
        ),
        Definition(
            key="dictation",
            page=FEATURES,
            name="Record now",
            kind=TOGGLE,
            default=False,
            needs="live_recording",
            what_it_does=(
                "People may record from the Start page, choosing a dictation, a "
                "meeting in the room, or a call on the computer: a recording "
                "kept on its own under Recorded here on My recordings, with a "
                "memo or summary one click away, sent to colleagues one at a time."
            ),
            when_changed=(
                "At once. Off hides Record now and Recorded here; every "
                "recording made there is kept."
            ),
        ),
        Definition(
            key="live_longest_minutes",
            page=LIMITS,
            name="Longest live recording",
            kind=NUMBER,
            default=180,
            least=10,
            most=480,
            unit="minutes",
            needs="live_recording",
            what_it_does="The Record page stops a recording at this length.",
            when_changed="The next recording.",
        ),
        Definition(
            key="sharing",
            page=CASES,
            name="Sharing",
            kind=TOGGLE,
            default=False,
            needs="folder_management",
            what_it_does="Owners may share Cases with named colleagues.",
            when_changed=(
                "At once. Off hides the Share button, the Shared with panel, "
                "and shared Cases from Collaborators' lists while keeping "
                "every Share; On restores them."
            ),
        ),
        # The Retention policy's three, greyed while Folder management is off.
        # One office-wide number each: there is no per-Case value anywhere.
        Definition(
            key="retention_days",
            page=CASES,
            name="Retention period",
            kind=NUMBER,
            default=30,
            least=7,
            most=3650,
            unit="days",
            needs="folder_management",
            what_it_does=(
                "The days without activity after which the Retention policy "
                "moves a Case to the Recycle bin. Any use of a Case starts its "
                "clock over; days while Folder management is off do not count."
            ),
            when_changed=(
                "The next sweep, at half past three. A Case already past the "
                "new number goes to the Recycle bin that night."
            ),
        ),
        Definition(
            key="warning_days",
            page=CASES,
            name="Warning before deletion",
            kind=NUMBER,
            default=7,
            least=1,
            most=30,
            unit="days",
            needs="folder_management",
            what_it_does=(
                "The days before deletion during which a Case carries the "
                "amber Retention warning and its Keep button. Always shorter "
                "than the Retention period."
            ),
            when_changed=(
                "The next page load for the amber mark; the next sweep for the "
                "Retention digest."
            ),
        ),
        Definition(
            key="recycle_bin_days",
            page=CASES,
            name="Recycle bin",
            kind=NUMBER,
            default=30,
            least=1,
            most=365,
            unit="days",
            needs="folder_management",
            what_it_does=(
                "The days a Case the clock deleted waits in the Recycle bin, "
                "restorable, before it is wiped for good."
            ),
            when_changed=(
                "The next sweep. Anything in the bin longer than the new "
                "number is wiped that night."
            ),
        ),
        Definition(
            key="recording_types",
            page=CASES,
            name="Recording types",
            kind=TEXT,
            default=SHIPPED_RECORDING_TYPES,
            lines=8,
            what_it_does=(
                "The labels a user may pick for a Recording at upload or "
                "later, one per line."
            ),
            when_changed=(
                "A type removed from the list stays on the Recordings that hold it."
            ),
        ),
        # Appearance -----------------------------------------------------------
        Definition(
            key="office_name",
            page=APPEARANCE,
            name="Office name",
            kind=TEXT,
            default="",
            lines=1,
            what_it_does=(
                "The office's name, under the logo on the sign-in page and on "
                "the cover of every Word export. Empty shows the app's name alone."
            ),
            when_changed="The next page or export.",
        ),
        # The Email page (Phase 2, Email notifications): two switches and the
        # four Notifications' wordings. Operator mail obeys .env alone.
        Definition(
            key="email_notifications",
            page=EMAIL,
            name="Email notifications",
            kind=TOGGLE,
            default=True,
            needs_mail=True,
            what_it_does=(
                "The master switch for mail to people: the Retention digest, "
                "a case shared or handed over, a batch finished."
            ),
            when_changed=(
                "At once. Off stops every mail to people; Operator mail is unaffected."
            ),
        ),
        Definition(
            key="batch_finished_emails",
            page=EMAIL,
            name="Batch finished emails",
            kind=TOGGLE,
            default=True,
            needs_mail=True,
            what_it_does=(
                "The optional mail when a batch finishes, which users ask for "
                "with a tick on the Upload page."
            ),
            when_changed="At once. Off hides the tick on the Upload page.",
        ),
        Definition(
            key="dictation_by_email",
            page=EMAIL,
            name="Dictation by email",
            kind=TOGGLE,
            default=False,
            needs_mail=True,
            what_it_does=(
                "Send to attaches a recording's memo or summary, as a Word file, "
                "and the recording itself up to the size below, to the mail that "
                "tells a colleague it is there. The one message the app sends "
                "that carries content; the recipient is always a colleague the "
                "directory knows."
            ),
            when_changed="The next Send to.",
        ),
        Definition(
            key="attachment_most_mb",
            page=EMAIL,
            name="Largest recording attached",
            kind=NUMBER,
            default=20,
            least=1,
            most=100,
            unit="MB",
            needs="dictation_by_email",
            what_it_does=(
                "With Dictation by email on, Send to attaches the recording "
                "itself as well as the memo or summary, up to this size. A "
                "larger one is left out and the mail says so; the link opens "
                "it in the app. Most relays refuse mail above 10 to 25 MB."
            ),
            when_changed="The next Send to.",
        ),
        Definition(
            key="dictation_subject",
            page=EMAIL,
            name="Recording sent: subject",
            kind=TEXT,
            lines=1,
            default="Gideon Transcribe: {by} sent you a recording",
            needs_mail=True,
            what_it_does="Placeholders: {name}, {by}, {title}, {link}.",
            when_changed="The next message.",
        ),
        Definition(
            key="dictation_body",
            page=EMAIL,
            name="Recording sent: body",
            kind=TEXT,
            lines=6,
            default=(
                "Hello {name},\n"
                "\n"
                '{by} sent you the recording "{title}". It is under Sent to you '
                "on your My recordings page.\n"
                "\n"
                "Open it: {link}\n"
            ),
            needs_mail=True,
            what_it_does=(
                "Sent at once when a recording made with Record now is sent to "
                "somebody. Placeholders: {name}, {by}, {title}, {link}. With "
                "Dictation by email on, the memo or summary is attached as a "
                "Word file."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="digest_subject",
            page=EMAIL,
            name="Retention digest: subject",
            kind=TEXT,
            lines=1,
            default="Gideon Transcribe: cases deleting soon",
            needs_mail=True,
            what_it_does=(
                "The nightly digest's subject. Placeholders: {name}, {cases}, "
                "{shared}, {dictations}, {link}."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="digest_body",
            page=EMAIL,
            name="Retention digest: body",
            kind=TEXT,
            lines=8,
            default=(
                "Hello {name},\n"
                "\n"
                "These cases delete unless someone uses them:\n"
                "{cases}\n"
                "\n"
                "{shared}\n"
                "\n"
                "{dictations}\n"
                "\n"
                "Open a case, or press Keep on the Cases page, to start its clock "
                "over: {link}\n"
            ),
            needs_mail=True,
            what_it_does=(
                "The nightly digest, one per person with a case or a dictation in "
                "its last days. {cases} is the list of their own cases, {shared} "
                "the cases shared with them, {dictations} their dictations, all "
                "built by the app; {name} and {link} as above. The footer is "
                "added by the app."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="shared_subject",
            page=EMAIL,
            name="Case shared with you: subject",
            kind=TEXT,
            lines=1,
            default='Gideon Transcribe: {owner} shared the case "{case}" with you',
            needs_mail=True,
            what_it_does="Placeholders: {name}, {owner}, {case}, {link}.",
            when_changed="The next message.",
        ),
        Definition(
            key="shared_body",
            page=EMAIL,
            name="Case shared with you: body",
            kind=TEXT,
            lines=6,
            default=(
                "Hello {name},\n"
                "\n"
                '{owner} shared the case "{case}" with you. You can do everything '
                "in it except share, rename, transfer, or delete it; recordings you "
                "add count against {owner}'s space.\n"
                "\n"
                "Open it: {link}\n"
            ),
            needs_mail=True,
            what_it_does=(
                "Sent at once when a case is shared with somebody. Placeholders: "
                "{name}, {owner}, {case}, {link}."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="handed_subject",
            page=EMAIL,
            name="Case handed to you: subject",
            kind=TEXT,
            lines=1,
            default='Gideon Transcribe: the case "{case}" is now yours',
            needs_mail=True,
            what_it_does="Placeholders: {name}, {by}, {case}, {days}, {link}.",
            when_changed="The next message.",
        ),
        Definition(
            key="handed_body",
            page=EMAIL,
            name="Case handed to you: body",
            kind=TEXT,
            lines=6,
            default=(
                "Hello {name},\n"
                "\n"
                '{by} handed you the case "{case}". It deletes in {days} days '
                "unless used, so open it to start its clock over.\n"
                "\n"
                "Open it: {link}\n"
            ),
            needs_mail=True,
            what_it_does=(
                "Sent at once on Transfer or Reassign, to the new owner. "
                "Placeholders: {name}, {by}, {case}, {days}, {link}."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="batch_subject",
            page=EMAIL,
            name="Batch finished: subject",
            kind=TEXT,
            lines=1,
            default=(
                "Gideon Transcribe: your batch has finished ({done} done, "
                "{failed} failed)"
            ),
            needs_mail=True,
            what_it_does=(
                "Placeholders: {name}, {count}, {done}, {failed}, {failed_list}, "
                "{where}, {time}, {link}."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="batch_body",
            page=EMAIL,
            name="Batch finished: body",
            kind=TEXT,
            lines=9,
            default=(
                "Hello {name},\n"
                "\n"
                "Your batch of {count} recordings finished at {time}: {done} "
                "transcribed, {failed} failed.\n"
                "\n"
                "{failed_list}\n"
                "\n"
                "The recordings are {where}.\n"
                "\n"
                "Open them: {link}\n"
            ),
            needs_mail=True,
            what_it_does=(
                "Sent when the last recording in a batch has ended, to a person "
                "who ticked the box. {failed_list} is one line per failed "
                "recording, built by the app; {where} is where the recordings "
                "are; the rest as above."
            ),
            when_changed="The next message.",
        ),
        Definition(
            key="logo_on_exports",
            page=APPEARANCE,
            name="Logo on Word exports",
            kind=TOGGLE,
            default=False,
            what_it_does=(
                "Puts the office logo, uploaded on this page, at the head of every "
                "Word export's cover: transcripts, summaries, chats and case chats."
            ),
            when_changed="The next export. Nothing already exported changes.",
        ),
        Definition(
            key="speaker_roles",
            page=CASES,
            name="Speaker roles",
            kind=TEXT,
            default="Defendant\nWitness\nVictim\nOfficer\nAttorney\nInterpreter\nInterviewer\nCaller",
            lines=8,
            needs="folder_management",
            what_it_does=(
                "The Roles a Person in a case may be given, one per line. Suggest "
                "names offers roles from this list when nobody is named."
            ),
            when_changed=(
                "The next Role pick; a Role removed from the list stays on the "
                "People that hold it."
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
            key="case_chat_hours",
            page=LIMITS,
            name="Case chat: most hours of talk per question",
            kind=NUMBER,
            default=120,
            least=6,
            most=600,
            unit="hours",
            what_it_does=(
                "The most talk one Case Chat question may read, as the summed "
                "length of the recordings it would read. A question over more "
                "refuses and says so."
            ),
            when_changed="The next question.",
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
                "The next Run. The service swaps models once, in under a minute."
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
            what_it_does=("For an office whose Recordings are mostly not in English."),
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
            when_changed=("The next media job. It is recorded in every Provenance."),
        ),
        # AI assistant ---------------------------------------------------------
        Definition(
            key="assistant_available",
            page=ASSISTANT,
            name="AI assistant",
            kind=TOGGLE,
            default=False,
            what_it_does=("The master switch. It starts Off until an engine answers."),
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
            key="chat_starters",
            page=TEMPLATES,
            name="Chat starter questions",
            kind=TEXT,
            default="",
            lines=5,
            what_it_does=(
                "Questions an empty Chat in the viewer offers as one-click chips, "
                "one per line. Empty means none are offered."
            ),
            when_changed="The next Chat opened; applies at once, outside the tray.",
        ),
        Definition(
            key="case_chat_starters",
            page=TEMPLATES,
            name="Case chat starter questions",
            kind=TEXT,
            default="",
            lines=5,
            what_it_does=(
                "Questions an empty Case Chat offers as one-click chips, one per "
                "line. Empty means none are offered."
            ),
            when_changed=(
                "The next Case Chat opened; applies at once, outside the tray."
            ),
        ),
        Definition(
            key="chat_across_cases",
            page=ASSISTANT,
            name="Chat across cases",
            kind=TOGGLE,
            default=True,
            needs="assistant_available",
            what_it_does=(
                "The Case Chat: a Chat tab on every Case page that answers from "
                "every transcript in the case. Under the master switch and "
                "independent of the Chat toggle above."
            ),
            when_changed=(
                "Off hides the Chat tab on every Case page and keeps the Chats."
            ),
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
            # Off until an office has seen it do well on its own recordings: a
            # small engine does this badly (docs/research/speaker-suggestions.md).
            default=False,
            what_it_does=(
                "Suggesting who each Speaker is, from the talk. Off by default: a "
                "small engine does this badly; try it and judge before leaving it on."
            ),
            when_changed="Off hides Suggest names.",
        ),
        Definition(
            key="suggestion_method",
            page=ASSISTANT,
            name="Speaker suggestion method",
            kind=CHOICE,
            default="evidence",
            choices=("evidence",),
            needs="suggestions_available",
            what_it_does=(
                'How Suggest names works out who is speaking. "evidence": the app '
                "finds self-introductions and forms of address in the transcript "
                "first, hands them to the model with the case's People and the "
                "Speaker roles, and keeps a name only when the text backs it. New "
                "methods join this list as they are built; the toggle above turns "
                "the feature off whatever the method."
            ),
            when_changed="The next Suggest names.",
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
        # The budgets ----------------------------------------------------------
        #
        # The AI assistant chapter's starting values, held in code until v1.37.0
        # and settings since, at the maintainer's decision: an office tunes them
        # to its engine and puts them back with Reset to default. The defaults
        # are the code values (core/assistant.py, core/prompts.py,
        # core/case_chat.py keep the same figures as their own constants, and a
        # test holds the pairs together).
        Definition(
            key="chat_answer_tokens",
            page=ASSISTANT,
            name="Chat answer cap",
            kind=NUMBER,
            default=1500,
            least=200,
            most=16000,
            unit="tokens",
            what_it_does=(
                "The most a Chat answer may run to: 1,500 tokens is about a "
                "thousand words. An answer that hits the cap is shown as it is, "
                'with "The answer was cut short."'
            ),
            when_changed="The next question.",
        ),
        Definition(
            key="summary_short_tokens",
            page=ASSISTANT,
            name="Summary answer cap, Short",
            kind=NUMBER,
            default=600,
            least=100,
            most=16000,
            unit="tokens",
            what_it_does="The most a Short Summary may run to.",
            when_changed="The next Summary.",
        ),
        Definition(
            key="summary_standard_tokens",
            page=ASSISTANT,
            name="Summary answer cap, Standard",
            kind=NUMBER,
            default=1200,
            least=100,
            most=16000,
            unit="tokens",
            what_it_does="The most a Standard Summary may run to.",
            when_changed="The next Summary.",
        ),
        Definition(
            key="summary_detailed_tokens",
            page=ASSISTANT,
            name="Summary answer cap, Detailed",
            kind=NUMBER,
            default=2500,
            least=100,
            most=16000,
            unit="tokens",
            what_it_does="The most a Detailed Summary may run to.",
            when_changed="The next Summary.",
        ),
        Definition(
            key="suggestions_answer_tokens",
            page=ASSISTANT,
            name="Speaker suggestions answer cap",
            kind=NUMBER,
            default=1500,
            least=200,
            most=16000,
            unit="tokens",
            what_it_does=(
                "The most the suggestions answer, a small JSON list, may run to."
            ),
            when_changed="The next Suggest names.",
        ),
        Definition(
            key="thinking_allowance_tokens",
            page=ASSISTANT,
            name="Thinking allowance",
            kind=NUMBER,
            default=8000,
            least=500,
            most=64000,
            unit="tokens",
            needs="assistant_thinks",
            what_it_does=(
                "Added to every answer cap while the model may think, since its "
                "thinking is billed against the same budget. A large model that "
                "spends the whole allowance thinking never begins the answer, and "
                "the page says so; raise this, or turn thinking off."
            ),
            when_changed="The next call.",
        ),
        Definition(
            key="chat_time_seconds",
            page=ASSISTANT,
            name="Chat time limit",
            kind=NUMBER,
            default=120,
            least=30,
            most=3600,
            unit="seconds",
            what_it_does=(
                "How long one Chat call may take, and each Reading of a Case Chat. "
                "Doubled while the model may think."
            ),
            when_changed=(
                'The next question. On timeout: "The AI assistant took too long."'
            ),
        ),
        Definition(
            key="summary_time_seconds",
            page=ASSISTANT,
            name="Summary time limit",
            kind=NUMBER,
            default=300,
            least=30,
            most=3600,
            unit="seconds",
            what_it_does=(
                "How long one Summary call may take. Doubled while the model may think."
            ),
            when_changed="The next Summary.",
        ),
        Definition(
            key="suggestions_time_seconds",
            page=ASSISTANT,
            name="Speaker suggestions time limit",
            kind=NUMBER,
            default=180,
            least=30,
            most=3600,
            unit="seconds",
            what_it_does=(
                "How long one Suggest names call may take. Doubled while the model "
                "may think."
            ),
            when_changed="The next Suggest names.",
        ),
        Definition(
            key="chat_history_tokens",
            page=ASSISTANT,
            name="Chat history",
            kind=NUMBER,
            default=16000,
            least=0,
            most=200000,
            unit="tokens",
            what_it_does=(
                "How much of the same Chat's earlier questions and answers goes "
                "back to the model with each question, oldest dropped first. The "
                "Transcript itself is never dropped. Zero sends none."
            ),
            when_changed="The next question.",
        ),
        Definition(
            key="engine_window_tokens",
            page=ASSISTANT,
            name="Engine window",
            kind=NUMBER,
            default=131072,
            least=4096,
            most=4000000,
            unit="tokens",
            what_it_does=(
                "The most the engine can read at once, by its own setting "
                "(vLLM's max model length). The app estimates each prompt at four "
                "characters a token with a ten percent margin and refuses a call "
                "that would not fit, saying the transcript is too long. The "
                "default is the Local engine's; enter the shared engine's if it "
                "is larger, and no more than it truly offers."
            ),
            when_changed="The next call.",
        ),
        Definition(
            key="reading_tokens",
            page=ASSISTANT,
            name="Reading size",
            kind=NUMBER,
            default=100000,
            least=2000,
            most=2000000,
            unit="tokens",
            what_it_does=(
                "How much rendered transcript one Reading of a Case Chat holds, "
                "whole transcripts packed together up to this much: 100,000 is "
                "about six hours of talk. A case over one Reading is read in "
                "parts and the answers combined. Kept well under the engine "
                "window on purpose: models use the middle of a long context badly."
            ),
            when_changed="The next Case Chat question.",
        ),
        Definition(
            key="readings_at_once",
            page=ASSISTANT,
            name="Readings at once",
            kind=NUMBER,
            default=2,
            least=1,
            most=4,
            unit="",
            what_it_does=(
                "How many Readings of one Case Chat question run at the same "
                "time, inside the assistant's four lanes, so one case never "
                "fills them."
            ),
            when_changed="The next Case Chat question.",
        ),
        Definition(
            key="case_chat_part_tokens",
            page=ASSISTANT,
            name="Case chat answer cap, each part",
            kind=NUMBER,
            default=1500,
            least=200,
            most=16000,
            unit="tokens",
            what_it_does="The most each Reading's answer may run to.",
            when_changed="The next Case Chat question.",
        ),
        Definition(
            key="case_chat_combined_tokens",
            page=ASSISTANT,
            name="Case chat answer cap, combined",
            kind=NUMBER,
            default=2000,
            least=200,
            most=16000,
            unit="tokens",
            what_it_does=(
                "The most the combined answer to a question read in parts may run to."
            ),
            when_changed="The next Case Chat question.",
        ),
        Definition(
            key="case_chat_question_minutes",
            page=ASSISTANT,
            name="Case chat question time limit",
            kind=NUMBER,
            default=15,
            least=2,
            most=120,
            unit="minutes",
            what_it_does=(
                "How long a whole Case Chat question may take across its Readings, "
                "on top of each call's own Chat time limit. Doubled while the "
                "model may think."
            ),
            when_changed="The next Case Chat question.",
        ),
        # Moments (Phase 4) ----------------------------------------------------
        Definition(
            key="moments_available",
            page=ASSISTANT,
            name="Moments",
            kind=TOGGLE,
            default=False,
            what_it_does=(
                "Describing what the camera shows at a chosen time of a video "
                "recording, on request, from a short clip and the words spoken in "
                "it. Off by default: it needs an engine that takes video, and an "
                "office tries it and judges before leaving it on."
            ),
            when_changed=(
                "Off hides the Moments tab and the camera buttons; existing "
                "Moments are hidden, not deleted."
            ),
        ),
        Definition(
            key="moments_in_answers",
            page=ASSISTANT,
            name="Moments in answers",
            kind=TOGGLE,
            default=True,
            needs="moments_available",
            what_it_does=(
                "Hand a recording's Moments to Summary and Chat as labelled camera "
                "lines, so a summary can say what was seen as well as what was said."
            ),
            when_changed="The next Summary or question.",
        ),
        Definition(
            key="moments_answer_tokens",
            page=ASSISTANT,
            name="Moment answer cap",
            kind=NUMBER,
            default=250,
            least=100,
            most=4000,
            unit="tokens",
            needs="moments_available",
            what_it_does="The most a Moment's description may run to: a few sentences.",
            when_changed="The next Moment.",
        ),
        Definition(
            key="moments_time_seconds",
            page=ASSISTANT,
            name="Moment time limit",
            kind=NUMBER,
            default=120,
            least=30,
            most=3600,
            unit="seconds",
            needs="moments_available",
            what_it_does=(
                "How long one Moment's call may take, the cut of the clip included. "
                "A Moment never lets the model think, so this is never doubled."
            ),
            when_changed="The next Moment.",
        ),
        Definition(
            key="moment_span_seconds",
            page=ASSISTANT,
            name="Moment clip length",
            kind=NUMBER,
            default=10,
            least=4,
            most=30,
            unit="seconds",
            needs="moments_available",
            what_it_does=(
                "How much of the recording the engine is shown for one Moment: half "
                "before the chosen time and half after."
            ),
            when_changed="The next Moment.",
        ),
        Definition(
            key="moment_frames_per_second",
            page=ASSISTANT,
            name="Moment frames a second",
            kind=NUMBER,
            default=2,
            least=1,
            most=4,
            unit="a second",
            needs="moments_available",
            what_it_does=(
                "How many frames of each second the clip keeps. Two catches most "
                "movement; more costs the engine more for little gain."
            ),
            when_changed="The next Moment.",
        ),
        Definition(
            key="moment_frame_height",
            page=ASSISTANT,
            name="Moment frame height",
            kind=NUMBER,
            default=360,
            least=180,
            most=720,
            unit="pixels",
            needs="moments_available",
            what_it_does=(
                "The height the clip's frames are scaled to before the engine sees "
                "them; a frame is never scaled up. Each 640 by 360 frame costs the "
                "engine about 150 tokens, so a ten-second clip at two frames a "
                "second is about 3,000."
            ),
            when_changed="The next Moment.",
        ),
        Definition(
            key="moment_style",
            page=ASSISTANT,
            name="Moment style",
            kind=CHOICE,
            default="brief",
            choices=("brief", "full"),
            needs="moments_available",
            what_it_does=(
                '"brief": one to three short sentences leading with the thing '
                'pointed at. "full": two to five sentences with the setting and '
                "the seconds in the clip. The Moment template on the Templates "
                "page holds the rules both follow."
            ),
            when_changed="The next Moment.",
        ),
        Definition(
            key="moment_question_height",
            page=ASSISTANT,
            name="Look closer frame height",
            kind=NUMBER,
            default=720,
            least=360,
            most=1080,
            unit="pixels",
            needs="moments_available",
            what_it_does=(
                "A question about a moment is answered from a few still frames at "
                "this height rather than the small clip, so a small object on a "
                "seat can be made out; never scaled up. A 1280 by 720 frame costs "
                "the engine about 1,200 tokens."
            ),
            when_changed="The next question.",
        ),
        Definition(
            key="moment_question_frames",
            page=ASSISTANT,
            name="Look closer frames",
            kind=NUMBER,
            default=3,
            least=1,
            most=5,
            unit="frames",
            needs="moments_available",
            what_it_does=(
                "How many still frames a question is answered from, spread over "
                "about a second either side of the chosen time."
            ),
            when_changed="The next question.",
        ),
        Definition(
            key="moment_finder_transcript",
            page=ASSISTANT,
            name="Find moments from the words",
            kind=TOGGLE,
            default=True,
            needs="moments_available",
            what_it_does=(
                "Find moments reads the whole transcript once and suggests the "
                "lines where the picture would add a fact: an object named or "
                "handled, a command that implies an action, an action narrated, "
                "a pointing phrase, a sudden change; each with its reason."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_finder_media",
            page=ASSISTANT,
            name="Find moments from the picture and sound",
            kind=TOGGLE,
            default=False,
            needs="moments_available",
            what_it_does=(
                "Find moments also scans the video itself, without the engine: "
                "sharp changes of picture and stretches of raised voices or a "
                "bang become suggestions. Off by default until an office has "
                "judged it on its own footage; a scan of a long recording takes "
                "the media worker a few minutes."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_finder_most",
            page=ASSISTANT,
            name="Most suggested moments",
            kind=NUMBER,
            default=12,
            least=3,
            most=40,
            unit="",
            needs="moments_available",
            what_it_does=(
                "The most lines one Find moments may suggest from the words, the "
                "surest first; and the most from the picture and sound together."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_finder_confidence",
            page=ASSISTANT,
            name="Least sure suggestion kept",
            kind=CHOICE,
            default="medium",
            choices=("high", "medium", "low"),
            needs="moments_available",
            what_it_does=(
                "A suggestion from the words is kept only when the engine is at "
                'least this sure of it. "high" gives few and sure; "low" gives '
                "everything it saw."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_finder_tokens",
            page=ASSISTANT,
            name="Find moments answer cap",
            kind=NUMBER,
            default=1500,
            least=200,
            most=8000,
            unit="tokens",
            needs="moments_available",
            what_it_does="The most the finder's list, a small JSON, may run to.",
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_finder_time_seconds",
            page=ASSISTANT,
            name="Find moments time limit",
            kind=NUMBER,
            default=180,
            least=30,
            most=3600,
            unit="seconds",
            needs="moments_available",
            what_it_does=(
                "How long the finder's one read of the transcript may take. "
                "Doubled while the model may think."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_scene_threshold",
            page=ASSISTANT,
            name="Picture change threshold",
            kind=NUMBER,
            default=40,
            least=10,
            most=90,
            unit="percent",
            needs="moment_finder_media",
            what_it_does=(
                "How much of the picture must change between one frame and the "
                "next for the scan to call it a moment. Lower finds more; a "
                "body camera that swings about needs a higher figure."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_loud_db",
            page=ASSISTANT,
            name="Loudness rise",
            kind=NUMBER,
            default=12,
            least=3,
            most=30,
            unit="dB",
            needs="moment_finder_media",
            what_it_does=(
                "How far above the recording's usual level a second must be for "
                "the scan to call it raised voices or a bang."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_media_gap_seconds",
            page=ASSISTANT,
            name="Gap between scanned moments",
            kind=NUMBER,
            default=15,
            least=5,
            most=120,
            unit="seconds",
            needs="moment_finder_media",
            what_it_does=(
                "Two moments the scan finds closer together than this become "
                "one, so a struggle is one suggestion and not twenty."
            ),
            when_changed="The next Find moments.",
        ),
        Definition(
            key="moment_interval_seconds",
            page=ASSISTANT,
            name="Describe at intervals: every",
            kind=NUMBER,
            default=60,
            least=20,
            most=600,
            unit="seconds",
            needs="moments_available",
            what_it_does=(
                "Describe the whole recording makes a Moment this far apart, from "
                "half an interval in, skipping any time already described. Each "
                "is one engine call of a few thousand tokens."
            ),
            when_changed="The next Describe the whole recording.",
        ),
        Definition(
            key="moment_interval_most",
            page=ASSISTANT,
            name="Describe at intervals: at most",
            kind=NUMBER,
            default=40,
            least=5,
            most=200,
            unit="moments",
            needs="moments_available",
            what_it_does=(
                "The most Moments one Describe the whole recording makes; a long "
                "recording gets them spread evenly rather than from the start."
            ),
            when_changed="The next Describe the whole recording.",
        ),
        Definition(
            key="summary_describes_first",
            page=ASSISTANT,
            name="Summaries describe the moments first",
            kind=TOGGLE,
            default=True,
            needs="moments_available",
            what_it_does=(
                "Whether Summarise this video starts with its tick, Look at the "
                "picture first, ticked, while fewer moments are described than "
                "Enough moments for a video summary. Ticked, the summary describes "
                "the recording at intervals before it writes, so it can say what "
                "was seen as well as what was said; the cost is one call per "
                "interval."
            ),
            when_changed="The next summary dialog opened.",
        ),
        Definition(
            key="summary_moments_enough",
            page=ASSISTANT,
            name="Enough moments for a video summary",
            kind=NUMBER,
            default=10,
            least=0,
            most=200,
            unit="moments",
            needs="moments_available",
            what_it_does=(
                "When at least this many moments are described already, Look at "
                "the picture first starts unticked and the summary draws on what "
                "there is. 0 means it always starts ticked."
            ),
            when_changed="The next summary dialog opened.",
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
                "What {model} prints in the AI notice. Empty means the served name."
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
            when_changed=("The next sweep. Shortening it removes rows the same night."),
        ),
    ]


DEFINITIONS = {one.key: one for one in _rows()}


def lines_of(key: str) -> list[str]:
    """A list setting's lines, trimmed, blanks dropped."""
    return [line.strip() for line in str(get(key) or "").splitlines() if line.strip()]


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

    text = str(value)
    # A Notification's template may use its kind's placeholders and no
    # other: the Email chapter's rule, kept here so every way in obeys it.
    from core import mail

    template_of = mail.template_kind_of(key)
    if template_of:
        why = mail.check_template(template_of, text)
        if why:
            raise ValueError(f"{known.name}: {why}")
    return text


def greyed_because(known: Definition) -> str:
    """Why a setting's control is closed on the panel, or "" when it is open.

    Under a toggle that is off, or while mail is not configured. The value is
    kept either way, and a closed control is never read back as a change.
    """
    if known.needs and not get(known.needs):
        return f"Greyed while {definition(known.needs).name} is off; the value is kept."
    if known.needs_mail:
        from core import mail

        if not mail.configured():
            return (
                "Greyed while mail is not configured (SMTP_HOST and MAIL_FROM "
                "in .env); the value is kept."
            )
    return ""


def check_together(pending: dict) -> None:
    """The one rule that spans two settings, checked before a tray is applied.

    The warning window must be shorter than the Retention period, or a Case
    would be warned from the day it was made. Each value is the pending one
    when the tray holds it and the stored one when it does not, so lowering
    the period and the warning together is judged as the pair it is.
    """

    def value_of(key: str) -> int:
        return int(pending.get(key, get(key)))

    if value_of("warning_days") >= value_of("retention_days"):
        raise ValueError(
            "Warning before deletion must be shorter than the Retention period: "
            f"{value_of('warning_days')} days is not shorter than "
            f"{value_of('retention_days')}."
        )


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

    if key == "folder_management":
        # The days nobody could reach a Case are recorded as they pass,
        # because they cannot be worked out afterwards.
        from core.cases import note_the_toggle

        note_the_toggle(bool(wanted))


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


# The AI assistant's budgets, read at every call so a change applies to the
# next one. Each default is the chapter's starting value, which the modules
# that used to hold them keep as their own constants.


def chat_answer_cap() -> int:
    return get("chat_answer_tokens")


def summary_answer_cap(length: str) -> int:
    key = {
        "short": "summary_short_tokens",
        "standard": "summary_standard_tokens",
        "detailed": "summary_detailed_tokens",
    }.get(length, "summary_standard_tokens")
    return get(key)


def suggestions_answer_cap() -> int:
    return get("suggestions_answer_tokens")


def thinking_allowance() -> int:
    return get("thinking_allowance_tokens")


def time_limit_seconds(feature: str) -> int:
    key = {
        "chat_turn": "chat_time_seconds",
        "summary": "summary_time_seconds",
        "speaker_suggestions": "suggestions_time_seconds",
        "moment": "moments_time_seconds",
        "moment_finder": "moment_finder_time_seconds",
    }[feature]
    return get(key)


def chat_history_tokens() -> int:
    return get("chat_history_tokens")


def engine_window_tokens() -> int:
    return get("engine_window_tokens")


def reading_tokens() -> int:
    return get("reading_tokens")


def readings_at_once() -> int:
    return get("readings_at_once")


def case_chat_part_cap() -> int:
    return get("case_chat_part_tokens")


def case_chat_combined_cap() -> int:
    return get("case_chat_combined_tokens")


def case_chat_question_seconds() -> int:
    return get("case_chat_question_minutes") * 60


# The Moments' shape (Phase 4).


def moments_answer_cap() -> int:
    return get("moments_answer_tokens")


def moment_span_seconds() -> int:
    return get("moment_span_seconds")


def moment_frames_per_second() -> int:
    return get("moment_frames_per_second")


def moment_frame_height() -> int:
    return get("moment_frame_height")


def moment_style() -> str:
    return str(get("moment_style") or "brief")


def moment_question_height() -> int:
    return get("moment_question_height")


def moment_question_frames() -> int:
    return get("moment_question_frames")


def moment_finder_most() -> int:
    return get("moment_finder_most")


def moment_finder_confidence() -> str:
    return str(get("moment_finder_confidence") or "medium")


def moment_finder_cap() -> int:
    return get("moment_finder_tokens")


def moment_scene_threshold() -> float:
    return get("moment_scene_threshold") / 100.0


def moment_loud_db() -> float:
    return float(get("moment_loud_db"))


def moment_media_gap_seconds() -> float:
    return float(get("moment_media_gap_seconds"))


def moment_interval_seconds() -> float:
    return float(get("moment_interval_seconds"))


def moment_interval_most() -> int:
    return get("moment_interval_most")


def summary_moments_enough() -> int:
    return get("summary_moments_enough")
