# Speaker verification: TitaNet-large measured on the office's recordings

Read and measured 2026-10-16 to 2026-10-19, stage one of the voice plan (the measurement before any design, gate B). Part 1 is the research report of 2026-10-16: the free speaker verification models compared from primary sources and the two facts that bite. Part 2 is the pin: the model, how it loads through the NeMo the diarizer image already carries, and what it costs. Parts 3 to 6 are the probe: the model run by hand on the office's server in a scratch container from the diarizer image, on three recordings the maintainer judged by ear on a local page, and the counts. Part 7 is what was decided from them. Nothing of the app or the service changed; the scripts live in the session tools folder, untracked; the container and its weights were removed after.

## Part 1. The models that are free and fit

A speaker verification model turns a stretch of speech into a vector so that two stretches can be compared by one number. The app's diarizer (Nemotron 3) gives spans and word labels, not voices: nothing in the app can say how sure the voice step was of a line, or whether two lines are the same voice. The literature in `docs/research/speaker-attribution.md` says where the gain is: text-only correction over-corrects, grounding in the voice raised errors corrected and cut errors introduced, and a voice confidence given as words (low, medium, high) is what a language model handles best.

| Model | Size | Error rate on VoxCeleb1 | Licence | Telephone speech in training | Fit with the stack |
|---|---|---|---|---|---|
| **NVIDIA TitaNet-large** | 23M parameters, vectors of 192 | 0.66% EER | CC-BY-4.0 (the Hugging Face card; the older NGC page points at the NeMo licence) | **Yes**: Fisher, Switchboard and NIST SRE 2004 to 2010 beside VoxCeleb and LibriSpeech; "trained on both telephonic and non-telephonic speech" | Loads in the diarizer container the app already runs (NeMo's `EncDecSpeakerLabelModel`); no new package, no new image |
| WeSpeaker ResNet34-LM | 6.6M, vectors of 256 | 0.72% EER | Toolkit Apache 2.0; the pyannote wrapper CC-BY-4.0 | No (VoxCeleb) | pyannote 3.1's embedding model; the WhisperX image carries pyannote |
| SpeechBrain ECAPA-TDNN | about 22M | 0.80% EER | Apache 2.0 | No (VoxCeleb) | A new package in either image |
| CAM++ and ERes2Net (3D-Speaker, Alibaba) | 7M to 22M | 0.65% to 0.52% EER | Toolkit open source; the models' terms to check | Largely Chinese corpora | A new package |

The error rates are within a hair of each other on clean studio speech, so the choice is made by the other columns: TitaNet-large is the only one trained on telephone recordings, which is what a jail call is, and it runs in the container the app already has. The named fallback, had it not loaded, was WeSpeaker ResNet34-LM in the WhisperX image.

**Two facts that bite.** Short lines are unreliable: every study agrees the vector of a one-second stretch is poor (one ECAPA baseline went from about 2.4% error at three seconds to about 18% at one second, the biggest fall between one and two seconds), so the voice must be allowed to say cannot tell under a floor. Telephone audio is narrowband: a jail call carries nothing above 4 kHz and the models are trained at 16 kHz; a wideband model on upsampled telephone audio does worse than one trained on telephone data (one study saw error rise from 7.6% to 8.8% from upsampling alone). A third fact helps: thresholds do not travel between datasets, and the remedy is calibration on matching data, which each recording supplies itself.

## Part 2. The pin, and what it costs

| Fact | Figure |
|---|---|
| Model | `nvidia/speakerverification_en_titanet_large`, revision `0dc382f40121a5fbd34db10a2bb04d826c2be6a8` (the repository's only commit, 2023-11-14) |
| File | `speakerverification_en_titanet_large.nemo`, 101,621,760 bytes, sha256 `e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3` |
| Licence | CC-BY-4.0; attributed as pyannote's community-1 is |
| Loads through | the NeMo Speech commit the diarizer image pins (`cf724ac3`, reporting itself as 3.1.0) on torch 2.8.0+cu128: `EncDecSpeakerLabelModel.restore_from` in 0.4 s |
| Vectors | 192 numbers per stretch; `forward(input_signal, input_signal_length)` on a padded batch returns `(logits, embeddings)`; `infer_segment` takes one stretch in memory |
| Card memory | 0.27 GB at peak for the model alone; 1.7 GB at peak embedding 953 clips of a 40-minute case, 2.3 GB for 604 clips of a 25-minute body camera |
| Time | 0.7 to 0.9 s to embed a whole case's clips (22 minutes of speech), 6 s with the load and the file reads |
| The diarizer's frame doubt | Yes: at this commit `SortformerEncLabelModel.diarize(..., include_tensor_outputs=True)` returns the spans and, beside them, the per-frame speaker probabilities, a tensor of 6,000 frames by 8 speaker slots for 60 seconds of audio; `forward` returns the same. The run on a 6-second stretch failed inside a Triton template compile and ran with `TORCH_COMPILE_DISABLE=1`; a free second signal exists, with that caveat |

Well inside the diarizer's 4 GB of host memory and Transcribe's 24 GB card reserve; nothing for the box ledger beyond the line the probe left.

## Part 3. How the probe measured

- **Clips cut by words.** Each Segment's clip is the span of its timed words minus the words the diarizer gave to another label, padded by 30 ms; a mixed line is split at the word where the label changes and its parts embedded apart. Net seconds of speech is what the floor is measured against.
- **Voice prints per Speaker.** One vector per Speaker and Side: the mean of its lines of three seconds or more, outliers dropped (more than two and a half scaled median deviations below the median cosine) and the mean re-taken until it settles; at least three lines, else no print. The plan's rule left lines under a pending proposal of the Speaker check out; the re-scoring (Part 6) also tried every line of a label.
- **Calibration on the recording.** For each undisputed line, the cosine to its own print against the best other; per duration bucket (under the floor, floor to the rule, over the rule), the firm threshold is the tenth percentile of that margin where it is positive, else a quarter of the median, never under 0.02. A line is **agrees** when the move the words propose gains at least the threshold, **against** when it loses as much, **cannot tell** between, under the floor, or where a print is missing.
- **The voice's own proposals.** Undisputed lines far from their own print and near another's, under a cap of fifteen per recording.
- **A second voice under one label.** Within one Speaker, two or three clusters of the lines' vectors that are apart by the recording's own midpoint, each of three lines and ten seconds or more, that also separate in time (eight in ten lines on their side of the change); never proposed where the clusters differ in loudness by 6 dB or more (a shout is not a second voice).
- **The call system.** Lines whose words carry one of a generic, editable list of phrases a prepaid call system says, read against the parties' prints: unlike every party, or like one.
- **Across calls.** The caller's print from the first call against the parties of the second, the gap between the best and the next match, and the lines of the second call the print picks.
- **The judgement sheet.** A local page, nothing of a recording leaving the building: each recording's labels with a sample of what the diarizer grouped under each, then a sample of lines, each with a Play button (the line with a second either side, cut from the prepared audio into a folder beside the page) and the question "which sample does this voice match": one button per label, "a voice not in the samples", "the phone system" on calls, "cannot tell". The maintainer need never know who a person is. For each label the sample matched most often is the label's owner; a line is right when its voice matches its label's owner. The voice's own answers stay hidden on the page. A first version asked "is this line Speaker 1" and was unanswerable where a label held three people; a second asked who the person was, which the ear cannot say; the third form is the one that worked.

## Part 4. The recordings

Three recordings in two Cases on the office's server, all processed with large-v3-turbo and the Nemotron diarizer on 2026-10-19, read from the database by query (no page opened, no audit row written).

| Recording | Length | Lines | Labels the diarizer made | Lines per label | Median line | The check's proposals pending |
|---|---|---|---|---|---|---|
| A jail call, judged by ear before the probe | 9.2 min | 170 | 3 | 96, 73, 1 | 1.36 s | 0 |
| A second jail call by the same caller | 31.2 min | 661 | 5 | 447, 96, 60, 47, 11 | 1.18 s | 118 |
| A body camera recording | 24.9 min | 497 | 7 | 177, 149, 118, 14, 11, 8, 5 | 0.96 s | 335 |

The lines are short: on the 9-minute call 92 of 155 scored lines are under 1.5 s and 15 over 3 s. On the first call, one label held three people by the maintainer's ear (the recorded announcement, the person who answered, and the person the phone was passed to). The Speaker check had proposed moves on 118 lines of the second call and 335 of the camera's 497, none of them decided.

On the sheets: 143 items for the calls (78 ordinary lines, 40 of the check's proposals, 24 announcement lines, 1 second-voice change) and 85 for the camera (39 ordinary lines, 40 proposals, 6 of the voice's own proposals); 132 and 82 answered. The camera's condition chips (quiet, noisy, distant, radio under it, shouting, overlapped) were not used, so the body camera's curve by condition is still to be measured.

## Part 5. The counts

**The labels.** By the maintainer's ear the diarizer's label was wrong on 23 of 92 judged lines on the calls (25%) and 8 of 42 on the camera (19%). On the first call the wrong lines are mostly the second and third person under one label.

**The words-only check.** Of its proposals the maintainer could judge, the check was right on 0 of 9 on the calls and 3 of 17 on the camera. Twelve of forty camera proposals and twelve of forty call proposals were lines the ear could not place either.

**The voice, under four rules for a Speaker's print.** The same answers scored four times; "speaks" is the share of judged lines where the voice said agrees or against rather than cannot tell, "right" how often that matched the ear.

| Rule | Calls: speaks | Calls: right | Camera: speaks | Camera: right |
|---|---|---|---|---|
| As planned: undisputed lines only, 3 s to join, cannot tell under 1.5 s | 27 of 79 (34%) | 23 of 27 (85%) | 14 of 37 (38%) | 14 of 14 (100%) |
| A: every line of a label, 3 s, 1.5 s | 39 of 79 (49%) | 36 of 39 (92%) | 16 of 37 (43%) | 16 of 16 (100%) |
| B: every line, 2 s, 1.5 s | 45 of 79 (57%) | 40 of 45 (89%) | 17 of 37 (46%) | 17 of 17 (100%) |
| C: every line, 2 s, 1 s | 55 of 79 (70%) | 49 of 55 (89%) | 23 of 37 (62%) | 23 of 23 (100%) |

Under the plan's rule the second call had one print and the camera two of seven labels, because the pending proposals took most lines out; under rule B the second call has four prints (7, 8, 12 and 100 lines) and the camera six (3 to 39 lines).

**The recording's own curve** (every undisputed line against its label, rule B; the buckets are under the floor, floor to the rule, over the rule):

| | Calls: lines | Calls: voice agrees with the label | Calls: firmly against | Camera: lines | Camera: agrees | Camera: firmly against |
|---|---|---|---|---|---|---|
| under 1.5 s | 422 | 91% | 7% | 83 | 63% | 34% |
| 1.5 to 2 s | 100 | 95% | 0% | 22 | 86% | 9% |
| over 2 s | 165 | 99% | 0% | 35 | 74% | 17% |

Under rule C the voice was firmly against the label on 41% of the camera's sub-second lines, more than twice the error the ear found, so a 1-second floor over-reaches on a camera; on the calls the same rule stayed at 7%.

**Lines the words never flagged.** The voice's own proposals: 0 on the calls under the plan's rule (4 under rule C, none on the sheet); 6 on the camera, every one "cannot tell" by ear.

**The second voice under one label.** One proposed, on the 9-minute call, the label that held three people: judged real. One candidate on the camera held by the loudness guard. The ten wrong lines the ear found on that call were caught by the voice on at most one, under any rule: a print built from a label that holds two people is a blend of both and cannot separate them. The clustering did.

**The call system.** 29 announcement lines found by phrase on the two calls; of the 24 on the sheet every one was marked the system by ear, and the voice read 23 of 24 as unlike every party. One system line the phrase list missed. The announcement lines' mean cosine among themselves was 0.33 to 0.36.

**Across calls.** The caller's print from the first call matched one label on the second at cosine 0.87, but the second call's other labels had too few long lines for a print, so there was no second party to tell the caller apart from. Unmeasured; it needs a call where both parties speak at length.

## Part 6. Against the bar

The plan's bar, per kind: right on nine in ten decided stretches where the voice speaks; speaks on two thirds; beats the words-only check on the same stretches.

| Kind | Right where it speaks | Speaks on two thirds | Beats the check |
|---|---|---|---|
| Jail call | 85 to 92% (passes under rule A only) | 34 to 70% (passes under rule C only) | Yes, everywhere (the check 0 of 9) |
| Body camera | 100% under every rule | 38 to 62% (fails) | Yes (the check 3 of 17) |

Neither kind clears the bar as written under one rule. The voice is right where it speaks, on a camera without exception on these 60-odd stretches; it is quiet on a third to half of lines because they are short, and because a print starved of lines gives it nothing to compare with.

## Part 7. What was decided

On 2026-10-19 the maintainer read the counts and took the recommendation:

1. **A Speaker's print is built from every line of its label with outliers dropped, not from the undisputed lines only** (the plan's rule starved the prints wherever the check had proposed much). Lines of two seconds or more join it. This is rule B.
2. **The floor is a setting per Recording type.** Cannot tell under 1.5 seconds as shipped; a lower floor (1 second) is allowed where it helps, which on these recordings was the calls and not the camera.
3. **The second-voice finding is the main instrument for a merged label.** A print cannot split a label that holds two people; clustering within the label found the one real case. The finding keeps its loudness guard. (The plan's word for it, "hand-over", is proposed and not yet in the glossary.)
4. **The words-only check stays, with the voice's word on every proposal**, as the plan says; on these recordings it was right on 3 of 26 judged proposals, so a proposal the voice is against should be shown as such.
5. **Still to measure before the body camera's switch ships on:** the curve by condition (the chips were not used), and a second call where both parties speak at length for the cross-call print. The measurement tooling is kept for both.

## Sources

- TitaNet-large model card: https://huggingface.co/nvidia/speakerverification_en_titanet_large (licence, training sets, 0.66% EER, the telephone statement, the one commit); NGC page: https://catalog.ngc.nvidia.com/orgs/nvidia/nemo/models/titanet_large/- (192 dimensions, the NeMo licence pointer); the paper: https://arxiv.org/pdf/2110.04410
- NeMo Speech at the pinned commit, the speaker model and the diarizer: https://github.com/NVIDIA-NeMo/Speech/blob/cf724ac337d1ebc7d0dda1e23fb80916f52927a5/nemo/collections/asr/models/label_models.py and `.../sortformer_diar_models.py`
- WeSpeaker: https://github.com/wenet-e2e/wespeaker (Apache 2.0, ResNet34 0.723% EER); the pyannote wrapper: https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM
- SpeechBrain ECAPA-TDNN: https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb (Apache 2.0, 0.80% EER, 16 kHz); the paper: https://arxiv.org/pdf/2005.07143
- 3D-Speaker toolkit: https://github.com/modelscope/3D-Speaker and https://arxiv.org/pdf/2403.19971 (CAM++ 0.65%, ERes2Net figures)
- Short utterances: https://arxiv.org/pdf/2008.12218; https://arxiv.org/abs/2406.02167 (the 2.4% to 18.4% fall); https://arxiv.org/pdf/2606.13712 (the jump between 1 and 2 seconds); https://arxiv.org/pdf/2002.06033
- Telephone bandwidth: https://www.isca-archive.org/odyssey_2020/sivaraman20_odyssey.pdf (wideband models on 8 kHz); https://arxiv.org/pdf/2007.14146 (7.6% to 8.8% from upsampling); https://www.isca-archive.org/interspeech_2018/nidadavolu18_interspeech.html
- Confidence and refinement: https://arxiv.org/pdf/2406.17124 (confidence measures; the lowest 10% holds about 30% of errors); https://arxiv.org/pdf/2510.19572 (VBx: short segments dropped before centroids); https://arxiv.org/pdf/2109.06483 (duration-gated centroid updates); https://arxiv.org/pdf/2501.16641 (length-aware similarity)
- Calibration: https://arxiv.org/pdf/2102.01760 (thresholds do not transfer); https://github.com/zh794390558/sv_score_calibration; https://speechbrain.readthedocs.io/en/stable/API/speechbrain.inference.speaker.html (the default 0.25 cosine threshold)
- Already in the repository: `docs/research/speaker-attribution.md` (AG-LSEC, SEAL, DiarizationLM, the interactive-correction figures); `docs/research/diarizer-pinned-stack.md`; `docs/research/nemotron-3-diarization.md`; `docs/spec/SPEC-PHASE-5.md` chapters 2 to 4; `app/core/speaker_check.py` (`voice_of`, `voices_heard`); `whisperx-service/diarizer/server.py`
