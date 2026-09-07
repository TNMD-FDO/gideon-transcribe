# The Interpreter's voice: Piper, Kokoro, and what the office may run

Read on 2026-09-07, before the build of Phase 3 chapter 3 (The Interpreter).
The chapter names Piper as the text-to-speech tool and asks this note for its
version, licence, and the voices chosen per language, with sources. Kokoro is
read beside it as the one credible alternative. Nothing here is
office-specific.

## Piper

**What it is.** A small neural text-to-speech engine that runs on the CPU:
one ONNX model file per voice, a few tens of megabytes each, and a
phonemiser (espeak-ng) built in. It was written for the Rhasspy and Home
Assistant projects and is now kept by the Open Home Foundation.

**Two repositories, two licences.** The original `rhasspy/piper` was archived
read-only in October 2025 under the MIT licence. Development moved to
`OHF-Voice/piper1-gpl`, which is **GPL-3.0-or-later**: it embeds espeak-ng,
itself GPL, and the new repository took that licence rather than keep the
two apart. The maintained one is the GPL one; its latest release at the time
of reading is v1.6.0 (July 2026) on GitHub and the `piper-tts` package on
PyPI is at 1.8.0 (4 September 2026).

**The package.** `piper-tts==1.8.0`: licence GPL-3.0-or-later; wheels for
Linux x86_64 and Linux aarch64 (one `abi3` wheel each, so any Python from
3.9), macOS and Windows too; runtime dependencies only `onnxruntime` and
`pathvalidate`; optional extras for training (PyTorch, Lightning) and for
Chinese, Japanese, and Thai text. The README says Piper "embeds espeak-ng
for phonemization", so nothing else is installed for the languages in the
table below. It has a command line, a Python API, and an HTTP server
(`docs/API_HTTP.md`).

**The voices.** Published on Hugging Face under `rhasspy/piper-voices`, 43
locales, each voice at a quality level (`x_low`, `low`, `medium`, `high`) and
each with a `MODEL_CARD` naming its training data and licence. The two
Spanish voices read for this note:

| Voice | Locale | Quality | Trained on | Licence on the card |
|---|---|---|---|---|
| `claude` | `es_MX` (Mexico) | high | HirCoir's Piper-TTS-Spanish data, Apache-2.0 | MIT |
| `davefx` | `es_ES` (Spain) | medium | OHF-Voice voice datasets, CC0; fine-tuned from the US English `lessac` voice | the repository's MIT |

The third Spanish locale is `es_AR` (Argentina). The full locale list is in
`interpreter-languages.md`.

**A sentence to know about.** The voices page says "Piper is intended for
personal use and text to speech research only" and warns that some voices
carry restrictive licences. That sentence is the project's guidance, not a
term of any licence: the engine is GPL-3.0 and the voices carry their own
cards, MIT and CC0 for the two above. It is why every voice the office
installs is chosen by its card, never by its name, and why the installer
records the card's licence beside the voice.

**Speed.** The project's claim is real-time or better on a modern CPU for
`medium` voices; this note found no published figure it would repeat as a
number. It is measured at the build, on the office's server, as the
benchmark gate measures WhisperX: seconds of speech produced per second of
CPU, for the voices installed.

## Kokoro

**What it is.** An 82-million-parameter text-to-speech model, `hexgrad/
Kokoro-82M`, weights under **Apache-2.0**, v1.0 of January 2025. Nine
languages: American and British English, Spanish, French, Hindi, Italian,
Japanese, Brazilian Portuguese, Mandarin. Fifty-four voices; the Spanish ones
are `ef_dora`, `em_alex`, and `em_santa`, ungraded on the voices page (graded
voices run from A to F by hours of training audio; the French `ff_siwis` is a
B-, the Hindi and Italian voices C).

**Two ways to run it.** The `kokoro` package (0.9.4, Apache-2.0) needs
PyTorch, which is the one thing the app image must never carry. The
`kokoro-onnx` package (0.6.1, MIT, August 2026) runs the same model on ONNX
Runtime without PyTorch, needs `espeakng-loader` and `phonemizer` (espeak-ng
again, GPL), and wants two files, `kokoro-v1.0.onnx` (about 300 MB, 80 MB
quantised) and `voices-v1.0.bin`. Its author reports near real-time speed on
an Apple M1.

**Where it stands against Piper.** Better-sounding voices in the languages it
has, by general report; nine languages against Piper's 43 locales; one 300 MB
model against Piper's per-voice files of tens of megabytes; and a Spanish
quality nobody has graded. A candidate for a second opinion on Spanish, not
the first choice for a tool whose point is breadth.

## What this decides for the build

- **Piper is the Voice engine**, as the chapter says, for its breadth (43
  locales, three of them Spanish), its size, its CPU speed, its aarch64 wheel
  should an office ever run on ARM, and its per-voice licence cards.
- **It runs as a service of its own, not inside the app image.** Piper is
  GPL-3.0 and the app is in the public domain (CC0). Running a GPL program as
  a separate process, spoken to over HTTP, keeps the two apart cleanly: a
  `voices` Compose service built from a two-line Dockerfile (`pip install
  piper-tts==1.8.0`, the voices mounted from the models folder), reached at
  `http://voices:5000` from the app's containers and nowhere else, under the
  same rules as the WhisperX service. The app sends text and gets audio; it
  never imports Piper. THIRD_PARTY_LICENSES.md gains a row for Piper and one
  per installed voice, from their cards.
- **The voices are fetched at install**, by `./transcribe voices add
  <language>`, from `rhasspy/piper-voices` on Hugging Face, pinned by the
  file's SHA-256 as the Whisper models are, into the models folder; never at
  run time (the app never reaches outside the building). The installer
  prints the voice's card licence as it fetches. Spanish's first voice is
  `es_MX` `claude` (high), with `es_ES` `davefx` (medium) and `es_AR` beside
  it for the Admin to choose from; a Spanish-speaking colleague picks the one
  that sounds right for the office's visitors.
- **Kokoro is held in reserve**, through `kokoro-onnx`, for the day Piper's
  Spanish is judged not good enough. Same shape: its own service, Apache
  weights, MIT runner, GPL phonemiser kept in the service.
- **Measured at the build:** speed on the office's CPU; the delay from the
  end of a Turn to the first sound; and a bilingual ear on each Spanish voice.

## Sources

- Piper's move and licences: <https://github.com/OHF-Voice/piper1-gpl> (README: "embeds espeak-ng for phonemization"; GPL-3.0 in COPYING) and the archived <https://github.com/rhasspy/piper> (MIT, read-only since October 2025), read 2026-09-07; summary of the move at <https://www.cekura.ai/discover/piper-tts>.
- The package: <https://pypi.org/pypi/piper-tts/json> (1.8.0, 2026-09-04, GPL-3.0-or-later, wheels and `requires_dist`), read 2026-09-07.
- The voices and the guidance sentence: <https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/VOICES.md>; the two Spanish cards: <https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_MX/claude/high/MODEL_CARD> and <https://huggingface.co/rhasspy/piper-voices/blob/main/es/es_ES/davefx/medium/MODEL_CARD>, read 2026-09-07.
- Kokoro: <https://huggingface.co/hexgrad/Kokoro-82M> (Apache-2.0, v1.0), <https://raw.githubusercontent.com/hexgrad/kokoro/main/README.md> (languages and codes), <https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md> (voices and grades), <https://pypi.org/pypi/kokoro/json> (0.9.4, torch required), <https://pypi.org/pypi/kokoro-onnx/json> (0.6.1, MIT, no torch), all read 2026-09-07.
