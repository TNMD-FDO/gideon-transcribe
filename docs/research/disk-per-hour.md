# What a recording keeps on disk, per hour of talk

Measured on 2026-10-04 on the office's own server, read-only, across every
recording the app held: 64 recordings, 21.6 hours of talk, 38 of them
untyped body-camera and interview video from the office's test cases, 12
typed Body camera, 9 Interview, 2 Meeting, 2 Other and 1 Jail call. The
question behind it (Phase 9, "the bloat question"): with dumps of 800 jail
calls coming, is the disk the thing that grows, and should the ASR audio be
dropped once a recording is Done?

## What the app keeps for a recording

The Phase 1 specification's media chapter: the uploaded bytes as they came
(hashed, probed, never served), one Playback copy the browser can play, one
ASR audio file per Side (WAV, 16 kHz, mono, 16-bit PCM, what the WhisperX
service's own loader would make), a waveform file, and under a Clip's
folder each rendered Clip. The database holds the words and the rows,
never audio.

## The figures

| What | Total | Per hour of talk |
|---|---|---|
| Uploaded bytes | 34.3 GB | 1.59 GB (video; a sound file is a small fraction) |
| Playback copy | 25.9 GB | 1.20 GB (video; sound is a few tens of MB) |
| ASR audio | 2.7 GB | 0.124 GB, that is 115 MB per Side |
| Waveforms | 0.02 GB | under 1 MB |
| Other (stretches, clips, probes) | 0.9 GB | |
| Database | 127 MB | |

The ASR figure is arithmetic as much as measurement: 16,000 samples a
second at two bytes is 115.2 MB an hour per Side, whatever the recording.
The data drive is 7.7 TB, shared with GIDEON, with 7.4 TB free on the day.

## What it means for 800 jail calls

A dump of 800 calls of fifteen minutes is 200 hours of talk. The ASR audio
is 23 GB for one-Side calls and 46 GB when every call is two-channel. The
uploaded files and the Playback copies are whatever the vendor's files
weigh: a telephone-quality file is small, and the Playback copy of a sound
file is small. One dump is well under 100 GB on the drive the office has,
and a year of them is a fraction of it.

## The decision

Nothing is dropped after Done, and no sweep of the ASR audio is planned.
Process again, the Speaker check's voice reading and the Clips read from
these files, and the ASR audio is under a tenth of what a recording keeps:
dropping it would save little and cost a re-decode on every Process again.
The free-disk floor on the Limits page (uploading pauses under it) is what
keeps the drive safe. The figures above go in the admin guide so an office
can size a drive; if an office's uploads are video at scale, the uploaded
bytes and the Playback copy are the two lines to watch, not the ASR audio.

## Sources

- The server's data folder read by the app's own `Recording.folder` paths
  on 2026-10-04 (counts and sizes only; nothing of the recordings).
- `docs/spec/SPEC-PHASE-1.md`, "The ASR audio" and the media layout.
