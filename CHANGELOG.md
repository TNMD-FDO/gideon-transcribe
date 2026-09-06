# Changelog

Every Release has a section here, newest first, and a Release's notes on
GitHub are its section of this file. Two lines open every section, before
anything else:

```
Models: unchanged
Database: unchanged
```

`Models: changed` means `./transcribe upgrade` has to fetch models again, and
`Database: migrates` means the database changes when the app starts. The
upgrade command reads both lines out before it does anything.

This project follows [Semantic Versioning](https://semver.org): a tag is
`vMAJOR.MINOR.PATCH`, and a Release is the only thing an installer ever
installs or upgrades to.

## Unreleased

Nothing yet.

## v1.28.0, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **Send to attaches the recording too.** With Dictation by email on, the
  mail to a colleague carries the memo or summary as a Word file and the
  recording itself, up to the new **Largest recording attached** setting on
  the Email page (20 MB by default, since most relays refuse mail above 10
  to 25 MB). A larger recording is left out and the mail says so; the link
  opens it. The office decided this knowing the recording is the privileged
  thing itself; the recipient is always a colleague the directory knows.

## v1.27.0, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Dictations tab is the Record tab, and it asks one question.** New
  recording opens on "What are you recording?" with three cards: a
  dictation (just you; the memo), a meeting or interview in the room (tap
  who is talking; an Interview summary), or a call or meeting on this
  computer (Zoom, Teams, a softphone, a jail call played there; the far side
  is its own side; a Meeting summary). Choosing a card sets everything, and
  Record is the next click; language, Translate to English, the recording
  type, and the computer's sound wait under More options. The tab lists
  everything recorded from it with its style, and the row's button reads
  Write the memo or Write the summary. Send to, Take back, Add to a case,
  Delete, and the retention rule are unchanged. The old addresses redirect.
- **A shipped Meeting recording type and Meeting summary template**: what
  was decided, who is to do what, questions left open, what each person
  said. The Features setting is named Record tab; the Send to mail reads
  "sent you a recording".

## v1.26.0, 2026-09-07

```
Models: unchanged
Database: migrates (0029_dictation: the Recording's dictation mark and clock, and the DictationShare)
```

### Added

- **Dictations, a tab of their own (Phase 3, step four).** With the new
  **Dictation** setting on (Features page, under Live recording), a
  Dictations tab is in the top bar: New dictation, talk, Stop, and when the
  transcript is ready **Write the memo** turns the words into the document
  dictated, by the shipped Dictation memo template, with the false starts
  taken out and nothing added. A dictation is kept on its own, past
  sign-out and outside any case, and can be added to a case afterwards
  from its row. **Send to** hands one dictation to one colleague, who sees
  it under Sent to you and is mailed that it is there; **Take back**
  removes it. The office's Retention period applies to each dictation on
  its own, from its last use, with the amber mark, the nightly digest's
  new "Dictations deleting soon" block, and no recycle bin.
- **Dictation by email** (Email page, off by default): the Send to mail
  carries the memo as a Word file. The one message the app sends that
  carries content, to a colleague the directory knows and never a typed
  address, as the maintainer decided for the office's legal assistants.

## v1.25.0, 2026-09-07

```
Models: unchanged
Database: migrates (0028_taps_and_marks: the speaker taps and the Marks)
```

### Added

- **Live recording, step three: who is talking, and the moments that
  matter.** The Record page lists the case's people and takes anyone else
  who will speak; while recording, tapping a person as they start talking
  names the transcript's speakers from those taps when it lands, on a call
  the microphone's side only, and a tapped person joins the case's people.
  **M**, or the Mark button, drops a mark at this moment with an optional
  word; the viewer's Details list every mark as a time that seeks the
  player, with Make a clip beside it. A mark's word never reaches an audit
  row or a message.

### Fixed

- **A live recording's length read as zero.** A file streamed from the
  browser carries no length in its header, so the queue estimate and the
  Word export had nothing to say; the length is now read from the prepared
  audio when the original has none.

## v1.24.0, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Added

- **Live recording, step two: the computer's sound.** Tick **Also record
  what this computer plays** on the Record page for a call or a meeting on
  the computer (Zoom, Teams, a softphone, a jail call played there). The
  browser asks which screen to share and the page keeps only its sound; the
  microphone becomes one side of the transcript and the computer the other,
  as the app already handles a two-channel call, so who said what comes out
  right without guessing. A meter for each; sharing stopped from the
  browser's bar leaves the microphone recording alone, and the details say
  from when. Edge and Chrome on Windows.

## v1.23.0, 2026-09-06

```
Models: unchanged
Database: migrates (0027_live_recording: the Recording's live facts and the Batch's mark)
```

### Added

- **Live recording, step one (Phase 3).** With the new **Live recording**
  setting on (Features page, under Folder management, off by default),
  **Record** sits beside Upload on the Cases page and beside Add recordings
  on a case's page. The page records from the computer's microphone, sends
  the sound to the server in pieces as it goes, and, at Stop, hands the
  recording to the transcription service ahead of every uploaded one; the
  page and the case row say where it stands in words ("2 recordings ahead,
  about 4 minutes") until the finished transcript opens. Never a draft.
  Pause cuts, the office's **Longest live recording** (Limits, three hours)
  stops it, and leaving the page ends it with what was sent. The Details
  panel and the Word export say it was recorded live. Audit rows: Live
  recording started, Live recording finished. Edge and Chrome on the
  office's computers.
- **The transcription service gains a priority** (service 0.2.0): an
  optional `priority` on a job, a higher number running first and equal
  numbers in arrival order, with position and minutes ahead counted under
  that rule. Every other job is unchanged at 0.

## v1.22.1, 2026-09-06

```
Models: unchanged
Database: unchanged
```

### Changed

- **A case has one door.** Clicking a case anywhere on its row opens the
  case's page, which is where its recordings, search, clips, speakers,
  chat and sharing are. The details pane beside the Cases table and its
  two buttons are gone; Keep sits on a row in its last days. Before,
  Open jumped into the viewer on the newest recording and the case page
  hid behind a quieter link, so people landed in a player when they
  expected the case. The viewer now shows the case's name beside its
  back arrow, which returns to the case page.

## v1.22.0, 2026-09-06

```
Models: unchanged
Database: migrates (0026_summary_template_types: the shipped templates' key, and the types a template is for)
```

### Added

- **Summary templates by recording type.** A Summary template can now be
  for one or more recording types, ticked on the Templates page over the
  Recording types list; none means any. In the viewer, a recording in a
  case with a type starts New summary on the template made for that type,
  listed first with the others still on offer, and the dialog says why. The
  app ships five such templates beside the Standard summary, one each for
  Jail call, Body camera, Interview, Phone call and Hearing, each Enabled
  from the first day, editable, and resettable to its shipped wording;
  Admins review them on the Templates page. Add template takes the ticks,
  and a new template appears in the viewer for its types at once. A type
  removed from the list stays on the templates that had it, marked so.

## v1.21.0, 2026-09-06

```
Models: unchanged
Database: migrates (0025_mail: the Email status row, and the Batch's tick)
```

### Added

- **Email notifications (Phase 2, chapter 8).** With a relay named in
  `.env` (the install asks; `./transcribe install-mail` asks again), the app
  sends plain-text mail through it: a nightly **retention digest** to every
  person with a case in its last days, their own and the ones shared with
  them; **a case shared with you** and **a case handed to you** at once;
  **your batch has finished** for a person who ticked the new box on the
  Upload page; and Operator mail to one IT mailbox: the cases whose owner
  has left, the backup reports, and the test message. Every message names
  things and never quotes content, is marked automatic, and is tried three
  times within thirty minutes before an "Email failed" row. Nothing waits
  for mail.
- **The Email settings page**: the Email notifications and Batch finished
  emails switches, the four templates with Reset to default, all greyed
  while mail is not configured, and Send a test message, which shows the
  relay's reply.
- **The email address** is the directory's `mail` value, refreshed at each
  sign-in and by the directory check, with an "Email address updated" row
  on change; the Users page gains an Email column, a No email address mark
  and filter, and an Email field for Local admins; the Status page an Email
  line and the count of people without an address; the Installation page
  the seven mail keys. `./transcribe check` sends a test message and counts
  the Sign-in group's members without a mail value.

## v1.20.0, 2026-09-06

```
Models: unchanged
Database: migrates (0024_share: the Share table)
```

### Added

- **Sharing (Phase 2, chapter 2).** With the new **Sharing** setting on
  (Cases page, under Folder management, off by default), a case's owner
  shares it with named colleagues from the case page. The Share dialog
  offers everyone who has signed in at least once and says, before the
  owner confirms, what the person will be able to do. A collaborator works
  in the case as the owner does: opens, plays, searches, exports, adds
  recordings, corrects, names speakers, asks for summaries and chats, saves
  clips; and may not share, rename, transfer or delete the case, nor throw
  away a recording somebody else brought in. A shared case sits in the
  collaborator's own Cases list marked "Shared by" and "New" until first
  opened; the owner's "Shared with" panel lists each collaborator with when
  they were added and last opened it, and Remove beside each. Recordings a
  collaborator adds count against the owner's space, which the Upload page
  and the Move picker show, and an upload over it is refused naming whose
  space is full. A collaborator's use moves the retention clock, they see
  the amber warning and may press Keep, and their own nightly digest will
  list the case under "Shared with you". Off hides every share and deletes
  none. New audit rows: Share granted, Share revoked; a collaborator's
  opening writes Recording opened with the owner as affected user.
- **Transfer.** The owner hands a case to a colleague from the case page;
  the new owner takes it over and the old one stays on it as a
  collaborator, and may leave. Writes "case reassigned" and "Share granted".
- **Leave this case**, for a collaborator who no longer needs it.

### Fixed

- **A reassigned case's new owner could not play what somebody else had
  uploaded**: the media gate asked who uploaded a recording and never whose
  case it was in. Every recording-level page now asks one question, whether
  the person is the uploader, a member of the case, or an Admin looking in.

## v1.19.8, 2026-09-06

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The Restore drill loaded its dump into a database that already had
  one.** The teardown emptied the drill folder with a star after its name,
  and that star is expanded by the shell of whoever runs the drill, who may
  not look inside a folder that is the app's account's alone; so it expanded
  to nothing, removed nothing, and every drill built on the last one's
  leftovers, including a database already loaded. The folder is now emptied
  by root, before the drill as well as after it, and a test keeps the star
  out.

## v1.19.7, 2026-09-06

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The Restore drill failed at migrate**, three ways at once, all in the
  throwaway project and none touching the live app. The app reaches its
  database by an alias the drill's network did not carry; the drill called
  its management commands as `python manage.py`, which the image's entrypoint
  took as a command named "python"; and the throwaway database had no role
  for the app to connect as, since a dump carries the database and never the
  cluster's roles. The drill now keeps the alias, calls commands by name, and
  makes the app's role before migrating, as the web container does at every
  start. A failing step prints its last lines instead of nothing.
- **A drill that restored nothing would have passed.** A missing manifest
  read as an empty one, and an empty manifest had nothing to disagree with.
  A manifest that is missing or names no tables now fails the check.

## v1.19.6, 2026-09-06

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The Restore drill's Postgres never came up.** The drill made the folder
  for its throwaway database the way it makes every other drill folder, for
  the app's account alone; but Postgres runs as its own user inside its
  container and could not enter it. The folder is now root's at 0755, as
  Docker would have made it, and when Postgres fails to start the drill
  prints its last log lines instead of waiting in silence. Found on the
  second drill against the office's store, which restored the Snapshot and
  stopped there.

## v1.19.5, 2026-09-06

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The first real Restore drill restored the Snapshot and then said it had
  no dump.** Everything under the drill folder belongs to the app's account,
  and the script looked for the restored folders as the person running it,
  who is not allowed to see inside; so the dump was never moved into place.
  `./transcribe restore-drill` and `./transcribe restore` now make every such
  check through sudo, and a test keeps a bare check off those paths. The
  same fault would have stopped a real restore at the same step. Found on the
  first drill against the office's store, whose restore of 3.6 GB took 33
  seconds.

## v1.19.4, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The first real backup could not read the two environment files**, which
  belong to the installer's account, and mounting the secrets folder whole
  would have carried the repository password and the store's key into the
  repository. `./transcribe backup` now stages a copy of the configuration
  into the backup folder just before the Snapshot, owned by the app's account
  and without the two backup secrets, and that copy is what the container
  reads. Found on the first Snapshot against the office's store, which
  otherwise carried 3.6 GB in 34 seconds.

## v1.19.3, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **`./transcribe install-backup` emptied the three backup secrets.** The step
  that makes sure the files exist tested for them as the person running the
  command, who cannot see inside the app account's secrets folder, took all
  three for missing, and wrote empty files over them. It tests through sudo
  now and never touches a file that exists. Found on the first real run; the
  key was safe in its owner's home and nothing had yet been encrypted with the
  password.

## v1.19.2, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **`./transcribe check` stopped silently after "key-only sign-in works".**
  Under the script's strict mode a `grep` that finds nothing returns failure,
  and the root-listing test's assignment aborted the whole command. Every such
  assignment in the backup commands now treats an empty result as an answer.
  Also: a directory Docker leaves where the container's passwd file goes is
  cleared before the file is written.

## v1.19.1, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Key-only sign-in to the store failed from the backup container.** Two
  causes, found on the first real `./transcribe check` against a Synology
  store. ssh will not run as a user its passwd file does not know, and the
  container runs as the app's account, which Alpine's file does not list
  ("No user exists for uid"): `./transcribe` now writes a one-line passwd file
  for the container before every restic run and mounts it. And a key the
  install generated was written without its final line break, which ssh calls
  no key at all: it is copied as a file now. The install also stops to ask
  before making a new key when none is in place, so an office whose store
  already knows a key places that one instead of getting a second the store
  has never seen.

## v1.19.0, 2026-09-05

```
Models: unchanged
Database: migrates
```

Migration 0023 adds the Backup's status row. The app image gains nothing;
restic runs from its own image behind the `backup` profile.

### Added

- **Backup and restore**, the Cases release's chapter 9. Every night at
  `BACKUP_TIME` a host timer runs `./transcribe backup`: one consistent dump
  of the database, a manifest (release, migration, a row count per table, a
  checksum per file under cases/), and restic carrying the dump, cases/ and
  the configuration to an encrypted, deduplicated repository over SFTP on
  the office's backup store, keeping `BACKUP_KEEP_DAYS` nights there and
  `BACKUP_LOCAL_DUMPS` dumps on the box. Sundays the repository is pruned and
  a tenth of its data checked; the first Sunday of the month
  `./transcribe restore-drill` restores the newest Snapshot into a throwaway
  project beside the live one, checks it against the manifest, records the
  result in the live app, and tears it down. `./transcribe snapshots` lists
  the nights; `./transcribe restore <id>` puts one back on the same or a
  fresh server, after saying what is lost and waiting for the word RESTORE,
  and ends with the after-restore step: everybody signed out, every
  workspace discarded, in-flight case jobs failed as `restored` with a
  Retry, the outage recorded as an Off spell, the audit chain checked, and
  the report written as "Restore completed". The Status page gains the
  Backup line (red when off, failed or 26 hours stale; amber while the first
  copy is to come or a drill is late), the Installation page its rows, the
  audit log the rows Backup ran, Backup failed, Backup overdue, Restore drill
  ran, Restore drill overdue and Restore completed. `./transcribe install`
  asks for the target and the Operator address, makes the key and the
  password when there are none, records the store's host key, makes the
  repository and writes the timers; `./transcribe check` gains eight tests
  against the store. The admin guide gains the Backups chapter, the store's
  side for a Synology-class device, and the restore runbook; the install
  guide its step and keys. Operator mail waits for the Email chapter; the
  Status page and the audit log say everything meanwhile.

## v1.18.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **Page pass two: Cases, a case, Clips, the Recycle bin, the Panel and the
  guides**, the last of the five releases of the finish. A clip's span reads
  as two clocks and its length in words, "00:12:04 to 00:13:40, 1 min 37 s",
  in the table and the details, instead of raw seconds. The instruction lines
  under the Cases and Clips tables are first-time hints with Got it. The
  Panel's Users table folds the display name and directory address under the
  username and the Admin's source under the role, seven columns instead of
  ten, so it fits beside the Create Local admin pane without a scrollbar. The
  case page, the Recycle bin, the rest of the Panel and the guides needed
  nothing beyond what the foundations, the dialogs, the empty states and the
  hints had already given them.

## v1.17.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **Page pass one: Upload, Recordings, Batch and the viewer**, checked against
  the finish at desk and laptop widths in both themes. The Upload page's
  settings say one sentence each ("Tells the speakers apart and labels each
  line. It is sometimes wrong, so check the names against the audio."), the
  list of file types folds behind "Which files", and the foot no longer
  repeats the standing line. The Batch page's tally names only the states
  there are, so "1 transcribing · 2 done" rather than a row of zeros.
  Checkboxes and radios take the accent colour and sit on the text's
  baseline. Recordings and the viewer needed nothing beyond what the
  foundations, the dialogs and the hints had already given them.

## v1.16.1, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The logo on the sign-in page was small, and dim on the dark theme.** The
  first office to upload one has a wide mark drawn for a white page, and the
  card boxed it into 110 pixels. The card is wider when there is a logo, the
  logo takes the card's width up to 230 pixels tall, and on the dark theme it
  sits on a white plate so its colours read as they were drawn. The exports
  were right already.

## v1.16.0, 2026-09-05

```
Models: unchanged
Database: migrates
```

Migration 0022 adds the office logo's table. Nothing on disk changes.

### Added

- **The office's own face.** The Panel gains an **Appearance** page. An Admin
  uploads the office logo there, a PNG or JPEG up to 2 MB, and it appears
  large on the sign-in page at once, with the **Office name** under it and
  the app's name under that. **Logo on Word exports**, Off by default, puts
  the logo at the head of every export's cover, above the title, with the
  office name in grey beneath. The logo is kept with the app's own data, so a
  backup carries it, and is served by the app itself to the sign-in page;
  uploading and removing are audited, the image never is. Replace and Remove
  sit beside the preview.
- **The front door.** The sign-in page is one calm card: the logo or the
  app's mark, the names, two fields and one button, and the line "Your office
  sign-in. Nothing you upload leaves this building." where no notice is set.
- **Titles.** Every browser tab reads where you are, then the app's name:
  "Sign in · Gideon Transcribe", "Ramirez · Gideon Transcribe".

## v1.15.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **The app asks in its own words.** Every browser pop-up is gone. Deleting,
  cancelling, merging, clearing, emptying the bin, resetting a template,
  blocking a user and the rest now ask in the app's own dialog: a plain
  title, the consequence in a sentence or two, the safe choice first and the
  action last, red when it destroys. Renaming a speaker or a clip asks in the
  same dialog with a field. Copied, Renamed and the other quiet confirmations
  are a toast for two seconds; a refusal that needs no decision is a toast
  too, marked as a problem.
- **Empty pages say what they are for.** Recordings, Cases, Clips, a case's
  recordings and clips, the Recycle bin and an empty audit search each show
  one empty state with the one thing to do, instead of a bare heading.
- **Instructions become hints.** The paragraphs that told you how to use the
  Speakers panel and the tables are first-time hints with Got it, remembered
  in your browser; the bar of the viewer's bottom panel no longer carries a
  sentence of instructions. The words on the working pages are for work.
- **Plainer messages.** A recording that will not play says so in one
  sentence, with the detail behind "Details". The standing line reads "Your
  recordings stay until you sign out, or 12 hours after you stop working."
  The assistant's failure lines lose the capital letters and the jargon.

## v1.14.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **The foundations of the finish.** One visual language on every page,
  approved as the first of five releases. The app ships its own typeface,
  IBM Plex Sans with IBM Plex Mono for times and counts, under the SIL Open
  Font License, so it looks like itself on every desk and fetches nothing from
  outside. The colour tokens gain a slight blue cast, a soft form for every
  state, and a hover for the accent; the dark palette is the same roles, not
  an inversion. Type is one of four sizes instead of nine. There are four
  buttons in three fixed heights, so a row of mixed buttons lines up; one
  shape of pill whose colour is the state, with a dot for anyone who does not
  see the colour; table headings in small capitals; a visible focus ring on
  every control; motion of 120 ms and none for anyone whose system asks for
  none. One set of line icons, drawn in a sprite included on every page,
  replaces the typewriter glyphs that rendered differently on every machine,
  and the brand mark beside the wordmark is the favicon's waveform. A
  recording in the queue now wears the working colour like one being
  processed again. Nothing moves; every page picks the finish up at once.
  Rule 31 in the Phase 1 chapter of rules records it.

## v1.13.1, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **The starter questions are the office's own.** The built-in questions an
  empty chat offered in v1.13.0 are withdrawn. In their place the Templates
  page gains two lists, **Chat starter questions** and **Case chat starter
  questions**, one question per line, empty by default: an empty chat offers
  chips only when an Admin has written some, and otherwise opens with its
  grounding line and its box alone. Saving writes the ordinary Setting
  changed row and applies at once.

## v1.13.0, 2026-09-05

```
Models: unchanged
Database: migrates
```

Migration 0021 adds one column to the Case Chat's turns. Nothing on disk changes.

### Changed

- **Chat, made natural.** The viewer's Chat panel and the case page's Chat
  tab are now one component, drawn the same in both places, and made for a
  person who has never used it. An empty chat opens with starter questions
  as chips and a line saying what the assistant reads. Your questions sit on
  the right, answers on the left as cards with their time; answers render
  their lists, bold and headings, with Copy under each. A citation is a play
  pill (▶ 12:45, or ▶ Jail call 2, 12:45 on a case): hover shows the line it
  points to, a click plays from there and lights that line in the transcript.
  While the assistant reads, a pulse, the reading line, an honest expectation
  ("usually 5 to 20 seconds"; "Part 2 of 4 read" on a case in parts) and the
  seconds elapsed. A failed answer offers Try again in both places; a
  cut-short one says what to do. Earlier chats are a list with their names,
  when they started and how many questions; New chat stands apart. The
  conversation follows new answers only while you are at the bottom. Enter
  asks, Shift+Enter makes a new line, and the box grows as you type. The AI
  notice is one quiet line. Inside a case, the viewer's chat links to the
  case's Chat tab: "Ask about the whole case instead".
- **Expand, on a laptop.** The bar of the bottom panel gains Expand, which
  gives the open panel the height the window allows, and Shrink to go back.

## v1.12.0, 2026-09-05

```
Models: unchanged
Database: migrates
```

Migration 0020 adds the Case Chat and its turns. Nothing on disk changes.

### Added

- **The Case Chat.** A case's page gains a **Chat** tab whose ground is the
  whole case: every recording with a transcript, read whole, as the case
  stands when the question is asked. A small case is one engine call, like a
  recording's Chat; a large one is read in parts, two at a time, and one
  combining call writes the answer from the part answers, with the tab saying
  "Reading 40 transcripts in 4 parts. This takes a few minutes." Nothing is
  indexed or kept between questions. The case's people go ahead of the talk
  with their roles and never their notes, and each transcript opens with a
  header line naming the recording, its type, upload date, length and nature.
  A citation names the recording as well as the time, "Jail call 2 at
  00:12:45", and opens that recording in the viewer at that moment; one whose
  recording has left the case is marked "(recording removed)". Recordings
  still transcribing or failed are skipped and the answer says so at the top.
  The chats belong to the case, are listed newest first and named from the
  first question, export to Word with the case's cover facts and the
  recordings read, and count in the case's Delete confirmation. Asking is
  activity for the retention clock; deleting a chat is not. This is the Cases
  release's Case Chat chapter, shipped early; its amendment records the
  build's decisions.
- **Three settings.** **Chat across cases** on the AI assistant page (On by
  default, under the master switch, independent of the viewer's Chat toggle)
  turns the tab on and off and keeps the chats. **Case chat: most hours of
  talk per question** on the Limits page (120 hours, 6 to 600) is the ceiling
  one question may read; over it the question refuses with the figures. The
  **Case chat** prompt template joins the Templates page, editable with Reset
  to default, version 1.
- **Reason class `llm_case_too_large`**, and `llm_too_long` now also names the
  one transcript that would not fit a reading even alone. The audit log gains
  the `case_chat_turn` call, metadata only: transcripts read, readings used,
  model, host, template versions, tokens, duration and outcome.

### Fixed

- **The open chat's name was invisible.** In the viewer's Chat panel, and so
  in the new tab, the selected thread button was filled with the accent colour
  and its text was the accent colour too. It is outlined now, and readable.

## v1.11.1, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **The engine has three plain states: the Local engine, a shared engine, or
  none.** `./transcribe engine local off` used to stop the container and leave
  the app pointed at it, so every user saw greyed Summary and Chat buttons
  saying the assistant was not available and the Status page reported it
  unreachable. Off now means none: the panel's Engine address and Model name
  are cleared and the AI assistant toggle is turned off, through the same
  checks and audit row as the panel. `./transcribe engine`, for a shared
  engine, now asks for the engine's address and model name and writes them
  into the panel, as `local on` already did for its own, and stops a running
  Local engine in the same step so it does not hold the card for nothing. The
  install and admin guides say so.

## v1.11.0, 2026-09-05

```
Models: unchanged
Database: migrates
```

Migration 0019 adds the Person table. Nothing on disk changes.

### Added

- **People and the Speakers tab.** Inside a case a name means a person: every
  speaker in the case's recordings given the same name is one person, with a
  role and notes. The case page gains a **Speakers** tab that lists them, where
  each appears (links that play from their first words), **Add person**, and
  under each row **Rename everywhere**, a role and notes to **Save**, **Merge
  into** and **Delete person**. Below, **Unnamed speakers** lists the
  recordings still to work through. Naming a speaker in the viewer, accepting
  a suggestion or moving a recording in makes or joins a person. This is the
  Cases release's People chapter, shipped early because Suggest names needed
  it; the chapter's amendment records the build's decisions, the main one that
  the name is the link and there is no separate person column on a segment.
- **The viewer's rename box, inside a case.** Clicking a speaker opens a box
  under the list that offers the case's people as you type, each with their
  role and how many recordings they are in, and says it changes this recording
  only, with a link to the tab for renaming everywhere. Each speaker's role is
  a small badge after the name, and the Word export's Appearances table fills
  its Role column inside a case. In the Workspace nothing changes.
- **Speaker roles**, a list on the Cases settings page (Defendant, Witness,
  Victim, Officer, Attorney, Interpreter, Interviewer, Caller by default).
- **Evidence-first Suggest names.** Before asking the engine, the app finds
  the self-introductions ("this is Detective Ruiz") and forms of address
  ("Thanks, Maria") in the transcript and sends them with their line numbers,
  along with the case's people first in the Known names line and the office's
  roles. A suggested name is kept only when some evidence line carries it; a
  role needs none. The suggested pill shows the role when the name is a person
  in the case. The research behind this is `docs/research/speaker-suggestions.md`.
- **Speaker suggestion method**, a choice on the AI assistant settings page
  with one method today, "evidence". It is the extension point the maintainer
  asked for: better methods, from more capable models or new pipeline tools,
  join the list as they are built and are chosen there, while the Speaker
  suggestions toggle turns the whole feature off whichever method is chosen.

### Fixed

- **The case page's Speakers column counted "Speaker 1" as a named speaker.**
  It looked for the engine's raw labels, which the app never stores as
  names; it now uses the app's own rule for what a label is.

## v1.10.6, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Changed

- **Speaker suggestions starts Off.** The feature stays, with its toggle on
  the AI assistant settings page, but a new install (and an install that
  never touched the toggle) no longer offers Suggest names until an Admin
  turns it on. The first trials against the small Local engine did the job
  badly, and the reading behind the decision, with what would make it better
  and why voice biometrics are not the answer, is in
  `docs/research/speaker-suggestions.md`. Chat and Summary stay On by
  default. The settings catalogue and the AI assistant chapter carry the
  amendment.

## v1.10.5, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Suggest names failed with "an answer the app could not read".** Under
  strict output shaping the small model repeated entries until the answer hit
  its cap and the JSON was cut off, twice. The schema now allows at most one
  entry per unnamed speaker and bounds every string, a cut-off answer is
  salvaged by keeping the entries that were finished, and the cap rises from
  1,000 to 1,500 tokens. Found on the second Suggest names against the Local
  engine.

## v1.10.4, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Suggest names offered speaker labels as names.** The model answered
  "Speaker3" where it had nothing to go on, and the app's checks, which stop
  unknown, low confidence and names already held, let a label through. A
  suggestion whose name is a label in any spelling (Speaker 3, SPEAKER_02,
  Side 1 Speaker 2) is now dropped, and the answer format the app adds to
  every suggestions call now says what is wanted: a name when one is spoken,
  otherwise a role (Officer, Caller, Suspect, Witness and the like) worked out
  from what the speaker does, with unknown only when even a role cannot be
  told, and never a label. Found on the first Suggest names against the Local
  engine.

## v1.10.3, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **An empty answer with "The answer was cut short" when thinking was on.** With
  "Let the model think before answering" On, the model's thinking was billed
  against the same answer budget, and a small model's thinking alone used all
  of it, so Summary and Chat came back empty and marked cut short. Thinking
  now gets its own room on top of the answer's cap, 8,000 tokens, and a call whose whole
  budget still goes on thinking fails with a plain line saying so and what to
  do, rather than an empty summary. The admin guide says to leave the setting
  Off for a small Local engine, and that the engine's first request after a
  start is slow while it warms up. Found on the first trial of the assistant
  against the Local engine.
- **`./transcribe check` said no engine token was stored when one was.** Since
  v1.2.2 the check asked for the token file through a helper miscalled with
  `-s` handed to `sudo` rather than to `test`, so it answered "no" whenever
  sudo had no cached password. It now asks through the same helper every
  other secret is looked for with. The engine itself was never affected.
- **`./transcribe engine local on` no longer prints the worker's start-up
  chatter** twice around the two lines that matter, the settings it moved.

## v1.10.2, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The Local engine stopped after warming up.** The model keeps a fixed
  state for every conversation in flight, and vLLM's default room for 1,024
  of them does not fit in the engine's share of the card: "max_num_seqs
  (1024) exceeds available Mamba cache blocks (409)". The app never has more
  than four calls in flight, so the engine is now told to hold eight, which
  also leaves more of its memory for the transcript itself. Found on the
  first start of the Local engine on the office server.

## v1.10.1, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The Local engine died before loading its model.** vLLM runs as the app's
  own account, as every container does, and that account has no home folder
  inside the image; vLLM writes its caches under the home folder, tried
  `/.cache`, was refused, and stopped with "Model architectures failed to be
  inspected", which hid the permission error underneath. The service now has
  its home on the models volume it already owns. Found on the first
  `./transcribe engine local on`; the upgrade restarts the engine with the
  fix, and the profile and settings from `on` are kept.

## v1.10.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. The Local engine stays off until an
Admin turns it on; an office already pointing at a shared engine sees no
change. `LLM_LOCAL_MODEL` and `LLM_LOCAL_GPU_FRACTION` gain new defaults in
`.env.example`; an existing `.env` keeps its own values until `engine local
on` asks.

### Added

- **The Local engine, on or off.** `./transcribe engine local on` starts a
  small language model on this server for the AI assistant, beside the
  transcription service on the same card: it shows the cards, offers the
  least busy one, asks the model and the share of the card's memory the
  engine may take, writes a token when none is stored, starts the engine and
  points the Panel's Engine address and Model name at it. `./transcribe
  engine local off` stops it and frees the card. `./transcribe check` reports
  the engine's health. The default model is `Qwen/Qwen3.5-4B`, chosen in
  `docs/research/local-engine-model.md` against the office's rule that the
  engine with its cache uses no more than 20 GB: the largest of its family
  that does, with the 262,144-token native context the chapter requires and
  the same reasoning parser as the shared engine. The default share is 0.21,
  twenty gigabytes of a 96 GB card. An office that wants a larger model
  changes one line in `.env`.
- **`manage.py set_setting`**, which moves one admin setting from the
  server's command line under the panel's own checks, with an audit row as
  the system; `engine local on` uses it and nothing else should.

### Changed

- The architecture and AI assistant chapters carry the new model and share;
  the install guide gains "The Local engine"; the licence table names the
  model's weights and their licence.

## v1.9.0, 2026-09-05

```
Models: unchanged
Database: migrates
```

### Upgrading to this one

The database migrates when the app starts: seven tables for the AI
assistant's templates and what its features store. The models are unchanged.
Nothing appears for users until the AI assistant toggle is turned on, which
should wait for Test connection to succeed against the office's engine; the
plumbing has been in place since v1.2.0, and the engine token is still the
one thing this office is waiting on.

### Added

- **The AI assistant's three features.** The second half of the AI assistant
  chapter, on the plumbing of v1.2.0. **Summary**: New summary asks for an
  optional focus and a length, Short, Standard or Detailed, and a template
  when two or more are Enabled; the call reads the whole transcript on
  `llm-worker` and the summary arrives whole, with every time the app can
  match to a segment made a citation that plays the recording from that
  moment, the AI notice at its head, Regenerate, Export to Word and Delete.
  **Chat**: threads named from their first question, answers from the
  transcript alone with the last turns carried back within the 16,000-token
  history budget, citations, Copy, Export to Word, Delete. **Speaker
  suggestions**: when two or more speakers have no name, Suggest names asks
  once for the whole transcript with the chapter's JSON schema; the app keeps
  a suggestion only when its line exists, its confidence is high or medium,
  the name is not unknown, not held by another speaker, and not proposed
  twice; each shows its reason and its time, with Accept renaming every
  segment of that speaker and Reject dismissing it. On the Bench, Summary and
  Chat are two more tabs beside Clips and Details; on a laptop they are the
  sheet's. Every call writes one audit row, metadata only: feature, model,
  endpoint host, template versions, token counts, duration, outcome. Never
  the question, the prompt, the answer, or a name.
- **The Templates page** in the Panel's Settings group: Ground rules, Chat
  and Speaker suggestions as plain text with Reset to default and a version
  that rises on every save; Summary templates with name, description, text,
  Enabled and Default, Add template, and the built-in Standard summary that
  cannot be deleted. Everything applies at once, outside the tray, each act
  its own audit row naming the template and version, never the text.
- **Two Word exports**: a Summary and a Chat each export on their own in the
  Record layout, cover facts, header block, the AI notice above the
  transcript's notice, and the body with citations printed in grey, named
  `<title> - summary (<template>) <date>.docx` and `<title> - chat
  <date>.docx`.

### Changed

- **The Status page's AI assistant line** reads "off; no engine token yet"
  when an address is set but the token file is empty, which is this office's
  state while it waits for the key, rather than "no engine is configured".

## v1.8.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes.

### Added

- **The guide beside the page.** On a window 1500 pixels or wider, a `?`
  beside Help opens the user guide (the admin guide, from the Panel) in a
  360-pixel column on the right of the page, at the section about the page
  you are on. The page makes room for it rather than being covered, it
  scrolls on its own, and it stays open from page to page, each time at the
  new page's section, until it is closed. The guide's own links work inside
  it, and Open as a page goes to the full guide. On a narrower window the
  `?` is not shown and Help opens the guide as a page, as before. Set aside
  in v1.7.0 and built at the maintainer's ask; the Admin panel chapter
  carries the amendment.

## v1.7.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. The last of the four Workbench
releases; every page now has its wide shape.

### Changed

- **The Panel spreads out on a wide window.** The audit log's filters sit in
  a pane on the left and stay put while the rows scroll; the form that
  creates a Local admin sits beside the users table instead of below it;
  every settings page lists its settings in a pane beside the form, each a
  jump to its row and marked when changed from default or waiting in the
  tray; and the panel page is no longer capped at 1100 pixels. Below 1280
  pixels the pages are as they were.
- **The guides read beside their contents.** The contents list is a rail on
  the left of the text, which keeps its reading width, and the section being
  read is marked as you scroll. Help on every page now opens the user guide
  at the section about that page: Help on the Recordings page lands on Your
  recordings, on the viewer on Reading a transcript, and so on. The
  proposal's "?" pane, the guide opening beside any page, is not built: a
  pane on every page would make every page's layout give way to it, and the
  section link gives most of its worth. The Admin panel chapter carries the
  amendment.

## v1.6.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. The Cases pages and the Clips page
change shape on wide windows; the Recycle bin keeps its address and gains
the Cases strip above it.

### Changed

- **The Cases page has three tabs and a details pane.** Mine, Everyone's
  (Admins only) and Recycle bin in one strip, in place of a second table
  below the first and a bin to go and find. The table gains a Retention
  column, the clock's own line for every case. Click a case and its details
  appear in a pane beside the table from 1280 pixels, or under its row on a
  narrower window, with Open, Case page, and Keep when it is in its last
  days. Up and down move along the rows; Enter opens.
- **A case's page is two panes.** What is in the case on the left: the
  Recordings and Clips tabs, the search box and its hits, and the recordings
  as a table (title, type, state, length, speakers, added) whose details,
  type and notes open under the row. What is about the case on the right:
  owner, count and size, last activity, where its clock stands with Keep,
  Download all transcripts, Rename, and Delete case. Add recordings stays in
  the header. On a narrower window the right pane follows the list.
- **The Clips page is one table with a player.** Every clip in one table
  with the recording as a column and a filter by recording above, in place
  of a table per recording. Click a clip and it plays where it is chosen,
  in the pane on the right from 1280 pixels or under its row below that,
  with its details, Download, Open in viewer and Delete. The Cases chapters
  of Phase 2 and the Clips chapter carry the amendments.

## v1.5.0, 2026-09-05

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. Three pages change shape on wide
windows and keep their shape on narrow ones.

### Changed

- **The Upload page shows its three steps at once on a wide window.** From
  1280 pixels, Choose files sits on the left and Settings above Check and
  start on the right, with Upload and transcribe always in view and greyed
  until there is a file to send. Nothing hides behind Next: the review table
  follows every change as it is made, and each file's card carries the
  `Same as batch` chip that opens that file's own settings, so the exceptions
  table is not repeated there. On a laptop the stepper is exactly as it was,
  with the chips on the cards as an extra way in.
- **The Recordings page is a table with the chosen recording's details
  beside it.** Title, state, length, clips and the time of its batch in one
  row each, with Open on every ready row, and one block of details for the
  chosen recording (the file, the state in full, the Sides, the clips, and
  Process again, Move to case, Retry and Delete) in a pane on the right from
  1280 pixels, or opening under the row on a narrower window. Up and down
  move along the rows, Enter opens, and a wide window shows the first
  recording's details until another is chosen. Twenty recordings are no
  longer twenty rows of buttons.
- **The Batch page has a `Ready now` pane.** While a batch runs, the rows sit
  on the left and, on the right, the transcripts that are already finished
  with Open beside each, the download of them so far, how many are still to
  come with the estimate, and Cancel. On a narrow window the same blocks
  follow the rows. The finished state is unchanged and takes the whole width.
  The Upload page and Batch page chapter carries the amendments.

## v1.4.0, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. The viewer's layout changes on wide
windows; a remembered sheet height and picture width carry over, and a
remembered column width is new.

### Changed

- **The viewer has a Bench.** On a window 1280 pixels or wider, the video
  and the Clips and Details panels move to a column on the right of the
  transcript, always open, with the video at the top and one panel at a time
  under it chosen by tabs. The top bar keeps the title, the markers, the
  transport and the Timeline, which now spans the transcript's width. The
  empty margins either side of the transcript on a wide monitor are what the
  column takes; the transcript keeps its reading width. Nothing covers the
  words: no sheet rises over them and, when the AI assistant's Summary and
  Chat arrive, they will be two more tabs on the Bench rather than overlays.
  The picture is resized by dragging the column's left edge, and the width is
  remembered on its own, apart from the picture width a laptop remembers. On
  a window narrower than 1280 pixels nothing changes: the picture sits beside
  the title and the panels are the bottom sheet, as before. This is the first
  page of the Workbench Layout, which the following releases apply to Upload,
  Recordings and Batch, then Cases and Clips, then the Panel. The viewer
  chapter carries the amendment and the glossary gains the word.

## v1.3.0, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. Recordings already on the server keep
the waveform files they have, which draw exactly as before; only recordings
made from now on get the smaller file.

### Changed

- **The Timeline no longer draws Speaker lanes.** The coloured bands behind
  the waveform, one per Segment, were drawn again on every redraw of the
  Timeline, once a second while playing, on transcripts of thousands of rows,
  and told a corrector nothing the rows beside them did not: a Speaker's
  colour stays on the name and on the bar beside each row. The Timeline is
  the waveform, split into one lane per Side on a Two-channel call. The
  specification's viewer chapter carries the amendment.
- **The waveform file is sized to the strip, not to the recording.** The
  Timeline draws the whole recording across the width of the page and never
  zooms, yet the peaks file held one pair for every 256 samples of sound:
  4 MB for a 51-minute recording, 27 MB for six hours, fetched again on every
  opening of the viewer, of which the strip drew one pair in four hundred. A
  recording now gets about 8,192 pairs whatever its length, never finer than
  before, so the file is about 60 KB for any recording (double for a
  Two-channel call). The strip is also truer: each pixel now shows the lowest
  and the highest of every pair it covers, worked out once per width, where
  before it sampled one pair and could miss a shout or a slammed door between
  samples. The media chapter carries the amendment.

### Fixed

- **A Two-channel call's waveform was never split into its two Sides.** The
  media chapter says the peaks are split per channel for a Two-channel call,
  and the viewer has always drawn one lane per Side when the file has two
  channels, but the media worker never asked audiowaveform for it, so the
  strip showed both parties mixed into one lane. It asks now, for a
  Two-channel call and nothing else. Recordings already on the server keep
  the file they have.

## v1.2.3, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. Recordings already on the server are
unaffected; the change is in how new copies are written and how the viewer
decides a copy is ready.

### Fixed

- **A video opened right after transcription loaded slowly and froze.**
  Recognition finishes on the GPU before the playback copy of a long video
  is finished on the CPU, and for that minute the copy existed on disk but
  was still being written, with its index not yet in place. The viewer
  handed the browser any playback file that existed, so a browser opening in
  that window found no index, read blindly, and stalled; and the page never
  re-checked, so the person stayed stuck until they reloaded by hand. The
  copy and the waveform are now written under another name and renamed when
  whole, so a half-written file is never visible under the name the viewer
  looks for; the viewer decides by the recording's own "playback ready" flag,
  which it had never read; and a page that opens before the copy is done
  shows "Preparing video", says so plainly, asks every five seconds, and
  lifts the overlay itself, as the chapter says it should. Reading, search
  and correction work meanwhile.

## v1.2.2, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### Fixed

- **`./transcribe upgrade` stopped silently after the checkout on a server
  installed the documented way.** After the install, `secrets/` belongs to
  the app's account and is mode 700, so the account running the script
  cannot see into it or write into it. The step added in v1.2.0 that makes
  sure the engine's token file exists asked with a plain test, was told the
  file was absent, tried to create it, and died on "Permission denied", which
  under the script's strict mode ended the upgrade with the checkout moved
  and nothing rebuilt. The v1.2.1 fix therefore never reached the
  containers. Every write of a secret now goes through one helper that uses
  `sudo` when the folder is not the caller's, and the existence test asks
  through `sudo` too: the token file, the engine token, the directory bind
  password, the Hugging Face token, and the generated secrets alike. A test
  fails if a bare redirection into a secrets folder comes back.
- **Recovering a server the v1.2.1 script left half upgraded** is one extra
  step, because the script that runs an upgrade is the one already checked
  out: `git fetch --tags && git checkout v1.2.2`, then
  `./transcribe upgrade v1.2.2` as usual. The install guide's "When it
  fails" table carries it.

## v1.2.1, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### Fixed

- **`llm-worker` connected to the wrong database on a shared engine's
  network.** Joining that network for the engine, as v1.2.0 does, also puts
  the worker where the other project's names resolve. Docker's DNS answers a
  bare `postgres` from either network, and the office's platform project
  runs a service called `postgres`, so the worker signed in to the platform's
  database, failed, restarted ten times, and never consumed its queue. Test
  connection therefore never ran and the page waited for ever. The app now
  reaches its own database as `transcribe-postgres`, an alias declared on the
  service and used by every container, never as the bare service name. ADR
  0003 records the consequence. Nothing else changes; the upgrade restarts
  the containers with the new name.

## v1.2.0, 2026-09-04

```
Models: unchanged
Database: migrates
```

### Upgrading to this one

The database migrates when the app starts: one table, the engine's status
row. The models are unchanged. The upgrade creates `secrets/llm_api_token`
empty if it is not there, so the stack starts exactly as before, with a new
`llm-worker` container that has nothing to talk to yet. Nothing changes for
users: the AI assistant toggle stays off and no feature appears.

To connect the office's engine, three steps, in the install folder and then
the panel:

1. `./transcribe engine`: the Docker network the engine listens on, and its
   bearer token, typed hidden and twice. Then `docker compose up -d`, so
   `llm-worker` joins that network.
2. Panel, Settings, AI assistant: the **Engine address** on that network
   (`http://<its name>:8000/v1`) and the **Model name** it serves, through
   the tray as every setting is.
3. Panel, Status: **Test connection**. Green means the engine lists its
   models and answered a question with the token. `./transcribe check` proves
   the same from the server.

Leave the AI assistant toggle off until the next release brings the
features; turning it on now shows nothing.

### Added

- **The AI assistant's engine, wired up.** The first half of the AI assistant
  chapter: the plumbing that lets an office point the app at a language-model
  engine and prove the connection, before any feature uses it. A fourth
  worker, `llm-worker`, on its own queue, the only container that may join a
  network outside the project; `./transcribe engine`, which asks for a shared
  engine's Docker network and token, writes the token file, and turns the
  shared-engine compose file on; `compose.shared-engine.yaml`, which joins
  `llm-worker` to that network and nothing else; the optional Local engine as
  Compose profile `llm`, pinned by digest, off by default; a once a minute
  check of the engine from `llm-worker`, whose result the Status page shows
  as an AI assistant line, green with the model or red with "unreachable
  since"; **Test connection** on the Status page, which lists the engine's
  models with the token and asks it one tiny question; the token shown as
  set or missing on the AI assistant settings page; and the six reason
  classes the chapter fixes. Summary, Chat and Speaker suggestions follow in
  the next release.

### Changed

- **Every install and upgrade makes sure `secrets/llm_api_token` exists**,
  empty when there is no engine, because a secret whose file is missing stops
  the whole stack. An install from before the AI assistant existed comes up
  as before.

## v1.1.0, 2026-09-04

```
Models: unchanged
Database: migrates
```

### Upgrading to this one

The database migrates when the app starts: one column. The models are
unchanged. The three retention settings arrive at their defaults, 30 days,
7 days and 30 days, greyed until Folder management is on. With the defaults
and Folder management on, the first sweep at half past three warns nothing
for 23 days from a case's last use, bins nothing for 30, and wipes nothing
for 60. Set the Retention period for your office before then, or leave it:
lengthening later is free, shortening later deletes that night.

### Added

- **The Retention policy and the Recycle bin**, Phase 2's third chapter. A
  case is kept for as long as somebody uses it: every use starts its clock
  over, looking at the list does not, and an Admin's audited opening does not.
  Three settings on the panel's Cases page, greyed while Folder management is
  off: the **Retention period** (30 days), the **Warning before deletion**
  (7 days, always shorter than the period; the tray refuses a pair that is
  not), and the **Recycle bin** (30 days). During a case's last days its row
  turns amber, reads "Deletes in N days unless used", and carries **Keep**,
  which starts the clock over without opening anything; an **Expiring**
  filter shows only those, and Admins also get "Owner deactivated". The
  nightly sweep at half past three marks the warning once, moves due cases
  whole into the Recycle bin, wipes what has sat there past the bin period,
  and writes one row with the counts; it does nothing at all while Folder
  management is off, and every count leaves the days it was off out. A case
  in the bin is out of every list and unusable by anybody, an Admin included,
  and counts against its owner's quota; the **Recycle bin** page, reached from
  the Cases page, offers **Restore**, which starts the clock over, **Delete
  permanently** behind a confirmation that names the counts, and **Empty
  recycle bin**. A person's own Delete is unchanged and final. Six audit rows,
  as the chapter fixes them. The digest by email waits for the Email chapter;
  the sweep already gathers what it would say.

### Changed

- **Delete data on the Users page** wipes a leaver's binned cases too, with
  the Admin as the cause.
- **The Status page's Cases line** now reads "Cases: N, X GB; M expiring; K in
  the recycle bin, Y GB".

## v1.0.0, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### What this release is

The first release meant for another office to install. Phase 1, the
Workspace, is complete: directory sign-in, batches and the queue,
transcription with translation and speaker separation, the viewer with
correction, search and clips, the exports, the Admin panel with its audit
log, and the three guides. Of Phase 2, Cases themselves are built, behind the
Folder management toggle and off by default.

Not built, and said so rather than implied: the AI assistant, and the rest of
Cases, which is sharing, the retention policy and recycle bin, the speakers
tab, chat across a case, email notifications, and backups. Those arrive in
later releases, and v2.0.0 is the one that completes Cases.

### Upgrading to this one

Nothing migrates and no model changes.

This is the first release that records the identity of its two images
(ADR 0013), so it is the first whose upgrade can check what it pulled against
what was built. The check runs only when the images are pulled rather than
built, and a server can pull only once the packages are public. So:

1. Wait for the release to appear on GitHub before upgrading. Its workflow
   takes about twenty minutes and writes the record last.
2. Either make the repository and both packages public first (below), so the
   upgrade pulls and checks; or upgrade now and accept that it builds from
   source as every upgrade has so far, which is the other way of getting
   exactly this release's bytes.

**The public flip**, for the maintainer, on GitHub, once and in this order:

1. The repository public: Settings, General, Danger Zone.
2. Each of the two packages public: the package's own settings, Danger Zone.
   This cannot be undone.
3. A ruleset on `main` forbidding force-push and deletion: Settings, Rules.
4. Issues on, Discussions off, Wiki off: Settings, General, Features.
5. Private vulnerability reporting on: Settings, Advanced Security.
   `SECURITY.md` already points at it.

The README's as-is line is already in place.

### Changed

- **The README says what is built.** It said the code was not written yet,
  and listed VTT export and an AI assistant that do not exist. It now lists
  what each Release actually holds, names what is not built rather than
  implying it, and points at the three guides.
- **The third-party licence file records the ffmpeg the Releases ship.** Its
  table said "none published yet" while three Releases sat on the registry,
  and a GPL binary that is distributed must have its source pointed at. The
  exact ffmpeg and codec package versions of both images are recorded from
  the running images, `audiowaveform` (GPL-3.0-or-later, in the app image)
  is listed for the first time, the app's Python packages are listed, and the
  rows for the engine and backup images say they are not yet shipped.
- **Why our two images are pinned by tag** is written down as ADR 0013: a
  tag cannot carry the digest of the image built from it, because the image
  is built after the tag exists. The upstream images are pinned by digest as
  before; ours are pinned by an immutable tag and checked at upgrade, below.
  The release workflow's summary no longer tells a reader to pin the digest
  in `compose.yaml`.

### Added

- **The upgrade checks what it pulled.** The release workflow now asks the
  registry what each tag resolves to and records it beside the Release: in
  the notes, as an attached `digests.txt`, and as a git note on the tagged
  commit, which is the copy a server can fetch with the same key it fetches
  the code with. `./transcribe upgrade`, when it pulled rather than built,
  compares each image against that record and stops before starting anything
  if they differ, naming the image and both digests, and offering `--build`
  as the way that trusts the source and not the registry. A release with no
  record, which is every one before v1.0.0, is said so and the upgrade goes
  on.

## v0.4.0, 2026-09-04

```
Models: unchanged
Database: unchanged
```

### Upgrading to this one

Nothing migrates and no model changes. The images are pulled from the
registry, so the upgrade takes a minute or two. Afterwards, Help at the top
of any page opens the user guide, and the Admin panel's rail has the admin guide.

### Added

- **The three guides.** The user guide is served at `/help/`, behind a Help
  link on every page, and the admin guide behind the Help link in the Admin
  panel's rail. Both are the repository's own Markdown in `docs/`, rendered to
  HTML when the image is built, so what the app shows is exactly the running
  release's text and nobody who uses the app needs GitHub to read it. The
  install guide, `docs/install.md`, is read from the repository: what you
  need, the directory checklist with both the clicking and the PowerShell
  path, the certificate request, the Hugging Face token, the server
  preparation commands, install, check, first sign-in, a table of what can go
  wrong, upgrade, roll back, uninstall, and every environment key with its
  meaning.

### Changed

- **The app image is built from the repository root** rather than from
  `app/`, so the build can reach the guides (ADR 0012). The root
  `.dockerignore` keeps the office's `.env`, secrets, certificate and CA root
  out of the build context, and a test fails if any of them is dropped from
  it. Nothing changes for an office: `./transcribe upgrade` builds and pulls
  exactly as before.

## v0.3.0, 2026-09-04

```
Models: unchanged
Database: migrates
```

### Upgrading to this one

The database migrates when the app starts, dropping a column that v0.2.0
added the same day and nothing reads any more. The models are unchanged. This
is the first upgrade that pulls the images from the registry instead of
building them, so it should take a minute or two rather than twenty.

### Changed

- **Every page is centred.** `main.wide` takes the whole window on purpose,
  for the viewer and the admin panel, but the six document pages inside it
  each set their own width with an inline `max-width` and no margin. So every
  one of them sat against the left edge with a third of a wide monitor empty
  beside it. The widths live in one `.page` class now, and a check fails if
  anyone writes an inline one again.
- **Signing in opens the Upload page**, for everybody, whatever the settings
  say. The specification lands people on Cases when folder management is on,
  which is right for the office that works in cases and wrong for the one
  whose larger use is batches that belong to no case. Upload is right for
  both, because it is what everybody came to do, and cases and recordings are
  one click away. This replaces the per-person landing preference added
  earlier the same day, whose column the database now drops.
- **The Upload page greets you** by name and by the hour, says in one line
  what will happen, and makes the drop area the main object on the page
  rather than a box inside "step 1 of 3". It also carries the line that
  answers the question every new user of this app has: nothing leaves this
  building, and everything here goes when you sign out.
- **A finished batch is about the download.** It used to be one button among
  four in a left-aligned row under a list. The page now says how many
  transcripts are ready, offers one large download, and puts everything else
  quietly underneath.

## v0.2.0, 2026-09-04

```
Models: unchanged
Database: migrates
```

### Upgrading to this one

The database migrates when the app starts, so the upgrade is one command and
there is no separate step to remember. The models are unchanged, so nothing
is fetched.

Nothing is published to the registry yet, so `./transcribe upgrade v0.2.0`
builds both images on the server. The WhisperX one takes ten to twenty
minutes the first time and is mostly waiting.

### Added

- **Finishing with a batch.** An office running batches works in a loop:
  upload, wait, download, clear, upload the next lot. The clearing step did
  not exist. The only ways to remove twelve recordings were Delete twelve
  times or signing out, and signing out takes everything, so somebody keeping
  one recording from last week had to choose between it and the room for
  tomorrow's batch. This is not tidiness: every recording counts against its
  owner's quota until it goes, so a morning of large files reached the quota
  with no remedy that kept the person signed in. A finished batch now offers
  **Done with these**, which removes that batch and takes you to Upload, and
  the recordings page offers **Clear my recordings** for all of them. Both
  say the counts and the size and tell you to download first, because both
  are final. Neither touches a recording in a case.
- **Upload recordings on the Cases page.** Not everybody who lands there is
  there for a case, and the page offered no way to start one.
- **Signing in opens the page you work on.** With folder management on
  everybody landed on Cases, which is right for the office that works in
  cases and a detour for the office whose larger use is batches that belong
  to no case. The specified landing page stands until somebody opens the
  other one, and after that they land where they were working. Turning folder
  management off puts everybody back on the recordings page, as before.
- **Cases**, the Phase 2 feature that lets a recording outlive the session
  that uploaded it. A case is a named page with one owner; a recording moved
  into one lives under `cases/<case id>/<recording id>/` and the sign-out
  discard leaves it alone. The Cases page, the case page with a search across
  its transcripts, New case, Rename, and a Delete that names what it is taking
  and cannot be undone.
- **Folder management**, the admin toggle that enables cases, default off, on
  a new Cases page of the settings rail with **Recording types** beside it.
  Off hides every case from everyone, Admins included, and deletes nothing;
  the days it is off are recorded as they pass, because the retention policy
  will subtract them and cannot work them out afterwards.
- **Add to case** and **Recording type** on the Upload page, set once per
  batch with a per-file override, and **Move to case** from the recordings
  list, from a case page, and from the sign-out dialog. On disk a move is a
  folder rename, so it is instant whatever the size.
- **A case opens into the player.** Clicking a case on the Cases page opens
  its newest recording that has a transcript, with the rest of the case
  beside it, rather than a list to click through. A case with nothing to play
  yet opens its own page, which is where Add recordings is, and every row
  carries a quiet "Case page" link for renaming, deleting, and the rest.
- **Download all transcripts** for a whole case, from the case page and from
  the rail. Transcripts only and not the media: a workspace is bounded by a
  login session and a case is not, so "everything" for a case could be
  hundreds of gigabytes.
- **Process again remakes the audio the model hears.** It handed the file
  prepared at upload straight back to the service, so a recording could never
  be improved by a change to how audio is prepared: a fix reached new uploads
  and nothing already on the disk, and the only way to mend a recording was to
  delete it and put it up again. It is remade from the uploaded bytes now,
  which is what those bytes are kept for. This is what makes the fix for
  dropped audio on a body-worn camera reach a recording already transcribed.
- **A seek that will not take says so.** A media element that cannot be
  jumped about in accepts the instruction and ignores it, so clicking the
  timeline did nothing and said nothing. Every seek is now watched, and one
  that does not land reports it in the same line the player's other troubles
  use, saying whether the server is not answering for parts of the file or
  the player simply refused.
- **Clicking the waveform seeks again.** A click and a drag were told apart by
  how much time was between them, and on a twenty-five minute recording one
  pixel of timeline is over a second, so every click, which always jitters a
  pixel or two, counted as a drag and marked a clip instead of seeking. It is
  measured in pixels now, which is the same however long the recording is.
- **Following stops only when you have read away from the line**, and comes
  back when you scroll to the line being spoken, or seek anywhere on purpose.
  Any nudge of the wheel used to stop it for good unless the amber notice was
  spotted.
- **A marked clip can be dropped.** A selection made and then thought better
  of stayed tinted across the transcript and the timeline with no obvious way
  to be rid of it. There is a **clear** beside where the selection is shown,
  Escape drops it, and saving a clip clears it, since the span it was cut from
  has stopped being a pending selection.
- **The correction box closes, and it has buttons.** It could only be
  finished with Ctrl+Enter or Escape, neither of which was written anywhere,
  so a box opened by mistake stayed open. It now carries Save correction and
  Cancel. Clicking away from a box nothing was typed into closes it; one that
  has been typed in stays open and says so, rather than being saved or thrown
  away on a guess. Only one box is ever open at a time.
- **What both sides of a call heard is read once.** A phone system plays its
  recorded announcement to both parties before the call connects, so both
  channels carry it and both sides transcribe it: the first minutes of a jail
  call read twice over. Those passages are now printed once, named "Side 1 and
  Side 2", and both copies are kept in the database. The viewer and every
  export say how many there were. Recordings already transcribed keep their
  doubled text until Process again.
- **Marking a clip from the transcript is two steps that say so.** The button
  on a segment reads **clip start**; press it and every button reads **clip
  end** until the second is pressed, with the starting segment marked
  meanwhile. Escape gives up on a half-marked clip. Marking a start no longer
  throws the clips panel open over the transcript: it appears on the second
  press, when there is something finished to name and save. The I key behaves
  the same way, and O still brings the panel up.
- **The bottom panel stays put and resizes.** Whichever panel was open, clips
  or details, comes back on the next recording, so moving through a case no
  longer closes it every time. Drag the strip above its tabs to make it taller
  or shorter; double-click to reset, or use the arrows. Close still puts it
  away, and that is remembered too. It can never be dragged so tall that the
  transcript disappears: the limit is measured from the layout, because the
  picture above it is itself resizable.
- **Clips in a case.** The viewer's clips sheet now holds every clip in the
  case, this recording's own first and the rest under "Elsewhere in this
  case", each saying which recording it came from and who saved it. The case
  page gains its **Clips tab** with the columns the chapter names, a "Saved
  by" column, no "Downloaded" column because nothing is lost at sign-out
  there, and a Download all for the case. The Clips page in the navigation
  stays the workspace's own list, so a clip is listed in one place.
- **The video window resizes.** Drag the right edge of the picture, and the
  height follows so it keeps its shape. Double-click the handle to put it
  back, or focus it and use the arrows. The size is remembered across
  recordings, and never grows past half the window, because the transcript is
  the point of the page.
- A **case rail** in the viewer: a recording opened from a case gets a third
  column listing the rest of the case, so somebody working through a matter
  moves between its recordings without going back to the case page. The
  chapter lists the viewer as unchanged when reached from a case; this is
  additive rather than contradictory and the maintainer asked for it. It
  hides on a narrow screen and opens over the page there, the button in the
  head is always present, and the choice is remembered.
- The users list reads "3 in session, 41 in cases", and its **Reassign** and
  **Delete data** actions, greyed since the first release, now act. The status
  page gains a Cases line and, while the toggle is off, the date it went off.
- `./transcribe install` and `./transcribe upgrade` now make `scratch/`,
  `cases/` and `uploads/` under the app data folder with the right owner,
  because Docker creates a missing mount source as root and the app could
  then never write into it. `./transcribe check` says so if one is wrong.

### Fixed

- CI had not run a single check since directory sign-in landed: `python-ldap`
  builds from source and the runner had none of the headers it needs, so the
  install step failed and the lint, the tests, the compose validation and the
  secret scan were all skipped. Four commits went in on a red build.
- Twenty tests had been failing on a missing static files manifest, which hid
  two more: signing out with a GET has shown the confirmation dialog rather
  than signing anybody out since the dialog was built, and nothing noticed.
- The check that proves Caddy asks the app before it serves a byte was not
  looking inside nested routes at all.

Three tabs of the four a case page is meant to have are absent on purpose:
Speakers, Clips, and Chat belong to chapters not yet built.

## v0.1.0, 2026-09-03

```
Models: changed
Database: unchanged
```

The WhisperX service, built first and on its own, so that the app has a
working engine to be written against.

This is a build release, not a public one: `v1.0.0` is the first Release an
office installs. It runs on the office's own server and has been measured
there against the office's own recordings.

### Added

- The WhisperX service in `whisperx-service/`: its image on
  `nvidia/cuda:12.8.2-base-ubuntu24.04` pinned by digest, with every Python
  package pinned to the version `docs/research/whisperx-pinned-stack.md` chose
  for the RTX PRO 6000 Blackwell cards.
- The API under `/v1/`: submit, poll, fetch, delete, list, models, status, and
  an unauthenticated liveness check, with bearer tokens read from a file that
  is re-read whenever it changes.
- The line: one job at a time across every Consumer, in arrival order, kept in
  SQLite so a restart keeps it; position and audio minutes ahead that count
  everyone's jobs; duplicate protection; one retry after an interruption;
  results dropped after a day and job rows after a month; and a measured speed
  figure per model and diarization setting.
- The model process: a process of its own, because nothing in the engine can
  be interrupted, so cancelling a job means killing it. The same path handles
  a job past its time limit and a driver fault.
- Language detection over three windows, the whole task table, speaker
  separation with the three shapes of speaker-count hint, and word timing
  where the language can be aligned.
- Commands in the container: `selftest`, `pull`, `make-token`, `bench`, and
  `serve`.
- `models.yaml`, pinning every model to a revision, and a pull that checks
  what it fetched against those pins.
- The benchmark harness, which measures the service on an office's own
  recordings and writes its report outside the repository.
- ADR 0007: the office's own build server tracks `main` until `v1.0.0`.

### Changed

- The default model is `large-v3-turbo`, decided at the Phase 1 benchmark gate
  on the office's own recordings: about 40 per cent faster than `large-v3`,
  about 4 GB less video memory, within 3 per cent of it on words found in 13
  of 14 recordings, and right about the language on the one recording
  `large-v3` misheard, and confirmed by a reader against both models'
  transcripts of the same recordings. It stays an admin setting that takes
  effect on the next Run.
- `docs/whisperx-api.md` now carries the decisions it had left to the build.
  Nothing specified was changed; what was open is filled in and listed under
  "Settled by the build".
- CI lints and tests the service and validates its compose file on its own.

### Measured

The Phase 1 benchmark gate, run on the office's own recordings on an RTX PRO
6000 Blackwell under driver 595:

- Speed, as the service publishes it: 194 times real time for
  `large-v3-turbo` without speaker separation and 87 with it; 156 and 73 for
  `large-v3`. These replace the research's reference figure of about 70.
- Batch size 16. Above it, video memory grows about a gigabyte for every 8 of
  batch size while transcription gains under 3 per cent.
- A GPU budget of 20 GB, which is in the service README as the figure to check
  before anything else is put on the same card.
- The voice-activity thresholds ship unchanged: lowering them found no more
  speech and no more words on nine narrowband calls.
- The pinned ffmpeg identifies and decodes G.729 inside WAV on its own, and
  the forced decoder still works.

Two legs of the gate could not run and are still owed: the translation checks,
which need non-English and mixed-language samples, and the Phone preprocessing
profile, which ships only if it measurably lowers errors.
