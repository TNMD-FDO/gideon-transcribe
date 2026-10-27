# 25. The recogniser is a choice, Whisper by default, Qwen3-ASR in a container of its own

Date: 2026-10-26. Status: accepted. Release: v1.160.0, 2026-10-27 (Phase 1 chapter 7, "The recogniser"); the translation under it, ADR 0026, not yet built.

## Context

Whisper's limits keep costing the office: words wrong on jail calls and
body cameras, repetition loops and words made up over silence, lines placed
early in a block (the clock verdict and re-read of ADRs 0022 and 0023
measure and patch it; the cause is Whisper's own rough utterance stamps,
which confine the word fitting), and weak handling of calls that mix
Spanish and English.

Qwen3-ASR (Apache 2.0, 2026-01-29) is a recogniser of a different kind: a
language-model decoder over an audio encoder, with a separate forced aligner
that times every word (`docs/research/qwen3-asr.md`). Tried on four of the
office's recordings on 2026-10-26, it had the words right 24 times to
Whisper's 7 where one of them did, led on every recording, agreed with the
app's re-read on the clock-marked lines where Whisper's original did not,
used half of Whisper's card memory, and looped nowhere once the audio was
cut into short pieces. It does not translate and it does not tell voices
apart.

Three things made the shape a decision rather than a swap:

1. **Its stack is not the WhisperX stack.** `qwen-asr` pins transformers
   4.57.6 and brings its own torch; the WhisperX image is pinned on purpose
   (`docs/research/whisperx-pinned-stack.md`) and must not move.
2. **It needs the audio cut short.** On the package's 180-second pieces the
   decoder stops early and leaves minutes empty; on 1,200-second pieces it
   wrote a tenth of the words. At 45-second pieces it keeps up everywhere.
   Whoever cuts owns the seams, the progress and the loops.
3. **Whisper is still needed.** Translate to English, the Fast lane and
   Live recordings, and an office with no chat engine all rest on it.

## Decision

- **The recogniser is a Panel setting**, Whisper or Qwen3-ASR, default
  Whisper, read when each Job is sent; the service takes it as a request
  field and returns one result shape whichever runs. The Whisper path is
  today's code, untouched.
- **Qwen3-ASR runs in a fourth image built here**, `recogniser`: the
  1.7B model and the 0.6B aligner, each pinned by revision in `models.yaml`
  and fetched at install, offline afterwards; the package pinned by version;
  FlashAttention 2, which runs on the office's card; the same rules as the
  other three images (ADR 0013). The WhisperX service calls it over the
  service's private network, one piece at a time, as it calls the
  diarizer (ADR 0014).
- **The service cuts the audio** into pieces of about 45 seconds at pauses
  with its own voice detection, sends each with the Vocabulary as context
  under the same 200-term rule, and keeps each piece's own language, so a
  mixed call stays Spanish where Spanish was spoken.
- **The lines are built from the aligner's words**: cut at pauses and
  sentence ends under a longest line, then split where the diarizer's
  speaker changes. A word the aligner gives no length takes a short span
  from its neighbours, and the count goes in `settings_used`. Whisper's
  utterance stamps, the cause of the squeeze, are not in this path.
- **Under Qwen3-ASR the service refuses `translate`**; Translate to English
  is the app's, by ADR 0026. The Fast lane stays on Whisper. The Model
  setting (large-v3 or turbo) is Whisper's and greys with its reason under
  the other choice.

## Consequences

- `CLAUDE.md`'s three images become four; CI's compose check and the
  release workflow build and publish four; the digest check covers four.
- About 7 to 8 GB of the card while a recording is recognised under
  Qwen3-ASR, against Whisper turbo's 12.3 GB; the models 5.5 GB held when
  loaded. A half-hour call takes about a minute instead of ten seconds. The
  box ledger's §3 line is unchanged; the figures go in the entry at the
  release.
- Every Transcript records which recogniser wrote it, in the Provenance,
  on Details and in the notices, which read "Whisper {model}" today and
  gain the recogniser's name.
- The clock verdict goes on checking every Transcript; its marked-line
  count becomes the measure of the new timing.
- The pinned-stack discipline applies to a fourth stack: a research note
  records what the image holds and why, and a bump is a research ticket
  first.
- Not built, and still the maintainer's: the 0.6B model, the vLLM backend,
  and Qwen3-ASR on the Fast lane.

## Settled by the build (v1.160.0)

- The cut lands on the quietest 100 ms within five seconds of each
  45-second target, the package's own rule, in the service's own code; a
  tail under a second stays on the piece before it. No voice-activity model
  is loaded for it.
- The container loads its two models on the first piece, not at start, so
  an office that keeps Whisper pays nothing on the card for it; the service
  checks the container answers before it accepts a job, as it does for the
  diarizer. A job under Qwen3-ASR lets go of the Whisper model the service
  held, so the two recognisers' memory is never on the card at once from
  the service's side: the worst case is Whisper's 12 to 17 GB beside the
  container's 5.5 GB held after its last job, inside the ledger's 24 GB
  with the diarizer's idle share. The Fast lane names no recogniser container and refuses the
  choice (`recogniser_unavailable`) rather than running Whisper quietly.
- At submit the service refuses `task=translate`, `translate_if_needed`
  and `translate_if_mixed` under Qwen3-ASR, whatever the language, since
  the language is not known until the job runs; the app sends `transcribe`
  for a Recording that asked for English and greys the Upload page's
  Translate to English with its reason until ADR 0026's path is built.
- A Transcript Qwen3-ASR wrote keeps its clock marks as the measure of the
  new timing and gets no re-read: the re-read is Whisper's path, and it
  would put one recogniser's words under another's lines.
- The lines: a new one at a pause of 0.7 seconds, after a sentence end,
  where a piece in another language begins, or past 15 seconds or 40
  words; then split where the diarizer's speaker changes. A word with no
  length takes up to 0.3 seconds forward to the next word, or back to the
  previous one.
- The prompt rule's cap counts words under Qwen3-ASR, the context being a
  system message with no token slot; the order of dropping stands.
- The transitive package tree of the fourth image is frozen at the first
  server build into `constraints.txt` in the release after this, as the
  diarizer's was (v1.135.0).
