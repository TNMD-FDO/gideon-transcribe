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

## The probe, 2026-11-02

Run read-only on the office's server at the maintainer's word, with the
scripts kept beside the session's checks (`probe_sound_match.sh`, `2.sh`,
`3.sh` under the maintainer's local tools): three incidents with 26 cameras
placed from checked clocks, so every pair's true shift was known; 14 true
pairs, and 6 pairs of cameras from different incidents, which never overlap.
The audio was whole (16 kHz, 10 to 126 MB a file) and a pair matched in
well under a second. Counts and seconds only; nothing of the sound left the
server.

| Search | True pairs within 2.5 s of the clocks | True strengths | False strengths |
|---|---|---|---|
| The whole range (the app's way with no file time) | 1 of 14 | 1.01 to 1.61 | 1.07 to 2.57; four of six at or over 1.5 |
| Ten minutes either side of the clocks' shift (the app's way when both files carry a time) | 8 of 14 | right ones 1.43 to 3.49; two wrong ones 2.06 and 1.63 | not run |
| One minute either side | 11 of 14 | right ones 1.95 to 5.94, one at 1.04 | wrong ones 1.07, 1.1, 1.63 |

The errors on the right matches were 0.1 to 0.7 s, with three at about
2.1 s, against clocks that drift a second or two. A second statistic, the
peak's prominence over every shift tried (in spreads above the mean),
separated nothing: the false pairs scored highest on it, up to 26.

What follows: the loudness-envelope correlation is a fine adjustment near
a known shift and unreliable over an unknown one, and its strength says
nothing on its own, since it depends on how wide the search was. At the
1.5 line a whole-range search would have placed four of the six false
pairs as Matched by sound. So (v1.183.0, `incidents._match_near`): a match
is looked for within a minute of the files' own shift first and applied as
Clear at 1.8 or more (ten right, none wrong on these pairs); else within
ten minutes, applied as Likely when it agrees with that shift to two
seconds at 1.5 or more; else, and always when the files carry no time,
Unclear, shown with its lag and never applied by the app. The Surety word
beside every placed pill (`CONTEXT.md`) is the same scale for the clocks:
checked on two frames is Clear, read once is Likely.

Still open: whether the match near a known shift stays right on a street
with wind and traffic (these incidents were the office's own, of unknown
kind to this note), and whether a better statistic than the peak ratio
exists for the whole-range case; a spectral method (onsets by band rather
than loudness alone) is the next thing to try if a surety over an unknown
shift is ever wanted.

## Sources

The app's own media facts (`docs/research/media-pipeline-facts.md`: the ASR
audio is 16 kHz mono 16-bit WAV). Cross-correlation of onset envelopes is
the standard way of aligning two recordings of one event; NumPy's `fft`
module documentation (numpy.org) for `rfft` and `irfft`.
