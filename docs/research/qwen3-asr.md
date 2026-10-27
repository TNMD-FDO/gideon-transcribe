# Qwen3-ASR as a second speech recogniser: the facts and the trial

Written 2026-10-26 for the recogniser choice (ADR 0025) and the translation
by the chat engine (ADR 0026). Part 1 is what the public sources say, each
with the address it was read from. Part 2 is the trial on the office's
server, counts only. Nothing here is a word of a recording.

## Part 1. The model

**What it is.** Qwen3-ASR is a speech recogniser built on the Qwen3-Omni
audio encoder with a Qwen3 language-model decoder, released 2026-01-29 under
Apache 2.0 as three open models: `Qwen/Qwen3-ASR-1.7B`, `Qwen/Qwen3-ASR-0.6B`
and `Qwen/Qwen3-ForcedAligner-0.6B`, the last a non-autoregressive aligner
that gives each word its time. Transformers gained native support
2026-06-26 (the `-hf` repositories). Sources: the repository
(https://github.com/QwenLM/Qwen3-ASR), the model cards
(https://huggingface.co/Qwen/Qwen3-ASR-1.7B,
https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B) and the technical
report (https://arxiv.org/abs/2601.21337).

**Pins used by the trial.** The 1.7B model at revision
`7278e1e70fe206f11671096ffdd38061171dd6e5` and the aligner at
`c7cbfc2048c462b0d63a45797104fc9db3ad62b7` (the Hugging Face API's `sha` on
2026-10-26, both last modified 2026-01-30). The package `qwen-asr` 0.0.6
(2026-01-30; https://pypi.org/project/qwen-asr/) pins `transformers==4.57.6`
and `accelerate==1.12.0`, with `vllm==0.14.0` behind its `vllm` extra; it
does not pin torch or flash-attn. The official image
`qwenllm/qwen3-asr:latest` is one tag, pushed 2026-01-29, digest
`sha256:fb75b775f089e06e5a1aaebffd421e37505cc630d50c86d889d95ffa45a7e16a`
(14.4 GB compressed, 42.9 GB unpacked), built from
`docker/Dockerfile-qwen3-asr-cu128`: `nvidia/cuda:12.8.0-devel-ubuntu22.04`,
`pip install qwen-asr[vllm]`, FlashAttention built from source. Inside it on
2026-10-26: torch 2.9.1+cu128, transformers 4.57.6, flash-attn 2.8.3, vLLM
0.14.0, librosa 0.11.0. A product image would be built here on the WhisperX
stack's own wheels and pinned by digest (ADR 0013), not this one.

**Accuracy as published** (the report and the README; Qwen's own test sets
where marked internal). Against Whisper large-v3, word error rate in
percent: LibriSpeech clean 1.63 against 1.51; LibriSpeech other 3.38 against
3.97; CommonVoice 9.18 against 10.77; Fleurs 12 languages 4.90 against 5.27;
Fleurs 30 languages 12.60 against 8.16 (Whisper better); ExtremeNoise
(internal, Mandarin) 16.17 against 63.17; singing (M4Singer) 5.98 against
13.58. Language identification 97.9 percent against Whisper's 94.1. No
published figure for 8 kHz telephone audio or for English and Spanish mixed
in one recording. An independent call-centre comparison at 16 kHz
(https://www.beri.net/article/deepgram-vs-assemblyai-vs-whisper-self-hosting-crossover-call-center-2026,
a vendor blog, not verified against its source) gives 8.3 against
Whisper's 15.0.

**Timing.** The recogniser writes no times. The aligner's average error in
milliseconds (the report, Table "forced alignment"): 42.9 on MFA-labelled
audio against WhisperX's 133.2; 52.9 on 300-second audio against WhisperX's
2,708.4 (the squeeze the app's clock verdict finds, ADR 0022); 32.4 on
human-labelled audio. Eleven languages, English and Spanish among them; up to
300 seconds by the card, 180 by the package's constant
`MAX_FORCE_ALIGN_INPUT_SECONDS`. Open issue 197
(https://github.com/QwenLM/Qwen3-ASR/issues/197): words with no length,
start equal to end, about 2.5 percent of words overall and 8 percent on
conversational audio; unanswered.

**Long audio.** `MAX_ASR_INPUT_SECONDS` is 1200, 180 when times are wanted;
the package cuts at a low-energy point within five seconds of each target
cut, with no overlap and nothing carried from one piece to the next
(`qwen_asr/inference/qwen3_asr.py`, `utils.py`). `max_new_tokens` is 512 on
Transformers and 4096 on vLLM. Streaming works on vLLM only, with no times.

**Language, translation, names.** Detection is automatic with `language=None`
or forced per call. Open issue 163 reports mixed Chinese and English coming
out all in English. There is no translate task: the model transcribes only.
Free-form context (names, terms) goes in as the system message
(`context=`); issue 140 (closed by a bot) reports a hotword list parroted
back under the 0.6B streaming model.

**Repetition.** The package collapses any character or short phrase repeated
twenty times or more; issue 129 (closed by a bot) reports endless repetition
on about one file in ten under vLLM 0.17.1.

**Speakers.** No diarization anywhere in the sources; the app's diarizer
stays.

**Known bugs of the Transformers path.** Issue 213: the encoder's attention
window is not applied on sdpa or eager attention, so clips over eight
seconds get full attention (FlashAttention 2 avoids it). Issue 207: batching
clips of different lengths corrupts the shorter clip (the trial ran one file
at a time).

## Part 2. The trial

Run 2026-10-26 on the office's server, on Transcribe's card (GPU 1, by UUID
through CDI) inside its 24 GB reserve, beside the idle stack and the
co-tenant's 22 GB, with the WhisperX queue empty: the official image pinned
by digest above in a scratch container with the cases folder mounted
read-only, the weights (5.3 GB) fetched once into the operator's home, no
port published, host memory capped at 24 GB. FlashAttention 2 ran on the
card (RTX PRO 6000 Blackwell, capability 12.0). The container, the image,
the weights, the outputs and the clips were removed the same evening.
Scripts: `.claude/tools/qwen-probe/` (untracked).

**What was asked.** Four recordings the maintainer named, all transcribed
by the app with Whisper large-v3 turbo, diarized by Nemotron, none with
corrected lines: three jail calls of 9, 31 and 31 minutes (one with 30
clock-marked lines, 24 of them re-timed by the re-read of ADR 0023) and a
25-minute body camera. Each was transcribed by Qwen3-ASR-1.7B with the
aligner, once with the case's names as context (the service's own prompt
line) and once without; words were aligned to Whisper's by sequence
matching; the stretches where the two differ were cut as clips, 24 per
recording spread across it with every clock-marked stretch first, and put
to the maintainer's ear on a local page with five answers: Whisper has it,
Qwen has it, both acceptable, both wrong, cannot tell.

**The first finding: the piece length.** At the package's 180-second pieces
the decoder stops early and leaves whole minutes nearly empty where the
sound level is normal: on the 31-minute call with marked lines Qwen wrote
1,820 words against Whisper's 3,202, six two-minute windows under 20 words,
and with the names context one piece looped (one four-word phrase 573
times). At 1200-second pieces (no aligner) it wrote 331 words for the whole
call. At 45-second pieces the loss vanishes: words per two-minute window
track Whisper's across every recording, with 5 to 10 percent more words than
Whisper, and no loop (the most repeated four-word phrase occurs three to
five times). Every figure below is at 45-second pieces.

**Counts, by recording** (words differ: the share of Whisper's words not
matched in Qwen's text; times: Qwen's word start against Whisper's for the
matched words; no length: the aligner's zero-length words; speed: audio
seconds per second; card: the probe's own share at the end of the run).

| Recording | Whisper words | Qwen words | Words differ | Within 2 s | Over 5 s | No length | Speed | Card |
|---|---|---|---|---|---|---|---|---|
| Jail call, 9 min | 1,050 | 1,164 | 24 % | 92 % | 5 % | 12 % | 32x | 6.9 GB |
| Jail call, 31 min | 4,009 | 4,385 | 26 % | 96 % | 2 % | 13 % | 20x | 7.3 GB |
| Jail call, 31 min, marked | 3,202 | 3,507 | 32 % | 89 % | 7 % | 16 % | 39x | 7.2 GB |
| Body camera, 25 min | 2,707 | 2,911 | 26 % | 89 % | 6 % | 18 % | 36x | 7.7 GB |

The models take 5.5 GB loaded (4.4 without the aligner). Whisper turbo
peaks at 12.3 GB and runs at about 190 times real time, so Qwen with its
aligner is five to ten times slower: about a minute for a 30-minute call.

**Names.** With the case's names as context they appear in Qwen's text 13,
24 and 22 times on the three calls, against 3, 12 and 6 without; Whisper,
given the same names, wrote them 6, 16 and 24 times. The words-differ rate
moved by one point or less.

**The clock-marked lines.** Of the 30 marked lines Qwen's aligner found 23
by their words. Of their timed words, 91 fall within two seconds of the
app's re-timed clock and 46 within two seconds of Whisper's original; where
Qwen agrees with neither it is never earlier and 24 times later, the
direction the maintainer's ear gave for the one disputed saying (ADR 0023).

**By ear, 96 items, all answered.**

| Recording | Qwen has it | Whisper has it | Both acceptable | Both wrong | Cannot tell |
|---|---|---|---|---|---|
| Jail call, 9 min | 8 | 2 | 2 | 10 | 2 |
| Jail call, 31 min | 4 | 3 | 1 | 16 | 0 |
| Jail call, 31 min, marked | 7 | 0 | 0 | 17 | 0 |
| Body camera, 25 min | 5 | 2 | 1 | 6 | 10 |
| All | 24 | 7 | 4 | 49 | 12 |

Where one recogniser had it, Qwen had it 24 times in 31 and led on every
recording; on the marked call's 14 clock-marked items, Qwen 5, Whisper 0,
both wrong 9. Half of the disputed stretches were wrong in both: on these
recordings, where the two disagree, often neither has the words, which is
the audio's own ceiling and not a thing a recogniser change fixes. The
body camera was the hardest to judge (10 of 24 cannot tell).

**Against the bar the maintainer set** (2026-10-26): fewer words wrong on
the calls and the body camera, passed; no new loops, passed at 45-second
pieces and failed at 180; timing at least as good as Whisper plus the
re-read, leaning passed on the counts above, the one disputed saying still
to be heard against Qwen's placing; the English as faithful as Whisper's,
untested, the four recordings being English, until a Spanish call and the
office's reader.

**What it decided.** The recogniser is worth building as a choice beside
Whisper (ADR 0025), with the service cutting the audio into pieces of about
45 seconds at pauses, the aligner's times taken for the words and the lines
built from them, and a word with no length given a span from its
neighbours. Since the model does not translate, Translate to English under
it is written by the chat engine from the words as spoken, which are kept
(ADR 0026). The speed and memory are acceptable: half of Whisper's card
memory, a minute for a half-hour call. Not decided by this trial: the 0.6B
model (not run), the vLLM backend (not run; the Transformers path with
FlashAttention 2 was enough), and the Spanish leg.

## Part 3. The pinned stack of the recogniser image (v1.160.0, 2026-10-27)

The counterpart of `docs/research/diarizer-pinned-stack.md` for the fourth image, `whisperx-service/recogniser/`: what it holds, why each pin is what it is, and what a bump has to prove. ADR 0025 is the decision; Part 2 above is the trial that settled the shape.

| Component | Pin | Why | Source |
|---|---|---|---|
| Base image | `nvidia/cuda:12.8.2-base-ubuntu24.04`, the same digest as the other two GPU images | One CUDA runtime for the three containers, so the package's driver requirement does not rise; the torch cu128 wheel carries its own CUDA libraries | the WhisperX Dockerfile |
| Python | 3.12, Ubuntu 24.04's | The package asks for 3.9 or above; the other images use the same | [S1] |
| torch | 2.8.0+cu128 from `download.pytorch.org/whl/cu128` | The WhisperX stack's own wheel. The package pins no torch; the trial ran on the official image's 2.9.1+cu128, and the model's code is plain transformers, so the stack's wheel is taken rather than a second torch | [S1], Part 1 |
| flash-attn | 2.8.3, the project's prebuilt wheel `flash_attn-2.8.3+cu12torch2.8cxx11abiTRUE-cp312-cp312-linux_x86_64.whl` (released 2025-08-14), sha256 `f25da18657a87fc83dc1bfb8b7751b82246e9db355510226b674fd437c34b5fb` read from the downloaded file on 2026-10-27 | The package's encoder attention window is applied only under FlashAttention 2 (issue 213), and the trial ran under it on the office's card (compute capability 12.0). Built from source it takes hours on the hosted runner; the wheel installs in seconds. cxx11abi TRUE matches the torch wheels since 2.6 | [S2] |
| qwen-asr | 0.0.6 (2026-01-30), installed with `--no-deps` | The only release at the trial; its wheel's sha256 `b9c55a38413298f3a990a4475467399daec6e8f4172363053fc42e2166c2dfd3`. Its dependency list carries the demo's gradio and flask and the vLLM extra, none of which the inference path imports, so the path's own imports are pinned instead | [S1], [S3] |
| transformers, accelerate | 4.57.6, 1.12.0 | The package's own pins | [S1] |
| librosa, soundfile | 0.11.0, 0.13.1 | librosa is what the official image carried at the trial; soundfile reads the WAV (`libsndfile1` from apt) | Part 1; [S4] |
| nagisa | 0.2.11 (with DyNet38) | The aligner imports it at module level for Japanese; manylinux wheels for cp312 exist (2024-01-28) | [S5] |
| soynlp | left out | The aligner imports it lazily for Korean text alone; it is GPL-3.0, so it stays out of the image and a Korean recording under this recogniser fails at the aligner | [S6] |
| huggingface-hub | 0.36.0 | The offline snapshot lookup by revision, as the other images do it | [S4] |
| FastAPI, uvicorn | 0.141.1, 0.52.4 | The container's small HTTP face, the same versions as the other two | `whisperx-service/requirements.txt` |
| everything else | unpinned at v1.160.0 | What the pins above pull in (tokenizers, safetensors, numpy, scipy, numba and the rest) is frozen from the first server build's `pip freeze` into `constraints.txt` at the release after this, as the diarizer's was at v1.135.0 | |

**The run.** The models load on the first piece, not at start: `/healthz` answers at once with `loaded: false`, and the first job under the choice pays the load (the trial: about 20 s). `attn_implementation` `flash_attention_2` on both models, `bfloat16`, `max_inference_batch_size` 1 (issue 207: a batch of unequal clips corrupts the shorter), `max_new_tokens` 1024 per piece (room, not a cap that cuts: a 45-second piece of fast speech is under 300 tokens). The service cuts the audio itself at about 45 seconds (Part 2's finding), so the package's own cutting at 180 never runs. Memory, from the trial: 5.5 GB held once loaded, 6.7 to 7.7 GB after a run; a job's wall time 20 to 36 times faster than real time.

**What a bump has to prove.** 1. The import at build (`from qwen_asr import Qwen3ASRModel, Qwen3ForcedAligner` and `import flash_attn` against this torch). 2. The counts of Part 2 on the same four recordings, or the difference explained: the words per window tracking Whisper's, no loop at 45-second pieces, the clock-marked lines' agreement with the re-read. 3. torch stays on the WhisperX stack's CUDA (12.8) unless that stack moves first. 4. A flash-attn wheel exists for the new torch, or the bump waits.

Sources for Part 3: [S1] qwen-asr on PyPI, https://pypi.org/project/qwen-asr/ (0.0.6, 2026-01-30; `requires_dist` read 2026-10-27). [S2] FlashAttention's releases, https://github.com/Dao-AILab/flash-attention/releases/tag/v2.8.3. [S3] The official Dockerfile, https://github.com/QwenLM/Qwen3-ASR/blob/main/docker/Dockerfile-qwen3-asr-cu128. [S4] The package's inference imports, https://github.com/QwenLM/Qwen3-ASR/blob/main/qwen_asr/inference/utils.py and `qwen3_forced_aligner.py`. [S5] nagisa on PyPI, https://pypi.org/project/nagisa/0.2.11/. [S6] soynlp on PyPI, https://pypi.org/project/soynlp/0.0.493/ (classifier GPLv3).
