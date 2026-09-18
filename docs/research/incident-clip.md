# The clip across cameras: how one file is cut from several

Written 2026-09-17 for Phase 7 chapter 1 (`docs/spec/SPEC-PHASE-7.md`),
which fixes the picture (1280 wide, Focus or Grid, the clock top right, the
ids bottom left, a camera that ends inside the span black in its tile) and
leaves the filter graph, the tile sizes at each count and what is measured
on the worker to the build. This note records the graph as built in
v1.63.0, why each filter is there, the escaping that a string passing three
of ffmpeg's parsers needs, the checks the design was put through before it
was written, and the by-hand check still owed on the worker.

## The command

One ffmpeg per Incident clip, built as a list of arguments (no shell) by
`media.wall_arguments` and run through `media._run`, which prepends the
thread cap as it does for every call. Every tile has an input, in tile
order, so tile k is input k; a camera whose playback copy is missing fails
the render before ffmpeg runs (`clip_work.tiles_of`), never a black
stand-in, because a clip made for a hearing must not quietly lose a camera.

```
ffmpeg -nostdin -y -v error
  [for each tile k]  -threads N -ss SEEK_k -t READ_k -i <playback copy k>
  -filter_complex_threads N -filter_complex "<graph>"
  -map [v] -map [a] -t L -threads N
  -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p
  -c:a aac -b:a 128k -movflags +faststart <clip>.mp4
```

with L the span's length and, per camera, from the offset stored in the
Clip's picture (the camera's own second at the clip's first frame, negative
when it starts inside the span):

- `SEEK_k = max(0, offset_k)`, before its `-i`, so ffmpeg decodes from the
  keyframe before the point and drops the frames up to it: the cut is
  frame-accurate and the input's clock starts at zero (cut_clip's own rule).
- `LEAD_k = max(0, -offset_k)`, the black before the camera's first frame.
- `READ_k = L - LEAD_k`, before its `-i`, so nothing past the span is
  decoded.

An option before an `-i` applies to that input alone, which is why the
seek, the length and the thread cap are repeated: the cap `_run` prepends
reaches input 0 only, and the encoder takes the cap written before `-c:v`.

## The graph

Per tile, W by H its box from `media.tile_boxes`:

```
[k:v]setpts=PTS-STARTPTS,fps=30,
  scale=w='trunc(min(W,H*dar)/2)*2':h='trunc(min(H,W/dar)/2)*2',
  pad=W:H:-1:-1:color=black,setsar=1,
  tpad=start_duration=LEAD_k:stop_duration=L:color=black,format=yuv420p,
  drawtext=fontfile='<DejaVuSans.ttf>':fontsize=S:fontcolor=white:borderw=2:
    bordercolor=black@0.5:textfile='<tile-k.txt>':expansion=none:x=8:y=h-th-8[tk]
```

- `setpts` pins the tile's first frame to zero whatever fraction of a frame
  the seek landed on.
- `fps=30` gives every tile one frame rate before they are stacked. xstack
  is a framesync filter and would otherwise emit at the combined rate of a
  25 and a 30 fps camera, and the clock would tick unevenly. It also sets
  the link's frame rate, which tpad needs to turn a duration into a count
  of frames.
- `scale` by display aspect: `dar` is the input's display aspect, so a
  source with non-square pixels (a CCTV export at 704 by 480, a DV tape) is
  fitted by how it looks and not by its pixel count, which the simpler
  `force_original_aspect_ratio` would squash once `setsar=1` follows. A 4:3
  or a portrait phone gets black bars; nothing is distorted. `trunc(x/2)*2`
  keeps every size even, as yuv420p needs. The single quotes are for the
  graph parser, which would otherwise split the chain at the comma inside
  `min()`.
- `pad` with `-1:-1` centres the picture in its box; `setsar=1` squares
  the pixels.
- `tpad` is the black tile: `start_duration` paints LEAD seconds before a
  camera that starts inside the span, `stop_duration=L` paints black after
  one that ends inside it. Both bounded, never `stop=-1`, so no stream is
  infinite even if the output `-t` were lost; the file is at most 2L before
  `-t` trims it.
- `format=yuv420p` makes every stacked input the same.
- `drawtext` comes after tpad so the id is on the black frames too. It reads
  the id from a file with `expansion=none`, so a colon, a quote, a percent
  sign or a backslash in a recording's title is drawn as it is and never
  passes through the graph. 22 px on a tile 360 high or more, 16 px below,
  8 px from the bottom left; the id cut to 40 characters on a tile 640 wide
  or more and 30 on a narrower one, because DejaVu Sans is about nine
  pixels a character at 16 px and drawtext neither wraps nor shrinks.

The stack, for two or more tiles, and the clock:

```
[t0][t1]...xstack=inputs=n:layout=x0_y0|x1_y1|...:fill=black,
  drawtext=fontfile='<DejaVuSans.ttf>':fontsize=28:fontcolor=white:borderw=2:
    bordercolor=black@0.5:x=w-tw-16:y=16:text='%{pts\:gmtime\:DELTA\:%T}'[v]
```

`fill=black` paints every pixel no tile covers (a short Focus row, a Grid at
3, 5, 7 or 8). With one camera there is no xstack; the tile chain runs
straight into the clock. With Burn the clock off, or no Incident clock, the
clock drawtext is left out; with Burn the camera ids off, every tile's.

The sound, from the sound camera's input alone:

```
[k:a]apad=whole_dur=L[a]                                             LEAD_k = 0
[k:a]adelay=delays=LEADMS:all=1,aresample=async=1:first_pts=0,
     apad=whole_dur=L[a]                                             LEAD_k > 0
```

`adelay` writes the lead as silence: ffmpeg 7.1's `af_adelay.c` moves the
delay every channel shares into a padding it emits as silent frames before
the first input frame, and places each input frame at its own time plus
that delay. (The first reading of the source, that the common part only
shifted the timestamps, was wrong; the build's review corrected it.) The
resample with `async=1:first_pts=0` (the app's `KEEP_THE_CLOCK`, used on
every playback copy) is kept as belt and braces: it pins the track's first
sample to zero whatever the copy's own start time, and on a track that
already starts at zero it does nothing. `apad` pads silence after a camera
that ends inside the span, so the audio track is the span long and no
player stops early.

## The clock

`%{pts\:gmtime\:DELTA\:%T}`: the frame's second plus DELTA, formatted as a
time of day in UTC with strftime's `%T` (`%H:%M:%S`). DELTA is
`int(round(clock_zero + from_at)) % 86400`, computed once when the clip is
made and stored in the picture (`incident_clips.clock_delta`): a whole
number so the first frame reads exactly what the box said (drawtext floors
the sum where the page rounds), wrapped into the day so the sum is never
negative (a negative time_t would truncate towards zero and read a second
late) and a clip across midnight reads 00:00:05 as the page does. `gmtime`
rather than `localtime` because DELTA is already the second of the day on
the Incident clock and the container's time zone must not be applied;
rather than `hms` because hms prints milliseconds and never wraps.

Render again burns the stored DELTA on purpose: the chapter says it remakes
the clip the same. A person who wants a corrected clock after a re-sync
makes a new clip from the event. On an Incident with no clock nothing is
burned: elapsed time in hh:mm:ss would read as a time of day just after
midnight.

## The escaping, the whole of it

The filter string passes three parsers. (1) The graph parser splits on
`,` `;` `[` `]` and copies what is inside single quotes literally,
backslashes included. (2) Each filter's option parser splits on `:` and
`=` and turns a backslash-colon into a colon. (3) drawtext's own expander
splits a `%{...}` function's arguments on the colons that are left. Only
one string carries backslashes: the clock's text, quoted at the first
layer, its argument separators written `\:`, and `%T` rather than
`%H:%M:%S` so no colon inside the format needs a third layer. Camera ids
never enter the graph (the id files). File names get the captions' rule:
backslash to slash, colon to `\:`, in single quotes (`media.filter_path`).
`media.clock_text` is one raw string with a test that pins its bytes.

## The tiles

Picture 1280 wide; heights follow from the rows. Every size even.

| Layout | Cameras | Tiles | Picture |
|---|---|---|---|
| Focus | 1 | 1280 by 720 | 1280 by 720 |
| Focus | 2 to 5 | the first 1280 by 720; the rest 320 by 180 on the row at y 720, centred (2: x 480; 3: 320, 640; 4: 160, 480, 800; 5: 0, 320, 640, 960) | 1280 by 900 |
| Grid | 1 | 1280 by 720 | 1280 by 720 |
| Grid | 2 | 640 by 360, two across | 1280 by 360 |
| Grid | 3 or 4 | 640 by 360, two across, two rows (at 3 the last slot black) | 1280 by 720 |
| Grid | 5 or 6 | 426 by 240 at x 0, 428, 854, two rows | 1280 by 480 |
| Grid | 7 to 9 | 426 by 240, three rows | 1280 by 720 |

Three 426-wide tiles make 1278, so the columns sit at 0, 428 and 854 with a
two-pixel black gutter after the first tile and none after the second,
keeping the picture 1280 wide, each tile exactly 16:9, and every tile on an
even column: at an odd x, xstack would copy a tile's colour planes one luma
pixel off its luma (a colour fringe down both edges of the middle column).
Focus holds up to five cameras, as the chapter's row of four small tiles
fixes; past five the box starts from Grid.

## How the design was checked before it was written

Two designs were drawn independently (a simple one and a fidelity-first
one), judged against each other, and the chosen one was then given to
three reviewers told to refute it. They found, and the build fixed: a
sound chain that needed the first sample pinned to zero (and a misreading
of adelay, corrected above by the build's second review, which also found
the odd column); the anamorphic squash above; a 40-character
id running off a 320-wide tile; the encoder's threads left uncapped; a
clock burned from elapsed time reading as a time of day; a rule the chapter
never made (refusing a sound camera that runs under a second of the span);
the migration clash with the chronology fields of the same release; the
Clips page reading span and length fields the row never had; the viewer's
Clips sheet offering Adjust and Play on a clip cut from several cameras;
and the case's Clips tab printing the sound camera's raw seconds. Each is
in v1.63.0's tests.

## What is still owed: the by-hand check on the worker

No ffmpeg runs in the test suite (its `_run` is a fake that records the
arguments), and the workstation this was built on has none, so the graph
has been checked by reading ffmpeg 7.1's sources and documentation and not
by running it. At the server upgrade, on the media worker (whose ffmpeg is
Debian 13's `7:7.1.5-0+deb13u1`, per `THIRD_PARTY_LICENSES.md`):

1. Make three short test videos with ffmpeg itself, as playback copies of
   three recordings in a test case: `testsrc2` at 30, 25 and 15 fps, one of
   them 4:3 and one with a sample aspect of 16:15, each with a sine tone at
   48 kHz, of different lengths. Place them on an incident, add an event,
   press Clip this event for a Focus clip and a Grid clip.
2. `ffprobe` each: 1280 by 900 and 1280 by 720, 30 fps, the duration equal
   to the span within a frame, aac at 48 kHz, and for the audio stream
   `start_time` 0.000 and the span's duration (not the lead and span minus
   lead).
3. Frames grabbed at t = 0, 0.99, 1.00 and the end: the clock reads the
   box's start time on the first frame, changes on the frame at each whole
   second, and wraps if a span crosses midnight.
4. The black tile appears the moment the shorter camera ends with its id
   still drawn; a camera starting inside the span is black first, and its
   sound, when it is the sound camera, is silent first; the 4:3 source has
   centred bars; the 16:15 source is not squashed.
5. The ids read at 320 by 180 and the clock at 28 px on a projector; the
   file plays in Chrome and Edge from the Clips page and in VLC; ffmpeg's
   stderr is empty (no font warning).
6. With the inputs repeated to nine, the wall time and peak memory (`docker
   stats`) for a 60 s span against the time limit (the span plus five
   minutes plus a minute per camera), and the file size per minute at 1280
   by 900 and 1280 by 720. `CAMERA_SECONDS` in `clip_work.py` is raised if a
   minute per camera is not enough on the office's CPU.

Record the results here when done.

## Sources

- ffmpeg 7.1 filter documentation: scale (`dar`, `force_divisible_by`),
  pad, setsar, tpad, fps, format, xstack (`fill`, 4.4), drawtext (`pts`
  with `gmtime` and a strftime format, `textfile`, `expansion`), adelay
  (`all`), apad (`whole_dur`), aresample (`async`, `first_pts`), read at
  https://ffmpeg.org/ffmpeg-filters.html on 2026-09-17.
- ffmpeg 7.1 sources read the same day: `libavutil/avstring.c`
  (`av_get_token`, the quoting and escaping rule), `libavfilter/graphparser.c`
  (the graph parser's separators), `libavutil/opt.c` (`av_opt_get_key_value`),
  `libavfilter/vf_drawtext.c` (`func_pts`, the argument order and the
  truncation to `time_t`), `libavfilter/af_adelay.c` (the common-delay
  timestamp shift), `libswresample/swresample.c` (`swr_next_pts`, the
  silence injected at `first_pts`), `libavfilter/vf_scale.c`
  (`ff_scale_adjust_dimensions` working on pixel sizes).
- `THIRD_PARTY_LICENSES.md` for the ffmpeg build in the app image.
- The Clips chapter of `docs/spec/SPEC-PHASE-1.md` and `media.cut_clip`, for
  the seek-before-input rule and the codec options.
