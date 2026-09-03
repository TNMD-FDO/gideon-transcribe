# Pinned WhisperX stack for RTX PRO 6000 Blackwell

Research date: 2026-09-01. Target: two RTX PRO 6000 Blackwell (sm_120, 96 GB GDDR7 each [S1]) on driver 595, Ubuntu 26.04.1 host, Docker. Primary sources only; "not found" marks the unverifiable.

## Recommended pin set

| Component | Pin | Why | Source |
|---|---|---|---|
| Base image | `nvidia/cuda:12.8.2-base-ubuntu24.04` | CUDA 12.x runs on any driver >= 525 [S2]; driver 595 natively supports CUDA 13.x [S3]. The only ubuntu26.04 images are 13.3.x, which need driver >= 610 [S2][S4]. The torch cu128 wheels bring their own CUDA 12.8 libs, so "base" is enough. | [S4] |
| Python | 3.12 | whisperx needs `>=3.10,<3.14` [S5]; torch 2.8.0 ships cp39-cp313 [S6]; torchcodec 0.7 is `<=3.13` [S7] | |
| whisperx | 3.8.6 (2026-05-25) | latest stable; 3.8.7rc1 (2026-06-26) is a prerelease | [S5] |
| faster-whisper | 1.2.1 (2025-10-31) | latest; Silero VAD v6 | [S8][S9] |
| ctranslate2 | 4.8.2 (2026-08-31) | latest; includes the sm120 INT8 fix from 4.6.2 and CUDA 12.8 wheels from 4.6.3 | [S10][S11] |
| torch / torchaudio | 2.8.0+cu128 (2025-08-06) | whisperx pins `torch~=2.8.0`, `torchaudio~=2.8.0` [S5]; install from `download.pytorch.org/whl/cu128` [S12] | [S6] |
| torchvision | 0.23.0 | whisperx pins `~=0.23.0`; pairs with torch 2.8 [S13] | [S5] |
| torchcodec | 0.7.0 | whisperx `>=0.6,<0.8`, pyannote `>=0.7.0`; 0.7 pairs with torch 2.8 and needs FFmpeg 4-9 in the image | [S5][S7][S14] |
| nvidia-cudnn-cu12 / cublas / cuda-runtime | 9.10.2.21 / 12.8.4.1 / 12.8.90 | exact pins carried by torch 2.8.0; CT2 wheels are built against the same CUDA 12.8.93 and cuDNN 9.10.2.21 | [S6][S15] |
| pyannote.audio | 4.0.7 (2026-06-30) | latest; needs torch >= 2.8, torchcodec >= 0.7; whisperx needs >= 4.0.0 | [S14][S5] |
| transformers | 4.57.6 (2026-01-16) | last 4.x. whisperx 3.8.6 caps `huggingface-hub<1.0.0` and transformers 5.x needs `huggingface-hub>=1.5`, so 5.x is unresolvable | [S5][S16][S17] |
| huggingface-hub | 0.36.2 (2026-02-06) | last 0.x; satisfies whisperx `<1.0.0`, transformers `<1.0,>=0.34`, pyannote `>=0.28.1` | [S18] |
| ASR models | `Systran/faster-whisper-large-v3` (3.09 GB, MIT); `mobiuslabsgmbh/faster-whisper-large-v3-turbo` (1.62 GB, MIT); `distil-whisper/distil-large-v3.5-ct2` (1.51 GB, MIT) | faster-whisper's own name map | [S19][S20] |
| Diarization | `pyannote/speaker-diarization-community-1` | whisperx default; CC-BY-4.0; auto-gated | [S21][S22] |

Cross-check: the maintainers' `uv.lock` (main) locks the same torch 2.8.0+cu128, torchvision 0.23.0, torchcodec 0.7.0, transformers 4.57.6 and cuDNN 9.10.2.21, with pyannote-audio 4.0.4, ctranslate2 4.6.0 and faster-whisper 1.2.0 [S23]; this set moves those three forward for the Blackwell INT8 fix.

PyTorch stable is 2.13.0 with a CUDA 13 default on PyPI [S24]; do not use it: whisperx pins 2.8 and CT2 ships CUDA 12 wheels only (CUDA 13 request #1933 open) [S25], so a cu13 torch would put the wrong cuBLAS on the path.

## Engine: whisperx, faster-whisper, CTranslate2, CUDA, cuDNN

- CT2 wheels are built on manylinux_2_28 with CUDA 12.8.93, `-DWITH_CUDNN=OFF`, `-DCUDA_DYNAMIC_LOADING=ON`, `-DCUDA_ARCH_LIST="Common"` under cmake 3.22 [S15][S26]. In cmake 3.22 the "Common" set tops out at `8.6` plus `8.6+PTX`; no 9.0, 10.0 or 12.0 SASS can be emitted [S27]. So on sm_120 the CT2 kernels run from driver-JIT-compiled PTX. It works (the old image proved it), but expect a first-load JIT pause and no Blackwell-tuned kernels.
- INT8 on Blackwell: `CUBLAS_STATUS_NOT_SUPPORTED` on RTX 50xx with any int8 compute type (issue #1865); fixed in 4.6.2 by removing int8 from the supported types for sm120, so `compute_type=auto` picks float16 [S28][S29]. Pin float16.
- faster-whisper on Linux needs cuBLAS for CUDA 12 and cuDNN 9 for CUDA 12, and documents `LD_LIBRARY_PATH` pointing at the pip `nvidia.cublas.lib` and `nvidia.cudnn.lib` dirs [S30]. The torch 2.8.0 pins supply exactly those.
- cuDNN 9.25.1 is current; compute capability 12.0 requires CUDA >= 12.8 and driver >= 570.26 [S31]. CUDA 12.8 added compiler support for SM_100, SM_101, SM_120 [S32]. Torch 2.7 introduced Blackwell support in the cu128 wheels; 2.8 added sm12x FP8 paths [S33][S34].

## Diarization: pyannote.audio, model choice, gating, embeddings

- community-1: CC-BY-4.0, gated "auto" (accept terms, give affiliation and use case, HF read token) [S21][S22]. VBx clustering, plus an `exclusive_speaker_diarization` output with no overlaps [S35]. DER improves on 10 of 12 benchmarks versus 3.1, ties VoxConverse, and worsens on REPERE (7.9 to 8.9); e.g. AliMeeting 24.5 to 20.3, DIHARD 3 21.4 to 20.2 [S22].
- 3.1: MIT, gated, and also requires accepting `pyannote/segmentation-3.0` (MIT, gated); its embedding model `wespeaker-voxceleb-resnet34-LM` is CC-BY-4.0 and not gated [S36][S37][S38].
- Embeddings: `SpeakerDiarization.apply` returns a `DiarizeOutput` with `speaker_embeddings` as a `(num_speakers, dimension)` array of clustering centroids, `None` only under OracleClustering or `legacy=True` [S39]. WhisperX's `DiarizationPipeline.__call__(..., return_embeddings=True)` reads `output.speaker_embeddings` and returns `{speaker: vector}`; the CLI flag is `--speaker_embeddings` and `assign_word_speakers` attaches them to the result [S40][S41]. WhisperX reads `output.speaker_diarization`, not the exclusive variant.
- pyannote 4 sends telemetry per pipeline call (pipeline class, file duration, speaker-count args); disable with `PYANNOTE_METRICS_ENABLED=0` [S42].

## Alignment, translate, mixed-language

- Alignment models: torchaudio pipelines for en, fr, de, es, it; 36 HF wav2vec2 models for other languages (ja, zh, nl, uk, pt, ar, cs, ru, pl, hu, fi, fa, el, tr, da, he, vi, ko, ur, te, hi, ca, ml, no, nn, sk, sl, hr, ro, eu, gl, ka, lv, tl, sv, id); anything else raises "No default align-model for language" [S43].
- `task=translate` disables alignment outright: `if task == "translate": # translation cannot be aligned; no_align = True` [S41]. Diarization still runs, but speakers are assigned per segment only; `--highlight_words` errors out (issue #1203) [S44]. Translations therefore carry segment timestamps and Speakers, no word timing.
- Mixed language: WhisperX detects the language once from the first 30 s and applies it to the whole file; its `multilingual` option merely mirrors `model.is_multilingual` [S45]. faster-whisper's per-segment `multilingual=True` detection exists but WhisperX's batched pipeline does not use it [S46]. One alignment model is used for the whole file; characters outside its dictionary map to a wildcard and segments with no dictionary characters are left unaligned [S43]. Numerals and currency cannot be aligned [S47].

## VAD and hallucination

- WhisperX VAD: `--vad_method pyannote` (default; weights bundled at `whisperx/assets/pytorch_model.bin`, no HF gating) or `silero` (downloaded at runtime via torch.hub `snakers4/silero-vad`, unpinned); `vad_onset 0.500`, `vad_offset 0.363`, `chunk_size 30` [S48][S49][S50].
- WhisperX passes only `beam_size, patience, length_penalty, max_length, suppress_blank, suppress_tokens, no_repeat_ngram_size, repetition_penalty` to CT2 `generate`. Temperature fallback, `compression_ratio_threshold`, `log_prob_threshold`, `no_speech_threshold`, `condition_on_previous_text` and `hallucination_silence_threshold` are declared but never applied [S46]. Working levers: VAD gating (README: "reduces hallucination"), `--suppress_numerals`, `--initial_prompt` and `--hotwords` (map Vocabulary here), `no_repeat_ngram_size`, `repetition_penalty`, and lower `vad_onset/offset` [S47][S48].
- faster-whisper's own path: `vad_filter` (Silero, removes silence > 2 s by default), batched pipeline `vad_filter=True`, plus `hallucination_silence_threshold` and `condition_on_previous_text` [S30][S46].
- Open issues: hallucination on silent audio (#820, open) and Silero-vs-pyannote boundary drift between ASR and diarization (#1288, open) [S51][S52].

## VRAM, co-residency, speed and quality

- faster-whisper benchmark (13 min audio, RTX 3070 Ti, CUDA 12.4): large-v2 fp16 beam 5: 1m03s, 4525 MB; batched 8: 17 s, 6090 MB; int8: 59 s, 2926 MB; batched int8: 16 s, 4500 MB. distil-large-v3 batched 16 fp16: 25m50s, WER 13.527 on YT Commons [S30]. large-v3-specific VRAM: not found; its fp16 weights are 3.09 GB [S19].
- Co-residency: weights total under 4 GB (large-v3 3.09 GB, community-1 32.6 MB) against 96 GB per card [S19][S22][S1]; the old image already held both in one process. Pyannote VRAM figure: not found.
- Quality: large-v3 1550M params, 10-20% fewer errors than v2, Open ASR WER 7.44, RTFx 145.51 [S53]. large-v3-turbo 809M, 4 decoder layers, WER 7.83, RTFx 200.19, supports translate [S54]. distil-large-v3.5 756M, English only, no translate, WER 7.08 short and 11.39 long form, 1.46x turbo's RTFx [S20]. WhisperX claims 70x realtime with large-v2 batched [S47]. int8 numbers do not apply on Blackwell (see above).

## Known Blackwell pitfalls

1. No sm_120 (or sm_90/100) SASS in CT2 wheels; PTX JIT on first load [S15][S27].
2. INT8 disabled on sm120 in CT2 >= 4.6.2; float16 only [S29].
3. No CUDA 13 CT2 wheels (#1933 open); stay on the cu12 torch line [S25].
4. Driver 595 known issue: sporadic illegal memory access from `cuTensorMapEncodeTiled` on Blackwell for backing allocations under 128 KB [S3].
5. The 595 notes validate RTX PRO 6000 Blackwell on Ubuntu 24.04 and 22.04, not 26.04; the container toolkit lists 26.04 as tested [S3][S55].
6. PyTorch issue #164342 (sm_120 in stable wheels) is open; 2.8.0 works via the cu128 build path [S56][S33].

## Open risks

- The stack is anchored on torch 2.8 by whisperx's year-old `~=2.8.0` pin, which also holds transformers at 4.57.x and huggingface-hub at 0.36.x; moving needs a new whisperx release.
- CT2 running from PTX: first-run JIT cost per container start unless the CUDA JIT cache is persisted (cache env-var defaults: not found in this pass); no Blackwell-tuned kernels.
- Silero VAD and HF alignment models download at runtime from third-party repos and are unpinned (models such as jonatasgrosman/* can disappear, issue #1219) [S57]. Pre-bake them.
- Translation loses word timing by design; do not promise word-level output for it.
- Gated HF models need a token at build or first run; pyannote telemetry is on by default.
- The 12.8.2 ubuntu24.04 images have no cudnn variant; if a system cuDNN is wanted use `12.9.2-cudnn-runtime-ubuntu24.04` [S4].

## Sources

- S1 https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/
- S2 https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html (13.3 Update 1; driver table)
- S3 https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-595-91-07/index.html
- S4 https://gitlab.com/nvidia/container-images/cuda/-/raw/master/doc/supported-tags.md
- S5 https://pypi.org/pypi/whisperx/json
- S6 https://pypi.org/pypi/torch/2.8.0/json
- S7 https://raw.githubusercontent.com/meta-pytorch/torchcodec/main/README.md
- S8 https://pypi.org/pypi/faster-whisper/json
- S9 https://github.com/SYSTRAN/faster-whisper/releases
- S10 https://pypi.org/pypi/ctranslate2/json
- S11 https://raw.githubusercontent.com/OpenNMT/CTranslate2/master/CHANGELOG.md
- S12 https://download.pytorch.org/whl/cu128/torch/
- S13 https://raw.githubusercontent.com/pytorch/vision/main/README.md
- S14 https://pypi.org/pypi/pyannote.audio/json
- S15 https://raw.githubusercontent.com/OpenNMT/CTranslate2/master/python/tools/prepare_build_environment_linux.sh
- S16 https://pypi.org/pypi/transformers/4.57.6/json
- S17 https://pypi.org/pypi/transformers/5.16.1/json
- S18 https://pypi.org/pypi/huggingface-hub/0.36.2/json
- S19 https://huggingface.co/api/models/Systran/faster-whisper-large-v3?blobs=true and https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/utils.py
- S20 https://huggingface.co/distil-whisper/distil-large-v3.5 and https://huggingface.co/api/models/distil-whisper/distil-large-v3.5-ct2?blobs=true
- S21 https://huggingface.co/api/models/pyannote/speaker-diarization-community-1?blobs=true
- S22 https://huggingface.co/pyannote/speaker-diarization-community-1
- S23 https://raw.githubusercontent.com/m-bain/whisperX/main/uv.lock
- S24 https://pypi.org/pypi/torch/json
- S25 https://github.com/OpenNMT/CTranslate2/issues/1933
- S26 https://raw.githubusercontent.com/OpenNMT/CTranslate2/master/.github/workflows/ci.yml and CMakeLists.txt
- S27 https://raw.githubusercontent.com/Kitware/CMake/v3.22.6/Modules/FindCUDA/select_compute_arch.cmake
- S28 https://github.com/OpenNMT/CTranslate2/issues/1865
- S29 https://github.com/OpenNMT/CTranslate2/pull/1937
- S30 https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
- S31 https://docs.nvidia.com/deeplearning/cudnn/backend/latest/reference/support-matrix.html
- S32 https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html
- S33 https://pytorch.org/blog/pytorch-2-7/
- S34 https://github.com/pytorch/pytorch/releases/tag/v2.8.0
- S35 https://github.com/pyannote/pyannote-audio/releases/tag/4.0.0
- S36 https://huggingface.co/api/models/pyannote/speaker-diarization-3.1
- S37 https://huggingface.co/api/models/pyannote/segmentation-3.0
- S38 https://huggingface.co/api/models/pyannote/wespeaker-voxceleb-resnet34-LM
- S39 https://raw.githubusercontent.com/pyannote/pyannote-audio/develop/src/pyannote/audio/pipelines/speaker_diarization.py
- S40 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/diarize.py
- S41 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/transcribe.py
- S42 https://raw.githubusercontent.com/pyannote/pyannote-audio/develop/README.md
- S43 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py
- S44 https://github.com/m-bain/whisperX/issues/1203
- S45 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/asr.py
- S46 https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/transcribe.py and S45
- S47 https://github.com/m-bain/whisperX/blob/main/README.md
- S48 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/__main__.py
- S49 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/vads/pyannote.py
- S50 https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/vads/silero.py
- S51 https://github.com/m-bain/whisperX/issues/820
- S52 https://github.com/m-bain/whisperX/issues/1288
- S53 https://huggingface.co/openai/whisper-large-v3
- S54 https://huggingface.co/openai/whisper-large-v3-turbo
- S55 https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/supported-platforms.html
- S56 https://github.com/pytorch/pytorch/issues/164342
- S57 https://github.com/m-bain/whisperX/issues/1219
