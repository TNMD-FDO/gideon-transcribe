# The camera's path file: the format as learnt, and what the dry run showed

Written 2026-11-02 for Phase 12 chapter 1 (`docs/spec/SPEC-PHASE-12.md`).
The office gave twenty-six of its own path files to learn the format from;
this note keeps the shape and the counts, never a value from a real file.
Every sample reading here is invented, with its fix in the open Atlantic.

## The shape

A WebVTT file, named as its video is named with the ending `.vtt`:

```
WEBVTT

1
00:00:00.000 --> 00:00:01.000
{"gpsCoordinates": "N10.000100 W30.000100", "mic": "0", "low battery": "0", "officer": "Pat Doe", "vehicle": "", "department": "Demo Police", "eventDate": ""}

2
00:00:01.000 --> 00:00:02.000
{"gpsCoordinates": "N10.000200 W30.000100", "mic": "0", ...}
```

One cue a second, each cue's text one JSON object. The keys met:

| Key | Body-worn | In-car | Read as |
|---|---|---|---|
| `gpsCoordinates` | yes | yes | "N dd.dddddd W ddd.dddddd"; "" when the camera had no fix; S and W negative |
| `mic` | yes | yes | 0 or 1 |
| `low battery` | yes | no | 0 or 1 |
| `officer` | yes | yes | the wearer's name as the department spelt it |
| `vehicle` | "" | yes | the unit id |
| `department` | yes | yes | the department's name |
| `eventDate` | "" | yes | "MM/DD/YY HH:MM:SS", the exporting office's local wall clock |
| `patrolSpeed`, `speedUnit` | no | yes | a number and "MPH" |
| `lights`, `siren`, `brakes`, `crash`, `aux`, `bookmark` | no | yes | 0 or 1 |

The file name carries the recording's start to the minute as twelve digits
between underscores (`_YYYYMMDDHHMM_`), in UTC: in every sample it sat one
zone's offset from the clock inside the in-car files, and the body files,
which carry no clock, name the same minute their video's stamp read.

## What the dry run showed (counts only)

Run on 2026-11-02 with a throwaway parser over the twenty-six files.

- 25 parsed with fixes; 1 parsed with no fix at all (a body camera indoors
  throughout), which still carried the mic readings. That file changed the
  plan: a file with no fix is kept for its readings rather than refused.
- Body files: 91 to 2,422 cues, 6 to 510 fixes after repeats collapse, no
  byte-order mark, LF endings, every name carrying its minute.
- The three in-car streams of one unit were identical: 3,528 cues, 1,251
  fixes, one zero-length cue, CRLF endings, a clock on every cue agreeing
  first to last, 153 flag changes. So one unit's streams are drawn as one
  camera (the twin rule).
- The mic flag turns on about 61 seconds into every body file. That is the
  camera's pre-record buffer, kept without sound until the officer
  activates it; so "mic on" past thirty seconds reads as "Activated", and
  the chat is told the minute before is the buffer.
- The slowest parse was 130 ms, so the file is read in the request and no
  queue is needed for the first reading.

## The parse rules

- Strip a byte-order mark; normalise CRLF; require `WEBVTT`; split on
  blank lines; skip NOTE, STYLE and REGION blocks; the timing line may be
  the first or second line of a block (a cue identifier before it); hours
  are optional in the timing.
- The source is `car` when the first reading carries `patrolSpeed`,
  `lights`, `siren` or `brakes`; `body` when it carries `low battery` or
  `gpsCoordinates`; anything else is refused as not a path file.
- A fix is kept at a tenth of a second and six decimal places; a repeat of
  the last fix is dropped; a stretch with no fix over ten seconds is a gap.
- Each flag's first value and every change is a mark; an in-car speed is a
  mark on change; `eventDate` on the first and last dated cues gives the
  clock's start and whether they agree within two seconds.
- Caps: 20 MB and 50,000 cues, refused before the read.

## Where the file is read from

`core/camera_paths.py`: `parse()` (pure), `add()` (the file kept, measured,
one row), `match_files()` (several files by name), `zero_of()` (the clock),
`events_of()` and `readings_words()` (the readings), `readings_block()` and
`readings_block_for_incident()` (Gideon's), `map_of()` (the tab's reading).
