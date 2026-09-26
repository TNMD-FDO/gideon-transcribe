# Gideon Transcribe, Phase 7 specification

The case as one place. Chapters 1 to 3 and 5 are written for the build; chapter 4 is outlined and takes its shape here so that the built chapters leave room for it.

## About this document

This is the build specification for Phase 7 of Gideon Transcribe. After Phase 6 (`docs/spec/SPEC-PHASE-6.md`) put the cameras of an incident in step, gave them a Chronology and had the assistant write across them, the maintainer asked on 2026-09-17 for the next ideas and chose six: a clip across cameras, people across cameras, the chronology as a document staff finish, questions answered from the incident record, a case dashboard line, and search across a case, with the instruction to "keep in mind how features may overlap and how they should relate, let's keep this smart and intuitive". This document is the answer: four chapters, each a release, that make a case one place to work in rather than a list of recordings.

One idea runs through it. **The Event is the spine.** An Event on a Chronology is already a moment every camera shares; four of the six ideas hang off it and should look and behave the same: a person's note on an event, a clip cut from an event, a question answered with events as its citations, and a person matched across cameras at the moments events are seen. The two case-level ideas, the dashboard line and the search, read everything the others produce.

Read it with the same companions as Phase 6: `CONTEXT.md` (the glossary, with the Phase 7 words Note, To check, About, Incident clip), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`, and the mock-ups the chapters were drawn from where there are any. The conventions of the Phase 1 document apply unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing leaves the building. Nothing in this document is office-specific and no new service or environment key is needed.

## What Phase 7 adds

- **The chronology as a document, and the clip across cameras** (chapter 1, for the build): each Event takes a Note in a person's own words and a To check mark; the Chronology takes an About paragraph; all of it prints in the exports and is told to the memo as the office's own words. Clip this event cuts one file from the event's cameras and span, the focus camera large or a grid, with the incident clock and the camera ids burned in, and it is a Clip like any other on the Clips page.
- **Events the office would want: the assistant's judgement, and the watch phrases under it** (chapter 2, for the build): the proposer asked to reason as an investigator and to say why each moment matters, reading a camera in windows with a second look at each so nothing is skimmed or cut short, sharpened by the office's context in a setting and a Look for box on one run; the memo re-shipped in a seasoned investigator's voice; and under the judgement one plain search for the words the office can never afford to miss, its finds shown apart. From the maintainer's finding of 2026-09-19 that a line saying "I got gun" went unproposed, and the word that the events are dynamic and the engine's reasoning is the finder.
- **The case dashboard line, search across a case, and Find on the incident page** (chapter 3, for the build): one line under the case's name with a pill for everything that has a state, each a link; a Search tab over every transcript, event, note, why, memo, summary and clip title of the case, hits grouped by where they live and every hit a time that plays or a place that opens; and Find on the incident page, where pressing a hit seeks every camera to that moment and brings the camera it was heard on to the front. From the maintainer's list of 2026-09-19.
- **People across cameras** (chapter 4, outlined): the cameras of an incident play in step, so a voice heard saying the same words at the same seconds on two cameras is one person; the app proposes the matches on the case's Speakers tab, a person confirms and names them once, and the name flows to every camera and to the case's People.
- **Gideon: the chat with a name, a place of its own, and the incident's chat** (chapter 5, for the build): the chat called Gideon on every page (a setting, so an office names its own), Ask Gideon opening a drawer beside the case, recording and incident pages, a cited moment playing in a preview under the answer, and the incident's chat grounded in the incident record with citations that play every camera and a cited line one press from an Event. From the maintainer's list of 2026-09-19 and the name chosen the same day.

## Contents

1. The chronology as a document, and the clip across cameras
2. Events the office would want: the assistant's judgement, and the watch phrases under it
3. The case dashboard line, search across a case, and Find on the incident page
4. People across cameras (outlined)
5. Gideon: the chat with a name, a place of its own, and the incident's chat
6. Deferred and ruled out

Appendices: A. Audit rows added in Phase 7. B. Settings added in Phase 7.

## 1. The chronology as a document, and the clip across cameras

Written 2026-09-17 from the maintainer's choice of ideas and the decisions taken the same day: a note per event and an About paragraph for the chronology; a clip cut from an event with the layout the person is in as its default, and both layouts on offer; the assistant never writes a note. Phase 6 chapter 2 built the Chronology and its exports; Phase 6 chapter 3 built the memo that reads it; Phase 1's Clips chapter built the single-recording Clip that this chapter's clip reuses.

### Principles

1. **The office's words stay the office's.** A Note is a person's line under an event: what it means for the case, a page cite, a thing to do. The assistant reads notes and never writes one, and a note is never mixed into the memo's text; it reaches the memo only as "the office's note" the memo must respect.
2. **A document staff finish.** The Chronology's Word export was a table of facts; with notes, marks and an About paragraph it is the working document the ask was about, and it is still made from the rows at the moment of export, nothing stored twice.
3. **A clip is an event, seen.** An Incident clip is cut from an Event: its cameras, its span, its name. A person adjusts before it is made and never types times from memory. There is no clip from nowhere: add the event first. (Amended by Phase 6 chapter 5, v1.66.0: a clip may also be cut from a span dragged on the strip, with no Event; its line then reads "from the strip".)
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

## 2. Events the office would want: the assistant's judgement, and the watch phrases under it

Written 2026-09-19, after v1.63.2, from the maintainer's finding on the server: the assistant read a camera whose record carried the line "I got, I got gun, I got gun" at 4:30 and did not propose it. The run on that six-camera incident proposed 87 events, five of its six answers cut off at the cap, most of them descriptions of the picture ("the camera view shifted to the interior of a moving vehicle"). The maintainer's words: the suggested events need to be better, the automatic events are verbatim VLM output and not useful, the memo reads too much of it and "should read like a good memo written by a seasoned investigator", and "maybe there's a way to expose these settings in the panel as well, where we can add instruction or phrases"; the gist, "if any event should auto find it's one similar to that". And, on the first draft of this chapter: the events are dynamic, and the point is "the reasoning power of the LLM to find events without explicit rules on my side". Phase 6 chapter 3 built the proposer and the memo; this chapter changes what the engine is asked for and how it is given room to think, gives the office a way to sharpen that thinking, and puts one plain search under it as a floor.

### Principles

1. **The engine's judgement is the finder.** What counts as an event cannot be listed in advance: a fragment ("I got, I got gun"), an answer that changes the case, a thing seen once. The proposer is asked to reason as an investigator reading one camera, to propose every moment that could matter to the case, and to say why each matters. It is not handed a checklist to tick; a rule the office could write down is the exception, not the mechanism.
2. **Room to think.** A camera is read in windows, one call each, so every line is read with attention and an answer has room to finish; and each window gets a second look, the engine reading it again against its own proposals for what it left out. The cut-off answers were the engine narrating the picture until the cap; short windows and a prompt that forbids narration fix both, and where an answer is still cut the page says so.
3. **One short sentence, and why.** An Event is a thing that happened, said in one plain sentence, with a line saying why it matters. "Why" is where the judgement shows: a person reads it before pressing Accept, and it keeps the engine reasoning about significance instead of describing. A description of the picture is not an event unless the picture shows one; "the camera view shifted" is never one. Fewer, shorter, better.
4. **The office sharpens the judgement; it does not replace it.** What the office knows about itself and the case (whom it defends, what tends to matter) is context that makes the engine's reasoning better, given in the panel and on one run. It is not a rulebook.
5. **A watch phrase is the floor.** Under the judgement, one plain search the app does itself: the office may list words it always wants an event for, and every line that carries one is proposed, with its source saying so. No cap, no window and no model change loses a watch phrase; and an office that lists none loses nothing of the finder. The two sources are told apart on the page, so the office can see what the judgement found and what the search did.
6. **The memo is an investigator's.** It reads as a seasoned investigator writes: what happened, who did what, where the cameras and the words are the evidence for it, said plainly and grouped by subject; the picture is described only where the picture is the evidence.
7. **What was, stays.** Propose, never apply; the office's Events first; every proposal rests on a real line; a numbered speaker label is one camera's alone; nothing the assistant proposes reaches the Chronology unaccepted. Chapter 3 of Phase 6 stands under this chapter.
8. **Measured before shipped.** The rewritten prompt is run over the camera that missed the line, on the maintainer's server, before the build is called done: what it proposes, whether the line is among them, and how many descriptions remain. The numbers go in `docs/research/event-spotting.md`.

### Words

**Why it matters**, the line under a proposal that gives the engine's reason. **About this office and case**, the office's context for the proposer, a setting; **Look for**, the box on one run. **Watch phrase**, as `CONTEXT.md` defines it from this chapter: a word or phrase the office always wants an event for, listed in the panel, found by the app's own search; **Watch phrases** is the setting. An Event found by a watch phrase has the source **watch phrase** ("Watch phrase: gun, on BWC2-098702"). The pages never say keyword, trigger, alert, hotword, rule, or score.

### The proposer's judgement

- **The ask**, the shipped wording of the Proposed events template rewritten: you are an investigator reading one camera of an incident for the office that defends the accused; propose every moment that could matter to the case, a thing that happened that a member of staff would put on the chronology and could point to in the record, and for each say in one line why it matters. Judge significance yourself: a fragment can matter ("I got, I got gun"), an answer can matter more than the question, a thing seen once can matter. To help the judgement, and not to bound it, moments that usually matter include: a person or a vehicle arriving, leaving or being stopped; a command, a warning or an advisement of rights; a question about consent or a search and its answer; a search, a restraint, a use of force, a weapon drawn, shown or mentioned, an injury, an arrest as the words or the picture describe it and never as a conclusion; a statement that carries weight, an admission, a denial, a threat; a thing handed over, found, seized or taken; a move to another place; a person or a vehicle identified; the camera starting, stopping or being muted. It is not: the picture changing, the camera moving, a vehicle driving with nothing happening, weather, scenery, a description of clothing or surroundings on its own, or small talk. One sentence each, plain words, third person, past tense, up to 120 characters, saying what happened and not what it means, never beginning "the camera" or "the view"; then why it matters, one line, up to 160 characters. A numbered speaker label is this camera's alone. Nothing already on the list given; only what this camera adds; every proposal rests on a line given, copied after it. The template stays editable and resettable on the Templates page.
- **Why it matters** is a field of the answer and of the proposal, saved with it, shown under the proposal's line on the page and on the lane's hover, and printed in the exports for an accepted Event with source assistant ("why it matters, in the assistant's words: ..."). It is never written into the Event's own line.
- **The office's context.** **About this office and case** is a setting on the Incidents page, under The assistant: a text box, empty by default, greyed while Assistant proposes events is Off, up to 2,000 characters. Its text is given to every run after the template as "About the office and its cases:" so an office tells the engine what it knows ("a public defender's office: what an officer said about why a stop was made, every question before rights were read, and every mention of a weapon matter most") and the engine reasons with it. Context, not rules; the template is not edited.
- **Look for, on one run.** Beside Propose events a small box, **Look for**, empty each time the page opens, up to 300 characters: "anything about the gun and the ring camera". Its text is given to that run alone as "For this run the office asks you to look for:". Never stored past the run; the audit row records that a Look for was given, never its words.
- **In windows.** A camera's record is read in windows of **Proposed events window** (600 seconds of the recording; 120 to 1,800), one call per window in time order, each call given the Events and the proposals so far. The answer cap stays per call, so a window has room to answer in full; the app keeps up to twelve proposals a window and drops the rest, which is still fewer than an answer cut mid-list. A camera of 47 minutes is five calls where it was one.
- **The second look.** After a window's answer is checked, one more call on the same window: the lines again, the proposals it made, and the ask "read it again against what you proposed; what did you leave out that an investigator would want, and why?", the same shape of answer, the same checks. What it adds joins the window's proposals (the twelve-a-window ceiling counts both). **Second look** is a switch (On; greyed while Assistant proposes events is Off) because it doubles the calls; a camera of 47 minutes is ten calls with it on.
- **Cut short, said so.** When an answer is still cut at the cap the state line says it ("Proposed 14 events at 14:02; 1 answer was cut short, raise Proposed events answer cap"), the run's Details fold for an Admin lists the windows and which were cut, and the audit row counts them as it does.

### Watch phrases, the floor

- **Under the judgement, not instead of it.** Everything above is the finder. The search below catches what the office has decided in advance it can never afford to miss, and shows its finds apart from the engine's, so the office can see which is which. An office may empty the list.
- **The setting.** **Watch phrases** on the Incidents page, under The assistant: a text box, one phrase per line, shipped with the list below, greyed while Incidents is Off. Editable and resettable to the shipped list as a template is. A phrase is one to six words; case does not matter; a phrase matches whole words only ("gun" matches "gun" and "guns", never "begun"); a line that is empty or a duplicate is dropped when saved; up to 200 phrases.
- **The shipped list**, one line each: gun, firearm, pistol, rifle, shotgun, knife, weapon, armed, shoot, shot, shots fired, taser, tase, pepper spray, mace; stop resisting, get on the ground, hands behind your back, I can't breathe, not breathing, ambulance, bleeding, medic, use of force; you're under arrest, you are under arrest, right to remain silent, Miranda, understand your rights, lawyer, attorney, I want a lawyer, I don't want to talk; can I search, mind if I search, consent, search warrant, warrant, probable cause, step out of the vehicle, open the trunk; I did it, it was me, going to kill, I'll kill, threatened; drugs, narcotics, fentanyl, meth, cocaine, marijuana, weed, stolen; identification, licence, license, registration. An office edits it to its practice; the first office's own list stays in its planning repository, never here.
- **The search.** On every Propose events run, before any engine call and whether or not the AI assistant is On: each synced camera's transcript lines and, where the camera has a Digest, its picture lines (the "seen" lines), read by the app for every watch phrase. Every line that carries one becomes a proposal at the line's time, with source watch phrase, the phrase, the camera, and the line as what it rests on: "Watch phrase "gun": I got, I got gun, I got gun." (a picture line: "Watch phrase "gun", seen: a handgun on the passenger seat"). A phrase heard again on the same camera within thirty seconds joins the first proposal ("said three times") rather than making another. The checks of Phase 6 chapter 3 apply: nothing within five seconds of an Event or a proposal already on that camera, nothing a person dismissed. The hits are saved as they are found, so the page shows them before the engine has answered.
- **On the page.** A watch-phrase proposal lists under Proposed by the assistant with the others, oldest first, its source pill reading **Watch phrase** with the phrase, and the same Accept and Dismiss. Accepted, the Event keeps the source watch phrase, prints in the exports as "from the watch phrase "gun" on BWC2-098702", and does not by itself put the AI notice on an export, because the app's search is not the assistant. On the strip's Events lane it is drawn as any proposal.
- **With the assistant Off.** Propose events shows while Incidents is On and either Assistant proposes events is On or the Watch phrases list is not empty; with the assistant Off or unreachable the run is the search alone and the state line says "Searched 6 cameras for 52 watch phrases: 3 found". So an office with no engine still gets the promise.
- **Told to the engine.** The engine is told the list ("The office watches for these words and phrases; every line that carries one is an event") and, as the earlier cameras' proposals are, the hits already found, so it neither misses nor doubles them.

### The memo's words

- **The Incident memo template's shipped wording is rewritten** to the voice asked for: a memo a seasoned investigator writes for the attorney on the case. It says what happened, who did what and what was said, in the order it happened, grouped by subject inside What happened, and it points at the evidence: the time of day, the camera, the event's number. It never narrates the picture ("the camera view shifted", "the footage shows") and describes what a camera showed only where the picture is the evidence for a fact ("a handgun lay on the passenger seat, BWC2-098702 at 21:58:10"). It uses the Chronology's events as the spine and the office's notes as the office's reading, and it stops at the facts. The parts and their order are unchanged (Summary; The cameras; People; What happened; Commands, warnings, and rights; Statements that matter; Names, places, and dates; Unclear parts), so nothing built on the shape changes.
- **The incident record it is written from** is unchanged, and so are its citations, the stale rule, the export and the settings. A memo written before this chapter stays as it is until Regenerate.
- **Speaker names in the memo** are out of this chapter, at the maintainer's word (2026-09-19: "let's deal with this more when this part of the plan is up for discussion"). The rule of Phase 6 chapter 3 stands: a numbered label is one camera's alone, and a line is attributed to a person only by a name the words give or the office set.

### In and out

- **In**: the run in windows with the second look and the cut-short line; the why line on every proposal and in the exports; the About this office and case, Second look, Proposed events window and Watch phrases settings; the Look for box; the search on every run and its proposals with the source watch phrase; the two templates' shipped wording rewritten; Propose events with the assistant Off while phrases are listed; the measurement in `docs/research/event-spotting.md`.
- **Out**: phrases as patterns (regular expressions), phrases matched on the sound rather than the words, a run by itself when a transcript lands (Phase 6 chapter 3's "Not in this phase" stands), accepting the sure ones automatically, and names across cameras.

### What changes from Phase 6 and earlier phases

- **Phase 6 chapter 3, Proposed Events**: the run gains the windows, the second look, the why line, the office's context and the Look for, and the search first; the shipped Proposed events template's wording is replaced by this chapter's; the state line gains the cut-short words; Propose events shows with the assistant Off while phrases are listed. **The Incident memo**: the shipped Incident memo template's wording is replaced by this chapter's; nothing else.
- **Phase 6 chapter 2, Events**: the Event gains a why (the assistant's reason, blank for a person's Event), shown on the proposal and printed in the exports for an accepted assistant Event; the source **watch phrase** joins person, quote, camera and assistant, on the page, on the lane, in the exports and in the events' JSON; the Word export's AI notice line prints for source assistant as before and not for source watch phrase.
- **Phase 4 chapter 7, The templates**: the two templates are re-shipped; an office that edited either keeps its edit and sees "Reset to the shipped wording" as before.
- **Phase 4 chapter 8**: the AI assistant call with feature `incident_events` gains the window's number and count, whether a Look for was given, and the count of watch-phrase hits; the never-logged list gains the watch phrases' hits, the Look for's words and the office's instructions.
- The Case Chat, the memo's citations and export, the clips, the notes and the strip are unchanged.

### Audit rows

Category Cases: **Events proposed** gains `watch_hits` and `windows`. Category LLM: **AI assistant call** with feature `incident_events` gains `window` (n of m), `pass` (first or second look), `look_for` (given or not) and `cut_short`. Category Admin: the settings' rows as every setting has them; a change to Watch phrases records the count before and after, never a phrase. None holds a phrase, a hit, a line or the Look for's words.

### Settings

On the Incidents page, under The assistant: **About this office and case** (empty; greyed while Assistant proposes events is Off); **Proposed events window** (600 seconds; 120 to 1,800; greyed while Assistant proposes events is Off); **Second look** (On; greyed while Assistant proposes events is Off); **Watch phrases** (the shipped list; greyed while Incidents is Off). The rows join `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` and Appendix B.

### Not in this chapter

- **Phrases as patterns**, and phrases by category with a colour each: a list of words is what the office asked for; the rest waits until an office has used it.
- **The search on the whole case** (every transcript, not the incident's cameras): that is chapter 3's search across a case, which will offer "make an event of this hit" on an incident's camera.
- **A run by itself** when a camera's transcript lands, and **accepting the sure ones automatically**: as Phase 6 chapter 3 left them.
- **Speaker names across cameras**: Phase 7 chapter 4, and the maintainer's discussion before it.

### Left to the build

- The whole-word rule's edges (apostrophes, hyphens, a phrase across a line break, the plural), within the rule that "gun" never matches "begun".
- The join window for a phrase heard again (thirty seconds) and the words of the joined proposal.
- The twelve-a-window ceiling and the order in which surplus items are dropped (the later ones).
- The exact wording of the rewritten templates and of the second look's ask, within the substance above, and of the state lines.
- Where the why line prints in the Chronology's Word export (under the line, in the assistant's words), within the rule that it is never mixed into the Event's own line.
- Whether the Look for box sits beside the button or opens from it on a narrow window.

## 3. The case dashboard line, search across a case, and Find on the incident page

Written 2026-09-19, after v1.64.0, from the shape decided on 2026-09-17 and three items of the maintainer's list of 2026-09-19: "search feature may need its own tab, seems like it is out of place on top of the recordings section in a case"; "add search ability in incidents that will dynamically position videos to the selected search finding"; and the dashboard line as the outline had it. Phase 2's Cases chapter built one search box over a case's transcripts and speaker names; Phase 6 built the incident page and its strip; this chapter gives the case one line that says where everything stands, one tab that searches all of it, and the incident page a way to find a moment and have every camera go there.

### Principles

1. **One line says where the case stands.** Everything in a case that has a state (a video transcribing, a video waiting for tonight's vision, an incident not synced, an event to check, a memo with newer events, a clip rendering, a share, a retention clock about to run out) shows as one pill on one line under the case's name, and each pill is a link to where it is dealt with. Nothing pending shows nothing, not a pill saying so.
2. **One search over everything in the case.** A tab of its own, because a search box above the recordings list looked like part of that list. It reads the words of every transcript, the events of every incident with their notes, their whys and their About, every memo, every summary and every clip's title, and shows the hits by where they live, every hit a time that plays or a place that opens.
3. **A hit on the incident page moves the cameras.** Find, on the incident page, is search with the cameras as its answer: type a few words, and each hit is a moment on the incident clock; press it and every camera seeks there, the camera it was heard on comes to the front with the sound. A person finds "gun" and watches every camera at the second it was said.
4. **Nothing is logged, nothing is stored.** A search term and a Find are never written to the audit log, as Phase 2 has it, and nothing of a search is kept past the page.
5. **Built from what the pages already count.** The line is drawn from the counters the pages already compute; the search extends Phase 2's query to more tables; Find reads the lines the incident page already serves. No new setting; no new audit row.

### Words

**Dashboard line**, as `CONTEXT.md` defines it from this chapter: the line of pills under a case's name. **Search**, the case page's tab and its box; a **hit**, one match, and where it lives (a recording's line, an event, a memo, a summary, a clip). **Find**, the box on the incident page, and its hits as moments. The pages never say dashboard (the line has no heading), status bar, alerts, results, or query.

### The dashboard line

- **Where.** Under the case's name and above the tabs, on every tab of the case page, one line of pills that wraps on a narrow window. Absent when nothing has a state.
- **The pills**, in this order, each shown only when its count is not zero, each a link, each with the count and plain words:
  - **Transcribing**: recordings whose Job is running or in line ("2 transcribing", "1 in line, about 20 minutes", the waiting words of `waiting.py`); links to the Recordings tab, which already refreshes its rows.
  - **Preparing**: recordings being prepared for summaries and chat, or enriched with vision now ("1 preparing"); links to the Recordings tab.
  - **Tonight**: videos marked for tonight's vision ("3 enriched tonight from 20:00"), from `vision.line`'s figures; links to the Recordings tab.
  - **Not synced**: incidents with a camera not yet synced ("1 incident not synced"); links to the Incidents tab.
  - **To check**: events marked To check across the case's incidents ("4 events to check"); links to the Incidents tab, whose lines already carry each incident's count, and from there to the incident's Chronology.
  - **Proposals**: proposals waiting to be accepted or dismissed ("6 proposed events waiting"); links to the Incidents tab.
  - **Memo**: memos with newer events ("1 memo has newer events") and memos being written ("1 memo writing"); links to the Incidents tab.
  - **Clips**: clips rendering ("2 clips rendering") and clips that failed ("1 clip failed"); links to the Clips tab.
  - **Shared**: whom the case is shared with ("shared with 2"); links to the pane's Sharing.
  - **Deletes**: the retention warning ("deletes in 12 days"), in the warning tone the pane's line already uses; links to the pane's Keep.
- **Tones.** A pill is plain, working (transcribing, preparing, rendering, writing), or warning (not synced, to check, failed, deletes), with the app's pill classes; no new colours.
- **Refresh.** Drawn on the server with the page. On the Recordings tab, where the page already asks for its rows while a video is prepared (v1.53.2), the line is asked for with them and redrawn; on the other tabs it is as fresh as the page.
- **The Cases page.** Unchanged: the case row keeps its own words. The line is the case page's.

### Search across a case

- **The tab.** **Search** is the second tab of the case page (Recordings, Search, Clips, Speakers, Chat, Incidents), offered to whoever can open the case. The Recordings tab loses the search box; a `?q=` on the case URL opens the Search tab with the term, so Phase 2's links keep working.
- **The box.** One box, "Search this case", with the term kept in the URL as `?tab=search&q=` so a search can be shared as a link within the office. Words all present, any case, any order ("gun backpack" finds a line with both); a phrase in quotes exactly ("I got gun"). A term shorter than two characters searches nothing. **Clear** empties it.
- **What it reads**, each kind counted and offered as a filter above the hits (Words, Events, Notes, Memos, Summaries, Clips), a filter showing only when its count is not zero:
  - **Words**: every Segment of every transcript in the case, its text and its speaker name, as Phase 2 had it.
  - **Events**: every Event of every incident in the case (not proposals): its line, its why, and the office's About of each Chronology.
  - **Notes**: the notes on events, with the writer's name.
  - **Memos**: every Incident memo, paragraph by paragraph.
  - **Summaries**: every recording's Summary, paragraph by paragraph.
  - **Clips**: every clip's title in the case, incident clips included.
- **The hits**, grouped by where they live (a recording, an incident), the groups in the case's order, the hits in time order within a group, the matched words marked:
  - A **Words** hit: the recording's title (once, as the group's head), the time as a citation that opens the viewer at that line, the speaker, the line. When the recording is a synced camera of an incident, an **all cameras** link beside the time opens the incident page at that moment, as Phase 6 chapter 1's link does.
  - An **Events** hit: the incident's name as the group's head, the event's time of day opening the incident page at that moment, the line, the why under it, the source pill. An About hit shows as the incident's About.
  - A **Notes** hit: under its event, in italics, with the writer.
  - A **Memos** hit: the incident's name, "Memo", the paragraph with the words marked, opening the Memo tab with that paragraph lit.
  - A **Summaries** hit: the recording's title, "Summary", the paragraph, opening the recording's Summary tab with the paragraph lit.
  - A **Clips** hit: the clip's title, its recording or its incident, opening the Clips tab at that clip.
- **How many.** The first two hundred hits of each kind, then "and N more; narrow the words". Never logged; never stored.
- **Speed.** The build measures the case-wide `icontains` over segments, events, memos and summaries on the office's largest case and, if a search takes more than a second there, adds a PostgreSQL trigram index on the segments' text (`pg_trgm`, in the database image already) and records the figures in `docs/research/case-search.md`. The search never leaves the office's database.

### Find on the incident page

- **Where.** A box in the incident page's work panel head, **Find**, beside the tab bar, on every layout; on a narrow window it is a magnifier that opens the box.
- **What it reads.** The lines of every synced camera (the transcript lines the page already serves per camera, at their times on the incident clock), the Chronology's events with their notes and whys, and the memo's paragraphs. A camera not yet synced is not read, and the box says "1 camera not synced is not searched" when one is skipped.
- **The hits**, under the box in a list that scrolls, in time order on the incident clock: the time of day, the camera's dot and id (or "Event", "Memo"), the line with the words marked; the count above ("7 moments for "gun"").
- **A hit moves the cameras.** Pressing a hit seeks every camera to that moment (Phase 6 chapter 1's seek), brings the camera it was heard on to the front in Focus (or scrolls it into view in a grid) and gives it the sound, and marks the hit as the one being watched; the page's playhead and the strip follow as they do for any seek. Playing is not started or stopped by a Find. Enter in the box goes to the next hit, Shift+Enter to the one before, Escape clears. An Event hit seeks there and shows the event on the Chronology tab; a Memo hit seeks there and lights the paragraph.
- **From a hit to an event.** Each Words hit has **E** (the page's key for an event at the moment being watched) as a small button, which opens the event box at that moment with the line filled and the camera ticked, as adding from a line under a camera does. Nothing is added until the person saves it.
- **Never logged, never stored.** The term stays in the box until cleared or the page is left.

### In and out

- **In**: the dashboard line with its ten pills and its refresh on the Recordings tab; the Search tab with its six kinds, its filters, its grouping and its links; Find on the incident page with its hits, its seek, its keys and its E; the `?q=` compatibility; the speed measurement.
- **Out**: search across all cases (Phase 2's rule stands), ranking by relevance, search inside documents (PDFs are a later phase), saved searches, a search of the audit log (it has its filters), and a Find across incidents.

### What changes from earlier phases

- **Phase 2, the Cases chapter, Search inside one Case**: the box moves from the Recordings tab to a Search tab and reads six kinds, not two; the rule that the term is never logged stands; `?q=` on the case URL opens the Search tab.
- **Phase 2, the case page's head**: the dashboard line under the name; the Recordings tab's rows request carries the line.
- **Phase 4, the Summary**: a Summary tab opened with a paragraph to light, from a hit; the Memo tab the same.
- **Phase 6 chapter 1, the Incident page**: Find in the work panel's head; a seek that brings a camera to the front with the sound (the Focus layout's press on a tile, done by the page).
- **Phase 6 chapter 2 and Phase 7 chapter 1**: an event's line, note, why and the About are read by the search; the incident page's `?at=` opens at a moment and, with `&event=`, on that event.
- **Phase 7 chapter 1, Incident clips**: a clip's title is read by the search; the Clips tab opens at a clip.

### Audit rows

None. A search and a Find are never logged; the counters the line reads are the pages' own.

### Settings

None. The line, the tab and Find are part of the case and the incident page, on whenever Cases (and, for the incident parts, Incidents) are.

### Not in this chapter

- **Ranking and full text.** Hits are in time order within their group; there is no score. The trigram index is a speed measure, not a ranking.
- **Search across cases**, **saved searches**, and **a search of the app's own guides**.
- **Documents in a case** (PDFs with page citations): a phase of its own, on the maintainer's list.
- **People to confirm** on the line: chapter 4's, added with it.

### Left to the build

- The pills' exact words and the order of two pills of the same tone, within the list above.
- The hit ceiling per kind (two hundred) and how "more" narrows.
- The phrase rule's edges (quotes inside a term, a lone quote).
- Whether Find's hit list sits under the box or as a fold of the panel, and its length before it scrolls.
- How a lit paragraph is found in a Summary or a memo (the paragraph's index in the text as stored).
- The trigram index, only if the measurement calls for it.

## 4. People across cameras (outlined)

Not yet written for the build; the shape decided on 2026-09-17, with the mock-up of the same day: the proposals live on the case's Speakers tab, never on the incident page beyond a one-line pointer.

- **The match.** The cameras of an incident are in step, so a voice saying the same words during the same seconds on two cameras is one person. For every pair of synced cameras with transcripts, the app lines up their segments on the Incident clock, folds the words (case, punctuation), and counts the pairs of lines that overlap in time and share most of their words; for each speaker label on one camera the label on the other with the most such lines, when there are at least three and no rival label has half as many, is proposed as the same person, and the proposals chain across cameras into one person seen on several. A label already a name on one camera carries its name into the proposal. No engine call; the media worker or the app itself runs it when the incident's sync changes or a transcript lands, and on a press.
- **On the Speakers tab** of the case page: a section "Same person on several cameras" above the case's speakers, one row per proposed person naming each camera's label, the count of matching moments with one example as a citation that plays every camera, a name field (filled when one camera already has a name), **Confirm** and **Not the same**. Confirm renames the label on every camera through the viewer's own speaker rename (the same audit row, the same undo) and joins the case's People, so the name reaches the memo, the proposals, the chat and the words under the tiles. Not the same puts the proposal away and it is not offered again for those labels.
- **On the incident page**, the Cameras tab shows one line while proposals wait: "3 people to confirm on the case's Speakers tab", a link.
- **The probe first.** As with the sound match, the build runs the match on one of the office's real incidents by a management command and records the counts in `docs/research/people-across-cameras.md` before the thresholds are fixed. Voice prints (Phase 5 chapter 2) stay deferred; the wearer of a camera by loudness is left to a later chapter.
- **Rows and settings**: category Cases, **People matched** (count, cameras), **Person confirmed across cameras** (as Speaker changed on each recording, with how: cameras), **Person match dismissed**; setting **People across cameras** (On) on the Incidents page, group The assistant, though it makes no engine call.

## 5. Gideon: the chat with a name, a place of its own, and the incident's chat

Written 2026-09-19, after v1.66.0, from three items of the maintainer's list of the same day: "let's find a way to make chat something more special. I think we should give the Chat a cool name as it relates to the office. Still need to respect boundaries as they are, no chatting across cases, etc. Just need chat to stand out from the basic tab it sits in now"; "when a video or anything else is cited, when the user selects the source, maybe it could play that in a preview, that way it doesn't have to load into another page"; and the name chosen the same day: **Gideon**. The chapter also takes in the outlined incident chat (questions answered from the incident record), so one chapter covers the chat wherever it is asked. Phase 1 built the chat on a transcript, Phase 2 the Case Chat, Phase 4 the chat's shape (`chat-ui.js`); Phase 6 chapter 3 told the Case Chat the placements.

### Principles

1. **One name, and the name is a setting.** The chat is called Gideon on every page: the tab, the button, the drawer's head, the export's title. The name ships as an Appearance setting, **What the chat is called**, with Gideon as its default, so an office that pulls the app calls its chat what it likes; the glossary's word stays Chat, in code, in settings and in the audit log. Gideon the chat is the app's; GIDEON the engine is the office's other project, and the guide says so once.
2. **A place of its own.** Gideon is not a tab among tabs. A button, **Ask Gideon**, sits at the bottom right of the case page, the recording page and the incident page, and opens a drawer beside the page, so a person asks while reading and the answer sits next to the transcript, the events or the cameras it cites. The Chat tabs stay, showing the same conversations, so nothing built is lost and a wide window can keep both.
3. **A cited moment plays where you are.** Pressing a citation in an answer plays that moment in a small player under the answer, with the line being spoken, and offers Open for the full page. On the incident page the cameras are the preview: a citation seeks every camera there.
4. **The boundaries stand.** Gideon on the case page reads that case and nothing else; on the recording page that recording; on the incident page the incident's record. No chat across cases, no chat outside the words the app holds, the same refusals, the same AI notice on every export, the same audit rows.
5. **The incident's Gideon reads the record.** Asked from the incident page, Gideon answers from the incident record (the cameras' Digests merged onto the Incident clock), the Chronology with its notes and About, and, when chapter 4 lands, the confirmed people; every time in an answer is a citation that plays every camera, and a cited line is one press from becoming an Event.

### Words

**Gideon**, the chat's name as shipped (the setting's default), used on the pages wherever they said Chat: **Ask Gideon** (the button), **Gideon** (the tab, the drawer's head), "Gideon says" nowhere (answers carry no speaker label, as today). **The drawer**, the panel Ask Gideon opens; **the preview**, the small player under an answer. In code, settings, exports' file names and audit rows the word stays Chat, Case Chat, Incident chat. The pages never say bot, assistant as a name, AI as a name, or the engine's name.

### The name

- **What the chat is called**, on the Appearance page: text up to 30 characters, shipped "Gideon", greyed while Chat is Off. Empty falls back to "Chat".
- **Where it shows.** The Chat tab on the case page and on the recording page reads the name; the Ask button reads "Ask <name>"; the drawer's head reads the name with the page's grounding under it ("this case", "this recording", "this incident"); the Word export of a conversation is titled "<name>: <the first question>" and its file named as today; the AI notice keeps its wording ("AI assistant"), because it says what the thing is, not what it is called.
- **Nothing else changes** with the name: the settings' names, the audit rows, the guides' headings (which say "the chat, called Gideon in the app" once).

### The drawer

- **Ask Gideon**, a round button at the bottom right of the case page (every tab), the recording page and the incident page, while the chat that page grounds is On (Chat for a recording, Chat across cases for a case, Incident chat for an incident) and the engine is reachable; greyed with the reason otherwise, as every withheld control is.
- **Opens a drawer** on the right, a third of the window and at least 380 pixels, the page's content narrowing beside it; under 900 pixels the drawer takes the whole window with a Back. Inside: the head (the name, the grounding, Close), the conversations of this page's grounding as `chat-ui.js` lists them (folded to the current one, with New conversation and the list), the answers above and the question box at the bottom, the starters when the conversation is empty, Export to Word on the conversation, everything the Chat tab has.
- **Stays with the reader.** The drawer keeps its state across the page's tabs and across a reload of the same page; open or closed is remembered per person per page kind (browser storage). Escape closes it; the button opens it again where it was.
- **The tabs stay.** The case page's Chat tab and the recording page's Chat tab show the same conversations in the tab's own width; a conversation begun in one continues in the other. The Memo tab of the incident page gains no chat section: the drawer is the incident's chat.

### The preview

- **A citation pressed** in an answer, in the drawer or on a Chat tab, plays the moment in a preview under that answer: a small player of the recording's playback copy from ten seconds before the citation, the line being spoken under it as the viewer's stage shows it, the recording's title, and **Open** (the viewer at that moment; on a synced camera also **All cameras**, the incident page at that moment). One preview at a time; pressing another citation moves it. The page's own player, on the recording page, pauses while the preview plays.
- **On the incident page** a citation seeks every camera to the moment and brings the camera it was heard on to the front with the sound, as Find does; no preview player, the wall is the preview.
- **A memo or summary citation** (a paragraph, not a moment) opens the tab with the paragraph lit, as the Search tab's hits do.
- **The preview is the same playback copy** the viewer plays, reached by the same media route; nothing is cut or copied.

### The incident's Gideon

- **Grounding.** Asked from the incident page, Gideon reads the incident record as the memo does (Phase 6 chapter 3: every synced camera's Digest with times rewritten to the Incident clock, a camera with no Digest read from its transcript while it fits, the longest dropped to a line first and the answer saying so), the Chronology as the office wrote it with its notes and About, and nothing else. A camera not synced is named as left out.
- **The template** Incident chat on the Templates page, shipped in the investigator's voice of chapter 2: answer from the record and the chronology, cite every time as `[hh:mm:ss]` on the Incident clock, name a camera by its id, never narrate the footage, never a legal conclusion, decline what the record does not hold. The incident rules of Phase 6 chapter 3 in force, the speaker-label rule included.
- **Citations** are `[hh:mm:ss]` on the Incident clock; each plays every camera from there. Beside a cited line, **+ event** opens the event box at that moment with the line filled and the camera it names ticked; nothing is added until saved.
- **Conversations** belong to the Incident (deleted with it, into the Recycle bin with the case and back), listed in the drawer as the case's are, exported to Word with the Chronology's cover line, under the audit row Chat exported.
- **The call**: the engine's lane, feature `incident_chat`, thinking as the switch says, capped at **Incident chat answer cap** (2,000 tokens), within **Incident chat time limit** (300 seconds, doubled while the model may think). The audit row is the AI assistant call with the cameras drawn on and whether it was cut; never a word.
- **Settings**: **Incident chat** (On; greyed while Incidents or the AI assistant is Off), **Incident chat answer cap**, **Incident chat time limit**, on the Incidents page under The assistant.

### In and out

- **In**: the name setting and the name on the pages; the Ask button and the drawer on three pages; the preview under an answer; the incident's Gideon with its template, its citations, + event, its conversations and its settings.
- **Out**: chat across cases (Phase 2's rule), a drawer on the Start page or the Clips page, the chat by voice, a preview that cuts a clip, and an answer that changes the Chronology by itself.

### What changes from earlier phases

- **Phase 1, the chat; Phase 2, the Case Chat; Phase 4 chapter 4, the chat's shape**: the name on the tabs and the export's title; the drawer beside the page; the preview under an answer. The conversations, the grounding, the refusals, the starters, the exports and the audit rows are unchanged.
- **Phase 4 chapter 7, The templates**: the Incident chat template joins the Templates page.
- **Phase 4 chapter 8**: the AI assistant call gains the feature `incident_chat`; the never-logged list gains its questions and answers.
- **Phase 6 chapter 1, the Incident page**: the Ask button and the drawer; a citation seeks every camera. **Chapter 3, the Memo tab**: unchanged; the drawer is the incident's chat.
- **Phase 7 chapter 3, Find**: the seek that brings a camera to the front is shared with the citations.
- **`docs/spec/ADMIN-SETTINGS-CATALOGUE.md`**: the four rows.

### Audit rows

Category LLM: **AI assistant call** with feature `incident_chat` (the cameras drawn on, whether cut). Category Cases: the Chat rows as they are (Chat created, Chat exported, Chat deleted) with the Incident as the object for the incident's conversations. Nothing holds a question, an answer or the name.

### Settings

**What the chat is called** (Appearance; "Gideon"). **Incident chat** (On), **Incident chat answer cap** (2,000 tokens), **Incident chat time limit** (300 seconds), on the Incidents page under The assistant. The rows join the catalogue and Appendix B.

### Not in this chapter

- **Confirmed people in the incident's grounding**: chapter 4's, added with it.
- **A chat that runs by itself** (a digest of the day, a question asked overnight).
- **The drawer on the Cases list and the Start page**: there is nothing to ground it in.

### Left to the build

- The drawer's exact width and the breakpoint, the button's place on a narrow window, and how the remembered state is keyed.
- The preview player's size and whether it shows the picture or the sound alone for an audio recording.
- The Incident chat template's exact wording within the substance above.
- Whether the incident's conversations show on the case page's Chat tab under the incident's name (the build may list them there, read-only, or leave them to the incident page).

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
| LLM | AI assistant call, feature `incident_chat`; Cases: the Chat rows with the Incident as the object | 5 |
| Cases | Events proposed gains watch_hits, windows and second_looks; Event added with source watch phrase | 2 |
| LLM | AI assistant call, feature `incident_events`, gains window, pass, look_for and cut_short | 2 |

## Appendix B. Settings added in Phase 7

| Setting | Page | Default | Chapter |
|---|---|---|---|
| Incident clips | Incidents | On | 1 |
| People across cameras | Incidents | On | 4 (outlined) |
| What the chat is called | Appearance | Gideon | 5 |
| Incident chat; Incident chat answer cap; Incident chat time limit | Incidents | On; 2,000 tokens; 300 seconds | 5 |
| About this office and case | Incidents | empty | 2 |
| Proposed events window | Incidents | 600 seconds | 2 |
| Second look | Incidents | On | 2 |
| Watch phrases | Incidents | the shipped list | 2 |

And, in chapter 5, the Incident chat template on the Templates page.

## Sources

The maintainer's choice of ideas and decisions of 2026-09-17, and the two mock-ups drawn the same day (the search across a case, the people section on the Speakers tab); Phase 1's Clips chapter (`app/core/clips.py`, `clip_work.py`, `media.cut_clip`); Phase 2's Cases and Case Chat chapters; Phase 6 chapters 2 to 4.

## Amendments applied

- **2026-09-25, v1.90.0.** From the maintainer's walk of the outputs as a defender would read them. Chapter 3's Incident memo template is re-shipped in the investigator's voice of the office's own body camera template: the working kept out, no speaker lists or labels, an unnamed officer named by the camera worn or as Officer A and B, phases with their spans of the clock, Questioning and rights, Searches, seizures and force, Gaps and unclear parts, and Points for counsel as questions with no cases cited, eight at most; the memo of v1.61.0 that ended at the facts is superseded, because the office's own template had shown what its attorneys want on the page and the questions are marked as questions. The cameras part is the app's. Chapter 5's incident chat gives a timeline in time order, one moment a line with its own unrounded time, Camera: on a line from the picture.
- **2026-09-25, v1.89.0.** From the walk of v1.88.0: chapter 3's Search matches plain words as whole words ("car" no longer lights the middle of "scared"); a phrase in quotes stays an exact match. Chapter 5's incident chat has its own starter questions (a Templates setting, two shipped). Chapter 3's memo prints The cameras from the app's own record of the cameras rather than the model's words (a memo once wrote an id with a space in it), each camera's kind, its span as citations, and how it was read.
- **2026-09-25, v1.87.0.** Chapter 3's dashboard line: "proposed events waiting" joins the pills in the warning tone (not synced, to check, newer events, failed, deletes), because proposals wait for a person's accept or dismiss and Home's Needs you (Phase 8 chapter 13) is drawn from that tone.
- **2026-09-24 (Phase 8 chapter 11, v1.81.0).** A Note on an Event: a note event (the office's note on a synced camera's line, an Event by itself) has no note of its own; its text is the note.
- **2026-09-19, v1.67.0.** Chapter 5 built the same day, with these decisions left to the build: the drawer is a third of the window and at least 380 pixels, the whole window under 900, its state keyed per kind of page in the browser's storage; on the recording page the drawer takes the page's Chat panel in (one conversation list, one poll) and gives it back on Close, while the case and incident pages mount their own; the preview is a player of the playback copy under the answer from ten seconds before, the picture for a video and the sound alone for an audio recording, one at a time, with Open and All cameras; a citation on the incident page seeks every camera and starts them playing; the incident's conversations are the Case Chat's rows with the Incident set, listed on the incident page alone and never on the case's Chat tab, and their export prints an incident citation as its time; the AI assistant call row for the incident chat carries the cameras read and whether the answer was cut; + event on an incident citation is carried by the shared chat's onPlus hook and opens the event box with the line filled.
- **2026-09-19.** Chapter 5 written for the build (Gideon: the name as a setting, the drawer, the preview, the incident's chat), from the maintainer's list of 2026-09-19 and the name chosen the same day; it takes in the outlined incident chat.
- **2026-09-19, v1.65.0.** Chapter 3 built the same day, with these decisions left to the build: the pills read "2 transcribing", "1 in line", "1 preparing", "3 videos enriched tonight from 20:00", "1 incident not synced", "4 events to check", "6 proposed events waiting", "1 memo writing", "1 memo has newer events", "2 clips rendering", "1 clip failed", "shared with 2", "deletes in 12 days", the warning tone on not synced, to check, newer events, failed and deletes; the hit ceiling is two hundred a kind and "more" says to narrow the words; a phrase is straight or curly quotes around the whole term; Find's hits sit under the box in a list that scrolls to a third of the window, up to four hundred; a lit paragraph is the nth block of the memo or the summary as drawn; a memo hit's moment is its first citation; the search on the largest case took milliseconds and no index was added (`docs/research/case-search.md`).
- **2026-09-19.** Chapter 3 written for the build (the dashboard line, the Search tab, Find on the incident page), from the shape of 2026-09-17 and the maintainer's list of 2026-09-19 (search as its own tab; a finding that positions the cameras).
- **2026-09-19, v1.64.0.** Chapter 2 built the same day, with these decisions left to the build: the AI assistant call audit row is one per run (as chapter 3 of Phase 6 had it), carrying the windows, the second looks, whether a Look for was given and the answers cut short, rather than one row per call; the state line reads "Proposed 14 events at 14:02, 3 from the watch phrases; 1 answer cut short, raise Proposed events answer cap", and a watch-only run the same shape; the why prints in the Chronology's Word export under the line in italics as "Why it matters: ..." and in the spreadsheet as a last column; the Look for box sits beside the button; a watch hit's why reads "The office watches for \"gun\"."; the whole-word rule allows the plural (gun, guns) and folds curly apostrophes; a phrase heard again on the same camera within thirty seconds joins its first hit as "(said 2 times)"; the second look is skipped when a window already holds twelve; the measurement is `docs/research/event-spotting.md`.
- **2026-09-19.** Chapter 2 written for the build, from the maintainer's finding that "I got, I got gun" went unproposed on the server; the outlined chapters move to 3, 4 and 5. Amended the same day at the maintainer's word that the events are dynamic and the engine's reasoning is the finder: the judgement first (the why line, the windows, the second look, the office's context), the watch phrases as the floor under it, and the prompt measured on the server before the build is called done.
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
