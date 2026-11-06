# Gideon Transcribe, Phase 13 specification

Home as the person's desk. Where sign-in lands says what is the person's to do, what cases they can open, and what their colleagues did lately in the cases they share; nothing on it is amber, and nothing on it is only a door.

## About this document

This is the build specification for Phase 13 of Gideon Transcribe. On 2026-11-06 the maintainer asked: "Home page redesign, less confusing, no needs you information. How can we add information relevant to collaboration, or not." Three directions were drawn the same day in `docs/spec/mockups/phase-13-home-redesign.html` (today's faults, what the app knows about colleagues, A your desk, B your desk and the team, C the cases as cards, eight choices) and the maintainer chose B.

It builds on Phase 8 chapter 13 (One home and the rail), Phase 9 chapter 3 (the Team, Assigned to and Reviewed), Phase 8 chapter 2 (Notes), Phase 2 (Sharing) and Phase 3 (Send to). Read it with `CONTEXT.md` (Home, Rail, Your work, Your team lately).

Nothing in this document is office-specific. One column on the person's account (when they last pressed Seen), no setting, no service.

## Contents

1. Home as the desk

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
