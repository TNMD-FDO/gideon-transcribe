# 27. A recording's clock is kept on the recording, and the case's chronology reads it

Date: 2026-10-28. Status: accepted. Release: v1.164.0 (Phase 10 chapter 1, "The case's chronology").

## Context

Until now the only clock a recording had was the one an Incident gave it:
`IncidentCamera.starts_at`, seconds from the Incident's zero, placed by the
camera's burned-in stamp, by sound, or by hand on the incident page's strip.
A recording in no Incident had no time of day, and a recording in two
Incidents could have two.

Phase 10 lays every note in a Case on one clock without an Incident (the
maintainer's ask of 2026-10-28). That needs a time of day per recording
that belongs to the recording, not to a grouping: a video with a read clock
has one from its stamp; a jail call or a camera with no clock in the picture
gets one once, by hand, and every note on it follows. The maintainer also
asked that an Incident made later from the chronology "not need a bunch of
rebuilds": the placement must be made once and read twice.

## Decision

- **A recording's clock is five columns on the Recording**: `clock_date`,
  `clock_start` (the second of the day it started at), `clock_how` (`clock`
  from the stamp, `hand`, or `day` for a date with no hour), `clock_by` and
  `clock_at`. Empty until read or placed.
- **The stamp wins.** A video whose stamp has been read carries `clock` and
  a person cannot overwrite it by hand; a stamp read later for a recording
  placed by hand takes over, and the hand placement stays in the audit only.
- **Placing is the person's, named and reversible**, from the case's
  chronology: a drag onto the ruler, a typed date and time, or the day alone;
  one audit row per recording, "Recording placed on the clock", with the how
  and never a time; "Recording taken off the clock" when undone. Anyone on
  the case may place, move or take off.
- **The case's chronology reads it and nothing else**: a note's time of day
  is its recording's clock plus the note's moment. The Incident's own
  placement (`IncidentCamera.starts_at`) is untouched by this ADR; Phase 10's
  second release lets an Incident made from a span of the chronology take its
  cameras' placements from this clock as its first placement, which is the
  "read twice" the context asked for.

## Consequences

- One migration, five nullable columns on Recording; nothing stored changes.
- Phase 6 chapter 6's rule stands: the app never invents a time. A clock here
  is read from the picture or typed by a person, and the page says which.
- A recording in two Cases is not possible (Phase 2), so one clock per
  recording is one clock per case.
- The incident page's by-hand placement and the chronology's are the same
  gesture with the same confirm box, so a person learns it once.
