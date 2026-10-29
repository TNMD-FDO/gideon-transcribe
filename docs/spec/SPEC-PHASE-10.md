# Gideon Transcribe, Phase 10 specification

The case's chronology. Every note in a Case laid on one clock without an Incident, one day at a time, with the recordings placed by their read clocks or by hand once, the marks where the notes were left, and the same exports the incident's chronology has; then, in a second release, an Incident made from a span of it. Two chapters, each a release.

## About this document

This is the build specification for Phase 10 of Gideon Transcribe. On 2026-10-28 the maintainer asked: "without creating an incident could notes help to create a timeline or chronology ... on a new tab within a case that allows some intuitive and interactive collaboration ... how then could exports be used from this page. It could use the read clocks to place markers. If a camera time isn't known or read I want an intuitive way to have the user select where in the timeline it should go. We don't want a bunch of rebuilds ... a snippet of the video where the note was left ... once generated, a perfect substrate to select markers that could become an incident ... clean and intuitive ... always present mock ups before building." The design was worked through the same day in nine rounds and drawn in `docs/spec/mockups/phase-10-case-chronology.html` (figures A to J), which the maintainer agreed stand; the draft with every round is the office's own planning note.

It builds on Phase 6 (`docs/spec/SPEC-PHASE-6.md`, Incidents and the Chronology), Phase 8 (`docs/spec/SPEC-PHASE-8.md`, Notes, the Timeline view, the Timeline report), Phase 9 (`docs/spec/SPEC-PHASE-9.md`, the Notes page) and Phase 4 chapter 3 (the camera's read stamp). ADR 0027 records the one decision that is hard to reverse: a recording's clock is kept on the recording.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 10 words Recording's clock, Date strip, Notes lane, Coverage lane, and Chronology and Spell as widened), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (no setting is added) and `docs/adr/0027-a-recordings-clock-is-kept-on-the-recording.md`.

Nothing in this document is office-specific. No new environment key, no new service, no new setting: everything here is rows, pages and calls the app already makes.

## What Phase 10 adds

- **The case's chronology** (chapter 1): the Notes tab's second shape, Rows | Chronology, and a tab of the Notes page: the case's notes on their recordings' clocks, one day at a time; recordings placed by their read clocks or by hand once; the Notes lane's marks; a band that keeps one height whatever the day holds; the Preview as the snippet; Chronology to Word with a still per entry, and the spreadsheet.
- **An incident from a span** (chapter 2, the second release): a span drawn across the ruler becomes an Incident whose cameras arrive already placed from their clocks and whose notes are already its events.
- **Proposed events and the comparison over the whole case** (chapter 4, three releases from v1.168.0): a proposal is a moment on a Recording, accepting it writes a Note there, and the note follows the recording everywhere; a Proposed events tab on the case in the chronology's shape; the comparison on the Documents tab read against every recording.

## Contents

1. The case's chronology
2. An incident from a span (the second release)
3. Deferred and ruled out
4. Proposed events and the comparison over the whole case

Appendix A. Audit rows added in Phase 10
Appendix B. Settings added or changed in Phase 10

## 1. The case's chronology

### Principles

1. **The notes are the entries, and nothing the app invents.** The chronology is the office's notes on one clock. The app places a recording by a clock it read from the picture or a person typed; it never guesses a time (Phase 6 chapter 6's rule stands).
2. **Place once, read twice.** A recording's time of day belongs to the recording (ADR 0027), so every note on it follows, and an Incident made later reads the same placement.
3. **The lane scrubs, the list reads.** The Notes lane keeps its marks alone; the Spells below are where the words are. Nothing is written beside a mark at any scale (Phase 8 chapter 11's rule).
4. **One height at the top whatever the day holds.** The band chooses its shape from the day's recordings; opened, it is capped and scrolls inside itself with the ruler and the lane pinned.
5. **One reading.** The page reads the case's notes once, in a handful of queries whatever the count, as the Notes page does; the placements add one column per recording.
6. **Clean and intuitive.** Gestures the office has met on the incident page, the same words, nothing new to switch.

### Words

**Chronology** (widened), **Recording's clock**, **Date strip**, **Notes lane**, **Coverage lane** and **Spell** (widened), as `CONTEXT.md` defines them. The pages say "the case's chronology" and never timeline, markers, calendar, density or sync (an Incident's word).

### Reached

- **On the case page's Notes tab**: a toggle **Rows | Chronology** at the head of the tab beside Notes page, Search notes and Download notes, shown when the case has a note; kept by the browser per person, Rows shipped. Chronology takes the tab's whole column where the rows were.
- **On the Notes page**: a **Chronology** button beside Recordings and Details in the work panel's bar, its panel the same drawing with the player beside it; Previous and Next step in the chronology's order while that panel is in front.
- A link may name a day and a span (`?tab=notes&shape=chronology&day=2025-11-06&from=20:00&to=21:00`), so a day or an hour can be sent to a colleague.

### Each note's time of day

A note's time of day is its recording's clock (ADR 0027) plus the note's moment in the recording. So the question is only ever "when did this recording start?", answered once per recording.

1. **A video with a checked clock** (Phase 4 chapter 3): placed by the app from its stamp, the pill says "clock".
2. **A video with an unchecked clock**: placed the same way, the pill says "clock, unchecked", Check the clock is one press away on the Cameras column; a check that changes the reading moves its notes.
3. **Anything else** (no clock in the picture, a jail call, an audio file, a dictation): not placed; it sits on the **unplaced rail** until somebody places it.

### Placing by hand

- **The rail**, above the ruler: a chip per unplaced recording that has notes, with its note count, five shown and "and N more"; recordings with no notes are not on it (the chronology is of notes). **Place recordings** beside it.
- **The drag**: a chip dragged onto the ruler follows the pointer with a guide line and the time it would start at; letting go opens the box **Place <recording> by hand?** with Date (the day in hand), Starts at (the time let go at), and "The day alone; the time is not known"; the sentence "Its N notes land from then on. It reads Placed by hand, <name>, and anyone on the case may move it or take it off the clock."; Cancel and Place. The incident page's gesture and box, with a date, since a case runs over days.
- **The typed way**: a chip pressed opens the same box with the day in hand and the time empty, for a call whose time is known from a log.
- **The sheet**: **Place recordings** opens a layer over the page (the layers' rule): one row per unplaced recording with notes, in upload order, with its note count, a play mark (to hear the date said on the call), Date, Starts at and Day alone; **Place N** places the rows typed and leaves the others; Cancel. Anyone on the case fills in what they know.
- **The day alone**: a recording placed by its day with no hour sits in a band **Time unknown on <day>** at the end of that day's spells, its entries' times reading the day; the pill says "placed by the day, <name>".
- **Kept on the recording** (ADR 0027), with how, by whom and when; one audit row per recording, "Recording placed on the clock", with the how and never a time; "Recording taken off the clock" on undo. A placed recording's bar carries Move and Take off the clock on hover; a bar dragged along the ruler moves it with the same box. A stamp read later takes over from a hand placement, and the legend says "clock".
- **Who may**: anyone with the case, as a note may be written by anyone with the case.

### The page, one day at a time

- **The date strip** at the top: one small bar per day that has notes, its height the day's note count, under its month; the day in hand lit; days with no notes not drawn; hovering a bar says the date and the counts; a press opens the day; the arrow keys step through days. Everything under the strip is one day. On a one-day case the strip is one tall bar and the day is the tool.
- **The rail**, as above.
- **The ruler**, fitted to the day's notes, first to last, in the day's six times; a drag across it narrows everything below to the span (the ruler, the band, the lane, the hints, the spells), with **Back to the day** beside the lead; the span is kept in the address.
- **The band**, in one of three shapes the page chooses from the day's recordings, never the person:
  - **Lanes in colour**, up to six recordings overlapping: one bar per recording in its colour, its id on it (figure A).
  - **Packed lanes**, more recordings but spread over the day: a recording takes the first lane free at its start, so calls over a day share two or three lanes and only same-time recordings stack; six lanes at most, the rest folded into one hatched lane "and N more · Show all" (figure F).
  - **The Coverage lane**, more than six overlapping: one shaded strip whose height at each moment is how many were running, labelled at its peaks; hover for the count; press for a layer listing every recording running then, the noted ones first, each with a play mark and how it was placed; under it bars for the **eight most noted** recordings, the rest folded "N more with notes, and M with none, in the shade above · Show all with notes" (figure H).
  - **Opened**, the fold shows one bar per recording with notes in the span in view, in note-count order so the top eight stay put, in a band **capped at eight rows** that scrolls inside itself; the ruler stays pinned above it and the Notes lane below, so the marks always line up with the time; **Show fewer** returns. The choice is per person, kept by the browser, off by default (figure J).
  - A bar hovered says the recording and its placement; a bar pressed lights its entries in the spells and dims the rest, pressed again clears. The same from a row of the running list.
  - Six colours cycle; within a day a recording keeps its colour on its bar, its marks, its chip and its entries' numbers; past six overlapping the marks and the numbers take the plain colour and the chip's name tells recordings apart.
- **The Notes lane**, under the band: a mark per note at its time of day in its recording's colour; marks that would overlap at the scale in hand merge into one pill with a count; hover shows the words; a press lights the entry below and plays it. Nothing is written beside a mark at any scale.
- **The hints**, under the lane: wherever two or more videos overlap and marks cluster under them, a soft bracket with the counts and the span ("3 cameras, 6 notes, 20:24 to 21:05"; a day may carry several). A signal only in this chapter; chapter 2 puts Make an incident on it.
- **The spells**: the day's notes in time order split where a gap of ten minutes or more begins (the incident's rule, one number in one place), each headed by its span and counts. An entry: the number in a circle in its recording's colour, the time of day, the note's words, under them in the muted colour the line it sits under (or "at a moment, nothing said", or the event it is on), the writer's pill, the recording's chip, To check when marked; Edit and Open the call on hover. The time plays the Preview; the words open the note for editing in place where it may be edited (a note on an incident's event is read-only here, as on the Notes page). Past forty notes on a day the spells open folded to their headings; press one to open it; **Open all** beside the lead. The writer pills, the type pills and Find narrow before that.
- **The snippet is the Preview**: pressing a time shows the frame at the moment in the page's own right pane (the case page's pane, the Notes page's player), then plays from a few seconds before. Nothing image-like is stored (Phase 4). (Amended v1.166.0: the case page has no right pane since v1.165.0; on it the Preview floats in a window of its own, the hearing window's frame without the dim, a sheet from the foot under 900 px; the Notes tab's rows open the same window from their times. The drawing `docs/spec/mockups/phase-8-notes-window.html`.)
- **To check**: pressed on or off by anyone on the case, as the incident's; kept on the note.
- **Collaboration** is the page's nature: everyone on the case sees the same entries with writers' names, narrows by writer, places and moves recordings under their own name, and sees who placed what.

### The exports

In the lead's **Export**, the incident's two, for the day in hand or every day:

- **Chronology to Word**: the Timeline report's shape (Phase 8 chapter 14): the cover, the recordings with how each was placed, the band of their spans, then the entries down the pages in spells, each with a still cut from the playback copy at the moment (a video only; a sound recording's entry has none), the words heard around it, the note and the writer. Stills are cut when the document is made and never kept; the report's own limits on stills and words apply (the Incidents page's settings Still height, Stills at most, Words either side).
- **As a spreadsheet** (.csv): date, time of day, recording, placed how, note, the line, writer, written on; UTF-8 with a byte order mark.
- The audit row **Chronology exported** with the format and the day, never a word. Download notes stays as it is.

### What is not

- Incident events (a person's, the words', the assistant's) are not on the case's chronology; only the office's notes, including notes on events. Chapter 2's bridge runs the other way first.
- No date read from a file's name or header (Phase 9 chapter 7 deferred it); a jail call is placed by hand until that returns.
- No proposals by Gideon on the chronology itself; the chronology is the office's notes. (Chapter 4 gives the proposals a tab of their own, and an accepted one is a note like any other.)
- Nothing crosses a case's edge.

### Left to the build

- The clustering distance on the Notes lane (pixels, not seconds), the coverage lane's sampling, and the packing's tie rule.
- The address form of the day and the span.

## 2. An incident from a span (the second release)

Written with chapter 1 and held for a second release at the maintainer's word of 2026-10-28, so that chapter 1 is "the way we want it" first. Chapter 1 keeps the recording's clock in the shape this chapter needs, so nothing placed is redone. Built as v1.167.0 (2026-10-28) with three guards against making an incident twice, drawn in `docs/spec/mockups/phase-10-incident-from-span.html` and agreed: the case's incidents are drawn on the chronology, Make on a span that touches an incident leads with Add to it, and a later note on a camera outside an incident but inside its span offers to add the camera. Nothing is ever made without a press.

- **The incidents lane** (v1.167.0): under the Notes lane and above the hints, one bracket per incident of the case on the day, in the accent colour with its name, camera count and event count on it; hover says its span; a press opens it. An incident's span on the day is read from its cameras as the case's clock has them, so the lane and the band agree; an incident with no camera on the day is not drawn. Chapter 3's deferral of incident *events* on the chronology stands; these are the spans only.
- **Selecting**: the drag across the ruler that narrows the page (chapter 1) is the span; with a span in hand the lead offers **Make an incident from this span**, and the hint's bracket carries **Make an incident** for its own span, so the common case is one press with no drag.
- **The picker**: the recordings with bars in the span, the eight most noted, come ticked; "and N more ran in this span · Choose more" shows the rows with no notes, each with how it was placed and its span in the window; the count reads against the Panel's Most cameras in an incident (20 as shipped, 2 to 40) and in hours, "14 of 20 cameras · 12 hours' worth"; the sitting bar (Phase 8 chapter 10) redraws with each tick, so a fifteenth camera shows its price before Make. A camera with no notes is tickable; a note on it afterwards makes it an event. The name is offered from the day and the span ("6 Nov 2025, 20:24 to 20:40") and can be typed over.
- **Add comes first** (v1.167.0): when the span touches an incident, the sheet names it and leads with **Add to it**: the recordings not yet in it come ticked, the ones already in it are shown and cannot be ticked twice; the count and the sitting bar read as the incident would after adding. When the span runs past the incident, Add widens the incident to cover both and says the new span before the press; the cameras already in it keep their places. **Make a new one anyway** stands second, in the quiet style, so a second incident over the same hour is a choice and never an accident. Two incidents touched: the sheet leads with the one holding more of the span and names the other with a link; nothing is merged by rule.
- **A later note** (v1.167.0): a note on a camera already in the incident is an event of it the moment it is written (Phase 8 chapter 11), and its entry wears the incident's pill; a spell whose entries are all events of one incident wears the pill on its heading. A note on a camera outside the incident but inside its span gets one quiet line under its entry, which incident and that the camera is not in it, with **Add <camera> to the incident**; the camera arrives on the incident's clock as it sits here and the note is then an event like the others. The line is the only invitation the page makes, and it never says "make an incident".
- **Nothing is rebuilt**: each camera's placement is carried over from its clock: `clock` arrives Synced by clock, `hand` arrives Synced by hand with the same person's name and the same start (and `file` From its file); with no stamp among the cameras the first carried one sets the incident's clock to the day; the incident's own sync, by sound and by hand, stays for fine adjustment. A recording placed by its day alone is not carried, and arrives Not synced yet.
- **The notes become events by themselves** (Phase 8 chapter 11): the incident's Chronology tab opens with the entries the person selected.
- **The link back**: on the incident's Details, "From: the case's chronology, 6 Nov 2025, 20:24 to 21:31" with Open there, and one line per addition from the chronology since (added to, or widened to a span, how many cameras, by whom, when); an incident made another way and then added to from the chronology says "added to from the case's chronology" instead. Kept on the incident (`from_chronology`, migration 0097). Each making is the audit row "incident made" with how `chronology`, the day and the span; each addition the row "incident widened from the chronology" with the span before and after and the count, never a word of a note.
- **How many is too many**, from the office's own engine (read 2026-10-28): one sitting holds about nine camera hours with what they showed and about eighteen by words alone; too many is hours, not cameras; the cap of 20 stands and the sitting bar is the guide.

## 3. Deferred and ruled out

- **Incident events on the case's chronology**: deferred until chapter 2 has run on the office's cases.
- **A still on every entry on the page**: ruled out (Phase 4: nothing image-like is stored; a long day would cut hundreds on every draw). The Preview on press and the stills in the export instead.
- **Replies or threads under a note**: ruled out; the note is editable in place and the glossary has no word for a thread.
- **A chronology across cases**: ruled out (Phase 2).
- **A date read from a file**: deferred as in Phase 9 chapter 7.

## 4. Proposed events and the comparison over the whole case

Written 2026-10-29 from the maintainer's ask of the same day, after v1.167.0: the assistant proposes events and compares a report only inside an incident; both should have a place on the case, the comparison on the Documents tab read over the whole case and the proposed events on a tab of their own, both in the chronology's shape, both verified through the Preview's window with the transcript, and anything accepted from either added as a note on the recording; nothing shows on a recording unless a person accepts it. The drawing is `docs/spec/mockups/phase-10-proposed-events-and-comparison.html`; it stands with the four answers recorded on it. Three releases: the store and the note (v1.168.0, this release), the Proposed events tab and the case-wide run, the comparison against the case on the Documents tab.

### Principles

1. **One rule under both.** A proposal, from the proposer, the watch phrases, a Look for or a comparison, is a moment on one Recording with a sentence and a why, kept in a list of its own. It touches nothing until a person accepts it. Accepting writes a Note on that Recording at the line being spoken, or at the moment when nothing was said, in the acceptor's name.
2. **A note already goes everywhere.** A Note follows its Recording onto the case's chronology and onto every Incident the Recording is a synced camera of, now or later (Phase 8 chapter 11). So an accepted proposal appears wherever it should with nothing else kept, and the other way round is already true: a note written anywhere is an event of any incident its recording is in.
3. **The note says where it came from.** One small thing is kept with the note: its origin, the source, the why and what it rested on. The source pill, the why line and the AI notice on the exports survive the change from an Event of its own source to a note, and the memo reads it.
4. **Nothing is proposed onto a recording page.** A proposal is listed on its tab and its layer and nowhere else; the recording page shows only notes, and only the ones a person wrote or accepted.

### Words

**Proposed event**: a moment on a Recording the assistant, the watch phrases, a Look for run or the comparison put forward, waiting for a person's Accept or Dismiss; the code and the database call the row a Proposal. **From a proposed event**, **from the report, page 4, paragraph 2**: the words a note shows for its origin. **Make it a note**: the comparison's button, where it read Make it an event. The pages never say suggestion, candidate, auto event or AI event.

### The store and the note (v1.168.0)

- **The Proposal row**: the Case, the Recording, the Incident it was proposed for when a run on an incident made it (kept as a name if the incident goes), the time in seconds into the recording and an optional end, the sentence, the why, what it rests on, the source (assistant, watch, looked, report), the state (waiting, accepted, dismissed), who proposed it and when, who decided and when, and the note it became. Its time is never a clock: each incident reads it on its clock through its camera, and the case's chronology by the recording's own placing (chapter 1).
- **The runs write Proposal rows.** Propose events and Look for on an incident write them with the incident set, as the Event rows with `proposed` were written until v1.167.0; the run's checks, its replacing of the waiting rows and its keeping of the dismissed ones are unchanged. The incident's Proposed events layer and its strip read the Proposal rows on the clock and, until they are gone, the Event rows waiting from before the upgrade, which stay as they are until accepted or dismissed (the maintainer's answer 4).
- **Accept is one press** (answer 1): the sentence becomes a note on the recording at the line it rested on, or the line being spoken at the moment, or at the moment itself when nothing was said; in the acceptor's name, with the origin kept. A line or moment already noted keeps its note and the new words join it after a blank line. The Proposal row stays, marked accepted, pointing at the note; an Event row from before goes, the note event in its place. Dismiss and Dismiss all put a Proposal row away as before. Accept all accepts every waiting row.
- **The incident's own Accept writes the note too** (answer 3): the Chronology's row for it is the note event the page already draws, its source pill reading "Note by D. Meehan, BWC2-1, from a proposed event" (or "from a proposed event (a watch phrase)", "(looked for)"), the why on the lane's hover and in the exports under the line as before, what it rested on kept. The memo's chronology lines say "accepted from a proposed event". The AI notice prints on the Chronology's exports when any note came from the assistant's judgement, a Look for or the report, as it printed for an Event with source assistant; never for a watch phrase, since the app's search is not the assistant.
- **Make it a note** replaces Make it an event on the comparison, on the incident page and on the recording page alike (so a recording's comparison, which could make nothing before, can): the claim becomes a note on the recording at the moment, in the person's name, its origin "from the report, page 4, paragraph 2" with the mark and the assistant's why, resting on the paragraph. On an incident the note goes on the camera running at the moment, the one with a line being spoken first; a Not on camera finding, which has no moment, asks for one as before. The finding says which recording the note is on; the office's own note on the finding stays on the finding.
- **Where the origin shows**: under the line on the recording page after the writer and date ("Note, D. Meehan, 29 Oct 2026 · from a proposed event"), on the Notes tab's row, on the chronology's source pill, in Download notes under the writer, in the Chronology's exports as the source and the why. A note cleared forgets its origin. The case's chronology entry, the Notes page and the transcript exports with notes show the note as any note for now.
- **What changes from earlier phases.** Phase 6 chapter 3 and Phase 7 chapter 2: Accept writes a note and the Chronology shows a note event, not an Event with source assistant or watch phrase; the why and the source live on the note's origin. Phase 8 chapter 2, principle 1: a note may be an assistant's sentence a person adopted by accepting it, and says so. Phase 8 chapter 4, part 3: Make it a note; a recording's comparison can make one. The audit rows: **proposal accepted** (the source, whether on a line or at a moment, the incident, the case) and **proposal dismissed**, and the note's own row with where "proposal"; "event added" with source assistant is no longer written.

### The Proposed events tab (the second release)

- In the order Recordings, Search, Proposed events, Notes, Documents, Incidents, Clips, Speakers, Details; hidden when the assistant is Off and no watch phrases are listed, its count the proposals waiting.
- The chronology's shape: the days, the ruler, the recordings' band on the case's clock, a lane of the proposals above the Notes lane, the incidents lane under it; the entries by time of day with the sentence, the why, the line it rests on, the source pill, and Accept, Accept and edit (the note box with the sentence in it) and Dismiss; a recording with no day yet under Not yet placed. An accepted entry stays, greyed, saying which note it became and whose.
- **Propose events reads every recording in the case** that has a transcript (answer 2), the watch-phrase search over all of them first, the engine's windows after, the time expectation under the button; running again replaces the waiting proposals and never proposes again what was dismissed; a recording landed since the last run shows as not yet read.
- A press on a proposal's time opens the Preview's window (v1.166.0) at the moment with the lines under it, one strip above the lines saying what is proposed and where it came from, and the three choices in its foot.
- A proposal on a camera of an incident says so with the incident's pill; a spell inside an incident's span wears it on its heading.

### The comparison against the case (the third release)

- The Documents tab gains the column Against the case and, per document, Compare with the case or Comparison; the layer opens over the table in the shape every layer has, with Documents as its Back. The document keeps its home; the comparison inside an incident and on a recording are untouched.
- The document is read against each recording of the case in turn, one run per recording, the way a recording's comparison reads a transcript and its Digest, since one record of a whole case does not fit a call; the findings gather on one layer, each naming its recording, by day and time on the case's clock with By recording as the other order. Make it a note as above; Choose the moment for a Not on camera finding opens the Preview's window on a recording the person picks. Stale as today, and Compare again.

### Left to the build

- The second and third releases' addresses, the lane's drawing and the layer's filters, within the drawing.
- Whether the case's chronology entry and the Notes page show the origin's words (a later release).

## Appendix A. Audit rows added in Phase 10

| Row | Category | Details kept | Never |
|---|---|---|---|
| Recording placed on the clock | Recordings | the recording, the how (hand, day), the case | a time, a date |
| Recording taken off the clock | Recordings | the recording, the case | a time |
| Chronology exported (the case's) | Exports | the case, the format, whether one day or every day | a word, a date |
| Incident made (how: chronology; v1.167.0) | Cases | the case, the incident, the day, the span, the camera count | a word of a note |
| Incident widened from the chronology (v1.167.0) | Cases | the case, the incident, the span before and after, the cameras added | a word of a note |
| Proposal accepted (v1.168.0) | Cases | the recording, the source, whether on a line or at a moment, the incident, the case | the sentence, the why, a word of a note |
| Proposal dismissed (v1.168.0) | Cases | the recording, the source, the incident, the case | the sentence |

## Appendix B. Settings added or changed in Phase 10

None. The Reading of the exports uses the Incidents page's report settings as they stand; the fold at eight bars, the cap at eight rows, the fold of spells at forty notes and the ten-minute spell gap are constants of the page.

## Sources

- The maintainer's asks and answers of 2026-10-28, recorded in the office's planning note and in `docs/spec/mockups/phase-10-case-chronology.html`.
- The maintainer's ask and four answers of 2026-10-29, recorded on `docs/spec/mockups/phase-10-proposed-events-and-comparison.html` (chapter 4).
- Phase 6 chapter 2, Phase 8 chapters 11, 12 and 14, Phase 9 chapter 4, Phase 4 chapter 3, ADR 0027.
