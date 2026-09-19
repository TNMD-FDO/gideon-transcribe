# Gideon Transcribe, Phase 8 specification

The pages laid out. Chapter 1 is written for the build; chapters 2 to 4 are outlined and take their shape here so that chapter 1 leaves room for them.

## About this document

This is the build specification for Phase 8 of Gideon Transcribe. Phases 6 and 7 (`docs/spec/SPEC-PHASE-6.md`, `docs/spec/SPEC-PHASE-7.md`) gave the app the incident page, the chronology, the assistant across cameras, search, and Gideon; each added a piece to pages that were laid out before it existed. On 2026-09-19 the maintainer's list named what that had done to the pages: the Start page's door to the cases says the wrong thing, the case page's tabs are small words, the recording page has dead space under the video, the incident page's Chronology tab is bunched and its pop-outs sprawl, Ask Gideon shoves the page aside, and the office's 49-inch screens are half used. The choices were drawn as mock-ups (`docs/spec/mockups/phase-8-layouts.html`, `docs/spec/mockups/phase-8-incident-panel.html`) and picked the same day; chapter 1 is written from the picks.

Read it with the same companions as Phase 7: `CONTEXT.md` (the glossary, with the Phase 8 words Layer and Work panel), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`, and the mock-ups. The conventions of the Phase 1 document apply unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing office-specific enters the repository.

## What Phase 8 adds

- **The pages laid out** (chapter 1, for the build): one rule for the incident page's work panel (tabs, and layers over them, with a Back that returns exactly), the Chronology tab unbunched, the proposals and Find's hits as layers, Gideon as one floating panel with the same shape on the three pages that have it (the case page, the recording page, the incident page) and nowhere else; the case page's tabs as a bar of sections with icons and counts, the same look on every page that has tabs; the recording page's case list under the video; the Start page's door saying Cases; and columns that follow the width up to the 49-inch screen.
- **Notes** (chapter 2, outlined): a note on a line of a transcript, and a Notes section on the case page that lists every note in the case with the moment each points at.
- **The bug report button** (chapter 3, outlined): a way for a person to report a problem or ask for a feature from any page, landing in the app for Admins and by mail to the Operator address, since nothing leaves the building.
- **Documents in a case** (chapter 4, outlined): PDFs uploaded to a case, read page by page, searched with everything else, and cited by page in Gideon's answers.

## Contents

1. The pages laid out
2. Notes (outlined)
3. The bug report button (outlined)
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
- **The case page**: Recordings, Search, Clips, Speakers, Incidents, in today's order, under the dashboard line. The Gideon tab goes: the panel is Gideon's one place, and it holds the same conversations.
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

## 2. Notes (outlined)

Not yet written for the build; the shape from the maintainer's list of 2026-09-19.

- **A note on a line.** On a transcript, a person adds a note to a line (as an Event takes a Note): their own words, with who wrote it and when, shown under the line in italics and in the exports. The assistant reads notes and never writes one.
- **A Notes section on the case page.** A tab, Notes, listing every note in the case with the recording, the moment it points at (a citation that plays), the writer and the words, newest first; the incident events' notes listed with them, each with its event. Search reads them (Phase 7 chapter 3 already reads the events' notes).
- **What changes**: Phase 1's transcript and its exports; Phase 2's case page (the tab); Phase 7 chapter 3 (the Notes kind). An audit row Note added; no setting.

## 3. The bug report button (outlined)

Not yet written for the build; the shape from the maintainer's list of 2026-09-19.

- **Report a problem**, in the page's foot on every page: a small box with what happened, what was expected, and a tick to include the page's address, the app's version, the browser and the person's name (never a transcript's words). It lands as a Report in the Panel, for Admins, and goes by mail to the Operator address when mail is configured. Nothing leaves the building.
- **The Panel's Reports page**: the reports, newest first, with Seen and Done marks; a count on the Status page while any is unseen.
- **What changes**: Phase 1's Panel and the foot of every page; the Email chapter (one more message kind). An audit row Report made; a setting Reports (On).

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
| Cases | Note added; Note changed; Note removed | 2 (outlined) |
| System | Report made; Report seen; Report done | 3 (outlined) |
| Cases | Document added; Document removed | 4 (outlined) |

## Appendix B. Settings added in Phase 8

| Setting | Page | Default | Chapter |
|---|---|---|---|
| (none) | | | 1 |
| Reports | Features | On | 3 (outlined) |
| Documents; Largest document | Cases | On; to be fixed | 4 (outlined) |

## Sources

The maintainer's list of 2026-09-19 and the asks of the same day; the mock-ups `docs/spec/mockups/phase-8-layouts.html` and `docs/spec/mockups/phase-8-incident-panel.html` and the picks made from them (1A, 2A, 3A, 4A; the rule, 1A, 2A, 3A, 4A); Phases 6 and 7 for what the pages hold.

## Amendments applied

- **2026-09-19, v1.68.0.** Chapter 1 built the same day, with these decisions left to the build: the layers are a stack, so a clip opened from an event returns to the event, then the tab; the moment is not moved back on Back; the work panel is 460 pixels to 1899, 560 to 2559 and 760 from 2560; the wall's columns follow the width in the Side by side layout only (a Grid a person chose wins, Focus wraps its filmstrip from 2560); Two panels shows from 3840 and puts the Memo beside the Chronology, remembered in the browser; the row menu is Edit, Add a note (Edit the note), Clip this event, Remove, with Remove asking first; the case card under the video shows eight recordings and "and N more"; the tabs' icons are play, search, clip, people, camera on the case page and text, clip, summary, info on the recording page and text, summary, camera, info on the work panel; Gideon's window of its own is the same page with only the panel showing (?gideon=window), which follows that case, recording or incident. **Not built in v1.68.0:** the case page's third pane and the recording page's three columns from 2560 (the pages lift their caps and the About pane widens; the third column waits for a build with the page's fold in hand), and the icons' being one drawn set (the app's existing icons serve).
- **2026-09-19.** Chapter 1 written for the build from the picks; chapters 2 to 4 outlined. Amended the same day at the maintainer's word ("I want Gideon's design language to be the same throughout"): Gideon is one floating panel on every page, the incident page included, and the Gideon tabs go.
