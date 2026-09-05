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
