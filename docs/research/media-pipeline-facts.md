# Media pipeline facts: upload, transcode, playback, waveform

Research date: 2026-09-02, gathered while resolving the "Media handling from browser to ASR to player" ticket. Primary sources only; "not found" marks the unverifiable.

## 1. Resumable upload for a Django app behind Caddy

| Component | Latest release | Licence | Status |
|---|---|---|---|
| tusd (official tus server, Go, separate container) | v2.10.0, 2026-06-16 | MIT | Actively maintained; official image `tusproject/tusd`; flags `-base-path`, `-upload-dir`, `-max-size`, `-behind-proxy` |
| tus-js-client | 4.3.1 stable (2025-01-16); 5.0.0-pre2 (2026-01-13) | MIT | Maintained |
| Uppy (`@uppy/core`, `@uppy/tus`) | 6.0.0, 2026-08-26 | MIT | Actively maintained; `@uppy/tus` wraps tus-js-client |
| drf-tus (Django REST Framework tus server) | 2.0.3, 2026-01-06 | MIT | The only Django-side tus server with a 2026 release; needs DRF |
| django-tus | 0.5.0, 2020-10-01 | MIT | Dormant (README targets Django 2.2 to 3.2) |
| resumable-upload (pure Python) | 0.1.1, 2026-07-31 | MIT | Brand new, tiny community |
| django-chunked-upload | 2.0.0, 2019-12-15 | MIT-0 | Not tus; no release in over six years |

tusd behind a proxy: use `-behind-proxy` so it honours `X-Forwarded-Host` and `X-Forwarded-Proto`; the proxy must not buffer request bodies (Caddy's `request_buffers` is opt-in, so Caddy streams by default; `request_body max_size` exists for a cap). tusd HTTP hooks (`-hooks-http <url>`, events pre-create, post-create, post-receive, pre-finish, post-finish, pre-terminate, post-terminate) POST JSON to the app; `post-finish` fires after all upload data is received.

Simplest free path: run `tusproject/tusd` as a sidecar container with `-behind-proxy -base-path /files/ -hooks-http http://app:8000/upload-hook/ -hooks-enabled-events pre-create,post-finish`, its upload directory on a volume shared with the app and the media worker, Caddy routing `handle_path /files/*` to tusd; browser side Uppy with `@uppy/tus` or plain tus-js-client. The app implements only the two hook endpoints (session check on pre-create, register the file on post-finish). Large bodies never pass through the Python web server. If a pure-Django route is required, drf-tus is the only maintained option.

## 2. What WhisperX does with an input file

`whisperx/audio.py` (`SAMPLE_RATE = 16000`) runs, verbatim:

```
ffmpeg -nostdin -threads 0 -i <file> -f s16le -ac 1 -acodec pcm_s16le -ar 16000 -
```

Output: raw signed 16-bit little-endian PCM, mono, 16 kHz, read from stdout and converted to float32 by dividing by 32768. On failure it raises `RuntimeError("Failed to load audio: ...")`. The path goes straight to `-i`, so any input ffmpeg can demux and decode is accepted, video containers included; with several audio streams ffmpeg picks the one with the most channels. A prepared 16 kHz mono WAV therefore passes through untouched.

## 3. Browser playback

- **PCM inside MP4: not playable in Chrome or Edge.** MDN lists AAC, FLAC, MP3, and Opus as the audio codecs supported in MPEG-4. Chromium's MP4 parser (`media/formats/mp4/fourccs.h`, `box_definitions.cc`) defines no PCM sample entry at all. The corpus's interview-room video (H.264 plus PCM s16le in mp4) needs its audio re-encoded to AAC for playback.
- **G.729: no browser support found** in MDN's codec guide or Chromium's list. Transcode server-side; ffmpeg decodes it.
- **HEVC/H.265 in MP4:** MDN: Chrome supports HEVC only on devices with hardware decode (Windows 8+); Edge needs the Microsoft Store "HEVC Video Extensions". Chromium: "requires hardware support". No software fallback, so transcode video to H.264 for playback.
- **VBR MP3 seeking without a Xing/Info header is imprecise in Chromium.** `ffmpeg_demuxer.cc`: "Seeking in MP3s is not precise due to our usage of AVFMT_FLAG_FAST_SEEK"; ffmpeg's `mp3dec.c` falls back to scaling byte position by time, which lands wrong on VBR files. Firefox behaviour: not verified. Never serve VBR MP3 for playback; use AAC in m4a, Opus, CBR MP3, WAV, or FLAC.
- **moov atom placement.** Apple's QuickTime documentation: a movie plays as it downloads only when the movie header (moov) is at the start of the file. ffmpeg's `-movflags +faststart` runs a second pass moving the index to the front and is off by default. Whether range requests rescue a trailing moov: not found. Always write `+faststart`.

## 4. ffmpeg availability

- Debian 13 trixie ships `ffmpeg 7:7.1.5-0+deb13u1`; Docker's `python:3.12` and `python:3.12-slim` tags currently alias `3.12.14-trixie`. Debian 12 bookworm ships `ffmpeg 7:5.1.9-0+deb12u1`.
- ffmpeg's codec table lists G.729 as decode-only (native decoder; do not confuse with the "G.729 BIT" file format row). Debian's build rules for both packages disable no decoders and never mention g729, so the native decoder ships in both. Not executed: `ffmpeg -decoders | grep g729` inside the image; one `docker run` closes that at build time.
- BtbN/FFmpeg-Builds: still published daily (GPL and LGPL, static and shared, Linux x86_64) on GitHub Releases, free. johnvansickle.com builds are GPLv3 but stale (7.0.2, 2024-06-29). Prefer the Debian trixie package or BtbN.

## 5. BBC audiowaveform and wavesurfer.js

- audiowaveform: GPL-3.0; not in the Debian archive; the project publishes `.deb` files on GitHub Releases for Debian 10 to 13 (`audiowaveform-1.10.2-1-13.amd64.deb` for trixie); latest tag 1.10.3 (2025-08-20) ships no binaries and is functionally identical to 1.10.2. Run it as a separate command-line process (GPL, not linked into the app). Inputs MP3, WAV, FLAC, Ogg Vorbis, Opus; outputs `.dat`, `.json`, `.png`. Example: `audiowaveform -i in.wav -o out.json -z 256 -b 8`. JSON fields: `version, channels, sample_rate, samples_per_pixel, bits, length, data` (interleaved min/max integer pairs).
- wavesurfer.js 7.12.11 (2026-07-17), BSD-3-Clause: accepts `peaks` (arrays of floats per channel) and `duration` as pre-computed data via `load(url, channelData, duration)`, default backend MediaElement. Convert audiowaveform's integer pairs to floats (divide by 128 or 32768) before handing them over.

## 6. ffmpeg loudnorm

"EBU R128 loudness normalization. Includes both dynamic and linear normalization modes. Support for both single pass (livestreams, files) and double pass (files) modes." Defaults: integrated loudness `I` = -24.0 LUFS (range -70 to -5), `LRA` = 7.0, true peak `TP` = -2.0 dBTP. The transparent linear mode needs two passes: pass 1 `loudnorm=print_format=json` to a null output, pass 2 with the four `measured_*` values and `linear=true`; otherwise it reverts to dynamic mode. In dynamic mode the stream is upsampled to 192 kHz for true-peak detection, so set the output sample rate explicitly (`-ar`). `dual_mono=true` treats mono files meant for stereo playback correctly.

## 7. Telling a genuine two-party stereo file from dual-mono

No single ffmpeg flag; three documented filters combine in one `-f null -` pass each:

- `aphasemeter` measures cross-channel phase in [-1, 1] and, with `phasing=1`, logs "mono" sequences (start, end, duration) in a stereo stream; options `tolerance` (default 0) and `duration` (default 2 s). Documented example: `ffmpeg -i stereo.wav -af aphasemeter=video=0:phasing=1:duration=1:tolerance=0.001 -f null -`. Dual-mono logs "mono" for essentially the whole file; one party per channel does not.
- `astats` reports per-channel RMS and peak levels (`lavfi.astats.1.RMS_level` and so on), which catches a silent channel (one-sided recording).
- `pan=1c|c0=c0-c1,astats` measures the left-minus-right difference signal; an overall RMS tens of dB below each channel's own RMS means identical channels. `channelsplit` writes each channel to its own stream when separate files are wanted.

## Not verified

- Firefox seeking in header-less VBR MP3; any browser statement on range-request fallback for a trailing moov.
- `ffmpeg -decoders` was not run inside the Debian image (build flags checked instead).

## Sources

- WhisperX audio.py: https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/audio.py
- ffmpeg stream selection: https://ffmpeg.org/ffmpeg.html
- tusd: https://github.com/tus/tusd/releases , https://github.com/tus/tusd , https://tus.github.io/tusd/getting-started/installation/ , https://tus.github.io/tusd/getting-started/configuration/ , https://tus.github.io/tusd/advanced-topics/hooks/
- tus implementations: https://tus.io/implementations
- npm registry: https://registry.npmjs.org/tus-js-client , https://registry.npmjs.org/uppy , https://registry.npmjs.org/@uppy/tus , https://registry.npmjs.org/wavesurfer.js
- PyPI: https://pypi.org/pypi/django-tus/json , https://pypi.org/pypi/drf-tus/json , https://pypi.org/pypi/tuspy/json , https://pypi.org/pypi/django-chunked-upload/json , https://pypi.org/pypi/resumable-upload/json
- GitHub: https://github.com/alican/django-tus , https://github.com/dirkmoors/drf-tus , https://github.com/juliomalegria/django-chunked-upload , https://github.com/sts07142/resumable-upload
- Caddy: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy , https://caddyserver.com/docs/caddyfile/directives/request_body
- MDN: https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Containers , https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Audio_codecs , https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs
- Chromium: https://www.chromium.org/audio-video/ , https://chromium.googlesource.com/chromium/src/+/main/media/formats/mp4/fourccs.h , https://chromium.googlesource.com/chromium/src/+/main/media/formats/mp4/box_definitions.cc , https://chromium.googlesource.com/chromium/src/+/main/media/filters/ffmpeg_demuxer.cc
- ffmpeg mp3 demuxer: https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavformat/mp3dec.c
- Firefox VBRI bug: https://bugzilla.mozilla.org/show_bug.cgi?id=1500713
- Apple QuickTime fast start: https://developer.apple.com/library/archive/documentation/QuickTime/Conceptual/QTScripting_HTML/QTScripting_HTML_Document/ScriptingHTML.html
- ffmpeg formats (faststart): https://ffmpeg.org/ffmpeg-formats.html
- Debian ffmpeg: https://packages.debian.org/trixie/ffmpeg , https://packages.debian.org/bookworm/ffmpeg , https://sources.debian.org/src/ffmpeg/7:7.1.5-0+deb13u1/debian/rules/ , https://sources.debian.org/src/ffmpeg/7:5.1.9-0+deb12u1/debian/rules/
- Docker python tags: https://raw.githubusercontent.com/docker-library/docs/master/python/README.md
- ffmpeg codec table: https://ffmpeg.org/general.html
- BtbN builds: https://github.com/BtbN/FFmpeg-Builds/releases ; John Van Sickle: https://johnvansickle.com/ffmpeg/
- audiowaveform: https://github.com/bbc/audiowaveform , https://raw.githubusercontent.com/bbc/audiowaveform/master/COPYING , https://github.com/bbc/audiowaveform/releases , https://github.com/bbc/audiowaveform/blob/master/doc/DataFormat.md , https://packages.debian.org/sid/audiowaveform
- wavesurfer.js options: https://raw.githubusercontent.com/katspaugh/wavesurfer.js/main/src/wavesurfer.ts
- ffmpeg filters (loudnorm, astats, aphasemeter, pan, channelsplit): https://ffmpeg.org/ffmpeg-filters.html
