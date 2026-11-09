# Gideon Transcribe, Phase 13 specification

Home as the person's desk. Where sign-in lands says what is the person's to do, what cases they can open, and what their colleagues did lately in the cases they share; nothing on it is amber, and nothing on it is only a door.

## About this document

This is the build specification for Phase 13 of Gideon Transcribe. On 2026-11-06 the maintainer asked: "Home page redesign, less confusing, no needs you information. How can we add information relevant to collaboration, or not." Three directions were drawn the same day in `docs/spec/mockups/phase-13-home-redesign.html` (today's faults, what the app knows about colleagues, A your desk, B your desk and the team, C the cases as cards, eight choices) and the maintainer chose B.

It builds on Phase 8 chapter 13 (One home and the rail), Phase 9 chapter 3 (the Team, Assigned to and Reviewed), Phase 8 chapter 2 (Notes), Phase 2 (Sharing) and Phase 3 (Send to). Read it with `CONTEXT.md` (Home, Rail, Your work, Your team lately).

Nothing in this document is office-specific. One column on the person's account (when they last pressed Seen), no setting, no service.

## Contents

1. Home as the desk
2. The recording page, redrawn

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

### Releases 2 to 4 (to come, at the maintainer's word)

- **Release 2, the hand-off.** ‹ and › keep the moment when both
  recordings are on the case's clock, so the same moment plays from the
  next camera; the next recording assigned to the reader at the list's
  foot.
- **Release 3, the Map tab** (figures 6 and 9): the case's map script
  following this page's clock as it follows the incident page's; the
  camera's path lit and its marker on the playhead; the other cameras of
  the case on the clock drawn grey with their distances; a pip on the path
  for every line where it was said, pressable; a Said here list beside the
  map; the Now caption; the camera's own readings. Four shapes by what the
  recording holds: no tab for a kind that can never carry a file (a jail
  call, a phone line, an interview room); no tab and the Details offer for
  a camera with no file not on the clock; the tab marked "around" for a
  camera with no file of its own on the clock among cameras that have one,
  drawing the others and never this camera; the tab marked "file waiting"
  opening on the waiting file's card. The page's state poll moves between
  the shapes without a reload. No position is sent to the server.
- **Release 4, the columns** (figure 4): from 2200 wide the case's
  recordings as a left column, the words at their measure, the stage with
  the picture and the map stacked; the Map tab opening beside the
  Transcript as the incident page's two panels do. With a picture and no
  file the stage holds the picture alone; with neither, the stage column
  goes and the transport and the Now line sit in a bar under the timeline.

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
