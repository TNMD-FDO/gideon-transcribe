# Gideon Transcribe, Phase 13 specification

Home as the person's desk. Where sign-in lands says what is the person's to do, what cases they can open, and what their colleagues did lately in the cases they share; nothing on it is amber, and nothing on it is only a door.

## About this document

This is the build specification for Phase 13 of Gideon Transcribe. On 2026-11-06 the maintainer asked: "Home page redesign, less confusing, no needs you information. How can we add information relevant to collaboration, or not." Three directions were drawn the same day in `docs/spec/mockups/phase-13-home-redesign.html` (today's faults, what the app knows about colleagues, A your desk, B your desk and the team, C the cases as cards, eight choices) and the maintainer chose B.

It builds on Phase 8 chapter 13 (One home and the rail), Phase 9 chapter 3 (the Team, Assigned to and Reviewed), Phase 8 chapter 2 (Notes), Phase 2 (Sharing) and Phase 3 (Send to). Read it with `CONTEXT.md` (Home, Rail, Your work, Your team lately).

Nothing in this document is office-specific. One column on the person's account (when they last pressed Seen), no setting, no service.

## Contents

1. Home as the desk
2. The recording page, redrawn
3. Usage

## 1. Home as the desk (v1.215.0)

### Principles

1. **Home is the person's, not the case's.** The one thing on Home that is about the person comes first: what is assigned to them and not yet reviewed. A case's state (an incident to sync, events to check, proposals waiting, a memo gone stale, a clip that failed, the retention warning) lives on the case's own page, in its Dashboard line, and on the Cases page; Home carries none of it. Needs you and the amber heading go.
2. **A case row says what it holds and who touched it, not where it stands.** The name, one muted line, when it was last used, Open. No pills, no incident lines.
3. **The team section states only what the app records.** Who reviewed what, who wrote a note, who shared a case with you, who added recordings, who asked Gideon what, who sent you a dictation: each is a row the app already keeps, and each line opens where the thing is. Nothing is sent, nothing is counted into a figure, nothing can be written there. There is no message, no mention and no presence in the app, and none is added.
4. **Less to read.** The sentence under each section's heading goes; the rail's line says what Home is for. The keep-or-lose line stays, in small type at the foot of This session.

### Words

Added to `CONTEXT.md` with this chapter: **Your work**, **Your team, lately**; the Home and Rail entries amended. The pages never say feed, activity stream, timeline (that is the viewer's), notifications, inbox or dashboard.

### Home, in order

- **The greeting** names the person: "Good evening, Pat", by their shown name, since the page names colleagues below.
- **The notices**, as before: transcription not installed, the service down, the storage warning, a quota notice.
- **Ready to download**, as before, without the sentence under its heading.
- **Your work.** One row per case in which something is assigned to the person and not reviewed: the case's name, "4 of 6 left for you" (the person's assigned count in that case), **Next: <the oldest, by when it was added>** as the primary button, which opens that recording's page, and **All N** to the Recordings tab filtered to Mine, not reviewed. Drawn only when something is left; a person with nothing assigned sees no section. The Running now pills stay the first line of This session.
- **Cases** beside **This session** from 1600 wide, as before. Cases: every case the person can open, by last activity, each a row: the name (a link), a muted line ("8 recordings · 6 incidents · shared with Pat and Sam"; on a case shared with the person, "shared with you by Sam"; a share not yet opened wears a small **new**), the last activity's date, Open; New case and All cases on the heading. The incidents' lines and every pill go. Whom the case was last used by is not shown: the app keeps the time of the last activity and not the person, and this chapter adds no column for it.
- **Your team, lately**, under Cases: what colleagues did in the cases the person shares, newest first, twenty lines at most, from the last thirty days. Six kinds and no others: **reviewed** ("Pat Okonkwo reviewed 3 recordings in Pike calls"), **noted** ("left 2 notes"), **added** ("added 2 recordings to Harbour Street stop"), **shared** ("Sam Reyes shared Marsh Lane interview with you"), **asked Gideon** ("asked Gideon about Pike calls: 'When was the phone handed over?'", the question cut at eighty characters), and **sent a dictation** ("sent you a dictation, Walk-through, 3 Nov"). Reviewed, noted and added by one person in one case on one day fold into one line ("reviewed 3 recordings and left 2 notes in Pike calls"). Each line carries the person's initials, their name, the case's name as a link, and when ("today, 14:10", "yesterday, 09:32", "4 Nov"). The person's own acts are never listed. Nothing is drawn when there is nothing: an office of one never sees the section.
- **Seen** on the section's heading folds it to its heading, and it stays folded until something newer than the press happens; the press is kept on the person's account (`team_seen_on`), the one thing this chapter stores. The heading, folded, reads "Your team, lately · nothing new since you looked".
- **This session**: Running now as its first line, the recordings not in a case, the keep-or-lose line in small type at the foot; **Clips** as before.

### The rail

The Home item's line becomes "Your work, your cases, your team" (its title the same); the count of batches ready stays on the item.

### What is not

No mail, no digest, no count of unread, no mark on a line, no reply. Nothing an Admin's audited look would show: the section reads only the cases the person is on. An Admin who owns no case and is on none sees nothing in it. The retention warning leaves Home and stays on the Cases page, the case page and the nightly digest.

### What changes from earlier phases

- Phase 8 chapter 13, Home: the order and the sections above supersede the chapter's; Needs you, Recent cases' pills and the incident lines are gone; Ready to download, This session and Clips stand. The rail's line for Home changes.
- Phase 9 chapter 3: "6 of 80 left for you" moves from a pill on the case's row to the Your work section; the Dashboard line on the case page keeps its pills.
- Phase 7 chapter 3, the Dashboard line: drawn on the case page only, no longer on Home's rows.
- `CONTEXT.md`: Home and Rail amended; Your work and Your team, lately added.

### Audit rows

None added. Pressing Seen writes nothing to the audit log.

### Settings

None.

### Left to the build

- The thirty-day window and the cap of twenty lines.
- The words of each kind of line, and how a person with no shown name is named.

## 2. The recording page, redrawn (release 1, v1.221.0)

On 2026-11-09 the maintainer asked for the recording page to be redesigned
for how it is used, with intuitive navigation between the case's
recordings, a Map tab showing the officer's position moving against the
lines being said, and an end to the Resume pop-out covering a line. Nine
figures were drawn the same day in
`docs/spec/mockups/phase-13-recording-page.html`; the maintainer took
Direction A (the desk of Phase 1 chapter 8, tidied) with Direction C's
three columns from 2200 wide, and figure 9's four shapes of the Map tab.
This chapter amends Phase 1 chapter 8 where the two differ.

### Principles

- The words are the work. On a laptop (1366 by 647) the first line of the
  transcript stood at 600 px of 647; everything above the words has to
  earn its height.
- The shape stays. The stage beside the work area was chosen on the review
  of 2026-09-12 and the reviewers know it; the redrawing gives it its
  height back and spends the ultrawide's width, it does not replace it.
- Nothing covers a line. State that must be seen (following paused) lives
  in a bar that is always in view, never floating over the words.
- The page shows what the recording holds. A Map tab, a picture, a path
  file: each appears when the recording has it and is not mentioned when
  it cannot.

### Words

**Recording walker**: the control in the head that moves between the
case's recordings (previous, next, and the place, "6 of 8", opening the
case's list). **Follow state**: "Following" or "Paused while you read" at
the tab bar's end. The pages say "the case's recordings", never siblings.

### Release 1: the head and the height (v1.221.0)

- **The recording walker** stands at the head's left in a case, where the
  back arrow stood: ‹ and › go to the previous and the next recording of
  the case that has a transcript, in the case's list order (newest first,
  as the Recordings tab lists them); at either end the arrow is greyed
  with why. The place ("6 of 8", counting every recording) opens the
  case's list: each recording's title, kind, length and state (not ready,
  in the queue, no transcript), the recording in hand marked and scrolled
  into view, and Download all transcripts at the foot. The keys `<` and
  `>` walk too, and the shortcuts overlay lists them. Outside a case the
  head is as it was. The list of the case's recordings that stood under
  the video since Phase 8 chapter 1 is gone; the walker is its place.
- **One head line** from 1280 wide: the walker, the title cut to one line
  with its full name as its tooltip and the rename pencil shown on hover
  or focus, the pills, then the search and the actions. Under 1280 the
  head keeps its two lines (v1.108.0).
- **The marking strip** under the timeline is hidden at rest and its
  sentence is the timeline's tooltip; while a range is marked the strip
  shows as before (the range, Preview, Save clip, clear).
- **The speakers fold** to one row from the start on a window under 900
  tall, a remembered choice winning either way: the chips in one line that
  fades at its end, the count, the tools. The "Click a name" hint shows
  only from an information mark in the tools (and unfolds the cast to show
  itself); Got it hides it; nothing is remembered and nothing shows by
  itself. Suggest names shows when the cast is unfolded, as before.
- **The follow state** sits at the tab bar's right end: "Following" with
  pause while the words follow the sound, "Paused while you read" with
  Resume (F) once the reader scrolls or presses pause. The pill that
  floated at the top of the transcript is gone. The Follow tick on the
  transport is unchanged.

### Release 2: the hand-off (v1.222.0)

- **The same moment on the next camera.** ‹ and ›, and the keys `<` and
  `>`, keep the moment when this recording and the neighbour are both
  placed on the case's clock (ADR 0027): the neighbour opens at the same
  time of day (`?t=` as citations use it), and the arrow's tooltip says
  "at the same moment". Off the clock on either side, or when the moment
  falls before the neighbour starts or after it ends, the neighbour opens
  from the start. The page works it out when the arrow is pressed, from
  the playhead, as All cameras does.
- **The next assigned to you** at the foot of the walker's list: the
  reader's next assigned recording of the case not yet reviewed, oldest
  after this one first (Phase 9 chapter 3's rule), with Open; absent when
  there is none.

### Amended by v1.225.0: the map in the stage

On 2026-11-09, with the four releases live, the maintainer found the Map
tab's layout unnatural, wanted the whole transcript tracking with the
dots (not a seven-line list), and wanted other recordings on the map only
when chosen. Three directions were drawn in
`docs/spec/mockups/recording-map-desk.html` and Direction A taken:

- **The map stands in the stage,** under the picture and the transport,
  following the player as release 3 had it; the Transcript keeps its whole
  column, untouched, and its lines are the dots: a line pressed moves the
  marker and the filled pip, a pip pressed scrolls the transcript to its
  line and plays from it. The Map tab, its panel, the Said here list and
  the map-beside-the-words of release 4 are gone.
- **A switch in the transport,** Picture · Map · Both, Both to start where
  there is a map, remembered in the browser; popping the picture out leaves
  the stage to the map. The shape marks (around, file waiting) stand with
  the switch; the waiting file's card and the around notice above the map.
- **One slim bar on the map's top edge:** a two-way choice, **This camera**
  (alone, as the map starts) or **All cameras** of the day with the others
  grey, remembered for the case apart from the case Map tab's own ticks
  (v1.225.1; v1.225.0 had a menu of the other cameras with a tick each,
  which dropped off the bottom of a laptop's stage); **Centre** brings
  this camera back to the middle and follows it again; then the trails,
  the events and More (Fit all, Tidy names, Save a picture). On a camera
  with no file of its own (the around shape) the map starts on All cameras.
- **The Now line** stands on the map's foot with the moment and the time
  of day.
- The map is not drawn under 1280 wide, where the stage is not a column.
  Release 3's four shapes, its pips and its shape watcher are unchanged.

### Release 3: the Map tab (v1.223.0, as first built)

- **The map, following the player.** The case's map script (Phase 12
  chapter 1) draws into a host on the recording page in a recording mode
  beside its incident mode: the page's player is the clock
  (`window.RecordingClock`, seconds of the day on the case's clock), this
  camera is selected and lit from the start, the other cameras of the day
  are drawn where they were at the moment, and the map keeps this camera in
  view until the person moves it; **This camera** brings it back. A press
  on another camera's marker opens that recording at the same moment where
  both are on the clock and the moment falls inside it, else from its
  start. The transport is the incident pane's (count, Show, the events'
  ticks, Fit all, Tidy names, Save a picture) without Larger map; the tab
  never opens in a window of its own, since it follows this page's player.
- **The lines said.** Every line of the transcript with a fix is a pip on
  this camera's path where it was said, the line being spoken filled; hover
  shows the time, the speaker and the words, a press plays from there. A
  line said where the camera had no fix, or outside the file, has no pip.
  The timeline under the head gains a tick at each line's start on every
  recording with a transcript.
- **Said here.** Beside the map, the line being spoken in the middle with
  three before and three after, each a press to play from; a dashed ring
  where this camera had no fix at the time, filled for the line being
  spoken; "whole transcript" returns to the Transcript tab. Under the map
  the Now caption: the moment, the time of day, the speaker and the words.
  Under 1100 wide the list is not drawn.
- **Four shapes, by what the recording holds** (figure 9), decided on the
  server from the picture, the clock placement and the case's files:
  - a recording without a picture (a jail call, a phone line, an interview
    room) never has the tab, and nothing says why;
  - a camera with no file of its own that is not on the case's clock, or
    on a day no other camera has fixes, has no tab; the Details tab's
    "Camera's file" row says "none yet" (and "not on the case's clock"
    where that is so) and offers the case's Map tab, where files are added;
  - a camera with no file of its own, on the clock, on a day other cameras
    have fixes, has the tab marked **around**: the others drawn, this
    camera with no marker and no pips, the Said here list by time alone,
    and one line above the map saying its own place is not known;
  - a camera whose file waits on the case (flagged against it when it came,
    or named like its video) has the tab marked **file waiting**, opening
    on the waiting file's card (its name, kind, readings and why it was not
    paired) with Add anyway and Remove, the case Map tab's own two acts;
    done, the page loads itself again at the same moment and tab.
- **The page notices.** Every recording of a case with a picture asks
  `recording/<id>/map-shape` (the shape alone, no position) every thirty
  seconds while its tab is in view; when the answer differs from the page,
  it says so and loads itself again at the same moment and tab. The
  decision of 2026-11-09, left to the build: the page reloads rather than
  redrawing in place, since the map's libraries and the case's JSON are
  not on a page that had no tab.

### Release 4: the three columns (v1.224.0)

- **From 2200 wide, in a case,** the page takes three columns under the
  head and the timeline: the case's recordings in a **case column** of
  their own at the left (300 px: the case and its count, Download all,
  every recording with its kind, length or state, the one in hand marked,
  the next assigned to the reader at the foot), the work area in the
  middle with the words at their reading measure, and the stage at the
  right with its grip on its left edge (dragging left makes the picture
  wider). A press on a column row keeps the moment as the walker's arrows
  do. The walker stays in the head, since it also walks by key. Under 2200
  nothing changes: the column is not drawn and the walker's list is the
  case's list.
- **The Map tab beside the Transcript.** From 2200 wide, pressing Map
  keeps the Transcript panel in view and opens the map panel beside it,
  half and half, as the incident page's two panels do; pressing Transcript
  closes the map panel. Crossing 2200 with the map open joins or parts the
  two. Under 2200 the Map tab replaces the Transcript as before.
- **A sound recording** (no picture) in a case keeps its transport under
  the head and gains the case column alone: two columns, the words beside
  the case's recordings.
- **Left to the build, decided (2026-11-09):** figure 4 drew the map a
  second time, small, under the picture in the stage. One map is drawn, in
  the work area beside the words, and the stage keeps the picture, the
  transport and the Now line: the same map script draws into one host, and
  a second small map would have said less than the words-and-map pair.

### What is not

No new page, no new endpoint and no new setting in release 1. The walker
does not reorder the case; the case's order is the Recordings tab's. The
Map tab draws no guess at a camera's position.

### Audit rows

None added.

### Settings

None.

### Left to the build

- The fold's threshold (900 tall) and the walker list's width (34rem).
- The "around" map's distance words and the Said here list's length.

Sources: the maintainer's asks of 2026-11-09; the drawing
`docs/spec/mockups/phase-13-recording-page.html`; Phase 1 chapter 8 (the
Desk layout); Phase 8 chapter 1 (the case's recordings under the video);
Phase 12 chapters 1, 4 and 5 (the map, where a line was said, the map pane
on the incident page).

## 3. Usage (v1.239.0)

On 2026-11-13 the maintainer asked what would make the app better, chose two of six ideas ("let's do 5 and 6"), and after a drawing of each (local pages, as the mock-ups of this period are) said "They stand, build". This is the first: a page in the Panel that says how much the office uses the app, so the server can be justified and another office can be told what to expect. The second, a practice case, is a later chapter.

### Principles

- **Counts only.** Never a Recording's name, a Case's name, a word that was said, a question that was asked, or who did anything. The page names no person and no Unit.
- **History that does not shrink.** The audit log is kept a set number of months and a Case that reaches its Retention policy takes its Recordings with it, so a figure counted from what the server still holds would fall as it was swept. The app keeps one row of numbers a month, for the life of the install.
- **Nothing leaves the building.** The page sends nothing anywhere. Its one button puts plain words on the Admin's clipboard.

### What is kept

- One row a month (the month's first day in the office's time, and a set of numbers). Each night at half past three, with the other nightly work, the month being lived in and the month before it are counted again from the Jobs, the Recordings and the audit log, and the numbers are joined to the row's: **a count never goes down** (the higher of the stored figure and the fresh one stands, so a Case swept between two counts changes nothing), a level (the disk held, the disk free, the accounts) is the newest and is set only by the month being lived in, and a typical figure is the one worked out from more.
- The first count is made at the upgrade (migration 0110), or on the first night where that did not finish: every month the server still holds anything of, up to thirty-six, counted once. A month that had already ended at the first count could only be counted from what was still held that day; the page tells those months apart (a lighter bar and one sentence).
- **What a month's numbers are.** The Recordings transcribed (each once, however often it was run; the speakers pass is not a transcription) and their hours, by Recording type and by spoken language, and the hours marked for translation. The waits from a file's arrival to its Transcript being ready (v1.239.1: from the Recording's own making, since a Job is made only once the file has been prepared; a Process again and a Live recording are timed from the Job's making, the first's file having arrived long before and the second's while it was still being recorded): how many, the typical (the median) and the longest. The people who did anything the audit log records; the Cases worked on (a Case named on a row, or holding a Recording named on one) and the Cases opened. The people who used each part of the app. The AI assistant's calls by kind, how many failed and why, and the typical time of a chat answer; the kinds are what people asked for (chat questions, Summaries, Speaker checks, Proposed events runs, Incident memos, Comparisons, Translations, Speaker suggestions) and, apart, Vision's own work on a video (a call for every span described, every part of a Digest and every camera clock read), which the page says in one sentence under the bars and never draws as a bar (v1.239.1). The uploads accepted and refused, and the transcriptions that failed. The levels: what the Recordings hold on disk, the drive's size and free room, and the accounts not deactivated or blocked.
- **The parts of the app.** Notes, Corrections, Naming speakers, Chat, Clips, Exports, Incidents, Comparison, Sharing, Dictation and Live recording are read from the audit rows a person's use already writes. A search in a Case, the Map and Bulk transcription write no audit row (the audit log records the thing that happened, never the page that showed it), so for those three the app keeps a mark: the month, the part and the person, one row however often. A mark is deleted once the month after its own has ended, when its month's count is final: what stays is the number and never who. The page says these three are counted from the first count's day.

### The page

- **Usage**, in the Panel's rail after Queue, for Admins alone. Opening it writes no audit row, as no Panel page does: it holds counts and is no reading of anybody's work.
- Three periods: **This month**, **Last 12 months** (the default) and **Since the install**. Five figures across the top: the hours transcribed, the Recordings, the people, the Cases worked on, and the typical wait with the longest. Under them: twelve months of hours as bars (always the last twelve, the month so far outlined); what was transcribed by Recording type (the six largest, the rest folded) with the spoken languages and the share translated; the parts of the app by people; the AI assistant; the disk (held, free, how fast it grows over the last three month-to-month steps, and the months of room that leaves above the free-space floor, amber under six); and what went wrong.
- **People are counted a month at a time**, because the app keeps no record of who and so cannot tell the same person in two months from two people. Over a period longer than a month the people and the Cases are a typical month's (the median of the months that have ended), and the parts are the last whole month's, named on the page; until a whole month has been counted as it was lived, they are the month so far.
- **Copy the figures** puts the period's figures on the clipboard as a few lines of plain words, which the page also shows folded; where the browser gives no clipboard the words open to be selected by hand.
- Before anything has been counted the page says the first count is made tonight.

### Where this differs from the drawing

- The short period is the month so far and not a rolling thirty days, which a tally by the month cannot give.
- The drawing said opening the page would write an audit row. It does not: no Panel page does, and this one shows nobody's work.
- The drawing's line for the server's graphics cards is left out of the copied words; the Release is given.

### Amendments applied

- **2026-11-13, v1.239.1.** Two figures the first count got wrong, found by the read-only check on the office's server the day v1.239.0 went on and fixed at the maintainer's word ("Yes, fix both"). The AI assistant's pane counted Vision's own work under Other, thousands of calls where people had asked for tens, so every bar of what people asked for was a sliver: those kinds are named, counted apart and said in a sentence, and Speaker suggestions, which a person asks for, gains a bar. And the typical wait began at the Job's making, which is after the file has arrived and been prepared, so it read as seconds: it begins at the file's arrival, and the tile says "from a file's arrival to ready". Migration 0111 counts the stored months again once for these two sets of figures, replacing a month's only where the server still holds as much as was counted, so a month the audit log no longer reaches keeps what it has.

### Carried

- A split by Unit, where an office lists Units, only if asked for; a Unit of fewer than five people folded into the rest. A figure by person is ruled out.
- The practice case's recordings and people are to be left out of every count here, save one line saying how many people made one.

### Left to the build

- The six Recording types shown before the fold, the four languages named, the thirty-six months a first count reaches, and the six months under which the disk's room turns amber.

Sources: the maintainer's ask and choice of 2026-11-13; the drawing `.claude/tools/preview/usage-figures.html` (local); Phase 1's audit log and Panel chapters; Phase 2's Retention policy.
