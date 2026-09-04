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
