# Gideon Transcribe, Phase 8 specification

The pages laid out, notes, and a way to report a problem. Chapters 1 to 3 are written for the build; chapter 4 is outlined and takes its shape here so that the built chapters leave room for it.

## About this document

This is the build specification for Phase 8 of Gideon Transcribe. Phases 6 and 7 (`docs/spec/SPEC-PHASE-6.md`, `docs/spec/SPEC-PHASE-7.md`) gave the app the incident page, the chronology, the assistant across cameras, search, and Gideon; each added a piece to pages that were laid out before it existed. On 2026-09-19 the maintainer's list named what that had done to the pages: the Start page's door to the cases says the wrong thing, the case page's tabs are small words, the recording page has dead space under the video, the incident page's Chronology tab is bunched and its pop-outs sprawl, Ask Gideon shoves the page aside, and the office's 49-inch screens are half used. The choices were drawn as mock-ups (`docs/spec/mockups/phase-8-layouts.html`, `docs/spec/mockups/phase-8-incident-panel.html`) and picked the same day; chapter 1 is written from the picks.

Read it with the same companions as Phase 7: `CONTEXT.md` (the glossary, with the Phase 8 words Layer and Work panel), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`, and the mock-ups. The conventions of the Phase 1 document apply unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing office-specific enters the repository.

## What Phase 8 adds

- **The pages laid out** (chapter 1, for the build): one rule for the incident page's work panel (tabs, and layers over them, with a Back that returns exactly), the Chronology tab unbunched, the proposals and Find's hits as layers, Gideon as one floating panel with the same shape on the three pages that have it (the case page, the recording page, the incident page) and nowhere else; the case page's tabs as a bar of sections with icons and counts, the same look on every page that has tabs; the recording page's case list under the video; the Start page's door saying Cases; and columns that follow the width up to the 49-inch screen.
- **Notes** (chapter 2, for the build): a note on a line of a transcript under the rules an Event's note already has, exports that carry notes only when chosen, a Notes tab on the case page that lists every note in the case with the moment each points at, and Gideon told the notes as the office's own words.
- **Report a problem** (chapter 3, for the build): one link on every page that opens a small box for a problem or an idea, in the person's own words, with where they were added only with their tick; a Report kept on the Panel's Reports page with New, Seen and Done marks, counted on the rail and the Status page, and mailed to the Operator address when mail is configured. Nothing leaves the building.
- **Documents in a case** (chapter 4, outlined): PDFs uploaded to a case, read page by page, searched with everything else, and cited by page in Gideon's answers.

## Contents

1. The pages laid out
2. Notes
3. Report a problem
4. Documents in a case (outlined)
5. Deferred and ruled out

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
- **The rows**: the time (a citation that plays every camera), the line with its To check pill, and the row menu; under them one muted line: the source ("Added by alvarez", "Words, BWC2-098679", "Assistant", "Watch phrase"), where it is seen, the note in italics with its writer, the why in italics for an assistant's event, and the clip mark ("1 clip ready", a link). The row being watched is lit as today.
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
- **A redesign of the Start page** beyond the tile's words.
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
- **On the timeline**, a small mark at each noted line's time, in the muted colour, under whatever the timeline already draws there; pressing it goes to the line.
- **In the transcript's window** (Open in a window) the notes show as they do on the page; they are written on the page.
- **Processing again.** When a recording is processed again and its Transcript replaced, each note is carried to the new line that spans its moment (the line whose start is at or before the moment and whose end is after it; failing that, the line with the nearest start), with its writer and date, and the audit says so. A note is never dropped by processing again.
- **Where it goes.** With the Segment, as everything about a line does: deleted with the recording, restored with it from the Recycle bin, never copied into a Clip.
- **The incident page's wall** is unchanged: the line under a camera shows the words, not the note. A note that should sit on the Chronology is put on an event, added from that line as Phase 6 chapter 2 has it.

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
- **The incident's Gideon** reads the notes on the synced cameras' lines, placed on the incident clock, listed after the chronology's events as "The office's notes on the cameras' lines:", each "[hh:mm:ss] <camera> <writer>: <note>", under the same rule. The events' notes are read as Phase 7 chapter 5 has them.
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
- **A note as a proposed event**: a person adds the event from the line, as today.
- **Notes on a Document**: chapter 4.
- **Replies, threads, mentions and notifications**: ruled out; a note is one line, and the office reads them together on the Notes tab.
- **A note visible to one person only**: ruled out; nothing inside a shared Case is private to one person.

### Left to the build

- The mark on the timeline and whether hovering it shows the note's first words.
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

## 4. Documents in a case (outlined)

Not yet written for the build; the shape from the maintainer's list of 2026-09-19, marked as a bigger project.

- **PDFs in a case**: uploaded to a case as Documents (a police report, a complaint, a lab report), their text read page by page with free tools, listed on a Documents tab with their pages.
- **Cited by page**: Search reads them (a Documents kind, each hit a page that opens); Gideon on the case page reads them beside the transcripts and cites "<document>, page 4" as it cites a recording's time, the citation opening the page; the incident memo does not read them (the record is the cameras').
- **What changes**: Phase 2's case page; Phase 7 chapters 3 and 5; the exports' covers list the documents read. Settings: Documents (On), a size ceiling; audit rows Document added and Document removed.

## 5. Deferred and ruled out

- **Workspace as the word for a Case**: ruled out with the layout picks of 2026-09-19; the glossary's word stands.
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
| Cases | Document added; Document removed | 4 (outlined) |

## Appendix B. Settings added in Phase 8

| Setting | Page | Default | Chapter |
|---|---|---|---|
| (none) | | | 1 |
| (none) | | | 2 |
| Reports | Features | On | 3 |
| Documents; Largest document | Cases | On; to be fixed | 4 (outlined) |

## Sources

The maintainer's list of 2026-09-19 and the asks of the same day; the mock-ups `docs/spec/mockups/phase-8-layouts.html` and `docs/spec/mockups/phase-8-incident-panel.html` and the picks made from them (1A, 2A, 3A, 4A; the rule, 1A, 2A, 3A, 4A); Phases 6 and 7 for what the pages hold.

## Amendments applied

- **2026-09-19.** Chapter 3 (Report a problem) written for the build from the outline: two kinds (a problem, an idea); the where line added only with the person's tick and shown before sending, the page's path without its query; the Panel is the record and the Operator mail the second copy; a Done report swept after ninety days; no screenshot, no reply in the app.
- **2026-09-19, v1.69.0.** Chapter 2 built the same day, with these decisions left to the build: the note's key is N and Escape closes the box; the box replaces the note's line under the words and Save with the box empty asks "Remove this note?"; the mark on the timeline is a small tick at the foot of the strip, with no hover; a note whose moment no new line spans takes the line with the nearest start, and two notes landing on one line are joined with a line break ("Note carried" rows say the old times); the date beside the writer is "19 Sep 2026"; the with-notes exports are two entries in the Export menu, and the Word one adds "with notes" to its kind line and running head and a count to the processing record; the Notes tab's rows carry the line's words shortened to 140 characters and a note opened from the tab or a Notes hit is lit under its line (?note=1); Download notes is one table (when, rests on, writer, note); the incident's Gideon lists the cameras' notes after the chronology and before the question. **Not built:** nothing of the chapter.
- **2026-09-19.** Chapter 2 (Notes) written for the build from the outline: the audit rows move from Cases to Edits, beside Segment corrected, since a note on a line is a change to a transcript's record and a recording need not be in a case; a note is carried on Process again; the exports that carry notes are separate entries.
- **2026-09-19, v1.68.0.** Chapter 1 built the same day, with these decisions left to the build: the layers are a stack, so a clip opened from an event returns to the event, then the tab; the moment is not moved back on Back; the work panel is 460 pixels to 1899, 560 to 2559 and 760 from 2560; the wall's columns follow the width in the Side by side layout only (a Grid a person chose wins, Focus wraps its filmstrip from 2560); Two panels shows from 3840 and puts the Memo beside the Chronology, remembered in the browser; the row menu is Edit, Add a note (Edit the note), Clip this event, Remove, with Remove asking first; the case card under the video shows eight recordings and "and N more"; the tabs' icons are play, search, clip, people, camera on the case page and text, clip, summary, info on the recording page and text, summary, camera, info on the work panel; Gideon's window of its own is the same page with only the panel showing (?gideon=window), which follows that case, recording or incident. **Not built in v1.68.0:** the case page's third pane and the recording page's three columns from 2560 (the pages lift their caps and the About pane widens; the third column waits for a build with the page's fold in hand), and the icons' being one drawn set (the app's existing icons serve).
- **2026-09-19.** Chapter 1 written for the build from the picks; chapters 2 to 4 outlined. Amended the same day at the maintainer's word ("I want Gideon's design language to be the same throughout"): Gideon is one floating panel on every page, the incident page included, and the Gideon tabs go.
