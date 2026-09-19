# Gideon Transcribe, Phase 7 specification

The case as one place. Chapters 1 and 2 are written for the build; chapters 3 to 5 are outlined and take their shape here so that the built chapters leave room for them.

## About this document

This is the build specification for Phase 7 of Gideon Transcribe. After Phase 6 (`docs/spec/SPEC-PHASE-6.md`) put the cameras of an incident in step, gave them a Chronology and had the assistant write across them, the maintainer asked on 2026-09-17 for the next ideas and chose six: a clip across cameras, people across cameras, the chronology as a document staff finish, questions answered from the incident record, a case dashboard line, and search across a case, with the instruction to "keep in mind how features may overlap and how they should relate, let's keep this smart and intuitive". This document is the answer: four chapters, each a release, that make a case one place to work in rather than a list of recordings.

One idea runs through it. **The Event is the spine.** An Event on a Chronology is already a moment every camera shares; four of the six ideas hang off it and should look and behave the same: a person's note on an event, a clip cut from an event, a question answered with events as its citations, and a person matched across cameras at the moments events are seen. The two case-level ideas, the dashboard line and the search, read everything the others produce.

Read it with the same companions as Phase 6: `CONTEXT.md` (the glossary, with the Phase 7 words Note, To check, About, Incident clip), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`, and the mock-ups the chapters were drawn from where there are any. The conventions of the Phase 1 document apply unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing leaves the building. Nothing in this document is office-specific and no new service or environment key is needed.

## What Phase 7 adds

- **The chronology as a document, and the clip across cameras** (chapter 1, for the build): each Event takes a Note in a person's own words and a To check mark; the Chronology takes an About paragraph; all of it prints in the exports and is told to the memo as the office's own words. Clip this event cuts one file from the event's cameras and span, the focus camera large or a grid, with the incident clock and the camera ids burned in, and it is a Clip like any other on the Clips page.
- **Events the office would want: watch phrases, and the assistant's words** (chapter 2, for the build): a list of words the office always wants an event for, searched by the app itself on every Propose events run so a hit is never lost to the engine's judgement; the proposer asked for significant moments in one short sentence each, read in windows so no answer is cut short in silence, with the office's instructions in a setting and a Look for box on one run; and the memo re-shipped in a seasoned investigator's voice. From the maintainer's finding of 2026-09-19 that a line saying "I got gun" went unproposed.
- **The case dashboard line, and search across a case** (chapter 3, outlined): one strip under the case's name with a pill for everything that has a state, each a link; and one search box over every transcript, event, note, memo and summary of the case, hits grouped by recording and every hit a time that plays.
- **People across cameras** (chapter 4, outlined): the cameras of an incident play in step, so a voice heard saying the same words at the same seconds on two cameras is one person; the app proposes the matches on the case's Speakers tab, a person confirms and names them once, and the name flows to every camera and to the case's People.
- **Questions answered from the incident record** (chapter 5, outlined): Ask about this incident on the Memo tab, a chat grounded in the incident record, the Chronology and its notes, every time in an answer a citation that plays every camera, and an answer's line one press from becoming an Event.

## Contents

1. The chronology as a document, and the clip across cameras
2. Events the office would want: watch phrases, and the assistant's words
3. The case dashboard line, and search across a case (outlined)
4. People across cameras (outlined)
5. Questions answered from the incident record (outlined)
6. Deferred and ruled out

Appendices: A. Audit rows added in Phase 7. B. Settings added in Phase 7.

## 1. The chronology as a document, and the clip across cameras

Written 2026-09-17 from the maintainer's choice of ideas and the decisions taken the same day: a note per event and an About paragraph for the chronology; a clip cut from an event with the layout the person is in as its default, and both layouts on offer; the assistant never writes a note. Phase 6 chapter 2 built the Chronology and its exports; Phase 6 chapter 3 built the memo that reads it; Phase 1's Clips chapter built the single-recording Clip that this chapter's clip reuses.

### Principles

1. **The office's words stay the office's.** A Note is a person's line under an event: what it means for the case, a page cite, a thing to do. The assistant reads notes and never writes one, and a note is never mixed into the memo's text; it reaches the memo only as "the office's note" the memo must respect.
2. **A document staff finish.** The Chronology's Word export was a table of facts; with notes, marks and an About paragraph it is the working document the ask was about, and it is still made from the rows at the moment of export, nothing stored twice.
3. **A clip is an event, seen.** An Incident clip is cut from an Event: its cameras, its span, its name. A person adjusts before it is made and never types times from memory. There is no clip from nowhere: add the event first.
4. **A clip is a Clip.** It lands where Clips land, lists where Clips list, downloads as Clips download, and counts against the same rules. The only new thing is what is inside the picture.
5. **Nothing new to switch for notes; one switch for clips.** Notes and About are part of an Incident. Incident clips have their own switch, under Clips and Incidents both.

### Words

**Note**, **To check** and **About**, as `CONTEXT.md` defines them from this chapter, and **Incident clip**. On the pages: **Note**, **To check**, **About this chronology**, **Clip this event**. The pages never say comment, annotation, remark, flag, or montage.

### The chronology as a document

- **A Note on an Event**: plain text up to 2,000 characters, a person's own, kept on the Event with who wrote it and when it last changed. The event box (chapter 2 of Phase 6) gains a Note field under the line of text, folded closed until pressed or until the event has one. On the Chronology tab the note prints under the event's text in the muted colour, whole, with the writer's name; on the Events lane nothing changes. A note is edited with the event, through Edit, and removed by clearing it.
- **To check**: a tick on the event box, shown as a pill on the Chronology tab and counted in the tab's head line ("12 events on the chronology, 2 to check"). It is a person's mark that something needs looking at, and a person clears it; nothing clears it by itself.
- **About this chronology**: one paragraph on the Incident, up to 2,000 characters, opened from a line at the top of the Chronology tab ("About this chronology: none yet" or its first words), edited in a small box with Save and Cancel, plain text. It is what a reader should know before the events: the matter, the date, the cameras' owners as the office knows them.
- **Where they print.** The Word export (Chronology to Word, and the memo's last pages) prints About under the facts on the cover, before the cameras table; each event's note under the event's text in its cell, in italics, with "Note:" before it; and a To check mark in the number column, with a line under the table saying how many are to check. The spreadsheet gains the columns Note and To check. The picture is unchanged.
- **Told to the memo.** The memo's input (Phase 6 chapter 3) gains About as "The office's note on the incident:" before the chronology, and each event's note as "the office's note: ..." on the event's line. The incident rules gain one sentence: the office's notes are its own words, to be respected and never contradicted or rewritten, and a To check mark means the office has not settled the point, so the memo says so where it touches it. The memo's stale signature covers notes, About and the marks, so a changed note makes the tab say "an event changed".
- **Told to the proposals** (Phase 6 chapter 3): the events given to Propose events carry their notes, so a proposal does not repeat what a note already says.
- **Search** (chapter 3) reads notes and About.
- **Where they go.** With the Event and the Incident, as everything else does; a Note is part of an Event's row, and About is part of the Incident's.

### The clip across cameras

- **Clip this event**, on the event box (Edit) and as a small button on each event's row of the Chronology tab, while Incident clips are on and Clips are on and at least one of the event's cameras is synced with a playback copy. It opens the clip box under the event box:
  - **The span**: from ten seconds before the event's time to ten seconds after its end (or its time, when it has none), shown and edited as times of day on the Incident clock (or minutes and seconds when the Incident has no clock), with the length said beside them. The box refuses a span under one second or over the office's Longest clip.
  - **The cameras**: every synced camera with a playback copy, ticked when it is on the event's Seen on list, and greyed with "not running then" when the span falls outside its run. The order is the Wall's order, dragged as tiles are.
  - **The layout**: Focus (the first ticked camera large, the rest in a row under it) or Grid (every camera the same size), starting from the layout the page is in (Phase 6 chapter 4). In Focus a press on a small tile in the box makes it the large one.
  - **The sound**: from one camera, starting from the camera the page hears.
  - **Burn the clock** (on) and **Burn the camera ids** (on).
  - **The title**: the event's text, shortened to the Clip's 120 characters, editable.
  - **Make the clip.** The box closes, the Clips tab of the case (and the Clips page) shows it rendering, and the Chronology tab's event row shows a clip mark with the count of clips made from it.
- **What is made.** One file, made on the media worker by ffmpeg from the playback copies, each camera cut from its own moment on its own clock so the tiles play in step; the picture 1280 pixels wide (Focus: the large tile at 1280 by 720 with up to four small tiles of 320 by 180 under it; Grid: two across at 640 by 360 for up to four cameras, three across at 426 by 240 for up to nine); a camera that ends inside the span goes black in its tile with its id; the sound from the chosen camera alone; the Incident clock burned in at the top right as hh:mm:ss running, and each tile's camera id at its bottom left, in the captions' typeface. The clip is a Clip row whose Recording is the sound camera's, so its folder, its excerpt (the sound camera's words), its download names and its groups on the Clips page are the existing ones; it carries besides the Incident, the Event, the cameras with each one's offset, the layout and the burn choices, so Render again remakes it the same. Captions are not burned on an Incident clip in this chapter.
- **Where it shows.** On the Clips page and the case's Clips tab, in the case's group, with a Cameras column ("4 cameras, Focus") and "from the event ..." under the title; on the Chronology tab as the clip mark on its event; in the Chronology's Word export as a line under the events table listing the clips made from events, by number, title and length. Downloading, Download all, deleting and Render again are the Clips chapter's, unchanged.
- **Who may.** Whoever can open the Incident may make a clip from it, as they may clip a recording of the case; the Clip belongs to the person who made it as Clips do.
- **Limits.** Up to nine cameras in a clip; more are refused with "Up to nine cameras in one clip." The office's Longest clip applies. The render's time limit is the Clips chapter's plus a minute per camera.

### In and out

- The event box's Note field takes Shift+Enter for a new line; Enter still adds or saves. Escape closes the clip box before the event box.
- The address gains nothing.

### What changes from Phase 6 and earlier phases

- **Phase 6 chapter 2, Events and The exports**: the Event's fields gain Note and To check; the Incident gains About; the Word document, the spreadsheet and the Chronology tab print them; the event box gains the field, the tick and Clip this event.
- **Phase 6 chapter 3, The Incident memo and Proposed Events**: the memo and the proposals are told the notes and About; the incident rules gain the sentence about the office's notes; the stale signature covers them.
- **Phase 1, the Clips chapter**: a Clip may be an Incident clip, with the fields above; the Clips page and the case's Clips tab show the Cameras column; Render again remakes an Incident clip from its own fields; `media.cut_clip` gains a sibling that cuts several sources into one picture.
- **Phase 6 chapter 5, Deferred**: the clip across cameras is taken up here; the entry points here.
- Nothing changes in the viewer, in a recording's own Clip, in the Case Chat, or in Vision.

### Audit rows

Category Cases: **Event changed** covers a note or a mark as it covers the text (never the words); **Incident changed** gains "about" as a detail when About is saved. Category Clips (Phase 1's): **Clip saved** carries `cameras` and `layout` for an Incident clip, **Clip rendered** and **Clip failed** as today. None holds a word of a note, an About, or an event.

### Settings

**Incident clips** (On) on the Incidents page, group Clips, greyed while Incidents or Clips is Off: Clip this event on the Chronology tab. The Clips page's own settings (Longest clip, and the rest) apply to Incident clips unchanged. Notes, To check and About have no switch: they are part of the Chronology.

### Not in this chapter

- **Captions burned on an Incident clip**, and **a clip from a span with no event**: later, if asked. An event is one press away.
- **A note the assistant writes**, or the memo rewriting a note: ruled out by principle 1.
- **Notes on a recording's own transcript lines**: that is the transcript's correction and the Speakers page's business, not the Chronology's.
- **Attaching a file to an event**: ruled out in Phase 6 chapter 2 and still.

### Left to the build

- The clip box's exact wording and the drag of its tiles, within the words fixed here.
- The ffmpeg filter graph (scaling, the stacked layout, the black tile past a camera's end, the two drawtext layers) and the tile sizes at counts between two and nine, within the picture width of 1280 fixed here; the research note that records what was measured on the worker (`docs/research/incident-clip.md`).
- The clip mark's look on the Chronology tab and the clips line under the export's table.
- How the Note field folds, and the About box's placement in the tab's head.

## 2. Events the office would want: watch phrases, and the assistant's words

Written 2026-09-19, after v1.63.2, from the maintainer's finding on the server: the assistant read a camera whose record carried the line "I got, I got gun, I got gun" at 4:30 and did not propose it. The run on that six-camera incident proposed 87 events, five of its six answers cut off at the cap, most of them descriptions of the picture ("the camera view shifted to the interior of a moving vehicle"). The maintainer's words: the suggested events need to be better, the automatic events are verbatim VLM output and not useful, the memo reads too much of it and "should read like a good memo written by a seasoned investigator", and "maybe there's a way to expose these settings in the panel as well, where we can add instruction or phrases"; the gist, "if any event should auto find it's one similar to that". Phase 6 chapter 3 built the proposer and the memo; this chapter changes what they are asked for, adds a search the app does itself, and gives the office the words.

### Principles

1. **A watch phrase is a promise.** The office lists the words it always wants an event for. The app itself searches every synced camera's transcript for them before any engine call and proposes an event at every line that carries one, resting on that line. A promise the engine's judgement cannot break: no cap, no window and no model change loses a watch phrase.
2. **The engine proposes what matters, in one short sentence.** An Event is a thing that happened that a member of staff would put on the chronology, said in one plain sentence. A description of the picture is not an event unless the picture shows one; "the camera view shifted" is never one. Fewer, shorter, better.
3. **No answer is cut short in silence.** The run reads a camera in windows, each with room to answer in full, and where an answer is still cut the page says so.
4. **The office steers in the panel, not in the template.** The shipped templates keep their wording; an office's own instructions sit in a setting beside the watch phrases and are folded into every run, and a person can add what to look for on one run without touching either.
5. **The memo is an investigator's.** It reads as a seasoned investigator writes: what happened, who did what, where the cameras and the words are the evidence for it, said plainly and grouped by subject; the picture is described only where the picture is the evidence.
6. **What was, stays.** Propose, never apply; the office's Events first; every proposal rests on a real line; a numbered speaker label is one camera's alone; nothing the assistant proposes reaches the Chronology unaccepted. Chapter 3 of Phase 6 stands under this chapter.

### Words

**Watch phrase**, as `CONTEXT.md` defines it from this chapter: a word or phrase the office always wants an event for, listed in the panel, found by the app's own search. **Watch phrases** is the setting; **What counts as an event** is the office's instruction to the proposer; **Look for** is the box on one run. An Event found by a watch phrase has the source **watch phrase** ("Watch phrase: gun, on BWC2-098702"). The pages never say keyword, trigger, alert, hotword or rule.

### Watch phrases

- **The setting.** **Watch phrases** on the Incidents page, under The assistant: a text box, one phrase per line, shipped with the list below, greyed while Incidents is Off. Editable and resettable to the shipped list as a template is. A phrase is one to six words; case does not matter; a phrase matches whole words only ("gun" matches "gun" and "guns", never "begun"); a line that is empty or a duplicate is dropped when saved; up to 200 phrases.
- **The shipped list**, one line each: gun, firearm, pistol, rifle, shotgun, knife, weapon, armed, shoot, shot, shots fired, taser, tase, pepper spray, mace; stop resisting, get on the ground, hands behind your back, I can't breathe, not breathing, ambulance, bleeding, medic, use of force; you're under arrest, you are under arrest, right to remain silent, Miranda, understand your rights, lawyer, attorney, I want a lawyer, I don't want to talk; can I search, mind if I search, consent, search warrant, warrant, probable cause, step out of the vehicle, open the trunk; I did it, it was me, going to kill, I'll kill, threatened; drugs, narcotics, fentanyl, meth, cocaine, marijuana, weed, stolen; identification, licence, license, registration. An office edits it to its practice; the first office's own list stays in its planning repository, never here.
- **The search.** On every Propose events run, before any engine call and whether or not the AI assistant is On: each synced camera's transcript lines and, where the camera has a Digest, its picture lines (the "seen" lines), read by the app for every watch phrase. Every line that carries one becomes a proposal at the line's time, with source watch phrase, the phrase, the camera, and the line as what it rests on: "Watch phrase "gun": I got, I got gun, I got gun." (a picture line: "Watch phrase "gun", seen: a handgun on the passenger seat"). A phrase heard again on the same camera within thirty seconds joins the first proposal ("said three times") rather than making another. The checks of Phase 6 chapter 3 apply: nothing within five seconds of an Event or a proposal already on that camera, nothing a person dismissed. The hits are saved as they are found, so the page shows them before the engine has answered.
- **On the page.** A watch-phrase proposal lists under Proposed by the assistant with the others, oldest first, its source pill reading **Watch phrase** with the phrase, and the same Accept and Dismiss. Accepted, the Event keeps the source watch phrase, prints in the exports as "from the watch phrase "gun" on BWC2-098702", and does not by itself put the AI notice on an export, because the app's search is not the assistant. On the strip's Events lane it is drawn as any proposal.
- **With the assistant Off.** Propose events shows while Incidents is On and either Assistant proposes events is On or the Watch phrases list is not empty; with the assistant Off or unreachable the run is the search alone and the state line says "Searched 6 cameras for 52 watch phrases: 3 found". So an office with no engine still gets the promise.
- **Told to the engine.** The engine is told the list ("The office watches for these words and phrases; every line that carries one is an event") and, as the earlier cameras' proposals are, the hits already found, so it neither misses nor doubles them.

### The proposer's words

- **What counts as an event**, the shipped wording of the Proposed events template rewritten: a thing that happened that a member of staff would put on the chronology and could point to in the record. It is: a person or a vehicle arriving, leaving or being stopped; a command, a warning or an advisement of rights; a question about consent or a search and its answer; a search, a restraint, a use of force, a weapon drawn, shown or mentioned, an injury, an arrest as the words or the picture describe it and never as a conclusion; a statement that carries weight, an admission, a denial, a threat; a thing handed over, found, seized or taken; a move to another place; a person or a vehicle identified; the camera starting, stopping or being muted. It is not: the picture changing, the camera moving, a vehicle driving with nothing happening, weather, scenery, a description of clothing or surroundings on its own, or small talk. One sentence each, plain words, third person, past tense, up to 120 characters, saying what happened and not what it means, never beginning "the camera" or "the view". A numbered speaker label is this camera's alone. Nothing already on the list given; only what this camera adds; every proposal rests on a line given, copied after it. The template stays editable and resettable on the Templates page.
- **The office's instructions.** **What counts as an event** is also a setting on the Incidents page, under Watch phrases: a text box, empty by default, greyed while Assistant proposes events is Off, up to 2,000 characters. Its text is given to every run after the template as "The office adds:" so an office says what its practice wants ("we defend the accused: everything an officer said about why the stop was made, every question before rights were read") without editing the template.
- **Look for, on one run.** Beside Propose events a small box, **Look for**, empty each time the page opens, up to 300 characters: "anything about the gun and the ring camera". Its text is given to that run alone as "For this run the office asks you to look for:". Never stored past the run; the audit row records that a Look for was given, never its words.
- **In windows.** A camera's record is read in windows of **Proposed events window** (600 seconds of the recording; 120 to 1,800), one call per window in time order, each call given the Events and the proposals so far. The answer cap stays per call, so a window has room to answer in full; the app keeps up to twelve proposals a window and drops the rest, which is still fewer than an answer cut mid-list. A camera of 47 minutes is five calls where it was one.
- **Cut short, said so.** When an answer is still cut at the cap the state line says it ("Proposed 14 events at 14:02; 1 answer was cut short, raise Proposed events answer cap"), the run's Details fold for an Admin lists the windows and which were cut, and the audit row counts them as it does.

### The memo's words

- **The Incident memo template's shipped wording is rewritten** to the voice asked for: a memo a seasoned investigator writes for the attorney on the case. It says what happened, who did what and what was said, in the order it happened, grouped by subject inside What happened, and it points at the evidence: the time of day, the camera, the event's number. It never narrates the picture ("the camera view shifted", "the footage shows") and describes what a camera showed only where the picture is the evidence for a fact ("a handgun lay on the passenger seat, BWC2-098702 at 21:58:10"). It uses the Chronology's events as the spine and the office's notes as the office's reading, and it stops at the facts. The parts and their order are unchanged (Summary; The cameras; People; What happened; Commands, warnings, and rights; Statements that matter; Names, places, and dates; Unclear parts), so nothing built on the shape changes.
- **The incident record it is written from** is unchanged, and so are its citations, the stale rule, the export and the settings. A memo written before this chapter stays as it is until Regenerate.
- **Speaker names in the memo** are out of this chapter, at the maintainer's word (2026-09-19: "let's deal with this more when this part of the plan is up for discussion"). The rule of Phase 6 chapter 3 stands: a numbered label is one camera's alone, and a line is attributed to a person only by a name the words give or the office set.

### In and out

- **In**: the Watch phrases, What counts as an event and Proposed events window settings; the search on every run and its proposals with the source watch phrase; the Look for box; the run in windows with the cut-short line; the two templates' shipped wording rewritten; Propose events with the assistant Off.
- **Out**: phrases as patterns (regular expressions), phrases matched on the sound rather than the words, a run by itself when a transcript lands (Phase 6 chapter 3's "Not in this phase" stands), accepting the sure ones automatically, and names across cameras.

### What changes from Phase 6 and earlier phases

- **Phase 6 chapter 3, Proposed Events**: the run gains the search first, the windows, the office's instructions and the Look for; the shipped Proposed events template's wording is replaced by this chapter's; the state line gains the cut-short words; Propose events shows with the assistant Off while phrases are listed. **The Incident memo**: the shipped Incident memo template's wording is replaced by this chapter's; nothing else.
- **Phase 6 chapter 2, Events**: the source **watch phrase** joins person, quote, camera and assistant, on the page, on the lane, in the exports and in the events' JSON; the Word export's AI notice line prints for source assistant as before and not for source watch phrase.
- **Phase 4 chapter 7, The templates**: the two templates are re-shipped; an office that edited either keeps its edit and sees "Reset to the shipped wording" as before.
- **Phase 4 chapter 8**: the AI assistant call with feature `incident_events` gains the window's number and count, whether a Look for was given, and the count of watch-phrase hits; the never-logged list gains the watch phrases' hits, the Look for's words and the office's instructions.
- The Case Chat, the memo's citations and export, the clips, the notes and the strip are unchanged.

### Audit rows

Category Cases: **Events proposed** gains `watch_hits` and `windows`. Category LLM: **AI assistant call** with feature `incident_events` gains `window` (n of m), `look_for` (given or not) and `cut_short`. Category Admin: the settings' rows as every setting has them; a change to Watch phrases records the count before and after, never a phrase. None holds a phrase, a hit, a line or the Look for's words.

### Settings

On the Incidents page, under The assistant: **Watch phrases** (the shipped list; greyed while Incidents is Off); **What counts as an event** (empty; greyed while Assistant proposes events is Off); **Proposed events window** (600 seconds; 120 to 1,800; greyed while Assistant proposes events is Off). The rows join `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` and Appendix B.

### Not in this chapter

- **Phrases as patterns**, and phrases by category with a colour each: a list of words is what the office asked for; the rest waits until an office has used it.
- **The search on the whole case** (every transcript, not the incident's cameras): that is chapter 3's search across a case, which will offer "make an event of this hit" on an incident's camera.
- **A run by itself** when a camera's transcript lands, and **accepting the sure ones automatically**: as Phase 6 chapter 3 left them.
- **Speaker names across cameras**: Phase 7 chapter 4, and the maintainer's discussion before it.

### Left to the build

- The whole-word rule's edges (apostrophes, hyphens, a phrase across a line break, the plural), within the rule that "gun" never matches "begun".
- The join window for a phrase heard again (thirty seconds) and the words of the joined proposal.
- The twelve-a-window ceiling and the order in which surplus items are dropped (the later ones).
- The exact wording of the rewritten templates, within the substance above, and of the state lines.
- Whether the Look for box sits beside the button or opens from it on a narrow window.

## 3. The case dashboard line, and search across a case (outlined)

Not yet written for the build; the shape decided on 2026-09-17, with the search drawn as a mock-up the same day.

- **The dashboard line.** One strip under the case's name, above the tabs, with a pill for everything in the case that has a state, each a link to the tab or page where it is dealt with: recordings transcribing or in the queue (with the waiting words of `waiting.py`), videos waiting for vision tonight and the window's words, incidents with their sync state, events to check, people to confirm (chapter 4), memos written and memos with newer events, clips rendering, and whom the case is shared with. A pill shows only when its count is not zero; a case with nothing pending shows one line, "Everything is ready." It is drawn on the server from the counters the pages already have (`vision.line`, `vision.pending`, `_rows_for`, `incidents.strip_rows`, `incident_assistant.memo_line`, the Clips groups) and costs no new query of size.
- **Search across a case.** One box in the case page's head, taking the place of the Recordings tab's search field (Phase 2's `?q=` over the segments, which it extends). It searches the words of every transcript in the case, the events of every incident with their notes and About, the memos, and the summaries, whole words, and shows the hits grouped by recording and by incident, with the counts by kind as filters (Words, Events, Memos and summaries, Notes). A hit on a recording is its time as a citation that opens the viewer at that line, with the all cameras link when the recording is a synced camera; a hit on an event is its time of day, opening the incident page there; a hit in a memo or a summary opens it at the paragraph. The first two hundred hits, then "more". The search term is never audited, as Phase 2 has it. The build measures the case-wide `icontains` on the office's largest case and adds a PostgreSQL text index on the segments' words if it is needed, recorded in a research note.
- **What changes**: Phase 2's Cases chapter (the head, the search); Phase 4's Vision (the tonight pill); Phase 6 (the incident pills). No setting; no audit row.

## 4. People across cameras (outlined)

Not yet written for the build; the shape decided on 2026-09-17, with the mock-up of the same day: the proposals live on the case's Speakers tab, never on the incident page beyond a one-line pointer.

- **The match.** The cameras of an incident are in step, so a voice saying the same words during the same seconds on two cameras is one person. For every pair of synced cameras with transcripts, the app lines up their segments on the Incident clock, folds the words (case, punctuation), and counts the pairs of lines that overlap in time and share most of their words; for each speaker label on one camera the label on the other with the most such lines, when there are at least three and no rival label has half as many, is proposed as the same person, and the proposals chain across cameras into one person seen on several. A label already a name on one camera carries its name into the proposal. No engine call; the media worker or the app itself runs it when the incident's sync changes or a transcript lands, and on a press.
- **On the Speakers tab** of the case page: a section "Same person on several cameras" above the case's speakers, one row per proposed person naming each camera's label, the count of matching moments with one example as a citation that plays every camera, a name field (filled when one camera already has a name), **Confirm** and **Not the same**. Confirm renames the label on every camera through the viewer's own speaker rename (the same audit row, the same undo) and joins the case's People, so the name reaches the memo, the proposals, the chat and the words under the tiles. Not the same puts the proposal away and it is not offered again for those labels.
- **On the incident page**, the Cameras tab shows one line while proposals wait: "3 people to confirm on the case's Speakers tab", a link.
- **The probe first.** As with the sound match, the build runs the match on one of the office's real incidents by a management command and records the counts in `docs/research/people-across-cameras.md` before the thresholds are fixed. Voice prints (Phase 5 chapter 2) stay deferred; the wearer of a camera by loudness is left to a later chapter.
- **Rows and settings**: category Cases, **People matched** (count, cameras), **Person confirmed across cameras** (as Speaker changed on each recording, with how: cameras), **Person match dismissed**; setting **People across cameras** (On) on the Incidents page, group The assistant, though it makes no engine call.

## 5. Questions answered from the incident record (outlined)

Not yet written for the build; the shape decided on 2026-09-17.

- **Ask about this incident**, under the memo on the Memo tab: a chat in the Case Chat's shape (`chat-ui.js`, the same box, the same history) grounded in the incident record (Phase 6 chapter 3's merge of the cameras' Digests onto the Incident clock), the Chronology with its notes and About, and the confirmed people; nothing else. Every time in an answer is `[hh:mm:ss]` on the Incident clock and a citation that plays every camera; beside it, **+ event** makes an Event from the answer's line with its time, as a chat citation does today. The answer says which cameras it drew on when the record left one out.
- **The template** Incident chat on the Templates page; the feature `incident_chat` on the AI assistant call row; settings **Incident chat** (On), its answer cap and time limit, on the Incidents page, group The assistant; the incident rules of Phase 6 chapter 3 in force, including the rule for speaker labels.
- Last in the order because it should read notes (chapter 1) and confirmed people (chapter 4).

## 6. Deferred and ruled out

- **Captions burned on an Incident clip**: later, if asked.
- **A clip from a span with no event**: ruled out for now; an event is one press away and keeps the clip's reason on the chronology.
- **Notes the assistant writes**: ruled out; the office's words stay the office's.
- **Voice prints**: still Phase 5 chapter 2, deferred.
- **The wearer of a body camera by loudness**: later, once people across cameras has been measured.
- **Search across cases**: ruled out, as Phase 2 rules out anything that crosses a case's edge.

## Appendix A. Audit rows added in Phase 7

| Category | Row | Chapter |
|---|---|---|
| Cases | Event changed (a note or a mark); Incident changed (about) | 1 |
| Clips | Clip saved with cameras and layout (an Incident clip) | 1 |
| Cases | People matched; Person confirmed across cameras; Person match dismissed | 4 (outlined) |
| LLM | AI assistant call, feature `incident_chat` | 5 (outlined) |
| Cases | Events proposed gains watch_hits and windows; Event added with source watch phrase | 2 |
| LLM | AI assistant call, feature `incident_events`, gains window, look_for and cut_short | 2 |

## Appendix B. Settings added in Phase 7

| Setting | Page | Default | Chapter |
|---|---|---|---|
| Incident clips | Incidents | On | 1 |
| People across cameras | Incidents | On | 4 (outlined) |
| Incident chat; Incident chat answer cap; Incident chat time limit | Incidents | On; to be fixed; to be fixed | 5 (outlined) |
| Watch phrases | Incidents | the shipped list | 2 |
| What counts as an event | Incidents | empty | 2 |
| Proposed events window | Incidents | 600 seconds | 2 |

And, in chapter 5, the Incident chat template on the Templates page.

## Sources

The maintainer's choice of ideas and decisions of 2026-09-17, and the two mock-ups drawn the same day (the search across a case, the people section on the Speakers tab); Phase 1's Clips chapter (`app/core/clips.py`, `clip_work.py`, `media.cut_clip`); Phase 2's Cases and Case Chat chapters; Phase 6 chapters 2 to 4.

## Amendments applied

- **2026-09-19.** Chapter 2 written for the build (watch phrases, the proposer's and the memo's words), from the maintainer's finding that "I got, I got gun" went unproposed on the server; the outlined chapters move to 3, 4 and 5.
- **2026-09-17, v1.63.0 (chapter 1 built).** Decisions the build made within the chapter's rules, and two points where it read the chapter narrowly:
  - The filter graph: one chain per camera (setpts, fps 30, a scale by display aspect so an anamorphic source is not squashed, a centred pad, setsar, a bounded tpad that is the black tile before and after the camera's run, format, a drawtext for the id read from a file with no expansion), xstack with the gaps filled black, one drawtext for the clock as `pts:gmtime` with a whole-second delta normalised into the day, and the sound with silence written for a lead rather than a shifted timestamp. The tile table at every count is in `media.tile_boxes` and `docs/research/incident-clip.md`. Focus holds up to five cameras, as the row of four small tiles fixes; past five the box starts from Grid and the save refuses Focus.
  - **No Incident clock, no burned clock.** The chapter burns "the Incident clock"; on an Incident with none, Burn the clock is off and greyed ("No camera clock on this incident"), because elapsed time in hh:mm:ss would read as a time of day just after midnight. Elapsed time burned in the page's m:ss form is a later amendment if the office asks.
  - **The viewer's Clips sheet leaves Incident clips out**, so that "nothing changes in the viewer" holds: the sheet plays and adjusts one recording's own spans, and an Incident clip is listed on the case's Clips tab and the Clips page with its cameras said, with Open the incident in place of Open in viewer. Adjust is refused on an Incident clip ("An incident clip is cut from its event; make a new one to change the span."); Rename, Render again, Download and Delete are the Clips chapter's.
  - The Clip row's start and end are the span moved onto the sound camera's own clock and not clamped, so a sound camera that starts inside the span has a negative start and its excerpt and caption file stay in step with the picture; the audit rows and the pages say the span on the Incident clock.
  - The audit event stays the code's "Clip created" (the chapter says "Clip saved", an older naming gap); it carries `cameras` and `layout`.
  - The Clips page's Span and Length columns, blank since the Clips chapter (the template read fields the row did not have), now show.
  - The by-hand check on the worker (a three-camera and a nine-camera clip from ffmpeg's own test sources, the clock frame by frame, wall time and peak memory) is owed at the server upgrade and recorded in the research note when done.
  - From the build's own review: **a recording that carries an Incident clip cannot leave its case** (Move to another case refuses with "This recording carries N clips cut from an incident in this case. Delete them first, or leave the recording here."), because the file holds the other cameras' pictures and the picture their recording ids, and an Incident cannot cross a case's edge; a camera moved away afterwards fails Render again plainly. **Process again on the sound camera refuses a new clip** with the Clips chapter's words (principle 4). **The Note's writer is kept** on the Event (who last wrote the note, and when), so another person's edit of the text does not put their name on it. The Clip button shows only when one of the event's own cameras can be cut, as the chapter says.
- **2026-09-17, v1.63.1.** From the maintainer's first use: the clip mark on the event's row carries the clips' state ("1 clip, rendering", "1 clip ready", "1 clip failed") and links to the case's Clips tab, the page polling while a clip renders; on an event none of whose cameras is synced with a playback copy the Clip button shows greyed with "Sync a camera first" rather than not at all.
