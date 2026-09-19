# Gideon Transcribe, Phase 6 specification

The Incidents release. Chapter 1 was built as `v1.58.0` and chapter 2 as `v1.59.0`, with the tuning pass as `v1.60.0`; chapter 3 as `v1.61.0`; chapter 4, the page laid out for watching, as `v1.62.0`; chapter 5, Sync as one control with the clip from the strip, is written for the build (2026-09-19).

## About this document

This is the build specification for Phase 6 of Gideon Transcribe: several cameras of one event played together. An office's case often holds more than one video of the same minutes, the body-worn cameras of every officer at a stop and the in-car camera of each unit, and today each is a recording of its own, opened one at a time. The maintainer asked on 2026-09-17 for "the ability to upload multiple body worn camera videos and have them sync so they play at the same time", for a "visual timeline that can also be exported and integrated within the investigative analysis by staff", and for the assistant to see across the cameras, all of it "a separate area" of the case. It builds on Phase 2 (`docs/spec/SPEC-PHASE-2.md`, Cases and the Case Chat), Phase 4 (`docs/spec/SPEC-PHASE-4.md`, the camera stamp and the Digest) and Phase 5 (`docs/spec/SPEC-PHASE-5.md`, whose Lanes are the shape of this phase's strip), and changes nothing in them beyond what each chapter's "What changes from earlier phases" lists.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 6 words Incident, Incident clock, Placed, Wall, Chronology, and Event), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the Incidents page), and the mock-ups the chapters were drawn from, `docs/spec/mockups/phase-6-incidents.html`, one page of seven screens in the app's own look. The mock-ups show the whole of the three chapters; a screen says which chapter builds each part.

Nothing in this document is office-specific. No new environment key is needed and no new service: the cameras are played by the browser, the placements are rows, and the one engine call this phase adds is one the app already makes. The conventions of the Phase 1 document apply here unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing leaves the building.

## What Phase 6 adds

- **Incidents, and the cameras in step** (chapter 1, for the build): a case's videos that ran at the same time become an Incident, offered by the app when their clocks overlap and made by hand otherwise. Each camera is placed on one clock, the time of day the cameras burn into their pictures, read as each playback copy lands; a camera without a clock is matched by sound to one that has, or placed by hand, and how each was placed is shown wherever it appears. The Incident page is a page of its own inside the case: up to six cameras playing in step under one transport and one clock, sound from one of them, a strip across the width with a lane per camera, and the words and the camera line under each picture. An Incidents page in the Panel holds its switches.
- **The Chronology** (chapter 2, for the build): the Incident's list of Events, each a time of day on the Incident clock, a line of text, its source (a person, the words of a camera, or what a camera showed) and the cameras that show it, added by a person at the moment being watched, from a line under a tile, or from a chat's citation; drawn as the strip's Events lane; listed on the Chronology tab with a citation that plays every camera from there; and exported as a Word document with the strip as a picture, as a spreadsheet, and as the picture alone.
- **The Incident page, laid out for watching** (chapter 4, for the build): a Layout menu in the transport with Focus (one camera large, the others in a filmstrip under it, any of them one press from the front, the sound following the focus unless pinned), Side by side (the grid beside the panel with the strip at the bottom) and Grid at 2, 3 or 4 across; lighter tile heads, the sound as a speaker icon, parked cameras as lanes in the strip, and the event box as a sheet. From the maintainer's finding after v1.61.0 that the page was "a bit smushed".
- **The assistant on the Incident** (chapter 3, built as `v1.61.0`): the Case Chat told each camera's place on the clock, so a time on one recording is the same moment on the others and an answer gives the time of day; Events the assistant proposes from the cameras' Digests on a press, accepted one by one; and the Incident memo, written across every synced camera from the incident record (the Digests merged onto the Incident clock) on the Chronology's Events, each cited so the citation plays every camera, on the Incident page's Memo tab, exported to Word with the Chronology as its last pages.

Chapter 1 adds an Incidents settings page with six settings, four audit rows, two tables, and one migration that moves the camera stamp from the Transcript to the Recording. Chapter 2 adds one table, four audit rows, three exports and no setting. Chapter 3 adds one table, seven settings, two prompt templates, four audit rows and one export. Chapter 4 adds one setting and no row.

## Contents

1. Incidents, and the cameras in step
2. The Chronology
3. The assistant on the Incident
4. The Incident page, laid out for watching
5. Sync, one control (with the clip from the strip)
6. Deferred and ruled out

Appendices: A. Audit rows added in Phase 6. B. Settings added in Phase 6.

## 1. Incidents, and the cameras in step

Written 2026-09-17 from the maintainer's ask and the answers to the build's questions the same day: the office's cameras are mostly Motorola with a clock burned into the picture, but the make has changed several times over the years and will again, and some videos will have no clock; alignment "as tight as possible", with a second or two accepted as what is realistic; between two and twenty cameras, and a limit is fine; usually one incident in a case, sometimes more; the stamp may be read by day; sound from one camera; and the feature is "a separate area" of the case, not one more list on the case page. The app proposing an incident when it sees the clocks overlap was chosen over creating one by hand every time, with New incident kept for the rest.

### Principles

1. **One clock, the cameras' own.** Every camera in an Incident sits on one clock, the time of day the cameras burn into their pictures. The app never invents a time: a camera's place comes from its checked stamp, from its sound matched against a camera that has one, from the time its file carries, or from a person's hand, in that order of trust, and the page says which.
2. **The app proposes; a person decides.** When a case's videos overlap on their clocks the case page offers them as an Incident in one line with one button. Nothing exists until the button is pressed, and New incident makes any group a person wants, whatever the clocks say.
3. **The best possible, said honestly.** Camera clocks are set to the second and drift, so two cameras placed from their clocks agree to a second or two and no better; a match by sound is closer where the cameras were within earshot. The pages never claim more than they know: how each camera was placed is a pill beside it, and a camera that is not placed is not on the Wall.
4. **Nothing new on disk.** The playback copies play as they are, from several video elements the browser keeps in step; no file is re-encoded, stitched or stored. An Incident, its cameras' placements and, in later chapters, its Events and memo are rows in the database and join the backup set with the rest of the case's rows.
5. **The Incident is the case's.** It lives inside one case and nowhere else. Whoever may open the case may open it and work in it, a Collaborator as the owner does; it counts as the case's activity; it goes to the Recycle bin with the case and comes back with it; deleting it removes placements and never a recording; a recording deleted from the case leaves it.
6. **A page of its own.** The Incident page is reached from the case page and left by Done, in the Speakers page's shape. The case page carries only the doorway: an Incidents tab beside Chat (a strip under the case name until v1.59.1).
7. **Every part is a switch.** Incidents as a whole, the proposing, the early stamp read, the sound match, and the two limits are settings on an Incidents page of the Panel, and Off hides and never deletes.

### Words

**Incident**, **Incident clock**, **Placed**, and **Wall**, as `CONTEXT.md` defines them; **Chronology** and **Event** are chapters 2 and 3's words and appear in chapter 1 only as the room the strip and the tabbar keep for them. The pages say "camera" for a video in an Incident and "incident" for the group; they never say sync, offset, or timeline (the Timeline is the viewer's waveform strip).

### Where an Incident lives, and how one comes to be

- **Inside a case.** An Incident is a named group of that case's videos with a clock they share. A case may hold several (a stop on one day, a station interview the next); most hold one. A video is in at most one Incident. Sound recordings and live recordings are not offered in this phase (see Not in this phase).
- **The doorway on the case page.** An **Incidents** tab beside Chat, the fifth tab of the Phase 2 case page (from v1.59.1; a strip under the case name and a header button from v1.58.0 to v1.59.0, which the maintainer found floated over the page): the case's Incidents one line each with the name, the count of cameras, the span by the clocks, a pill for how many cameras are placed, the count of Events and **Open the incident**; the offers; **New incident**; and every video in the case with its clock and the Incident it is in. The recordings tab gains two columns, **Clock in the picture** (the stamp as read, with "checked" or "unchecked", or "no clock in the picture", or "not read yet") and **Incident** (which one the video is in, or none). The strip and the button are absent while Incidents is Off, and the Incident column with them.
- **The offer.** On the Incidents tab, the app looks at the case's videos that are in no Incident and have a checked clock: two or more whose spans on the clock overlap are one group (a chain of overlaps is one group), and each group is offered on the tab in one line, "8 videos ran at the same time on 7 June 2025. Make them an incident?", with **Make it** and **Choose myself**. Make it makes the Incident with those cameras, named by the date ("7 June 2025"), and opens its page. Choose myself opens the New incident dialog with those videos ticked. A video that lands later in the case, with a checked clock inside an existing Incident's span, is offered to that Incident the same way: "1 more video ran during Traffic stop. Add it?" An offer declined with **Not these** is not shown again for that set of videos; a further video makes a fresh offer. Offers are made only while Incidents proposed is On, and a group larger than Most cameras in an incident is offered as its first twenty by start time, the line saying so.
- **New incident.** A dialog listing the case's videos, each with its title, its type and length, and its clock pill, any number ticked, a name (the date of the first ticked clock suggested), and **Make the incident**. The dialog refuses more than Most cameras in an incident and says the limit. A video from another day may be ticked; it is simply not placed until a person places it. The dialog opens the page on the new Incident.
- **The Cameras tab** on the Incident page is where an Incident changes afterwards: **Add cameras** (the same dialog, for the videos not yet in it), remove a camera (its placement goes, the recording stays), **Rename incident**, and **Delete incident**, which asks once and removes the Incident, its placements and, in later chapters, its Events and memo, never a recording. A recording deleted from the case, or moved to another case, leaves the Incident; an Incident left with no cameras stays, its line on the tab saying "no cameras", until someone deletes it.

### The Incident clock

- **What it is.** The time of day, with its date, that the cameras' checked stamps give. A camera placed from its clock sits at the stamp's clock time less the second the stamp was read at, as Phase 4 chapter 3 tells the assistant; the Incident's span runs from the earliest placed camera's start to the latest placed camera's end. The page shows the clock as hh:mm:ss with the date beside it, and the elapsed time into the Incident with its length in the transport.
- **When no camera has a clock.** An Incident whose cameras are all placed by hand or by sound has no time of day: its clock runs from 00:00:00 at the first placed camera's start, and the page says "no camera clock; times are from the first camera". When a camera with a checked clock is later added or placed, the clock becomes the time of day and every placement keeps its distance from the others.
- **Drift.** Two cameras placed from their clocks may disagree by a second or two, because camera clocks are set to the second and drift between dockings. The page does not hide this: a person who hears an echo places one of them by sound or nudges it by hand, and the pill says so from then on.

### The stamp, read early

- **When.** Phase 4 reads the camera's stamp when the picture record is first made, which under Vision's overnight position is the night after the upload. Chapter 1 reads it **as the playback copy lands**, for every video in a case (a video moved into a case from the Workspace is read at the move), two frames as Phase 4 chapter 3 has them, when Read the camera's stamp is On, Stamp reads early is On, and the engine passes the minute check. It is one small call for each of two frames, by day, and the Incidents settings page says so. Vision reads a stamp only when none has been read. Off, the stamp waits for Vision as before and an Incident's cameras are placed by hand until then.
- **Where it is kept.** The stamp becomes the Recording's, since the picture is the recording's and not the transcript's, and a Process again must not lose it: a migration copies every stamp a Transcript holds onto its Recording, and every reader (the assistant's clock line, Details, the export's processing record) reads it there. An empty stamp is kept too, so nothing is read twice; Process again does not read it again.
- **The file's own time.** Many cameras write the moment recording began into the file itself; the probe already keeps it. It is shown on the Cameras tab as "the file says <time>" and offered as a way to place a camera, marked unchecked, because a camera's file clock is often minutes out and nobody has checked it against the picture.

### Placing a camera

Each camera in an Incident carries one of these, as a pill wherever the camera is named:

- **From its clock, checked**: placed from a stamp whose clock moved on between the two frames. The best the app can do by itself.
- **From its clock, unchecked**: placed from a stamp read from one frame when the second could not be read; the page suggests a listen.
- **Matched by sound**: the app compared this camera's sound with a placed camera's and found where they line up. Offered on the Cameras tab and in the Place dialog against any placed camera; runs on the media worker from the two ASR audio files already on disk, as a Clip render does, never a Job and never an engine call; takes about a minute; comes back as a distance and a strength, and the page applies a strong match, shows a weak one with "the sounds did not clearly line up" and leaves the choice to the person, and says "no match" when there is none. Works where the two cameras were within earshot and not otherwise. Offered while Match by sound is On.
- **From its file, unchecked**: placed from the time the file carries.
- **Synced by hand** (Placed by hand until v1.60.0): dragged on the strip, or nudged with the buttons (a second and a tenth of a second either way) while both play with the sound from one, or typed as a clock time, from **Sync** on the camera's tile or on the Cameras tab. A camera placed from its clock and then nudged becomes Synced by hand.
- **Not synced yet** (v1.60.0; Not placed until then): none of the above has happened, and the camera sits at the app's guess, the file's time when the Incident has a clock and the file carries one, else the Incident's start, on the Wall like the rest so a person can see it and nudge it with Sync. All cameras and the sound match treat it as not yet in step.

Placing is audited (Camera placed, with how); who placed it and when are shown on the Cameras tab. A placement is a number of seconds on the Incident clock and a word for how, on an Incident camera row; nothing on disk changes, and a Process again of the recording leaves it standing.

### The Incident page

In the Speakers page's shape: the app's bar with nothing lit, the page's own head, and the desk below.

- **The head.** The label Incident, the name, and in small type the case, the count of cameras, the span and the count of events; the clock in large figures with its date; **Add event here** (chapter 2; absent until then); **Export** (chapter 2; absent until then); **Done**, which returns to the case page.
- **The Wall.** Up to **Cameras on the wall** (six shipped) placed cameras, in a grid the build chooses for one to nine (three across at six), in the order of their start on the clock unless a person reorders them. Each tile: the camera id from its stamp when there is one, else the recording's title, with its colour dot, its Placed pill, Sound, and a menu (Sync this camera, Swap out, Open the recording, Remove from incident); the picture; and under it the line being spoken on that camera, in that camera's Speaker colours (the camera line under a tile was withdrawn in v1.60.0). A Speaker's label shows only when it is a name a person set or accepted on that recording's Speakers page; a label the voice split handed out (Speaker 1, Speaker 4) is not shown on the Incident page, in the event box or on the Chronology, because such labels are given per recording and the same person carries a different one on each camera (the maintainer, 2026-09-17: what matters on an incident is what was said, and a name accepted by staff carries over). Tiles are dragged into place, and **Across** in the transport sets the columns. A tile whose camera has not started at the clock's moment shows "Starts in 0:47" over a dark picture; one whose camera has ended shows "Ended at 21:57:30"; the tile stays, so the Wall does not rearrange itself while playing. The remaining placed cameras are listed under the Wall as parked tiles with **Swap in**, which takes a camera off the Wall (the one the person picks, or the last) and puts this one on; the swap is remembered for the Incident.
- **The sound.** One camera has the sound, marked on its tile and chosen there or in the transport's Sound from list; the others are muted. The camera with the sound leads: the browser sets every other video to the same clock moment when play starts and on every seek, corrects a follower that has drifted by more than a small fraction of a second by adjusting its rate, and seeks it outright when it is out by more than about half a second (the figures are left to the build). A camera that has not started at the moment waits and starts at its own time. The Speed control applies to all.
- **The transport.** Play and pause, back three seconds, five seconds either way, the elapsed time and the length, Speed, Sound from, and Follow, which keeps the line being spoken in view under each tile as the viewer's Follow does. Space, B, Left and Right are the viewer's keys.
- **The strip.** Across the width under the desk, in the shape of the Speakers page's Lanes: a ruler of clock times, then one lane per camera in the Wall's order and then the parked ones, each with its colour dot and id at the left and, across the width of the Incident, a bar from its start to its end on the clock, thin for a camera not on the Wall, and greyed for one not placed. The playhead is a line through every lane. A press anywhere seeks every camera there; a press on a camera's bar seeks there too and swaps that camera onto the Wall when it is parked; dragging a bar places that camera by hand (a confirmation names the distance moved). Zoom: all, 10 min, 2 min, as the Lanes have it. The strip's last lane, Events, is empty in chapter 1 and drawn only from chapter 2.
- **The work area.** Beside the Wall, in the viewer's tabbar shape: **Cameras** (the table: each camera with its id and title, where it starts on the clock, its placement pill, who placed it and when, the file's own time, and Adjust or Place; Add cameras, Rename incident, Delete incident), and **Details** (the Incident: who made it, when and how, its clock and where it came from, its span; each camera's stamp as Details shows it; nothing about the engine). Chronology and Memo are chapters 2 and 3 and are absent until built. Open in a window is not offered in chapter 1.
- **Below 1280 pixels** the work area follows the Wall and the strip, and the Wall shows two across; the build decides the rest within that.

### In and out

- **Open the incident** on the case page's strip opens the page at the Incident's start, paused. **Done** returns to the case page. The browser's Back does the same.
- **All cameras** in the viewer's head, on a recording in an Incident, opens the page at the viewer's playhead translated to the clock, so a moment found in one transcript is seen from every camera. It is absent on a recording in no Incident, and on one that is not placed.
- **All cameras** beside a Case Chat citation on a recording in an Incident, and beside a citation in that recording's own Chat and Summary, opens the page at that moment. The assistant is told nothing new in chapter 1; the link is the app's arithmetic.
- A time in the address opens the page there, as the viewer's does.
- Standing is the case's: whoever may open the case may open the page and do everything on it, a Collaborator as the owner does. An Admin's opening writes the Admin access row and does not count as activity, as Phase 2 has it.

### What changes from earlier phases

- **Phase 4, chapter 3, The stamp**: read as the playback copy lands when Stamp reads early is On, kept on the Recording, and read by the record only when none is there. The migration copies the stamps that exist. The words the assistant is given do not change.
- **Phase 2, the Cases chapter, The Case page**: a fifth tab, Incidents, beside Chat, and the Clock in the picture and Incident columns on the recordings list.
- **Phase 2, the Cases chapter, Last activity**: opening an Incident, making one, placing a camera, and (chapter 2) adding an Event count as the case's activity.
- **Phase 2, the Cases chapter, One way out, and the Retention policy chapter**: an Incident goes to the Recycle bin with its case and comes back with it; deleting a recording removes it from its Incident; moving a recording between cases removes it from its Incident, since an Incident cannot cross a case's edge.
- **Phase 2, the Backup chapter**: the Incident rows join the database's part of the backup set; nothing is added on disk.
- **Phase 1, the Transcript viewer and player chapter, the head**: All cameras on a recording in an Incident.
- **Phase 2, the Case Chat chapter, Citations**, and **Phase 1's Citations**: All cameras beside a citation on a recording in an Incident.
- **Phase 2, the Cases chapter, Not in this phase**: "Tags on Recordings in a Case" and the like are untouched; an Incident is not a tag and does not narrow the Case Chat.

### Carried for chapters 2 and 3

- The strip keeps an empty Events lane and the head keeps room for Add event here and Export.
- The tabbar keeps room for Chronology and Memo.
- Each camera's placement is a number of seconds on the clock, so chapter 3 can tell the assistant "Recording 3 starts at 21:55:44" in one line per camera.

### Audit rows

Category Cases: **Incident made** (from an offer or by hand, with the count of cameras), **Incident changed** (a camera added or removed, or the name), **Incident deleted**, and **Camera placed** (how: clock, sound, file or hand; never the distance in a row's words, since the distance says nothing a person needs from the log). The stamp's read writes the AI assistant call row with feature `stamp` as Phase 4 has it. The Admin access row covers an Admin's opening. No row holds a camera id, a name or a word of a transcript.

### Settings

An **Incidents** page in the Panel's Settings group, between Vision and Speakers, since it shares the camera stamp with Vision:

- **Incidents** (On or Off, On shipped; greyed while Folder management is Off). Off hides the Incidents tab, the Incident column, the Incident pages and every All cameras; keeps everything.
- **Incidents proposed** (On or Off, On shipped; greyed while Incidents is Off). Off makes no offer; New incident stays.
- **Cameras on the wall** (2 to 9, 6 shipped). How many play at once; the rest are parked.
- **Most cameras in an incident** (2 to 40, 20 shipped). New incident and the offer refuse more.
- **Stamp reads early** (On or Off, On shipped; greyed while Read the camera's stamp is Off). Read the stamp as the playback copy lands, two small engine calls per video by day, rather than with the vision work.
- **Match by sound** (On or Off, On shipped). Offer the sound match on the Cameras tab and in the Place dialog.

### Not in this phase

- **Sound recordings and live recordings in an Incident.** A phone call or a dictation has no picture to read a clock from and no tile to show; the cameras are videos. A later chapter may place a sound recording by hand.
- **Mixing the sound** of several cameras. One camera has the sound.
- **Frame-accurate sync.** Within a second or two from the clocks, closer by sound; the maintainer accepted this.
- **A Clip across cameras**, side by side, for a hearing. Deferred by the maintainer.
- **An Incident across cases.** Nothing crosses a case's edge.
- **Reordering the Wall by drag**, and remembering a person's own Wall per person. The order is the clock's, and a swap is the Incident's.
- **Open in a window** for the Incident page's tabs.

### Left to the build

- The sound match: the method (comparing the two cameras' ASR audio over a window around the expected place, on the media worker), its window and what "strong" means, decided after a probe on the office's own files, recorded in `docs/research/` with the figures, before the chapter's promise is relied on.
- The following figures: how far a follower may drift before its rate is adjusted, and before it is seeked; within the rule that a person hears no echo between two cameras placed by sound.
- The Wall's grid for each count from one to nine, and the arrangement under 1280 pixels, within the rules above.
- The exact wording of the offer, the pills, the "no camera clock" line, and the swap's confirmation, within the words fixed here.
- Whether the case page's Clock in the picture column shows the date or the time alone when every clock is on one day.

## 2. The Chronology

Written 2026-09-17, after chapter 1 had gone to the server, from the maintainer's ask for "a visual timeline that can also be exported and integrated within the investigative analysis by staff" and the decisions of the same day: people add events first, with the assistant able to propose them later (chapter 3); an event added while playing carries the clock's moment, so it lands on every camera; and the memo of chapter 3 is written on these events, so the two match. Chapter 1 left the room: the Events lane on the strip, Add event here and Export in the head, and the Chronology tab.

### Principles

1. **A person's record, on the cameras' clock.** An Event is something a person says happened, at a time of day the cameras agree on. The app never adds one by itself in this chapter; the assistant's proposals are chapter 3's and join only when accepted.
2. **Every Event is a place to look.** Its time plays every camera from there, on the page and from the export's table. An Event is worth adding only because someone will want to see that moment again.
3. **Made where the moment is.** The clock's moment while watching, a line being spoken under a tile, or a citation from a chat: the Event is made at the moment a person is already looking at, never typed from memory.
4. **The source stays on it.** An Event says whether a person wrote it, whether it quotes what a camera heard, or what a camera showed; the export prints the same. Words quoted from a transcript are a copy as the transcript stood, and the pill says Words so a reader knows to check the transcript itself.
5. **The picture is drawn from the rows, never kept.** The strip as a picture is made by the page from the same rows the strip is drawn from, at the moment of the export, and travels inside the document; nothing image-like is stored, as Phase 4 has it.
6. **Nothing new to switch.** The Chronology is part of an Incident: Incidents Off hides it with the page, and no setting of its own is needed.

### Words

**Chronology** and **Event**, as `CONTEXT.md` defines them, in force from this chapter. The pages say "event" and "chronology"; they never say timeline, log, mark (a live recording's) or moment (a description). The strip's last lane is the **Events lane**.

### Events

- **What an Event holds.** A time on the Incident clock (seconds from the Incident's zero, shown as the time of day when the Incident has a clock, else as elapsed time); optionally an end, for something that ran a while; a line of text, up to 500 characters; its source, one of **person**, **words** or **camera**, with the camera it came from when it has one; the cameras that show it, a list the person may change, filled at first with the cameras running at that moment; who added it and when; who last changed it and when. Chapter 3 adds the source **assistant** and a proposed state; nothing in this chapter makes either.
- **Add event here**, in the head and on the E key: a box under the head with the moment prefilled as the clock shows it (editable as hh:mm:ss, or m:ss without a clock), an optional end, the line of text with the focus, the running cameras as ticks, and **Add**. Playing does not stop for it; the moment is the one at the press. Escape or Cancel closes it. The Event's source is person.
- **From a line being spoken**: the line under a tile carries **+ event** on hover. The Event takes that line's words as its text, the moment as its time, that camera as its source and its only ticked camera at first, and opens the box for the person to edit the words or accept them; its source is words.
- **From a camera line** under a tile (a video enriched with vision): the same, with the description as the text and camera as the source.
- **From a chat's citation**: the all cameras link beside a citation (chapter 1) opens the page at that moment with the box open and the cited line's words in it, when the address says so; the person edits or accepts. Its source is words. The viewer's All cameras does the same when its playhead is on a line.
- **Edit** on the Chronology tab opens the same box on that Event, with **Remove**. Changing the time moves it on the lane; changing the cameras changes Seen on. An Event whose source camera has left the Incident keeps its text and reads "a camera no longer in the incident" for its source.
- **Where an Event goes.** With the Incident: deleting the Incident removes its Events; a case in the Recycle bin takes them and brings them back; a recording deleted leaves its Events standing without their camera. Adding, changing or removing an Event counts as the case's activity.

### The Chronology tab

- First in the tabbar, before Cameras and Details, and the tab the page opens on once any camera is placed (Cameras until then). Its head line says how many Events there are and, from chapter 3, how many the memo was written on.
- **The list**, in time order: the time as a citation that plays every camera from there; the text, with "Seen on" and the cameras under it; the source pill (**Added by <name>**, **Words, <camera>**, **Camera, <camera>**); Edit. An Event with an end shows both times. The Event whose time is the latest at or before the clock's moment is the current one, marked as the line being spoken is, and Follow keeps it in view.
- **Add event here** repeated at the top of the list, so the tab has its own way in.

### The Events lane

- The strip's last lane, drawn from chapter 1's empty one: a mark at each Event's time, or a short bar from its time to its end, with the first few words of its text beside it; a person's Event and a quoted one in the accent colour, and chapter 3's proposed ones in the working colour. A press on a mark seeks every camera there; hovering shows the whole line. When two labels would overlap at the zoom in hand the later one is drawn as a mark alone, and the Zoom buttons of the strip spread them.

### The exports

- **Export** in the head offers three: **Chronology to Word**, **Chronology as a spreadsheet** (.csv), and **The strip as a picture** (.png). Each writes the audit row Chronology exported with the format, never a word of an Event.
- **The Word document**, in the app's export shape (the office's name and logo on the cover as the other exports carry them): the title "Chronology: <incident>", the case, the Incident clock's date, the cameras with how each was placed (the pills as printed), the strip as a picture, then the table: number, time (the time of day), event, source, seen on. Under the table two lines: that an event marked Words or Camera was taken from a transcript or from a model's description of the picture and accepted by a person, and that a quoted transcript may have been corrected since. The AI notice prints only when any Event was proposed by the assistant (chapter 3); the transcription notice does not print, since the document is not a transcript.
- **The spreadsheet**: one row per Event with number, time of day, seconds into the incident, end, event, source, source camera, seen on, added by, added on; the first row the column names; UTF-8 with a byte order mark so a desktop spreadsheet reads it as it is.
- **The picture**: the strip as the page draws it, at twice the screen's resolution, with the ruler, a lane per camera with its id and bar, and the Events lane with its marks and labels, in the light palette whatever the person's theme, so it reads on paper. The page draws it on a canvas from the same rows as the strip and hands it to the export; the Word document embeds it, and The strip as a picture saves it alone. Nothing of it is stored.
- The exports are offered to whoever can open the Incident; a Collaborator exports as the owner does.

### In and out

- The E key opens Add event here at the moment; Escape closes the box; Enter in the text adds. Space, B, Left and Right stay the transport's while the box is closed.
- The address gains `?t=<moment>&event=<words>`: the page opens at the moment with the box open and the words in it, which is how a citation makes an Event.

### What changes from chapter 1 and earlier phases

- **Chapter 1, The Incident page**: Add event here and Export join the head; the Events lane is drawn; the tabbar reads Chronology, Cameras, Details, and the page opens on Chronology once a camera is placed.
- **Chapter 1, In and out**: the all cameras link beside a citation, and All cameras in the viewer's head, carry the cited or spoken line into the address so the Event box opens with it.
- **Phase 2, the Cases chapter, Last activity**: adding, changing and removing an Event count.
- **Phase 1, the Exports chapter**: a fourth kind of export, the Chronology's three, in the same shape and under the same audit row pattern; Download everything and the case's Download all transcripts do not carry them.
- Nothing changes on the case page, in the viewer's transcript, or in Vision.

### Carried for chapter 3

- The Event's source may be **assistant** and an Event may be **proposed**, with Accept and Dismiss; chapter 2 draws proposed Events on the lane in the working colour and lists them under the Chronology as chapter 3 will fill them, and makes none.
- The Chronology tab's head keeps room for "written on N of them" and the memo's staleness line.

### Audit rows

Category Cases: **Event added** (source), **Event changed**, **Event removed**; category Exports: **Chronology exported** (format). None holds a word of an Event, a camera id, or a time.

### Settings

None new. Incidents governs the whole.

### Not in this phase

- **Events the app makes by itself**, from the words or the picture: chapter 3, and only as proposals.
- **A clip from an Event**, side by side across cameras: deferred with clips across cameras.
- **Events on the case page or in the case chat's answers**: an Event lives on its Incident page and in the exports; chapter 3 tells the assistant about them.
- **Attaching a file or a picture to an Event.** An Event is a line and a time.

### Left to the build

- The picture's exact size and the rule for thinning overlapping labels, within the rule that every Event has a mark and the strip stays legible on a Letter page.
- The Word document's table widths and the picture's placement, in the app's export shape.
- The Event box's wording and its keyboard details, within the words fixed here.
- How the cited line reaches the address from the viewer's head (the line being spoken at the playhead) and from a citation (the citation's own line).

## 3. The assistant on the Incident

Written 2026-09-17, after the tuning pass (v1.60.0 and v1.60.1) had gone to the server, from the maintainer's asks of the same day: the deliverable is "an incident memo written by the assistant across all cameras", on a page of its own where staff scroll and investigate; people add Events first and the assistant may propose them later; the memo is written on the Chronology so the two match; and "the chronology should eventually be a smarter presentation based on LLM summaries". Chapters 1 and 2 left the room: the placements as seconds on one clock, the Event's source **assistant** and its proposed state, the working colour on the Events lane, and the Memo tab's place in the tabbar.

### Principles

1. **The cameras' clock is the assistant's clock.** Every synced camera's place is a number of seconds on the Incident clock (chapter 1). The assistant is told each camera's start by that clock, so a time on one recording is the same moment on every other, and an answer can say when a thing happened by the time of day rather than by minutes into one file.
2. **Written on the Chronology.** The memo is written on the Events the office recorded: a sentence that rests on an Event carries the Event's number, the memo never contradicts an Event, and when the Chronology changes after the memo was written the page says so and offers to write it again. The Events are the office's; the memo is the assistant's account of them and of what the cameras add.
3. **It proposes; a person accepts.** An Event the assistant proposes sits under Proposed by the assistant until somebody presses Accept, on the Speaker check's pattern (Phase 5 chapter 3): propose, never apply. Nothing the assistant proposes reaches the Chronology, the exports or the memo unaccepted.
4. **What the words and the cameras give.** The narrative rules of Phase 4 stand throughout: names and roles only as the words give them, a person the camera shows by clothing and position, a thing what the description saw, never a legal fact such as consent, arrest, search or force as a conclusion. The assistant reads the cameras' Digests and transcripts and nothing else; it is never asked to guess what a camera did not show.
5. **Every time is a place to look.** A time in the memo, in a proposal, or in a Case Chat answer that names the time of day is a citation that plays every camera from there.
6. **One switch per thing.** Each of the three parts has its own switch on the Incidents page, and Incidents Off hides all three with the page.

### Words

**Incident memo**, as `CONTEXT.md` defines it from this chapter; **Proposed**, the state of an Event the assistant offered and nobody has accepted; and the **incident record**, the app's own merge of the cameras' Digests onto the Incident clock, plumbing that the memo is written from. On the pages: **Propose events**, **Proposed by the assistant**, **Accept**, **Dismiss**, **Accept all**, **Write the memo**, **Regenerate**, **Memo to Word**. The pages never say report, narrative, story, auto-events or timeline.

### The Case Chat is told the placements

- **What is added.** When any recording the question reads is a synced camera of an Incident, one block per Incident follows the People line: "Incident <name>, <N> cameras on one clock, <date>. Recording 1 (<camera>) starts at 21:55:44 by the cameras' clock and runs to 22:37:10. Recording 3 (<camera>) starts at 21:56:31 and runs to 22:31:05. ..." with the rule under it: "A time in a recording plus that recording's start is the time of day; the same time of day on another camera is that time of day less the other camera's start. Where a camera's own stamp and the incident's clock differ, the incident's clock is right: the office synced the cameras." A camera guessed and not yet synced is named as running at about a time, not placed. An Incident with no clock (chapter 1: it counts from its first camera) gives each camera's start as minutes and seconds into the incident, and the answer gives times the same way.
- **What the answer does.** The Case chat template gains two sentences, editable with the rest: asked when something happened on a camera of an incident, give the time of day by the cameras' clock beside the citation; asked what another camera showed at that moment, read that camera's record at the same time of day, and say when the camera had not started or had stopped. The citations stay `[Recording n, hh:mm:ss]` of the recording, so the viewer and the all cameras link of chapter 1 work as they do; the time of day is words in the answer.
- **Nothing else changes** in the Case Chat: the readings, the hours ceiling, the Digest standing in for a transcript, the combining call. The block costs a few lines per Incident. Its switch is **Case chat knows the incidents** (On); Off, the Case Chat reads the transcripts as Phase 4 has it.

### Proposed Events

- **On a press.** **Propose events** sits at the top of the Chronology tab beside Add event here, for whoever can open the Incident, while **Assistant proposes events** is On and at least one camera is synced. It never runs by itself: people add Events first (the maintainer's decision of 2026-09-17), and a proposal is asked for. One run at a time per Incident; a state line beside the button reads "Reading 7 cameras...", "Proposed 4 events at 14:02", "Nothing to propose", or the engine's reason in the assistant's words.
- **The run**, on the engine's lane, one job, feature `incident_events`, thinking off and the suggestions' deterministic sampling as the Speaker check has it. One call per synced camera, in the order the cameras start: the Ground rules, the **Proposed events** template, the answer's shape, the camera's start by the Incident clock, the camera's Digest on the recording's own times (or, for a camera with no Digest, its transcript as the Case Chat renders it, in windows of the Reading size), the Events that stand and the proposals the earlier cameras of this run made, each as its time of day and its line, with the instruction to propose only what this camera adds. The answer is a JSON list, each item a time in the recording, an end when the thing ran a while, a line of up to 200 characters, and the words or the description it rests on; vLLM's structured output holds the shape.
- **What makes an Event**, in the template's shipped wording: a person or a vehicle arriving or leaving; a command, a warning or an advisement of rights; a statement that carries weight; a search, a restraint, a use of force or an arrest as the words or the camera describe it and never as a conclusion ("handcuffs put on", not "arrested"); a thing handed over, found or taken; a move to another place; a camera starting or stopping. Plain words, third person, past tense; the line says what happened, not what it means.
- **The same rule for the proposals**: the template says a numbered Speaker label is that camera's alone and a proposal names a person only by a name; otherwise it says what was said and on which camera.
- **The app checks every item**: the time falls inside the camera's span; the line is not empty; the text it rests on is a real line of what the camera was given; and no Event or proposal already stands on the same camera within five seconds of it. What fails is dropped without a word. A run replaces the pending proposals with its own and offers again nothing a person dismissed (the same camera within five seconds of a dismissed one), as the check does. A problem mid-run keeps the earlier cameras' proposals and reports the reason; an unreadable camera is a lost camera, not a lost run.
- **On the page.** Under the Chronology's list, **Proposed by the assistant (N)**, oldest time first: the time as a citation that plays every camera, the line, "From the words on <camera>" or "From the camera <camera>", the words it rests on as the hover title, **Accept** and **Dismiss** on each, **Accept all** at the top when two or more wait. On the strip's Events lane a proposal is drawn in the working colour with "(proposed)" after its label, as chapter 2 has it.
- **Accept** makes an Event at once with source **assistant**, the camera it came from, the cameras running at that moment ticked, the accepting person as who added it, and the audit row Event added (source assistant); it lands on the lane, the list and the exports like any other, and Edit works on it. **Dismiss** keeps the proposal out and off the lane. Neither stops playing. A proposal counts nowhere: not in the Chronology's count, not in the exports, not in the memo.
- **Where a proposal goes.** With the Incident, as an Event does. A camera removed from the Incident takes its pending proposals with it.

### The Incident memo

- **The Memo tab**, second in the tabbar (Chronology, Memo, Cameras, Details), while **Incident memo** is On. With no memo: a line saying what it will be written from ("7 cameras synced, 12 events on the chronology; Dash cam unit 4 is not synced and will be left out"), **Write the memo**, and, when no camera is synced, why it cannot be written yet. While it is written: the card's waiting line, as a Summary's, with the stage ("Reading 7 cameras", "Writing the memo") and a cancel. With a memo: the AI notice at the top as every Summary carries it; the memo; under its head "Written <date> from the transcripts and the vision of 7 cameras, on the chronology's 12 events. One camera (Dash cam unit 4) is not synced and was left out."; **Regenerate** and **Memo to Word**.
- **Stale, and said so.** The memo keeps a signature of the Events it was written on (their ids, times and text) and of the cameras (their ids and starts). When either changes the tab says "The chronology has changed since this memo was written: 2 events added" (or changed, removed; "a camera was synced"; "a camera joined"), and offers Regenerate; the memo itself stays readable and exportable as it was. The Chronology tab's head reads "12 events on the chronology. The memo was written on 10 of them." and the case page's Incidents tab line reads "memo written 17 Sep" with "2 events newer" when stale, or "no memo yet".
- **One memo per Incident.** Regenerate replaces it; the Word export is how an earlier one is kept. The memo goes with the Incident: deleted with it, into the Recycle bin with the case and back.
- **The incident record**, made by the app with no engine call, is what the memo is written from: every synced camera's Digest with each line's times rewritten from the recording's own to the Incident clock (the recording's time plus the camera's start), each line prefixed with the camera's name, the lines of all cameras merged in time order. A camera with no Digest contributes its transcript's lines the same way, rewritten and prefixed, while the whole fits the engine's window beside everything else; when it does not, the transcript-only cameras drop to a line saying the camera ran from one time to another and its words were not read, the longest first, and the memo's "written from" line says so. An Incident that still does not fit fails as `llm_too_long` with "The incident is too long for one memo. Prepare its videos so their Digests can stand in for the transcripts." Nothing of the record is stored; it is made for the call and shown to nobody, though an Admin's Details fold on the Incident page says how many lines it had and from which cameras, as the Digest's fold does.
- **What the memo is given.** The Ground rules; the **Incident memo** template; the narrative rules (fixed); a fixed block of incident rules: every time is written as the time of day by the Incident clock in the form `[hh:mm:ss]`, never a recording's own elapsed time; a sentence that rests on an Event carries its number as `(Event 4)` after the time; what one camera shows and another does not is said by the camera's name; a camera's description of the picture stays a description; a Speaker's label is per camera, so a numbered label means nothing across cameras and a line is attributed to a person only by a name the words give or the office set, otherwise to the camera it was heard on; the memo covers every camera it was given and names none it was not. Then the Incident line (name, date, the cameras with their starts and ends by the clock and how each was placed, said as the pills say it), the Chronology as the office wrote it ("Event 1, 21:57:02, Vehicle stopped on the shoulder; seen on Dash cam unit 12, BWC2-098679; added by a person" and "from the words on BWC2-098679" for a quoted one), the incident record under a heading of its own, and the Length line (the Detailed length). No Focus; the memo has one shape.
- **The shape**, in the Incident memo template's shipped wording, a memo a member of staff hands to an attorney, across cameras: **Summary** (one paragraph a reader in a hurry could stop at, with the date and the times of day the incident ran); **The cameras** (one line each: what the camera is, when it starts and ends by the clock, whose it is only as the words say); **People** (as the Body camera summary has it, and which cameras show each); **What happened** (the substance in paragraphs, each on one subject, the Events in their order, what each camera adds where it adds something); **Commands, warnings, and rights** (every one spoken, quoted exactly with the speaker's label, the time of day and the camera it was heard on); **Statements that matter**; **Names, places, and dates**; **Unclear parts** (a stretch no camera showed, a thing the cameras or the words disagree on, and an Event the record does not bear out, said plainly). No closing section of points for the attorney, as Phase 4 decided. Third person, past tense, plain words; grouped by subject inside What happened, never minute by minute. The template is editable and resettable on the Templates page, following the shipped wording while unedited.
- **The call**, on the engine's lane, one job, feature `incident_memo`, thinking as the switch says (the memo is a Summary in kind), capped at **Incident memo answer cap** (4,000 tokens; a cap hit shown as "The memo was cut short."), within **Incident memo time limit** (600 seconds, doubled while the model may think). The audit row is the AI assistant call with the cameras drawn on, the Events written on and whether it was cut; never a word.
- **Citations.** A `[hh:mm:ss]` in the memo that falls inside the Incident's span is a citation that plays every camera from there, on the page and from the export's table of contents; one that does not stays plain text. An `(Event n)` is the Event's mark, as the mock-up draws it, and a press on it seeks the Event and shows it on the Chronology tab. The memo's text is the assistant's; the app changes no word of it.
- **Memo to Word**: the app's export shape (the office's name and logo on the cover as the other exports carry them): the title "Incident memo: <incident>", the case, the Incident clock's date, the cameras with how each was placed and which were left out, the AI notice, the memo with the times as printed and the Event numbers as printed, and then the Chronology as its last pages, the table and the strip as a picture exactly as chapter 2's Chronology to Word has them, so the two travel together. The audit row is **Incident memo exported**. Offered to whoever can open the Incident; a Collaborator exports as the owner does. Download everything and the case's Download all transcripts do not carry it, as they do not carry the Chronology.
- **Who may write it.** Whoever can open the Incident, as a Summary in a case is written by whoever can open the recording. The memo remembers who asked for it.

### What changes from chapters 1 and 2 and earlier phases

- **Phase 2, the Case Chat chapter, and Phase 4 chapter 4, The chat**: the Incident block after the People line and the two sentences in the Case chat template, under the switch Case chat knows the incidents.
- **Phase 4 chapter 7, The templates**: two prompt templates join the Templates page, **Proposed events** and **Incident memo**, editable, resettable, following the shipped wording while unedited; the incident rules join the fixed rules that are never edited.
- **Phase 4 chapter 8**: the AI assistant call gains features `incident_events` and `incident_memo`; the never-logged list gains a proposal's line and the words it rests on, the memo, and the incident record.
- **Chapter 1, The Incident page**: the tabbar reads Chronology, Memo, Cameras, Details; the Details fold for an Admin says what the last memo's record held. The case page's Incidents tab line gains the memo's state.
- **Chapter 2, Events**: the source **assistant** and the proposed state are made; the Word export's AI notice line prints, as chapter 2 provided, when any Event's source is assistant; the Chronology tab's head gains "The memo was written on N of them."
- **Phase 1, the Exports chapter**: a fifth export kind, the Incident memo, in the same shape and under the same audit row pattern.
- Nothing changes in the viewer, in a recording's own Summary or Chat, in Vision, or in the Speaker check.

### Audit rows

Category LLM: **AI assistant call** with feature `incident_events` (the camera's number in the run, the proposals kept) and `incident_memo` (the cameras drawn on, the Events written on, whether it was cut). Category Cases: **Events proposed** (how many, from how many cameras, on a run's end), **Event added** with source assistant on an Accept (chapter 2's row), **Event dismissed**. Category Exports: **Incident memo exported**. None holds a word of a proposal, an Event, or the memo, a camera id, or a time.

### Settings

On the Incidents page, a group **The assistant**, every row greyed while Incidents is Off or the AI assistant is Off: **Case chat knows the incidents** (On); **Assistant proposes events** (On); **Proposed events answer cap** (2,000 tokens); **Proposed events time limit** (180 seconds); **Incident memo** (On; Off hides the Memo tab and keeps every memo); **Incident memo answer cap** (4,000 tokens); **Incident memo time limit** (600 seconds). On the Templates page, the **Proposed events** and **Incident memo** prompt templates.

### Not in this phase

- **Proposals made by themselves**, as the vision lands or the memo is written, and **accepting the sure ones automatically**: later switches, once an office has watched the proposals for a while.
- **A memo per camera** (that is the recording's Summary), **a memo across Incidents**, and **a Chat grounded in one Incident** (the Case Chat with the placements is that).
- **Proposals from the picture alone** on a camera with no Digest: the assistant proposes from what the Digest or the transcript carries.
- **The memo in Download everything**, as the Chronology is not.
- **Editing the memo in place.** The memo is the assistant's text under the AI notice; a person's account is the Chronology.

### Left to the build

- The proposals' answer shape and the most per camera, within the rule that every proposal rests on a real line; the window for a camera read from its transcript.
- The exact wording of the state lines, the stale line and the "written from" line.
- Whether the Case Chat prints the time of day beside each line of a synced camera's Digest, within the rule that citations stay the recording's own time.
- The incident record's line shape and the order in which transcript-only cameras drop to a line when the whole does not fit, within the rule that the longest goes first and the memo says so.
- The Word document's layout for the memo with the Chronology as its last pages, in the app's export shape.

## 4. The Incident page, laid out for watching

Written 2026-09-17, after v1.61.0 had gone to the server, from the maintainer's finding that the page is "a bit smushed" and the ask to make it more intuitive, and the choice made the same day from three mock-ups (`docs/spec/mockups/phase-6-layouts.html`): one camera large with the others in a filmstrip under it, and a Layout menu that also gives the cameras side by side with the strip at the bottom. Chapters 1 to 3 are unchanged in what the page does; this chapter changes where things sit and how much room the pictures get.

### Principles

1. **The pictures come first.** Whatever the layout, the cameras get the width and the controls stay out of their way: one head, one transport, one strip.
2. **One camera at a time is how people look; every camera in step is the point.** The Focus layout gives one camera the room to be read and heard while the rest play small in step, and any of them is one press from the front.
3. **The person chooses, the app remembers.** The Layout menu is the person's; the browser keeps the choice as it keeps Across today, and the office sets what a new person starts with.
4. **Nothing present is taken away.** Every control of chapters 1 to 3 stays on the page; some move, some shrink, none goes.

### Words

**Layout**, as `CONTEXT.md` defines it from this chapter: the Incident page's arrangement, one of **Focus**, **Side by side**, and **Grid** (2, 3 or 4 across). The large camera in Focus is the **focus camera**; the row of small ones under it is the **filmstrip**. The pages never say view mode, multiview, mosaic or split screen.

### The Layout menu

- In the transport, in the place Across held: **Focus** (the shipped default), **Side by side**, **Grid, 2 across**, **Grid, 3 across**, **Grid, 4 across**. One press changes the layout at once, keeping the moment, whether it is playing, the sound and Follow.
- The choice is kept in the browser per person, as Across was; a new person starts with the office's **Incident layout** setting. Below 1280 pixels every layout folds to one column: the cameras, the transport, the strip, the panel.

### Focus

- **The focus camera** is one tile that takes the stage's width, beside the work panel (about a third of the width on a wide screen). Its head is a tile's head; its picture is as large as the width allows; under it the line being spoken in the viewer's reading size, with + event on hover, and the camera line's + event for a video with vision.
- **The filmstrip** under the focus: every other camera of the Incident as a small tile (about 170 pixels wide), in the Wall's order, with its colour dot, its id and a short pill, playing in step and muted. A press on a tile makes it the focus and puts the former focus in its place in the strip; tiles are dragged into place as the Wall's tiles are today. A camera that has not started at the moment is dimmed with "in 0:41"; one that has ended is dimmed with "ended". The Cameras on the wall setting says how many filmstrip tiles play live; beyond it a tile is parked as today (its id and pill, no picture) and a press swaps it in and makes it the focus.
- **The sound follows the focus** unless a person pins it: the speaker icon on any tile takes the sound and keeps it there through focus changes; a press on the icon of the focus camera lets the sound follow again. The transport says which camera is heard.
- **The work panel** beside the focus holds the Chronology, Memo, Cameras and Details tabs as chapters 2 and 3 have them; the transport sits under the filmstrip and the strip under the transport, across the whole width.

### Side by side

- Every camera at the same size in a grid on the left: two across at four cameras or fewer, three across at five or more, in the Wall's order, dragged into place as today; the work panel on the right; the transport and the strip across the whole width at the bottom. This is today's page with the tidy-ups below, and the layout for comparing cameras while reading the chronology.

### Grid, 2, 3 or 4 across

- The cameras alone across the whole width at the chosen count, the transport and the strip under them, and the work panel under the strip at the full width. The layout for a wall of pictures and nothing beside them; the chronology is a scroll away.

### Tidy-ups, in every layout

- **Tile heads lighter**: the colour dot, the camera id, one short pill (**Clock**, **Clock?** for unchecked, **Sound**, **File**, **Hand**, **Guess**, each with chapter 1's full words as its hover title), the speaker icon, **Sync**, and the three-dot menu. The Sound radio button and its label go.
- **Sound is one press**, the speaker icon on a tile; the Sound from list leaves the transport, which shows the heard camera's id instead.
- **Parked cameras live in the strip** as thin lanes with **Swap in** on the lane's head; the row of parked tiles under the transport goes.
- **The event box is a sheet** that opens over the head, at the right, and never pushes the page down; Escape and Cancel close it as today.
- **The words under a tile** keep the small size on a grid or filmstrip tile and take the viewer's reading size on the focus camera.
- The head, the strip, the tabs and every action stay as chapters 1 to 3 have them.

### What changes from chapters 1 to 3

- **Chapter 1, The Incident page**: the Wall is one of three layouts; the parked tiles move into the strip; the tile head's pill is short with the full words on hover; the Sound radio and the Sound from list are replaced by the speaker icon; Across is replaced by the Layout menu; the event box is a sheet. The 1280 pixel rule stays; the 1900 pixel rule widens the work panel as before.
- **Chapters 2 and 3**: nothing but where the panel sits.
- **Amendment v1.60.0**: Across (Auto, 2, 3, 4) is withdrawn in favour of the Layout menu; the wall's grid rules survive as the Grid layouts.

### Audit rows

None. A layout is the person's browser's, not a case's activity.

### Settings

**Incident layout** on the Incidents page, under The wall: Focus (shipped), Side by side, Grid 2, Grid 3, Grid 4; the layout a person starts with before they choose. Cameras on the wall keeps its meaning as the count of pictures that play live at once.

### Not in this chapter

- **Two focus cameras** side by side with the filmstrip under both. A later ask if staff want it.
- **A pop-out window** for the focus camera. Chapter 1 ruled Open in a window out of the page.
- **Keyboard focus switching** (number keys to the cameras). Left to a later tuning pass; the number keys are the viewer's speaker keys.

### Left to the build

- The filmstrip tile's exact width and the focus picture's proportion, within the rule that the focus camera takes the stage's width.
- The 1280 pixel fold's order and the filmstrip's scrolling when it does not fit.
- The short pills' exact words.
- Whether the sheet's opening steals the focus from the transport's keys (it should not while the box is closed).

## 5. Sync, one control

Written 2026-09-19, after v1.65.0, from the maintainer's list of the same day: "we need to refine the sync functionality, maybe we have a single sync button that then allows selecting the specific videos or a 'sync all' feature. How do we handle a timestamp detection or sound sync attempt failure? Upon testing it looks like the auto sync feature utilizing embedded timestamps works well." Chapter 1 gave every camera a place and five ways to it; the tuning pass (v1.60.0) put Sync on every tile and on the Cameras tab. This chapter puts the whole of syncing behind one button, lets the app do the rounds by itself in the order that works, and says plainly what it could not do and what to do next.

### Principles

1. **One button, and the app does the rounds.** **Sync** in the transport opens one sheet with every camera on it. **Sync all** has the app try each camera in the order that works: its clock when the picture carries one and the read was checked, then the clock unchecked, then the sound against a camera already in step, and only then a person's hand. A person presses once and reads the result; nothing is typed until the app has said it cannot.
2. **Every failure has a next step.** A camera the app could not sync is not a pill saying so; its row says why in plain words (no clock in the picture; the clock was read from one frame only; the sounds did not line up; the file carries no time) and offers what a person does next, on the same row.
3. **Nothing learned is lost.** The five ways of chapter 1 stand, the pills stand, the audit rows stand, and the tile's Sync and the Cameras tab's Sync stay as doors to the same sheet with that camera's row open. Dragging a bar on the strip stays.
4. **A clip from the strip.** The strip is where a person sees the moment; dragging across it should give the clip. Phase 7 chapter 1's clip box opens with the dragged span, and the clip is cut whatever the cameras' sync state, with the page saying so.

### Words

**Sync** (the button, the sheet), **Sync all**, **Sync ticked**, **needs a hand** (the state of a camera the app could not sync). The pages never say auto-sync, calibrate, align, offset or drift.

### The Sync sheet

- **Where.** **Sync** in the transport, beside Layout, opens the sheet under the head where the event and clip sheets open. The tile's Sync button and the Cameras tab's Sync open the same sheet with that camera's row expanded. Escape or Done closes it.
- **The rows.** One row per camera, in the Wall's order: the colour dot and camera id, the clock pill (the stamp read from the picture: "06/07/2025 21:56:19, checked", "unchecked", "no clock in the picture", "not read yet"), the placed pill as chapter 1 has it, who synced it and when, a tick box, and the row's controls.
- **Sync all** at the top runs the rounds on every camera not yet synced (a synced camera is left alone); **Sync ticked** runs them on the ticked rows only, synced or not, so a person can redo one. Either is one press; the sheet stays open and polls while the app works.
- **The rounds**, per camera, each tried only when the one before did not sync it:
  1. **From its clock, checked**: the stamp was read from two frames and the clock moved on between them. Placed at once.
  2. **From its clock, unchecked**: the stamp was read from one frame. Placed, and the row says "from its clock, read once: listen to a moment where two cameras hear the same thing" with **Listen** (seeks every camera to the first moment the two run together and plays them, the sound from the other camera).
  3. **Matched by sound**: while Match by sound is On and some other camera is synced, queued against the synced camera with the longest overlap; a strong match places it; a weak one is shown as chapter 1 has it, with **Use it anyway**; none is said with the reason.
  4. **Needs a hand**: the row says why in one line and shows the controls: the nudges (a second and a tenth either way, while the cameras play with the sound from one), **Type a time**, **From its file** when the file carries a time, and **Match the sound** against a chosen camera.
- **The state line**, at the top of the sheet while the rounds run and after: "Syncing 6 cameras: 3 from their clocks, 1 matching the sound, 2 need a hand", then "5 synced, 1 needs a hand". A camera being matched shows "matching the sound, about a minute". The line is the page's, not stored.
- **Not read yet.** A camera whose stamp has not been read (the playback copy is not there, or Stamp reads early is Off and the vision has not run) is queued for the read as chapter 1's early read does, when the engine is on, and its row says "reading the clock..."; with no engine it needs a hand.
- **The Cameras tab** keeps its table and its placed pills, who synced and when, and one Sync per row that opens the sheet; the per-row Match the sound control and its select leave the tab for the sheet.
- **Audit.** Nothing new: each placement writes Camera placed with how, as chapter 1 has it, and a sound match its rows. Sync all is a press, not a row.
- **Settings.** None new. Match by sound and Stamp reads early gate their rounds as they gate the controls today.

### The clip from the strip

- **Dragging on the ruler** (the ticks row above the lanes), or dragging on a lane with Shift held, draws a band across the strip; on release the clip box of Phase 7 chapter 1 opens with that span, no event needed. Escape while dragging cancels; the band stays while the box is open and goes when it closes.
- **The box** is the chapter 1 box with these differences: the title starts as the span's times ("21:57:02 to 21:57:40"); every camera with a playback copy that runs inside the span is offered and ticked, synced or not; a camera not synced shows its placed pill in the row and the box carries one line above the cameras, in the warning tone: "A camera not synced is cut at its guessed place, so its tile may not play in step. Sync it first for a clip that does." The person may go on.
- **What is made** is chapter 1's file, cut at the cameras' places as they stand, the clock burned from the Incident clock. The Clip has the Incident and no Event; on the Clips tab and page its line under the title reads "from the strip, 21:57:02 to 21:57:40" instead of "from the event ..."; the Chronology's Word export lists it under the events' clips as "from the strip". Render again cuts at the places as they stand then, so a camera synced after the clip was made plays in step on the next render.
- **Chapter 1's principle 3** ("there is no clip from nowhere: add the event first") is amended: a clip is cut from an event or from a span dragged on the strip; the event's clip keeps its mark on the event's row, the strip's clip has none.
- **Who may**: as chapter 1.

### In and out

- **In**: the Sync sheet with Sync all, Sync ticked, the rounds, the state line, the per-row next steps; the Cameras tab's Sync opening the sheet; the clip from a span dragged on the strip, unsynced cameras allowed with the warning; the Clips words "from the strip".
- **Out**: a sync that runs by itself when a camera joins (it is a press), matching by the picture, a drift correction along a recording, and a clip from more than one span.

### What changes from chapters 1 to 4 and Phase 7 chapter 1

- **Chapter 1, Placing a camera and The Incident page**: the Sync sheet is the one place; the tile's Sync and the Cameras tab's Sync open it; the rounds order the five ways; the wording of the failures.
- **Chapter 4, the transport**: a Sync button beside Layout.
- **Phase 7 chapter 1, The clip across cameras**: the box opens from the strip as well as from an event; a camera not synced may be ticked, with the warning; the Clip may have no Event; the Clips words and the Word export's line for a strip clip; principle 3 amended. `docs/spec/SPEC-PHASE-7.md` carries a pointer.

### Audit rows

None new.

### Settings

None new.

### Not in this chapter

- **A sync by itself** as cameras join or their stamps are read; a press stays the rule until an office has watched Sync all for a while.
- **Matching by the picture** (a flash, a door), and **drift** between cameras whose clocks run at different speeds.
- **A clip from several spans** joined.

### Left to the build

- The sheet's layout on a narrow window (rows that wrap, controls under the row).
- The exact wording of the reasons and of the state line, within the substance above.
- How the "longest overlap" partner for a sound match is chosen when two cameras tie.
- The drag threshold for the band (a few pixels) and its colour; whether a band may be dragged on a lane without Shift once the bar drag of chapter 1 is not in the way.

## 6. Deferred and ruled out

- **A Clip across cameras** (side by side, one file): deferred by the maintainer on 2026-09-17, and taken up as Phase 7 chapter 1 (`docs/spec/SPEC-PHASE-7.md`) the same day.
- **Sound recordings in an Incident**: deferred; not asked for.
- **Incidents across cases, and any list of Incidents outside a case**: ruled out, as Phase 2 rules out anything that crosses a case's edge.
- **Re-encoding or stitching the cameras into one file**: ruled out; the browser plays the playback copies as they are, and nothing new lands on disk.
- **Reading the clock from anything but the picture, the file, the sound and a person**: ruled out; the app never invents a time.
- **Frame-accurate sync**: ruled out for this phase; see chapter 1.
- **Reconciling Speaker labels across the cameras of an Incident** (the same person is Speaker 1 on one camera and Speaker 4 on another): deferred by the maintainer on 2026-09-17 as a bigger problem than this phase. An Incident is the one place the app will ever hold the evidence for it, since the cameras are in step and a person talking during the same seconds on two cameras with the same words is one person, so a later chapter could propose matches from that overlap, with voice prints (Phase 5 chapter 2) for the rest; the names would then flow through the case. Until then the Incident page shows names and hides numbers. Taken up as Phase 7 chapter 3, people across cameras, from the overlap of speech.
- **A tuning pass over the Incident page** from staff's first use (2026-09-17, the maintainer: "it's gonna need some fine tuning to make it all very intuitive for users"): done as v1.60.0 and v1.60.1 (see the amendments); a second pass follows chapter 3 on the server the same way.

## Appendix A. Audit rows added in Phase 6

| Category | Row | Chapter |
|---|---|---|
| Cases | Incident made; Incident changed; Incident deleted; Camera placed | 1 |
| Cases | Event added; Event changed; Event removed | 2 |
| Exports | Chronology exported | 2 |
| LLM | AI assistant call, features `incident_events` and `incident_memo` | 3 |
| Cases | Events proposed; Event dismissed | 3 |
| Exports | Incident memo exported | 3 |

## Appendix B. Settings added in Phase 6

| Setting | Page | Default | Chapter |
|---|---|---|---|
| Incidents | Incidents | On | 1 |
| Incidents proposed | Incidents | On | 1 |
| Cameras on the wall | Incidents | 6 | 1 |
| Most cameras in an incident | Incidents | 20 | 1 |
| Stamp reads early | Incidents | On | 1 |
| Match by sound | Incidents | On | 1 |
| Case chat knows the incidents | Incidents | On | 3 |
| Assistant proposes events | Incidents | On | 3 |
| Proposed events answer cap | Incidents | 2,000 tokens | 3 |
| Proposed events time limit | Incidents | 180 seconds | 3 |
| Incident memo | Incidents | On | 3 |
| Incident memo answer cap | Incidents | 4,000 tokens | 3 |
| Incident memo time limit | Incidents | 600 seconds | 3 |
| Incident layout | Incidents | Focus | 4 |

And, in chapter 3, the Proposed events and Incident memo prompt templates on the Templates page.

## Sources

The maintainer's ask and answers of 2026-09-17, and the mock-ups chosen the same day (`docs/spec/mockups/phase-6-incidents.html`) and the layout mock-ups chosen after v1.61.0 (`docs/spec/mockups/phase-6-layouts.html`); the Phase 2 Cases, Sharing, Retention policy, Case Chat and Backup chapters; Phase 4 chapter 3 (the stamp and the Digest), chapter 4 (the memo and the chat) and chapter 7 (the templates); Phase 5 chapter 1 (the Lanes) and chapter 3 (propose, never apply); `docs/research/media-pipeline-facts.md` (the playback copy plays in every browser; the probe keeps the file's own facts).

## Amendments applied

- 2026-09-19 (v1.66.0): chapter 5 built the same day, with these decisions left to the build: the sheet is drawn under the head where the event and clip sheets are, and a synced camera's row folds its controls behind More; the reasons read "no clock in the picture", "the clock has not been read yet", "no match: <the worker's reason>", "a weak match; listen, then use it or nudge it", "no clock in the picture, and Match by sound is off", "no clock in the picture, and no camera in step to match against"; the state line reads "Syncing 6 cameras: 3 from their clocks (1 read once), 1 matching the sound, 2 need a hand" or "Every camera is synced already"; the sound match partner is the synced camera with the longest overlap, the earlier on a tie; a camera whose stamp is not read yet goes to the sound round rather than waiting for the engine; the band needs a drag of more than three pixels and a span of at least a second, drawn in the accent colour on the ruler, dragged on the ruler alone (the lanes keep the bar drag); a strip clip's picture carries from_strip so a clip whose event was removed later is still told apart; the strip clip's default title is its span; an event's clip keeps the synced rule while the strip's allows the guess.
- 2026-09-19: chapter 5 written for the build (Sync as one control with Sync all and the rounds, every failure with its next step; the clip from a span dragged on the strip, unsynced cameras allowed with the warning), from the maintainer's list of 2026-09-19; Deferred and ruled out becomes chapter 6.
- 2026-09-19 (v1.63.2): from the maintainer's list. While the proposals run is going, Accept, Dismiss and Accept all are greyed and refused (a proposal accepted mid-run was proposed again by the cameras read after it). The strip zoomed in draws only the part of a bar inside the window, and the window moves with the wheel over the lanes or the arrows beside the zoom buttons, following the playhead again once it plays out of view.
- 2026-09-17: chapter 4 built as v1.62.0 the same day, with these decisions left to the build: the filmstrip tile is 170 pixels wide and the row scrolls sideways when it does not fit; the focus picture keeps the 16:9 well; below 1280 pixels the order is the cameras, the transport, the strip, the panel, as chapter 1 had it; the short pills read Clock, Clock?, Sound, File, Hand, Guess; the sheet does not take the transport's keys; the sound follows the focus only in Focus, and in the other layouts a press on a speaker simply picks the camera; a parked lane's Swap in and a filmstrip's parked tile both bring the camera to the front; the panel moves under the strip in a Grid by moving the one element, so the tabs keep their state.
- 2026-09-17: chapter 4 written for the build after v1.61.0 on the server, from the maintainer's finding ("the incident layout is a bit smushed") and the choice of the Focus layout with a Layout menu that also gives Side by side; the Deferred and ruled out chapter becomes chapter 5.
- 2026-09-17: chapter 3 built as v1.61.0 the same day, with these decisions left to the build: the proposals' answer is a JSON list of up to sixty items per call, thirty kept per camera, each item the time in the recording, an end, the line and the words it rests on, the first forty folded characters of which must be found in what the camera was given; a transcript-only camera is read in as few calls as fit the window, whole lines only; a dismissed proposal is kept as a dismissed row and a later run offers nothing within five seconds of it on the same camera; the incident record's line shape is "camera: [hh:mm:ss] ..." with a Digest line's number dropped and a transcript line's numbered label dropped, hh:mm:ss into the incident when it has no clock; transcript-only cameras drop to a line the longest first; the memo is one row per Incident, reset by Regenerate; its citations are the [hh:mm:ss] inside the span and its marks the (Event n) of the Chronology's numbering at the time of writing; the Word export prints the memo's parts as headings, then the Chronology's pages after a page break. The speaker-label rule is applied in the lines endpoint (a numbered label blanked), in the record, and in the fixed incident rules.
- 2026-09-17: Speaker labels on the Incident page: a name set or accepted on a recording's Speakers page carries over; a numbered label does not show, on the page, in the event box, on the Chronology, or to the assistant. Reconciling labels across cameras is deferred (chapter 5). For the build with chapter 3.
- 2026-09-17: chapter 3 written for the build after v1.60.1, from the maintainer's asks (the memo across cameras on a page of its own, people's Events first with the assistant proposing later, the memo written on the Chronology, and the chronology as a smarter presentation built on the model's summaries); the incident record, the app's merge of the Digests onto the Incident clock, is what the memo is written from.
- 2026-09-17 (v1.60.1): Sync is a button on every tile's head, not a menu entry; the Wall follows the saved order; Add cameras is drawn from the page's state.
- 2026-09-17 (v1.60.0): the tuning pass from the maintainer's first use. Sync is the one control for a camera's place, on a menu at each tile's top right (Sync this camera, Swap out, Open the recording, Remove from incident) and on the Cameras tab; a camera with no clock is on the Wall at the app's guess (the file's time when the Incident has a clock, else the Incident's start) marked Not synced yet, so Not placed no longer keeps a camera off the Wall and the pill Placed by hand reads Synced by hand; tiles are dragged into place; Across in the transport (Auto, 2, 3, 4) sets the columns, Auto using four on a screen 1900 pixels wide or wider, where the work area also widens; the camera line under a tile is withdrawn (the words stay); the Clock column leaves the recordings tab and a video with no clock shows nothing rather than a warning. All cameras and the sound match wait for a camera to be synced, not merely guessed.
- 2026-09-17 (v1.59.1): the case page's doorway is an Incidents tab beside Chat, at the maintainer's word after v1.58.0 on the server ("the incident floats on top of the cases page, that's not intuitive"); the strip under the case name and the header's New incident go; the tab lists the Incidents with their Events count, the offers, New incident, and every video with its clock. Held as a later step: a tuning pass over the Incident page once staff have used it.
- 2026-09-17: chapter 2 built as v1.59.0 the same day, with these decisions left to the build: the picture is 1000 by (34 + 22 per camera + 76) points at twice the screen's resolution, the ruler with seven ticks, a label drawn only when its left edge clears the previous label's right edge and a mark alone otherwise, and the events numbered as in the table; the Word document carries the cameras table before the picture and the events table after it, at 6.5 inches wide; the event box is one form under the head for new and Edit alike, its cameras ticked from the placed cameras running at the moment; the viewer's All cameras carries the line being spoken and a citation carries its own line into the address as `event=`, and the viewer's own Summary and Chat citations carry the moment alone; the Chronology tab opens by default once any camera is placed; the E key opens the box and Escape closes it.
- 2026-09-17: chapter 1 built as v1.58.0 the same day, with these decisions left to the build: the sound match compares each camera's loudness in 20 ms frames against the two seconds around it and cross-correlates the two with a fast Fourier transform, scoring each shift by the overlap and taking the best score over the best score three seconds away as its strength, 1.5 and over applied (`docs/research/sound-match.md`; the probe on the office's own files is still owed and the `sound_match` command is for it); a follower is nudged by its rate when it drifts over 80 ms and seeked when over half a second; the Wall's grid is three across, two across for two or four cameras and under 1280 pixels, one for one; From its file needs the Incident to have a clock, since a file time is not a clock of its own; the case page's Clock column shows the date with the time; an unchecked clock places a camera but does not become the Incident's clock; an Incident's first checked clock, by start, is its zero; the file's own time is shown in the office's time zone (`TZ`); the offer's key is the sorted set of recording ids, so a set once put away stays away until a video joins it. NumPy joins the app image for the match.
