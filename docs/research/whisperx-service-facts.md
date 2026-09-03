# WhisperX service facts: progress, cancellation, prompts, caches, VRAM

Research date: 2026-09-02. Pins as in `whisperx-pinned-stack.md`: whisperx 3.8.6, faster-whisper 1.2.1, ctranslate2 4.8.2, torch 2.8.0+cu128, pyannote.audio 4.0.7, model `pyannote/speaker-diarization-community-1`. Every code claim below was read from the tagged source (v3.8.6, v1.2.1, v4.8.2, 4.0.7, v2.8.0); line numbers refer to those tags. Primary sources only; "not found" marks the unverifiable.

## 1. Progress reporting

- Signature: `FasterWhisperPipeline.transcribe(audio, batch_size=None, num_workers=0, language=None, task=None, chunk_size=30, print_progress=False, combined_progress=False, verbose=False, progress_callback=None)` [S1 L197-209]. `ProgressCallback = Optional[Callable[[float], None]]` [S4].
- `print_progress=True` does `print(f"Progress: {percent_complete:.2f}%...")` to stdout once per VAD-merged chunk, where `percent_complete = (idx+1)/total_segments*100`, halved (0-50) when `combined_progress=True` so that `align()` can print 50-100 [S1 L266-271][S2 L147-155]. `verbose=True` prints `Transcript: [start --> end] text` per chunk [S1 L279-280].
- Callback hooks exist in all three stages of 3.8.6: `transcribe(progress_callback=)` is called with `(idx+1)/total_segments*100` after each chunk result [S1 L272-273]; `align(..., progress_callback=)` after each transcript segment [S2 L117-127, L408-409]; `DiarizationPipeline.__call__(..., progress_callback=)` wraps pyannote's `hook(step_name, step_artifact, file=None, total=None, completed=None)` and maps `segmentation` to 0-50, `embeddings` to 50-99, then sends 100.0 [S3 L138-165][S22 L553]. `combined_progress` changes only the printed number, never the callback value [S1 L269-273].
- Granularity: the transcribe loop iterates a transformers `PipelineIterator` with `loader_batch_size=batch_size`, which un-batches model outputs per item [S1 L176-195][S14 pt_utils `loader_batch_item`], so `idx` counts VAD-merged chunks (each at most `chunk_size` = 30 s), and `total_segments = len(vad_segments)` is known before generation starts because VAD runs first [S1 L229-235, L266]. Updates arrive in bursts of `batch_size` when each batch finishes. Natural units: chunks (ASR), transcript segments (alignment), pyannote batches (diarization: embeddings total = `ceil(num_chunks*num_speakers/embedding_batch_size)`) [S22 L435-459].
- Language detection and model load emit nothing to the callback; whisperx logs go through `whisperx.log_utils` loggers [S1 L19, L311].

## 2. Cancellation

- CTranslate2 `Whisper.generate(features, prompts, *, asynchronous=False, beam_size=5, patience=1, num_hypotheses=1, length_penalty=1, repetition_penalty=1, no_repeat_ngram_size=0, max_length=448, return_scores=False, return_logits_vocab=False, return_no_speech_prob=False, max_initial_timestamp_index=50, suppress_blank=True, suppress_tokens=[-1], sampling_topk=1, sampling_temperature=1)`: no callback and no stop flag [S15][S16 L242-262]. With `asynchronous=True` the result object has only `done()` and `result()`; no cancel [S17]. The token-level `callback` that can stop decoding by returning `True` exists only on `Generator.generate_batch` / `Translator`, and only when `beam_size` is 1 [S18][S19]; CT2's docs add that breaking out of a streaming loop lets generation "still run to completion in the background" [S19].
- faster-whisper: `WhisperModel.transcribe` returns a generator, "the transcription only starts when you iterate over it" [S13 L150]; the batched path `_batched_segments_generator` yields after each batch of `batch_size` features [S11 L580-617]. Abandoning the generator stops later batches; the in-flight `generate` call still completes.
- whisperx 3.8.6: `transcribe` is eager (it collects every chunk before returning) and exposes no flag; `grep -i "cancel|interrupt|abort|stop_event"` over asr.py, alignment.py, diarize.py, faster_whisper/transcribe.py and CT2's whisper.cc finds nothing [S1][S2][S3][S11][S16]. The only in-process lever is plain Python: the per-chunk `progress_callback` runs inside the loop, so an exception raised there propagates out of `transcribe` (likewise out of `align` per segment and out of pyannote's `apply` via the hook per batch). That is language semantics, not a documented feature, and the current CT2 batch (up to `batch_size` x 30 s) or pyannote batch finishes first.
- Hard stop for an in-flight batch: kill the process. Nothing in whisperx, faster-whisper or CT2 interrupts a running `generate`.

## 3. Vocabulary mapping: initial_prompt, hotwords, prefix

- `WhisperModel.max_length = 448` [S11 L722]. `get_prompt(tokenizer, previous_tokens, without_timestamps=False, prefix=None, hotwords=None)` builds, in order [S11 L1532-1565]:
  1. if `previous_tokens` or (`hotwords` and not `prefix`): `sot_prev`; then, if `hotwords` and not `prefix`, `encode(" " + hotwords.strip())` truncated to `max_length//2 - 1` = 223 tokens; then `previous_tokens[-223:]`;
  2. `sot_sequence` (sot, language, task); `no_timestamps` when `without_timestamps`;
  3. if `prefix`: `encode(" " + prefix.strip())` truncated to 223 tokens (preceded by `timestamp_begin` when timestamps are on).
- So hotwords are dropped only when `prefix` is set ("Has no effect if prefix is not None" [S11 L346, L856]); `initial_prompt` and `hotwords` coexist (hotwords first, then previous text). Each slot is capped at 223 tokens separately, so hotwords + previous text can reach 446 tokens before `sot_sequence`. CT2's `max_length` is "Maximum generation length" (default 448) [S15]; faster-whisper treats it as prompt plus new tokens (`max_length = len(prompt) + max_new_tokens`, error if over 448) [S11 L194-207]. whisperx passes `max_length=448` with no prompt-length check [S1 L68]; CT2 behaviour when the prompt alone exceeds it: not found. Keep hotwords + initial_prompt well under 224 tokens.
- Sequential `WhisperModel.transcribe`: `initial_prompt` tokens seed the previous-text slot; `prefix` only when `seek == 0` (first window) [S11 L1143-1149, L1187, L1204]; `condition_on_previous_text` and `prompt_reset_on_temperature` then govern later windows [S11 L1374-1383].
- `BatchedInferencePipeline.generate_segment_batched`: `previous_tokens = tokenizer.encode(options.initial_prompt)` (no leading space), `hotwords` passed, `prefix` never passed even though its docstring says "at the beginning of each window" [S11 L174-191, L365]; the same prompt goes to every window.
- whisperx's own `WhisperModel.generate_segment_batched` [S1 L37-74]: `initial_prompt = " " + strip` encoded as `previous_tokens`; `get_prompt(..., without_timestamps=options.without_timestamps, prefix=options.prefix, hotwords=options.hotwords)`; `[prompt] * batch_size`, so `initial_prompt`, `hotwords` and `prefix` apply identically to every 30 s chunk, not only the first. Resulting layout: `[sot_prev][hotwords <=223][initial_prompt last 223][sot,lang,task][no_timestamps][prefix <=223]`.
- `asr_options` accepted by `whisperx.load_model` are exactly faster-whisper's `TranscriptionOptions` fields (beam_size, best_of, patience, length_penalty, repetition_penalty, no_repeat_ngram_size, log_prob_threshold, no_speech_threshold, compression_ratio_threshold, condition_on_previous_text, prompt_reset_on_temperature, temperatures, initial_prompt, prefix, suppress_blank, suppress_tokens, without_timestamps, max_initial_timestamp, word_timestamps, prepend_punctuations, append_punctuations, multilingual, max_new_tokens, clip_timestamps, hallucination_silence_threshold, hotwords) plus whisperx's `suppress_numerals`; any other key raises `TypeError` at `TranscriptionOptions(**...)` [S1 L371-407][S11 L70-97]. Only `initial_prompt`, `prefix`, `hotwords`, `without_timestamps` (prompt) and `beam_size, patience, length_penalty, suppress_blank, suppress_tokens, no_repeat_ngram_size, repetition_penalty` (generate) reach CT2 [S1 L52-74].
- `suppress_tokens` default `[-1]` = CT2's "default set of symbols as defined in the model config.json" [S1 L387][S15]. `suppress_numerals=True` adds every token whose decoded text contains any of `0123456789%$£` to `suppress_tokens` for the call, then restores the original list [S1 L22-29, L256-262, L294-296].

## 4. Diarization arguments, embeddings, speaker labels, token

- `DiarizationPipeline(model_name=None, token=None, device="cpu", cache_dir=None)`; default model `pyannote/speaker-diarization-community-1`; loads via `Pipeline.from_pretrained(model_config, token=token, cache_dir=cache_dir).to(device)` [S3 L91-103]. pyannote's signature: `from_pretrained(checkpoint, revision=None, hparams_file=None, subfolder=None, token=None, cache_dir=None)` [S23 L153-161].
- `__call__(audio, num_speakers=None, min_speakers=None, max_speakers=None, return_embeddings=False, progress_callback=None)` returns a DataFrame with columns `segment, label, speaker, start, end`, or `(DataFrame, embeddings)` when `return_embeddings=True` [S3 L105-182]. pyannote: `min_speakers`/`max_speakers` "Has no effect when num_speakers is provided" [S22 L530-550]. whisperx reads `output.speaker_diarization`, not `exclusive_speaker_diarization` [S3 L167].
- Embeddings: pyannote returns `speaker_embeddings` as a "(num_speakers, dimension) array" [S22 L73-75]; whisperx converts it to `{"SPEAKER_00": [floats], ...}` in `diarization.labels()` order [S3 L174-176]. Dimension for community-1: not found (config.yaml and embedding/README.md sit behind the gate; the HF API only lists `embedding/pytorch_model.bin` 26,646,242 bytes, `segmentation/pytorch_model.bin` 5,906,507 bytes, `plda/plda.npz`, `plda/xvec_transform.npz`) [S26]. Measure `len(vector)` once at first run.
- Labels are `f"SPEAKER_{speaker:02d}"` after pyannote renames clusters "to human-readable SPEAKER_00, SPEAKER_01, ..." [S22 L298, L733-740].
- `assign_word_speakers(diarize_df, transcript_result, speaker_embeddings=None, fill_nearest=False)`: sets `seg["speaker"]` to the label with the largest summed overlap; for each word that has a `start` key sets `word["speaker"]` the same way; words without `start` are skipped; no overlap leaves the key absent unless `fill_nearest=True`; when embeddings are given adds `result["speaker_embeddings"]` [S3 L185-263].
- Token: `token=` on `DiarizationPipeline` (CLI `--hf_token`) [S3][S6 L77][S5 L218]; env `HF_TOKEN` overrides the stored token [S28]. pyannote fetches files with `huggingface_hub.hf_hub_download(..., cache_dir=cache_dir, token=token)` [S24 L80-89]; with `HF_HUB_OFFLINE=1` "no HTTP calls will be made ... only the cached files will be accessed. If no cache file is detected, an error is raised", and the etag check on cached files is skipped [S28]. The model card also documents cloning the repo and `Pipeline.from_pretrained('/path/to/dir')` for offline use [S27].

## 5. Model cache locations and offline switches

| Asset | How it is fetched | Where it lands | Override |
|---|---|---|---|
| CT2 Whisper weights | `WhisperModel(download_root=...)` -> `download_model(cache_dir=download_root)` -> `huggingface_hub.snapshot_download(repo_id, cache_dir=..., local_files_only=..., allow_patterns=[config.json, preprocessor_config.json, model.bin, tokenizer.json, vocabulary.*])` [S11 L655-690][S12 L49-116] | HF hub layout (`models--Systran--faster-whisper-large-v3`) under `download_root`, else `HF_HUB_CACHE` (default `$HF_HOME/hub`, `~/.cache/huggingface/hub`) [S28] | `whisperx.load_model(download_root=, local_files_only=)`; CLI `--model_dir`, `--model_cache_only` [S1 L315-364][S6 L17-18] |
| torchaudio align bundles (en, fr, de, es, it) | `bundle.get_model(dl_kwargs={"model_dir": model_dir})` -> `torch.hub.load_state_dict_from_url(url, model_dir=...)` from `download.pytorch.org/torchaudio/models/` [S2 L93-96][S30] | `model_dir`, else `<hub_dir>/checkpoints` = `$TORCH_HOME/hub/checkpoints`; `TORCH_HOME` defaults to `$XDG_CACHE_HOME/torch` = `~/.cache/torch`; a present file is reused without network [S29 L88-90, L139-146, L396-397, L823-865] | `load_align_model(model_dir=)`, `TORCH_HOME` |
| HF wav2vec2 align models (other languages) | `Wav2Vec2ForCTC.from_pretrained(model_name, cache_dir=model_dir, local_files_only=model_cache_only)` [S2 L101-102] | HF hub layout under `model_dir`, else `HF_HUB_CACHE` | `HF_HOME`, `HF_HUB_OFFLINE=1` |
| pyannote community-1 | `hf_hub_download(cache_dir=cache_dir, token=token)` [S24] | HF hub layout under `cache_dir`, else `HF_HUB_CACHE` | `DiarizationPipeline(cache_dir=)`, `HF_HUB_OFFLINE=1` |
| whisperx pyannote VAD | bundled in the wheel: `whisperx/assets/pytorch_model.bin` (17,719,103 bytes); `load_vad_model` resolves `<package>/assets/pytorch_model.bin` (or `model_fp`), raises `FileNotFoundError` if absent, loads with `Model.from_pretrained(model_fp, token=token)`; no download [S8 L21-41][S10] | site-packages | none needed |
| Silero VAD | `torch.hub.load('snakers4/silero-vad', model='silero_vad', force_reload=False, onnx=False, trust_repo=True)` [S9 L26-30]; torch.hub reuses `$TORCH_HOME/hub/snakers4_silero-vad_master` when present and `force_reload` is False (prints "Using cache found in", no GitHub call); otherwise validates against GitHub and downloads the master zip [S29 L250-262]; weights live inside the repo (`src/silero_vad/data/silero_vad.jit`) [S31] | `$TORCH_HOME/hub/` | `TORCH_HOME`; unpinned (master) |

- One mounted folder: `HF_HOME=/models/hf` (gives `HF_HUB_CACHE=/models/hf/hub` and the token path), `TORCH_HOME=/models/torch`, `HF_HUB_OFFLINE=1`, plus `CUDA_CACHE_PATH` (section 6). The whisperx CLI reuses one `--model_dir` as `download_root` (ASR), `model_dir` (align) and `cache_dir` (diarize) [S5 L131, L170, L218].

## 6. CUDA JIT compute cache

- Programming guide: when the driver JIT-compiles PTX "it automatically caches a copy of the generated binary code in order to avoid repeating the compilation in subsequent invocations of the application. The cache - referred to as compute cache - is automatically invalidated when the device driver is upgraded" [S32 sec. Just-in-Time Compilation]. So it persists across process restarts as long as the path persists.
- Environment variables [S32 CUDA Environment Variables table]: `CUDA_CACHE_DISABLE` 0 or 1 (default 0); `CUDA_CACHE_PATH` default Linux `~/.nv/ComputeCache` (Windows `%APPDATA%\NVIDIA\ComputeCache`); `CUDA_CACHE_MAXSIZE` "default is 1073741824 (1 GiB) for desktop/server platforms and 268435456 (256 MiB) for embedded platforms and the maximum is 4294967296 (4 GiB)"; "Binary codes whose size exceeds the cache size are not cached. Older binary codes are evicted from the cache to make room for newer binary codes if needed." `CUDA_FORCE_PTX_JIT=1` forces JIT of embedded PTX; `CUDA_DISABLE_PTX_JIT=1` disables it (validation aids).
- Container implication: `~/.nv` is inside the container user's HOME; set `CUDA_CACHE_PATH` to a mounted volume and raise `CUDA_CACHE_MAXSIZE` toward 4 GiB so the CT2 PTX-to-sm_120 build survives restarts.

## 7. VRAM control

- `torch.cuda.set_per_process_memory_fraction(fraction, device=None)`: "The fraction is used to limit an caching allocator to allocated memory on a CUDA device. The allowed value equals the total visible memory multiplied fraction. If trying to allocate more than the allowed value in a process, will raise an out of memory error in allocator." [S33 L169-183]. PyTorch's caching allocator holds freed blocks, which "will still show as if used in nvidia-smi" [S34].
- CTranslate2 allocates through its own allocators: `CT2_CUDA_ALLOCATOR=cuda_malloc_async` (default for CUDA >= 11.2, CUDA memory pools) or `cub_caching` (defaults `bin_growth=4, min_bin=3, max_bin=12, max_cached_bytes=209715200`, tunable via `CT2_CUDA_CACHING_ALLOCATOR_CONFIG=bin_growth,min_bin,max_bin,max_cached_bytes`) [S20][S21 L37-58, L90, L146]. Neither path touches PyTorch's allocator, so the PyTorch fraction does not bound CT2 memory (inference from [S33] and [S20]; no source states it either way). `max_cached_bytes` bounds only cached free blocks, not live use. No CT2 setting caps total device memory.
- Driver or container level on a plain GPU: no documented per-process cap. MPS provides one: `set_default_device_pinned_mem_limit <dev> <value>` / `set_device_pinned_mem_limit <PID> <dev> <value>` or `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT="0=1G,1=512MB"` "limits the amount of GPU memory that is allocatable by CUDA APIs by the client process"; "By default, there is no memory limit set"; documented for Volta and later, alongside `CUDA_MPS_ACTIVE_THREAD_PERCENTAGE` for SM share [S35]. MIG: the supported-GPU table lists "RTX PRO 6000 Blackwell Workstation Edition, GB202, compute capability 12.0, 96GB, max 4 instances" (also Server and Max-Q editions) [S36]; the product page describes "up to four (4) fully isolated instances" each with its own memory [S37]. So the hard-cap options are MIG partitioning or an MPS pinned-memory limit; otherwise one job at a time is the control.

## 8. Speed and VRAM figures

- whisperx README: "70x realtime transcription using whisper large-v2" and "requires <8GB gpu memory for large-v2 with beam_size=5"; no GPU named [S7 L36-39].
- faster-whisper README (13 min audio, RTX 3070 Ti 8GB, CUDA 12.4, faster-whisper v1.1.0): large-v2 fp16 beam 5: 1m03s, 4525 MB; `batch_size=8` fp16: 17s, 6090 MB; int8: 59s, 2926 MB; `batch_size=8` int8: 16s, 4500 MB; distil-large-v3 `batch_size=16` fp16: 25m50s, WER 13.527 (no VRAM) [S13 L9-40]. large-v3 and large-v3-turbo rows: not found.
- pyannote README (4.0.7): community-1 "31s per hour of audio" on AMI (~1h files) and "37s per hour of audio" on DIHARD 3 (~5min files), "Self-hosted speed on a NVIDIA H100 80GB HBM3", benchmark "last updated in 2025-09" [S25 L105-110]; that is roughly 100x realtime on an H100. The HF model card shows DER tables only [S27]. pyannote VRAM figure: not found.

## 9. batch_size defaults and VRAM scaling

- CLI default `--batch_size 8` [S6 L21]; README Python example `batch_size = 16 # reduce if low on GPU mem` [S7 L170]. Library default when omitted: `transcribe(batch_size=None)` falls back to `self._batch_size` (only set if `batch_size` was passed to the pipeline constructor, which `load_model` does not do), and transformers then resolves `None` to 1 [S1 L132, L265][S14 base.py L1414-1418]. Always pass it explicitly.
- Every batch item is one VAD-merged chunk padded to a full 30 s mel window (`padding=N_SAMPLES - audio.shape[0]`) [S1 L159-167], so activation memory scales with `batch_size` x 30 s regardless of real chunk length. Documented guidance is only "reduce batch size, e.g. `--batch_size 4`" [S7 L220-224]; the one measured pair is large-v2 fp16 4525 MB unbatched vs 6090 MB at batch 8 [S13]. A formula: not found.

## 10. Result fields and language detection

- `transcribe` returns `{"segments": [{"text", "start", "end", "avg_logprob"}], "language": str}`; start/end rounded to 3 decimals [S1 L281-298][S4 `SingleSegment`, `TranscriptionResult`].
- `align` returns `{"segments": [{"start", "end", "text", "words": [...], "chars": None | [...], "avg_logprob"?}], "word_segments": [...]}`; each word dict always has `"word"` and gets `"start"`, `"end"`, `"score"` only when alignable (numerals and out-of-dictionary characters stay without timing); chars carry `char, start, end, score` when `return_char_alignments=True` [S2 L210-225, L340-361, L388-418][S4].
- `assign_word_speakers` adds `"speaker"` (e.g. `SPEAKER_00`) to segments and to timed words, and optionally `result["speaker_embeddings"]` [S3]. The CLI overwrites `result["language"]` with the alignment language before writing [S5 L236].
- `detect_language(audio) -> str`: runs `model.model.detect_language` on the first 30 s, takes `results[0][0] = (language_token, language_probability)`, strips the token to a code, and only logs the probability (`logger.info`, "Detected language: xx (0.97) in first 30s of audio"); it warns when audio is shorter than 30 s. The probability is not returned or stored [S1 L300-312]. CT2 `detect_language` itself returns per batch "a list of pairs (language, probability) ordered from best to worst" [S15], so a service that wants the probability must call `pipeline.model.model.detect_language` directly.

## Sources

- S1 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/asr.py
- S2 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/alignment.py
- S3 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/diarize.py
- S4 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/schema.py
- S5 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/transcribe.py
- S6 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/__main__.py
- S7 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/README.md
- S8 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/vads/pyannote.py
- S9 https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/vads/silero.py
- S10 https://api.github.com/repos/m-bain/whisperX/contents/whisperx/assets?ref=v3.8.6
- S11 https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/faster_whisper/transcribe.py
- S12 https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/faster_whisper/utils.py
- S13 https://raw.githubusercontent.com/SYSTRAN/faster-whisper/v1.2.1/README.md
- S14 https://raw.githubusercontent.com/huggingface/transformers/v4.57.6/src/transformers/pipelines/base.py and pt_utils.py
- S15 https://opennmt.net/CTranslate2/python/ctranslate2.models.Whisper.html
- S16 https://raw.githubusercontent.com/OpenNMT/CTranslate2/v4.8.2/python/cpp/whisper.cc
- S17 https://opennmt.net/CTranslate2/python/ctranslate2.models.WhisperGenerationResultAsync.html
- S18 https://opennmt.net/CTranslate2/python/ctranslate2.Generator.html
- S19 https://raw.githubusercontent.com/OpenNMT/CTranslate2/v4.8.2/docs/generation.md
- S20 https://raw.githubusercontent.com/OpenNMT/CTranslate2/v4.8.2/docs/environment_variables.md
- S21 https://raw.githubusercontent.com/OpenNMT/CTranslate2/v4.8.2/src/cuda/allocator.cc
- S22 https://raw.githubusercontent.com/pyannote/pyannote-audio/4.0.7/src/pyannote/audio/pipelines/speaker_diarization.py
- S23 https://raw.githubusercontent.com/pyannote/pyannote-audio/4.0.7/src/pyannote/audio/core/pipeline.py
- S24 https://raw.githubusercontent.com/pyannote/pyannote-audio/4.0.7/src/pyannote/audio/utils/hf_hub.py
- S25 https://raw.githubusercontent.com/pyannote/pyannote-audio/4.0.7/README.md
- S26 https://huggingface.co/api/models/pyannote/speaker-diarization-community-1?blobs=true
- S27 https://huggingface.co/pyannote/speaker-diarization-community-1
- S28 https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables
- S29 https://raw.githubusercontent.com/pytorch/pytorch/v2.8.0/torch/hub.py
- S30 https://raw.githubusercontent.com/pytorch/audio/v2.8.0/src/torchaudio/pipelines/_wav2vec2/impl.py and utils.py
- S31 https://raw.githubusercontent.com/snakers4/silero-vad/master/hubconf.py
- S32 https://docs.nvidia.com/cuda/archive/12.8.0/cuda-c-programming-guide/index.html (sections "Just-in-Time Compilation" and "CUDA Environment Variables")
- S33 https://raw.githubusercontent.com/pytorch/pytorch/v2.8.0/torch/cuda/memory.py
- S34 https://docs.pytorch.org/docs/2.8/notes/cuda.html
- S35 https://docs.nvidia.com/deploy/mps/appendix-tools-and-interface-reference.html
- S36 https://docs.nvidia.com/datacenter/tesla/mig-user-guide/supported-gpus.html
- S37 https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/rtx-pro-6000/
