# Gideon Transcribe, Phase 12 specification

The cameras on a map. A body-worn or in-car camera's export puts a small text file beside the video that says where the camera was, second by second, and what its switches were doing; the app keeps that file on the Recording as its Path file, reads it once, and draws every camera of a Case on a street map on one clock, with the video a press away and the readings answerable by Gideon anywhere in the Case. Five releases; this document holds chapter 1, the first.

## About this document

This is the build specification for Phase 12 of Gideon Transcribe. On 2026-11-02 the maintainer asked: "for some body worn camera video we receive a separate file that contains metadata related to the recording. In the metadata there's location data that tracks the movement of the officer ... there could be a separate tab in a case that utilizes that file to show the movement on a map dynamically ... users should be able to click on a camera and have that play along with it ... I want smart use of data. There's good data in these files ... chat anywhere within a case should be usable. For example when were the lights triggered or turned on. When did officer so and so turn their body camera recorder on/off ... the user should be able to add notes from this maps tab ... I want users to be able to toggle a larger view of the map ... toggle the trail movement ... click and select events." The design was worked through the same day and drawn in `docs/spec/mockups/phase-12-map.html` (figures A to L, fifteen choices), which the maintainer agreed stands. The maintainer's four answers: the street map in the first release; the word is Path; the camera's clock comes from the file, then the app's clock, then the file's name; path files come in through the Map tab only. The joins chosen from the fifteen offered: 1, 2, 4, 5, 6, 8, 9, 10 and 11.

It builds on Phase 6 (Incidents and their clock), Phase 8 chapter 2 (Notes), Phase 9 (People), Phase 10 (the case's chronology, the Recording's clock, ADR 0027, the Incidents tab's strip) and Phase 7 chapter 5 (Ask Gideon). ADR 0029 records the decisions that are hard to reverse.

Read it with `CONTEXT.md` (Path, Fix, Path file, Map, Basemap), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the Maps row) and `docs/adr/0029-the-cameras-path-is-kept-on-the-recording-and-the-map-is-drawn-from-a-file-the-office-holds.md`. `docs/research/path-file.md` is the file's format as learnt, and `docs/research/basemap.md` the street map's facts, pins and hashes.

Nothing in this document is office-specific. The sample readings here are invented, from the demo office, with the fixes in the open Atlantic. No new environment key and no new service; one setting (Maps), one folder under the app data folder, one file the Admin places.

## What Phase 12 adds

- **The Map tab** (chapter 1, v1.187.0): the Path file taken in from the Map tab, matched to its video by name; the camera's Path read once into Fixes and marks; every camera of the Case drawn on the street map, or on plain ground, on one clock, one day at a time, with markers, trails, lanes, events to press, the camera list filtered by the view, the Preview playing the camera in step, a note from the map, the larger map; the readings known to Gideon in the case chat and the incident chat; the Basemap placed once with `./transcribe basemap`; the joins to incidents, Home, Details, search, notes, proposed events and clips.
- **Left to later releases**: the path file's clock placing a recording on the case's clock (release 2); the readings in the memo, the comparison and the timeline report (release 2); the Readings list, Offer to the chronology and Who was near here (release 3); the wearer on the Speakers page and where a line was said (release 4); the map pane on the incident page and Save a picture (release 5).

## Contents

1. The cameras on a map
2. The path file's clock, and the readings beside the record
3. The Readings
4. The names the cameras' files give, and where a line was said
5. The map pane on the incident page, and Save a picture of the map

Appendix A. Audit rows added in Phase 12
Appendix B. Settings added or changed in Phase 12

## 1. The cameras on a map

### Principles

1. **The file is the camera's record, and the app invents no position.** Where the file has no fix, the map draws nothing and says "no fix". Nothing is interpolated across a gap; between two fixes within ten seconds the marker moves in a straight line, which is how a reading a second apart is drawn, not a guess.
2. **A Path belongs to its Recording.** One file per video, kept in the recording's folder beside the playback copy, counted in its size, gone with it, never served to a browser.
3. **Nothing reaches outside the office.** The drawing library is in the app's static files; the streets come from one file the Admin placed on the server, served by the office's own server to signed-in browsers; the app never fetches a tile.
4. **Positions are content.** A camera's fixes, the wearer's name, the unit and the department are never in an audit row, a log line, an export or the engine's reading. Gideon is told times of day, distances between cameras and the readings' words, never a coordinate.
5. **One clock, one day at a time, the office's time of day.** The same clock the incident page and the case's chronology run on; a camera off the clock is listed and can be shown on its own, never guessed onto it.
6. **The same words, gestures and places the office has met.** The Preview is the player; the strip is the incident page's; a note from the map is a note on the recording like any other; an incident from the map is the Incidents tab's own Make it.

### Words

**Path**, **Fix**, **Path file**, **Map** (the tab) and **Basemap**, as `CONTEXT.md` defines them. The pages say "path", "fix", "no fix", "path file", "street map" and never track, route, GPS, ping, waypoint, sidecar, tiles or tile server.

### The path file

What the exporting cameras write, as learnt from the office's own files (`docs/research/path-file.md`, counts only):

- A WebVTT file (`WEBVTT` first; cues of `HH:MM:SS.mmm --> HH:MM:SS.mmm`, one a second) named as the video is named with the ending `.vtt`. Each cue's text is one JSON object.
- Every reading carries `gpsCoordinates` ("N36.123456 W86.123456", or "" when the camera had no fix), `mic` (0 or 1), `low battery`, `officer` (the wearer's name as the department spelt it), `vehicle` (the unit id), `department` and `eventDate`.
- A **body-worn** camera's `eventDate` is empty, and its `mic` turns on about sixty seconds into every file: the camera keeps the minute before the officer activates it, without sound. So the reading's words are "activated at 20:27:05 (the minute before is the camera's buffer, without sound)", and "camera on" is the buffer's start.
- An **in-car** unit's readings also carry `eventDate` as its own wall clock ("11/06/25 14:20:03", the exporting office's local time), `patrolSpeed` with `speedUnit`, and the switches `lights`, `siren`, `brakes`, `crash`, `aux` and `bookmark` as 0 or 1. One unit exports one file per stream (front, cabin, rear), identical.
- The file name's twelve-digit stamp (`_YYYYMMDDHHMM_`) is the recording's start to the minute in UTC: in every sample it sits one zone's offset from the clock inside.

The parser (`core/camera_paths.py`, `parse()`) is pure and refuses with plain words: not WebVTT; no cue with a camera reading; a reading with neither a position nor a camera flag; over 20 MB; over 50,000 cues. It reads a byte-order mark, CRLF endings, a cue identifier line, a zero-length cue, and skips a cue whose JSON will not parse (counted as unread). The source is `car` when the first reading carries `patrolSpeed`, `lights`, `siren` or `brakes`, else `body`. Fixes are kept to a tenth of a second and six decimal places, repeats collapsed; a stretch with no fix over ten seconds is a gap; each flag's first value and every change is a mark; an in-car speed is a mark on change. A file with no fix at all is kept for its readings (one of the office's twenty-six samples is such a file, a camera indoors throughout, and it still says when the officer activated it).

### Taken in

- **From the Map tab only** (the maintainer's answer): **Add path files** in the tab's head takes a folder's worth of files in one post (`POST case/<id>/paths/add`). Each file whose name matches exactly one video of the case that has no path file lands on it at once; the answer says what landed ("12 files added to their videos") and lists the rest to settle in a Layer: **flagged** (the name matched, but the unit inside disagrees with the camera id the picture's clock named, or the length differs from the video's by over a tenth, or the minute in the name sits over an hour from the recording's clock), with Add anyway; **has one** (the video already has a file), with Replace; **unmatched** (no video of that name), with a chooser of the case's videos and the file described in a few words ("A body camera, 38 minutes, 6 Nov 2025 by its name"); **refused**, with the reason. Settling posts the same endpoint again with the chosen recording ids.
- **On a row**: a video without a file has **Add a path file** (`POST recording/<id>/path`); a camera's "..." offers Replace and Remove (`POST recording/<id>/path/remove`). A mismatched name is taken with a warning; a second file replaces only when asked.
- **Who may**: anyone who may open the recording (`cases.standing`), so the owner, a collaborator and an Admin; while Maps is off the endpoints are 404 and files already there stay.
- The file is written into the recording's folder as `path.vtt`, the recording's disk measured, one audit row written (Appendix A), the case's activity noted. The parse runs in the request: the slowest of the office's files reads in a tenth of a second.

### What is kept

`CameraPath`, one per Recording (migration 0103): the source, the wearer, the unit and the department as the file gives them; the in-car clock's start in the office's zone and whether the first and last dated cues agree within two seconds; the fixes, the marks, the gaps, the speed unit; the counts (cues, unread, fixes), the first and last fix, the length, the bounds; whether the stem matched; the state, the error and the read version (a later parser re-reads the kept file on the media queue, as Documents do); the file's name, its size, who added it and when. The file itself is `path.vtt` in `Recording.folder`.

### The camera's clock

For the map, in the maintainer's order (`zero_of`): (1) the path file's own clock, surety **Clear** when the first and last dated cues agree and **Likely** when they do not; (2) the clock the app holds for the recording (ADR 0027: from the stamp, by hand, from the file, by sound), with its own surety word; a day alone is not a zero and the camera is listed under its day as not on the clock; (3) the file's creation time from the probe, **Unchecked** (the build's addition within the rules: it is seconds-precise and the chronology already offers it); (4) the minute in the file's name, read as UTC and shown in the office's time, **By its name** in the warning tone; (5) none: the camera is off the clock, listed under every day with **Show on its own**. In this release the path file's clock is read for the map alone and places nothing on the case's chronology; release 2 amends ADR 0027 for that.

### The Map tab

Between Incidents and Clips in the case bar, with the count of cameras that have a path file; present while Maps is on. One reading, `GET case/<id>/map.json` (optional `?day=`), never polled, read again after a change: the time zone, the basemap's state, the days with their camera counts, the cameras (id, title, unit, wearer, source, colour as the chronology colours the recording, the zero with its surety, the day alone, the length, the fixes, the marks, the gaps, the events, the notes, the clips, the playback address, the recording page, the incident, the twin), the cameras off the clock, the videos without a file, the incidents with their cameras and dates, the forming offer, the note endpoint.

- **The day.** Chips for every day on which a camera is on the clock, each with its camera count and, where the Incidents tab knows one, its incident count; the day with the most cameras opens first; `?day=` keeps the choice in the address. The clock runs one day at a time; a camera past midnight belongs to the day it started.
- **The lead.** How many cameras and how many with a path file; the Show control (**Markers only**, **Trails**, **Whole paths**, remembered per person); the Events ticks (camera on and off, lights, siren, mic, bookmarks, notes) choosing what is drawn on the map and the lanes; the transport (Play, −10 s, +10 s, ‹ event, event ›, Speed 1/4/16/60, the clock with the zone name and the day, Fit all, Note here, Larger map).
- **The map.** The street map from the basemap when it is installed, in the page's light or dark flavour, swapped when the theme changes; plain ground otherwise, with a line saying so and that the Admin can install one. Every camera's whole path faint, its trail to the clock's moment in its colour, a marker where it is now (round for a body camera, square for an in-car unit, its unit id on it, dimmed in a gap, hollow after it ended, with a badge for lights and siren), and pips where the ticked events happened. Zoom and pan freely; rotation is off and north is up. The browser's full screen from the map's corner, with a slim bar (play, clock, speed, Leave full screen).
- **The list.** Beside the map at 1024 and up, under it narrower: "N of M in view" from the map's bounds, the rest folded; a row with the camera's colour, unit, wearer, surety pill, its span on the clock, body or in-car, no position where the file has none, **Play here**, and the "..." for Replace and Remove; hover lights the path, a press flies to it; the cameras not on the clock under their own fold with **Show on its own** (the path lit with its own bar); other days' cameras folded; the videos without a file last with Add a path file. The forming offer (below) as a card at the foot.
- **The strip.** The incident page's lanes: a ruler of the day's span, a lane per camera on the clock with its bars (segments of fixes), its gaps thinner, its clips along the top in the clip colour, its events as marks (lights and siren with their on-spell drawn), its notes, the camera's speed in the lane head while it moves; the playhead draggable by mouse or touch.
- **The Preview as the player.** A marker, Play here or a row opens the Preview's window on that camera at the clock's moment exactly (no ten-second lead-in; `exact`), and the transport reads "following BWC2-1": while the window plays, every marker moves with the video, and a seek on the strip seeks the video. Closing the window leaves the clock where it is. A two-stream in-car unit is one marker and one row with its streams named.
- **The events.** A press on a pip or a lane mark selects it: the clock moves there, the camera lights, a card beside the pip says what, when (and the street, read from the basemap's own labels in the browser, when there is one), until when, with **Play here**, **Add a note**, **Clip from here**, the camera's previous and next, and Close; ‹ event and event › on the transport step every shown event of the day in order; Escape clears. A note pip opens the same card with the note's words, who wrote it, **Edit** (the recording page with the note lit) and **On the Notes tab**.
- **Notes from the map.** **Note here** on the transport writes a note on the selected camera at the clock's moment; **Add a note** on an event's card at the event's moment. Both go through the recording's own note-at-a-moment endpoint (v1.99.0) and are the recording's notes: on the Notes tab, in the exports, an event on an incident's chronology where the camera is synced. Nothing new is kept.
- **The keyboard.** Space plays and pauses; Left and Right step a second, ten with Shift; Escape clears the selection; the Preview's keys are its own.
- **Narrow screens.** One column under 1024; under 900 a slim bar with play, the clock and the speed stays above the Preview's sheet; under 700 the lane heads narrow and the rows become cards.
- **Without WebGL.** The constructor's failure is caught: "This browser cannot draw the map"; the list and the strip still work.
- **Not on the clock.** A camera with no zero has no lane and no marker on the shared clock; **Show on its own** draws its path with its own range control, and Play here opens the Preview at that point.

### Gideon knows the readings

The case chat (`case_chat.answer_case_turn`) appends a readings block beside the placements block for every recording the question reads that has a path file: one paragraph per camera in the office's time of day, "Recording 3 (BWC2-1; a body camera, worn by the wearer as the file gives it; clock from the minute in its file name): recording began 14:20:03; activated 14:21:04 (the minute before is the camera's buffer, without sound); no fix 14:31:10 to 14:36:00; stood still 14:45:00 to 14:51:00 (6 minutes); recording ended 14:58:11." and for an in-car unit "lights on 14:22:08 to 14:31:40; siren on 14:22:08 to 14:26:30; brakes 14:26:28; bookmark pressed 14:30:01; reached 41 mph 14:24:10"; then which cameras were within 50 m of each other and when. A rule joins the system message, as the Documents rule does: the readings come from the camera's own file, say which camera, give the time of day, cite the moment as [Recording N, HH:MM:SS]. The incident chat gets the same block for its cameras, by the incident's clock where the camera is placed on it. So "when were the lights turned on", "when did the officer turn the camera on" and "who was near the vehicle at 14:30" are answered from the readings alone, and a cited moment opens the Preview as any citation does. A camera not on the clock is told in minutes into the recording. Coordinates are never in the prompt. The chat's audit row is unchanged.

### The basemap

One file, `<app data folder>/maps/basemap.pmtiles`, no setting and no path to type: the Admin cuts a region of the free OpenStreetMap-based Protomaps builds on a workstation with the internet (`pmtiles extract` with a bounding box; the admin guide and `docs/research/basemap.md` give the command) and places it with `./transcribe basemap <file>`, which checks the file's first bytes, copies it under the app's account at 0640 and says so; `./transcribe basemap remove` takes it out. Caddy serves it from a third read-only root, `/maps/*`, behind the same forward_auth as the recordings (`/maps-auth`: 401 for nobody, 404 while Maps is off or for any other name, 200 for a signed-in person, no audit row, since the map is a public map of the region and not content), with byte ranges and `Cache-Control: private, max-age=604800` (a browser reads the file in small ranges on every pan and may keep them privately; the recordings' `no-store` stays theirs). `caddy/check-ranges.sh` proves the ranges on this route too. The Status page says whether the file is in place with its size and date. The drawing library (MapLibre GL JS 5.24.0), the PMTiles reader, the two Protomaps styles, three Noto Sans glyph stacks (eight ranges each) and the sprites are vendored in the app image's static files with their hashes in `app/static/vendor/README.md`. No CSP exists today; one added later must allow `worker-src blob:` for the library's worker.

### Joined to the rest of the case (Figure K)

1. **Incidents.** **On the map** on an incident's row of the Incidents tab and in the incident page's head opens `?tab=map&incident=<id>`, scoped to the incident's cameras and span with **whole day** to widen; the day chips carry the incidents' days. The map makes the Incidents tab's own offer: cameras within 50 m of each other for over five minutes that sit in no incident are one card at the list's foot, "BWC2-1 and Dash-4 were within 50 m of each other for 12 minutes, 14:31:00 to 14:43:00, and are in no incident", with **Make an incident** (the Incidents tab's New incident form, posted with the cameras) and the tab's link. Nothing is made without a press.
2. **Counts.** Home's case card carries "N cameras on the map" among its pills; the Details tab's About this case says "N cameras with a path file, M videos without"; the Status page says whether the street map is installed.
4. **Search, notes and proposed events.** **on the map** beside a search hit, a Notes tab row, and a case's chronology or Proposed events entry opens `?tab=map&recording=<id>&at=<seconds>`: the tab on that camera's day at that moment, the camera selected and in view.
5. **Clips.** A camera's clips sit along the top of its lane, pressable to play in the Preview; **Clip from here** on an event's card opens the recording page at that moment with the Clips tab ready, the way a clip starts from a line.

### What is not

No live positions and no address lookup: the app knows the streets only as the basemap draws them, and names one only in the browser from the basemap's own labels. No export of a path and no picture of the map until release 5. Nothing is told to Gideon but the readings' words and times. The path file's clock does not place a recording on the case's chronology until release 2. A Readings list, Offer to the chronology and Who was near here are release 3.

### Left to the build

- The twin rule for one unit's streams (same unit and clock start, or the same fix count and first fix): one marker, one row with its streams named.
- The event pips drawn as circles coloured by kind rather than symbols, so no sprite is needed for the paths' own layers; the tick row filters by rebuilding the source.
- The trail redrawn only when a camera's fix index moves, so thirty cameras at 60x stay within the tick.
- The three Preview exports (`media`, `asked`, `seek`) and the `exact` open, the one change to `preview.js`.
- The forming offer counted at ten-second steps from the fixes, in the request, for a case's cameras on one day.

## 2. The path file's clock, and the readings beside the record (the second release, v1.188.0)

### The path file's clock places the recording

An in-car unit's path file carries the unit's own wall clock on every reading (chapter 1). When such a file is added to a recording that nothing has placed on the case's clock, the recording is placed from it: `clock_how` **path**, the date and the second of the day from the first dated cue less its offset, in the name of the person who added the file, with the usual "recording placed on the clock" row (how `path`). The rules of ADR 0027 bend by this much and no more (its amendment of 2026-11-02): the stamp still wins; anything a person chose (by hand, by the day, from the file's time, by sound) stands; the path clock takes only a recording with no clock at all, or one its own forerunner placed. Removing the file takes the clock with it ("recording taken off the clock"); replacing the file places afresh. The surety word is **Clear** when the file's first and last readings agree within two seconds and **Likely** otherwise, with the chapter 1 words; the chronology's pill reads "from its path file, <who added it>". A body camera's file carries no clock and places nothing. No migration.

### The readings beside the record

The memo's facts sheet and the comparison with the report are given each camera's readings beside the incident record, as the incident chat is (chapter 1): one line per camera with a path file, in the time of day, placed after the record and before the report's pages, with the readings rule joined to the system message. So a claim in the report about the lights, the siren, a camera turned off or a vehicle stopped is read against the file that knows, and the facts sheet can give the moment the officer activated the camera without the picture. The second pass of the memo is unchanged: it writes from the sheet alone. The timeline report prints **The cameras' own files** after the cameras' table, one bulleted line per camera, with a note saying what the lines are read from and that a body camera keeps the minute before activation without sound. Never a position in any of them.

### Also in this release

`./transcribe folders`, `install`, `upgrade` and `basemap` asked whether each data folder existed without sudo, on a folder the operator cannot read, and so reported having made every folder on every run; the check asks with sudo now.

## 3. The Readings (the third release, v1.189.0)

### Words

**Reading**, as `CONTEXT.md` defines it: one moment a Path file records of its camera. The pages say "readings" and "the camera's file", never metadata, telemetry or flags.

### The Readings list

Each camera's row on the Map tab carries **readings**, which opens under the row the list of every moment its file records, in time order, each with its time of day on the case's clock (minutes into the recording for a camera off the clock), and for a spell (lights, siren, muted, stood still, no fix) its end. A press on a reading moves the clock there and lights the camera; where the reading is an event the map draws (and its kind is ticked), it selects it as a press on the pip would. The list is the chapter 1 events: camera on and off, the officer activating a body camera, the mic muted and back (a muted spell knows when the mic came back, from this release), the lights, the siren, the brakes, the crash sensor, a bookmark, a low battery, the top speed reached, each spell stood still, each stretch with no fix. An in-car unit's speed is drawn as a trace along its lane, scaled to its top speed.

### Offer to the chronology

On a reading in the list and on an event's card: **Offer to the chronology** makes a Proposed event on the recording (Phase 10 chapter 4) at the reading's moment, with the reading's words as its sentence, "Read from the camera's own file, not from the picture" as its why, the incident the camera is in where there is one, source `path` ("From the camera's file"), in the offerer's name. It waits on the Proposed events tab, and on the incident's Proposed events layer, for Accept or Dismiss as any proposal; accepted, it is a Note on the recording as any accepted proposal is, with the origin "from a proposed event (the camera's own file)". A reading is offered once: a second offer of the same words at the same moment is refused with the reason, and a dismissed one is not offered again. The button is withheld, with the reason, while the Proposed events tab is off in the office (the assistant's judgement off and no watch phrase listed), since the offer would have nowhere to land. `POST recording/<id>/path/offer` with JSON `t`, `until`, `words`; one audit row, "Reading offered to the chronology", with the reading's kind and never a position.

### Who was near here

**Who was near here** on the transport: pressed, the next press on the map asks the question of that place, marked with a ring. The answer is a card: every camera of the day that came within 50 m of the place, in the order they arrived, each with the spells it was there (a spell ends when a minute passes with no fix within reach), each a press to go there with the camera lit; or "No camera came within 50 m of here on this day." It is answered in the browser from the paths the page already holds: no request carries a position, and the server is not asked. Escape or Close clears it.

### What is not

No reading is offered by the app itself: Offer is the person's press, as Accept is. No position is in an offer, a proposal, a note or a row. The incident's own chronology gets the reading through the proposal's acceptance alone.

## 4. The names the cameras' files give, and where a line was said (the fourth release, v1.190.0)

### The wearer in the speaker picker

The speaker picker (Phase 5 chapter 3) gains a fourth group inside a case, **From the cameras' files**: one row per name the case's path files give, the wearer of each body camera ("Pat Doe, wore BWC2-1, from its path file") and the driver of each in-car unit ("Sam Roe, drove unit 9082, from its path file"), keyed like the People rows and chosen the same way: the speaker in hand takes the name, and a name new to the case becomes a Person as any name does. Names already on the call are left out. The app matches no voice to a wearer: the chapter 1 plan's "the voice nearest the microphone" was set aside, since nothing the app keeps says which voice that is, and a guess here would be a guess about a person. The group is absent while Maps is off or no file names anyone. Nothing new is kept; the voice book (Phase 5 chapter 2) keys prints to Persons as before, so a wearer named becomes a print's name through the same road.

### Where a line was said

On the recording page, a line of a recording that has a path file carries **where** beside note and clip: a press asks the file where the camera was when the line was said (`GET recording/<id>/path/where?t=`) and shows the answer under the words: whether the camera had a fix at that moment (none yet, none indoors, none in the file), and the case's other cameras that had one on the same clock by their distance from it, nearest first ("At 14:26:28: 9082 30 m away, BWC3-1 410 m away"); then **On the map**, which opens the Map tab at that moment with the camera selected (chapter 1's address), where the street is named from the basemap. A second press folds it. The answer carries distances and times and never a position; the street is the browser's to read on the Map tab and is not sent. Nothing is kept and no row is written: the file is read, not changed.

## 5. The map pane on the incident page, and Save a picture of the map (the fifth release, v1.191.0)

### The map pane

The incident page (Phase 6 chapter 2) gains a **Map** panel beside Cameras when a camera of the incident has a path file. It is the Map tab's own script on a second host (`map-host.html`, the one template both pages include), scoped to the incident as **On the map** scopes the tab, and it has no clock of its own: the incident page publishes its clock (`window.IncidentClock`: the moment as the time of day, seek, play, pause and the camera to bring to the front), the map reads the moment from it each tick, and a press on a pip or a marker seeks the incident's clock and brings that camera to the front of the wall in the Focus layout, with the sound following unless it is pinned. The panel's foot carries the count in view, the Show choice (Markers, Trails or Paths), the event kinds, Fit all, Save a picture and **Larger map**. Larger map moves the host onto the stage in the wall's place (the videos keep playing, so the sound plays on) and the panel says "The map has the wall's place" with Smaller map; the choice is remembered per person apart from the Map tab's. An incident without a clock shows the map at the cameras' start and says so. The keys stay the page's; Escape clears a selection on the map. The panel is absent while Maps is off or no camera of the incident has a file. Nothing new is kept; the page's own address `?tab=map` opens on the panel.

### Save a picture of the map

**Save a picture** on the Map tab's transport and on the incident's map pane keeps the view as a **Document**: the map as drawn, the markers at the clock's moment drawn onto a copy (they are page elements, not part of the map's canvas), and a band under it with the title ("Map at 14:21:50, 2 Nov 2026 · Stop"), the scale bar and the street map's attribution when one is installed. The browser draws it; the server keeps it (`POST case/<id>/map/picture`) as a Document on the incident shown, or on the Map tab on the camera pressed (its row or its marker); with neither the button says what to press. A picture Document is a `kind` of its own (migration 0104; every Document so far is a report): one page whose picture is the file itself, no words, ready at once, counted against the same ceiling as the reports, listed on the Documents tab and the Report panel and downloaded as the PNG it is, never compared ("A picture of the map has no words to compare") and never put back in the reading line. Its audit row is the Documents' own, "Document added", with the kind. Nothing about the map's content, no position, is in the row or the title: the title is the time of day and the day. The street names on the picture are the basemap's, drawn in the browser as on the page.

### What is not

No picture is taken without a press; the memo and the timeline report list the picture as they list any Document and do not place it in their body. A note on the ground with no camera, and a picture of a span rather than a moment, are left to later.

## Appendix A. Audit rows added in Phase 12

| Row | Category | Details kept | Never |
|---|---|---|---|
| Path file added | Recordings | the recording, the case, the source (body or car), the fix and cue counts, whether the name matched, whether the file carries a clock | a position, the wearer, the unit, the department, a time |
| Path file replaced | Recordings | as above | as above |
| Path file removed | Recordings | the recording, the case | a position |
| Recording placed on the clock, how `path` (chapter 2) | Recordings | the recording, the case, the how | a time, a date |
| Reading offered to the chronology (chapter 3) | Recordings | the recording, the case, the reading's kind | a position, a time |

The basemap's route writes no row; the map's reading writes the case page's own Admin access row and nothing else; a note from the map writes the note's usual row; a picture of the map (chapter 5) writes the Documents' own "Document added" with `kind: picture` and never a position.

## Appendix B. Settings added or changed in Phase 12

| Setting | Page | Shipped | What it does |
|---|---|---|---|
| Maps | Features | On | A case's Map tab shows each camera's path from its path file on a map, with a clock; a path file is added from the Map tab. Needs Folder management. Off hides the Map tab, the path endpoints and the street map; path files already there stay. At once. |

## Sources

- The maintainer's asks and answers of 2026-11-02, recorded on `docs/spec/mockups/phase-12-map.html` (figures A to L, the fifteen choices and the joins chosen).
- The dry run on the office's own path files, counts only, in `docs/research/path-file.md`.
- The street map's pins, hashes and the extract command in `docs/research/basemap.md`.
- Phase 6 chapters 1 and 2, Phase 8 chapter 2, Phase 10 chapters 1 and 5, Phase 7 chapter 5, ADR 0011, ADR 0027.
