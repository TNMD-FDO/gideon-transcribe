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

## v1.81.0, 2026-09-24

```
Models: unchanged
Database: migrates
```

Phase 8 chapter 11, a note is an event, and the Event card.

- **A note on a line is an event on the chronology.** A note written on a
  transcript line of a recording that is a synced camera of an incident is
  an event on that incident's chronology, at the line's moment, with the
  writer's name ("Note by alvarez, BWC2-1"), from the moment the camera is
  synced: notes written before the recording joined included. One set of
  words in two places: Edit on the chronology changes the note on the line,
  Remove on the chronology removes it from the line, and a note changed or
  removed under the line follows to every chronology. The migration makes
  the events for the notes already written. The memo, the incident chat and
  Propose events read them as events that are the office's own notes; the
  chat's separate block of notes is gone.
- **A mark alone on the Events lane.** No words beside the marks, so
  nothing overlaps at any zoom. Hover a mark for a small card with the
  time, the line and the source; press it and every camera goes there and
  the card opens whole. Each mark takes keyboard focus; Enter opens.
- **The Chronology rows simplified**: the time, the line, a small source
  pill and the menu. The detail, seen on, rests on, the note, the why and
  the clip mark move into the same **Event card**, which the row's line
  opens; the card offers Edit, Add a note, Clip this event, Remove and Go
  to the row (Accept and Dismiss on a proposal; Open the line on a note).
- **The same card** from the focus camera's scrub-bar ticks and from the
  recording page's timeline mark of a noted line (Go to the line, Change
  the note). Escape closes it before anything else on the page.
- In passing: Back now lights the Chronology row it returns to (it looked
  for the row by the wrong attribute), and the event layer's duplicate
  element id is gone.

## v1.80.2, 2026-09-24

```
Models: unchanged
Database: unchanged
```

- **The diarizer container could not find its weights offline.** The pull
  fetches the model at its pinned revision, but NeMo's own loader asks the
  cache for "main", which a fetch by revision does not record, and with the
  network off that is a refusal. The container now opens the model file at
  the pinned revision itself. Found at the v1.80.1 upgrade. The rebuild is
  from cache except the last layer: `./transcribe upgrade v1.80.2 --build`.

## v1.80.1, 2026-09-24

```
Models: unchanged
Database: unchanged
```

- **The diarizer container failed to start** on a server where the app's
  account has no name inside the image (only a number): NeMo's start-up
  asks torch for the account's name and its compile cache, and torch
  refused with `getpwuid(): uid not found`. The image now names the
  account and the cache folder itself. Found at the v1.80.0 upgrade; the
  image is rebuilt by `./transcribe upgrade v1.80.1 --build`, from cache
  except its last layer.

## v1.80.0, 2026-09-24

```
Models: changed
Database: unchanged
```

Phase 5 chapter 4, the diarizer. The model that tells voices apart is now
a choice, and the default is new.

- **Nemotron 3 Diarization is the diarizer** on a fresh install and after
  this upgrade: NVIDIA's open model, not gated, no Hugging Face token, up
  to eight voices. It runs in a third container of its own, `diarizer`,
  built from this repository beside the WhisperX service and called by it
  on the service's private network (ADR 0014). pyannote community-1 stays
  in the package, one Panel setting away.
- **Diarizer** on the Panel's Transcription defaults page: `nemotron` or
  `pyannote`. The next recording transcribed follows the change; nothing
  already transcribed changes.
- **The speaker-count hint is pyannote's alone.** Under Nemotron the
  Upload page's Speakers box is greyed with the reason, the app sends no
  hint, and a stored hint is kept unused. The stretch embeddings a Live
  recording asks for are pyannote's too.
- **Where it shows.** A recording's Details tab and the exports'
  processing record say "Voices told apart by Nemotron 3 Diarization" or
  "by pyannote community-1". The Status page's WhisperX block lists which
  diarizers are installed.
- **The service** is 0.3.0: the request gains `diarizer`, a hint or
  embeddings sent with `nemotron` are refused (`hint_not_supported`,
  `embeddings_not_supported`), a Nemotron job while the container is down
  is refused with `diarizer_unavailable`, and `settings_used` names the
  diarizer and its version. `pull` fetches the Nemotron weights (about
  0.45 GB) and, without a token, skips the gated pyannote model and says
  so instead of failing.
- **The Hugging Face token is optional at install**: an office gives one
  to have pyannote as well.
- **Three images** are built and published now: `app`, `whisperx` and
  `diarizer`, each pinned by tag and checked by digest at upgrade. The
  first build of the diarizer image on the server takes a while; the
  upgrade's build floor of 40 GB free applies.
- After this upgrade, at the maintainer's word, the recordings of two
  cases are processed again so the office can judge the new diarizer on
  footage it knows: the operator's act, not a feature.

## v1.79.0, 2026-09-23

```
Models: unchanged
Database: migrates
```

Phase 8 chapter 10, the sitting on the case page.

- **The Incidents tab's row carries the bar in small.** A column, "The
  assistant holds", after Cameras: the figure ("5½ of 7½ hours' worth"), a
  thin bar with one block per camera, and a word on the right: "all 12
  whole", or "3 cameras by words alone" in amber, or "does not fit". The
  row's hover carries the incident page's sentence. The column is absent
  while the assistant or Incidents is off.
- **The offer shows the bar before the incident exists.** "12 videos ran
  at the same time" gains the bar as the incident would read with those
  videos in, and the offer to add one later video to an incident shows the
  bar with the video in. Nothing is withheld for size.
- **Each camera's share is kept on the camera** (`record_tokens`,
  `words_tokens`, `record_made_at`, migration 0059) and counted again when
  its Digest is newer, so a case page draws the bar without reading a
  Digest, and the incident page's bar is drawn from the same figures.
- The incident page's bar now comes from the kept shares by the same
  longest-first arithmetic the real reading follows, rather than fitting
  the record itself on every draw.

## v1.78.0, 2026-09-23

```
Models: unchanged
Database: migrates
```

Phase 8 chapter 9, One sitting, from the walk of a real twelve-camera
incident on 2026-09-23, where Compare with the report, Ask Gideon and the
memo each refused the incident as too long.

- **The bar on the Cameras tab.** "How much the assistant can hold at
  once": one block per camera, the longest the widest, in hours of camera
  against what the engine can hold at once, with a sentence for each zone
  that says what changes for the person: room for about N more cameras;
  nearly full; more than one sitting. The same bar on the Add cameras
  dialog reads as it will with the ticked cameras in. Adding a camera is
  never refused for size.
- **Everything said is always read.** When the whole incident does not fit
  the engine's window, the longest cameras are read by their words alone
  (their transcript in place of their Digest), longest first, until it
  fits; before this release a Digest was never given up and the call
  failed at once. The memo, the incident chat and the comparison share the
  one fit, and each says what it read: "everything said on 12 cameras and
  what 7 of them showed; 5 cameras by words alone", on the memo's head
  line and its Word export, the comparison's state line, and Gideon's
  panel. **Always read what it showed** on a camera pins it into the
  sitting; the next longest moves to words alone instead. The Proposed
  events layer names cameras no run has read.
- **The engine's window, read from the engine.** The llm-worker's minute
  check reads the served model's `max_model_len` and every fit and every
  bar uses it; the Panel's Engine window setting is the fallback while the
  engine does not say, and its row greys with the engine's figure. The
  Status page says which is in force and counts the readings refused as
  too long. On the office's copy the engine reports 262,144 tokens, twice
  the setting, so the record refused on 2026-09-23 fits from this release
  without a camera going to words alone.
- Audit: Camera pinned and Camera unpinned rows; every AI assistant call
  row carries `window_source`, and the memo's, the chat's and the
  comparison's carry `words_alone`. Migration 0058.

## v1.77.0, 2026-09-23

```
Models: unchanged
Database: unchanged
```

Phase 8 chapter 8, the event's line and the merge hint's rule, from the
end-user walk of 2026-09-22.

- **An event is one line; the rest is under it.** Wherever an event is
  drawn, its text is read as a line and a detail: the line is the text up
  to its first line break, or its first sentence when the text runs past
  120 characters; the detail is everything after, shown on the muted line
  under the event before its source. The four-line camera descriptions
  accepted as events before the proposer was asked for one sentence now
  read as one line each, with the description under them, and no data
  changed. The event box is a box of lines: Enter starts the detail,
  Ctrl+Enter saves. The Word export prints the detail under the line in
  the smaller type, the spreadsheet gains a Detail column after Event, the
  Events lane's labels and a clip's title from an event use the line, and
  the memo reads the whole as before.
- **The merge hint names a neighbour or nobody.** On the Speakers page the
  merge is offered only to a fragment (at most eight lines, under thirty
  seconds, never over anyone else) whose lines sit inside one speaker's
  turns: more than half of them within three seconds of that speaker's
  line before or after. The hint names that neighbour, not the busiest
  speaker, and reads "Never speaks while Officer does, and its 2 lines sit
  inside Officer's turns". A fragment with no neighbour reads "2 short
  lines, never over anyone else's; see the lanes." and gets no button.
  Five bystanders are no longer each offered a merge into the officer.

## v1.76.0, 2026-09-23

```
Models: unchanged
Database: unchanged
```

Phase 8 chapter 7, the pages that fail well: four things the end-user walk
of 2026-09-22 met that needed a design rather than a line.

- **A session that ends under an open page is said on that page.** When
  the app answers a page's script that the session has ended (a small
  reply and the status 401, never the sign-in page), the page stops every
  poll, pauses its videos, greys its controls and shows one line where
  the idle warning sits: why it ended (a long wait, a sign-in from another
  place, an Admin) and what stays (cases, clips and documents; or, with
  Folder management off, that the recordings and transcripts have been
  removed). Nothing is asked of the server again, so a page left open
  overnight shows the line in the morning with no errors under it.
- **Sign in again returns you to where you were.** The line's button goes
  to Sign in with the page's address, tab and moment, and the sign-in page
  brings the same person back there; somebody else signing in lands on
  Start, and an address outside the app is ignored.
- **The idle warning asks before it claims.** At nought the page asks the
  server once whether the session is still open, with a question that
  does not move the clock, so a second tab that kept the clock moving no
  longer makes the first say you were signed out.
- **The gone page.** An address with nothing behind it is answered in the
  app's frame: why it might be gone, and the way back (the case by name
  when it is one you may see, Cases, My recordings, the Panel, Start). It
  never says whether a case exists that you may not see. The server's own
  failure and a form left open too long (or sent after a sign-in in
  another tab) get the app's pages too, in place of the framework's.
- **The Admin's warning is a pill beside the title.** On another person's
  case, incident, recording, Speakers page or recordings list the band
  across the page becomes **As an Admin** beside the title: hover shows
  the whole sentence, a press opens it in a small card. Every word stays.
- **The case page's list takes the width.** The cap on the page goes and
  About this case takes a measure of 24rem at the right, so a file name
  stays on one line.
- **Fixed**: v1.75.1 wrote the page's Admin mark with stray backslashes,
  so the Speakers page's cut-short advice showed Admins the non-Admin
  line.

## v1.75.1, 2026-09-23

```
Models: unchanged
Database: unchanged
```

The fix release from walking the app as a new user on 2026-09-22 (the
findings report of that walk lists every item).

- **The incident transport's Sync button opens the Sync sheet again.** It
  had tested the wrong thing since the layers release and always took the
  close branch; the Cameras tab's Sync was the only way in.
- **The recording page loads clean.** The case script, loaded on every
  page while cases are on, tried to bind the incident box that only the
  case page has and stopped with an error.
- **The Report tab on a recording stands on its own switch**, so an office
  with Clips off still sees its reports.
- **The Gideon button always says why it is greyed**: the engine
  unreachable, the chat off for the office, or no transcript yet.
- **Words**: the Start tile tells an Admin who owns no case how many the
  office has; the sign-out page says what stays rather than "nothing here
  to remove"; the case page's Speakers tab reads "0 named" beside rows of
  unnamed speakers; the Type column is shown only when a recording has a
  type; the Admin banner names the person and says "case" for a recording
  in one; the incident's Details and the Status page use the app's one
  date style, and the Status page's speeds have one decimal; the Queue
  shows people's names; an empty Clips page drops "0.0 MB in all"; the
  keeping rule is said once on My recordings; the speaker check's
  cut-short advice about the Panel is shown to Admins alone; the user
  guide's Notes and Speakers sections are separated and its Chat tab
  section now describes Ask Gideon.
- **Reading**: the said band marks the first line "next" before anything
  is said; a comparison row shows the first lines of its paragraph and
  the card the whole; Find's memo hits and Search's document hits show the
  sentence with the words, not the paragraph; the speaker merge hint is
  offered to a small speaker alone, not to everyone who never overlaps the
  busiest.

## v1.75.0, 2026-09-22

```
Models: unchanged
Database: unchanged
```

Phase 8 chapter 6: the report in place. From the maintainer's first real
comparison: a citation to the report took the reader to the document's
page and away from what they were reading.

- **The paragraph card.** A press on any citation to a paragraph opens a
  card in place, under the citation: the document's title and "page N,
  paragraph M" (and "read by OCR" when the page was), the real page picture
  scrolled so the paragraph is in view with its box lit, the paragraph's
  words with the paragraph before and after in muted type, then **Open the
  document**, **Copy the citation** and **Close**. One card at a time;
  Escape, a press outside it or on the citation again closes it; the page
  under it never moves. The same card opens from Gideon's answers (in place
  of the words-only preview), the comparison's rows, a chronology row that
  rests on a paragraph ("rests on page 4, para 2"), and a document hit on
  the case page's Search tab.
- **The comparison's export where exports are.** Comparison to Word is in
  the incident page's and the recording page's Export menus, greyed with
  "compare with the report first" until a comparison is done, and on the
  case's Documents tab row of a report that has one. The link beside
  Compare again stays.
- **The Report tab says where the comparison is.** Once one exists, the
  button reads "Open the comparison, 5 findings" instead of "Compare with
  the report", which read as a second run.
- **A handle on Gideon's panel.** Drag its left edge from 360 pixels to six
  tenths of the window; remembered in your browser for every page the
  panel opens on; a double-press puts the usual width back; the arrows move
  it from the keyboard.

## v1.74.2, 2026-09-22

```
Models: unchanged
Database: migrates (0057, two columns on the comparison)
```

- **The comparison reads the engine's answer.** The first real comparison
  came back with nothing: the engine wrote its findings inside a Markdown
  code fence (```json ... ```), and the app threw every answer away as
  unreadable. The app now takes the fence off, and anything before the
  first brace, before it reads.
- **An empty comparison says why.** The state line counts the answers the
  app could not read and the findings it dropped, by reason ("3 findings
  dropped: paragraph not found 2, no time on the clock 1"), and the
  Comparison run audit row carries the two counts. The worker's log says
  the shape of an unreadable answer, never its words.

## v1.74.1, 2026-09-22

```
Models: unchanged
Database: unchanged
```

- **The panel stays in a Grid.** Grid, 2, 3 or 4 across no longer moves the work panel under the strip; the cameras take that many columns beside the panel, and the handle gives them more room when wanted. From the maintainer's first use of v1.74.0.
- **The Chronology tab's first line** ("4 events on the chronology") keeps its width and lets the buttons wrap under it, instead of being squeezed beside them on a narrow panel.

## v1.74.0, 2026-09-22

```
Models: unchanged
Database: unchanged
```

Phase 8 chapter 5: the desk, kept. The incident page as it stands, with
four things added to it and nothing taken away.

- **The focus camera is a video.** In Focus the large picture sits at its
  own proportions, and a player bar appears on it when the pointer is over
  it or the cameras are paused: a scrub bar across the whole incident with
  the events as ticks and this camera's own stretch shown, play, back and
  forward five seconds, the time, the speaker, the speed, and Fill the
  window. Each does what the transport's control of the same name does,
  and the keys are unchanged.
- **What is being said.** Under the filmstrip, the focus camera's words
  following the clock: the line being said lit, two before it and one
  after. Press a line and every camera goes there; on the lit line,
  **+ event** and **Clip from here**. Change the focus and the words follow.
  **Open the transcript** opens the recording at this moment.
- **Clip is a button.** **Clip** on the transport marks the start at this
  moment and becomes **End the clip here**, with the span so far drawn on
  the scrub bar, the strip and the Clips lane as it grows; the second press
  opens the clip box filled in (the title from the one event inside the
  span, when there is one). Escape cancels. Under the strip's ruler a
  **clip track** says in words what it is for: drag across it and the box
  opens with that span, with a tag that follows the pointer; a press on it
  seeks. A **Clips lane** under Events shows every clip made from the
  incident, a press opening the case's Clips tab. Every way in ends in the
  same box, and the audit row says which way ("from the button", "from the
  strip", "from a line", "from an event"). With incident clips off, the
  button and the track stay, greyed, and say so.
- **A handle sizes the work panel.** Drag the grip between the cameras and
  the panel from 360 pixels to six tenths of the desk (the cameras never
  under 420); it is remembered in your browser, a double-press puts the
  usual width back, and the arrows move it from the keyboard. Under 400
  pixels the tabs show their icons alone, with the names on hover.
- The strip's paragraph of instructions is behind a **?** at its foot.

## v1.73.0, 2026-09-19

```
Models: unchanged
Database: migrates (0056, a table for comparisons)
```

Phase 8 chapter 4, part 3 of 3: the comparison. The police report set
beside what the cameras recorded, every finding cited on both sides.

- **Compare with the report**, on the Report tab of the incident page and
  of a recording's page. The assistant reads the report in windows of
  pages against the incident record and the chronology (or the recording's
  transcript and digest) and gathers findings: one row each, the report's
  paragraph and the record's moment both cited, marked **Agrees**,
  **Differs**, **Not on camera** or **Not in the report**, with one line of
  why. A finding that names no real paragraph, or no real moment where one
  is needed, is dropped by the app. What the report leaves out is asked once
  against the whole report, so an event mentioned anywhere is not a finding;
  when the report is too long for that check the state line says so.
- **The comparison as a layer** over the incident page's Report tab, and as
  a block under the document on a recording's page: the state line ("2
  pages against 1 camera; 4 findings: 1 agree, 1 differ, 1 not on camera, 1
  not in the report"), the four marks as pills that filter, and on each row
  the paragraph as a citation that opens the page, the moment as a citation
  that plays every camera, the why, **Note**, **Dismiss** (and Undo). There
  is no Accept all: a person reads the rows.
- **Make it an event** puts a finding on the chronology at its moment with
  the claim as its line, source "From the report", resting on the paragraph
  (shown under the event), the mark as its why and the note carried; a Not
  on camera finding opens the event box so a person picks the moment. The
  memo reads the paragraph an event rests on.
- **Comparison to Word**: the cover with the document, the cameras and the
  counts, then one table of the findings with their notes.
- **Kept and stale.** One comparison per report and home, replaced by
  Compare again, and marked stale when the chronology or the cameras change,
  as the memo is. A new Comparison template is on the Templates page.
- **Settings**, on the Documents page: Compare with the report (On, needs
  the assistant), Comparison answer cap (3,000 tokens), Comparison time
  limit (600 seconds). Audit rows: one AI assistant call for the run
  counting its calls, Comparison run with the counts, comparison exported; never a word of the
  report or the record.

## v1.72.0, 2026-09-19

```
Models: unchanged
Database: migrates (0055, one column on documents)
```

Phase 8 chapter 4, part 2 of 3: the Report tab and Gideon's citations, with
three cleanups from the first day's use of part 1. Part 3, the comparison,
follows.

- **Gideon reads the report.** The incident's Gideon reads the report linked
  to the incident after the chronology; the recording page's Gideon reads
  the report linked to that recording after the transcript; the case page's
  Gideon reads every report in the case. Each is given as numbered
  paragraphs, and an answer cites "[Report, page 4, paragraph 2]". Press the
  citation and the paragraph shows under the answer with the one before and
  after in the muted colour, the document's title and page, and **Open**,
  which goes to the page with the paragraph lit. A citation that names no
  real paragraph stays plain text. The rules say the report is the officer's
  account and the cameras are the record, to say which says what, and to
  cite both where they differ.
- **The reading ceiling.** A new setting on the Documents page (400
  paragraphs). Under it the linked reports are read whole with every
  question; past it, only the paragraphs whose words match the question are
  read, and the answer ends "(Read 40 of 310 paragraphs of the report, those
  matching the question.)". Nothing is silent.
- **The Report tab**, on the incident page's work panel and the recording
  page's work area, only while a report is linked there: the document's
  pages at the panel's width with the words under each, a paragraph lit from
  either side, Open and Download.
- **Adding from the Documents tab.** Add the report is on the tab as well as
  on the two Details tabs; the page asks what the report is for, an incident,
  a camera, or both, and arrives with the choice made when it came from a
  Details tab. A report is never loose.
- **Re-link is a row**, two plain choices and a button on the document's
  row, instead of a menu that a scrolling table clipped.
- **Ways back** from the document page: the case's name at the top left,
  and Back to the incident or Back to the recording beside it.
- **Read again.** A document read before the paragraph rule was tightened
  (a bullet's second line is no longer split off) is read again by itself
  within a minute of the upgrade; nothing to do.

## v1.71.0, 2026-09-19

```
Models: unchanged
Database: migrates (0054, two tables for documents and their pages)
```

Phase 8 chapter 4, part 1 of 3: Documents beside the cameras. The police
report that corresponds to the body-worn cameras, added to the incident or
the camera it is about and read page by page. Parts 2 (the Report tab and
Gideon's citations) and 3 (the comparison) follow.

- **Add the report**, on the incident page's and the recording page's
  Details tab, and nowhere else: a document is the report for that incident
  or that camera, never loose in a case. The page says what fits before a
  file is chosen: PDFs only, the report for this incident or camera and
  nothing else, up to 60 pages (the Admin's figure), a scan is read by OCR
  and its words may carry mistakes, nothing leaves the building. A file
  that does not fit is refused with the reason.
- **Read at upload**, on the media queue: each page's words with their
  positions, a page without words of its own read by OCR (Tesseract,
  English) and marked so, a page the OCR read poorly said so, the words
  split into numbered paragraphs by the gaps on the page, every page drawn
  to a picture.
- **The Documents tab** on the case page, with the count: every document,
  its pages ("42 pages, read by OCR, 3 poorly read"), what it is the report
  for, who added it, and Open, Re-link and Remove. Both Details tabs list
  their reports.
- **The document page**: the page pictures down the middle, the words of the
  page in view beside them paragraph by paragraph with their numbers, a page
  box, Find within the document, Download. A press on a paragraph's box on
  the picture lights its words and the other way round; a citation opens
  the page with the paragraph lit. A page read by OCR says so; a poorly read
  page says to read the picture.
- **Search** gains a Documents kind: one hit per paragraph, opening the page
  with it lit.
- **Nothing new to install.** The PDF reader, the page renderer and the OCR
  engine are in the app image, pinned, on the CPU; the image grows by about
  a hundred megabytes for the OCR engine and its English data. Settings on
  a new Documents page of the Panel: Documents (On), Largest document (60
  pages), Documents per incident or recording (3), Read scans with OCR
  (On). Audit rows Document added, Document re-linked, Document removed,
  never with a word of a page.

## v1.70.0, 2026-09-19

```
Models: unchanged
Database: migrates (0053, a table for reports)
```

Phase 8 chapter 3: Report a problem. From the maintainer's list of
2026-09-19 ("bug report button").

- **Report a problem**, a small link at the right of every page's foot (on
  the incident page, in the work panel's head beside Find), opens the app's
  own box: **A problem** or **An idea**, what happened (or what would help)
  and what you expected, in your own words. **Include where I was**, ticked,
  adds the line shown under it before you send: this page's address without
  its search words, the Release, the browser, the window's size and your
  name. Nothing else, no screenshot, never a transcript's words. Send says
  "Thank you. Your report went to the Admins." and nothing leaves the
  building.
- **The Panel's Reports page**, beside Status: every report, newest first,
  New before Seen before Done, with a filter and **Seen** and **Done** on
  each row; the whole words fold open on a press. The rail carries the count
  of New reports as a badge, and the Status page a line while any is new.
- **The Operator's copy.** When mail is configured and the Operator address
  is set, each report also goes to that mailbox as the app's own mail, with
  the words and the where line and a link to the Reports page; the Panel is
  the record whether or not the mail goes.
- **Housekeeping.** A Done report is removed ninety days after its mark by
  the daily sweeper. A new setting, **Reports** on the Features page, is on;
  off hides the link and refuses new reports, keeping the page for Admins.
  Audit rows Report made, Report seen, Report done and Reports swept, never
  with a word of the report.

## v1.69.0, 2026-09-19

```
Models: unchanged
Database: migrates (0052, three columns on a transcript's segments)
```

Phase 8 chapter 2: Notes. From the maintainer's list of 2026-09-19 ("notes
in transcript"), under the rules an event's note already has.

- **A note on a line.** On the recording page every line of the transcript
  has **note** beside edit and clip start (or N on the line being played).
  A small box opens under the line: your own words, up to 2,000 characters,
  Save and Cancel, Ctrl + Enter and Esc. The note shows under the line in
  italics with the writer's name and the date; press it to change it, and
  save it empty to remove it, after a question. Whoever may correct the
  transcript may write a note; the writer is whoever last wrote it. A small
  mark on the timeline shows where the noted lines are.
- **Nothing leaves by default.** Export to Word, Export as text and Captions
  are unchanged and never carry a note; two new entries, **Export to Word,
  with notes** and **Export as text, with notes**, appear only while a line
  has one. A clip's excerpt and captions never carry a note.
- **The Notes tab** on the case page, between Clips and Speakers, with a
  count: every note in the case, on lines of transcripts and on events of
  chronologies, newest first, each a citation that opens where the note was
  written (with **all cameras** when the recording is a synced camera).
  **On lines** and **On events** filter it; **Search notes** opens the Search
  tab on notes; **Download notes** is a Word document of them all, for the
  office's own reading.
- **Gideon reads the notes and never writes one.** On the case page each
  recording's notes are given after its words as the office's own; on the
  incident page the notes on the synced cameras' lines, on the incident
  clock. The Summary, the memo and Propose events do not read them.
- **Search's Notes kind and Find** read the notes on lines with the notes on
  events.
- **Processing again** carries every note to the new transcript's line at
  its moment, so nothing is lost.
- **Audit rows** Note added, Note changed, Note removed and Note carried,
  under Edits beside Segment corrected, never with a word of the note; an
  export with notes says so in its row. No setting.

## v1.68.0, 2026-09-19

```
Models: unchanged
Database: unchanged
```

Phase 8 chapter 1: the pages laid out. From the maintainer's list of
2026-09-19 and the picks made from the mock-ups the same day.

- **The incident page's work panel is tabs and layers.** The tabs
  (Chronology, Memo, Cameras, Details) are what is always there; a job in
  hand (Proposed events, Sync, an event, a clip, Find) opens as a layer
  over the tab, with the same head on every one: Back with the tab's
  name, the layer's name, its main button. Back or Escape returns exactly
  to the tab, its scroll and the row you had marked; a clip opened from
  an event goes back to the event first. The wall and the strip never
  move: the sheets that opened above the wall are gone.
- **The Chronology tab holds the events, with air.** One line for what
  happened, one muted line under it for the source, the cameras, the
  note, the why and the clip mark; Edit, a note, Clip this event and
  Remove behind the row's menu. Propose events is a button with the
  count waiting; About is one line.
- **Proposed events** is a layer: Propose again, the Look for box, the
  state line, Accept and Dismiss on each row, Accept all in the head.
  **Find's hits** are a layer that names what each hit is and marks the
  words.
- **Gideon is one panel, the same on the three pages that have it.** It
  floats over the page's right edge, 420 pixels, the page unchanged
  beneath it; the Ask button reads Close while it is open; an arrow in
  its head opens it in a window of its own that follows the page. The
  Gideon tabs on the case page and the recording page are gone; the
  panel holds the same conversations.
- **The tabs everywhere are a bar of sections**, an icon and a count
  each, the open one drawn as a card joined to its content: the case
  page, the recording page's work area and the incident page's panel.
- **The recording page** shows the case's recordings and Download all
  transcripts in a card under the video, eight at a time with "and N
  more"; the column below the transcript that held the same list, and
  its hide button, are gone.
- **The Start page's tile** reads Cases, with the counts under it.
- **Widths.** The incident page's wall shows 3 cameras across from 1900
  pixels, 4 from 2560 and 6 from 3840 in the Side by side layout; the
  work panel grows to 760 from 2560; from 3840 a Two panels button puts
  the Memo beside the Chronology; the case page's About pane widens from
  2560. Nothing is remembered per screen. The three-column case and
  recording pages the chapter names for 2560 and above are not in this
  release; see the chapter's notes.

## v1.67.0, 2026-09-19

```
Models: unchanged
Database: migrates (0051: a conversation may belong to an incident)
```

Phase 7 chapter 5: Gideon, the chat with a name, a place of its own, and
the incident's chat. From the maintainer's list of 2026-09-19 and the
name chosen the same day.

- **The chat is called Gideon** on every page: the tab on the case page
  and the recording page, the Ask button, the drawer's head, and a
  conversation's export title ("Gideon: <the first question>"). The name
  is an Appearance setting, **What the chat is called**, so an office
  names its own; empty falls back to Chat. Code, settings, file names and
  the audit log keep the word Chat. Gideon the chat is not GIDEON the
  engine.
- **Ask Gideon**, a round button at the bottom right of the case page,
  the recording page and the incident page, opens a drawer beside the
  page (a third of the window, the whole window on a narrow one) so a
  person asks while reading. On the case page it holds the case's
  conversations; on the recording page it takes the page's own chat
  panel in and gives it back on Close; on the incident page it holds the
  incident's. Escape closes it; open or closed is remembered per person.
  Greyed with the reason while the engine is off.
- **A cited moment plays where you are.** Pressing a citation in a case
  chat answer plays the recording in a small player under the answer,
  from ten seconds before, with the line and the recording's title, and
  Open for the viewer or All cameras for a synced camera. On the
  recording page a citation seeks the page's own player, as before.
- **The incident's Gideon.** Asked from the incident page, it reads the
  incident record (the cameras' Digests merged onto the incident clock)
  and the chronology with its notes and About, and nothing else, in the
  investigator's voice of the Incident chat template. Every time in an
  answer is a citation on the incident clock; pressing one seeks every
  camera there. Its conversations belong to the incident and go with it.
  Settings **Incident chat** (On), its answer cap (2,000 tokens) and time
  limit (300 seconds) on the Incidents page; the Incident chat template
  on the Templates page.

## v1.66.0, 2026-09-19

```
Models: unchanged
Database: unchanged
```

Phase 6 chapter 5: Sync as one control, and the clip from the strip. From
the maintainer's list of 2026-09-19.

- **Sync, one button.** Sync in the transport, beside Layout, opens a
  sheet with one row per camera: its clock as read from the picture, its
  place, who synced it, a tick and its controls. The tile's Sync and the
  Cameras tab's Sync open the same sheet on that camera's row; the inline
  box on the tile and the Cameras tab's own match controls are gone.
- **Sync all** has the app do the rounds on every camera not yet synced,
  in the order that works: from its clock when the read was checked, then
  from its clock read once, then matched by sound against the synced
  camera it overlaps most, and only then "needs a hand". **Sync ticked**
  redoes the ticked cameras, synced or not. The sheet says "Syncing 6
  cameras: 3 from their clocks, 1 matching the sound, 2 need a hand" and
  keeps asking while a match runs.
- **Every failure has a next step** on the row: no clock in the picture,
  the clock not read yet, the clock read once (with Listen, which plays
  the camera with a synced one from the first moment they run together),
  no match with the reason, no camera in step to match against, Match by
  sound off. The nudges, Type a time, From its file and Match the sound
  sit on the row.
- **A clip from the strip.** Drag across the strip's ruler and the clip
  box opens with that span, no event needed; every camera running inside
  it is ticked. A camera not synced is offered too, with the warning that
  it is cut at its guessed place, so its tile may not play in step. The
  clip's line reads "from the strip, 21:57:02 to 21:57:40" on the Clips
  tab and page and in the Chronology's Word export. An event's clip keeps
  its rule that the camera must be synced.

## v1.65.0, 2026-09-19

```
Models: unchanged
Database: unchanged
```

Phase 7 chapter 3: the case dashboard line, search across a case, and
Find on the incident page. From the maintainer's list of 2026-09-19.

- **The dashboard line.** Under the case's name, one line of pills for
  everything in the case that has a state: transcribing, in line,
  preparing, enriched tonight, an incident not synced, events to check,
  proposed events waiting, a memo writing or with newer events, clips
  rendering or failed, shared with, deletes in N days. Each pill is a link
  to where it is dealt with. Nothing pending shows nothing. On the
  Recordings tab it refreshes with the rows.
- **Search is a tab of its own**, second after Recordings, and the box
  leaves the recordings list. It reads six kinds, offered as filters when
  they have hits: the words of every transcript and its speaker names,
  every incident's events with their why and About, the notes on events,
  every memo and every summary paragraph by paragraph, and every clip's
  title. Hits are grouped by the recording or the incident they live in,
  in time order, the words marked. A words hit plays in the viewer, with
  "all cameras" when the recording is a synced camera; an event hit opens
  the incident page at that moment; a memo or summary hit opens the tab
  with the paragraph lit; a clip hit lands on its row. Words in any order,
  a phrase in quotes for an exact match, the first two hundred of a kind.
  Phase 2's `?q=` on a case's address opens the tab. The term is never
  logged. Measured on the office's largest case, a search takes
  milliseconds; no index was needed (`docs/research/case-search.md`).
- **Find on the incident page.** A box in the work panel's head. It reads
  the synced cameras' words, the chronology's events and the memo, and
  every hit is a moment: pressing one seeks every camera there, brings the
  camera it was heard on to the front and gives it the sound. Enter goes
  to the next hit, Shift+Enter to the one before, Escape clears. A small E
  on a words hit opens the event box at that moment with the line filled.
  A camera not synced is not searched, and the box says so.

## v1.64.0, 2026-09-19

```
Models: unchanged
Database: migrates (0050: the why line on an event; what the last run cut,
what the watch phrases found and the Look for on an incident)
```

Phase 7 chapter 2: the assistant's judgement, and the watch phrases under
it. From the maintainer's finding that a line saying "I got, I got gun"
went unproposed: the run had proposed 87 events across six cameras with
five answers cut off at the cap, most of them descriptions of the picture.

- **Propose events asks for judgement.** The shipped Proposed events
  template now asks the engine to read one camera as an investigator for
  the office that defends the accused, to propose the moments that could
  matter to the case in one plain sentence each, in its own words, and to
  say **why it matters**. The why shows under each proposal, on the lane's
  hover, and prints in the exports under an accepted event. Measured on
  the camera that missed the line: 31 proposals for 47 minutes, none
  cut short, none narrating the picture, the gun line among them with its
  reason (`docs/research/event-spotting.md`).
- **Room to think.** A camera is read in windows (**Proposed events
  window**, ten minutes), one call each, up to twelve proposals a window,
  and each window gets a **Second look** (a switch, On): the engine reads
  it again against what it proposed and adds what it left out. Where an
  answer is still cut short the state line says so.
- **The office sharpens the judgement.** **About this office and case**,
  a setting under The assistant, is given to every run as context; a
  **Look for** box beside Propose events is given to one run alone and
  never kept.
- **Watch phrases, the floor.** A list in the panel of words the office
  always wants an event for, shipped with a default list (weapons, force
  and injury, commands and rights, consent and search, admissions and
  threats, drugs, identification). On every run the app itself searches
  each synced camera's transcript, and its record's picture lines, for
  them before the engine is asked, whole words and any case, and proposes
  an event at every line that carries one with the source **Watch
  phrase**, so the office can see which finds came from the judgement and
  which from the search. With the assistant Off, the run is the search
  alone. An empty list loses nothing of the finder.
- **Accept while the run is going** is refused, as v1.63.2 has it, and the
  buttons show greyed.
- **The memo re-shipped** in a seasoned investigator's voice: what
  happened, who did what, pointing at the time, the camera and the event
  number, never narrating the footage. Same sections. An office that
  edited either template keeps its edit; an unedited one follows the new
  wording.

## v1.63.2, 2026-09-19

```
Models: unchanged
Database: unchanged
```

Seven fixes from the maintainer's list of 2026-09-19.

- The case page's Clips tab says how many clips on every tab, not only
  while it is open.
- Check and start on the Upload page: a long file name breaks inside the
  table instead of running past the card's edge.
- While a batch uploads, each file's card takes the batch's own words once
  the file is up (Checking the file, Preparing the audio, In line,
  transcribing, Done), asked for every few seconds, and the page says it
  is opening the batch before it goes.
- While the assistant is still proposing events, Accept, Dismiss and
  Accept all show greyed ("The assistant is still proposing"), and the
  server refuses them; a proposal accepted mid-run was proposed again by
  the cameras read after it.
- The incident strip zoomed in: a camera's bar is drawn only for the part
  inside the window, so the events and the playhead are no longer left
  behind past the track's edge; the wheel over the lanes, or the arrows
  beside the zoom buttons, move along the strip, and the window follows
  the playhead again once it plays out of view.
- The audit log's write is serialised (an advisory lock on the chain), so
  two workers writing in the same instant no longer both link to the same
  row. The Integrity check knows that shape from before (two rows written
  within seconds that both link to the row before them, both verifying),
  names the pair, and carries on rather than calling the chain broken.
- The transcript's Follow: after a line is clicked, scrolling away no
  longer fights the reader. The follow resumes only once the line being
  spoken has left the screen and been scrolled back into view; Resume on
  the pill remains the way back at any time.

## v1.63.1, 2026-09-17

```
Models: unchanged
Database: unchanged
```

From the maintainer's first use of Clip this event: it was not clear why
the button was missing, where the clip went, or whether it finished.

- The event's row now says where its clips stand, as a link to the case's
  Clips tab: "1 clip, rendering", then "1 clip ready", or "1 clip failed"
  (and "2 clips, 1 rendering" and the like). The incident page keeps asking
  while a clip renders, so the words change by themselves.
- On an event none of whose cameras is synced with a playback copy, Clip
  shows greyed with "Sync a camera first", instead of not at all.
- The words after Make the clip say where it lands and that the row will
  say when it is ready.

## v1.63.0, 2026-09-17

```
Models: unchanged
Database: migrates
```

Phase 7 chapter 1 (`docs/spec/SPEC-PHASE-7.md`): the chronology as a
document, and the clip across cameras.

**The chronology as a document.** Every event takes a **Note** in a person's
own words (up to 2,000 characters, folded under the Note button on the event
box) and a **To check** mark for a point the office has not settled; the
Chronology tab shows the note under the event with the writer's name and the
mark as a pill, and counts the marks in its head line. **About this
chronology**, one paragraph before the events, is edited at the top of the
tab. The Word export prints About on its cover, each note in italics under
its event, "(to check)" beside the event's number and a count line under the
table; the spreadsheet gains Note and To check columns. The memo and the
proposals are told the notes and About as the office's own words, which the
incident rules now say the assistant respects and never rewrites, and where
an event is marked to check the memo says the office has not settled the
point; the memo's stale mark covers them. An accepted proposal edited by a
person keeps its source, and only Accept makes an event the assistant's.
The note keeps its writer's name whoever edits the event afterwards; in
the Note field Enter saves and Shift+Enter starts a new line.

**Clip this event.** On the event box (Edit) and as a Clip button on each
event's row, while Incidents, Clips and the new Incident clips setting are
on: the clip box offers the span from ten seconds before the event to ten
after, the event's cameras ticked (a camera the span falls outside greyed
with "not running then"), Focus or Grid starting from the page's layout, the
sound from the camera the page hears, the clock and the camera ids burned in,
and the event's text as the title. One file is cut on the media worker by
ffmpeg: each camera from its own moment on its own clock, scaled into its
tile without distortion, the tiles stacked 1280 wide (Focus: one at 1280 by
720 with up to four 320 by 180 under it; Grid: two across at 640 by 360 up to
four, three across at 426 by 240 up to nine), a camera that ends inside the
span or starts inside it black in its tile with its id, silence where the
sound camera was not running, the incident clock top right as hh:mm:ss
running, each camera's id bottom left in the captions' typeface. The clip is
a Clip like any other on the case's Clips tab and the Clips page, in the
case's group, with a Cameras column ("2 cameras, Focus") and "from the event
..." under its title, and Open the incident in place of Open in viewer; its
picture (the cameras with their offsets and ids, the layout, the sound, the
burn choices, the clock's second) is copied when it is made, so Render again
remakes it the same whatever is re-synced or renamed afterwards, and a
camera whose playback copy is gone fails the render plainly rather than
painting a black stand-in. The Chronology tab's event row shows "1 clip";
the Word export lists the clips made from events under the table. Incident
clips render one at a time on the media worker; the time limit is the Clips
chapter's plus a minute per camera. Adjust is not offered on an Incident
clip (its span is its event's; a new clip changes it), and the viewer's own
Clips sheet, which plays one recording, does not list it. Without an
incident clock the clock is not burned: elapsed time would read as a time
of day. Focus holds up to five cameras; past that the box starts from Grid.
A recording that carries an incident clip cannot be moved to another case
while the clip is on it (the file holds the other cameras' pictures), and a
camera moved away afterwards fails Render again plainly; Process again on
the sound camera refuses a new clip as it refuses any other.

**Settings.** Incident clips (On) on the Incidents page under Clips, greyed
while Incidents or Clips is off. The Clips page's own limits apply.

**Audit.** Clip created carries `cameras` and `layout` for an Incident clip;
Event changed covers a note or a mark; Incident changed carries `about`;
none holds a word of a note, an About or an event.

**Image.** The app image names `fonts-dejavu-core` and checks at build that
ffmpeg carries drawtext, xstack and tpad and that DejaVu Sans is on disk, so
an image that cannot draw the wall never reaches a server. CI now checks
that every model change has its migration.

**Database.** One migration: Note and To check on the Event, About on the
Incident, and the Incident, the Event and the picture on the Clip.

**Records.** `docs/research/incident-clip.md` records the filter graph, the
reasons for each filter and the by-hand check owed on the worker; the Clips
page now shows a clip's span and length, which it had left blank.

## v1.62.0, 2026-09-17

```
Models: unchanged
Database: unchanged
```

Phase 6 chapter 4: the incident page laid out for watching, from the
maintainer's finding after v1.61.0 that the page was "a bit smushed".

### Added

- **The Layout menu** in the transport, in Across's place: Focus (the
  shipped default), Side by side, and Grid at 2, 3 or 4 across. One press
  switches at once, keeping the moment, the play state, the sound and
  Follow; the browser remembers each person's choice, and the new setting
  Incident layout on the Incidents page says what a new person starts with.
- **Focus**: one camera large beside the panel, its words in the reading
  size, every other camera in a filmstrip under it playing in step; a
  press on a small tile brings it to the front. Parked cameras sit at the
  end of the filmstrip and a press swaps one in and to the front.
- **Side by side**: every camera at the same size in a grid beside the
  panel with the strip at the bottom. **Grid**: the cameras alone across
  the width at the chosen count, the panel under the strip.

### Changed

- The sound is a speaker on each tile: a press pins the sound there; in
  Focus it follows the camera at the front until pinned, and a second
  press on the front camera's speaker lets it follow again. The transport
  says which camera is heard; the Sound from list and the Sound radio go.
- Tile heads are lighter: a short pill (Clock, Clock?, Sound, File, Hand,
  Guess) with the full words on hover.
- Parked cameras are thin lanes in the strip with Swap in; the row of
  parked tiles under the transport goes.
- The event box opens as a sheet over the head and no longer pushes the
  page down.
- Two icons, a speaker heard and muted, join the sprite.

## v1.61.0, 2026-09-17

```
Models: unchanged
Database: migrates
```

Phase 6 chapter 3, the assistant on the Incident, and the rule for
speaker labels across cameras.

### Added

- **The case chat knows the incidents.** A recording that is a synced
  camera of an incident is read with its start by the cameras' clock, in
  a block after the case's people, so an answer says when something
  happened by the time of day and reads every camera at that moment. The
  Case chat template gains the sentences that say so (an unedited copy
  takes the new wording by itself). Switch: Case chat knows the incidents.
- **Proposed events.** Propose events on the Chronology tab: the assistant
  reads each synced camera's record (or its transcript) one call at a
  time and proposes events, each with the line it rests on, checked by
  the app before it is shown. They wait under Proposed by the assistant
  with Accept, Dismiss and Accept all; nothing joins the chronology, the
  exports or the memo unaccepted, and a dismissed one is not offered
  again. Switches: Assistant proposes events, its answer cap (2,000
  tokens) and time limit (180 s). The Proposed events template on the
  Templates page.
- **The Incident memo.** A Memo tab on the incident page. The app merges
  every synced camera's digest onto the incident clock, camera by camera,
  into one time-ordered record (made for the call, never stored), and the
  assistant writes a memo from it on the chronology's events: every time
  the time of day and a citation that plays every camera, and a sentence
  written on an event carrying its number. The tab says what the memo
  was written from and which cameras were left out, says when the
  chronology or the cameras changed since, and offers Regenerate. Memo
  to Word carries the chronology as its last pages. Switches: Incident
  memo, its answer cap (4,000 tokens) and time limit (600 s). The
  Incident memo template on the Templates page.
- The case page's Incidents tab says whether an incident has a memo and
  whether events are newer than it.

### Changed

- **Speaker labels on an incident.** The words under a camera show a
  speaker's name only when a person set or accepted it on that
  recording's Speakers page; a numbered label (Speaker 1, Speaker 4) is
  not shown, since each recording is labelled on its own and the same
  person carries a different number on each camera. The assistant is
  told the same rule for the memo and the proposals.
- The chronology's exports and counts leave proposals out; an event
  accepted from a proposal reads "Assistant, <camera>" and the Word
  export prints the AI notice when any event came that way.

### Audit rows

AI assistant call with features `incident_events` and `incident_memo`;
Events proposed; Event added (source assistant); Event dismissed;
Incident memo exported. None holds a word of a proposal or the memo.

## v1.60.1, 2026-09-17

```
Models: unchanged
Database: unchanged
```

### Fixed

- A camera removed from an incident did not appear in Add cameras until
  the page was reloaded: the list was drawn once with the page. It is
  drawn from the page's state each time the box opens.
- Dragging a tile to another place on the wall changed nothing: the order
  was saved but the wall was drawn in clock order. The wall now follows the
  saved order, and a tile can be taken hold of by its picture.
- Sync was behind a three-dot menu that was easy to miss. Every tile now
  carries a Sync button in its head; the menu keeps Swap out, Open the
  recording and Remove from incident.

## v1.60.0, 2026-09-17

```
Models: unchanged
Database: unchanged
```

The tuning pass over the incident page from the maintainer's first use.

### Changed

- **Sync is the one control for a camera's place.** Every tile has a menu
  at its top right with Sync this camera, Swap out, Open the recording and
  Remove from incident. Sync opens the nudge buttons (a second or a tenth
  either way, with the camera's start on the clock beside them), Type a
  time, From its clock, From its file and Match the sound, right on the
  camera, so a person nudges it into step while the wall plays. The
  Cameras tab's Place and Adjust read Sync too.
- **Every camera is on the wall.** A camera with no clock is no longer
  parked as Not placed; the app puts it on the wall at its best guess, the
  time its file carries or else the incident's start, marked **Not synced
  yet** until Sync fixes it. Placed by hand reads Synced by hand; an
  incident's line reads "3 of 4 synced".
- **Tiles are dragged into place** on the wall, and **Across** in the
  transport sets how many sit side by side (Auto, 2, 3 or 4), remembered
  in the browser. Auto uses four across on a wide screen, and the
  right-hand area gets more room from about 1900 pixels.
- **What the vision model saw** no longer prints under the tiles; the words
  being said stay.
- **The clock is shown only where one was read.** The Clock column leaves
  the recordings tab; the Incidents tab's list of videos and the New
  incident dialog show a clock where the picture carries one and nothing
  otherwise, since many videos have none and that is not a fault.

## v1.59.1, 2026-09-17

```
Models: unchanged
Database: unchanged
```

### Changed

- **Incidents are a tab on the case page.** The strip under the case name
  and the New incident button in the header, which floated over the page,
  are gone; an **Incidents** tab beside Chat holds the case's incidents
  with Open the incident, the app's offer when videos overlap on their
  clocks, New incident, and every video with its clock and the incident it
  is in. The recordings tab keeps its Clock in the picture and Incident
  columns.

## v1.59.0, 2026-09-17

```
Models: unchanged
Database: migrates
```

### Added

- **The Chronology** (Phase 6 chapter 2). An incident's list of events,
  each a time of day on the cameras' clock, an optional end, a line of
  text, its source (a person, the words of a camera, or what a camera
  showed) and the cameras that show it. Add event here in the head, or
  the E key, adds one at the moment being watched; + event on the line
  being spoken under a camera adds those words, quoted as they stand, and
  on a camera line adds what the camera showed; a chat citation's all
  cameras link, and All cameras in the viewer's head, open the incident
  with the cited or spoken line ready as an event. The Chronology tab is
  first on the incident page, its times play every camera from there, the
  event nearest the moment is marked as the page plays, and Edit changes
  or removes one. The Events lane at the foot of the strip shows every
  event as a mark with its first words.
- **Three exports** from the incident page's head: the chronology as a
  Word document (the cameras and how each was placed, the strip drawn by
  the page as a picture in the light palette, the events in a table), as a
  spreadsheet (.csv), and the picture alone. Nothing image-like is
  stored; the picture is drawn when asked for. Each writes the audit row
  Chronology exported with the format.
- Audit rows Event added (with the source), Event changed and Event
  removed, in the Cases category, without a word of an event.
- No new setting: Incidents governs the whole.

## v1.58.0, 2026-09-17

```
Models: unchanged
Database: migrates
```

### Added

- **Incidents** (Phase 6 chapter 1, `docs/spec/SPEC-PHASE-6.md`). A case's
  videos that ran at the same time become an incident and play in step on
  a page of their own. Each camera is placed on the incident clock, the
  time of day the cameras burn into their pictures: from its checked stamp,
  matched by sound against a placed camera, from the time its file
  carries, or by hand, and a pill beside every camera says which. The case
  page carries an Incidents strip under its name with Open the incident,
  New incident in the header, and the app's offer when two or more videos
  overlap on their clocks ("8 videos ran at the same time on 7 June 2025.
  Make them an incident?"), with Make it, Choose myself and Not these; a
  later video that ran during an incident is offered to it. The recordings
  list gains Clock in the picture and Incident. The incident page: up to
  six cameras on the wall (the office sets how many), one transport, the
  clock in large figures, Sound from one camera, "Starts in" and "Ended
  at" on a camera not running at the moment, the words being said and the
  camera line under each picture, parked cameras to swap in, a strip with
  a lane per camera (click to seek, drag to place by hand, zoom), and the
  Cameras and Details tabs. All cameras in the viewer's head and beside a
  chat's citation opens the incident at that moment.
- **The sound match.** A camera without a clock is placed by comparing its
  sound with a placed camera's, on the media worker, with no engine call:
  the loudness of the two over time, cross-correlated; a strong match is
  applied, a weak one shown and left to the person. NumPy joins the app
  image for it.
- **An Incidents page in the Panel** between Vision and Speakers: Incidents
  (On), Incidents proposed (On), Cameras on the wall (6), Most cameras in
  an incident (20), Stamp reads early (On), Match by sound (On).
- Audit rows Incident made, Incident changed, Incident deleted and Camera
  placed, in the Cases category, without a camera id or a word.

### Changed

- **The camera stamp is the recording's, read early.** It moves from the
  transcript to the recording (the migration copies every stamp), so a
  Process again keeps it, and while Stamp reads early is On it is read as
  each playback copy lands for every video in a case, two small engine
  calls by day, rather than with the night's vision work. Vision reads a
  stamp only when none has been read. Videos already in cases have no
  clock until something reads it: after the upgrade, run
  `docker compose exec app python manage.py read_stamps` once to queue
  the read for every case video without one.
- A recording moved to another case leaves its incident; a recording
  deleted leaves it. Opening an incident, making one and placing a camera
  count as the case's activity.

## v1.57.0, 2026-09-16

```
Models: unchanged
Database: unchanged
```

### Changed

- **A case's Chat says what it read without the vision.** An answer opens
  by naming the videos it read from the transcript alone ("Recording 2 and
  Recording 4 were read from the transcript alone"), the way a summary's
  card does, so a reader knows which recordings' pictures are not yet in
  the answer. Nothing is said when Digests are off.
- **A transcript's exports are the words.** The What the camera showed
  section no longer prints in a transcript's Word or text export unless
  the office turns on the new Vision page switch **Transcript exports
  carry what the camera showed** (Off). **Exports carry what the camera
  showed** (On) keeps governing a summary's export and a clip's captions,
  and the Details panel counts the descriptions whatever the switches say.

## v1.56.1, 2026-09-15

```
Models: unchanged
Database: unchanged
```

### Fixed

- A recording processed again had Check the speakers greyed out from the
  start: the check queued as the transcript landed was taken up before the
  row that queued it was committed, so the job found nothing, ended, and
  the row stayed queued for good. The task is now queued once the row is
  committed, looks again in a few seconds when it finds no row, and the
  queue's minute sweep queues again any check left queued for two minutes
  with no task behind it. The same cure as the vision task's in v1.54.1.

## v1.56.0, 2026-09-15

```
Models: unchanged
Database: migrates (0045: how many of a Speaker check's windows were cut short)
```

### Added

- **Swap two speakers between times** on the Speakers page, under the
  lanes: two speakers and two times, and every line of one in that stretch
  becomes the other's and the other way round, in one press. It is the
  shape the engine's mistake takes when it confuses two voices for a
  passage. Undo puts both sides back; the audit row Speakers swapped holds
  the count and the stretch's length, never a name.
- The Speaker check's **Suggested corrections offer the swap** when eight
  or more of them lie between the same two speakers, and a swap settles
  the corrections in its stretch.

### Fixed

- A Speaker check window could propose at most sixty moves, so a swapped
  stretch was listed only to its sixtieth line and the rest never
  proposed. A window may now propose up to four hundred; the answer cap
  is the real ceiling, and the page says when a window's list was cut
  short there.

## v1.55.1, 2026-09-14

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Speakers page in three columns.** The transcript stands at full
  height in the middle, between the speaker cards and the player, and the
  lanes sit under the player on the right. Until now the transcript was
  squeezed under the lanes to a few lines. On a window narrower than 1280
  pixels the cards sit beside the player and the lanes in a band across
  the top, and the transcript runs full width under it with the rest of
  the height.

### Fixed

- The Speaker check ran with thinking on when the AI assistant's switch
  said so, and the model spent the answer room reasoning: every window
  came back cut off and the run found nothing after twelve minutes. The
  check answers without thinking whatever the switch says; its answer is a
  short list.

## v1.55.0, 2026-09-14

```
Models: unchanged
Database: migrates (0044: the Speaker check's runs and its corrections)
```

### Added

- **The Speaker check** (Phase 5 chapter 3). After a transcript lands with
  its speakers told apart, the AI assistant reads it in windows of about
  ten minutes and proposes the lines whose words show they were given to
  the wrong speaker: a question and its answer under one label, a person
  addressed by name answering under the asker's label. It proposes and
  never applies. Every proposal is checked by the app (a real line, a
  speaker already on the transcript, the label as shown) and waits on the
  Speakers page under **Suggested corrections**, each with the words, a time
  that plays the line, "Speaker 2, not Speaker 1", and the reason, with
  **Accept**, **Dismiss** and **Accept all**. Accepting moves the line as
  the number keys do, with the same audit row and the same Undo; a line
  that changed hands since the check is dismissed rather than applied. The
  check never adds or merges a speaker and never changes a word.
- **Check the speakers** on the Speakers page runs it on request, and the
  recording page's speaker strip shows a pill with how many corrections
  wait.
- **A Speakers page** in the Panel's Settings group: Speaker check (shipped
  Off), Speaker check runs (as each transcript lands, or overnight, when a
  check queued by day waits for the Vision window), Speaker check window,
  answer cap and time limit. The wording is the **Speaker check** template
  on the Templates page.
- Audit rows Speaker check queued, Speaker correction accepted and Speaker
  correction dismissed, and the AI assistant call for `speaker_check` with
  the windows and the corrections found; never a word of the transcript.
- `docs/research/speaker-check-probe.md` records the probe on the office's
  recordings that preceded the chapter.

## v1.54.2, 2026-09-14

```
Models: unchanged
Database: unchanged
```

### Fixed

- On a window 1280 pixels or wider, clicking a recording's row on the case
  page shaded the row and showed nothing: the rule that hides a row's
  details where they go to the pane on the right (My recordings, Clips) hid
  them on the case page too, which has no such pane. The type, Rename,
  Process again, Move to another case, Delete and the Vision buttons were
  unreachable there on a wide screen. The fold opens at every width now.
- The line above a case's recordings, with Enrich now for an Admin, went
  away once every video was marked for tonight. It stays: "1 video is
  enriched tonight", with Ask for it now and Enrich now.

### Changed

- The New summary form says plainly when the video is not yet enriched with
  vision and when it will be ("it is enriched tonight, between 20:00 and
  06:00"), and that Regenerate takes the vision in; a finished summary's
  card carries "Written from the transcript" as a pill rather than a
  fragment of its header line.

## v1.54.1, 2026-09-14

```
Models: unchanged
Database: unchanged
```

### Fixed

- Two videos sat at "Enriching now, about 5 minutes" with nothing running.
  The vision task can be taken up before the mark that queued it is
  committed, and it took the transcript for one with nothing to do. On its
  first go it now looks again in a few seconds, and the queue's minute
  sweep queues again any video left queued for two minutes with no task
  behind it.
- The Vision switch's help still spoke of the Moments tab.
- The case page's "not yet enriched" count took in an enriched video whose
  digest was stale.
- The transcript's "Following paused while you read. Resume" pill was six
  pixels tall and could not be read: its holder stretched it to no height.
  It keeps its own height now.

### Added

- **Process again** offers **Tell the speakers apart** in its box, starting
  as the recording had it, so a recording transcribed without the speakers
  told apart can be sent back with them, or the other way round. And where
  the recording page says Not diarized, a button, **Tell the speakers
  apart**, does the same in one press, after the upload page's own warning
  about speaker separation.

## v1.54.0, 2026-09-14

```
Models: unchanged
Database: migrates (0043: the Enrich with vision tick on a recording and a
batch, when a batch's second message went, and the Vision requests)
```

### Added

- **Vision on the office's terms** (Phase 4 chapter 5). The picture step of
  a video is called Vision on every page and is chosen with a tick on the
  upload page, **Enrich with vision**, whose starting position is an office
  setting. The office says when it runs: **as each transcript lands** (what
  v1.52.0 did, and the shipped position), **overnight** in a window of two
  server-time clock times, oldest video first, one at a time, or **only
  when asked**, when nothing runs until an Admin allows it. Under the two
  scheduled positions vision is offered only for a recording in a case,
  since a session's recordings are gone by night.
- **The case page's Vision column** in one family of words: Enriched with
  vision; Enriching now, 12 of 60, about 18 minutes; Enriching tonight (and
  how many are ahead of it, or that it was not reached last night); Requested
  now, waiting for an Admin; Not yet enriched with vision. **Enrich tonight**
  for anyone with the case, **Ask for it now** as a request with an optional
  line of why, and **Enrich now** for an Admin, on the line above the list
  and on each video's row.
- **Requests** at the top of the Panel's Vision page, with the asker, the
  case or video, the estimate and the line, and Allow or Decline with a line
  back; a count in the rail; every Admin with an address is mailed when one
  arrives, the asker when it is allowed and when the work is done.
- **A Vision page** in the Panel's Settings group holding every picture
  setting under its group (Vision, the descriptions, the scan, the record,
  the digest, the chat, the camera stamp, exports), moved from the AI
  assistant page with their keys unchanged. Moments is named **Vision**,
  Moments in answers **Descriptions reach summaries and chat**, and the
  Moment prefix Description. **Exports carry what the camera showed** (On)
  leaves the camera section out of the exports when Off.
- **Two mails for a case batch under a schedule**: the Batch finished
  message says the videos are enriched tonight, or when an Admin allows it,
  and that a second message follows; **Vision done** says they are ready.
  Three new templates on the Email page: Vision done, Vision requested,
  Vision allowed.
- **Before the vision**, under a schedule, a summary or a chat question is
  written from the transcript at once and the card says "written from the
  transcript"; once the video is enriched the card says "Regenerate to
  include the vision". A summary never starts the vision work under a
  schedule. As each transcript lands, the v1.52.0 rule stands.
- The engine gone during the night puts the video back to tonight rather
  than failing it. GIDEON's own maintenance nights are parked for a later
  chapter.

### Changed

- The audit row Video prepared is written as **Video enriched**; new rows
  Vision queued, Vision requested, Vision allowed, Vision declined.
- The batch page says "Enriching 3 videos with vision, about 40 minutes" or
  "3 videos are enriched with vision tonight, between 20:00 and 06:00".

### Withdrawn

- Three settings whose features v1.52.0 removed: Moment clip length, Look
  closer frame height, Look closer frames. A stored value is ignored.
- The case page's Prepare them now, replaced by the three buttons above.

## v1.53.2, 2026-09-14

```
Models: unchanged
Database: unchanged
```

### Fixed

- The case page's recordings list only changed when the page was reloaded.
  While any video is being prepared the page now refreshes each row's State
  and Prepared cells, and the line above the list, every fifteen seconds,
  and stops once nothing is preparing.
- The recordings table, wider since the Prepared column, ran under About
  this case and covered its buttons. It scrolls inside its own pane now;
  the Prepared pill wraps and the date stays on one line.

## v1.53.1, 2026-09-14

```
Models: unchanged
Database: unchanged
```

### Fixed

- A video being prepared read "5 of 4": a digest window that split made more
  parts than the plan had counted. The total now grows with the splits.
- A digest part cut off at its cap split only its own window, and the next
  window, cut to the same size from the same talk, was cut off too: ten
  calls thrown away on one fifty-minute video. A cut now splits the cut
  window and every later window no part has been made for, in one go.
- The player's one-frame-back and one-frame-forward buttons had each
  other's picture.
- A summary deleted while it waited for the video to be prepared was still
  written at the end, or failed the worker's job with an error. The wait
  ends when the summary is gone and nothing is written; the preparation
  itself finishes, since it is the transcript's.

## v1.53.0, 2026-09-14

```
Models: unchanged
Database: migrates (0042: the digest's splits, whether a part was cut off,
and the hash of the shipped wording a template took)
```

### Changed

- The Standard, Video and Body camera summaries are written as a memo a
  member of staff hands to an attorney: a summary paragraph, the people as
  the recording identifies them, what happened grouped by subject rather
  than minute by minute, the statements that carry weight, then the names
  and dates and the unclear stretches. Third person, past tense, a time only
  where a reader would want to check. A person is named, or given a role,
  only as the words give it; the People part says where. No closing section
  of points for the attorney: the memo ends at the facts.
- The digest is condensed in windows of about 4,000 tokens (12,000 before),
  one time per line, exact quotes only where the words carry weight, filler
  folded, camera lines only where they add what the words do not. A part
  that comes back cut off at its cap splits its window in two and the halves
  are condensed afresh; a one-line window still cut is kept and marked, and
  the Admin's fold under Details says which part and how many splits.
- The summary answer caps start at 800, 1,600 and 3,500 tokens (600, 1,200
  and 2,500 before), so a Detailed memo of a long recording is not cut off.
- A shipped template the office has not edited follows the wording of each
  new release by itself, its version rising as if reset. One the office has
  edited keeps its words, and the Templates page marks it "shipped wording
  changed" so Reset is a choice. Until now a built-in was made once and never
  followed a later release: the v1.52.0 Video summary never reached a server
  that had used the v1.43.0 one.

### Fixed

- The digest of a fifty-minute video stopped at minute four: each part hit
  its cap on timestamps and filler quotes and nobody was told. See the split
  rule above; the cut is recorded from now on.

## v1.52.2, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Fixed

- The Summary and Chat panels drew nothing since v1.52.0: the page script
  still named a helper the Moments tab took with it, the first draw threw,
  and the poll's error handler hid it. A summary written meanwhile was there
  all along and shows now.
- A summary asked for while the dialog had drawn nothing named no template
  and got the office's Default (the Standard summary) rather than the Video
  summary. The app now falls back to the template the page preselects for
  the recording, its type's or the Video summary, never the Default over it.
- A video's State pill said Ready while its picture was still being prepared
  and the Prepared column said Preparing beside it. The pill now says
  Preparing, and the batch card Transcribed, preparing, until the picture is
  done; Ready and Done mean ready for everything.
- A batch that went into a case carried the sign-out warning ("Your
  recordings stay until you sign out..."), which is not true of a case: the
  case keeps them. The batch page shows it only for a batch of the session.
- The Admin's fold, The digest and the descriptions (admins only), sat under
  the provenance list at the foot of Details, folded, where nobody found it.
  It is first in Details now, still folded.
- `./transcribe tidy`, and the tidy every upgrade runs after it starts the
  containers, freed no build cache on Docker's buildx 0.36: the filter's
  pattern was unquoted, so buildx read its first `|` as the end of the value,
  matched nothing and said nothing, and six torch installs (69 GB) sat on the
  root filesystem until an upgrade refused to build for want of room. The
  pattern is quoted now, and names each image's last build step, since a
  record is pruned only once nothing built on it remains.

## v1.52.1, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Fixed

- A video sat at "preparing" with the engine idle. The picture record thins a
  long span's frames to a fraction of a frame a second (sixteen frames over
  twenty seconds is 0.8), and the clip's cut rounded that to a whole number:
  zero, at which ffmpeg cuts nothing until the cut's time limit ends it, one
  span after another, every one of them failed. The fraction now goes to
  ffmpeg as it is.
- A preparation left part-way when a worker stopped (an upgrade restarts the
  workers) stayed "preparing" for good: the queue gave the job back, but the
  task left a transcript already marked running alone, and the spans left
  queued or running counted as taken. The task now takes such a transcript up
  again, and a preparation starts from the descriptions that stand, the spans
  the last attempt left queued, running or failed described afresh.

## v1.52.0, 2026-09-12

```
Models: unchanged
Database: migrates (0041: the transcript's preparation state and counts, and
the seconds a description and a digest part took)
```

Phase 4, chapter 7 (`docs/spec/SPEC-PHASE-4.md`): prepared videos, one
account, and the digest for Admins. The maintainer, on v1.51.0: "the intent
is getting lost"; the record and the digest are a foundation, not something
a person presses or reads, and the summary is "a narrative and executive
summary of the events" from both.

### Added

- **Prepared videos.** A video is prepared, its picture record complete and
  its digest current, by itself as its transcript lands (queued before the
  batch is looked at, waiting a minute at a time for the playback copy), on
  first use when a summary or a chat question comes first (the card says
  "Preparing the recording (12 of 60), about 18 minutes", and waits for a
  preparation already running rather than starting another), or on purpose
  from the case page, whose recordings list gains a **Prepared** column and
  **Prepare them now** for the rest. One audit row, **Video prepared**, with
  the descriptions and the parts made. The count and the time left come from
  what descriptions and digest parts have taken on this engine.
- **Wait times.** The batch page says, per recording, "preparing 12 of 60,
  about 18 minutes" or "prepared", and at the top, once transcribed,
  "Preparing 3 videos for summaries and chat, about 2 h 40 min", polling
  until they are done; the case page says the count and the time; the
  summary dialog says what preparing will do first.
- **The mail waits.** The Batch finished message goes only once the batch's
  videos are prepared, and gains {prepared}: "3 videos prepared for summaries
  and chat in 2 h 10 min; 1 could not be prepared."
- **One account.** The Video summary is an executive summary and the events
  in order as prose, from the words and the picture together, never saying
  which source a sentence came from; the body camera summary's timeline is
  one account too. A summary written from the digest is given the narrative
  rules in place of the camera rules: the guardrails stay (a person named
  only from the words, an object what the description saw, no legal
  conclusion, "not visible" reported), the two-source wording goes. The chat
  still says where a fact came from.
- **The digest for Admins.** Details shows an Admin, and nobody else, the
  digest's parts as the model wrote them, every description with its span,
  and the template versions that made them. The digest's instructions are a
  **Digest** template on the Templates page, editable and resettable.

### Withdrawn

- The Moments tab, Describe this moment, questions answered from close
  frames, Describe the whole recording, the summary dialog's Look at the
  picture first tick, the setting Summaries describe the moments first, the
  endpoints that made, edited, described again and deleted a moment, and the
  audit rows Moment edited and Moment deleted. Nobody presses anything on the
  recording page for the picture. Moments made before this release stay in
  the exports' What the camera showed section.

## v1.51.0, 2026-09-12

```
Models: unchanged
Database: migrates (0040: the digest's parts, the record's change points and
the camera's stamp on the transcript, the summary's digest count and stage;
the cues table dropped, the moment's cue text gone)
```

Phase 4, chapter 6 (`docs/spec/SPEC-PHASE-4.md`): the picture record, the
digest, and the camera's stamp. The maintainer asked to "make summarization
smart", read the first proposal and cut it back: cues out, no overlapping
descriptions, "smart optimization" throughout, nothing about the camera in
line with the transcript; then sent a stamped frame.

### Added

- **The picture record.** Describe the whole recording no longer describes
  on a clock. The picture and the sound are scanned once per transcript for
  where they change sharply (the scan of v1.40.0, kept, its change points
  now kept on the transcript), and the recording is cut at those points into
  spans that touch, never overlap, and cover it end to end: no span longer
  than **Picture record: longest span** (15 s, renamed from Describe at
  intervals: every), none shorter than **Picture record: shortest span**
  (3 s), at most **Picture record: most descriptions** (600), and a span
  already described is never described twice. Each span is described as
  itself, its frames thinned to at most **Picture record: frames per
  description** (16) so a long still stretch costs no more than a short busy
  one, with the previous span's description in hand and an instruction to
  say only what is new; a span where nothing changed comes back as one line
  beginning "Unchanged:". The summary dialog's tick starts ticked while
  anything is left to describe, and its line says the count, "up to" until
  the picture is scanned. **Picture record for summaries** turns it off.
- **The digest.** Made in the summary's lane after the record: the transcript
  cut into windows of about **Digest window** tokens (12,000) on line
  boundaries, each sent with the camera lines in it and condensed by one call,
  capped at **Digest part cap** (1,200), into numbered lines that say the span,
  (said), (seen) or (both), and what happened, exact quotes kept. Kept part
  by part with a signature of what each was made from, so the next summary
  remakes only the parts whose words or descriptions changed. The summary is
  written from the digest with the transcript beside it when it fits, and
  from the digest alone when it does not, so a long recording is never
  refused; the per-length caps on camera lines are gone. The chat is told the
  digest in place of the camera block, plus the descriptions whose spans hold
  the times the question names (**Chat: descriptions near an asked time**,
  6). The case chat reads each recording's digest after its transcript, and
  the digest alone when the case would exceed the hours ceiling or a
  transcript alone would not fit. Nobody reads a digest: Details says when it
  was made and from what; the summary's card says it was written from the
  digest; the chat's grounding line says the record it answers from. Audit
  feature `digest`, one row per part. **Digests** turns it off.
- **The camera's stamp.** When the record is first made, one frame two
  seconds in is read at the look-closer height with fixed instructions to
  transcribe the date, the time and the camera id burned into the picture,
  character for character, never guessing; a second frame a minute on checks
  that the clock moved on by that minute. Kept on the transcript, shown in
  Details, on the export's processing record and on the Moments tab, and
  told to the summary, the chat and the digest as the camera's clock, with
  the recording's own zero worked out so a time can be given as the time of
  day; the date goes as printed and is never reordered. Audit feature
  `stamp`. **Read the camera's stamp** turns it off.

### Changed

- **Gap between change points** (3 s; was Gap between scanned moments, 15 s)
  and the scan's two thresholds now hang on Moments rather than on the
  withdrawn media finder.
- The exports' What the camera showed section shows a span on a record's
  line; the summary's head reads "from the digest" when it was.

### Withdrawn

- **Cues.** The word finder (Find moments from the words), the cue rows and
  the Suggested moments list, the "Camera?" pill, Dismiss, the six finder
  settings, the Find moments template (an office's edited copy goes with
  it), the audit feature `moment_finder`, and the cues table. The scan of
  the picture and sound stays as the record's cut.
- **The camera among the transcript's rows.** The camera line under the
  nearest row and the row's describe button in the viewer, and the camera
  lines interleaved among the lines in the text and Word exports; the exports
  keep the What the camera showed section at the end, the transcript export
  gaining it.
- **Enough moments for a video summary** and the tick's count rule.

## v1.50.1, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The word being said no longer breaks onto a line of its own.** Since
  v1.46.0 the stage's line being spoken was styled through a bare `now`
  class under the desk, and the word being said in the transcript carries
  that class too, so as the transcript followed along the underlined word
  took the box's layout: a line to itself, the rest of the line after it,
  and on a sound recording it vanished altogether. The stage's rules now name
  the box by its id.

## v1.50.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

The Speakers release: Phase 5, chapter 1 (`docs/spec/SPEC-PHASE-5.md`).
The maintainer asked for speaker management as "more of a suite", answered
the build's questions (a deliberate pass and a quick fix alike, naming the
voices first, a page of its own, the case's people first), and chose the
layout from the mockups: the line-up with lanes.

### Added

- **The Speakers page.** **Manage speakers** on the speakers strip opens
  `recording/<id>/speakers`, a page whose one job is saying who each speaker
  is. A card per speaker down the left, in the order they first spoke: the
  name or the engine's label, the role inside a case, named or unnamed, the
  engine's own label in small type, how many lines and how long talking,
  three **samples** (one from each third of the speaker's lines, the one
  nearest four seconds among those between two and eight, each playing that
  line on its own and stopping at its end), **rename** and **same person
  as**, and on an unnamed card the name box: inside a case the case's
  people first with their roles and "in N other recordings", then a new
  name with a **role picker** so a person made here takes a role at once.
  A card whose lines never overlap a bigger speaker's says "Never speaks
  while X does; see the lanes" with **Merge into X**.
- **The lanes.** Under the player, one lane per speaker across the whole
  recording with a block wherever they talk (lines of one speaker under a
  second apart drawn as one), the playhead through every lane, and the lanes
  as the only scrub bar: a press seeks, a block plays from its start, a
  speaker's name picks the card, and dragging one name onto another merges
  them. Zoom **all**, **2 min** and **30 s**, remembered in the browser; the
  narrow views follow the playhead. With more than six speakers, those under
  a minute fold into one "small speakers" lane. The picked card's samples
  show as ticks on its lane.
- **The Ledger under the lanes**, the viewer's own rows, filtered to the
  picked speaker with the line before and after each dimmed for context, or
  **Everyone**; Follow keeps the line being spoken in view under the
  viewer's band rule. On the line being spoken, **play** and **not this
  speaker**; the number keys 1 to 9 give the line to a speaker as the window
  did.
- **The head**: "N of M speakers named" with a bar, **Undo** with the last
  change in words, **Suggest names** under the AI assistant's rules with
  each suggestion landing on its card as "Probably X (Role), from 0:19:
  '...'" with Accept and Reject, **Open in a window**, and **Done**, which
  returns to the recording at the page's playhead.
- A rename or merge may carry a `role`, applied to a person made by it and
  never to one that exists; a role not on the Admin's list is ignored.

### Changed

- **The Speakers window is the Speakers page in a window.** The route
  `recording/<id>/window/speakers` shows the page with no Done; the
  recording's page follows it through the channel as before. **Tag
  speakers** on the strip is gone, replaced by Manage speakers. The window's
  own roster, nowbox and scrub bar are gone with it.

### Documents

- `docs/spec/SPEC-PHASE-5.md`: chapter 1, the page; chapter 2, voice prints,
  deferred, written as the reservation the page keeps (an empty "Sounds
  like" line on an unnamed card) and the five rules the release will have to
  meet. Phase 1's rule against embeddings and Phase 2's stand.
- `CONTEXT.md`: Speakers page, Lane, Sample, Voice print; the Speakers
  window entry rewritten. Pointer lines in Phase 1 (the Speakers window,
  Speaker suggestions) and Phase 2 (the viewer inside a case). The user
  guide's Speakers section.

## v1.49.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Pop out video and the keyboard shortcuts overlay did nothing**, and
  Escape and ? threw in the page's script: their code sat between two
  sections the v1.46.0 rewrite replaced and went with them. Put back, with
  a test that they stay.
- **Follow mode bounced.** Every new line was scrolled to the centre with
  a smooth glide, so a column of short lines crept and bounced every
  second or two; and the "Following paused" pill took height when it
  appeared, so the transcript jumped by a line when it came and went. The
  transcript now moves only when the line being spoken has left the middle
  of the column, and the pill sits in a holder of no height.
- The chat's list of earlier chats was rebuilt on every poll; it is now
  rebuilt only when it changed, like the conversation.

### Added

- **Download all** on the Clips tab: one zip of the recording's ready
  clips with their excerpts and captions, once there is one. In a case it
  takes every collaborator's clips of the recording, as the tab lists them.
- **fold** at the end of the speakers strip folds it to one line with the
  count of speakers; the page remembers the choice.
- **A scrub bar** in the Speakers window, under the picture, to drag
  through the recording.

## v1.48.1, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The upgrade's free-space gate read the wrong disk.** It measured the
  filesystem under Docker's root, which since the shared server's window
  of 2026-09-12 is a volume with 560 GB free, while the containerd image
  store, where a build's layers land, stayed on the root disk with 1 GB.
  The gate waved a v1.48.0 build through and the root disk filled mid
  build; the old containers kept running and the upgrade stopped where
  it should. The gate now takes the least free space among Docker's root,
  the containerd store and the root filesystem, so a build is refused
  when any of them is short.

## v1.48.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Speakers window plays the recording itself.** The maintainer found
  it "a bit off" to tag voices in a window while steering the picture and
  the sound from another. The window now carries the picture, or the sound
  alone, with its own Play, back three seconds, five seconds either way,
  the clock, the speed, and the page's keys (Space, B, the arrows), so
  nothing else needs to be in view while tagging. Whichever of the page and
  the window you pressed Play in last has the sound; the other follows
  along, so the page's rows light as the window plays and Play on the page
  carries on from where the window paused.

## v1.47.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Added

- **A tab in its own window.** Open in a window, at the end of the tab bar,
  puts the tab shown (any but the transcript) in a window of its own and
  brings the transcript back on the page. The window follows the recording:
  the page tells it the time and the line being spoken, a citation or Play
  in the window seeks the page's player, a clip range typed there lights
  the timeline here, and anything described, saved or asked in the window
  shows on the page at once. With two monitors the words stay on one and
  the chat, the moments or the clips sit on the other. The tab shows as
  away while its window is open; press it to bring the window to the
  front. A window opens nothing the page does not offer.
- **The Speakers window.** Tag speakers, on the speakers strip, opens a
  window made for matching voices to names while the recording plays: the
  line being spoken at the top with its speaker, the speakers under it with
  a number key each, the count of their lines and a sample line. A number
  gives the line being spoken to that speaker, one line at a time, and the
  page's rows change as you go; rename, same person as (merge) and Undo are
  the viewer's own; play a line plays a line of that speaker; Space pauses
  and B goes back three seconds. The new one-line change writes the audit
  row "Speaker changed on a line", with no name, and Undo puts it back.

## v1.46.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Changed

- **The recording page is the stage and the work area**, chosen by the
  maintainer from four mockups after v1.45.0 showed that a picture in the
  same column as the tools takes its size from them. On a wide monitor the
  **stage** is a column on the left: the picture, the play controls under
  it, the line being spoken with its time and speaker, and Describe this
  moment; drag its right edge to make the picture bigger or smaller, from
  360 pixels to half the window, and nothing else changes shape. The **work
  area** is the rest: tabs along its top, Transcript, Clips, Summary, Chat,
  Moments, Details, one at a time, each taking the whole area, so Chat is
  never squeezed under a picture again. On a laptop the picture sits beside
  the title and the same tabs fill the screen below; a sound recording has
  no stage. The bottom sheet, its grip, Expand and Close are gone: both
  shapes of the page are one page.
- **The transcript reads like a court transcript.** The time, the speaker's
  name in a column of its own, the words, and the row's buttons at the
  right; when one person speaks several lines in a row the name is shown
  once; 16 px type. The speakers are stuck at the head of the Transcript
  tab so they never scroll away while a voice is being matched to a name.
  Names hidden take their column with them.
- **Marking a clip never changes the tab.** Any route (I and O, a drag on
  the timeline, clip start on a line, S, a typed time, Make a clip on a
  moment or a mark) fills the strip under the timeline with the range, its
  length, Preview, Save clip and clear. Save clip, New clip and Adjust open
  the Clips tab.
- A citation in a Summary or a Chat answer opens the Transcript tab and
  lights the line. D opens Details as before; the tab chosen is remembered.

## v1.45.1, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The head of the Moments tab was squeezed to a sliver** on a wide
  monitor once a recording had many described moments. A tab's two panels
  sat in a grid with one flexible row, so the first panel (Describe this
  moment, Suggested moments) got only what the second (Described moments)
  left over, and with fifty moments that was nothing: the top edge of the
  button peeked over the Described moments heading. Latent since v1.42.0,
  seen on the first recording described throughout. The panels now stack
  at their own heights and the column scrolls as a whole; the Chat alone
  still fills the column so its box stays at the foot. The Clips tab had
  the same shape and the same fix.

## v1.45.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Changed

- **The recording page's rail is gone**, the first of the layout slices the
  maintainer asked for ("giving the main things more space to move"). The
  260 pixels it took from the words on every screen go to the transcript,
  now 1,040 pixels wide at most. What the rail held moves to where it is
  used: the search box into the header with its match count beside it; the
  speakers into a strip at the head of the transcript that scrolls with it,
  with hide at its end; the three exports into an **Export** menu in the
  header; the keyboard shortcuts, Process again and Delete this recording
  into a **More** menu, Delete last and red only inside the menu. Nothing
  is red at reading height, and New clip is the header's one coloured
  button. A menu closes on a click outside it, on a choice, or on Esc.
- **Pop out video** sits on the picture itself, beside its consequence,
  rather than in the header.
- **Each row's buttons** (edit, clip start, describe) sit in a column of
  their own to the right of the words instead of floating over them.
- **The tabs** under the picture (Clips, Summary, Chat, Moments, Details)
  are drawn as the case page's tabs, an underline rather than five boxed
  buttons, and the Bench column grows with the window: 400 pixels on a
  small monitor, 620 on a wide one, the grip's choice over both.
- The `No word timing` pill leaves the header: the Details panel says it,
  and the missing word underline shows it. The timeline's caption is one
  sentence; the picture's edge says it can be dragged when the pointer
  rests on it.

## v1.44.0, 2026-09-12

```
Models: unchanged
Database: unchanged
```

### Added

- **Back to the case.** A batch started from a case's Add recordings now
  offers **Back to the case** beside Ready now while it runs, and once it
  has finished the page counts down eight seconds and returns to the case
  by itself, with **Stay here** to stop it. What the batch made is on the
  case page, a refused recording with its reason included. A batch whose
  files went to several places, or to your own recordings, behaves as
  before.

### Changed

- **A clearer refusal for an incomplete video.** Two surveillance exports
  were refused as "could not be decoded" when the truth was that their
  index had never been written: the export or the copy was cut short, and
  no player anywhere could open them. The app now tells that case apart by
  ffprobe's own words, under its own reason class `incomplete_file`, and
  says what to do: play the file on your own computer, and if it will not
  play there either, export it again from the system it came from.
- **A duplicate refusal links to the recording it already is.** "You
  already have this file in your recordings as ..." names the recording as
  a link on the Batch page, so nobody hunts for it by title.

## v1.43.0, 2026-09-12

```
Models: unchanged
Database: migrates (0039, how many moments a summary drew on)
```

### Added

- **The video summary** (Phase 4, chapter 5). On a video with Moments on
  and Moments in answers on, the Summary tab's button reads **Summarise
  this video**, and the summary is written from the words and the described
  moments together. A new shipped template, **Video summary**, is
  preselected for a video without a recording type (a type still wins, so a
  body camera recording keeps its Body camera summary); it interleaves what
  was said and what the camera showed inside What happened, and adds a part
  **Seen but not said** for what the camera showed that nobody spoke about.
  The Body camera summary gains the same two things. The model is given a
  fixed set of camera rules whenever a camera block is present: two sources
  kept apart in every sentence ("the camera shows ..." for the picture, the
  line's time for the words); neither wins, and a disagreement is reported
  as one; a person is named only from the words; nothing is inferred from
  the picture, least of all a legal fact; only the listed times were looked
  at; and a camera fact earns a clause, not a paragraph. The summary is told
  how many camera lines to draw on for its length (5, 12, or 30) and to
  leave the rest out rather than list them; the camera block itself is
  thinned to a budget when an office's numbers make it too big, every asked
  and suggested moment kept.
- **The video-aware chat.** Chat answers from both feeds: asked what was
  visible at a time it uses the camera line nearest it within a minute, or
  says no moment has been described there and where to ask for one; asked
  for a legal conclusion (consent, arrest, a lawful search) it gives what
  was said and what the camera showed, with times, then says in one
  sentence that the conclusion is not something it can answer. The Chat
  panel's grounding line and its waiting line count the described moments.
- **The look-first line** in the summary dialog replaces the tick's caption
  with one of three forms: **Look at the picture first** with its cost in
  numbers ("15 descriptions, one every minute, one engine call each, about 5
  minutes. 4 moments are described already.") while intervals are left to
  describe; "The summary draws on the 23 described moments." when none are;
  and a line saying the office writes from the words alone when it hands no
  moments to answers. The tick starts ticked by a rule rather than a bare
  toggle: the office's toggle is On, something is left to describe, and
  fewer moments are described than **Enough moments for a video summary**,
  a new setting (10; 0 means always ticked). **Summaries describe the
  moments first** now starts On.
- **A camera citation** in a summary or a chat answer, a time that is a
  described moment's, is drawn with the camera glyph before it and the
  description as its hover title, so a reader sees at once that the fact
  came from the picture; the summary card's head says how many moments the
  summary drew on, and a summary remembers the number.

### Changed

- The model's camera block gains a legend line under its heading (one line
  per moment, in time order, times not listed were not looked at), and a
  line staff edited ends "(edited by staff)" in the block, so the heading's
  "a model's descriptions" is honest for every line. The exports are
  unchanged: their legend and provenance row already say so.
- The summary format line no longer carries the one sentence on the camera
  block; the camera rules replace it, and a part that asks for what the
  camera showed with no block given reads "No moments were described".

## v1.42.0, 2026-09-11

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Moments tab is two panels**, as the Clips tab is, because the one
  panel was getting congested as chapters 3 and 4 added their presses to it:
  the first, Moments, has Describe this moment and, under **Suggested
  moments**, Find moments and Describe the whole recording together, each
  with a caption that says what it does and what it costs in numbers ("A
  description every minute, 23 in all for this recording, one engine call
  each") and a line under it that says what the press did ("7 lines
  suggested from the words.", "20 moments described across the recording.");
  then the suggestions, each now quoting the transcript line it was found on
  and saying sure, fairly sure, or unsure. The second, **Described moments
  (n)**, lists the Moments, with a foot line saying where they print. The
  state answer gains `cue_runs.intervals`, the interval and the count, so
  the caption, the confirm, and the summary dialog's tick can say the numbers.
- **The words on the page** read in the order a person works: the row's
  button says **describe** and opens a box that names the time, with
  Describe as its button; the Camera? pill on a suggested line is a button
  that says "Looking..." once pressed; a card says "from a suggestion" or
  "from the whole recording", "Waiting its turn..." while queued, and its
  Again button reads **Describe again**, or **Ask again** on a question, and
  waits while the Moment is being described; the Camera line under a row has
  lost its second coloured bar. Nothing was added and nothing hidden: every
  press is where it was, with its cost stated before and its result after.

## v1.41.0, 2026-09-11

```
Models: unchanged
Database: migrates (0038, the intervals' run and the summary's tick)
```

### Added

- **Describe the whole recording**, at the head of the Moments tab (Phase 4,
  chapter 4): a Moment every interval through the video, described one
  after another in a single lane of the assistant, skipping times already
  described, at most a set number spread evenly; the tab counts them as
  they land. Two settings: the interval (60 s) and the most (40).
- **Describe the moments first**, a tick on a video's summary dialog: the
  summary runs the intervals before it writes and then draws on what was
  seen, citing the camera's moments and saying "the camera shows"; the
  setting **Summaries describe the moments first** (Off) says how the tick
  starts. The summary's Word export ends with **What the camera showed**,
  every described moment with its time, under the camera legend.

## v1.40.0, 2026-09-11

```
Models: unchanged
Database: migrates (0037, Cues and their runs)
```

### Added

- **Find moments**, in the Moments tab (Phase 4, chapter 3). One press reads
  the whole transcript once and suggests the lines where the picture would
  add a fact, each with a reason: an object named or handled, a command
  that implies an action, an action narrated, a pointing phrase, a sudden
  change. Ordinary talk that happens to use such words is passed over,
  because the engine reads the context. With the second finder on, the
  picture and sound are scanned as well, without the engine: sharp changes
  of picture and raised voices or a bang. Each suggestion shows its time,
  kind, reason and source, with Describe and Dismiss; the reason rides on
  the Camera? pill. Nine settings, the Find moments template, the audit
  feature `moment_finder` and the row "Picture and sound scanned".

### Removed

- **The word-list cues** of v1.38.0. On the office's footage they flagged
  "what was that" and "on the ground" in ordinary talk far more often than
  a pointer at evidence; the maintainer: "too much general conversation".

## v1.39.0, 2026-09-11

```
Models: unchanged
Database: migrates (0036, a Moment may answer a question)
```

### Added

- **Ask about this moment.** The camera button on a line and Describe this
  moment now open one box: empty for a description, or a question about
  the picture, "is that a gun on the seat?". A question is answered from
  a few still frames at the camera's own detail (Look closer frames, 3,
  at Look closer frame height, 720 pixels) in a fixed shape: what is
  visible, what it is consistent with, and what cannot be told from the
  frames and why. The answer appears as a camera line with the question
  in front, everywhere a description would.
- **Make a clip** on a Moment's card marks its span in the Clips tool
  with the description as the note; a Clip with burned captions carries
  each Moment inside its span as a caption marked Camera.

### Changed

- **Descriptions are brief.** The shipped Moment template leads with the
  thing pointed at in one to three short sentences, concrete nouns and
  plain verbs, no restated setting; the answer cap ships at 250 tokens
  (was 400). A new **Moment style** setting brings back the full style.
  Asked for by the maintainer after the first Moments on the office's
  own footage: "meaningful explanations".

## v1.38.0, 2026-09-11

```
Models: unchanged
Database: migrates (0035, Moments: what the camera showed)
```

### Added

- **Moments** (Phase 4, `docs/spec/SPEC-PHASE-4.md`). On a video
  recording, the AI assistant describes what the camera showed at a chosen
  time: a camera button on every transcript line, **Describe this moment**
  in a new Moments tab for wherever the player is, and **Camera?** pills on
  lines whose words point at something ("look at that", "there's the"),
  listed as suggested moments and described only when asked. The app cuts
  about ten seconds of the playback copy around the time, shows it to the
  engine with the words spoken in it, keeps the description and deletes
  the clip. A description appears under its line marked Camera, in the
  Moments tab, in Details, and in the Word and plain-text exports with a
  legend; with **Moments in answers** on it reaches Summary and Chat as
  labelled camera lines. Edit, Again and Delete on each. Off by default:
  it needs an engine that takes video (the shared engine's Qwen3.8 does).
  Seven settings on the AI assistant page, the Moment prompt template on
  the Templates page, the audit row "AI assistant call" with feature
  `moment`, and the rows "Moment edited" and "Moment deleted", none
  carrying a word. Asked for by the maintainer: "when 'look at that' or
  'there's the drugs' is said, the model would look at the snip".
- **Every engine request carries priority 1**, as the box ledger's
  shared-engine paragraph asks of a client; GIDEON's line 17 is closed.
- **`llm_no_vision`**, a seventh reason class: an engine handed a clip it
  cannot read answers "This engine cannot look at video."

## v1.37.0, 2026-09-11

```
Models: unchanged
Database: unchanged (settings are rows in the Setting table)
```

### Added

- **The AI assistant's budgets are settings**, on the AI assistant page,
  each with the value the app was built with as its default: the answer
  caps (Chat; Summary Short, Standard, Detailed; Speaker suggestions), the
  thinking allowance, the three time limits, the chat history, the engine
  window, and the Case Chat's Reading size, Readings at once, two answer
  caps, and question time limit. An office tunes them to its engine and
  puts them back. Asked for by the maintainer after the shared engine's
  large model spent the whole thinking allowance thinking.
- **Reset to default on every number** on every settings page, beside the
  field while it differs from the default, and **Reset every number on
  this page** under the form. Both put defaults in the fields for the tray
  to carry, so nothing applies until Apply.

### Changed

- The specification's "never settings" line for the caps and time limits
  is overturned to that extent, recorded in the AI assistant and Case Chat
  chapters and the settings catalogue. Sampling stays in code.

## v1.36.6, 2026-09-10

```
Models: unchanged
Database: unchanged
```

### Changed

- **The chat's waiting sign is three dots fading in turn**, in place of one
  dot that grew and shrank. The single dot still shimmered on a light
  ground after the redraws were fixed in v1.36.2 and v1.36.3: a ten-pixel
  circle drawn at fractional sizes every frame flickers at its edge, and a
  dark dot on white shows it where a light dot on dark hides it. The new
  sign changes only its opacity, which the browser fades without redrawing
  the shape.

## v1.36.5, 2026-09-10

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The tidy step's filtered prune did nothing in v1.36.4.** It went
  through the older `docker builder prune`, which takes the filter flag
  without a word and then prunes only the dangling records anyway. The
  step now goes through `docker buildx prune -a`, which reads the pattern
  the way `docker buildx du` does and, with `-a`, takes the records marked
  shared with the image store, which a plain prune keeps; with the filter
  it still touches nothing outside it. On the office's server that freed
  111.7 GB in one go, none of it any other project's.

## v1.36.4, 2026-09-10

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The upgrade's tidy step now frees the build cache it made.** It ran
  `docker builder prune -f`, which removes only what buildx calls dangling,
  and the records that matter (the torch install, 11.5 GB per WhisperX
  build) are not dangling: nine of them sat on the server's root filesystem
  until it filled during the v1.36.3 upgrade, which stopped every container
  on the server. The step now prunes by the words this repository's own
  Dockerfiles leave in the records, and nothing of any other project's.
- **A build refuses to start on a nearly full disk**, with less than 40 GB
  free where Docker keeps its images, and says how to make room. A failed
  build stops the upgrade with the same message whether `--build` was given
  or not.

### Added

- **`./transcribe tidy`**: this app's old image tags and build cache records
  removed by hand between upgrades, with the free space before and after.

## v1.36.3, 2026-09-10

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The chat's waiting dot still flickered in light mode.** v1.36.2 stopped
  the one-second redraw, but the page also polls the assistant every two
  seconds while an answer runs, and each poll rebuilt the chat body and
  restarted the dot's pulse; on a light surface the faint end of the pulse
  made every restart a blink. A poll that changes nothing now redraws
  nothing, and the dot never fades below half.

## v1.36.2, 2026-09-09

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The chat's waiting dot flashed instead of breathing.** While an answer
  was on its way the chat redrew its whole body once a second to advance
  the seconds counter, and every redraw made a fresh dot whose pulse
  restarted from dim. The counter now advances in place, and the dot's
  pulse is slower and gentler. Found by the maintainer on the first day the
  assistant ran on the shared engine.

## v1.36.1, 2026-09-09

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The rename box lists the case's people in the open.** Inside a case,
  clicking a speaker's name is meant to offer the case's people; the
  browser's own suggestion list did that, but it filters by the field's
  text, and the field holds the speaker's current name, so the list stayed
  empty until the name was cleared (the maintainer: "the dropdown isn't
  working"). The people are now buttons under the field: one click names
  the speaker, typing narrows the list, and a name that matches nobody
  makes a new person as before.

## v1.36.0, 2026-09-08

```
Models: unchanged
Database: migrates (0034, a transcript remembers its speaker changes)
```

### Added

- **Undo in the Speakers panel.** Renaming a speaker or merging two can be
  undone: the line under the names says what it would undo and puts exactly
  those lines back under their old name, one change at a time, newest
  first. Found by the maintainer, who merged the wrong two and had no way
  back.
- **Rename a recording** after the fact: the pencil beside the title in the
  viewer, and Rename on a recording's row under My recordings. The file
  keeps its own name.

### Changed

- **A call recorded in the app has two speakers, its two sides**, unless
  "Tell the speakers apart" is turned on under More options. Separating
  voices within each side of a Teams call split one person into several
  and filled the Speakers panel with cards. A meeting in the room still
  separates them, since the people buttons name the voices.

## v1.35.1, 2026-09-08

```
Models: unchanged
Database: unchanged
```

### Added

- **The microphone check** on the New recording page: a chooser naming the
  computer's microphones, a live level bar before Record, and a plain
  warning when nothing reaches the app for a few seconds, before and in
  the first seconds of a recording. The choice is remembered per computer.
  A Remote Desktop session can leave Windows recording from "Remote Audio",
  which carries no sound at the machine itself; the page names it when it
  sees it. Found by the maintainer, whose taskbar showed the microphone in
  use while the app's bar stayed flat.

## v1.35.0, 2026-09-07

```
Models: unchanged
Database: migrates (0033, the Interpreter's tables and fields are removed)
```

### Removed

- **The Interpreter**, built in v1.33.0 to v1.34.0, is withdrawn at the
  maintainer's decision: the office is not ready to take it on and does not
  expect it to be used much. The page, its settings, the door on the New
  recording page, and the media worker's place on the service's network are
  gone; the app is as it was at v1.32.4. A session recorded while it was on
  keeps its recording and its transcript; the translations under the lines
  and the turn rows are dropped. The chapter stays in the specification as
  deferred, and the two research notes stay, so the work can be picked up
  if the need appears.

## v1.34.0, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Interpreter says whose turn it is.** One of the two buttons, Visitor
  or Staff, is always lit; tap yours and speak, and the lit column reads
  "Speak now" in its language. Nothing is guessed from the language heard
  any more, and the recogniser is told the language for every turn. The
  Turn-taking setting's choices are Tap (the default) and Hold.
- **Turns are cut from a rolling buffer** of the microphone's own samples,
  with half a second of lead-in, so the first syllable is never lost and the
  recogniser gets a clean clip. Before, a second recorder started at the
  onset and missed the start of every turn.

### Fixed

- **"Gracias" or "Thank you" whatever was said.** The recogniser makes those
  up from a short quiet clip. Such a result is now "nothing heard; please
  say it again", never a turn to translate.
- **A turn arriving while the service was away** (restarting, mid-upgrade)
  is asked again a few times before it is written off, instead of failing
  at once with "service unreachable".

## v1.33.1, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Every turn in an interpreted session failed with "service_unreachable".**
  The media worker, which hears the turns, was not on the transcription
  service's network; only the main worker was. It is now.

## v1.33.0, 2026-09-07

```
Models: unchanged
Database: migrates (0032, a Session's Turns; a Segment's language and translation)
```

### Added

- **The Interpreter, text only** (Phase 3, chapter 3, first slice). With the
  new **Interpreter** toggle on (Features, under Live recording, and an
  engine configured), the New recording page offers a door to a Session
  between a staff member and a visitor who speaks another language. Each
  turn is heard by the transcription service the moment the person stops
  talking, on the fast lane when there is one, and translated by the engine
  a second or two later; the page shows both in two columns, the visitor's
  on the side facing them. Hold-to-talk buttons for a loud room, Type
  instead, quick phrases, a notice in both languages, and a language the
  app can hear for itself. The session is kept as a recording with a
  transcript in both languages, in the viewer and the Word export. Never a
  substitute for a certified interpreter, and the page says so. Voices come
  in a later release.
- **The Interpreter settings page**: Languages offered (Spanish at install),
  Turn-taking, Readback, Quick phrases, The notice.
- **Two research notes** behind it: which languages each tool covers, and
  the voice engine and its licences.

## v1.32.4, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- The red of a failed row under Recorded here now comes from the theme's
  token alone, as every colour in the stylesheet must; v1.32.3 had written
  a fallback colour into the rule, which the stylesheet test refuses and
  which left the main branch's checks red.

## v1.32.3, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- **My recordings refreshed itself every few seconds** when a recording
  under Recorded here had failed (for instance one that ended before any
  sound arrived), which closed the Send to dialog and everything else as
  soon as it opened. A failed recording now says why in its row and is not
  watched; a recording still on its way is watched as before, and the page
  reloads only when its state has actually changed.

## v1.32.2, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### For the office that builds

- **The first Transcribe entry in the box ledger** (`docs/box-ledger.md`,
  section 12), answering GIDEON's eleven lines by number: the shared engine
  is the plan and the local engine is for testing only, off when not in
  use; CI is narrowed and image builds are gated; the repository is public
  since 7 September 2026; and Transcribe asks for a 40 GB line of host
  memory.
- **Memory limits that add up to that line.** The WhisperX service's limit
  drops from 32 GB to 12, the fast lane's from 16 to 8, the media worker's
  from 8 to 6, the worker's from 8 to 4, and the local engine gains a limit
  of 16 GB while it runs. Every one is a ceiling against a runaway; the
  working sets peak near 11 GB.
- **`./transcribe upgrade` keeps two tags of each image** and prunes the
  build cache it made, so old images stop piling up on the root filesystem.

## v1.32.1, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Export to Word failed for a recording transcribed in stretches.** v1.32.0
  wrote the count of stretches into the transcript's provenance beside the
  per-run entries, and the exporter read it as a run. The count is no longer
  written there, and every reader skips anything that is not a run's entry,
  so a recording made under v1.32.0 exports too.

## v1.32.0, 2026-09-07

```
Models: unchanged
Database: migrates (0031, a Job may stay open for more Runs; a Run knows its stretch)
```

### Added

- **Transcription during the recording** (Phase 3, step five). A recording
  made in the app is transcribed while it records: every five minutes, and
  what came before a pause, is cut from the pieces already on the server and
  sent to the service at once, ahead of everything else; at Stop only the
  last stretch is left, so the transcript is ready about a minute later
  however long the meeting ran. Each stretch is transcribed at finished
  quality, the speakers are matched across stretches by their voices, and
  the taps name them as before. Nothing is shown before the transcript is
  whole; the page says "Finishing: about a minute". The Details panel says
  how many stretches there were. With the fast lane on, the stretches never
  wait behind an upload.

### For the office that builds

- A stretch of a recording still in progress asks the service for priority
  100, a recording that has ended 90, an upload 0.

## v1.31.1, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The upgrade to v1.31.0 stopped on a server without the fast lane's two
  keys.** Compose reads every service's variables whether or not its profile
  is on, and the lane's were demanded rather than defaulted. They now
  default until `./transcribe fast-lane on` writes them, so the stack comes
  up as before. A server that hit this: run the upgrade again.
- CI keeps its Python packages between runs.

## v1.31.0, 2026-09-07

```
Models: unchanged
Database: migrates (0030, a Run remembers which copy of the service holds it)
```

### Added

- **The fast lane.** A second copy of the transcription service, beside the
  first on the same card, for what must not wait behind a long job: a
  recording made in the app today, and the pieces of one transcribed while
  it records and the Interpreter when they come. Same image, same model,
  its own state folder, about eight gigabytes of the card. The installer
  asks whether to turn it on; `./transcribe fast-lane on` and `off` do it
  later; the Status page has a Fast lane card and `./transcribe check` asks
  it. A lane that is on but not answering is not waited for. An office
  without one loses nothing but the waiting.

### For the office that builds

- `COMPOSE_PROFILES` in `.env` is now a comma-separated list (`llm`, `fast`),
  and the installer adds and removes each on its own. Nothing to change on
  an installed server.

## v1.30.1, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Upload page chooses nothing for you.** The "What are these?" cards
  and their presets are gone. The page asks where the files go, when the
  office uses cases, and then takes the files; a plain transcript needs no
  settings. **Tell the speakers apart** (Diarize) is off until you turn it
  on, and while it is on the page says plainly that speaker separation is
  not always right and the labels are guesses until checked against the
  audio.
- **The Start page's upload door says a batch is fine**: one recording or a
  whole batch.

## v1.30.0, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **The Clips page is My clips, organised by where each clip lives.** One
  table of every clip you saved, with a heading row for each case, one for
  Recorded here, and one for This session, the place you touched last on
  top. A clip made inside a case now shows here under that case's name as
  well as on the case's own Clips tab, and the heading opens that tab.
  Download all takes every clip on the page. Before this the page listed
  only the session's clips, so a clip made in a case seemed to vanish.

## v1.29.2, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- **Captions burned into a clip now show.** The clip was cut after the
  captions were drawn, so the captions were timed for the start of the
  recording rather than the start of the clip and fell before it. The cut
  now seeks first, which is just as exact, faster, and lines the captions
  up. A clip made with captions before this release shows "Captions out of
  date" once its transcript is touched; making it again draws them.

## v1.29.1, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Fixed

- **The Upload page's case dropdown stayed inside its card**, and the batch
  settings no longer repeat the Add to case choice the "Where do they go?"
  cards already make. The box still appears for one file given its own
  settings, where it is the way to send that file somewhere else.

## v1.29.0, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **The top bar reads Start, Cases, My recordings, Clips, Panel, Help.**
  Sign-in lands on the new **Start** page, which asks one question and
  offers **Upload files**, **Record now** (when the office has it on), and
  **Open a case** (when it uses cases). The Upload and Record tabs are gone
  from the bar; Start is the door to both.
- **My recordings is one page in two parts.** **Recorded here** is what the
  Record tab held: everything recorded at the desk, with Play, the memo or
  summary, Send to, Add to a case, and what colleagues have sent. **Uploaded
  this session** is the recordings table as before. Each part says how long
  it keeps things. Stop on a recording kept on its own lands here; the old
  Record tab address redirects here.
- **The Upload page asks what and where first.** Above the three steps,
  **What are these?** offers a card for each recording type the office lists
  (jail call, phone call, interview, body camera, hearing, meeting,
  dictation) and Something else; one click presets the speaker settings, and
  labels the recordings when they go into a case. **Where do they go?**
  offers This session only or Into a case, when the office uses cases. Step
  2 becomes "Anything else? (optional)". Done with these returns to Start.
- **The setting Record tab is now Record now** (same key; nothing to change
  on an installed server).

### For the office that builds

- **The Release workflow builds and publishes images only when the
  repository variable `PUBLISH_IMAGES` is `yes`.** While the repository is
  private its packages are too, so a server builds its own images and the
  two builds per tag spent a quarter of an hour of free minutes for nobody.
  The GitHub Release and its notes are made either way; without images the
  notes say to install with `--build`, and `./transcribe upgrade`, finding
  no digest record, already says the same. CI no longer runs a second time
  on a tag push.

## v1.28.1, 2026-09-07

```
Models: unchanged
Database: unchanged
```

### Changed

- **Stop lands on the Record tab.** A recording made from the tab now
  returns there when its transcript is ready, marked "Just recorded" on
  top, rather than opening the viewer; a recording made from a case still
  opens in the viewer beside its case. Every row on the tab gains a play
  button that plays the recording in place, so a person can check it is
  the right one before Write the memo and Send to.

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
