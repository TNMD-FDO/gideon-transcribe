# Gideon Transcribe, Phase 6 specification

The Incidents release. Chapter 1 was built as `v1.58.0`; chapter 2 is written for the build; chapter 3 is proposed and takes its shape here so that the earlier chapters leave room for it.

## About this document

This is the build specification for Phase 6 of Gideon Transcribe: several cameras of one event played together. An office's case often holds more than one video of the same minutes, the body-worn cameras of every officer at a stop and the in-car camera of each unit, and today each is a recording of its own, opened one at a time. The maintainer asked on 2026-09-17 for "the ability to upload multiple body worn camera videos and have them sync so they play at the same time", for a "visual timeline that can also be exported and integrated within the investigative analysis by staff", and for the assistant to see across the cameras, all of it "a separate area" of the case. It builds on Phase 2 (`docs/spec/SPEC-PHASE-2.md`, Cases and the Case Chat), Phase 4 (`docs/spec/SPEC-PHASE-4.md`, the camera stamp and the Digest) and Phase 5 (`docs/spec/SPEC-PHASE-5.md`, whose Lanes are the shape of this phase's strip), and changes nothing in them beyond what each chapter's "What changes from earlier phases" lists.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 6 words Incident, Incident clock, Placed, Wall, Chronology, and Event), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the Incidents page), and the mock-ups the chapters were drawn from, `docs/spec/mockups/phase-6-incidents.html`, one page of seven screens in the app's own look. The mock-ups show the whole of the three chapters; a screen says which chapter builds each part.

Nothing in this document is office-specific. No new environment key is needed and no new service: the cameras are played by the browser, the placements are rows, and the one engine call this phase adds is one the app already makes. The conventions of the Phase 1 document apply here unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing leaves the building.

## What Phase 6 adds

- **Incidents, and the cameras in step** (chapter 1, for the build): a case's videos that ran at the same time become an Incident, offered by the app when their clocks overlap and made by hand otherwise. Each camera is placed on one clock, the time of day the cameras burn into their pictures, read as each playback copy lands; a camera without a clock is matched by sound to one that has, or placed by hand, and how each was placed is shown wherever it appears. The Incident page is a page of its own inside the case: up to six cameras playing in step under one transport and one clock, sound from one of them, a strip across the width with a lane per camera, and the words and the camera line under each picture. An Incidents page in the Panel holds its switches.
- **The Chronology** (chapter 2, for the build): the Incident's list of Events, each a time of day on the Incident clock, a line of text, its source (a person, the words of a camera, or what a camera showed) and the cameras that show it, added by a person at the moment being watched, from a line under a tile, or from a chat's citation; drawn as the strip's Events lane; listed on the Chronology tab with a citation that plays every camera from there; and exported as a Word document with the strip as a picture, as a spreadsheet, and as the picture alone.
- **The assistant on the Incident** (chapter 3, proposed): the Case Chat told each camera's place on the clock, so a time on one recording is the same moment on the others; All cameras on a citation; Events the assistant proposes from the words and the cameras, accepted one by one; and the Incident memo, written across every camera on the Chronology's events, each cited, on the Incident page's Memo tab.

Chapter 1 adds an Incidents settings page with six settings, four audit rows, two tables, and one migration that moves the camera stamp from the Transcript to the Recording. Chapter 2 adds one table, four audit rows, three exports and no setting.

## Contents

1. Incidents, and the cameras in step
2. The Chronology
3. The assistant on the Incident (proposed)
4. Deferred and ruled out

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
- **The Wall.** Up to **Cameras on the wall** (six shipped) placed cameras, in a grid the build chooses for one to nine (three across at six), in the order of their start on the clock unless a person reorders them. Each tile: the camera id from its stamp when there is one, else the recording's title, with its colour dot, its Placed pill, Sound, and a menu (Sync this camera, Swap out, Open the recording, Remove from incident); the picture; and under it the line being spoken on that camera, in that camera's Speaker colours (the camera line under a tile was withdrawn in v1.60.0). Tiles are dragged into place, and **Across** in the transport sets the columns. A tile whose camera has not started at the clock's moment shows "Starts in 0:47" over a dark picture; one whose camera has ended shows "Ended at 21:57:30"; the tile stays, so the Wall does not rearrange itself while playing. The remaining placed cameras are listed under the Wall as parked tiles with **Swap in**, which takes a camera off the Wall (the one the person picks, or the last) and puts this one on; the swap is remembered for the Incident.
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

## 3. The assistant on the Incident (proposed)

Not yet written for the build; the shape decided on 2026-09-17.

- **The Case Chat is told the placements.** One line per placed camera after its nature line ("Recording 3, Dash cam unit 12, starts at 21:55:44 by the cameras' clocks and runs 41 min 26 s"), so a question about one camera's moment is answered from every camera at that moment; asked what another camera showed, it reads the description whose span holds the same clock time. **All cameras** beside a citation is chapter 1's; the answer giving the time of day is this chapter's.
- **Proposed Events.** On request from the Chronology tab, the assistant reads the cameras' Digests on the Incident clock and proposes Events, each with its time, its line, its source camera and the words or the description it rests on; they sit under Proposed by the assistant with Accept and Dismiss and join the Chronology only when accepted, on the Speaker check's pattern of propose, never apply.
- **The Incident memo.** On the Incident page's **Memo** tab: a memo in the shape of Phase 4's memos, written across every placed camera from their transcripts and Digests on the Incident clock, on the Chronology's Events, each cited by its clock time so the citation plays every camera; a sentence written on an Event carries the Event's mark. The memo says which cameras it drew on and which it left out (not placed); when Events change after it was written the tab says so and offers Regenerate. Its instructions are the **Incident memo** template on the Templates page. Its Word export carries the Chronology as its last pages.
- **Rows and settings.** Audit rows for the proposals and the memo as the AI assistant call with features `incident_events` and `incident_memo`; settings Assistant proposes events (On), the memo's answer cap and time limit, on the Incidents page; the template.

## 4. Deferred and ruled out

- **A Clip across cameras** (side by side, one file): deferred by the maintainer on 2026-09-17.
- **Sound recordings in an Incident**: deferred; not asked for.
- **Incidents across cases, and any list of Incidents outside a case**: ruled out, as Phase 2 rules out anything that crosses a case's edge.
- **Re-encoding or stitching the cameras into one file**: ruled out; the browser plays the playback copies as they are, and nothing new lands on disk.
- **Reading the clock from anything but the picture, the file, the sound and a person**: ruled out; the app never invents a time.
- **Frame-accurate sync**: ruled out for this phase; see chapter 1.
- **A tuning pass over the Incident page** from staff's first use (2026-09-17, the maintainer: "it's gonna need some fine tuning to make it all very intuitive for users"): held as the step after chapter 2, before or beside chapter 3.

## Appendix A. Audit rows added in Phase 6

| Category | Row | Chapter |
|---|---|---|
| Cases | Incident made; Incident changed; Incident deleted; Camera placed | 1 |
| Cases | Event added; Event changed; Event removed | 2 |
| Exports | Chronology exported | 2 |
| AI assistant | AI assistant call, features `incident_events` and `incident_memo` | 3 (proposed) |

## Appendix B. Settings added in Phase 6

| Setting | Page | Default | Chapter |
|---|---|---|---|
| Incidents | Incidents | On | 1 |
| Incidents proposed | Incidents | On | 1 |
| Cameras on the wall | Incidents | 6 | 1 |
| Most cameras in an incident | Incidents | 20 | 1 |
| Stamp reads early | Incidents | On | 1 |
| Match by sound | Incidents | On | 1 |
| Assistant proposes events; Incident memo answer cap; Incident memo time limit | Incidents | On; to be fixed; to be fixed | 3 (proposed) |

And, in chapter 3, the Incident memo template on the Templates page.

## Sources

The maintainer's ask and answers of 2026-09-17, and the mock-ups chosen the same day (`docs/spec/mockups/phase-6-incidents.html`); the Phase 2 Cases, Sharing, Retention policy, Case Chat and Backup chapters; Phase 4 chapter 3 (the stamp) and chapter 4 (the Digest and the Case Chat); Phase 5 chapter 1 (the Lanes) and chapter 3 (propose, never apply); `docs/research/media-pipeline-facts.md` (the playback copy plays in every browser; the probe keeps the file's own facts).

## Amendments applied

- 2026-09-17 (v1.60.0): the tuning pass from the maintainer's first use. Sync is the one control for a camera's place, on a menu at each tile's top right (Sync this camera, Swap out, Open the recording, Remove from incident) and on the Cameras tab; a camera with no clock is on the Wall at the app's guess (the file's time when the Incident has a clock, else the Incident's start) marked Not synced yet, so Not placed no longer keeps a camera off the Wall and the pill Placed by hand reads Synced by hand; tiles are dragged into place; Across in the transport (Auto, 2, 3, 4) sets the columns, Auto using four on a screen 1900 pixels wide or wider, where the work area also widens; the camera line under a tile is withdrawn (the words stay); the Clock column leaves the recordings tab and a video with no clock shows nothing rather than a warning. All cameras and the sound match wait for a camera to be synced, not merely guessed.
- 2026-09-17 (v1.59.1): the case page's doorway is an Incidents tab beside Chat, at the maintainer's word after v1.58.0 on the server ("the incident floats on top of the cases page, that's not intuitive"); the strip under the case name and the header's New incident go; the tab lists the Incidents with their Events count, the offers, New incident, and every video with its clock. Held as a later step: a tuning pass over the Incident page once staff have used it.
- 2026-09-17: chapter 2 built as v1.59.0 the same day, with these decisions left to the build: the picture is 1000 by (34 + 22 per camera + 76) points at twice the screen's resolution, the ruler with seven ticks, a label drawn only when its left edge clears the previous label's right edge and a mark alone otherwise, and the events numbered as in the table; the Word document carries the cameras table before the picture and the events table after it, at 6.5 inches wide; the event box is one form under the head for new and Edit alike, its cameras ticked from the placed cameras running at the moment; the viewer's All cameras carries the line being spoken and a citation carries its own line into the address as `event=`, and the viewer's own Summary and Chat citations carry the moment alone; the Chronology tab opens by default once any camera is placed; the E key opens the box and Escape closes it.
- 2026-09-17: chapter 1 built as v1.58.0 the same day, with these decisions left to the build: the sound match compares each camera's loudness in 20 ms frames against the two seconds around it and cross-correlates the two with a fast Fourier transform, scoring each shift by the overlap and taking the best score over the best score three seconds away as its strength, 1.5 and over applied (`docs/research/sound-match.md`; the probe on the office's own files is still owed and the `sound_match` command is for it); a follower is nudged by its rate when it drifts over 80 ms and seeked when over half a second; the Wall's grid is three across, two across for two or four cameras and under 1280 pixels, one for one; From its file needs the Incident to have a clock, since a file time is not a clock of its own; the case page's Clock column shows the date with the time; an unchecked clock places a camera but does not become the Incident's clock; an Incident's first checked clock, by start, is its zero; the file's own time is shown in the office's time zone (`TZ`); the offer's key is the sorted set of recording ids, so a set once put away stays away until a video joins it. NumPy joins the app image for the match.
