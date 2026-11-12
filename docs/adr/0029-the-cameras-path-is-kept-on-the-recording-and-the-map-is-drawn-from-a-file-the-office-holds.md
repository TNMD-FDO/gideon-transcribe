# 29. The camera's path is kept on the recording, and the map is drawn from a file the office holds

Date: 2026-11-02. Status: accepted. Release: v1.187.0 (Phase 12 chapter 1, "The cameras on a map").

## Context

Some of the office's body-worn and in-car camera exports arrive with a text
file beside the video (a WebVTT file of JSON readings, one a second) that
says where the camera was and what its switches were doing. The maintainer
asked for a tab in a Case that draws those movements on a map, with a
clock, the video a press away, and the readings answerable by Gideon.

Three things had to be decided that are hard to undo once offices have
cases built on them: where the file and its reading live, where the map's
streets come from when nothing may leave the building, and whose clock the
map runs on.

## Decision

- **A Path belongs to its Recording.** One `CameraPath` row per video,
  OneToOne on the Recording, cascaded with it; the file itself is kept as
  `path.vtt` in the recording's folder beside the playback copy, counted in
  its size, moved and removed with it, and never servable (it is not in the
  media route's list). It is not a Document (a Document is a report the
  office reads; a path file is a camera's own record, read by the app and
  never shown as pages) and it is not loose in the Case.
- **The file is read once into fixes and marks, kept as JSON on the row**,
  with a read version so a later parser re-reads the kept file on the
  media queue, as Documents do. The app invents no position: a gap is a
  gap, a file with no fix is kept for its readings.
- **The street map is one file the office holds, served by its own
  server.** The Admin cuts a region of the free OpenStreetMap-based builds
  once on a workstation with the internet and places it at
  `<app data folder>/maps/basemap.pmtiles` with `./transcribe basemap`.
  Caddy serves it from a **third read-only root**, `/maps/*`, with byte
  ranges, behind the same forward_auth as the recordings, and a browser may
  keep the ranges privately for a week. This reconciles ADR 0011 ("two
  roots, not one"): the third root holds exactly one file that is not
  content, a public map of the region, and the two content roots keep their
  `no-store`. The drawing library and the map's style, fonts and sprites
  are vendored in the app image's static files with their hashes recorded;
  nothing on the Map tab reaches outside the office, and without the file
  the tab draws its paths on plain ground and says so.
- **The map's clock is the camera's clock in the maintainer's order**: the
  path file's own clock (an in-car unit's wall clock, Clear when its first
  and last readings agree), then the clock the app already keeps for the
  recording (ADR 0027), then the file's creation time, then the minute in
  the file's name read as UTC ("By its name"), else off the clock. In this
  release the path file's clock is read for the map and places nothing on
  the case's chronology; the second release lets it place a recording that
  has no clock, never over a stamp or a hand placement, which amends ADR
  0027's "the stamp wins" with one more read clock below it.
- **Positions are content.** A camera's fixes, the wearer, the unit and the
  department are never in an audit row, a log line, an export or the
  engine's reading. Gideon is told the readings as words with times of day
  and distances between cameras, never a coordinate.

## Consequences

- The file and its reading go wherever the recording goes: a case's
  Download everything, the Recycle bin, a restore, a deletion.
- A later parser costs one re-read per path on the media queue, not a
  migration; a later map library costs new vendored files and hashes, not
  a data change.
- An office without a basemap has a working tab on plain ground; an office
  with one serves a few hundred megabytes from its own disk and the browser
  keeps what it read. The region is the office's choice, and so is the
  file's size.
- A browser without WebGL has the list and the strip and no map.
- A future content-security policy must allow `worker-src blob:` for the
  library's worker.

## Amendment, 2026-11-04 (Phase 12 chapter 6, v1.194.0)

A path file may wait on the Case for its video. Offices upload path files
by the hundred before the videos they belong to, so a file that matches no
video is no longer answered at once with a chooser: it is kept on the Case
(`WaitingPathFile`, its bytes under the case's folder), read by nothing,
and made the recording's Path through the same `add()` when a recording of
its name lands by upload or by a move into the case. The decision above
stands: a Path is made only on a Recording, is kept in its folder and goes
with it; the waiting file is not a Path and has no readings, so nothing
that reads paths (the map, the chat, the memo, the comparison, the Speakers
page) can see it. Add path files moved to the case's head for the same
reason: a path file is the case's input, not the map's.

## Amendment, 2026-11-12 (Phase 12 chapter 1, v1.232.0)

The street map may be fetched on the server. The decision above said the
Admin cuts a region once on a workstation; offices across the whole United
States, the territories among them, are to use the app, and five steps on
two computers with a rectangle to draw is the wrong way to ask each of them
for a map. `./transcribe basemap fetch` cuts the whole country with its
territories, or the states and territories an Admin names, out of the
newest Protomaps build with Protomaps' own tool, on the server.

What stands: the map is one file the office holds, served by its own
server from the third read-only root; nothing on the Map tab reaches
outside the office; the app never fetches the map, and without one the tab
draws on plain ground. The fetch is an Admin's command at a terminal, like
an upgrade, and the way by hand remains for a server with no route out.

What changes, and what it costs:

- The file may be about 20 GB, not a few hundred megabytes. It is served
  by byte ranges either way, so a browser reads no more than before.
- One more outside host is reached, at the moment of the command only:
  `build.protomaps.com`, and Docker Hub once for the tool.
- The build is the one input the app cannot pin by digest, since a new
  one is made each day and none is kept past a week. Its date is recorded
  beside the map and shown on the Status page. The tool is pinned by tag
  and digest and is no part of the running stack.
- The backup does not carry the map; it is fetched again after a restore.
