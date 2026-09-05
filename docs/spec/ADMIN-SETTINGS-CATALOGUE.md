# Admin settings catalogue

Every setting the panel exposes, in both phases, grouped as the panel's pages group them, with the Phase column saying when a row arrives (a Phase 2 row is absent from the Phase 1 build, not greyed). Type includes the range; "When changed" says when a change takes effect and what it does to what already exists.

## Features

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Diarization available | On or Off | On | 1 | Users may separate a Recording into Speakers, with a speaker-count hint. | Off hides the Diarization choice on the Upload page; Recordings already processed keep their Speakers; Queued Jobs run as submitted. |
| Translation available | On or Off | On | 1 | Users may ask for "Translate to English". | Off hides the choice; a Recording holding more than one language is then transcribed in its winning language with a warning, whatever the mixed-language setting says. |
| Clips available | On or Off | On | 1 | Users may save a chosen span of a Recording as a playable file, a Clip. | Off hides New Clip and the Clips sheet, hides the Clips page in the navigation, and drops Clips from the sign-out dialog and "Download everything"; Clip files already made stay until their Recording goes. In Phase 2, Off hides the Case page's Clips tab too. |

## Limits

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Largest file | 1 to 100 GB | 10 GB | 1 | The biggest single upload accepted; larger is refused with `too_large`. | The next upload. |
| Longest Recording | 1 to 8 hours | 6 hours | 1 | Longer Recordings are refused when the file is inspected, with `too_long`; the WhisperX service refuses over 8 hours whatever is set. | The next upload. |
| Longest Clip | minutes, 1 to the "Longest Recording" value | 30 minutes | 1 | Users may save a Clip up to this long. | The next Clip saved. |
| Files per Batch | 1 to 200 | 25 | 1 | The only size rule for a Batch; 1 makes every Batch a single file, so there is no separate bulk-upload switch. | The next Batch. |
| Default Workspace quota per user | 1 to 5,000 GB | 50 GB | 1 | Everything on disk for a user's Recordings counts; the per-user override on the Users page wins. In Phase 2 the description says it covers the Workspace and every Case the user owns together; there is no separate Case quota. | The next upload; nothing already stored is touched. |
| Minimum free disk space | 10 to 10,000 GB | 200 GB | 1 | Uploads are refused below it with `disk_full`; nothing is discarded early. | At once; the Status page turns amber under twice this figure and red under it. |
| Case chat: most hours of talk per question | hours, 6 to 600 | 120 hours | 2 | The most talk one Case Chat question may read; a question over more talk refuses with `llm_case_too_large`. | The next question. |

The idle timeout is on the Sign-in and directory page; the Limits page carries a cross-reference to it, because it is also the Workspace's lifetime.

## Transcription defaults

What every Upload page starts with.

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Model | large-v3-turbo or large-v3 | large-v3-turbo | 1 | The model every Run asks for; users cannot change it, and the Upload page does not show it as a field. | The next Run; the service swaps once, in under a minute. |
| Diarization ticked by default | On or Off | On | 1 | The Upload page's "Diarize" checkbox starts ticked. | The next Upload page opened. |
| Speaker-count hint default | Let the app decide, Exactly N, Between N and M | Let the app decide | 1 | What the hint starts as. | The next Upload page opened. |
| "Translate to English" ticked by default | On or Off | Off | 1 | For an office whose Recordings are mostly not in English. | The next Upload page opened. |
| Translate mixed-language Recordings to English automatically | On or Off | On | 1 | A Recording holding more than one language is translated wholesale to English. | Off: such a Recording is transcribed in its winning language with a warning. The next Run. |
| Office Vocabulary | text, one name or term per line | empty | 1 | Sent with every Run ahead of the Batch's own Vocabulary; the WhisperX service's prompt is short (223 tokens), so a long list is cut from the end and the Batch's list wins. Sent silently; the Upload page's Vocabulary help says "office names are added automatically". | The next Run. The audit row says only that it changed. |
| Preprocessing profile | Standard or Off (Phone only if the benchmark gate admits it) | Standard | 1 | The audio clean-up before recognition. | The next media job; recorded in every Provenance. |

## AI assistant

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| AI assistant | On or Off | Off | 1 | The master switch; starts Off until an engine answers. | Off hides Summary, Chat, and Suggest names everywhere; existing Summaries and Chats are hidden, not deleted. |
| Chat; Summary | On or Off, one each | On | 1 | One feature each, under the master switch. | Off hides that feature; existing items hidden, not deleted. |
| Speaker suggestions | On or Off | Off | 1 | Suggesting who each Speaker is, from the talk. Off by default since v1.10.6: a small engine does this badly (`docs/research/speaker-suggestions.md`); an office tries it and judges before leaving it on. | Off hides Suggest names; existing suggestions hidden, not deleted. |
| Speaker suggestion method | a choice | evidence | 1 | How Suggest names works out who is speaking. Since v1.11.0 the one method is "evidence": the app finds self-introductions ("this is Detective Ruiz") and forms of address ("Thanks, Maria") in the Transcript first, hands them to the engine with the Case's People and the Speaker roles, and keeps a name only when the text backs it; a role (Interviewer, Caller) needs no evidence. New methods join this list as they are built (`docs/research/speaker-suggestions.md`); the Speaker suggestions switch above turns the feature off whatever the method. Greyed while Speaker suggestions is Off. | The next Suggest names. |
| Chat across cases | On or Off | On | 2 | The Case Chat: a Chat tab on every Case page. Under the master switch and independent of the Chat toggle above. | Off hides the Chat tab on every Case page and keeps the Chats. |
| Let the model think before answering | On or Off | Off | 1 | Slower, sometimes better. | On doubles the time limits (Chat 4 min, Summary 10 min, suggestions 6 min). The next call. |
| Engine address | text, with Test connection | `http://vllm:8000/v1` (the Local engine's) | 1 | The engine's base URL; Test connection lists the models and runs one tiny completion. | The next call. |
| Model name | text | `local-engine` (the Local engine's) | 1 | The served name the engine expects; an office on a Shared engine enters that engine's served name here. | The next call. |
| Model display name | text | empty | 1 | What `{model}` prints in the AI notice; empty means the served name. | The next Summary or Chat shown or exported. |
| Token | read-only | set in `.env` (`LLM_API_TOKEN_FILE`) | 1 | Shown as set or missing, never editable here. | Change the file on the server and restart. |
| Ground rules; Chat; Speaker suggestions | prompt templates: plain text, Reset to default, a version that rises on every save | the AI assistant chapter's wordings, version 1 | 1 | The instructions the app builds on; the app adds the Transcript, the user's choices, and the answer format. | The next call; applies at once, outside the tray. |
| Case chat | prompt template: plain text, Reset to default, a version that rises on every save | the Case Chat chapter's wording, version 1 | 2 | The instructions the app builds a Case Chat on. | The next call; applies at once, outside the tray. |
| Summary templates | a list: name, one-line description, instruction text, Enabled, Default (exactly one among the Enabled), Add template; "Standard summary" built in, editable, not deletable | Standard summary | 1 | The shapes a Summary can take; users choose only when two or more are Enabled. | The next Summary; applies at once, outside the tray. |

## Notices

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Transcription notice | text with `{model}` | "Automatic transcription by Whisper {model}. Corrections made by staff are marked. This is not a certified transcript." | 1 | Printed on every export of a Transcript that was not translated. | The next export. |
| Translation notice | text with `{language}` and `{model}` | "Machine translation to English from {language} by Whisper {model}. The original-language text was not kept. This is not a certified translation." | 1 | Printed on every export of a translated Transcript; never on Captions. | The next export. |
| AI notice | text with `{model}` and `{date}` | "AI-generated and unverified. Check against the recording before relying on it. Written by {model} on {date}." | 1 | Shown at the top of every Summary and Chat and printed on their exports. | The next Summary or Chat shown or exported. |
| Sign-in page notice | text | empty | 1 | A short text under the sign-in form, for an authorised-use line or a support line; empty hides it. | The next sign-in page shown. |

An export carries one notice, never both. The default wordings, for copying exactly:

```
Automatic transcription by Whisper {model}. Corrections made by staff are marked. This is not a certified transcript.
```

```
Machine translation to English from {language} by Whisper {model}. The original-language text was not kept. This is not a certified translation.
```

```
AI-generated and unverified. Check against the recording before relying on it. Written by {model} on {date}.
```

## Sign-in and directory

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Directory connection | read-only from `.env` (`LDAP_ENABLED`, `LDAP_SERVER_URI`, `LDAP_CA_FILE`, `LDAP_BIND_USER`, `LDAP_BIND_PASSWORD_FILE`, `LDAP_SEARCH_BASE`, `LDAP_SIGNIN_GROUP`, `LDAP_ADMIN_GROUP`), with Test directory connection | - | 1 | Shown for checking; the bind password shown as set or missing. Test directory connection runs the four checks the Admin panel chapter lists. | Change the file on the server and restart. |
| Idle timeout | 1 to 24 hours | 8 hours | 1 | A Login session ends after this long without activity. The description says it is also the Workspace's lifetime ("recordings and transcripts are removed when a session ends"); the grace period after a session's last Job equals it. | The next request of every open session; the 15-minute warning stands. |
| Directory check time | time of day, with Check directory now and the last run's result | 03:00 | 1 | The nightly comparison of accounts against the directory, office time. | The next night. |
| Local admins | an action, Create Local admin (username, display name, password; in Phase 2 an Email address too), not a setting; the last one cannot be deleted | `transcribe-admin`, created by the install | 1 | Accounts kept inside the app for when the directory is down; managed on the Users page. | At once. |

## Audit log

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Audit log retention | 1 to 120 months | 3 months | 1 | Rows older than this are removed by the daily sweep, which is itself recorded. | The next sweep; shortening it removes rows the same night. |

## Cases (Phase 2)

The Cases page of the rail, absent from the Phase 1 build. Sharing, Retention period, Warning before deletion, Recycle bin, and Speaker roles are greyed while Folder management is Off.

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Folder management | On or Off | Off | 2 | Enables Cases. On: the Cases pages appear and paused Retention clocks resume. Off: every Case is hidden from everyone, Admins included, and kept; its Retention clock pauses; nothing is deleted. | At once, through the tray like every other setting, the note optional; the tray row shows the counts ("Hides 14 cases, 210 GB, for 6 users. Nothing is deleted."). While Off: the greyed Cases rows stay greyed; Reassign and Delete data on the Users page grey out again; the Admin's Cases page and the Recycle bin page are hidden; the Users page keeps its "in cases" figure and the Status page keeps its Cases line, followed by "Folder management has been off since <date>". |
| Sharing | On or Off | Off | 2 | Owners may share Cases with named colleagues. | At once. Off hides the Share button, the Shared with panel, and shared Cases from Collaborators' lists while keeping every Share; On restores them. |
| Retention period | whole days, 7 to 3650 | 30 days | 2 | The days without activity after which the Retention policy moves a Case to the Recycle bin. | The next sweep. A Case already past the new number goes to the Recycle bin that night. |
| Warning before deletion | whole days, 1 to 30, always shorter than the Retention period | 7 days | 2 | The days before deletion during which a Case carries the Retention warning. | The next page load for the amber mark; the next sweep for the Retention digest. |
| Recycle bin | whole days, 1 to 365 | 30 days | 2 | The days a Case the clock deleted waits in the Recycle bin before it is wiped. | The next sweep. Anything in the bin longer than the new number is wiped that night. |
| Recording types | a list, one per line | Body camera, Jail call, Interview, Phone call, Hearing, Other | 2 | The labels a user may pick for a Recording at upload or later. | A type removed from the list stays on the Recordings that hold it. |
| Speaker roles | a list, one per line | Defendant, Witness, Victim, Officer, Attorney, Interpreter, Interviewer, Caller | 2 | The Roles a Person may be given. | The next Role pick; a Role removed from the list stays on the People that hold it. |

## Email (Phase 2)

The Email page of the Settings group, absent from the Phase 1 build.

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Email notifications | On or Off | On | 2 | The master switch for mail to people. Greyed "SMTP not configured" while `SMTP_HOST` is empty. | At once. Off stops every mail to people; Operator mail is unaffected. |
| Batch finished emails | On or Off | On | 2 | The optional mail when a Batch finishes, which users ask for with a tick on the Upload page. | At once. Off hides the tick on the Upload page. |
| Notification templates (four, one per Notification kind: the Retention digest, a Case shared, a Case handed over, a Batch finished) | a Subject and a Body each, plain text with a fixed set of placeholders per kind, Reset to default; no versions | the Email notifications chapter's wordings | 2 | The text of each Notification. | Saved through the tray, so the Setting changed row holds the old and new text; Apply refuses an unknown placeholder. |
| Test message | an action outside the tray, not a setting | - | 2 | Mails the signed-in Admin and shows the relay's reply. | At once. |

## Rules that apply to every setting

- **The tray.** A setting never applies as it is edited. Edits collect in a tray fixed at the bottom of the panel and kept across pages, listed as the setting's name with its old and new value, with one optional note for the audit log (a ticket number or the reason). Apply writes every change in one step; Cancel all drops them; leaving the panel with a tray that is not empty asks whether to apply or drop. No setting asks "are you sure"; the tray is the confirmation.
- **One audit row per setting.** Each Apply writes one Setting changed row per changed setting, in the Admin category, carrying the setting's name, its old value, its new value, and the tray's note. Office Vocabulary's row says only that it changed, because Vocabulary is content. A Phase 2 Notification template's row holds its old and new text.
- **Outside the tray.** Templates apply at once: Save raises a prompt template's version, Reset to default restores its wording, and Add template, Enabled, Default, and Delete act at once on Summary templates, each writing its own audit row with the template's name and its new version or flag, never the text. So do every Users page action, the test buttons (Test directory connection, Check directory now, Test connection, Integrity check, and in Phase 2 Test message), and Cancel on the Queue page.
- **Off hides and never deletes.** Turning a feature off hides its controls and its existing items; turning it on again brings them back as they were. Queued Jobs run as submitted.
- **Phase 2 rows are absent until Phase 2.** The Phase 1 build has no Cases page, no Email page, and no greyed placeholders; the Phase 2 rows on the Limits and AI assistant pages are absent too. They arrive with Phase 2 as the Cases page and the Email page of the rail and as rows on those two pages. From Phase 2, the Cases rows marked above are greyed while Folder management is Off.
- **Office configuration.** Every setting, prompt template, and Summary template is office configuration in the database and belongs in the backup set.
- **Viewing writes nothing.** Reading the panel's pages writes no audit row.

### Not settings

Fixed in code or in `.env`, and listed at the foot of the Settings pages so nobody looks for them: one unfinished Batch per user, Admins included; one sign-in per user at a time; the keep-alive grace period equals the idle timeout; no Queue priority and no Pause; the Discard within a minute and the sweeper at 03:30; Spoken language starts Automatic with Whisper's own list; the AI assistant's sampling, answer caps, and time limits; pages poll every five seconds and the worker every three; three uploads at once per browser, and leaving the Upload page abandons them; Two-channel call detection thresholds; export layouts, file names, and formats, and the Clip caption style; the WhisperX service's own settings (batch size, VAD, limits, timeouts, alignment languages, model cache) in its environment file; the audit log's field set and the list of what is never logged; five sign-in failures then a fifteen-minute wait; the storage warning past 80% of a user's space; the backup schedule and keep rule (`.env` facts, because a host timer cannot be changed from inside a container); the directory connection, the service address and token, and the engine token (`.env` and secrets files). There is no queued-Jobs-per-user setting, no Spoken language default, no bulk-upload switch, and no Workspace retention setting.

## Sources

Admin settings catalogue and panel (its Answer; the facts it carries from the LDAP, media handling, audit log, WhisperX contract, translation, queue, Workspace lifecycle, Phase 1 LLM features, Word export, deployment topology, Case folder, GitHub distribution, and directory objects tickets; and every amendment recorded on it); the glossary.

## Amendments applied

- From the Case folder ticket, to the Cases group and the Limits group: Recording types added; the quota's Phase 2 description.
- From the sharing ticket, to the Cases group: Sharing fixed (On or Off, default Off, greyed while Folder management is Off, Off hiding and never deleting).
- From the Retention policy ticket, to the Cases group: Retention period, Warning before deletion, and Recycle bin defined with their ranges and defaults.
- From the Speaker management panel ticket, to the Cases group: Speaker roles added.
- From the toggle transitions ticket, to the Cases group: Folder management fixed, its tray counts, and what greys and hides while it is Off.
- From the backup ticket, to Not settings: the backup schedule and keep rule are `.env` facts, never settings.
- From the Clips ticket, to the Limits and Features groups: Longest Clip added; what Clips available Off hides, the Clips page, the sign-out dialog, "Download everything", and in Phase 2 the Case page's Clips tab; no caption style setting.
- From the Upload page ticket, to the Transcription defaults group: "Two-channel calls start unticked regardless" withdrawn from Diarization ticked by default; the "Diarize" label; the 80% storage warning as a build constant, not a setting.
- From the email notifications ticket, to the Email group and the Sign-in and directory group: Email notifications, Batch finished emails, the Notification templates, Test message; the Email address on Create Local admin.
- From the v1.12.0 build: Chat across cases, the Case chat template, and Case chat: most hours of talk per question ship, as the Case Chat chapter defines them; Chat across cases is greyed while the AI assistant is Off.
- From the v1.11.0 build, to the AI assistant group: Speaker suggestion method, the extension point for better ways of telling Speakers apart, with "evidence" as its first and only method. To the Cases group: the Speaker roles row ships in v1.11.0, greyed while Folder management is Off, as the Cases release planned.
- From the Case Chat ticket, to the AI assistant and Limits groups: Chat across cases, the Case chat prompt template, Case chat: most hours of talk per question.

