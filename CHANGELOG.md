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

```
Models: unchanged
Database: migrates
```

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
