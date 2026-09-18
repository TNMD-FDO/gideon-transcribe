# The sound match: placing a camera without a clock by what it heard

Written 2026-09-17 for Phase 6 chapter 1 (`docs/spec/SPEC-PHASE-6.md`),
which leaves the method and its threshold to the build and asks for a probe
on the office's own files before the promise is relied on. This note records
the method as built in v1.58.0, what it did on made-up sound, and the probe
still owed on real files.

## What it does

Two body cameras within earshot hear the same doors, voices and sirens a
fraction of a second apart. The app compares the loudness of the two
recordings over time and finds the shift at which they agree best. It reads
the ASR audio the app already keeps for each recording (16 kHz mono WAV,
the first Side), never the picture, and nothing goes to the engine. It runs
on the media worker, as a Clip render does. The code is
`app/core/sound_match.py`; the rows and the placement are
`app/core/incidents.py`.

The method, step by step:

1. Each recording is cut into 20 ms frames and each frame's loudness taken
   in decibels, so a shout and a whisper both count as change.
2. Each frame is compared with the two seconds around it (the local mean
   subtracted, the result scaled to unit spread), so only changes count and
   the general level of one camera against the other does not.
3. The two rows of numbers are cross-correlated with a fast Fourier
   transform (NumPy; a forty-minute recording is 120,000 frames), every
   shift scored by the correlation divided by the frames that overlap at
   that shift, and only shifts with at least a minute of overlap are
   considered. When both files carry the time the camera wrote into them,
   the search is narrowed to ten minutes either side of the difference.
4. The best shift is the lag: the other camera starts that many seconds
   after the reference. Its strength is the best score over the best score
   more than three seconds away from it: a true match is a spike, a false
   one a plateau.

A match with strength 1.5 or more is applied (the camera reads Matched by
sound); a weaker one is kept, shown as "the sounds did not clearly line
up", and left to the person with Use it anyway. The figure is the constant
`STRONG_MATCH` in `incidents.py`.

## What it did on made-up sound

The suite's test (`app/tests/test_incidents.py`,
`test_the_sound_match_finds_a_known_shift`) builds ninety seconds of quiet
with forty random bursts, and a second file that is the same scene from
3.2 seconds in with its own noise added. The match finds 3.2 seconds within
50 ms either way round, with a strength well over the threshold, and says
no when the search window is put ten minutes from the truth.

## What is still owed: the probe on the office's files

Made-up sound says the arithmetic is right; it does not say how two real
body cameras at one stop behave, where one officer is at the driver's
window and another at the boot, wind and traffic differ from camera to
camera, and the cameras' own microphones colour the sound. Before the match
is relied on, run it on the server against a few pairs from one real
incident, with the true shift known from the cameras' clocks:

```
docker compose exec app python manage.py sound_match <recording a> <recording b>
```

It prints the lag, the strength, and how long it took; the recording ids
are the ones in the address bar. For each pair note the lag against the
clocks' difference, and the strength. Two questions decide the threshold:
do true matches within earshot always score over 1.5, and does any pair out
of earshot score over it? Record the counts here, never the words; nothing
of the sound leaves the server.

**First report, 2026-09-17.** The maintainer ran the match on the server on
two videos of one interview filmed from different angles, and it placed
the second camera correctly. One pair, within earshot, with no numbers
recorded: it says the method works on real sound in a quiet room, and
nothing yet about a street with wind and traffic, or about a pair out of
earshot. The counts above are still owed.

## Sources

The app's own media facts (`docs/research/media-pipeline-facts.md`: the ASR
audio is 16 kHz mono 16-bit WAV). Cross-correlation of onset envelopes is
the standard way of aligning two recordings of one event; NumPy's `fft`
module documentation (numpy.org) for `rfft` and `irfft`.
