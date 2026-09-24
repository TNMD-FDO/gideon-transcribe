# Nemotron 3 Diarization: what it is, and how it scored on an office recording

Read 2026-09-24, the day after NVIDIA released the model, at the maintainer's ask ("is it worth pivoting to it?"). Part 1 is the model's facts from primary sources; part 2 is a probe on the office's server: the model run once, by hand, in a scratch container on the Transcribe card, against the one recording the office has corrected line by line, and scored beside what the app runs today. Nothing of the app or the service changed; the probe image was removed after.

## Part 1. The model

| Fact | What the sources say | Source |
|---|---|---|
| Released | 2026-09-23 | [S1] |
| Weights and licence | `nvidia/Nemotron-3-Diarization` on Hugging Face, OpenMDW License 1.1, commercial use allowed, **not gated** (no token, unlike pyannote's community-1) | [S1] |
| The preview | A second repo, `-preview`, is gated under NVIDIA's evaluation licence: internal testing only, no production, no publishing of results. Not the one to use | [S2][S6] |
| Shape | About 100M parameters: a 31-layer Transformer encoder with rotary positions and a Conv1D upsampler to 10 ms frames; one pass does segmentation, embedding and clustering (end to end, the Sortformer line) | [S1] |
| Speakers | Up to **eight**, ordered by arrival; overlap handled; output is a `[T, 8]` tensor of per-frame speaker probabilities, post-processed to spans | [S1] |
| No count hint | No `num_speakers` or min/max: the model decides. The app's Speaker-count hint has no equivalent on this path | [S1][S3] |
| No embeddings | Nothing per speaker comes out but the spans; the one-vector-per-speaker that pyannote returns (kept for voice prints, Phase 5 chapter 2) has no source here | [S1] |
| Input | 16 kHz mono WAV/FLAC/Opus/MP3; offline and streaming; long files by chunked inference ("not limited when chunked"), with a note that quality "can still degrade on unusually long recordings" | [S1][S3] |
| Runs on | NeMo 3.0 (`nemo-toolkit[asr]`), also through Transformers and a C++ port; PyTorch with optional `torch.compile`; BF16; Ampere to Blackwell, tested on an RTX PRO 5000 Blackwell (the office's cards are RTX PRO 6000 Blackwell) | [S1][S3] |
| NeMo 3.0's own pins | Released 2026-08-07; Python 3.10+, "PyTorch 2.7 or above"; the actively tested set is Python 3.13 with PyTorch 2.11 (CUDA 12.9) or 2.12 (CUDA 13.2) | [S4][S5] |
| Published DER | DIHARD III 12.73 (against 19.09 for NVIDIA's earlier four-speaker Sortformer), CALLHOME part 2 9.10 (10.32), AliMeeting near 6.40 (11.57), at 30.4 s latency; an independent leaderboard puts it first at 14.72 against 19.3 for the next system | [S1][S3][S7] |
| Speed | RTFx about 12,000 to 15,000 batched at 30 s latency on that card; one card said to hold hundreds of concurrent streams | [S1][S3] |
| Word attribution | NVIDIA's own recipe pairs it with an ASR model and gives each word the speaker active at its midpoint; WhisperX's `assign_word_speakers` does the same from a table of spans, so the app's downstream is untouched by which diarizer made the spans | [S3]; `whisperx-service/service/model_process.py` |
| Telemetry | None mentioned on the card; the weights are fetched once and run offline (pyannote 4, by contrast, sends per-call metrics unless `PYANNOTE_METRICS_ENABLED=0`) | [S1]; `docs/research/whisperx-pinned-stack.md` |

**One fact the card does not say, found by the probe:** the released `nemo-toolkit` 3.0.0 on PyPI cannot load the model. Its Transformer encoder refuses `self_attention_model='rope'` ("only 'abs_pos', 'rel_pos', and 'no_pos'"), and the model is built on rotary positions. The model needs the NeMo Speech repository past 3.0.0; the probe installed it from GitHub at commit `cf724ac3` (2026-09-23). Until NVIDIA cuts a release with it, a pin means a git commit, not a PyPI version, which the pinned-stack rule does not like.

**The engineering question.** The WhisperX service is a pinned stack: torch 2.8.0+cu128, pyannote.audio 4.0.7, whisperx 3.8.6 (`docs/research/whisperx-pinned-stack.md`). NeMo 3.0 says torch 2.7 or above and tests on 2.11 and 2.12. So the model *may* install beside the pinned torch, but nobody has tested that pairing, and NeMo is a large toolkit with its own pins on Lightning, transformers and numpy. The safe shape is a second small container (the model, NeMo's ASR extra, nothing else) that the service calls for the spans, the way the service is already a separate container the app calls; the WhisperX image stays as it is. A one-image shape is worth a try only in a research ticket with the pinned-stack note's method, never in a release.

**What the app would give up or change if it adopted it.** The Speaker-count hint (Upload page, per Side on a call) does nothing on this path and the specification would say so; voice prints would need a separate embedding model; a third pinned model joins the app's care, with its research note and re-verification at each bump; and live speaker labels become possible later, since the model streams.

## Part 2. The probe

Run 2026-09-24 on the office's server, on the Transcribe card beside an idle WhisperX, in a scratch container (`python:3.12-bookworm`, `nemo-toolkit[asr]` from the NeMo Speech repository at `cf724ac3`, which pip resolved to torch 2.14.0+cu130, transformers 5.17.0, lightning 2.4.0; 12.5 GB image, 190 MB of weights, removed after). Nothing of the app or the service was touched; the recording's prepared 16 kHz WAV was read from its case folder read-only, and the spans were written to a scratch folder outside `/data`.

**What was asked.** The office has corrected exactly one recording line by line: a 25-minute video in a case, five voices, 497 lines, 2,813 aligned words, 164 Speaker check corrections accepted (the earlier probe found no line moves at all; the Speaker check has since made them). The interviews with corrections are Live two-channel recordings whose only changes are merges, which say nothing about a split, so they were left out. Both diarizers were scored at the word level against the names the office settled on: pyannote's word labels are the ones the service stored; Nemotron's are the speaker active at each word's midpoint in its spans (the model's own attribution rule), and again by the span overlapping the word most. Labels were mapped to names one to one by the best matching (a system that finds more voices than there are pays for the extras), and again many to one (each label to its commonest name, the kindest reading). pyannote was run by the app with no speaker-count hint, so neither side had help.

**What came back.**

| System | Voices found (five settled) | Words under the wrong name, one to one | Many to one | Words given no voice |
|---|---|---|---|---|
| pyannote community-1, as the app ran it | 5 | **8.8 %** (246 of 2,813) | 8.8 % | 15 |
| Nemotron 3, as loaded (its low-latency values) | 8 | 32.1 % | 24.7 % | 150 |
| Nemotron 3, the card's offline configuration | 7 | 33.9 % | 32.1 % | 159 |
| Nemotron 3, offline, attribution by overlap | 7 | 31.3 % | 29.5 % | 188 |

Nemotron diarized the 25 minutes in 5.5 seconds with 2.3 GB of card memory in use (WhisperX's idle share included). Its spans covered 787 of the 1,496 seconds; its largest voice was 76 % one person by words and its second 90 %, and the rest were fragments of the five, so the error is over-splitting and confusion, not missed speech alone.

**Two things to weigh against the figure.** The truth was made by correcting pyannote's own output, so a pyannote error the office did not notice counts in pyannote's favour; that bias is real but small beside a threefold gap. And one recording is one recording: a night-time body camera with radio traffic is a hard case, and the model was a day old with no community settings for it. A second corrected recording of another kind would be worth scoring the day the office makes one; the scoring script (`.claude/tools/nemotron_score.py`, untracked) takes the export and an RTTM and prints the table.

**What it decided.** Not a pivot: the model the app runs stays. Nemotron 3 is faster by an order of magnitude and easier to ship (no gating, no token), but on the one recording the office can score it was three to four times worse at putting words under the right name, found seven or eight voices where the office settled on five, and would take away the speaker-count hint and the embeddings that voice prints need. Revisit when NVIDIA cuts a NeMo release that loads it, when a second corrected recording exists, or when someone publishes body-camera results. The Sortformer paragraph in `speaker-pipeline-review.md` is corrected only on its ceiling; its conclusion stands.

**The run, for the ledger.** One scratch image built twice (12.4 GB and 12.5 GB on the Docker volume) and run twice on the Transcribe card within its reserve, about twenty minutes of card time in all, by day, with no service touched; both images are to be removed, and the next ledger entry says so.

## Links

- [S1] Model card: https://huggingface.co/nvidia/Nemotron-3-Diarization
- [S2] The preview's card and its access terms: https://huggingface.co/nvidia/Nemotron-3-Diarization-preview
- [S3] NVIDIA's write-up with the run recipe and the word-attribution rule: https://huggingface.co/blog/nvidia/nemotron-diarization
- [S4] nemo-toolkit on PyPI (3.0.0, 2026-08-07): https://pypi.org/project/nemo-toolkit/
- [S5] NeMo Speech on GitHub (tested versions): https://github.com/NVIDIA-NeMo/Speech
- [S6] On the preview's evaluation-only terms: https://runtimewire.com/article/nvidia-nemotron-diarization-eight-speakers-open-weights
- [S7] The leaderboard figure: https://alphasignal.ai/news/nvidia-s-nemotron-3-beats-12-rivals-with-a-14-72-speaker-error-rate
- `docs/research/speaker-pipeline-review.md`: the review this note corrects on NVIDIA's models.
- `docs/research/speaker-check-probe.md`: the earlier probe, and its finding that hand corrections are scarce.
