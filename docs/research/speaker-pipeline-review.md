# The speaker pipeline reviewed: is what the app runs the best it can do locally?

Read on 2026-09-14, at the maintainer's ask after the Speaker check
(Phase 5 chapter 3) shipped, to check the whole chain that turns voices
into named speakers against what is available to run on the office's own
server. Primary sources where they exist; a claim without one is marked.

## What the app runs today

| Step | What | Where it is decided |
|---|---|---|
| Telling voices apart | `pyannote/speaker-diarization-community-1` through pyannote.audio 4.0.7 inside WhisperX 3.8.6: powerset segmentation, WeSpeaker embeddings, VBx clustering [S1][S2] | `docs/research/whisperx-pinned-stack.md` |
| Words to voices | `whisperx.assign_word_speakers`, each word to the voice talking over it | `whisperx-service/service/model_process.py` |
| The count hint | `exactly N` or `between N and M` per recording, passed to pyannote as `num_speakers` or `min_speakers`/`max_speakers`; per Side on a call | `docs/whisperx-api.md` |
| Fixing the split by the words | The Speaker check: the engine proposes lines to move among the speakers there are; a person accepts | Phase 5 chapter 3 |
| Naming | Suggest names from the words, the Case's People first; the Speakers page with samples, lanes, merge and the number keys | Phase 1, Phase 2, Phase 5 chapter 1 |
| Recognising a voice heard before | Reserved: the service already returns one embedding per speaker; nothing is stored or compared yet | Phase 5 chapter 2, not in force |

## The diarization model

- **community-1 is the current open release of the most used diarization
  stack.** It came with pyannote.audio 4.0 and is released MIT (code) and
  CC-BY-4.0 (weights), gated behind a Hugging Face token. Against 3.1 the
  published numbers are 17.0% against 18.8% DER on AMI (IHM), 20.3%
  against 24.5% on AliMeeting, 11.7% against 12.2% on AISHELL-4, with the
  gain mostly in speaker counting and confusion, the two things that go
  wrong on a body-camera scene [S1][S2].
- **An independent benchmark (September 2025) put DiariZen ahead of the
  open field** at 13.3% DER on 196 hours across five languages, two points
  behind pyannote's commercial model at 11.2% [S3]. DiariZen's weights are
  CC BY-NC 4.0, non-commercial only, and it is built on pyannote 3.1 with
  torch 2.1.1 [S4]: it cannot drop into a stack that WhisperX holds at
  pyannote 4 and torch 2.8 [S5]. Not a candidate today; worth a look if its
  authors move to pyannote 4.
- **NVIDIA's Nemotron 3 Diarization (2026-09-23)** lifts the Sortformer
  line's ceiling to eight speakers and is open and ungated. Probed on
  2026-09-24 (`docs/research/nemotron-3-diarization.md`): the only
  corrected recording proved a bad reference, and by ear Nemotron was right
  where the page was wrong on eleven of thirteen disputed stretches. A
  proper trial is proposed there; the paragraph below stands only on its
  facts, and "the right model to run" is an open question.
- **NVIDIA's Sortformer** is an end-to-end model with a ceiling of four
  speakers, English first, inside the NeMo research toolkit [S6][S7]. A
  traffic stop with two officers, a driver, a passenger and dispatch is
  over its ceiling. Not a candidate.
- **Joint transcription-and-diarization models** (Diarization-Conditioned
  Whisper and its speaker-attributed successors) are research code with
  published weights for narrow settings and no serving stack the office
  could pin [S8][S9]. Watch, do not adopt.

So the model the app runs is the right one to run, and the gap to the best
commercial system is about two points of DER, not a different league.

## Where the remaining accuracy is

1. **The count hint.** pyannote's own failure analysis and the benchmark
   agree that missed speech and speaker confusion at high speaker counts
   are the main errors [S3]. A right `exactly N` removes the counting
   problem outright. The app carries the hint but leaves it empty unless a
   person fills it; defaults by recording type (a jail call is two per
   Side, an interview two or three, a body camera between two and six)
   are the cheapest gain left and need no model change.
2. **Correcting the split by the words works, and the literature says
   how much.** Google's DiarizationLM (2024) cut word diarization error by
   55% on Fisher and 45% on Callhome by handing the diarized transcript to
   a language model and taking its corrected labels back [S10]. Two things
   differ from the app's Speaker check: their model was fine-tuned for the
   job (an 8-billion Llama 3 fine-tune is published, phone calls, two
   speakers, Llama licence [S11]), and it rewrites the labels of a whole
   passage rather than listing moves, which forces a coherent reading of
   the scene. The office's engine is a general model on a prompt, which is
   why the probe found it eager and blind to the scene. The next two steps
   for the check follow from this: a sketch of the whole recording ahead
   of every window, and an experiment with the rewrite form (the engine
   returns the window with corrected labels; the app diffs) in place of
   the list of moves.
3. **Naming.** No local method names a voice from sound alone; a name
   comes from the words (someone says it) or from having heard the voice
   before. Suggest names covers the first. The second is voice prints:
   comparing the speaker embeddings the service already returns across
   the recordings of a Case, so an officer named on Monday's stop is
   offered first on Tuesday's. The embedding model (WeSpeaker, inside
   community-1) is the same family the speaker-verification field uses
   [S12]; newer embeddings (ReDimNet, ECAPA2) score better on verification
   benchmarks but would mean a second model beside the pipeline [S13].
   Phase 5 chapter 2 stays the right shape: embeddings kept per Case,
   compared by cosine similarity with a threshold a person can raise, the
   match offered and never applied, and Phase 1's rule against stored
   embeddings amended first.
4. **The audio.** Nothing above beats the recording: a body camera in a
   wind, a jail phone, a hearing room microphone. Calls already go
   through per Side. There is no local step that recovers what the
   microphone lost.

## What is not worth doing now

- Swapping the diarization model: nothing open and compatible beats
  community-1 for this office's recordings.
- A second language model fine-tuned for diarization: the office's
  engine is GIDEON's, serving one model, and the published fine-tunes
  are English phone calls with two speakers.
- Streaming or real-time diarization: the app transcribes recordings, not
  live rooms, and Sortformer's ceiling rules it out anyway.

## Sources

- [S1] https://huggingface.co/pyannote/speaker-diarization-community-1
- [S2] https://www.pyannote.ai/blog/community-1
- [S3] https://arxiv.org/abs/2509.26177 (Benchmarking Diarization Models)
- [S4] https://github.com/BUTSpeechFIT/DiariZen
- [S5] https://raw.githubusercontent.com/m-bain/whisperX/main/pyproject.toml
- [S6] https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1
- [S7] https://www.pyannote.ai/blog/pyannote-vs.-nvidia-nemo-diarization-accuracy-setup-and-production-readiness
- [S8] https://arxiv.org/abs/2501.00114 (DiCoW)
- [S9] https://arxiv.org/abs/2510.03723 (speaker-attributed Whisper)
- [S10] https://arxiv.org/abs/2401.03506 (DiarizationLM)
- [S11] https://github.com/google/speaker-id/tree/master/DiarizationLM
- [S12] https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb
- [S13] https://arxiv.org/pdf/2606.22369 (Kiwano, with the ReDimNet and ECAPA2 comparison)
- Also read: https://www.pyannote.ai/benchmark; https://github.com/pyannote/pyannote-audio; `docs/research/speaker-suggestions.md`; `docs/research/speaker-check-probe.md`.
