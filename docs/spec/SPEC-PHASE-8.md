# Gideon Transcribe, Phase 8 specification

The pages laid out, notes, a way to report a problem, the police report beside the cameras, the incident page's desk kept and made plainer to use, the report brought to the reader in a card, the pages that fail well, and the event's line with the merge hint's rule. All eight chapters are written for the build; chapters 4, 7 and 8 are in parts.

## About this document

This is the build specification for Phase 8 of Gideon Transcribe. Phases 6 and 7 (`docs/spec/SPEC-PHASE-6.md`, `docs/spec/SPEC-PHASE-7.md`) gave the app the incident page, the chronology, the assistant across cameras, search, and Gideon; each added a piece to pages that were laid out before it existed. On 2026-09-19 the maintainer's list named what that had done to the pages: the Start page's door to the cases says the wrong thing, the case page's tabs are small words, the recording page has dead space under the video, the incident page's Chronology tab is bunched and its pop-outs sprawl, Ask Gideon shoves the page aside, and the office's 49-inch screens are half used. The choices were drawn as mock-ups (`docs/spec/mockups/phase-8-layouts.html`, `docs/spec/mockups/phase-8-incident-panel.html`) and picked the same day; chapter 1 is written from the picks.

Read it with the same companions as Phase 7: `CONTEXT.md` (the glossary, with the Phase 8 words Layer and Work panel), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`, and the mock-ups. The conventions of the Phase 1 document apply unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing office-specific enters the repository.

## What Phase 8 adds

- **The pages laid out** (chapter 1, for the build): one rule for the incident page's work panel (tabs, and layers over them, with a Back that returns exactly), the Chronology tab unbunched, the proposals and Find's hits as layers, Gideon as one floating panel with the same shape on the three pages that have it (the case page, the recording page, the incident page) and nowhere else; the case page's tabs as a bar of sections with icons and counts, the same look on every page that has tabs; the recording page's case list under the video; the Start page's door saying Cases; and columns that follow the width up to the 49-inch screen.
- **Notes** (chapter 2, for the build): a note on a line of a transcript under the rules an Event's note already has, exports that carry notes only when chosen, a Notes tab on the case page that lists every note in the case with the moment each points at, and Gideon told the notes as the office's own words.
- **Report a problem** (chapter 3, for the build): one link on every page that opens a small box for a problem or an idea, in the person's own words, with where they were added only with their tick; a Report kept on the Panel's Reports page with New, Seen and Done marks, counted on the rail and the Status page, and mailed to the Operator address when mail is configured. Nothing leaves the building.
- **Documents beside the cameras** (chapter 4, for the build, in three parts): the police report added to an incident or a camera as a PDF, read page by page (OCR for a scan), its paragraphs cited by Gideon and found by Search with the real page shown; and the comparison, the report against the record with every finding cited on both sides and marked agrees, differs, not on camera or not in the report, each one press from becoming an event.
- **The desk, kept** (chapter 5, for the build): the incident page as it stands, with the focus camera behaving like a video (a player bar on the picture, the picture at its own proportions), the focus camera's words following the clock in the space under the filmstrip, Clip as a button on the transport and a track on the strip that says what it is for, a lane of the clips made, and a handle that sizes the work panel.
- **The report in place** (chapter 6, for the build): one paragraph card, opened in place from every citation to a paragraph (Gideon's answers, the comparison's rows, a chronology row or event that rests on a paragraph, the memo, Search's hits, the Notes tab), showing the page's picture with the paragraph lit and the words around it, with Open the document one press further; the comparison's Word export in the Export menu; a handle on Gideon's panel.
- **The pages that fail well** (chapter 7, for the build, in four parts): a session that ends under an open page is said on that page, once, with Sign in again returning the person to where they were, and the page stops asking the server for anything; one page in the app's frame for an address that is gone and one for the server's own failure; the Admin's warning as a pill beside the title instead of a band; the case page's list given the width.
- **The event's line, and the merge hint's rule** (chapter 8, for the build, in two parts): an Event's text read as a line and a detail wherever it is drawn, so a row says what happened in one line and puts the rest under it, nothing stored twice and no data changed; and the Speakers page's merge hint offered to a fragment with a neighbour, the Speaker whose turns its few lines sit inside, and to nobody else.
- **The sitting on the case page** (chapter 10, for the build): the Incidents tab's row carries the bar in small, and the offer to make an incident shows the bar as the incident would read; each camera's share is kept on the camera so a case page reads no Digest to draw a row.
- **One sitting** (chapter 9, for the build): a bar on the incident page's Cameras tab that says how much of the incident the assistant can hold at once, in hours of camera, with a sentence for each zone that says what changes; everything said always read and the longest cameras' pictures left out first when the sitting is full, with a pin to keep one; the engine's window read from the engine so a larger model changes every bar and no setting; and the memo, the comparison and Gideon saying what they read.
- **A note is an event, and the Event card** (chapter 11, for the build): a note on a line of a synced camera is an event on that incident's chronology at the line's moment, one thing in two places, changed or removed from either; the Events lane draws a mark alone per event, and one Event card, light on hover and whole on a press, carries what the lane's labels and the row's muted line used to spell out, from the strip, the focus camera's scrub bar, the Chronology row and the viewer's timeline.
- **The Timeline view, the chronology figure, and the camera that comes to the front** (chapter 12, for the build): a press on an event, from the lane, a row, the card, a tick, the memo or Find, brings the event's own camera to the front as it seeks; the Chronology tab gains a Timeline view beside its rows, the cameras' spans as a band and the events down the page in spells with a numbered mark in the camera's colour; the Word export prints that figure in place of the strip picture, which goes.
- **One home and the rail** (chapter 13, for the build): sign-in lands on Home, which leads with a finished batch's download, the cases that need the person, what is running, this session's recordings with the keep-or-lose line and every case; a rail down the left of every page carries the two actions at its top and the places with one line each saying what they are for; the Start page and the top bar's places go; a batch's download is on Home and on My recordings, never only on the batch page.

## Contents

1. The pages laid out
2. Notes
3. Report a problem
4. Documents beside the cameras
5. The desk, kept
6. The report in place
7. The pages that fail well
8. The event's line, and the merge hint's rule
9. One sitting
10. The sitting on the case page
11. A note is an event, and the Event card
12. The Timeline view, the chronology figure, and the camera that comes to the front
13. One home and the rail
14. Deferred and ruled out

Appendices: A. Audit rows added in Phase 8. B. Settings added in Phase 8.

## 1. The pages laid out

Written 2026-09-19 from the maintainer's list of the same day and the picks made from the two mock-up pages: the Start page's door says Cases (1A); the case page's tabs become a bar of sections (2A); the recording page's case list goes under the video (3A); columns follow the width (4A); the work panel is tabs and layers (the rule); the Chronology tab holds the events with air (1A of the second page); the proposals are a layer (2A); Find's hits are a layer (3A); Gideon is one floating panel on every page (4A, amended the same day at the maintainer's word that Gideon's design language be the same throughout: the incident page gets the panel too, not a tab).

### Principles

1. **The wall and the strip never move.** On the incident page nothing opens above the cameras or beside them; everything a person does opens inside the work panel. A person who opened the page to watch is never pushed off the picture.
2. **Tabs, and layers over them.** The work panel has tabs for what is always there and layers for a job in hand. A layer opens over the tab, has one shape, and closes to exactly where the person was: the tab, its scroll, the row that was marked, the moment being watched. One way in, one way out, for every piece.
3. **One shape for the tabs everywhere.** The case page, the recording page and the incident page's work panel draw their tabs the same way: a bar of sections, an icon and a count each, the open one drawn as a card joined to its content. What a person learns on one page holds on the next.
4. **Room to read.** A row on the Chronology says what happened on one line and everything about it on a muted line under it; the controls sit behind a row menu and on the row's own layer. Fewer things on the screen at once, each with air.
5. **Gideon does not shove, and is the same everywhere.** On every page that grounds a chat (the case page, the recording page, the incident page) the same button opens the same panel, floating over the page's right edge with the same head and the same ways in and out; the page under it does not reflow. There is no other Gideon: not a tab, not a drawer.
6. **Width is used, not capped.** Columns follow the window's width from a laptop to a 49-inch screen, and a window dragged from half the screen to the whole re-lays itself. Nothing is remembered per screen.
7. **Words stay.** Cases stay Cases; nothing in the glossary changes for a page's look.

### Words

**Work panel**, the incident page's panel of tabs and layers (chapter 1 of Phase 6 called it the panel); **Layer**, one job opened over a tab, with a Back; **Back**, the layer's way out, the tab's name after the arrow ("&lsaquo; Chronology"); **the row menu**, the "&middot;&middot;&middot;" on a Chronology row. The floating Gideon is **the panel**, on the three pages that have it; the pages never say drawer, modal, dialog (for a layer), popup or pop-out.

### The Start page

- The tile that read "Open a case" reads **Cases**, as the menu does, with the counts under it ("12 cases, 2 shared with you"; a Collaborator sees "3 cases shared with you"; nobody sees a count of zero, the tile then says "None yet"). Nothing else on the Start page changes.

### The tabs, everywhere

- **The shape.** A bar of sections under the page's head: each section a word and an icon, with the count beside the word where a count means something (Recordings 5, Clips 3, Speakers 6, Incidents 1; Search and Gideon carry none); the open section is drawn as a card joined to the content under it, the others as plain words that light on hover. Larger type than today's underlined words; the bar wraps on a narrow window.
- **The case page**: Recordings, Search, Clips, Speakers, Incidents, in today's order, under the dashboard line (chapter 2 adds Notes after Clips). The Gideon tab goes: the panel is Gideon's one place, and it holds the same conversations.
- **The recording page**: the work area's tabs (Transcript, Summary, Clips, Details, and Open in a window at the end) take the same shape; the Gideon tab goes, for the same reason.
- **The incident page's work panel**: Chronology, Memo, Cameras, Details, with Find's magnifier at the right of the bar.
- **Icons**: one set, drawn as the app's other icons are (`icons.html`), one per section; the build chooses them within the rule that an icon never stands alone without its word.

### The recording page

- **The case's recordings under the video.** Under the stage's transport, a card headed "This case: <name>" lists the case's recordings (this one marked, each with its length, a press opening it at its start), with **Download all transcripts** at the card's head; a case of more than eight shows eight and "and N more", which opens the case page. The transcript column runs the full height of the page beside the stage and the card.
- **What goes**: the section below the transcript that held the same list, and the control that hid it. The stage's resize grip stays.
- **A recording in no case** shows no card; the space under the transport is the stage's.

### The widths

- **The rule.** No page caps its width. Columns follow the window: the incident page's wall shows 2 across to 1919 pixels, 3 to 2559, 4 to 3839, 6 from 3840 (Grid layouts a person chose still win; Focus keeps one camera large and lets the filmstrip grow to two rows). The work panel is 380 pixels wide to 2559 and 760 from 2560; from 3840 it can show two tabs side by side (Chronology beside Memo, a second tab bar), a choice the person makes with **Two panels** at the right of the bar, remembered in the browser. The strip runs the whole width at every width.
- **The case page** is two panes to 2559 and three from 2560: the list, the open recording's details (or the Search tab's hits, or the Chronology of an incident opened from the Incidents tab in place), and the About pane.
- **The recording page** is the stage over the case card with the transcript beside them to 2559; from 2560 the transcript, the stage and the case card, and the work area's other tab (Summary, Clips, Details) can sit side by side in three columns, with the same **Two panels** choice.
- **Re-laid on resize.** The pages read their width when drawn and when the window changes, so a window dragged from half of a 49-inch screen to the whole of it re-lays without a reload. Nothing is remembered per screen; only the Two panels choice and the layouts a person already chooses are remembered, per person, in the browser.

### The work panel: tabs and layers

- **Tabs**: Chronology, Memo, Cameras, Details. What is always there.
- **Layers**, one at a time, each opened over the tab the person is on: **Proposed events** (from the Chronology tab's button), **Sync** (from the transport, a tile or the Cameras tab), **an event** (add, edit, note, clip this event: from Add event here, the E key, a row's menu, a line under a camera, a citation), **a clip** (from an event's layer or a span dragged on the strip), **Find** (from the magnifier). The sheets of Phase 6 chapter 4 and chapter 5 (the event box, the clip box, the Sync sheet) become layers; nothing opens above the wall any more.
- **The head**, the same on every layer: **&lsaquo; <the tab's name>** on the left, the layer's name, and the layer's one main button on the right (Accept all, Sync all, Save, Make the clip, none for Find). Escape is Back. A second Back on a layer opened from another layer (a clip from an event) returns to the event's layer, then the tab.
- **Back returns exactly.** Opening a layer remembers the tab, its scroll, the row marked as current and the moment being watched; Back restores the tab and its scroll and marks the row; the moment is not moved back (the person may have seeked while on the layer, and the cameras are where they left them). Saving on a layer returns the same way, with the saved row marked and lit for a moment.
- **A layer's times drive the wall**: a proposal's time, a hit's time, an event's time play every camera as a Chronology row's does.
- **Nothing else opens anywhere else.** The Add cameras dialog and the Delete confirmation, which stop the page rather than work on it, stay dialogs.

### The Chronology tab

- **The head**: **+ Event here** (the primary button), **Propose events** with a warning pill carrying the count waiting ("6 waiting") when some wait, and the count line ("4 events, 1 to check") at the right; the About paragraph as one line with Edit under the head, or "About: none yet" with Write it.
- **The rows**: the time (a citation that plays every camera), the line with its To check pill, and the row menu; under them one muted line: the source ("Added by alvarez", "Words, BWC2-098679", "Assistant", "Watch phrase"), where it is seen, the note in italics with its writer, the why in italics for an assistant's event, and the clip mark ("1 clip ready", a link). The row being watched is lit as today. (Amended by chapter 11: the muted line moves into the Event card, which the row's line opens; the row keeps the time, the line, the To check pill and gains a source pill.)
- **The row menu**: Edit (the event's layer), Add a note (the layer with the note field focused), Clip this event (the clip layer), Remove.
- **What leaves the tab**: the proposals' list, the Look for box, Find's hits, the event box and the clip box (all layers), and the per-row Edit and Clip buttons (the menu).

### The Proposed events layer

- **Opened** from the Chronology tab's button; the head reads "&lsaquo; Chronology", "Proposed events (6)", **Accept all** on the right.
- **Under the head**: **Propose again**, the **Look for** box (this run only), and the state line ("Proposed 6 events at 14:02, 1 from the watch phrases"; "Reading the cameras..."; the cut-short words). While a run is going the rows say so and Accept, Dismiss and Accept all are greyed, as v1.63.2 has it.
- **The rows**: as the Chronology's, with **Accept** and **Dismiss** in place of the menu and the why under the line. Accept moves the row onto the chronology behind the layer; the layer stays until Back, so a person works down the list.
- **Empty**: "Nothing waiting. Propose events reads each synced camera and proposes what it finds; nothing joins the chronology until you accept it."

### The Find layer

- **Opened** by typing in the magnifier's box at the right of the tab bar (the box is the magnifier, opened by a press or by the / key); the head reads "&lsaquo; Chronology" (or the tab it was opened from), "7 moments for "gun"", and "Enter: next" at the right.
- **The rows**: the time, the line with the matched words marked, a small **E** on a words hit; under them the source ("Said on BWC2-098679, Speaker 4"; "Event 3, why: a weapon changes the stop"; "Memo, paragraph 2"). The hit being watched is lit; Enter and Shift+Enter walk them; a press seeks every camera and brings the camera it was heard on to the front with the sound, as Phase 7 chapter 3 has it.
- **Back** clears the box and returns.

### Gideon's place

- **One panel, on the three pages that have it and nowhere else.** On the case page, the recording page and the incident page, as today, **Ask Gideon** (the same round button, the same place at the bottom right) opens the same panel: floating over the page's right edge, 420 pixels wide, the window's height less a margin, a shadow, the page under it unchanged and scrollable; the same head (the name, the grounding, a pop-out arrow, Close); the Ask button, while the panel is open, is its Close; Escape closes; open or closed remembered per person per kind of page. On a narrow window the panel is the whole window. The pop-out arrow puts the conversation in a window of its own that follows the page, as the Speakers window does.
- **What it holds** is the page's grounding, as Phase 7 chapter 5 has it: the case's conversations on the case page, the recording's on the recording page, the incident's on the incident page. Nothing else shows Gideon: the Gideon tabs on the case page and the recording page go, and the incident page never had one. The drawer that pushed the page aside goes.
- **On the incident page** the panel floats over the right of the page, so the wall stays in view beside it on any window of 1280 pixels or more; a citation seeks every camera and brings the camera it was heard on to the front, and + event opens the event's layer at that moment with the line filled. From 2560, where the work panel is 760 wide, the panel floats over the work panel's right half and the Chronology stays readable beside it.
- **The preview** plays inside the panel on the case page; on the recording page the panel's citations seek the page's player; on the incident page the cameras are the preview.

### In and out

- **In**: the Start page's tile; the tab bar's shape on three pages; the case card under the video and the removal of the section below the transcript; the width rule with Two panels; the work panel's layers with the head and the Back; the Chronology tab's rows and menu; the Proposed events layer; the Find layer; Gideon as one floating panel on the three pages that have it, the Gideon tabs gone; no new page gets Gideon.
- **Out**: the word Workspace, a rail of sections, a density switch, dialogs for proposals, a filter of the chronology in place, and any change to what the pages hold or to the words the glossary fixes.

### What changes from earlier phases

- **Phase 1, the Start page and the recording page**: the tile's words; the case card under the video; the work area's tabs.
- **Phase 2, the case page**: the tabs' shape; three panes from 2560.
- **Phase 6 chapters 1, 4 and 5**: the sheets become layers; the wall's columns follow the width; the Sync sheet is a layer; the work panel's tabs gain Gideon.
- **Phase 7 chapter 1**: the event box and the clip box are layers; the clip from the strip opens its layer. **Chapter 2**: the proposals and the Look for box move to their layer. **Chapter 3**: Find's hits are a layer. **Chapter 5**: Gideon's drawer becomes the floating panel on every page; the Gideon tabs of the case and recording pages go, the panel holding their conversations.
- The exports, the audit rows, the settings and every word in the glossary are unchanged.

### Audit rows

None.

### Settings

None. Two panels and the panel's open state are the browser's, per person.

### Not in this chapter

- **Notes on a transcript** and the case's Notes section: chapter 2.
- **The Panel's pages** and the Cases list at 49 inches: they are lists and settings, and their widths stay as they are.
- **A redesign of the Start page** beyond the tile's words. (Superseded by chapter 13, v1.86.0: the Start page went, and Home and the rail took its place.)
- **Remembering a layout per screen**: the width is read, not stored.

### Left to the build

- The icon for each section, within the app's icon set.
- The exact breakpoints and the panel widths, within the figures above; how the two-panel bars share the width.
- The row menu's order and whether Remove asks for confirmation (it does today).
- The animation, if any, when a layer opens and closes (a short slide is enough; none is fine).
- Where the floating panel remembers its pop-out and whether the popped-out window follows the page's case or recording when the person moves on.
- How the case card under the video lists a case of one recording (the card shows it alone with Download all transcripts).

## 2. Notes

Written 2026-09-19 from the maintainer's list of the same day ("notes in transcript") and the shape outlined beside chapter 1. Phase 7 chapter 1 gave an Event a Note: a person's own line under it, told to the assistant as the office's words and never written by it. This chapter gives a line of a Transcript the same, under the same rules, and gives the case page one place where every note in the case is read together.

### Principles

1. **A note is the office's own words.** Written by a person, changed by a person, removed by a person. The assistant is told them as the office's own, respects them, never rewrites them, and never writes one. Phase 7 chapter 1's rule, unchanged and widened.
2. **One rule for a note wherever it sits.** A note on a line of a transcript and a note on an event have the same length, the same writer and date, the same look (a muted line in italics under the thing it rests on), the same audit row, the same place in Search, and the same list on the case page. What a person learned on the Chronology holds on the transcript.
3. **A note stays inside the office unless a person chooses otherwise.** The exports a person makes today are unchanged; the exports that carry notes are separate choices, plainly named; a Clip never carries a note. A note is work product, and the app never lets it out by default.
4. **Written where it belongs, found from one place.** A note is written and changed on the line or the event it rests on, where its context is; the Notes tab lists every note in the case and opens each where it was written; Search finds them.
5. **Nothing is lost by processing again.** A note follows the words it was written under when a transcript is made again.

### Words

**Note** (the glossary's entry widened): a person's own line under an Event or under a line of a Transcript, up to 2,000 characters, with who wrote it and when it last changed. The line or event it rests on is **its line** or **its event**; the moment it points at is that line's start or that event's time. **The Notes tab**: the case page's list of every note in the case. **On lines** and **on events** name the two places a note sits. The Clip's own note (Phase 1) and a Recording's note (Phase 2, its description) are other things and keep their names; a page never calls a Note a comment, an annotation, a remark, a flag or a bookmark.

### A note on a line

- **Where.** On the recording page, every line of the transcript gains **note** beside **edit** and **clip start** in the row's controls, shown as those are. Pressing it opens a small box under the line's words, "A note on this line", plain text up to 2,000 characters, with **Save** and **Cancel**; with a row lit, **N** opens it as **E** opens Correct. Escape cancels. The box is the page's, under the line; a layer is the incident page's shape and is not needed here.
- **How it shows.** A line with a note shows it under its words, whole and wrapping: the muted colour, italics, and before the words the writer's shown name and the date ("Note, D. Meehan, 19 Sep 2026: check the body-worn footage at this point"). Pressing the note opens the box with the words in it. Saving with the box emptied removes the note, after asking. The lines' Follow, the lit line, and everything else the transcript does are unchanged; a note only makes its row taller.
- **Who.** Whoever may correct the transcript may write, change or remove a note on it: the recording's owner, and everyone a Case is shared with, since nothing inside a shared Case is private to one person. The writer is whoever last wrote the note, and the date is when it last changed, as an Event's note has it; a note cleared has no writer.
- **One per line**, on the shown line. The second Side's copy of a line (the copy the transcript hides) is never noted. A corrected line keeps its note; a note is about the moment, not the words as first heard. A recording moved into a case, or out of it, keeps its notes.
- **On the timeline**, a small mark at each noted line's time, in the muted colour, under whatever the timeline already draws there; pressing it goes to the line. (Chapter 11: hovering it shows the Event card with the note, and a press opens the card too.)
- **In the transcript's window** (Open in a window) the notes show as they do on the page; they are written on the page.
- **Processing again.** When a recording is processed again and its Transcript replaced, each note is carried to the new line that spans its moment (the line whose start is at or before the moment and whose end is after it; failing that, the line with the nearest start), with its writer and date, and the audit says so. A note is never dropped by processing again.
- **Where it goes.** With the Segment, as everything about a line does: deleted with the recording, restored with it from the Recycle bin, never copied into a Clip.
- **The incident page's wall** is unchanged: the line under a camera shows the words, not the note. A note that should sit on the Chronology is put on an event, added from that line as Phase 6 chapter 2 has it. (Amended by chapter 11: a note on a synced camera's line is on the Chronology by itself, as an event.)

### Where the notes print

- **Two more entries in the recording page's Export menu**, shown only while the transcript has at least one note: **Export to Word, with notes** and **Export as text, with notes**. The three entries of today (Export to Word, Export as text, Captions) are unchanged, so a transcript a person makes for anyone outside the office never carries a note unless they chose the entry that says so. Captions never carry notes.
- **In Word, with notes:** each note under its line, in italics, "Note (D. Meehan, 19 Sep 2026): ..."; on the cover, under the facts, "With the office's notes: 4"; the running head gains "with notes"; the processing record counts the notes. **In text, with notes:** the note on the line after its line, indented four spaces, "Note (D. Meehan, 19 Sep 2026): ...", and the head's notice says the file carries the office's notes.
- **A Clip's excerpt, its caption file and its burned captions never carry a note.** Download all transcripts and the case's Everything export are as today, without notes.
- **Download notes**, on the Notes tab: a Word document for the office's own reading, the case's name, the count and the date on its cover, then one table of every note in the case, newest first: when (the recording's title and the time, or the incident's name and the time of day), the words it rests on (the line, or the event's line), the writer and the date, and the note.

### The Notes tab

- **Where.** On the case page, between Clips and Speakers (Recordings, Search, Clips, Notes, Speakers, Incidents), with the count of every note in the case, on lines and on events, drawn as chapter 1 draws every tab. It is always there; with no notes it reads "None yet" and one line says where a note is written (a line of a transcript, an event on a chronology).
- **The rows**, newest first by when the note last changed, each the note's words whole, with a muted line under them: for a note on a line, the recording's title and the time as a citation that opens the viewer at that line with the note lit, the line's words shortened, and, when the recording is a synced camera of an incident, **all cameras** as Phase 6 chapter 1's link; for a note on an event, the incident's name and the time of day as a citation that opens the incident page at that moment, and "on the event: <its line>"; then the writer and the date. A press on the words opens the note where it was written, with the box ready; nothing is edited on the tab.
- **Two pills** at the head when both kinds exist, **On lines** and **On events**, each with its count, filtering the list; **Search notes** opens the Search tab with the Notes kind chosen; **Download notes** as above.
- **How many.** Every note, no paging; a case with more than two hundred notes shows two hundred and "and N more; Download notes has them all".

### Told to Gideon

- **The case page's Gideon** reads them. After each recording's lines, a block "The office's notes on this recording:" with one line per note, "[hh:mm:ss] <writer>: <note>", in time order; a recording read from its Digest alone (Phase 7 chapter 5's ceiling) has the block after the Digest. The case chat's rules gain the sentence the incident rules have: the office's notes are its own words, to be respected and never contradicted or rewritten, and the assistant never writes one. A note's moment is cited as a line's is, and the citation plays it.
- **The incident's Gideon** reads the notes on the synced cameras' lines, placed on the incident clock, listed after the chronology's events as "The office's notes on the cameras' lines:", each "[hh:mm:ss] <camera> <writer>: <note>", under the same rule. The events' notes are read as Phase 7 chapter 5 has them. (Amended by chapter 11: the lines' notes are events on the Chronology and are read as such; the separate block is gone.)
- **Not read.** The Summary and the Digest are the words as spoken and seen, made when the video is prepared, and do not read notes; the Incident memo's spine is the Chronology, and it reads the events' notes as today and not the lines'; Propose events, the Speaker check and every other call are unchanged and read no note.

### Search and Find

- **The Notes kind** (Phase 7 chapter 3) reads the notes on lines as it reads the notes on events, and its count counts both. A hit on a line's note sits under the recording's group: the time as a citation that opens the viewer at that line, "Note, <writer>", the line's words, and the note under them in italics with the words marked; **all cameras** beside the time when the recording is a synced camera.
- **Find** on the incident page reads the notes on the synced cameras' lines with the cameras' words: a hit says "Note, <writer>" as the Notes hit does, and opens the moment.
- **The dashboard line** gains nothing; a note has no state.

### In and out

- **In**: the note on a line, its box, its look and its controls; the mark on the timeline; the carry on processing again; the two with-notes exports and Download notes; the Notes tab with its rows, pills and count; Gideon's reading on the case page and the incident page; the Notes kind and Find reading lines' notes; the audit rows.
- **Out**: any change to the Chronology's notes beyond the shared rule; notes in the plain exports, in captions or in Clips; a note the assistant writes; replies, threads, mentions and notifications; a note as a proposed event; a setting.

### What changes from earlier phases

- **Phase 1, the recording page and the exports**: the row's controls gain note; the box under the line; the mark on the timeline; the Export menu's two with-notes entries; the Word and text exports with notes; Process again carries notes.
- **Phase 2, the case page**: the Notes tab.
- **Phase 7 chapter 1**: the glossary's Note is widened to a line of a transcript; the rules for an event's note are unchanged. **Chapter 3**: the Notes kind and Find read lines' notes. **Chapter 5**: Gideon on the case page and on the incident page reads them.
- **Phase 8 chapter 1**: the case page's bar of sections gains Notes, with the same shape and a count.
- The Summary, the Digest, the memo, the proposals, the Chronology's exports and every setting are unchanged.

### Audit rows

Category Edits, as **Segment corrected** is written: **Note added**, **Note changed**, **Note removed**, with the segment's times as the label and never a word of the note; **Note carried** when Process again moves a note to a new line, with the old and the new times. Category Exports: **Exported** gains `notes` when a with-notes entry is used, and Download notes is an export of the case with `kind` notes. An event's note stays under **Event changed** (Phase 7 chapter 1). No row anywhere holds a word of a note.

### Settings

None. A note needs nothing switched on beyond the recording page; the Notes tab needs Folder management, as the case page does.

### Not in this chapter

- **A Clip's own note**, a Recording's note and a Person's notes: other fields, unchanged.
- **A note as a proposed event**: a person adds the event from the line, as today. (Reversed by chapter 11, 2026-09-24: a note on a synced camera's line is an event, not a proposal.)
- **Notes on a Document**: chapter 4.
- **Replies, threads, mentions and notifications**: ruled out; a note is one line, and the office reads them together on the Notes tab.
- **A note visible to one person only**: ruled out; nothing inside a shared Case is private to one person.

### Left to the build

- The mark on the timeline and whether hovering it shows the note's first words. (Settled by chapter 11: the Event card.)
- The key for the box (N) and where the focus lands when it closes.
- How the Notes tab shortens a long line, and how a note of many lines is shown in its row.
- The carry rule's edge: a note whose moment no new line spans takes the nearest start; the build says so in its notes.
- The date's form beside the writer, within the app's date rules.
- Whether the with-notes entries stand in the Export menu or under one "with notes" tick; two entries are the picture here.

## 3. Report a problem

Written 2026-09-19 from the maintainer's list of the same day ("bug report button") and the shape outlined beside chapter 1. Today a person who hits a problem tells IT in the corridor or by the office's own mail, and what they were doing, on which page, in which release, is lost by the time IT looks. This chapter gives every page one small way to say what went wrong, or what would help, that lands where the Admins already look and reaches the IT mailbox the app already writes to. Nothing leaves the building; the app never phones home.

### Principles

1. **One link, every page, the same words.** "Report a problem" sits in the same place on every page a signed-in person sees, and opens the same small box. A person never hunts for it.
2. **Say what happened, in your own words.** The box asks for what happened and what was expected, and nothing else is required. The app adds where the person was (the page, the Release, the browser) only with their tick, and shows what it will add before it goes.
3. **It lands where Admins look.** A Report is kept in the app, on a Reports page of the Panel with New, Seen and Done marks, and the Panel's rail and the Status page say how many are new. Mail to the Operator address is the second copy, when mail is configured; the Panel is the record.
4. **Never a transcript's words.** The app adds nothing that could carry the words of a recording: the page's address without its query, the Release, the browser's name and version, the window's size, the person's name. The guide asks the person to describe the problem and not to paste the words. No screenshot.
5. **A report is not a ticket.** The app keeps it, shows it and marks it; the conversation about it, if one is needed, happens the way the office talks. Replies, assignment and threads are not built.

### Words

**Report**: a person's own account, sent from a page of the app, of a problem they hit or a thing that would help, kept for the Admins with where the person was. **A problem** and **An idea** are its two kinds. **The Reports page**: the Panel's list of Reports. **New**, **Seen** and **Done** are its marks. The pages never say bug, ticket, issue (that is GitHub's word for other offices' reports, CLAUDE.md), feedback or complaint.

### The link and the box

- **Where.** **Report a problem**, a small link at the right of every page's foot, on every page a signed-in person sees, the Panel's pages included; not on the sign-in page. The incident page, which fills the window and has no foot, carries it in its work panel's head beside Find's magnifier. Hidden while the Reports setting is Off.
- **The box.** The app's own dialog (never the browser's), headed "Report a problem", with:
  - **What is it?** Two choices, **A problem** (chosen) and **An idea**.
  - **What happened** (for an idea: **What would help**): a box for plain words, required, up to 4,000 characters.
  - **What you expected**: a box, optional, the same length; absent for an idea.
  - **Include where I was**: a tick, on, and under it the line the app will add, drawn before sending: "This page (/case/…/incident/…), Release v1.69.0, Chrome 129 on Windows, a window of 1920 by 1080, sent by Daniel Meehan." The page's address is its path alone, never its query (a search term lives there and is never logged; a moment's `?t=` goes with it, which loses nothing). Unticked, the report carries the person's name and the Release only, so an Admin can still ask.
  - **Send** and **Cancel**. Esc cancels. A box that has been typed in asks before closing, as the correction box does.
- **After Send** the app says "Thank you. Your report went to the Admins." in its toast, and the page is as it was. A person has no list of their own reports (below, Not in this chapter).
- **What the app adds** and how: the Release from the environment's `RELEASE_TAG` ("not tagged" when empty); the browser's name and version worked out by the build from the User-Agent header, short ("Chrome 129 on Windows", "Edge 128 on Windows", "Firefox 130 on Windows", else "a browser"); the window's size from the page; the person's shown name. Nothing from the page's contents.

### Where it lands

- **The Report** is kept: its kind, the words of both boxes, the where line's parts (page, release, browser, window), who sent it and when, its mark (New, Seen, Done) with who set the mark and when. It belongs to nobody's Case and is not deleted with anything; a Report of a person who leaves stays, named for them.
- **The Reports page** in the Panel, beside Status in its group, listed on the rail with the count of New reports as a badge in the warning tone, as the Vision page carries its requests. Newest first, New before Seen before Done; a filter of pills at the head (**New**, **Seen**, **Done**, **All**, each with its count). Each row: the kind as a pill, the first line of what happened, who and when, the where line, then the whole words folded open on a press; **Seen** on a New report, **Done** on a New or Seen one, each one press with no question; a Done report shows who marked it and when. Nothing on the page edits the person's words.
- **The Status page** gains one line, "2 reports not yet seen", a link to the Reports page, shown only when the count is not zero.
- **The mail.** When mail is configured and the Operator address is set (the rules of the Email chapter for the app's own mail: `SMTP_HOST`, `MAIL_FROM` and `OPERATOR_EMAIL`, unaffected by the Email notifications switch), each Report goes as one message to the Operator address, kind `report`: subject "Report from <name>: <the first words>" (or "Idea from <name>: …"), body the kind, what happened, what was expected, the where line, and "Seen and marked on the Panel's Reports page at <the page's address>". The mail is the second copy: a report is kept and shown whether or not the mail goes, and a mail that fails is the Email page's business as every mail is. Nothing goes to the person.
- **Sweeping.** A Done report is kept ninety days from its Done mark and then removed by the daily sweeper, with one System row saying how many went. New and Seen reports are kept until they are Done.

### In and out

- **In**: the link and its place on every page; the dialog with its kinds, boxes and tick; the where line and how it is made; the Report kept; the Reports page with its marks, filter and rail badge; the Status line; the Operator mail; the sweep; the setting; the audit rows.
- **Out**: a screenshot or any capture of the page; a person's own list of reports; replies, assignment, threads, priorities; mail to the person; any report leaving the building; reports on the sign-in page.

### What changes from earlier phases

- **Phase 1, every page**: the foot gains the link (the incident page its head). **The Panel**: the Reports page; the Status page's line; the rail's badge. **The daily sweeper**: the sweep of Done reports.
- **Phase 2, the Email chapter**: one more kind of the app's own mail, `report`, to the Operator address, under the rules the backup reports follow.
- **The settings catalogue**: Reports on the Features page.
- The exports, the glossary's other words, Gideon and Search are unchanged; a Report is not searched.

### Audit rows

Category System: **Report made** (who, the kind, the page's path, the release; never the words), **Report seen** and **Report done** (which report, by whom), **Reports swept** (how many). The words of a report are the report's own and are read on the Reports page by Admins, never in the audit log.

### Settings

| Setting | Page | Default | What it does | When changed |
|---|---|---|---|---|
| Reports | Features | On | People may send a Report from any page. | Off hides the link on every page and refuses the endpoint; the Reports page and its reports stay for the Admins. At once. |

### Not in this chapter

- **A person's own reports** and an answer in the app: a Report is one message to the Admins; the office answers the way it talks. Deferred, to be asked for.
- **A screenshot**: ruled out; it could carry a transcript's words out of the page.
- **Reports to GitHub**: ruled out; the repository's Issues are other offices', and nothing leaves the building.
- **A count of open reports for people**: nothing is shown to people beyond the toast.

### Left to the build

- The dialog's layout and the toast's words, within those above.
- How the browser's name is worked out from the User-Agent header, and the words when it is not one of the three.
- Whether the rail's badge counts New alone (it does here) or New and Seen.
- The Reports page's paging past two hundred.
- The sweeper's hour, with the other daily sweeps.

## 4. Documents beside the cameras

Written 2026-09-19 from the maintainer's list of the same day ("PDFs in a case") and the discussion of the same day that fixed its purpose: the police report that corresponds to the body-worn cameras, put beside what the cameras recorded, so that a reader sees where the report and the record agree, where they differ, and where the report says something no camera shows. Reading a PDF is the plumbing under that; the comparison is the feature. Three parts, built in order as three releases: the documents and their pages (part 1), the Report tab and Gideon's citations (part 2), the comparison (part 3).

### Principles

1. **A document is read whole, as a transcript is.** The app hands the engine numbered paragraphs, checks every citation against what it handed over, and reads in windows and in parts when the whole will not fit. No retrieval store, no embeddings, nothing outside the building; the one rule for paperwork that outgrows the reading (below) uses the database's own text search and says so under the answer.
2. **A document belongs to what it is about.** A PDF is added from the incident page or the recording page as the report for that incident or that camera, never loose in a case. One report linked to an incident is read once against every camera. The case's Documents tab lists them; it is not where they arrive.
3. **The page is the truth; the words are a reading.** Every page is drawn to a picture at upload and shown beside the words the app read from it. A scan is read by OCR and marked so; a page the OCR read poorly says so; a citation always opens the real page with the paragraph lit.
4. **Both sides of every finding are cited.** A comparison's row carries the report's paragraph and the record's moment, each a citation that opens; a finding with a side missing is refused by the app. The camera's description is a description, the officer's sentence is the officer's, and the app never states one as the other or draws a legal conclusion. A person marks each finding; the app proposes.
5. **Limits are settings and are said aloud.** The page ceiling, the documents per incident, the reading ceiling and OCR are on the Panel with On and Off; the upload page says what fits before a file is chosen; the answer says what was left out.
6. **Nothing new to install.** The PDF reader, the page renderer and the OCR engine are packages in the app image, pinned, running on the media queue's worker on the CPU. No container, port, service, token, GPU or language pack beyond English. An office that never uploads a PDF sees a tab and nothing more.

### Words

**Document**: a PDF added to an Incident or a Recording as the report about it, kept in the Case, read page by page. **Page**: one page of a Document, drawn as a picture and read as words. **Paragraph**: one numbered block of a Page's words ("page 4, paragraph 2"), the unit the assistant cites and Search hits. **Read by OCR**: the words of a Page that had none of its own, read from the picture. **The Report tab**: the tab on the incident page's work panel and the recording page's work area that shows the Documents linked there. **Comparison**: the assistant's reading of a Document against the incident record and the Chronology (or one Recording's Transcript and Digest), one **Finding** per row, each marked **Agrees**, **Differs**, **Not on camera** or **Not in the report**. The pages never say attachment, exhibit, file (that is a Recording's), chunk, embedding, index or RAG.

### Part 1. The documents and their pages

- **Where they arrive.** **Add the report** on the incident page's Details tab and on the recording page's Details tab, and nowhere else. It opens the app's upload page for documents, headed for that incident or that camera, which says before a file is chosen:
  - PDFs only; a Word file is saved as a PDF first.
  - The report for this incident (or this camera), nothing else: a document is read beside the cameras, so a document about something else only slows the reading and clouds the answers.
  - Up to N pages (the Admin's figure); a larger file is refused, and a production should be cut down to the report that matters.
  - A scan is read by OCR, and its words may carry mistakes; the page itself is always shown beside them.
  - Nothing leaves the building; the document is read by the office's own engine and kept with the case.
  Then the file, a title (the file's name, editable), and **Add**. The document goes on the media queue as a video does, and its row on the tab says "Reading 42 pages" until it is done.
- **What the app does at upload**, on the media queue's worker: reads each page's words with their positions (a text PDF); when a page has fewer than a few words of its own, reads its picture by OCR (Tesseract, English) and marks the page **read by OCR**; a page whose OCR yields too little says **poorly read**; splits each page into Paragraphs by the gaps on the page, numbered from 1 on each page; draws each page to a picture at reading size. All of it is kept with the Document under the Case's folder and goes with the Case. A PDF over the page ceiling, not a PDF, or unreadable is refused with the reason, the way an oversized video is.
- **The Documents tab** on the case page, drawn as every tab (chapter 1), with the count: every Document in the case, newest first, each with its title, its pages ("42 pages, read by OCR, 3 poorly read"), what it is linked to (the incident's name or the recording's title, a link), who added it and when, and **Open**, **Re-link** (to another incident or recording of the case) and **Remove** (asks first). Nothing is added here.
- **The document page.** A Document opens on a page of its own inside the case: the page pictures down the middle at reading size, the words read from the open page beside them paragraph by paragraph with their numbers, a page number box, Find within the document, and **Download** of the PDF as it was. A page read by OCR says so above its words; a poorly read page says so in the warning tone. A citation arriving with `?page=4&para=2` opens that page with the paragraph lit on the picture (from the words' positions) and in the words.
- **Search** (Phase 7 chapter 3) gains the kind **Documents**: one hit per Paragraph, the document's title as the group's head, "page 4, paragraph 2" as the citation that opens the page with the paragraph lit, the words marked.
- **Deletion and retention.** A Document is part of its Case: recycled and restored with it, deleted with it, counted in the case's size; removing it removes its pages and words. Never in a Clip, never in an export of a transcript.

### Part 2. The Report tab and Gideon

- **The Report tab** appears on the incident page's work panel (after Cameras) and on the recording page's work area (after Clips) only when a Document is linked there, drawn as every tab, with the count of documents. It lists the linked documents with their state and opens each in the panel: the page pictures with the words beside them, at the panel's width, the same page as the document page shows; Add the report and Re-link stay on Details.
- **Gideon reads linked documents.** The incident's Gideon reads the documents linked to the incident after the chronology and before the question, as "The report(s) for this incident:", each document as numbered paragraphs "[Report, page 4, paragraph 2] the words". The recording page's Gideon reads the documents linked to that recording after the transcript in the same way. The case page's Gideon reads every document in the case, each under the recording or incident it is linked to. The rules gain: the report is the officer's account and the cameras are the record; say which says what; a description of the picture stays a description; where they differ say so plainly and cite both; never a legal conclusion.
- **Citations.** "[Report, page 4, paragraph 2]" (the document's short title when there are several), checked against the paragraphs given, as a time is checked against a transcript. Under the answer the preview shows the paragraph's words with the paragraph before and after in the muted colour, the document's title and page, "read by OCR" when it was; **Open** goes to the document page with the paragraph lit. The same look as the moment preview.
- **The reading ceiling.** A question reads at most N paragraphs of documents (a setting). When the linked documents fit, they are read whole. When they do not, the app reads only the paragraphs whose words match the question, found by the database's own text search over the Paragraphs, and says under the answer "Read 40 of 310 paragraphs of the report, those matching the question." Never silent. The memo and Propose events do not read documents; the memo reads the paragraph an event rests on (part 3).
- **The exports.** A case chat's Word export lists the documents read on its cover as it lists the recordings; a citation prints as the title and page.

### Part 3. The comparison

- **Compare with the report**, a button on the Report tab, on the incident page (the report against the incident record and the Chronology) and on the recording page (the report against that recording's Transcript and Digest). It says what it will read and about how long, as Propose events does, and runs on the llm queue.
- **How it reads.** One document at a time, in windows of pages (about eight pages a window) against the whole record, so no call is large and no answer is cut short; the findings are gathered across the windows and the documents. Each window is asked for findings in a fixed shape: the paragraph, the claim in a few words, the moment or moments on the record it rests on, and the mark. A finding with no paragraph or, for Agrees and Differs, no moment is dropped by the app.
- **The four marks.** **Agrees**: the record shows what the paragraph says, at the cited moment. **Differs**: the record shows otherwise, at the cited moment. **Not on camera**: the paragraph describes something no camera shows or says (a claim, an observation, an act off camera). **Not in the report**: an Event of the Chronology, or a moment the record makes plain, that the report does not mention. The rules: cite both sides; a description of the picture is a description; say what was said and what was seen, never what it means in law; where the OCR's words are doubtful, say so.
- **The Comparison layer.** The findings land as a layer over the Report tab, one shape with every layer (chapter 1): the head "Comparison, <document>", the state line ("42 pages against 6 cameras; 31 findings: 12 agree, 6 differ, 9 not on camera, 4 not in the report"), a filter of the four marks as pills, then one row per finding: the mark as a pill, the paragraph's words (page and paragraph as a citation that opens the document page), the claim, the moment as a citation that plays every camera (or the recording), and the assistant's one line of why. On each row **Make it an event** (the incident page; below), **Note** (a note on the finding, the office's own), and **Dismiss**; **Accept all agreed** is not offered; a person reads the rows. The comparison is kept on the incident (or the recording), one per document, replaced by Compare again, marked stale when the Chronology or the cameras change, as the memo is.
- **Findings become events.** **Make it an event** adds an Event at the moment with the claim as its line, source **report**, resting on the paragraph (shown under the event as a line rests on a camera), the mark carried as the event's why; a Not on camera finding asks for the moment, since the report has no clock. The memo then reads that paragraph as part of the chronology it is written from, and its rules gain the sentence that the report is the officer's account. Propose events is unchanged.
- **The exports.** **Comparison to Word**: the cover with the document, the cameras and the counts, then one table with the mark, the paragraph (page, number, words), the claim, the moment and the why, and the office's notes; the Chronology's exports show a report paragraph under an event that rests on one, and the spreadsheet gains a Rests on column. The comparison is never in a transcript's export or a Clip.

### The settings

On a Documents page of the Panel, with Reset to default on every figure:

| Setting | Default | What it does | When changed |
|---|---|---|---|
| Documents | On | People may add a PDF to an incident or a recording. | Off hides the Documents tab, Add the report and the Report tab; documents already there stay and are read by nothing. At once. |
| Largest document | 60 pages | A PDF over it is refused at upload with the reason. | The next upload. |
| Documents per incident or recording | 3 | Add the report is greyed with the reason at the count. | The next upload. |
| Read scans with OCR | On | A page without words of its own is read from its picture. Greyed "OCR not installed" when the image lacks it. | The next upload; Off keeps and shows a scan and says its words were not read. |
| Reading ceiling | 400 paragraphs | The most paragraphs of documents a question reads whole; past it, the paragraphs matching the question. | The next question. |
| Compare with the report | On | The comparison button. Needs the assistant. | Off hides the button; comparisons already made stay. |
| Comparison answer cap; Comparison time limit | 3,000 tokens; 600 seconds | The call's figures, as the memo's are. | The next comparison. |

### In and out

- **In**: PDFs added from an incident or a recording; pages read, OCR'd, split and drawn; the Documents tab and the document page; the Documents kind in Search; the Report tab; Gideon reading linked documents with paragraph citations and the preview; the reading ceiling and the matching rule; the comparison with its four marks, its layer, Make it an event, its export; the settings; the audit rows.
- **Out**: any format but PDF; a document loose in a case; embeddings, a vector store, a retrieval service; OCR in any language but English; the memo or Propose events reading a document whole; a comparison accepted in bulk; a document in a Clip or a transcript export; anything leaving the building.

### What changes from earlier phases

- **Phase 2, the case page**: the Documents tab; the case's size counts documents; recycle, restore and delete carry them.
- **Phase 4, the assistant**: a new feature, comparison, with its template on the Templates page and its budgets.
- **Phase 6, the incident page**: the Report tab; Details gains Add the report; an Event's source gains report and Rests on a paragraph; the memo reads a rested-on paragraph. **The recording page** (Phase 1): the Report tab; Details gains Add the report.
- **Phase 7 chapter 3**: the Documents kind. **Chapter 5**: Gideon's reading and the paragraph preview.
- **The upload rules** (Phase 1): a second upload page, for documents, with its own statements and ceilings.

### Audit rows

Category Cases: **Document added** (the title, pages, read by OCR, poorly read, linked to), **Document re-linked**, **Document removed**; **Comparison run** (the document, the windows, the findings by mark, never the words); **Event added** with source report. Category LLM: **AI assistant call** with feature comparison, as every call. No row holds a paragraph's words.

### Not in this chapter

- **Other formats** (Word, images, e-mail): saved as PDF first.
- **A document for the whole case** with no incident or recording: ruled out; the reading stays small and the purpose plain.
- **Embeddings and a vector store**: not needed at this scale; the matching rule is the step before them, and they would need a model inside the building.
- **OCR in other languages**: later, if asked.
- **The comparison in the memo**: the memo reads only the paragraphs events rest on.

### Left to the build

- The PDF and OCR packages and their pins, recorded in `docs/research/documents.md` with what was measured on a real text report and a real scan; the paragraph splitter's rule and the "poorly read" threshold.
- The page picture's size and the panel's page view.
- The window of pages for the comparison (about eight) and the finding's JSON shape.
- How the matching rule ranks paragraphs (PostgreSQL full-text search, the question's words, the top N).
- The short title for a document in a citation when several are linked.

## 5. The desk, kept

Written 2026-09-22 from the maintainer's word on the incident page after v1.73.0: the page as it stands is the right page, and three mock-ups that moved its parts were set aside. Four things are to change on it, and one more was added the same day. The video should feel like a video; making a clip should be obvious; the dead space under the pictures, when one camera is the focus, should show what is being said; the work panel should be draggable wider and narrower; and the place on the strip that takes a drag should say so. The drawings are `docs/spec/mockups/phase-8-incident-desk.html` (the desk with the four changes, making a clip, the clip track close up, the panel dragged wider), picked the same day.

### Principles

1. **Nothing moves.** The head, the wall, the transport, the strip and the work panel stay where Phase 6 chapter 4 and Phase 8 chapter 1 put them. This chapter adds to the page and changes how three of its parts behave; it takes nothing away that a person has learnt.
2. **The focus camera is a video.** When one camera is the focus it behaves the way every video on every screen behaves: the picture at its own proportions, and the controls a person expects on the picture when the pointer is over it. The transport row under the wall stays for the people who use it.
3. **The words follow the picture.** The space under the filmstrip shows the focus camera's transcript following the clock, the line being said lit. Change the focus and the words change with it. A person reads and watches in one place.
4. **Clip is a thing you can see.** A button on the transport, a track on the strip that says what it is for in words, a lane that shows the clips already made, and a line under the picture that offers to start one. Every way in ends in the same clip box, filled in.
5. **The panel is the person's to size.** A handle between the wall and the panel; the width is remembered for that person; the wall gives way and is never squeezed to nothing.
6. **Withheld is greyed and says why.** Where the office's Clips setting is off, the button, the track and the lane stay on the page greyed, with the reason, as chapter 1's rule for a withheld control has it.

### Words

Added to `CONTEXT.md` with this chapter. **Player bar**: the controls drawn on the focus camera's picture when the pointer is over it (a scrub bar, play, back and forward, the time, which camera is heard, the speed, fill the window). **Said band**: the block under the filmstrip that shows the focus camera's words following the clock. **Clip button**: the Clip on the transport that starts a clip at this moment and ends it on the second press. **Clip track**: the hatched band under the strip's ruler that takes a drag to make a clip. **Clips lane**: the strip's lane of the clips already made from this incident. **Handle**: the grip between the wall and the work panel that a person drags to size the panel. The pages never say scrubber, seek bar, live captions, subtitles, in point, out point, marker, splitter or gutter.

### The focus camera as a player

- **The picture at its own proportions.** In the Focus layout the focus camera's well takes the picture's own proportion once the browser knows it (a body-worn camera held upright is upright; a dash camera is wide), instead of a 16:9 well with bars. The well's height is capped so the filmstrip, the said band and the transport stay in view on a 1080-pixel-tall window; past the cap the picture is fitted inside with bars. Filmstrip tiles, Side by side and Grid keep the 16:9 well, since a row of tiles has to be a row.
- **The player bar.** When the pointer is over the focus picture, and while the focus camera is paused, a bar sits on the picture's lower edge over a soft dark fade: a scrub bar across the width; play or pause; back five seconds and forward five; the elapsed time and the incident's length ("1:45 / 41:26"); the speaker, lit when this is the camera heard, a press hearing it (or, when it is heard, pinning it, as the tile's speaker does today); the speed, a small menu of the transport's speeds; and **Fill the window**, which shows the focus picture and the bar alone until Escape or the same button. The bar fades out two seconds after the pointer leaves or stops moving while playing. Nothing on the bar is new: each control does what the transport's control of the same name does, and the keys (space, the arrows, B, E) are unchanged.
- **The scrub bar** is the incident's span, as the strip is, not the focus camera's file: the played part is drawn to the clock, the focus camera's own stretch is a lighter band inside it, and a press or a drag on it seeks every camera, as a press on a strip lane does. The events are ticks on it; hovering a tick shows the Event card with the event's line (chapter 11). While a clip is being marked (below), the span so far is drawn on it in the clip's colour.
- **The tile head** (the dot, the id, the pill, the speaker, Sync, the menu) stays as it is on the focus tile and on every tile. The line under the focus tile that today carries the words and the camera line keeps the camera line only; the words move to the said band.
- **Not the focus.** A filmstrip tile, and every tile in Side by side and Grid, has no player bar; a press on its picture makes it the focus (filmstrip) or plays and pauses (the other layouts), as today.

### The said band

- **Where.** In the Focus layout only, under the filmstrip and above the transport, across the stage's width, in the space that was empty: a block headed "Said on DC-12, following the clock" with, at its right, "Press a line to go there" and **Open the transcript** (the recording page's Transcript tab, at this moment).
- **What it shows.** The focus camera's transcript lines around the clock: the line being said lit as the recording page lights its line, two lines before it and one after, each with its start on the incident clock, the speaker's name (a numbered label shows as no name, as the line under a tile does today) in the speaker's colour, and the words. The band scrolls as the clock runs so the lit line stays in place. When nothing is being said, the last line stays with its light off. When the focus camera has no transcript, the band says "DC-12 has no transcript yet" and, when a person may, "Transcribe it" as the Cameras tab offers. When the focus camera has not started or has ended at the moment, the band says so in the tile's words ("Starts in 0:41"; "Ended at 22:31:07").
- **What it does.** A press on a line seeks every camera to that line's start, exactly as a press on the strip. When the pointer is over the lit line, two things appear at its right: **+ event**, which is the line under a tile's + event (the words as the event's text, the moment, this camera as its source), and **Clip from here**, which starts a clip at the line's start as the Clip button does (below). The band never opens a layer of its own.
- **Follow.** The band follows the clock while Follow is ticked, as the strip does; with Follow off a person may scroll the band by hand, and it snaps back to the clock on the next press of Play.
- **Which cameras.** The focus camera only. Every camera's words interleaved was considered and set aside: two officers' cameras hear the same words, and one band that says each line twice with a camera's name on it is harder to read than one camera's words with the camera's name in the head. Find, across every synced camera, is the way to look for words the focus camera did not hear.
- **How the words arrive.** From the camera's lines endpoint the tile already reads, once per camera, so the band costs no new request; the band is drawn from what the tile has.

### Clip, four ways in and one box

- **The Clip button.** On the transport, after the time and before the speed, "Clip" with the scissors, drawn in the accent, with "starts a clip at this moment" in small type beside it. A press marks the start at the clock and the button becomes **End the clip here**, drawn in the clip's colour, with "Clip from 21:57:27, 0:14 so far · Esc cancels" beside it; the span so far is drawn on the scrub bar, on the strip's clip track and as a ghost on the Clips lane, growing with the clock. The video keeps playing the whole time. The second press sets the end and opens the clip box (below). Escape while marking cancels and clears the drawing; so does leaving the page, with nothing kept. Seeking while marking is allowed and moves the end, not the start; seeking before the start swaps them.
- **The clip track.** On the strip, under the ruler and above the lanes, a band of the strip's width (the lane heads' width left clear) that says what it is: hatched in the clip's colour with a dashed edge, the scissors and "Drag across here to make a clip" at its left, and "or press Clip on the transport, or Clip this event on a row" in muted type at its right. The pointer over it is a crosshair, the edge turns solid with a soft glow, and a faint line follows the pointer down through the lanes so the time under it is plain. Dragging across it draws the span so far in the clip's colour on the track and as a ghost on the Clips lane, with a tag that follows the pointer ("22:04:10 to 22:07:48 · 3:38"), and the track's words change to "Dragging: release to set the end". Release opens the clip box with that span. A drag of under a second is a press and seeks there. Escape while dragging cancels. The ruler above it keeps a press to seek and loses its drag, which the track now owns; the strip's foot line of instructions goes, since the track and the "?" say it.
- **The Clips lane.** A lane under Events, headed Clips, that draws every clip made from this incident (the incident's clips, whatever way they were made) as a block over its span in the clip's colour, with the clip's title on hover and a press opening the clip on the case's Clips tab. The lane is there only when the incident has a clip or one is being marked, so a strip with no clips is as tall as today.
- **Clip from here** on the said band's lit line, and **Clip this event** on a chronology row and on the event layer, stay and start the same marking: Clip from here marks the start at the line's start and turns the transport's button into End the clip here; Clip this event opens the box at once with ten seconds either side, as today.
- **The clip box** is the layer of Phase 7 chapter 1 and Phase 6 chapter 5, unchanged in what it holds, filled in by whichever way opened it: From and To; the cameras ticked from those running inside the span (an event's own cameras when opened from an event); the layout and the sound as today; the title from the event's line, or from the one event whose moment falls inside the span, or the two times. The head says which way in ("Clip from here", "Clip from the strip", "Clip this event", "Clip"), and the one main button is **Make the clip**, greyed with "set the end first" while a clip is still being marked and the box was opened early. Making it does what it does today: one file, rendered on the media worker, landing on the case's Clips tab, and now on the Clips lane too.
- **Withheld.** Where the office's Clips setting is off, the Clip button is greyed with "Clips are off for this office" on hover, the clip track is drawn without its hatching and says "Clips are off for this office" in muted type, the Clips lane is not drawn, and Clip from here does not appear; Clip this event stays greyed as today.

### The handle

- **Where.** Between the stage and the work panel, the full height of the two, a narrow strip with a short grip drawn at its middle; the pointer over it is the column-resize pointer and the grip lights. It is there whenever the panel is beside the wall (Focus and Side by side at 1280 pixels and wider); in a Grid layout and under 1280 pixels, where the panel sits under the strip, there is no handle.
- **Dragging.** The panel's width follows the pointer between 360 pixels and six tenths of the desk; the wall, the filmstrip, the said band, the transport and the strip give way in the stage's width as they do when the window is resized, and the focus picture keeps its proportions. The drag stops at the point where the stage would fall under 420 pixels, so the video is never a postage stamp. While dragging, a faint line shows where the split will land, and the width snaps gently at the usual 460 pixels and at half the desk. Releasing keeps it.
- **Remembered.** The width is kept in the person's browser as the recording page keeps its stage's width, for every incident that person opens; a double-press on the handle puts the usual 460 back. Nothing is kept on the server and nothing is per incident.
- **The keyboard.** The handle takes focus with Tab and moves twenty pixels a press on the left and right arrows, Home and End going to the two limits, as the recording page's handle does.
- **A narrow panel.** Under 400 pixels the tabbar shows each tab's icon alone with its name on hover, keeping the Report count and Find's box; the panel's rows and layers are already fluid. **Two panels** on a very wide window (chapter 1) keeps working: the handle then sizes the pair.

### Settings and audit

- No setting is added. The Clips setting on the Features page already governs clips; the player, the band, the track and the handle are the page's own.
- No audit row is added. Clip created stays the row for a clip across cameras, and gains its way in ("from the button", "from the strip", "from a line", "from an event") beside its cameras and layout.

### Left to the build

- The player bar's exact controls' drawing and fade timing, within the rule that it is what a person expects of a video and adds no control the transport lacks.
- The focus well's proportion cap, within the rule that the filmstrip, the band and the transport stay in view at 1080 pixels.
- The said band's height (about four lines) and how it snaps back after a hand scroll.
- The clip track's height, hatching and colours, within the rule that it reads as a place to drag before a hand is on it; and the Clips lane's block drawing.
- The handle's snap distances and how the tabbar decides to show icons alone.
- Whether a clip being marked survives a change of focus (it should; the span is the incident's, not a camera's).

### Not in this chapter, and ruled out

- **Moving the parts**: the three mock-ups of 2026-09-22 that slimmed the head, hid the once-only controls behind a Set up sheet, put the strip first, or added a Watch or Read switch were set aside by the maintainer; the page as it stands is kept.
- **Every camera's words in one band**: set aside for the focus camera's words alone (above); may come back as a tick on the band if staff ask.
- **A player bar on every tile**: ruled out; one video is a video, six are a wall.
- **The panel's width on the server**: ruled out; a person's browser remembers it, as the recording page's stage.
- **Dragging the strip's height**: not asked for; deferred.

## 6. The report in place

Written 2026-09-22 from the maintainer's first real comparison and the asks that came with it: a citation to the report takes the reader to the document's page and away from the cameras, the chronology or the comparison they were reading; the comparison's Word export was not found where it was looked for; and Gideon's panel cannot be made wider. The one design under all three: a person reading the record never leaves it to look at the report. The report comes to them, in a card, and the same card everywhere.

### Principles

1. **The report comes to the reader.** A citation to a paragraph, wherever it is, opens a card in place that shows the paragraph on its page, lit, with the words around it. The page under the reader does not change and nothing they were looking at moves. Opening the document's own page is one press further, for reading it whole.
2. **One card everywhere.** Gideon's answers, the comparison's rows, a chronology row that rests on a paragraph, the memo's citations, Search's hits and the Notes tab all open the same card with the same head, the same picture and the same way out. What a person learns once holds everywhere a paragraph is named.
3. **The page is the truth.** The card shows the real page picture with the paragraph's box drawn on it, as the document page does, never the words alone. A page read by OCR says so on the card.
4. **Exports are where exports are.** The comparison's Word export sits with the page's other exports as well as on the comparison itself, so a person who looks in the Export menu finds it.
5. **The panel is the person's to size.** Gideon's panel takes a handle as the incident page's work panel does, with the same limits, the same memory and the same keys.

### Words

Added to `CONTEXT.md` with this chapter. **Paragraph card**: the card that opens in place from a citation to a Paragraph, showing the Page's picture with the Paragraph lit, the words before and after, and the way to the document's page. The pages never say popup, popover, modal, tooltip, lightbox or preview (the chat's word for the moment player stays the chat's). The Gideon panel's grip is a **Handle**, as the work panel's is.

### The paragraph card

- **What opens it.** Every place a Paragraph is cited: a `[Name, page N, paragraph M]` pill in a Gideon answer (which today opens a preview of the words alone; that preview becomes the card); the "page N, para M" citation on a comparison row; the "From the report, page N, para M" line on a chronology row and on the event layer for an event that rests on a paragraph; a citation in the memo; a document hit on the case page's Search tab; and, on the Notes tab, a note whose line rests on a paragraph. A press opens the card; the page under it stays where it is.
- **What it shows.** A card of the work panel's width (or the chat panel's, or the tab's, wherever it opens), anchored under the citation: a head with the document's title and "page N, paragraph M", "read by OCR, so check the page" when the page was; the page's picture scrolled so the paragraph is in view with its box drawn on it in the accent, as the document page draws it; under the picture, the paragraph's words in the reading size with the paragraph before and after in muted type; and a row with **Open the document** (the document page at that page and paragraph, in the same tab), **Copy the citation** ("Incident report, page 4, paragraph 2") and **Close**. On the incident page a citation that also names a moment (a comparison row's other side) keeps its moment citation as it is; the card is for the paragraph.
- **How it behaves.** One card at a time: opening another closes the first. Escape closes it, as does a press outside it or on the citation again. It never covers the cameras or the strip on the incident page: it opens inside the work panel or the layer the citation is in, and scrolls with it. In Gideon's panel it opens under the answer, as the moment player does. It is drawn from the document's state endpoint and page pictures the app already serves, so it costs no new request beyond the picture.
- **The document page stays.** It is the place to read the report whole, and Open the document goes there with the paragraph lit, as today.

### The comparison's export

- **Where it is.** The comparison's Word export stays on the comparison (the "Comparison to Word" link beside Compare again) and is added to the incident page's **Export** menu as **Comparison to Word** while a comparison exists and is done, greyed with "Compare with the report first" until then; on a recording's page, to the page's Export menu the same way. The case page's Documents tab row for a report with a comparison carries the same link.
- **What it holds** is unchanged from chapter 4: the cover with the document, the cameras and the counts, then the table of findings with their marks, both citations, the why and the notes, dismissed rows left out.

### The Gideon panel's handle

- A handle on the panel's left edge, the full height, with a grip at its middle, drawn as the work panel's handle is. Drag it and the panel grows or shrinks between 360 pixels and six tenths of the window; the page under it does not reflow, as chapter 1 has it. The width is kept in the person's browser, for every page the panel opens on; a double-press puts the usual 420 back; with the handle focused the arrow keys move it twenty pixels, Home and End to the limits. In the panel's own window (the pop-out arrow) there is no handle.

### Settings and audit

- No setting is added. No audit row is added; opening a card is reading, and the export rows are chapter 4's.

### Left to the build

- The card's exact size and where the picture is cropped, within the rule that the paragraph is in view and its box drawn.
- Whether the card is one drawing shared by the pages (it should be: one script, as the report panel is).
- The handle's snap points, if any, and how the chat's width and the work panel's width are kept apart in the browser.

### Not in this chapter, and ruled out

- **Camera lines in clip captions** ("Camera:" cues from a described moment, under the Vision page's Exports switch): left alone at the maintainer's word on 2026-09-22; a split switch for captions alone is noted for later.
- **The card as a window of its own**: not chosen; the document page is the whole-report view.
- **Editing a document's words from the card**: ruled out; the page is the truth.

## 7. The pages that fail well

Written 2026-09-23 from the end-user walk of 2026-09-22 (the report "Transcribe walk findings", items V5, D2, V2 and C5). Four things the walk met that a fix release cannot take, because each needs a design rather than a line: the session ended under an open page and the page went on as if nothing had happened, then dropped the person on Sign in without a word; an address that no longer exists answers the framework's bare "Not Found" with no way back; the Admin's warning band takes a whole stripe of four pages for one sentence; and the case page wraps every file name onto three lines beside a pane of five facts. The one design under all four: a page that fails, or that has something to say beside its work, says it in place, in the app's own words, and leaves the person where they were.

### Principles

1. **The page says what happened, where the person is.** A session that ends under an open page is announced on that page, once, with the way back, and the page stops asking the server for anything. Nobody learns their session ended by landing on Sign in.
2. **Nothing is lost by the ending that the rules do not already lose.** With Folder management on, the cases, clips and documents stay and the line says so; with it off, the Workspace goes as Phase 1 fixes, and the line says that instead. Signing in again returns the person to the page they were on.
3. **A gone address is the app's page, not the server's.** Whatever a person typed, followed or kept, a page that does not exist answers in the app's frame with the reasons it might be gone and a way to the place it belonged to. It never reveals whether a thing exists that the person may not see.
4. **A warning is the size of its words.** The Admin's notice on somebody else's page is a pill beside the title that carries the whole sentence one hover or press away, not a band across the page.
5. **The list takes the width.** On the case page the recordings take the room and the facts about the case take what facts need. Chapter 1's rule, width is used, not capped, holds here as it holds on the incident page.

### Words

Added to `CONTEXT.md` with this chapter. **Admin pill**: the small mark beside a page's title that says an Admin is viewing another person's case, Workspace or recording, with the audit sentence behind it. The pages never say banner (the band it replaces), badge, tag or chip for it. **The gone page**: the app's one page for an address that has nothing behind it. No other word is added; the session's ending keeps Phase 1's words (Login session, idle timeout, the idle warning).

### Part 1. A session that ends under an open page

- **What happens today.** The idle warning counts down in the browser from the moment the page loaded and, at nought, guesses that the session ended. Meanwhile a page that asks the server for anything (the state of a batch, a playback copy, a match, the incident's state, Gideon's answer, a Stay signed in press) gets the sign-in page back as an answer, because the app redirects a request whose session has ended; the page tries to read it as JSON, fails, logs an error and asks again. The next thing the person presses lands them on Sign in. The cause line the middleware queues ("You were signed out after a long wait.", "You signed in from another place; this session has ended") is printed on the sign-in page, which is right, but the person has already lost their place.
- **The server answers a script plainly.** A request made by a page's script, rather than by the browser following a link, is answered with a small JSON body and the status 401 when the session has ended, never with the sign-in page. The body says why, in the same causes the audit row records: `idle`, `elsewhere`, `blocked`, `deactivated`, `ended` (an Admin's End sessions), and `gone` when the browser has no session at all. The build marks a script's request the one way, on every request the scripts make (the incident page, the recording page, the case page, the Panel, the upload page, Gideon, Report a problem), so one rule covers them all. A request from a link or a form is redirected to Sign in as today.
- **The page stops and says so.** The first such answer stops every timer and poll on the page, disables the page's controls (the transport, the forms, the buttons; the words stay readable and the video stays where it was, paused), and shows, where the idle warning shows, one line and one button:

  ```
  Your session ended after a long wait. Your cases, clips and documents are kept.   [ Sign in again ]
  You signed in from another place, so this session ended. Your cases, clips and documents are kept.   [ Sign in again ]
  ```

  With Folder management off the second sentence is Phase 1's: "Your recordings and transcripts have been removed." A blocked or deactivated account gets the middleware's line, "This account cannot sign in. Contact IT.", and no button. Nothing is asked of the server again; a page left open overnight shows the line in the morning, once, with no errors under it.
- **Sign in again returns the person.** The button goes to Sign in with the page's address as `next`, the tab or moment included when the page's address can carry it (the case page's tab, the incident page's moment and tab, the recording page's moment, a document's page and paragraph). The sign-in page honours `next` when it is a path inside the app (it begins with one slash and names no host; anything else is ignored and the person lands on Start as today), and the cause line is shown above the form as it is now. A person who signs in as somebody else lands on Start, not on the other person's page.
- **The idle warning stops guessing.** The countdown stays, since the server can only say the time left when a page loads; but at nought the page asks the server once, with the same kind of request, whether the session is still open, and shows the ended line only when it is not. A second tab that kept the clock moving no longer makes the first say it was signed out when it was not. Stay signed in keeps working as it does.
- **A form left open.** A form sent after the session ended, or after a sign-in in another tab changed the token, is refused today with the framework's plain "Forbidden" page. It becomes the app's page: "The form was open too long, or you signed in again in another tab. Go back and send it again." with Back, and nothing else on it. What was typed is the browser's to keep on Back; the page does not promise it.

### Part 2. The gone page

- **One page for every address that has nothing behind it.** The app's frame (the bar, the theme, the guide link, Report a problem), the words "There is no page at this address." and, under them, why that might be: the thing it pointed at was removed, the link is older than the thing it pointed at, or the address was mistyped. Then the way back: **Cases** for an address under `/case/`, **My recordings** for one under `/recording/`, the Panel's Status page for one under `/panel/` (an Admin only), and **Start** on every one of them. When the address names a case the person may see, the case's name is a link on the page ("Back to the case Smith"); when it names a case they may not see, or no case, the page reads the same as for an address that never existed, so a gone page never says whether a case is there.
- **Nothing from the server's own page.** The 404 is answered in the app's template with the status kept, for a page request. A script's request that meets a 404 gets the small JSON body it gets today, and the page that asked handles it as it does; the gone page is for people, not scripts.
- **The server's own failure.** A request the app could not answer (a 500) becomes the same frame with "Something went wrong on the server. It has been logged; try again in a moment, and if it keeps happening, report it." and the Report a problem link, which pre-fills where the person was as chapter 3 has it. The static page the framework shows today goes.
- **What it is not.** A withheld feature (Folder management off, Documents off) answers as today, a 404 for a page that is not on; it lands on the gone page like any other. A page the person may not see (another person's case, Workspace or recording) answers the gone page too, as today's `Http404` answers, and for the same reason.

### Part 3. The Admin pill

- **Where it is.** On every page an Admin opens that belongs to somebody else (the case page, the incident page, the recording page and its Speakers page, My recordings as someone else's), a pill at the right of the title row reads **As an Admin** in the warning colour, with an icon from `icons.html` the build chooses. The band across the page goes.
- **What it holds.** Hover or focus shows the whole sentence as the pill's title; a press opens it in a small card under the pill, the same shape as the paragraph card's head, with Close: "You are viewing Alex Reyes's case as an Admin. This access is recorded in the audit log, and it does not count as the owner having used the case." (a recording in a case says "case", a recording in nobody's case says "Workspace", as v1.75.1 has it; the name is the person's shown name). The sentence keeps every word the band carried; only its place changes.
- **The idle warning and the session line** keep the band's shape, since they are the page's own state and not a note on it, and the messages a page prints on arrival (the cause line, "Kept", "Saved") keep theirs.

### Part 4. The case page's width

- **The rule.** From 1280 pixels the case page's cap of 100rem goes and the About pane takes a measure of 24rem at the right; the list takes everything else. The file name column takes the room a name needs before any other column wraps; the wrap that scrolls the table sideways is for a window narrower than the columns, not for a wide one. Below 1280 the About pane follows the list as today.
- **From 2560** chapter 1's three panes stand (the list, the open recording's details or the Search tab's hits or an incident's Chronology in place, and the About pane), with the About pane at the same 24rem.
- **The About pane** keeps its five facts and its buttons; it is not folded into the head. A person who opens a case is reading the list, and the pane is the place the facts are looked for.

### In and out

- Signing in with `next` lands on the page named; an audit row is not added for that, since the sign-in row already records the sign-in.
- The gone page and the failure page are the app's templates for 404 and 500 and the CSRF failure view for 403; a script's request keeps its JSON answers on every status.

### What changes from earlier phases

- Phase 1's idle warning ("You have been signed out and your recordings and transcripts removed." at nought) becomes the session line above, asked of the server before it is shown.
- Phase 1's sign-in page gains `next`; nothing else on it changes.
- The Admin band of Phase 1 (the Workspace) and Phase 2 (the case) becomes the pill. ADR 0004's rule that an Admin's look is recorded and is not the owner's activity is unchanged; only where the sentence sits changes.
- Chapter 1's case page widths: the cap goes and the About pane takes a measure instead of a share.

### Audit rows

- None added. A session's ending writes the sign-out row it writes today, with its cause; a 404 writes nothing.

### Settings

- None added.

### Not in this chapter

- **Keeping a form's words across a session's end**: not chosen; the browser keeps them on Back, and a page that promises more must store what a person typed, which nothing in the app does yet.
- **A page that signs itself in again**: ruled out; the password is typed by the person, every time.
- **The Admin pill on the Panel's pages**: nothing there belongs to another person; no pill.

### Left to the build

- The one way a script's request is marked (a header the scripts always send is the plain choice), and the one place in the scripts that reads the 401 and stops the page.
- Which of a page's address parts `next` carries, within the rule that the person returns to the same page, tab and moment where the address can say them.
- The card the pill opens: whether it is the paragraph card's drawing or the confirm box's, so long as it is one of the two.
- The measure of the About pane if 24rem proves wrong on the office's screens; the rule that the list takes the rest stands.

## 8. The event's line, and the merge hint's rule

Written 2026-09-23 from the end-user walk of 2026-09-22 (the report "Transcribe walk findings", items I4 and V7). Two things on two pages that read wrong for the same reason: the page shows the data as it came, where a reader wants one line and the rest under it, and a hint is offered on a test that is true of too many. The first rows of the walk's chronology were camera descriptions four lines long, accepted as events before Phase 7 chapter 2 asked the proposer for one sentence; and on the Speakers page five different people were each offered a merge into the officer, because each never spoke while the officer did.

### Principles

1. **An event is one line; everything else is under it.** Whatever an Event's text is, the row says what happened in one line and puts the rest on the muted line with the source and the note. Nothing is thrown away: the layer edits the whole, the exports print the whole, and the memo reads the whole. The rule is the page's, so it holds for every Event there is, old and new, and no data changes.
2. **A hint says what the evidence shows and is offered when the evidence is enough.** The merge hint is Phase 5's: the timing shows it, the listener decides. What changes is when the timing is enough to name a merge: silence beside the busiest speaker is not; a few short lines that sit inside another speaker's turns is.
3. **Fewer buttons, the same words.** Where the timing shows less, the card says so in plain words and offers no button; same person as... on the card remains the way to merge by ear.

### Words

Added to `CONTEXT.md` with this chapter. **Detail**: the part of an Event's text after its line, shown on the muted line under it. **Neighbour**: the Speaker whose turns a small Speaker's lines sit inside, the one the merge hint names. The pages never say summary, snippet or truncation for the line, nor cluster, similarity or confidence for the hint.

### Part 1. The event's line

- **The line and the detail.** An Event's text is one field, up to 500 characters, as it is. The page reads it in two parts: the **line** is the text up to its first line break when it has one; otherwise its first sentence when the text runs past 120 characters (a sentence ends at a full stop, a question mark, an exclamation mark or a semicolon followed by a space); otherwise the whole. The **detail** is everything after the line. A line that would still run past 160 characters is cut at the last word before 160 with an ellipsis, and the detail is then the whole text. The split is made in one place in the app and given to every drawing; nothing is stored twice.
- **On the rows.** The Chronology's row and the Proposed events layer's row draw the line where the text was drawn, with the To check pill after it as today, and the detail first on the muted line, before the source, in plain type (the note stays in italics, the why in italics after it). The Event card's light state (chapter 11, which replaced the lane's hover) and the strip's picture carry the line alone. Find's hits match on the whole text and show the line.
- **On the layer.** The event's layer edits the whole text in one box, with the words under it: "The first line is the event. Anything after a line break is its detail, shown under it." A person who wants a shorter line presses Enter after it; a person who wants the description gone edits it out. Nothing else on the layer changes.
- **In the exports and the memo.** The chronology's Word export prints the line in the event's cell and the detail under it in the smaller type, and the spreadsheet gets a Detail column after the event's; the memo is told the whole text as today, since the detail is often the evidence. A clip's caption from an event uses the line.
- **What is accepted.** Accepting a proposal, a camera line or a comparison's finding stores the text as it comes, as today; the rule above makes the row read right whatever came. The proposer's own ask (one sentence, up to 120 characters, never beginning "the camera") stands from Phase 7 chapter 2, so new proposals seldom have a detail at all.
- **Rewriting a line** by the engine ("shorten this") is not in this chapter; a person edits.

### Part 2. The merge hint's rule

- **Today's test** names a merge for any Speaker under thirty seconds of talk who never overlaps a Speaker with more lines, and names the busiest such Speaker. On a stop with one officer talking most, every bystander with two lines qualifies, and each is offered a merge into the officer.
- **The fragment.** A Speaker is a fragment when it has at most eight lines and under thirty seconds of talk and none of its lines overlaps another Speaker's (two lines that touch within half a second are not an overlap, as Phase 5 has it).
- **The neighbour.** For each of a fragment's lines, the Speaker whose line ends within three seconds before it starts, or begins within three seconds after it ends, is that line's neighbour; where both sides have one, the nearer. The fragment's neighbour is the Speaker who is the neighbour of more than half of its lines. A fragment with no such Speaker has no neighbour.
- **The hint.** A fragment with a neighbour carries "Never speaks while <neighbour> does, and its N lines sit inside <neighbour>'s turns; see the lanes." with **Merge into <neighbour>**. A fragment without one carries "N short lines, never over anyone else's; see the lanes." and no button. A Speaker that is not a fragment carries no hint. Two fragments never name each other.
- **Where the rule lives.** In the app, on the Segments as they are, when the Speakers page is drawn; nothing is stored and nothing is asked of the engine. The Speaker check and the voice comparison of the accuracy plan are not changed by this chapter and not depended on.

### In and out

- Nothing is imported or exported differently except the Detail column and the Word export's second paragraph, both under Part 1.

### What changes from earlier phases

- Phase 6 chapter 2's row and Phase 8 chapter 1's "one line and a muted line under it" gain the line-and-detail rule; the exports of Phase 7 chapter 1 gain the detail's place.
- Phase 5 chapter 1's fragment hint gains the neighbour rule; its words change as above; same person as... and the lanes' drag are unchanged.

### Audit rows

- None added. A merge writes its rows as today.

### Settings

- None added. The measures (120 and 160 characters, eight lines, thirty seconds, three seconds, half a second) are the app's, written down here; an office that finds them wrong asks for a change.

### Not in this chapter

- **The engine shortening a line**: not chosen; a person edits, and the proposer already asks for one sentence.
- **Storing the line and the detail as two fields**: ruled out; one field, read two ways, keeps every export and the memo as they are and changes no data.
- **A voice comparison behind the hint**: held with the accuracy plan.

### Left to the build

- The exact sentence-end rule where a full stop sits inside an abbreviation ("Sgt. Hale"): the build may keep a short list of such abbreviations or accept the odd early cut; either is written in the commit.
- Whether the detail on the muted line is cut to a measure with the whole on the layer, within the rule that nothing is lost.
- The neighbour's tie-break when two Speakers neighbour the same number of a fragment's lines: the one with more lines.

## 9. One sitting

Written 2026-09-23 from the walk of a real twelve-camera incident on the office's copy (the session's walk log; the drawings `docs/spec/mockups/phase-8-sitting.html`). With all twelve cameras synced, Compare with the report, Ask Gideon on the incident page and the memo's Regenerate each stopped at once with "This transcript is too long for the AI assistant" and an `llm_too_long` row with no tokens sent. The cause, measured: the twelve transcripts together are about 28,000 tokens, the twelve Digests about 144,000, and the incident record reads a camera's Digest in place of its transcript and never drops one. So enriching a camera with vision, which the office does for every video, made the incident too heavy for the features that read across cameras, and the page said only that it was too long. The maintainer's asks: a limit the person can see coming, in words that mean something to them; never a refusal to add a camera; a limit that follows the engine when the office moves to a model with a larger window.

### Principles

1. **The assistant reads the incident at one sitting.** Before it writes the memo, checks the report or answers a question, it reads everything in the incident in one call. The sitting is what the engine can hold at once; the page shows how full it is, in the person's own unit, and says what changes on either side of the line. Nothing is called a token on a page a person reads.
2. **Everything said is always read.** Adding a camera never takes words out of the sitting. When the sitting is full, what the longest cameras *showed* is left out first, and their words stay in; the page says which cameras, and every output written that way says so where it is written.
3. **The limit is the engine's, read from the engine.** The app asks the engine what it can hold and draws every bar from that figure; the Panel's Engine window setting is the fallback for an engine that does not say. A larger model changes the bars within a minute and changes no setting.
4. **Adding a camera is never refused for size.** The wall, the chronology, Find and the clips take every camera under the count cap as today; the sitting governs only what the assistant reads whole.

### Words

Added to `CONTEXT.md` with this chapter. **Sitting**: everything the AI assistant reads of an Incident in one call before it writes the memo, checks the report or answers a question; the bar on the Cameras tab is how full the Sitting is. **Pinned**: a camera the person has asked to keep in the Sitting with what it showed, whatever else is added. The pages never say context, window, tokens, prompt or budget; those words stay on the Panel.

### The bar

- **Where.** A block at the head of the incident page's Cameras tab, under the heading "How much the assistant can hold at once". The same bar, without the camera list, on the Add cameras dialog.
- **The figure.** One line: "6 of 8 hours' worth", then the count and the sources: "12 cameras, what was said and what they showed". The unit is hours of camera: the engine's window converted at this incident's own rate (the record's tokens so far divided by the cameras' total length), so the figure is honest for a picture-heavy incident and for a sound-only one alike, and it is recomputed each time the page is drawn.
- **The blocks.** The bar is one block per synced camera in strip order, the longest widest, with a 2 pixel gap; hovering a block names the camera, its length and how it is read. A vertical line marks one sitting. Under the bar, small: "Each block is one camera; the longest is the widest." and "8 hours' worth: one sitting".
- **Three zones, each a sentence that says what changes for the person.** Under 85 percent of the line (green): "It reads everything in this incident at one sitting before it writes the memo, checks the report or answers a question. Room for about N more cameras of this length." (N from the average camera's share.) From 85 percent to the line (amber): "Nearly full. One more long camera and the assistant will stop reading what the longest cameras showed, and read their words alone. Everything said stays in, whatever is added." Past the line (the bar full, the blocks read by words alone hatched): "More than one sitting. The assistant reads everything said on all N cameras, and what M of them showed. The K longest are read by their words alone, so the memo, the report check and Gideon's answers say nothing about what those cameras showed; the chronology keeps every camera's events. Each one says so where it is written." A legend under the bar names the solid and the hatched block.
- **The list under a full bar.** Each camera read by words alone, with its length and **Always read what it showed**; under the list: "Pinning a camera keeps its picture in the sitting; the next longest camera moves to words alone instead."
- **On the Add cameras dialog.** The bar as it will read with the ticked cameras in, the cameras being added drawn lighter; under it the zone's sentence for that reading ("Still one sitting: the memo, the report check and Gideon's answers read what was said and what was shown on all 13 cameras."). Add is never greyed for size; the count cap keeps its refusal as today.

### What the assistant reads

- **The fit.** The record read across cameras (the memo, the incident chat, the comparison) is built as today from each synced camera's Digest, or its transcript where it has none, on the incident clock. When the whole does not fit the sitting with the chronology, the question or the report's window and the answer cap, cameras are moved to words alone one at a time, longest first, skipping Pinned cameras, until it fits: a camera read by words alone contributes its transcript's lines in place of its Digest. Only when every unpinned camera is by words alone and the whole still does not fit does the call fail as today, `llm_too_long`, and the page says "The words alone of these cameras are more than the assistant can hold at once; leave a camera out." A Pinned camera is never moved; if the Pinned cameras alone do not fit, the page says which pin to lift.
- **The same rule everywhere.** The memo, the incident chat and the comparison call one function for the record and the list of cameras read by words alone, so the bar, the fit and the outputs never disagree. Today's memo rule (drop transcript-only cameras to a line, longest first) is replaced by this one: no camera is ever reduced to a line.
- **Said where it is written.** The memo's head line: "Written <date> from everything said on N cameras and what M of them showed." with "K cameras by words alone." linking to the list; the memo's Word export carries the same line in its processing record. The comparison's state line: "5 pages against everything said on N cameras and what M of them showed" and the same link; the comparison's Word export likewise. Gideon's panel on the incident page: "Answers from everything said on N cameras and what M of them showed." above the question box, and each answer's notice carries it. The Proposed events layer, which reads cameras one at a time and is not bound by the sitting, gains its own line: "Read: N cameras. Never read: <cameras>" when a synced camera has had no run, so a person knows to run Propose events again.
- **The pin.** Always read what it showed on a camera's row on the Cameras tab (and on the list under a full bar) sets it; the row then carries a small pin and **Read it like the others** to lift it. A pin is the incident's, kept with the camera's placement, and survives a re-sync. Setting or lifting one writes an audit row.

### The engine's window

- **Read from the engine.** The llm-worker's minute check of the engine (Phase 3) also reads the model listing's window (`max_model_len` on the served model, as vLLM reports it) and keeps the figure with the check's result. Every fit check and every bar reads that figure; when the engine gives none, the Panel's Engine window setting is used.
- **On the Panel.** The Status page's AI assistant block gains "Engine window: 131,072 tokens, read from the engine at 11:20" or "…, from the setting; the engine did not say", "Largest reading today" (the biggest record the app fitted or refused, with its page) and "Readings refused" (the day's and the week's `llm_too_long` count). The AI assistant page's Engine window row greys with "read from the engine" while the engine answers, keeps its value, and says it is the fallback.
- **When the model changes.** GIDEON announces an engine swap under the box ledger's section 8; the app needs no word of it: the next minute's check reads the new window and every bar follows. The chapter asks nothing of GIDEON beyond what section 8 already gives.

### In and out

- The memo's and the comparison's Word exports carry the sources line under What the assistant reads; nothing else is exported differently. Nothing is imported.

### What changes from earlier phases

- Phase 7 chapter 1's memo fit (transcript-only cameras dropped to a line, a Digest never dropped) is replaced by the words-alone rule above; Phase 7 chapter 3's incident chat and Phase 8 chapter 4's comparison take the same rule in place of their own `llm_too_long` at the first misfit.
- Phase 3's Engine window setting becomes the fallback; its catalogue row says so.
- Phase 6 chapter 1's Add cameras dialog gains the bar; its count cap is unchanged.

### Audit rows

- **Cases**: Camera pinned; Camera unpinned (the incident, the camera). The existing AI assistant call row gains `words_alone` (the count of cameras read by words alone) on the memo, incident chat and comparison features, and `window_source` (`engine` or `setting`) on every call.

### Settings

- None added. Engine window's row in the catalogue is amended: the fallback while the engine does not report a window; greyed with the engine's figure while it does. The zone thresholds (85 percent) and the unit's conversion are the app's.

### Not in this chapter

- **A coarser Digest for reading across cameras** (one part per few minutes beside today's 30-second parts), which would make the bar seldom fill: held; this chapter makes the limit visible and survivable first, and the coarse Digest is measured against it afterwards.
- **Reading the incident in passes** (the memo or the comparison written from windows of time and combined): held for the same reason.
- **A count cap lowered for size**: ruled out; the count is a workstation's decoding limit, not the assistant's.
- **Showing tokens on the incident page**: ruled out; tokens stay on the Panel.
- **Dragging cameras into an order of importance**: not chosen; one pin per camera is the control.

### Left to the build

- The exact conversion to hours' worth when an incident has no Digest yet (the transcripts' rate alone) and the rounding of the figure (halves under ten hours, whole above).
- Whether the words-alone list on the Cameras tab shows under an amber bar as well (which cameras would go first), or only past the line.
- Where the minute check keeps the engine's window (the settings store's cache or the check's own row) and how a change is noticed by an open page (the page's five-second line, or the next draw).
- The name of the audit field for the cameras read by words alone if the count alone proves too little.

## 10. The sitting on the case page

Written 2026-09-23, the evening v1.78.0 went on the server, from the maintainer's ask ("I'm wondering if it should show somewhere on the case landing page") and the drawings `docs/spec/mockups/phase-8-sitting-case.html`. Chapter 9 put the bar on the incident page's Cameras tab, where a camera is added and pinned. A person opening a case asks two earlier questions: of the incidents the case has, which does the assistant read whole; and, when the case page offers to make an incident of the videos that ran together, what the assistant will be able to do with it. Three places were drawn; the head pill (a flag on the case name only when an incident is over) was set aside as saying little beside the tab.

### Principles

1. **The same bar, smaller, wherever an incident is listed.** The Incidents tab's row carries the sitting the way it carries "12 of 12 synced": the figure, a thin bar, and a word on what is read whole. Nothing new is said; the incident page's sentence is the hover.
2. **Before the incident exists.** The offer the case page makes for videos whose clocks overlap shows the bar as the incident would read, so the person sees what the assistant can do with it before pressing Make it.
3. **Cheap to draw.** A case page must not read every camera's Digest to draw a row. Each camera's share is kept on the camera and refreshed when its record changes; the case page adds the shares and compares them with the engine's window as it stands.

### Words

No new word. The Sitting and Pinned are chapter 9's; the case page says "The assistant holds" as the column's head and "whole" or "by words alone" as chapter 9 does.

### The Incidents tab

- **A column, The assistant holds**, after Cameras: the figure ("5½ of 7½ hours' worth"), a bar 8 pixels tall in the zone's colour with the words-alone part hatched as chapter 9 draws it, and on the bar's right a word: "all 12 whole" in the muted colour, or "3 by words alone" in the warn colour, or "does not fit" in the danger colour when even the words alone are too long. The row's hover carries the zone's sentence from chapter 9. The column is absent while the assistant is off or Incidents is off, and blank for an incident with no synced camera that has a transcript.
- **The videos list under the tab** is unchanged.

### The offer

- The offer line ("12 videos ran at the same time on 11/06/2025. Make them an incident?") gains the bar as the incident would read with those videos in: the figure, the sources line, the bar with one block per video, and under it the zone's sentence in the short form ("Room for about 5 more cameras of this length." or "More than one sitting: the assistant would read what 9 of 12 showed."). Make it and Choose myself stay as they are; the offer is never withheld for size. The offer to add one later video to an existing incident ("1 more video ran during Traffic stop. Add it?") gains the same bar, as the incident would read with the video in, the way the Add cameras dialog shows it.

### What is kept

- **Each camera's share.** `IncidentCamera` gains `record_tokens`, the estimate of the camera's record as chapter 9 counts it (its Digest, or its transcript when it has none), and `record_made_at`. The share is written when a camera joins an incident, when a Digest part lands or is remade for its recording, and when a transcript is corrected, by the same code that today makes the Digest and saves a Segment; a share found empty on a draw is computed then and kept. A video not yet in an incident (the offer) has its share computed for the draw and not kept; a case page with an offer of twelve videos reads twelve Digests once, as the Add cameras preview does today.
- **The fit on the case page** is chapter 9's arithmetic run on the kept shares against the engine's window as it stands and the memo's overhead, and the words-alone set is the same longest-first rule on the shares, skipping Pinned cameras; the case page never calls `sitting.fit` on the record itself. The two must agree: the incident page's `json_for` gains a mode that reads the kept shares, and the Cameras tab's bar and the case page's row are drawn from the same figures.

### In and out

- Nothing is exported differently; the case's exports do not carry the bar.

### What changes from earlier phases

- Phase 6 chapter 1's Incidents tab row and its offer line gain the column and the bar; the videos list is unchanged.
- Chapter 9's `json_for` reads kept shares when it has them and the record when it has not.

### Audit rows

- None added. A camera's share is not an event.

### Settings

- None added.

### Not in this chapter

- **A pill on the case head** when an incident is over one sitting: set aside; the Incidents tab says it.
- **The bar on the case list** (the Cases page): not chosen; a case's incidents are inside it.
- **The bar in the recordings table**: not chosen; a recording has no sitting of its own.

### Left to the build

- Whether the offer's bar counts the memo's overhead with the chronology of an incident that does not exist yet (the chronology is empty, so the overhead is the templates' alone) or leaves the overhead out and says so.
- The width of the column against the tab's other columns at the case page's narrow widths (under 900 pixels the figure alone, the bar dropped).
- Where the share's refresh hooks in when a Digest is remade part by part (after the last part, not after each).

## 11. A note is an event, and the Event card

Written 2026-09-24 from the maintainer's ask the same day, the last change before a pause: "notes should become events", because a note written on a recording's lines before the recording joins an incident is nowhere on the chronology; and the incident page's events "show very jumbled", the Events lane's words running into each other and a Chronology row saying everything at once. The maintainer's picks: one thing in two views (a note on a synced camera's line is an event, changed or removed from either place); a mark alone on the lane, with a card on hover or a press; the rows simplified, with the same card from the row; and the card from the focus camera's scrub bar and the viewer's timeline too. Built as `v1.81.0`.

### Principles

1. **A note on a synced camera's line is an event.** It sits on that Incident's Chronology at the line's moment on the Incident clock, with the note's writer, from the moment the camera is synced: a note written before the recording joined the Incident included. The app makes and unmakes the row as the note and the camera come and go, and writes no event row of its own for it; the note's own rows say what happened.
2. **One set of words, two places.** The event's text is the note. Edit on the Chronology changes the note on the line; Remove on the Chronology removes the note from the line; a note changed or removed under the line follows to every Chronology it is on. Nothing is copied.
3. **A mark is a mark.** The Events lane draws each event as a mark alone, so nothing on the strip can overlap at any zoom. What the mark stands for is one hover or one press away.
4. **One card everywhere.** The same Event card opens from the strip, from the focus camera's scrub bar, from a Chronology row and from the viewer's timeline, with the same shape, the same keys and the same way out, as the paragraph card is one card for every citation.
5. **The row says what happened.** A Chronology row is the time, the line and where it came from; everything about the event is on the card, not on the row. Chapter 1's principle 4 (room to read), taken further.
6. **Nothing moves for it.** The card floats over the page, beside the mark or the line; the wall, the strip and the rows stay where they were, and Escape puts everything back.

### Words

Added to `CONTEXT.md` with this chapter. **Event card**: the card that opens from a mark of an Event or a row's line; **light** for the state on hover or focus (the time, the line and the source), **open** for the whole card with its actions. **Note event**, in this document and the code and never on a page: the Event a note on a synced camera's line is; its pill reads "Note by <writer>, <camera>". The pages never say tooltip, popup, popover, pop-out, hover card, flyout, modal or dialog for the card, nor pinned for its open state (a camera's word, chapter 9), nor label for the lane's old words, nor shadow, mirror, copy or link for a note event.

### The note on the chronology

- **What it is.** An Event with the source **note**, its text the note's words (up to a note's 2,000 characters; a typed event keeps its 500), its time the line's start on the Incident clock, its camera the one the line is on, the cameras that show it its own camera alone when it is made (amended 2026-09-24, v1.85.2: it had been every camera running at that moment, which read on the Event card as if the note were on each) and the person's to change after, To check the person's, its writer the note's. It has no note of its own, no end, and is never proposed.
- **Where it comes from.** Every note on a shown line of a recording that is a synced camera of the Incident (a hidden second-Side copy of a line is never noted). A recording in more than one Incident has the note on each Chronology, one note.
- **Where it moves.** When a camera is placed or re-placed (by its clock, its file, by sound or by hand, or in the app's rounds), its note events are made or moved to the lines' new moments; a camera the app has only guessed has none. When a camera is removed from the Incident, or its recording leaves the case, its note events go and the notes stay on the lines. When the Incident is deleted, or the recording, they go with it. When a recording is processed again, each note event goes to the line its note is carried to, keeping its marks and its clips; two notes joining one line keep the first's row; a note no line takes leaves no row.
- **Edited from either side.** Under the line, the note's box changes or clears the note as chapter 2 has it, and every Chronology follows. On the Chronology, Edit on a note event opens the event's layer as "Edit note": the words (which are the note's), the cameras and To check; the time is the line's and cannot be moved from here, and the layer says so; there is no note under a note. A change to the words is written as the note's change (Note changed, with where it was done); a change to the cameras or the mark alone is the event's (event changed). Remove on the Chronology asks, saying it removes the note from the line and from every Chronology it is on, and is written as Note removed. Clip this event works as on any event.
- **Where it prints.** The Chronology's Word export prints the note event as an event, its source "Note by <writer>, <camera>", with a third legend when any row is one: "An event marked Note is the office's own note on a line of that camera's transcript, printed as written and never the assistant's." The spreadsheet's Source column says it and its Note column is blank. The transcript exports print the note as chapter 2 has it.
- **Told to the assistant.** The memo, the incident chat and Propose events read a note event among the Chronology's events, as "Event n, hh:mm:ss, <the note>; seen on <cameras>; the office's own note, written by <writer> on the line at hh:mm:ss on <camera>.", and are given the notes rule when any event is one or carries a note. The incident chat's separate block of the cameras' notes (chapter 2) is gone: every such note is on the Chronology. The memo counts a note event as an event and is stale after a note is written, changed or removed.
- **Search, Find and the Notes tab.** A note event is found once, as the line's note: Search's Events kind, Find's event hits and the Notes tab's list of notes on events leave it out.

### The Events lane

- Each event is a mark at its time, or a short bar to its end: a person's and a quoted one in the accent colour, a proposal in the working colour, a note event in the muted colour; the current event's mark lit. No words beside a mark at any zoom.
- Hovering a mark shows the Event card light: the time (and the end), the line, and the source pill. A press plays every camera from there and opens the card whole. Each mark takes keyboard focus in time order; with focus the light card shows, and Enter or Space opens it.
- The strip's picture for the exports is unchanged: numbered marks with the first words, as chapter 8 has it. (Superseded by chapter 12, v1.85.0: the strip picture is gone, and the Word export prints the chronology figure.)

### The Chronology tab's rows

- A row is the time (a citation that plays every camera), the line as a press that opens the Event card, the To check pill, a small source pill ("Added by alvarez", "Words, BWC2-098679", "Camera, DC-12", "Assistant, BWC2-098702", "Watch phrase, BWC2-098702", "From the report", "Note by alvarez, BWC2-098679"), and the word "note" in the muted colour when the event carries one, with the clip mark's words beside it when it has clips. The row being watched is lit as today.
- The detail, the cameras it is seen on, what it rests on, the note with its writer, the why and the clip mark's link leave the row for the card.
- The row menu stays: Edit, Add a note or Edit the note, Clip this event, Remove. A note event's menu has Edit, Clip this event, Open the line (the viewer at that line with the note lit) and Remove, and no Add a note.

### The Event card

- **Light** (hover, or keyboard focus on a mark): the time and the end, the line, the To check pill, the source pill; on a proposal a Proposed pill and the working colour. It goes when the pointer leaves. On a touch screen there is no light state: a press opens the card whole.
- **Open** (a press, Enter or Space): the light card's head with Close, then the detail, "Seen on" with the cameras, "rests on" as a citation that opens the paragraph card, the note in italics with its writer, the why in italics, the clip mark as a link to the case's Clips tab, and the actions: Edit, Add a note or Edit the note, Clip this event (greyed with "Sync a camera first" as the row menu is), Remove (which asks), and Go to the row when the card did not open from the row. A proposal's actions are Accept, Dismiss (greyed while the assistant is still proposing) and Go to the proposal. A note event's card shows the note as its line, the words of the line it sits on, its writer and date, and offers Edit, Clip this event, Open the line, Remove and Go to the row.
- **One at a time.** Opening another closes the first. Close, Escape, a press outside, or a press on the same mark closes it; after Close or Escape the focus goes back to the mark. Escape closes the card before anything else on the page: a layer under it stays open, and a paragraph card opened inside the Event card closes on the first Escape, the Event card on the second.
- **Where it sits.** Beside the mark or the line, on the side with more room, kept inside the window; it follows the mark when the strip is zoomed or moved and closes when the mark leaves the window. It is redrawn from the page's next state, so a note saved or a clip that finishes rendering shows without a press.

### The scrub bar and the viewer's timeline

- The focus camera's scrub bar keeps its ticks; hovering one shows the light card, and a press seeks and opens it. Chapter 5's "hovering a tick says the event's line" is met by the card.
- The viewer's timeline keeps chapter 2's mark for each noted line; hovering it shows the light card with the time, the note as the line and "Note, <writer>, <date>"; a press goes to the line and opens the card, whose actions are Go to the line and Change the note. This settles chapter 2's open item on the mark's hover.

### In and out

- **In**: the note event and its six sync points; the lane's marks alone with focus; the card in its two states from the strip, the scrub bar, the rows and the viewer's timeline; the row's new shape and the source pill; the keys; the note event's card, menu and layer.
- **Out**: any change to the event's layer for a person's event, the exports' shape beyond the source words and the legend, the memo's shape, the proposals layer's rows (the layer is where a proposal is read), the row menu's order.

### What changes from earlier phases

- Phase 6 chapter 2, Events: a fifth source, note; Edit on a note event changes its words, cameras and mark and never its time; a note event goes with its line, its camera's place and the note. The Events lane: the words beside a mark and the rule for overlapping labels are gone.
- Phase 7 chapter 1: a note event has no note of its own; its text is the note.
- Phase 8 chapter 2: "a note as a proposed event" reversed; the incident page's Gideon reads the lines' notes as events, not as a block; the timeline's mark gains the card and the open item on its hover is closed.
- Phase 8 chapter 1, The Chronology tab's rows: the muted line under a row moves into the card; the row gains the source pill.
- Phase 8 chapter 5: the scrub bar's ticks open the card.
- Phase 8 chapter 8: "the Events lane's hover carries the line alone" becomes the light card's line; the strip's picture is unchanged.
- `CONTEXT.md`: Event card added; Event, Note and Chronology amended.

### Audit rows

- None added. Note changed and Note removed gain `where` ("chronology") when done from the Chronology. A note event is never Event added or Event removed; event changed is written for its cameras or its mark alone. Opening a card is not an event.

### Settings

- None added.

### Not in this chapter

- **A note on an unsynced camera's line**, or on a recording in no Incident: a line note alone, as chapter 2 has it.
- **A note event's cameras following a camera synced later**: not chosen; Seen on is filled once (with the note's own camera, from v1.85.2) and is the person's, as for any event.
- **An end (`until`) on a note event**: ruled out; a note is a moment.
- **Editing on the card**: ruled out; the event's layer edits, the card reads.
- **A card for a camera's bar or a clip's block on the strip**: not chosen; a bar has its hover words and a clip's block opens the Clips tab.
- **Words beside the marks at a wide zoom**: ruled out; one rule at every zoom.
- **The comparison and the proposals reading a note event** as an event: they do, and the line names it a note; whether the comparison should leave the office's notes out is for the first real comparison to say.

### Left to the build

- The hover delay and the card's width, within the paragraph card's look.
- Whether the current event's mark is lit on the lane.
- Whether the row shows the one-word "note" tell.
- The words on a note event's layer and on its Remove question.
- The migration's treatment of notes already written on synced cameras' lines (they become note events at the upgrade).

## 12. The Timeline view, the chronology figure, and the camera that comes to the front

Written 2026-09-24 from the maintainer's two asks after the staged install went out: "in an incident when a note or event is selected, it should automatically show that camera as the focus", and "make the chronology a lot cleaner; the png export doesn't seem useful. How can we make this timeline look very clean and usable". The strip picture was a canvas drawing of the strip with each event's first words squeezed beside its tick, which collided as soon as two events were close. A mock-up was drawn and judged the same day: a vertical timeline, the cameras' spans as a band, the events down the page in spells, each a numbered mark in its camera's colour with its time, its line and its source; and the same figure on the Word export's page. Built as `v1.85.0`.

### Principles

1. **The camera you pressed is the camera you see.** A press on an event, from wherever the event is reached, seeks every camera and brings the event's own camera to the front, as Find's hits already did. Nobody should have to find the camera after finding the moment.
2. **One list, two shapes.** The Chronology tab's rows and its Timeline view show the same events from the same state; a toggle chooses, and nothing is on one that is not reachable from the other. The Event card holds every action in both.
3. **Nothing overlaps because entries stack.** The Timeline view and the figure run down the page, one entry after another, at any density; the strip's lane keeps its marks alone (chapter 11) and is the scrubbing surface, not the reading one.
4. **The export is the view on paper.** The Word document prints the chronology figure, the Timeline view in the light palette with the note and the why under each entry; a screenshot of the strip is not a document.

### Words

Added to `CONTEXT.md` with this chapter. **Timeline view**: the Chronology tab's second shape, a toggle beside Rows. **Spell**: a run of events with no gap of ten minutes or more between neighbours, headed by its span. **Chronology figure**: the Timeline view drawn on the Word export's page in place of the strip picture. The pages never say Gantt, chart, graph, list view, phase, segment, section, cluster or diagram.

### The camera comes to the front

- **The camera** is the event's own (the words' camera, the note's line's camera, the assistant's camera, the watch phrase's) when it names a synced camera on the page; else the first of the cameras the event is seen on that is synced; else none, and the front camera is left as it is.
- **Where it applies**: a press on a mark on the Events lane, on a row's or an entry's time, on the Event card's time (and so on the focus camera's scrub-bar ticks, which open the card), on the memo's event marks, on Find's event hits, and on a proposal's time in the Proposed events layer.
- **What happens**: every camera seeks the event's moment as today; then, in the Focus layout, the event's camera comes to the front and the sound follows it unless the sound is pinned (chapter 5's rule for a press on a tile); in the Side and Grid layouts the camera's tile scrolls into view and takes the sound unless pinned. A camera parked off the wall is swapped in first, as a press on its bar does.
- **Not from** the memo's plain citations (a time, not an event), the About line, or the Cameras tab.

### The Timeline view

- **The toggle**, Rows or Timeline, at the Chronology tab's head after the lead line, kept by the browser per person; Rows shipped. Event here and Propose events stay where they are.
- **The band**: the ruler's six times across the width, then one thin bar per camera in the camera's colour (the lane's colour), from its start to its end on the incident's span, a parked or unplaced camera drawn faint; under it a legend of the cameras' dots and ids and the words "The cameras' spans on the incident clock." Nothing else is written on the band; hovering a bar says the camera.
- **The spells**: the events in time order split where a gap of ten minutes or more begins; a heading per spell of its span ("21:56:24 to 21:58:47"), then "n events" in the muted colour, then a rule. One event alone is a spell headed by its time. The gap is one number in one place, in the page's script and in the server's export, and is not a setting.
- **An entry**: the event's number in a circle in its camera's colour (a person's event with no camera and no seen-on camera in the muted colour); a stem down to the next entry of the spell; the time as a citation that plays every camera and brings the camera to the front; the line as a press that opens the Event card; the To check pill; an end as "to hh:mm:ss"; and under it the source pill and the one-word tells (note, clips) as the row carries them. The current event's entry is lit as the row is; Back lights the entry it returns to.
- **Proposals** are not drawn; they have their layer, and the head's count says how many wait.
- **The row menu is not on an entry**: the Event card holds Edit, the note, Clip this event, Remove, Go to the row and Open the line, as chapter 11 has it.

### The chronology figure

- **In the Word export** (Chronology to Word, and the memo's last pages), in place of the strip picture and the five-column table: the band as a small picture drawn by the server (the times, one bar per camera in its colour) with a legend line under it; then the spells and the entries as text and rules, each entry its number in its camera's colour, its time in the mono type and its end under it, its line with To check beside it, its detail in the smaller type, and under it, in the small italic type, the note, the why and the source with the cameras it is seen on. The To check count, the clips line, the legends and the AI notice follow as before.
- **The spreadsheet** gains a last column, Spell, the heading's words.
- **The strip picture is gone**: the export menu offers Chronology to Word and the spreadsheet; Chronology to Word is a plain link, since the page no longer draws anything for it; the memo's export the same. The audit row Chronology exported no longer carries the format png.

### In and out

- **In**: the rule for the camera and its seven sources; the toggle and the Timeline view; the figure in the Word export and the memo's last pages; the spreadsheet's column; the picture export's removal.
- **Out**: the strip itself (unchanged; it drives the cameras), the Event card, the row's shape, the Proposed events layer's rows, the exports' cover.

### What changes from earlier phases

- Phase 6 chapter 2, Export: three exports become two; the Word document prints the chronology figure, not the strip as a picture and the table; the picture line reversed. Principle 5 (the picture is drawn from the rows, never kept) holds for the figure.
- Phase 7 chapter 1, Where they print: a note and To check print in the figure's entry rather than the table's cell and number column.
- Phase 8 chapter 1, The Chronology tab: the tab has two shapes.
- Phase 8 chapter 11: "the strip's picture for the exports is unchanged" is superseded; the card's time brings the camera to the front.
- `CONTEXT.md`: Timeline view, Spell, Chronology figure added; Event amended.

### Audit rows

- None added. Chronology exported loses the kind png.

### Settings

- None.

### Not in this chapter

- **A name for a spell** ("the stop", "the search"): ruled out; the app does not know what happened, and a wrong name on a heading is worse than none.
- **A setting for the gap**: not chosen; one number, changed in the code if an office's cases want another.
- **The strip replaced by the timeline**: ruled out; the strip is where the cameras are driven and placed by hand, and its marks now behave (chapter 11).
- **A figure on the case page**: not chosen.
- **Editing on the Timeline view**: ruled out, as on the card; the event's layer edits.

### Left to the build

- The gap that starts a spell (600 seconds) and the heading's words.
- How the band is drawn in Word (a small picture drawn by the server, so it prints sharp at page width).
- The stem between entries and the numbers' size, within the mock-up's measures.

## 13. One home and the rail

Written 2026-09-25 from the maintainer's asks the same day: the top level was unintuitive, a Start page asking "what do you want to do" with three doors beside a top bar of six places that overlapped it; people should know what each thing does; and after a batch, downloading the transcripts had to be obvious, since a person who left the batch page had no way back to its download but the page's address. Six landings were drawn the same day (three in the chat, three on a page; kept as `docs/spec/mockups/phase-8-home.html`) and E was picked: a rail down the left with one line under each place, the two actions at the top of the rail on every page, and Home leading with what needs the person; at the pick the download rule was added. "Workspaces" as the word for Cases was raised again and ruled out again: Workspace names the holding area behind My recordings. Built as `v1.86.0`.

### Principles

1. **A place says what it is for.** Every place in the rail carries one line in plain words, always there, so nobody has to open a page to learn what it holds.
2. **An action is a button, always in the same place.** Upload files and Record now sit at the top of the rail on every page; inside a case they put the recording in that case. An action is not a place and lights nothing.
3. **Home leads with what needs you.** A finished batch's download first, then the cases with something to settle, then what is running; the rest under them. Nothing on Home is only a door.
4. **A batch's download is wherever the person is.** On the batch page as before, on Home until Done with these, and on My recordings on the batch's group. Leaving the batch page loses nothing.
5. **Words stay.** Cases stay Cases; Workspace stays the holding area; My recordings stays the working page.

### Words

Added to `CONTEXT.md` with this chapter: **Home**, **Rail**, **Ready to download**; the Start page entry becomes history; Recordings page, Workspace, Clips page, My clips, Record now, Folder management, Dashboard line and Batch amended. The pages never say sidebar, menu, nav, dashboard, landing page, inbox or notifications.

### The rail

- **On every page**, down the left: at the top **Upload files** (the primary button, always) and **Record now** (with the Record now setting on, or inside a case with Live recording on; a bare New recording page without Record now has nowhere to land). Both carry the case the person is inside (`?case=`), so the upload page preselects Into a case and the recording lands in it; an Admin looking into somebody else's case gets neither, since those pages would refuse it.
- **The places**, each an icon, its name and one line: Home, "What is running, and what needs you"; Cases (with Folder management on), "Kept for a matter, after sign-out"; My recordings, "This session only, then gone"; Clips (with Clips available), "Pieces cut for a hearing". Under **Office**: Panel (an Admin), "Settings, status, people"; Help, "The guide, at this page", with the "?" that opens the guide beside the page as a small link under it where the window has room.
- **The place the person is on** is lit and carries `aria-current`; the upload page, the batch page and the record page light nothing. The Home item carries a count when batches wait for their download ("1 ready").
- **Widths.** From 1400 pixels the rail shows its lines; from 900 to 1399 it folds to icons and names; under 900 it is a row of icons under the top bar, the lines as titles. The incident page folds it at every width, since its desk needs the room.
- **The top bar** keeps the brand (to Home), the person's name, Sign out and the theme.

### Home

- **Where sign-in and the brand land**; `/start` follows to Home for old links, not permanently.
- **In order**: the greeting; the notices (transcription not installed; the service down; the storage warning); **Ready to download**; **Needs you**; **Running now**; **This session**; **Recent cases**; **Clips**. A section with nothing in it is not drawn.
- **Ready to download**: one row per finished batch of this session with at least one transcript: "5 transcripts ready, uploaded 10:02" (and how many were not transcribed), Download transcripts (the batch's zip, as the batch page offers it), Open the batch, Done with these. It stays until Done with these; a batch whose recordings went into a case is the case's.
- **Needs you**: the cases from the person's list whose dashboard line carries a pill in the warning tone (an incident not synced, events to check, proposed events waiting, a memo with newer events, clips failed, the retention warning), each with those pills and Keep where retention warns.
- **Running now**: one line of pills for the person's own work in hand: the unfinished batch ("2 of 5 transcribed", to the batch page), a Process again, transcripts preparing, tonight's vision.
- **This session**: the recordings not in a case, newest first, each with its state pill, its length, when it was uploaded and Open; above them the keep-or-lose line said once, plainly ("These stay until you sign out, or 8 hours after you stop working. Put a recording in a case to keep it."; without Cases, "Export anything you want to keep."); "n recorded here" when Record now is on; a small My recordings link.
- **Recent cases** (with Folder management on): every case the person can open, by last activity, each with its name, Shared by and New, its dashboard pills, Keep where warned, its count of recordings and its date, Open; New case opens the same box the Cases page has; All cases. An Admin who owns none sees the office's count and a link to Everyone's cases; empty, "No cases yet."
- **Clips**: one line with the count and how many are rendering, to the Clips page.

### The batch's download, wherever the person is

- **On the batch page**: unchanged; its finished state is the download.
- **On Home**: Ready to download, above everything, until Done with these.
- **On My recordings**: Uploaded this session grouped by batch, each group headed by when it was uploaded, its count and how many transcripts are ready, with Download transcripts, Open the batch and, once finished, Done with these. The rows keep their details pane and their acts.
- **In the rail**: the Home item's count, from the same rule.
- **Done with these** from any of the three lands on Home.

### What goes

- The Start page (`start.html`) and its tiles; the top bar's places; the Cases page's "Your recordings" button and its own copy of the New case box (one box, included on both pages).
- The route name `home` now means Home; My recordings is `recordings`, and every link that meant My recordings (the recording page's crumb, the New recording page's, the gone page's way, the clips page's headings, the after-recording landing, the redirects when a recording is missing) points there.

### What changes from earlier phases

- Phase 8 chapter 1, The Start page and its "Not in this chapter" line: superseded; the tile's words went with the page.
- Phase 2 chapter 1, The Cases page as the landing: superseded at v1.29.0 by the Start page and at v1.86.0 by Home.
- Phase 1, the batch page: its download gains two other doors, Home and My recordings.
- `CONTEXT.md`: the entries above.

### Audit rows

- None added.

### Settings

- None.

### Not in this chapter

- **Workspaces as the word for Cases**: ruled out again; Workspace names the holding area, and renaming both is a change of the app's vocabulary for a look.
- **A top bar of places**: replaced by the rail; a bar has no room for a line under each place.
- **Folding My recordings into Home**: ruled out; the working page with its details pane, Rename, Process again, Move to case, Clear and the Admin's view of somebody's Workspace stays a page.
- **A list of past batches beyond this session**: not chosen; a batch is the session's.
- **A "downloaded" mark** to hide Ready to download: not chosen; the count stays until Done with these, and the guide says so.
- **The case page's own Record and Add recordings** beside the rail's: kept this release; the walk decides.

### Left to the build

- The rail's widths and where it folds; the words of the six lines.
- The keep-or-lose line's words.
- The order of the pills under Needs you (the dashboard line's).
- How Recent cases performs for a person with many cases (every case is listed, at the maintainer's word; the pills cost about a dozen queries a case).

## 14. Deferred and ruled out

- **Workspace as the word for a Case**: ruled out with the layout picks of 2026-09-19, and again with chapter 13 on 2026-09-25; the glossary's word stands.
- **A rail of sections and a density switch**: not chosen.
- **Dialogs for proposals and a page for them**: ruled out; the layer keeps the cameras in view.
- **Filtering the chronology in place as Find**: ruled out; the words said on a camera are not events.
- **Gideon as a window always**: not chosen; the pop-out arrow gives it when wanted. **Gideon as a tab on the incident page** (the mock-up's 4A as drawn): amended out the same day; one design language throughout.
- **Layouts remembered per screen**: deferred; the width is read.

## Appendix A. Audit rows added in Phase 8

| Category | Row | Chapter |
|---|---|---|
| (none) | | 1 |
| Edits | Note added; Note changed; Note removed; Note carried | 2 |
| Exports | Exported gains notes; Download notes | 2 |
| System | Report made; Report seen; Report done; Reports swept | 3 |
| Cases | Document added; Document re-linked; Document removed; Comparison run; Event added with source report | 4 |
| (none; Clip created gains its way in) | | 5 |
| (none) | | 6 |
| (none) | | 7 |
| (none) | | 8 |
| Cases | Camera pinned; Camera unpinned; AI assistant call gains words_alone and window_source | 9 |
| (none) | | 10 |
| Edits | Note changed and Note removed gain where (chronology) | 11 |
| (none; Chronology exported loses the kind png) | | 12 |
| (none) | | 13 |

## Appendix B. Settings added in Phase 8

| Setting | Page | Default | Chapter |
|---|---|---|---|
| (none) | | | 1 |
| (none) | | | 2 |
| Reports | Features | On | 3 |
| Documents; Largest document; Documents per incident or recording; Read scans with OCR; Reading ceiling; Compare with the report; Comparison answer cap; Comparison time limit | Documents | On; 60 pages; 3; On; 400 paragraphs; On; 3,000; 600 s | 4 |
| (none) | | | 5 |
| (none) | | | 6 |
| (none) | | | 7 |
| (none) | | | 8 |
| (none; Engine window becomes the fallback) | AI assistant | | 9 |
| (none) | | | 10 |
| (none) | | | 11 |
| (none) | | | 12 |
| (none) | | | 13 |

## Sources

The maintainer's list of 2026-09-19 and the asks of the same day; the mock-ups `docs/spec/mockups/phase-8-layouts.html` and `docs/spec/mockups/phase-8-incident-panel.html` and the picks made from them (1A, 2A, 3A, 4A; the rule, 1A, 2A, 3A, 4A); Phases 6 and 7 for what the pages hold. For chapter 5, the maintainer's asks of 2026-09-22 and the drawings `docs/spec/mockups/phase-8-incident-desk.html`. For chapter 6, the maintainer's asks of the same evening after the first real comparison. For chapter 7, the end-user walk of 2026-09-22 (the report "Transcribe walk findings", items V5, D2, V2 and C5) and the drawings `docs/spec/mockups/phase-8-fail-well.html`. For chapter 8, the same walk (items I4 and V7) and Phase 5 chapter 1's fragment hint. For chapter 9, the walk of a twelve-camera incident on 2026-09-23 (the record measured at 144,000 tokens of Digest against 28,000 of transcript), the maintainer's asks the same day, and the drawings `docs/spec/mockups/phase-8-sitting.html`. For chapter 10, the maintainer's ask the evening v1.78.0 went on the server and the drawings `docs/spec/mockups/phase-8-sitting-case.html` (A and B picked, C set aside).

## Amendments applied

- **2026-09-25, v1.86.2.** Proposed events waiting are in the warning tone, so a case with proposals waiting for accept or dismiss is under Needs you on its own: the maintainer's word after the server walk of v1.86.0, where a case with 115 proposals waiting sat under Needs you only for its stale memo. Phase 7 chapter 3's tone list is amended the same day.
- **2026-09-25, v1.86.0.** Chapter 13 (One home and the rail) written and built the same day from the maintainer's asks and the pick of landing E among six drawn, with these decisions left to the build: the rail is 220 pixels from 1400, folds to icons and names from 900 to 1399 and to a row under 900, and is folded on the incident page at every width; the six lines are as the chapter has them; the keep-or-lose line reads "These stay until you sign out, or n hours after you stop working. Put a recording in a case to keep it."; every case is listed under Recent cases; the New case box is one include on both pages; the route name home now means Home and My recordings is recordings. Chapter 1's Start page lines superseded; Phase 2's Cases landing line amended.
- **2026-09-24, v1.85.0.** Chapter 12 (The Timeline view, the chronology figure, and the camera that comes to the front) written and built the same day from the maintainer's two asks and the mock-up judged the same day, with these decisions left to the build: a spell starts at a gap of 600 seconds; the heading reads the span and the count and never a name; the band in Word is a small picture drawn by the server with Pillow, the entries text and rules; the number's colour is the camera's lane colour, and the source pill still names the camera; the export keeps the note and the why under each entry; the memo's export posts nothing and the Word export is a plain link. Phase 6 chapter 2's export lines amended in place; chapter 11's picture line superseded.
- **2026-09-24, v1.81.0.** Chapter 11 (A note is an event, and the Event card) written and built the same day from the maintainer's asks and picks (one thing in two views; a mark alone with the card on hover or a press; the rows simplified; the card from the row, the scrub bar and the viewer's timeline). Decisions left to the build: the hover delay is a quarter second and the card 36 characters wide; the current event's mark is lit on the lane; the row shows the "note" tell and the clip mark's words; a note event's layer is titled Edit note with the time greyed and a line saying it is the line's; its Remove question says it removes the note from the line and from every chronology; a press on a strip mark still seeks every camera as before and opens the card from the same press; the migration makes a note event for every note already on a synced camera's line. Chapter 11 in the contents, Deferred and ruled out now 12. In passing: a Chronology row is now lit by Back (the row was looked for by the wrong attribute since chapter 1), and the event layer's duplicate id is gone.
- **2026-09-23, v1.79.0.** Chapter 10 built the same day, with these decisions left to the build: the offer's bar counts the templates' overhead with an empty chronology (the incident does not exist yet) and says nothing of it; the column keeps the figure, the bar and the word at every width (the table scrolls under 900 pixels as the tab's tables do); a share is refreshed on a draw that finds it never counted or older than the camera's newest Digest part, one reading of the record for the whole incident, so a Digest remade part by part is counted once at the next draw after its last part, and a transcript correction alone does not refresh it (the drift is a few tokens); the incident page's bar is now drawn from the kept shares by the same longest-first arithmetic the real fit follows, so the Cameras tab's bar and the case page's row are one set of figures and the real calls alone fit the record itself; a Digest part with no time (a test's) counts as fresh. Two migrations in two releases (0058, 0059) since chapter 9 shipped first.
- **2026-09-23.** Chapter 10 (The sitting on the case page) written for the build from the maintainer's ask after v1.78.0: the Incidents tab's column and the offer's bar (A and B of the drawings); the case head's pill set aside; each camera's share kept on the camera.
- **2026-09-23, v1.78.0.** Chapter 9 built the same day, with these decisions left to the build: the hours' worth figure is the cameras' own length, and the sitting holds that many hours as often as the window holds the reading (a rate-based conversion was tried first and gave absurd figures for a camera with few words); halves under ten hours, whole above; the words-alone list on the Cameras tab shows only past the line, since under an amber bar nothing is read by words alone yet; the engine's window is kept on the engine's status row (`EngineStatus.window_tokens`, migration 0058) with the minute check, and an open page reads it at its next draw; the audit rows carry `words_alone` as a count and `window_source` as `engine` or `setting`; the bar is drawn against the memo's reading, the largest an incident gets, and the Add cameras dialog's bar counts the ticked cameras' records as if in without fitting them; the comparison fits the record once against its largest page window; the memo's old drop-to-a-line rule is gone (`cameras_not_read` stays on the row, always empty from here). Confirmed before the build: GIDEON's engine reports `max_model_len` 262,144, twice the setting, so the record refused on 2026-09-23 fits from this release.
- **2026-09-23.** Chapter 9 (One sitting) written for the build from the walk of a real twelve-camera incident, where Compare with the report, Ask Gideon and the memo all refused the incident as too long: the bar on the Cameras tab in hours of camera with three zones that say what changes; everything said always read, the longest cameras' pictures left out first, a pin to keep one; the engine's window read from the engine with the setting as the fallback; the outputs saying what they read. The coarse Digest and reading in passes held.
- **2026-09-23, v1.77.0.** Chapter 8 built as written. Decisions left to the build: a full stop after a short list of abbreviations (Sgt., Ofc., Lt., Mr., No. and the like), after a single initial or after a number does not end the line; the detail on the muted line is shown whole; a line's neighbour on a tie between the speaker before and the speaker after is the one with more lines, and so is the fragment's on a tie of lines; the fragment's measures are the chapter's (eight lines, thirty seconds, three seconds); the event box's text became a box of lines with Ctrl+Enter to save.
- **2026-09-23, v1.76.0.** Chapter 7 built as written. Decisions left to the build: a script's request is marked with the header `X-Requested-With: transcribe`, set by `session.js` on every same-origin fetch, and the same script reads the 401 and stops the page (timers cleared up to the highest id, videos paused, the main column and the panels inert); `next` carries the page's path and query, and Sign in honours it only for the person whose session ended, remembered in the browser's session for the sign-in that follows; the pill's card is a details element in the paragraph card's shape with Close alone as script; the About pane is 24rem; the gone page's ways are chosen by the address's first part. Chapter 1's three panes from 2560 pixels remain unbuilt, as before. Also fixed: the page's Admin mark, written with stray backslashes in v1.75.1.
- **2026-09-23, v1.75.1.** The fix release from the maintainer's end-user walk of 2026-09-22, run in Claude's browser on the office's copy as a test Admin (the report is the artifact "Transcribe walk findings"): the transport's Sync button (chapter 1's layer conversion left it testing the box, not the layer); the case script's error on the recording page; the recording page's Report tab out of the Clips switch (chapter 4 part 2); the Gideon button's reason; the words and reading fixes the changelog lists. Chapter 7 (the pages that fail well: a session that ends under an open page, one page for a gone address, the Admin banner as a pill, the case page's width) and chapter 8 (the proposed event's line) are to be written from the same walk.
- **2026-09-22, v1.75.0.** Chapter 6 built the same day, with these decisions left to the build: the card is one script (`paragraph-card.js`) on the incident, recording and case pages and in the chat window, opened by any element carrying the card's data attributes, so a new citation anywhere joins by markup alone; the card reads the document's state endpoint once per document and shows the page picture in a scrolling frame about 260 pixels tall with the paragraph brought into view; a chronology row's citation is parsed from the event's rests-on text ("[Report, page 4, paragraph 2] ...") against the incident's linked reports, the first when the name does not match; Gideon's words-only preview stays for a page without the script; the Notes tab has no paragraph to cite (a note is on a line, not a paragraph), so it is left out; the memo carries no paragraph citations today, so it is left out; Escape closes the card before the page's own Escape, so a layer or the panel stays open; the Export menu's greyed line says "compare with the report first"; the Gideon handle is the work panel's code with its own memory (gideon-width) and no snap points. The Report tab's button reads "Open the comparison, N findings" once one exists (held from the same day). **Not built:** nothing of the chapter.
- **2026-09-22.** Chapter 6 (The report in place) written for the build from the maintainer's asks after the first real comparison: a paragraph card in place of the jump to the document page, the same card everywhere a paragraph is cited; the comparison's Word export in the Export menu; a handle on Gideon's panel. Camera lines in clip captions left alone at the maintainer's word.
- **2026-09-22, v1.74.2.** The first real comparison (a five-page report against six cameras) came back empty: the engine wrapped its JSON in a Markdown code fence and the app read nothing. Chapter 4's parser now takes a fence and any words before the first brace off before reading; a comparison keeps how many answers could not be read and what it dropped by reason (migration 0057), says them on its state line, and puts the two counts on the Comparison run row. The record's size (1,004 lines, about 59,000 tokens in one call) was read fine by the incident chat the same afternoon, so the reading is unchanged.
- **2026-09-22, v1.74.1.** The maintainer's first use of the desk: a Grid layout no longer moves the work panel under the strip; the panel stays beside the cameras in every layout, and the handle gives the cameras their width. Phase 6 chapter 4's "a Grid puts the panel under the strip" is amended by this line; the glossary's Layout entry says so.
- **2026-09-22, v1.74.0.** Chapter 5 built the same day, with these decisions left to the build: the player bar fades two seconds after the pointer stops moving while playing and stays while paused; the focus well's proportion comes from the picture's own width and height once known, capped at the window's height less 500 pixels and never under 220; the said band draws two lines before the lit one and one after, redraws only when the lit line changes, and freezes while Follow is off (it snaps back on Play); the focus tile's line under the picture is hidden in Focus, since the band carries the words and no camera line was drawn there; the clip track is 24 pixels tall, hatched in the warn colour, with a tag that follows the pointer at rest (the time under it) and while dragging (the span and its length); the Clips lane's block opens the case's Clips tab; a clip being marked survives a change of focus; the handle snaps within twelve pixels of 460 and of half the desk, and the panel's tabs show icons alone under 400 pixels; the clip box opens only once the end is set, so its Make the clip is never greyed for a marking in progress; the ruler keeps a press to seek and the track owns the drag. **Not built:** nothing of the chapter.
- **2026-09-22.** Chapter 5 (The desk, kept) written for the build from the maintainer's asks of the same day and the drawings picked: the page kept as it stands; the focus camera a player; the said band under the filmstrip, the focus camera alone; Clip as a button, a track that says what it is for, a lane and a line; the handle for the work panel. Three earlier mock-ups that moved the page's parts were set aside.
- **2026-09-19, v1.73.0.** Chapter 4 part 3 built the same day, with these decisions left to the build: a window is eight pages and its findings' JSON shape is page, paragraph, claim, at, mark, why; the window calls ask for agrees, differs and not on camera only, and one further call asks for what the report leaves out against the whole report with the chronology (skipped and said on the state line when the whole does not fit); a finding is dropped without a real paragraph (except not in the report) or without a real moment on the home's clock (except not on camera), and twins are dropped; at most twenty-five findings a window and two hundred a comparison; the comparison's home is the incident or the recording the report is linked to, one comparison per pair, the recording's without Make it an event; a Not on camera finding made an event opens the event box with the claim and the paragraph as its note, since the report has no clock; the layer on the incident page and a block under the document on the recording page are one drawing; the Comparison template joins the Templates page; the memo reads a rested-on paragraph as "from the report, which says". **Not built:** nothing of the chapter; the scan and the agency report are still to be measured.
- **2026-09-19, v1.72.0.** Chapter 4 part 2 built the same day, with these decisions left to the build and three cleanups from the first day's use: a document may be linked to an incident and to a recording at once (the tables held both), so Add the report on the Documents tab asks for either or both and a report is never loose; Re-link is two choices and a button on the row; the document page carries the case's name as its back arrow and Back to the incident or recording; the Report tab draws the document's pages from a state endpoint (`/document/<id>/state`) with the words under each page; a report read alone is named "Report" in citations and several are named by their titles made unique; a citation to a name the reading did not carry is dropped, except that any name resolves when one report was read; the matching rule counts the question's words of three letters or more in each paragraph and keeps the fullest matches, in document order; the ceiling's line is appended to the answer in parentheses; the recording page's chat reads that recording's report too (the chapter's third option, taken); a document keeps the splitter version it was read with, and the minute task reads an older one again. **Not built in part 2:** the comparison (part 3); the case chat's export cover naming the documents read.
- **2026-09-19, v1.71.0.** Chapter 4 part 1 built the same day, with these decisions left to the build: pdfplumber (over pdfminer.six) reads a text page's words with their positions and pypdfium2 draws the pages, at 110 dots an inch for the picture and 220 for OCR; a page with fewer than eight words of its own is read by OCR, and an OCR'd page with fewer than twenty words or a mean confidence under 55 is poorly read; a paragraph breaks at a gap of more than nine tenths of a line or at an indented line that follows a full one, numbered from 1 on each page, its box the words' bounds in page points and drawn on the picture as percentages; the page count is read at upload before the file is kept; the pictures are served by the app to whoever may open the case, not by Caddy, since they are small; the document page's words follow the page in view; Re-link and Remove are the Documents tab's, Add the report the two Details tabs'; the two tables are Document and DocumentPage (migration 0054); the settings page is Documents. **Not built in part 1:** the Report tab, Gideon's reading, the reading ceiling and the comparison (parts 2 and 3); the research note's server measurements wait for a real report and a real scan.
- **2026-09-19.** Chapter 4 written for the build from the outline and the discussion of the same day: the purpose fixed as the police report beside the cameras; a document is added from an incident or a recording, never loose; read whole with a reading ceiling and a matching rule past it, no embeddings; OCR for scans, English only, marked; the comparison with four marks, both sides cited, findings made events by a person; three parts as three releases; the settings on a Documents page; the upload page's statements.
- **2026-09-19, v1.70.0.** Chapter 3 built the same day, with these decisions left to the build: the box is the app's dialog with the kinds as two radio choices, the expected box hidden for an idea, and Close without sending asked only once the person has typed; the browser's name is read from the User-Agent header for Edge, Opera, Firefox, Chrome and Safari (else "a browser"), with the system after "on"; the rail's badge counts New alone; the Reports page has no paging (every report, in one table, the words folded); the sweep runs with the daily sweeper at half past three and is counted in its row as well as in Reports swept; the Status line is drawn with the page, not with its five-second lines; the Operator mail names the Reports page by its full address when sent from a request. **Not built:** nothing of the chapter.
- **2026-09-19.** Chapter 3 (Report a problem) written for the build from the outline: two kinds (a problem, an idea); the where line added only with the person's tick and shown before sending, the page's path without its query; the Panel is the record and the Operator mail the second copy; a Done report swept after ninety days; no screenshot, no reply in the app.
- **2026-09-19, v1.69.0.** Chapter 2 built the same day, with these decisions left to the build: the note's key is N and Escape closes the box; the box replaces the note's line under the words and Save with the box empty asks "Remove this note?"; the mark on the timeline is a small tick at the foot of the strip, with no hover; a note whose moment no new line spans takes the line with the nearest start, and two notes landing on one line are joined with a line break ("Note carried" rows say the old times); the date beside the writer is "19 Sep 2026"; the with-notes exports are two entries in the Export menu, and the Word one adds "with notes" to its kind line and running head and a count to the processing record; the Notes tab's rows carry the line's words shortened to 140 characters and a note opened from the tab or a Notes hit is lit under its line (?note=1); Download notes is one table (when, rests on, writer, note); the incident's Gideon lists the cameras' notes after the chronology and before the question. **Not built:** nothing of the chapter.
- **2026-09-19.** Chapter 2 (Notes) written for the build from the outline: the audit rows move from Cases to Edits, beside Segment corrected, since a note on a line is a change to a transcript's record and a recording need not be in a case; a note is carried on Process again; the exports that carry notes are separate entries.
- **2026-09-19, v1.68.0.** Chapter 1 built the same day, with these decisions left to the build: the layers are a stack, so a clip opened from an event returns to the event, then the tab; the moment is not moved back on Back; the work panel is 460 pixels to 1899, 560 to 2559 and 760 from 2560; the wall's columns follow the width in the Side by side layout only (a Grid a person chose wins, Focus wraps its filmstrip from 2560); Two panels shows from 3840 and puts the Memo beside the Chronology, remembered in the browser; the row menu is Edit, Add a note (Edit the note), Clip this event, Remove, with Remove asking first; the case card under the video shows eight recordings and "and N more"; the tabs' icons are play, search, clip, people, camera on the case page and text, clip, summary, info on the recording page and text, summary, camera, info on the work panel; Gideon's window of its own is the same page with only the panel showing (?gideon=window), which follows that case, recording or incident. **Not built in v1.68.0:** the case page's third pane and the recording page's three columns from 2560 (the pages lift their caps and the About pane widens; the third column waits for a build with the page's fold in hand), and the icons' being one drawn set (the app's existing icons serve).
- **2026-09-19.** Chapter 1 written for the build from the picks; chapters 2 to 4 outlined. Amended the same day at the maintainer's word ("I want Gideon's design language to be the same throughout"): Gideon is one floating panel on every page, the incident page included, and the Gideon tabs go.
