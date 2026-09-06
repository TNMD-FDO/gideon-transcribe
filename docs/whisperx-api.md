# WhisperX service API and operating contract

The WhisperX service is the independent transcription engine of Gideon Transcribe. It transcribes, aligns, and diarizes one audio file per request on the GPU, using a fresh, pinned build of WhisperX and nothing reused from any older app. It is not part of the app: it has its own folder in the repository, `whisperx-service/`, with its own Dockerfile, `compose.yaml`, `.env.example`, `models.yaml`, version number, and README, and it runs without the app. Any application that holds a token for it is a Consumer and uses the same contract; Gideon Transcribe is the first Consumer. The service runs exactly one job at a time across every Consumer, in arrival order within a priority (the `priority` request field, 0 for every job unless the Consumer asks), and that serial behaviour is part of its published contract, not an internal detail.

This document is the contract: the HTTP API under `/v1/`, the job states and failure classes, the queue and its durability, the models and their pins, the tokens, the limits, and the operating rules. It carries every decision the planning tickets made about the service; the app-side behaviour (how the app maps a Recording to Runs, what users see, the admin settings) lives in the app's chapters. In the repository this document ships as `docs/whisperx-api.md`, beside the service's own README.

## Principles and vocabulary

1. **Independent.** The service is its own folder in the repository with its own image, Compose file, version, and README, and runs without the app. Other Consumers use the same contract.
2. **One job at a time across every Consumer, enforced here.** The app's Queue orders and presents; the service's line is the only place the GPU rule is enforced, so no Consumer can bypass it. A future move to parallel transcription (a second worker or a second GPU) is a change to the service that every Consumer inherits without code changes of its own.
3. **Recognition only.** The app prepares audio and merges results; the service transcribes, aligns, and diarizes one file per request. It tolerates any audio ffmpeg can decode and documents the prepared WAV (16 kHz, mono, 16-bit PCM, the format WhisperX's own loader produces) as the expected input. The service never trims or drops audio; the only way it can leave speech out is a voice-activity decision, and every such setting is recorded in the result.
4. **Holds nothing it could leak.** No titles, file names, or user names travel to the service; audio is deleted the moment a job ends; results wait at most 24 hours; logs carry metadata only.
5. **Every setting used is echoed in every result**, so a Consumer's Provenance can name them without guessing.

Words. The service's own API says `job`. Inside the app, one Side's pass through the service is a **Run**; a Job has one Run per Side, and the app merges the Runs' Segments into the one Transcript by time. So two lines exist by design and their units differ: the app's Job is one Recording, the service's job is one Side. A multi-Side Recording (a Two-channel call, or distinct audio tracks) is several requests that the app merges. An application holding a token is a **Consumer**. The app keeps its own Queue for what the service cannot know: Batches, per-user limits, the order of a Recording's Sides, the Workspace keep-alive rule, and what users see.

## The serial rule and the durable line

- First in, first out across every Consumer. One job runs at a time. A Consumer sees only its own jobs, but each job's `position` and `audio_minutes_ahead` count everyone's: `position` is the number of jobs ahead of this one (the running job counts as one) and `audio_minutes_ahead` is their audio minutes, across every Consumer.
- The line lives in the service's own SQLite database on its own volume, so a restart keeps every queued job in order. A job that was running when the service stopped goes back to the head of the line once (`attempt` becomes 2); if it is interrupted again it fails with `service_restarted`. A queued job is run when its turn comes even if its Consumer has stopped polling; a Consumer that has given up on a job deletes it to free the GPU.
- Duplicate protection: a submission whose `client_reference` matches a queued or running job from the same Consumer returns that job's status (`200`, not a new `202`).
- No per-Consumer caps inside the service; the app's Queue sets per-user limits (see the transcription queue chapter).
- **Speed and the estimated wait.** The status endpoint publishes `speed`: audio minutes processed per wall-clock minute, a rolling average of the last ten completed jobs, kept per model and separately for Diarization on and off. Translate and transcribe are not separated, since their speeds match. The service never states a wait; the Consumer multiplies `audio_minutes_ahead` by the matching speed. Polling every three to five seconds is the intended use.
- Reference points from the research, until measured: WhisperX quotes about seventy times real time for batched transcription (with large-v2, no GPU named), and pyannote quotes about half a minute per hour of audio for community-1 on a datacentre card (31 seconds per hour on hour-long files, 37 seconds per hour on five-minute files, on an H100). The Phase 1 benchmark gate replaces these with measured numbers on the service's GPU.

## The API under `/v1/`

JSON over HTTP under `/v1/`, with a bearer token on every request except the liveness check: the token is presented as `Authorization: Bearer <token>`. Async throughout, because hour-long jobs exceed any proxy timeout: submit returns at once; the Consumer polls status, fetches the result, then deletes the job. The API is versioned by path, so a breaking change gets `/v2/` rather than a surprise; the service's own version number is reported in every result and on the status endpoint.

| Method and path | What it does |
|---|---|
| `POST /v1/jobs` | Submit. Multipart body: an `audio` file part and a `request` JSON part. Returns `202` with the job id, its position, and the audio minutes ahead. |
| `GET /v1/jobs/{id}` | Status (the status body below). |
| `GET /v1/jobs/{id}/result` | The result once `state` is `done`; `409` with the status body before that; `410` after the result was deleted. |
| `DELETE /v1/jobs/{id}` | Cancel a queued or running job, or delete a finished one (releases the result at once). |
| `GET /v1/jobs` | The caller's own jobs, newest first; every job for an admin token. |
| `GET /v1/models` | The allow-list, with `cached` and `loaded` flags per model. |
| `GET /v1/status` | Token-gated service status (below). |
| `GET /healthz` | Unauthenticated liveness: `200` when the API is up and the model process is alive or loading. |

A job belongs to the token that created it; any other token gets `404` for it, except an admin token.

### Submit: `POST /v1/jobs`

Request: a multipart body with two parts.

- `audio`: the audio file. Any audio ffmpeg can decode is accepted; the expected input is a prepared WAV, 16 kHz, mono, 16-bit PCM. One file is one job; a Consumer with several Sides sends several requests.
- `request`: a JSON object with the fields below. Unknown fields are refused.

| Field | Type | Allowed values | Default | Meaning |
|---|---|---|---|---|
| `task` | string | `transcribe`, `translate`, `translate_if_needed` | `transcribe` | What to produce. `transcribe` writes the speech in its own language. `translate` writes English, whatever the language spoken (Translation is to English only). `translate_if_needed` transcribes when the speech is English and translates otherwise (see Language detection and tasks). |
| `translate_if_mixed` | boolean | `true`, `false` | `false` | Applies only to `task=transcribe` with `language` empty: when detection finds a mixed file, the service runs translate instead. Consumers that leave it false see no change. |
| `language` | string | a two-letter Whisper language code, or empty | empty | Empty means detect the language once from the opening audio (three windows, below). A code switches detection off. The service never switches language mid-file. |
| `model` | string | `large-v3`, `large-v3-turbo` | `large-v3-turbo` | The allow-list. Anything else is `400`. |
| `diarize` | boolean | `true`, `false` | `false` | Separate the audio into Speakers. |
| `speakers` | object or empty | empty, `{"exactly": N}`, or `{"between": [N, M]}` | empty | The Speaker-count hint, in its three shapes: let the service decide, exactly N, or between N and M. Mapped to pyannote's `num_speakers`, or `min_speakers` and `max_speakers` (pyannote ignores the min and max when `num_speakers` is given). N must not exceed M. |
| `vocabulary` | list of strings | up to 200 terms | empty | Names and terms to improve recognition. Built into the prompt (below). |
| `context` | string | one line, up to 500 characters | empty | One line in the style of the speech, for example `Interview of a witness by an investigator about a robbery`. Built into the prompt first. |
| `return_speaker_embeddings` | boolean | `true`, `false` | `false` | One vector per Speaker in the result. Needs `diarize`. Not requested or stored by the app in Phase 1; the flag exists for the day voice matching arrives. |
| `priority` | whole number | 0 to 100 | 0 | Where the job goes in the line: a higher number runs before a lower one, and equal numbers run in arrival order. Added in service 0.2.0 for the app's Live recordings, which ask 100 so a meeting that has just ended is transcribed before the batches waiting. `position` and `audio_minutes_ahead` count what will run before this job under the rule. |
| `client_reference` | string | any | none (optional) | The Consumer's own id for this request, used for duplicate protection. The app sends the Run id. |

**A `speakers` hint without `diarize` is refused**, `400` with a `reason_class`, not ignored (settled 2026-09-03; the two sources disagreed and the refusal was chosen). A Consumer that sends a Speaker-count hint without asking for Diarization has a bug, and silently dropping the hint hides it until someone wonders why the result has no Speakers.

**The prompt rule.** The service builds Whisper's prompt itself: the `context` line first, then the Vocabulary as one sentence:

```
Names and terms: a, b, c.
```

The model's previous-text slot holds 223 tokens, and WhisperX applies the same prompt to every 30-second chunk, so the prompt is kept short by design: the service encodes the prompt, and when it exceeds 200 tokens it drops Vocabulary terms from the end of the list until it fits, then reports `vocabulary_terms_used` and `prompt_tokens` in the result. The Vocabulary sentence follows the `context` line after a single space, and a context line that does not already end a sentence gains a full stop so the two do not run together; the count is the model's own tokenizer's. The prompt goes in as `initial_prompt`; `hotwords` and `prefix` are not used, because they share the same slot and `prefix` would silence the hotwords. `suppress_numerals` is off, so amounts and dates come out as digits.

Facts behind the rule, from the WhisperX service research file: WhisperX's batched pipeline encodes `initial_prompt` as the previous-text tokens and repeats the same prompt for every chunk in the batch, not only the first; each of the `hotwords`, previous-text, and `prefix` slots is capped at 223 tokens separately; the generation length limit is 448 tokens, prompt included, and WhisperX passes it with no prompt-length check, so the 200-token cap keeps the prompt well inside it.

**Validation at submit** (fast failure, `400` with a `reason_class` unless another code is named):

- unknown fields;
- a `model` outside the allow-list;
- `speakers` without `diarize` (see the rule above the Validation list);
- `between` with N greater than M;
- a `context` over 500 characters;
- more than 200 Vocabulary terms;
- a diarize request when the diarization model is not in the cache: `model_unavailable`. A diarize request never waits until after transcription to discover the model is missing;
- an upload with no decodable audio stream: `bad_input`, found by an ffprobe of the uploaded file;
- audio over the length limit: `too_long`, measured by ffprobe at submit;
- a body over the size limit: `413`, `too_large`.

Response: `202` with the job's `id`, `position`, and `audio_minutes_ahead`. A duplicate (a `client_reference` matching a queued or running job of the same Consumer) returns `200` with that job's status body instead.

### Poll: `GET /v1/jobs/{id}`

The status body:

| Field | Content |
|---|---|
| `id`, `client_reference`, `consumer` | The job's identity; `consumer` is the token's name. |
| `state` | `queued`, `running`, `done`, `failed`, `cancelled`. |
| `stage` | While running: `loading model`, `transcribing`, `aligning`, `diarizing`, `finishing`. |
| `percent` | Present only while `transcribing`. WhisperX's progress callback reports per voice-activity chunk (each at most 30 seconds), and results arrive in bursts as each batch finishes, so the number moves in steps of one batch. The total is known before generation starts because voice-activity detection runs first. Language detection and model load report nothing. |
| `position`, `audio_minutes_ahead` | Jobs ahead of this one (the running job counts as one) and their audio minutes, across every Consumer. |
| `created`, `started`, `finished` | Timestamps (UTC). |
| `attempt` | 1, or 2 after the one automatic retry. |
| `failure` | When failed: `reason_class` and a short safe message (never file names or text). |

The app renders `stage` as the plain-word Step a user reads (loading the model, transcribing, aligning words, separating speakers, finishing); the service's values are the ones above.

### Fetch: `GET /v1/jobs/{id}/result`

`200` with the result body once `state` is `done`; `409` with the status body before that; `410` after the result was deleted (by the Consumer, or by the 24-hour rule).

| Part | Content |
|---|---|
| `audio` | `duration_seconds`, `sample_rate`, `channels`, as received. |
| `language` | `requested` (the code given, or empty), `detected` and `probability` (the winner of detection), `windows` (one entry per detection window: `offset_seconds`, `language`, `probability`), `combined` (a figure per language: the mean of the probabilities of the windows that heard it, counting a window that heard something else as zero, so it stays between 0 and 1 whether a Run got one window or three), and `mixed` (`true` or `false`). |
| `word_timestamps` | An object: `present` (`true` or `false`) and `reason`, which is empty when they are present and otherwise one of: `translation` (alignment is disabled whenever the service ran translate, including when it chose to) or `no_alignment_model` (a language WhisperX cannot align, or whose model could not be fetched). |
| `segments` | Ordered: `start`, `end`, `text`, `speaker` (present when diarized), `words`. |
| `words` (inside each segment) | `word`, `start`, `end`, `score`, `speaker`; a word the aligner could not place carries only `word`. |
| `speakers` | An object: `labels`, the labels found in the engine's own form (`SPEAKER_00` and on), and, only when embeddings were asked for, `embeddings` (one list of floats per label) and `embedding_dimension`. Labels are per job; the app renames them before anyone sees them, and prefixes them with the Side for a multi-Side Recording. |
| `settings_used` | `task` (as requested), `task_run` (`transcribe` or `translate`, what the service actually ran), `task_reason` (`requested`, `english_detected`, `mixed_detected`), `language`, `model` and its revision, `compute_type` (`float16`), `batch_size`, `vad` (`method`, `onset`, `offset`, `chunk_seconds`), `diarize` and the hint as applied, `vocabulary_terms_given`, `vocabulary_terms_used`, `context_given`, `prompt_tokens`, `return_speaker_embeddings`. |
| `service` | `version`, `api_version`, and the pins (whisperx, faster-whisper, ctranslate2, torch, pyannote.audio, the diarization model revision). |
| `timings_seconds` | `queued`, `load`, `transcribe`, `align`, `diarize`, `total`. |
| `gpu` | `uuid`, `name`. |

Word timestamps are required in the result whenever the task run is not translation, because the app's viewer underlines the current word during playback. Word scores are available to the app. Timestamps are rounded to three decimals by WhisperX.

### Delete or cancel: `DELETE /v1/jobs/{id}`

- A queued job is simply removed from the line; it ends `cancelled`.
- A running job is stopped by killing the model process (see Cancel and the supervised model process); it ends `cancelled` and the GPU is free within seconds.
- A finished job (`done`, `failed`, or `cancelled`) is deleted, and its result is released at once.

A regular token can cancel or delete only its own jobs; an admin token can cancel any job.

### List: `GET /v1/jobs`

The caller's own jobs, newest first, each as a status body. The app's worker calls this once every three seconds and gets every Run of its own in one call. For an admin token: every job (ids, Consumer names, stages, timings, never content).

### Models: `GET /v1/models`

The allow-list (`large-v3`, `large-v3-turbo`), with `cached` (the files are in the model folder) and `loaded` (held by the model process now) flags per model.

### Status: `GET /v1/status` (token-gated)

| Field | Content |
|---|---|
| `model_loaded` | The model the model process holds, and its revision. |
| `gpu` | `uuid`, `name`, `vram_used_gb`, `vram_free_gb`, reported at all times. |
| `queue` | `length`, `audio_minutes`. |
| `current_job` | `id`, `consumer`, `stage`. For a regular token whose own job is not the one running, `id` and `consumer` are empty and `stage` stands: that something is running, and how far along it is, is what a Consumer needs to judge its own wait; whose job it is, is not. |
| `speed` | Audio minutes per wall-clock minute, per model, Diarization on and off (the rolling average of the last ten completed jobs). |
| `versions` | service, API, pins. |
| `uptime_seconds` | |
| `last_failure` | `reason_class`, `time`. |
| `tokens` | Name and last-used time per token; the token values never. |

Other Consumers' job ids are never shown here, only counts.

### Liveness: `GET /healthz`

Unauthenticated. Answers `200 ok` when the API is up and the model process is alive or loading. The Compose healthcheck and any future proxy use it; the app's Upload page calls it when it opens and when Submit is pressed.

### Job states

| State | Meaning | What happens next |
|---|---|---|
| `queued` | In the line; `position` and `audio_minutes_ahead` say where. | Its turn makes it `running`; a delete makes it `cancelled`. |
| `running` | The model process holds it; `stage` and, while transcribing, `percent` say how far. | Completion makes it `done`; a failure makes it `failed`; a delete or an admin cancel makes it `cancelled`; a service stop puts it back at the head of the line as `queued` once, and a second interruption makes it `failed` with `service_restarted`. |
| `done` | The result is ready to fetch. | The Consumer fetches and deletes it. If nobody deletes it, the result is removed after 24 hours (the state stays `done`, and a fetch answers `410`) and the row after 30 days. |
| `failed` | `failure.reason_class` says why. | A delete removes it; otherwise the row goes after 30 days. |
| `cancelled` | Deleted by its Consumer or an admin token while queued or running. | A delete removes it; otherwise the row goes after 30 days. |

### Error responses

Request-time refusals are plain HTTP:

| Code | When |
|---|---|
| `400` | An invalid field, or a submit-time reason class (`bad_input`, `too_long`, `model_unavailable`), with a `reason_class` in the body. |
| `401` | A missing or unknown token. |
| `404` | A job that is not the caller's (an admin token excepted), or does not exist. |
| `409` | A result that is not ready; the body is the status body. |
| `410` | A result already deleted. |
| `413` | A body over the size limit; `reason_class` is `too_large`. |

## Failure reason classes

The nine classes. A failed job carries one in `failure.reason_class`; a refused submission carries one in its `400` or `413` body. The app records the service's class in its audit log as the Job's Reason class, so the classes are fixed words, never free text.

| Class | When | Retried |
|---|---|---|
| `bad_input` | No decodable audio (at submit, or a decode failure mid-job). | no |
| `too_large` | Body over the size limit (submit). | no |
| `too_long` | Audio over the length limit (submit). | no |
| `model_unavailable` | The model is not cached and cannot be fetched, or the licence gate refused it (submit for the ASR and diarization models). A missing alignment model whose fetch failed mid-job is not a failure but the `no_alignment_model` flag. | no |
| `gpu_error` | CUDA fault or out-of-memory. | once, after a model process reload |
| `timeout` | Past the job time limit. | no |
| `cancelled` | Deleted by its Consumer or an admin token. | no |
| `service_restarted` | Interrupted by a service restart twice. | no |
| `internal` | Anything else, with the details in the journal. | no |

Once the model cache is filled the service runs offline, so a withdrawn licence acceptance shows up only as a failing `pull`, never as a failing job; `model_unavailable` keeps its licence-gate meaning for a model that was never pulled.

## Cancel and the supervised model process

Nothing in WhisperX, faster-whisper, or CTranslate2 can interrupt a running batch. The facts, from the WhisperX service research file: CTranslate2's Whisper `generate` has no callback and no stop flag, and its asynchronous form offers only `done()` and `result()`; faster-whisper's generator stops later batches when abandoned but the in-flight call still completes; WhisperX's `transcribe` is eager and exposes no flag. An exception raised inside the per-chunk progress callback would propagate out, but that is language semantics, not a documented feature, and the current batch (up to `batch_size` chunks of 30 seconds) finishes first. The hard stop is to kill the process.

So the service is two processes:

- the **API**, FastAPI on uvicorn, which holds the line, the SQLite database, the tokens, and the status surface;
- one supervised **model process**, which holds the loaded model and runs one job at a time.

Cancelling a running job kills the model process; the GPU is free within seconds, the job ends `cancelled`, and the next job sees `loading model` while the supervisor starts a fresh process. A queued job is simply removed. The same kill-and-reload path handles a timeout and a GPU fault, and it isolates the API from the Blackwell memory fault the driver's release notes list (a sporadic illegal memory access from `cuTensorMapEncodeTiled` for backing allocations under 128 KB). Retry: a job that fails with a CUDA fault or out-of-memory is run once more after the reload before it is reported as `gpu_error`; nothing else is retried. A cancel therefore costs the next job a model reload (well under a minute).

## Language detection and tasks

**Detection.** When `language` is empty the service detects the language once, before transcription, and never switches language mid-file. It samples **three 30-second windows**: the start, one third in, and two thirds in. A file under 90 seconds gets as many non-overlapping windows as fit, at least one. Each window reports a language and a probability. The service asks the model for the probability directly, because WhisperX's own detect call runs on the first 30 seconds only and returns just the code (it logs the probability and does not return it); CTranslate2's `detect_language` returns pairs of language and probability ordered from best to worst.

- A file is **mixed** when at least two windows report different languages, each with a probability of 0.5 or more.
- Otherwise the language with the highest combined probability is the detected language. `detected` and `probability` in the result describe that winner; `windows`, `combined`, and `mixed` carry the rest.
- Under translate with `language` empty, the service passes Whisper the non-English language with the highest combined probability. English speech passes through untranslated under the translate task anyway.
- Detection is best effort: an interpreted interview where every window holds both languages may still come out as one language.

When `language` holds a code there is no detection, so the mixed rule cannot fire, and the Consumer gets exactly the language it asked for.

**What each task does.**

| `task` | `language` | What the service runs | `task_run` | `task_reason` |
|---|---|---|---|---|
| `transcribe` | a code | Transcribe in that language. No detection. | `transcribe` | `requested` |
| `transcribe` | empty | Detect, then transcribe in the detected language. When the file is mixed and `translate_if_mixed` is `true`, translate the whole file to English instead. When mixed and the flag is `false`, transcribe in the winning language. | `transcribe`, or `translate` under the mixed rule | `requested`, or `mixed_detected` |
| `translate` | a code | Translate to English from that language. No detection. | `translate` | `requested` |
| `translate` | empty | Detect, then translate to English, telling Whisper the non-English language with the highest combined probability. | `translate` | `requested` |
| `translate_if_needed` | `en` | Transcribe. No detection. | `transcribe` | `requested` |
| `translate_if_needed` | any other code | Translate. No detection. | `translate` | `requested` |
| `translate_if_needed` | empty | Detect, then transcribe when the detected language is English and translate otherwise. A mixed Run is translated whatever its winning language, without consulting `translate_if_mixed`, which belongs to the plain transcribe task: the point of this task is English out, and the English part of a mixed Run passes through translate untouched. | `transcribe` or `translate` | `english_detected` when it transcribed, `mixed_detected` for a mixed Run, `requested` otherwise |

`word_timestamps.reason` is `translation` whenever the service ran translate, including when it chose to.

## Alignment

After transcription, WhisperX aligns the text to the audio with a per-language alignment model to produce word timestamps; Diarization runs after that and assigns Speakers to Segments and to timed words.

| Task run and language | Alignment | `word_timestamps` |
|---|---|---|
| translate (requested or chosen) | Disabled: WhisperX hard-codes `no_align = True` for `task=translate` ("translation cannot be aligned"). Diarization still runs, and Speakers are assigned per Segment only. | `false`, reason `translation` |
| transcribe, a language with an alignment model in the cache | Runs. | `true` |
| transcribe, a language WhisperX can align whose model is not cached | One fetch attempt is made for it; if the network refuses, the job completes with Segment timing only and never fails. | `true` if fetched, otherwise `false`, reason `no_alignment_model` |
| transcribe, a language WhisperX cannot align | No alignment. | `false`, reason `no_alignment_model` |

Which languages have alignment models, from the pinned stack research file: torchaudio bundles for English, Spanish, French, German, and Italian (fetched from `download.pytorch.org` into `TORCH_HOME`), and HuggingFace wav2vec2 models for 36 other languages (ja, zh, nl, uk, pt, ar, cs, ru, pl, hu, fi, fa, el, tr, da, he, vi, ko, ur, te, hi, ca, ml, no, nn, sk, sl, hr, ro, eu, gl, ka, lv, tl, sv, id); anything else has no default alignment model. The `pull` command fetches the models for the languages in `WHISPERX_ALIGN_LANGUAGES`, default `en,es`, so English and Spanish are aligned offline from the first run; any other language's model is fetched on first use when the network allows. The HuggingFace alignment models are hosted in third-party repositories that can disappear, which is why the pulled ones are pinned and cached.

Alignment facts a Consumer should know: one alignment model is used for the whole file; characters outside its dictionary map to a wildcard and Segments with no dictionary characters are left unaligned; numerals and currency cannot be aligned, so those words carry only `word`; a word without timing gets no `speaker`.

## Voice activity

The service uses WhisperX's own voice-activity detection, which is pyannote-based; its weights ship inside the WhisperX package (no download, no licence gate). The defaults are WhisperX's: onset 0.50, offset 0.363, 30-second chunks. Silero is not used, because WhisperX fetches it at run time from an unpinned repository. The thresholds are service settings, `WHISPERX_VAD_ONSET` and `WHISPERX_VAD_OFFSET`, echoed in every result under `settings_used.vad` so a Provenance can show them. The only way the service can leave speech out is a voice-activity decision, which is why the Phase 1 benchmark gate's dropped-speech check on the jail-call files exists; it may lower the thresholds, and any change is recorded in the settings.

From the pinned stack research file, the levers that actually reach the engine: voice-activity gating (WhisperX's README says it reduces hallucination), `suppress_numerals`, `initial_prompt` and `hotwords`, `no_repeat_ngram_size`, `repetition_penalty`, and the onset and offset thresholds. faster-whisper's temperature fallback, compression-ratio, log-probability, no-speech and hallucination-silence thresholds, and `condition_on_previous_text` are declared by WhisperX but never passed to CTranslate2. Hallucination on silent audio and boundary drift between the ASR and Diarization voice-activity passes are open WhisperX issues.

## Tokens

A tokens file, mounted read-only into the service, one Consumer per line: a name, the token (64 hexadecimal characters), and an optional `admin` mark.

```
# name          token                                                              role
transcribe      0f3c...64 hex characters...a91e
it              7b2d...64 hex characters...c04f                                    admin
```

- The service reloads the file when it changes; no restart.
- The command `make-token <name>` generates a token and prints the line for the tokens file. It does not write the file itself: the file reaches the container as a read-only secret, and a running service has no business adding Consumers to itself. On a full installation `./transcribe make-token` generates the line and puts it in the file in one step. For the app's own token the install does this in the same step as the app's other secrets and hands the token to the app (the app reads it from the secret file its `.env` names as `WHISPERX_TOKEN_FILE`; see the Architecture and deployment chapter of the Phase 1 specification). The file lives at `whisperx-service/secrets/tokens` under the Install home and is never committed.
- A token is presented as `Authorization: Bearer <token>` on every request except `/healthz`. Tokens are compared in constant time and never logged. The last-used time per token is kept in the service database and shown on the status endpoint.
- A **regular token** sees and cancels only its own jobs. The app holds a regular token.
- An **admin token** lists every job (ids, Consumer names, stages, timings, never content) and can cancel any of them, so IT can clear a wedged line from a terminal without touching containers.
- Job ownership follows the token: any other regular token gets `404` for a job it did not create.

## Limits and retention

All settings are in the service's environment file, `whisperx-service/.env`. The ceilings sit above the app's own limits so other Consumers are not bound by app policy.

| Setting | Default | Effect |
|---|---|---|
| `WHISPERX_MAX_UPLOAD_GB` | 2 | Largest request body (a 16 kHz mono WAV of over 17 hours). Over it: `413`, `too_large`. |
| `WHISPERX_MAX_AUDIO_HOURS` | 8 | Longest audio, measured by ffprobe at submit. Over it: `400`, `too_long`. |
| `WHISPERX_JOB_TIMEOUT_BASE_MINUTES` and `WHISPERX_JOB_TIMEOUT_PER_AUDIO_HOUR_MINUTES` | 30 and 60 | A job may run for 30 minutes plus one minute per minute of audio; past that it fails with `timeout` and the model process is restarted. |
| `WHISPERX_RESULT_HOURS` | 24 | How long an unfetched result is kept. |
| `WHISPERX_JOB_HISTORY_DAYS` | 30 | How long a job's metadata row is kept. |

**What the service keeps, and for how long.**

- The uploaded audio is deleted the moment a job finishes, fails, or is cancelled.
- The result, which holds Transcript text, is deleted when the Consumer deletes the job after fetching it, or after 24 hours, whichever comes first.
- The job's row (id, Consumer, timings, outcome, settings, reason class) stays for 30 days for troubleshooting and holds no text.
- All of it lives under the service's own state folder, `<App data folder>/whisperx/` (the database, in-flight audio, results awaiting collection).

**Backup.** Nothing of the service's state (`whisperx/`: job database, in-flight audio, results) or its model cache is backed up; its two secret files (`hf_token`, `tokens`) ride in the app's Snapshot with the app's other secrets. After a restore the service's job ids in the dump mean nothing, so the app fails in-flight Runs rather than resuming them; the service stops and starts with the stack during a restore, and `pull` rebuilds the model cache afterwards.

## Models, the model folder, and `pull`

### The allow-list and residency

Two models: `large-v3-turbo` (the default since the Phase 1 benchmark gate) and `large-v3`. The turbo model is about twice as fast on paper and was about 40 per cent faster measured, uses about 4 GB less video memory, and still translates. The English-only distil model (`distil-whisper/distil-large-v3.5-ct2`) is excluded because it cannot translate. Each job names its model; the model process keeps the last-used model loaded and swaps when a job asks for the other (one reload, well under a minute); nothing unloads when idle. The default for the app's own requests is an admin-panel setting (see the admin settings catalogue); the service's default serves other Consumers.

Compute type `float16` only: CTranslate2 disables INT8 on this GPU generation. The batch size is a service setting, `WHISPERX_BATCH_SIZE`, default 16, and must always be set explicitly, because WhisperX falls back to a batch of one when it is omitted (the library resolves a missing batch size to 1; the command line's default is 8 and the README's example is 16). Memory scales with the batch size times 30 seconds of audio, because every batch item is one voice-activity chunk padded to a full 30-second window whatever its real length; the one measured pair in the research is large-v2 at float16, 4525 MB unbatched against 6090 MB at a batch of 8.

Model quality figures from the research, for the benchmark gate to test: large-v3 has 1550M parameters, 10 to 20 percent fewer errors than v2, Open ASR WER 7.44 and RTFx 145.51; large-v3-turbo has 809M parameters and 4 decoder layers, WER 7.83 and RTFx 200.19, and supports translate. The weights are small against the card: large-v3 3.09 GB, large-v3-turbo 1.62 GB, the diarization model 32.6 MB.

### The model folder

One mounted folder, `<App data folder>/models/whisperx/`, holds everything, addressed by the environment:

| Variable | What lands there |
|---|---|
| `HF_HOME` | The HuggingFace cache: the two ASR models, the diarization model, and any alignment model fetched from the hub (the hub cache is `$HF_HOME/hub`). |
| `TORCH_HOME` | The torchaudio alignment bundles for English, Spanish, French, German, and Italian, and torch hub. |
| `CUDA_CACHE_PATH`, with `CUDA_CACHE_MAXSIZE` raised to 4 GiB (4294967296, the maximum; the default is 1 GiB) | The driver's compute cache. CTranslate2's kernels for this GPU generation are compiled from PTX by the driver on first load, and the driver caches the result; keeping the cache on the mounted folder means the first-load pause is paid once per image rather than once per container start. The driver invalidates the cache after a driver upgrade, so expect one more pause then. |

The voice-activity weights need no folder: they ship inside the WhisperX package. The WhisperX service research file's example layout mounts the folder at `/models` inside the container, with `HF_HOME=/models/hf` (so the hub cache is `/models/hf/hub`), `TORCH_HOME=/models/torch`, and `CUDA_CACHE_PATH` beside them; WhisperX's own command line reuses one model folder for the ASR download root, the alignment model folder, and the Diarization cache folder alike.

### `models.yaml`

Every model is pinned to a revision in the service's `models.yaml`, and `pull` verifies what it fetched.

| Model | Repository | Licence | Pin |
|---|---|---|---|
| ASR, `large-v3` | `Systran/faster-whisper-large-v3` | MIT | the revision in `models.yaml` |
| ASR, `large-v3-turbo` | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` | MIT | the revision in `models.yaml` |
| Diarization | `pyannote/speaker-diarization-community-1` | CC-BY-4.0, gated | revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee` (last modified 2025-09-29) |
| Alignment, one per language in `WHISPERX_ALIGN_LANGUAGES` | the torchaudio bundle for `en` and `es`; a HuggingFace wav2vec2 model for the other languages WhisperX supports | per model | a pin per model (see Left to the build) |

The diarization repository is self-contained: it carries `segmentation/pytorch_model.bin`, `embedding/pytorch_model.bin`, and `plda/` itself, so one acceptance and one token cover Diarization; there is no second gated repository, as pyannote 3.1 had.

### The `pull` command

```
docker compose run --rm whisperx pull
```

Run at install (before the first start), after an image update when the Release notes say the models changed, and after a restore. It fetches the two ASR models, the diarization model (which needs the HuggingFace token and the licence acceptance), and the alignment models for the languages in `WHISPERX_ALIGN_LANGUAGES` (default `en,es`), checks each against its pin in `models.yaml`, and reports. It needs `huggingface.co` and `*.hf.co` reachable; the ASR models are open and need no token.

### Offline after the pull

After the pull the service runs offline: `HF_HUB_OFFLINE=1` (no HTTP calls; only cached files are read, and the etag check on them is skipped), with pyannote's telemetry off (`PYANNOTE_METRICS_ENABLED=0`; pyannote 4 otherwise reports the pipeline class, file duration, and speaker-count arguments on every call). One exception: a transcribe job in a language whose alignment model is not cached makes a single fetch attempt for it; if the network refuses, the job completes with Segment timing only and `no_alignment_model`, never fails. The offline flag is lifted around that one call and put back whatever happens, the attempt is made once per language for the life of the model process, and its outcome is remembered, so a language that cannot be fetched is not reached for again.

Every pinned model is loaded from the folder its revision was fetched into, and never by repository name. Fetching one exact revision leaves the cache with no note of where a branch points, so a lookup by name cannot be answered from the cache and reaches for the network; naming the folder keeps the service offline and makes the pin bind when a job runs as well as when the model was fetched.

### The HuggingFace token

The token is a secret of the service alone: `HF_TOKEN`, read from the secret file named by `HF_TOKEN_FILE` in the service's `.env`, which is `whisperx-service/secrets/hf_token` under the Install home, mode 0400, owned by the installing admin. `./transcribe install` asks for it typed hidden on the terminal (never a command argument, never echoed) and writes the file; the service alone reads it, and the app never sees it. The file is never committed.

## The HuggingFace gate

The diarization model `pyannote/speaker-diarization-community-1` is free (CC-BY-4.0) but gated, of the automatic kind: access is granted the moment the form is sent, and nobody at pyannote reviews it. Without a token, `huggingface.co` answers HTTP 401 for the model's files with `x-error-code: GatedRepo`.

**The acceptance.** Acceptance belongs to a user account, never to an organisation ("Access requests are always granted to individual users rather than to entire organizations"). An office is best served by a dedicated account of its own, signed up with a mailbox that outlives any one person, whose password and two-factor secret go in the office's password manager, so that the acceptance and the token belong to the office and a colleague can rotate the token. Signed in as that account, open the model's page and fill the form: **Company/university**, the office's public name; **Use case**, **Other** (the list offers Meeting note taker, Conversation AI, CCaaS and customer experience, Voice agents, Media and automated dubbing, Training and development, Other; none of them is transcription of legal recordings). The form's notice says the account's mailbox will get occasional mail from pyannote. The page changes at once to say access is granted.

**The token.** At the account's token settings, create a token named for the app (for example `gideon-transcribe-whisperx`). Either kind works:

- a plain **Read** token, which reads every repository the account can read, accepted gated ones included (fine for a dedicated office account with nothing else in it);
- a **fine-grained** token with exactly one box ticked, "Read access to contents of all public gated repos you can access", and nothing else (HuggingFace recommends fine-grained tokens for production and one token per application).

Leave any expiry blank; neither kind expires unless a date is set. The value is shown once; copy it into the office's password manager together with the account's username, the token's name, and the date. It reaches the server only through the install's hidden prompt.

**Both are needed.** `pull` needs the token and the acceptance together; neither alone is enough. A token from an account that has not accepted the conditions is refused at the gate.

**The check.** A token's permissions cannot be checked by reading them back: the account endpoint (`/api/whoami-v2`) reported a working fine-grained token's permissions as empty in the same run in which a file behind the gate returned HTTP 200. The only sound check is to fetch a file that sits behind the gate. `./transcribe check` does a HEAD request on `pyannote/speaker-diarization-community-1/resolve/main/config.yaml` with the token, handing the token to curl on stdin so it never appears in the process list, and reports plainly:

| HTTP code | Meaning |
|---|---|
| 200 (or a 302 or 307 redirect to a download host) | Good: the account has accepted the conditions and the token opens the gate. |
| 401 | The token is wrong, missing, or revoked. |
| 403, or 401 with `x-error-code: GatedRepo` while the account itself reads back fine | That account has not accepted the model's conditions. |

The same request with no token must give 401, which proves the gate is genuinely closed to the unauthenticated box. The two ASR models answer HTTP 307 with no token: they are open. If a future token fails on the gate, the fix is the "Read access to contents of all public gated repos you can access" box on the token, or a plain Read token.

**Egress.** At install and upgrade only (the pull): `huggingface.co` and its download hosts as `*.hf.co`. HuggingFace routes large-file downloads through regional hosts under `hf.co` that it changes without notice (the gated model's weight was served from `us.aws.cdn.hf.co` on the day the token was tested, which was none of the three hosts documented until then, though all three resolved), so an office that filters egress allows the wildcard, never a list of names. At run time the service makes no network call beyond the Docker network it listens on, except the single alignment fetch attempt described under Offline after the pull, which is designed to fail harmlessly when egress is closed.

**Licence.** Each office accepts the CC-BY-4.0 licence itself; the model is never redistributed with the app. The model authors can withdraw an accepted access at any time without notice; the cached copy under the model folder keeps the service working offline regardless, so this is a risk to a future `pull` only, not to a running service.

## The pinned stack

The service is built on Python 3.12 on the pinned base image with the pins below, chosen for two RTX PRO 6000 Blackwell cards (compute capability 12.0, `sm_120`, 96 GB each) under NVIDIA driver 595 on an Ubuntu 26.04.1 host with Docker. Every pin, reason, and risk is from the pinned stack research file; the WhisperX maintainers' own lock file locks the same torch, torchvision, torchcodec, transformers, and cuDNN, and this set moves pyannote.audio, ctranslate2, and faster-whisper forward for the Blackwell INT8 fix.

| Component | Pin | Why | Risks the research named |
|---|---|---|---|
| Base image | `nvidia/cuda:12.8.2-base-ubuntu24.04` | CUDA 12.x runs on any driver from 525 up, and driver 595 runs it fine. The only ubuntu26.04 CUDA images are 13.3.x, which need driver 610 or later. The torch cu128 wheels bring their own CUDA 12.8 libraries, so the `base` variant is enough. | The 12.8.2 ubuntu24.04 images have no cudnn variant; if a system cuDNN is ever wanted, use `12.9.2-cudnn-runtime-ubuntu24.04`. The driver's release notes validate the card on Ubuntu 24.04 and 22.04, not 26.04; the container toolkit lists 26.04 as tested. |
| Python | 3.12 | whisperx needs 3.10 to 3.13; torch 2.8.0 ships cp39 to cp313; torchcodec 0.7 needs 3.13 or lower. | |
| whisperx | 3.8.6 | The latest stable release; 3.8.7rc1 is a prerelease. | Its `torch~=2.8.0` pin anchors the whole stack (torch, transformers, huggingface-hub); moving needs a new whisperx release. Open issues: hallucination on silent audio (#820) and Silero-against-pyannote boundary drift between ASR and Diarization (#1288). |
| faster-whisper | 1.2.1 | The latest release. | On Linux it needs cuBLAS for CUDA 12 and cuDNN 9, which the torch pins supply; its README documents `LD_LIBRARY_PATH` pointing at the pip `nvidia.cublas.lib` and `nvidia.cudnn.lib` folders. |
| ctranslate2 | 4.8.2 | The latest release; includes the sm120 INT8 fix from 4.6.2 and CUDA 12.8 wheels from 4.6.3. | The wheels carry no `sm_120` SASS (the build's arch list tops out at 8.6 plus PTX), so on this GPU generation the kernels run from driver-JIT-compiled PTX: a first-load pause (paid once thanks to the persisted compute cache) and no Blackwell-tuned kernels. INT8 gives `CUBLAS_STATUS_NOT_SUPPORTED` on this generation and is disabled since 4.6.2, so `float16` only. No CUDA 13 wheels exist (issue #1933 open). |
| torch, torchaudio | 2.8.0+cu128, from `download.pytorch.org/whl/cu128` | whisperx pins `~=2.8.0`. Torch 2.7 introduced Blackwell support in the cu128 wheels; 2.8 added the sm12x FP8 paths. | PyTorch stable is 2.13 with a CUDA 13 default; do not use it, because CTranslate2 ships CUDA 12 wheels only and a cu13 torch would put the wrong cuBLAS on the path. PyTorch issue #164342 (`sm_120` in stable wheels) is open; 2.8.0 works through the cu128 build path. |
| torchvision | 0.23.0 | whisperx pins `~=0.23.0`; pairs with torch 2.8. | |
| torchcodec | 0.7.0 | whisperx wants 0.6 to below 0.8, pyannote wants 0.7 or later; 0.7 pairs with torch 2.8. | Needs FFmpeg 4 to 9 in the image. |
| nvidia-cudnn-cu12, cublas, cuda-runtime | 9.10.2.21, 12.8.4.1, 12.8.90 | The exact pins carried by torch 2.8.0; the CTranslate2 wheels are built against the same CUDA 12.8.93 and cuDNN 9.10.2.21. | Compute capability 12.0 needs CUDA 12.8 or later and driver 570.26 or later; CUDA 12.8 added compiler support for SM_100, SM_101, and SM_120. |
| pyannote.audio | 4.0.7 | The latest release; needs torch 2.8 or later and torchcodec 0.7 or later; whisperx needs 4.0.0 or later. | Telemetry is on by default: set `PYANNOTE_METRICS_ENABLED=0`. |
| transformers | 4.57.6 | The last 4.x. whisperx caps `huggingface-hub<1.0.0`, and transformers 5.x needs `huggingface-hub>=1.5`, so 5.x is unresolvable. | Frozen by whisperx's pins. |
| huggingface-hub | 0.36.2 | The last 0.x; satisfies whisperx, transformers, and pyannote together. | Frozen by whisperx's pins. |
| ASR models | `Systran/faster-whisper-large-v3` (3.09 GB, MIT); `mobiuslabsgmbh/faster-whisper-large-v3-turbo` (1.62 GB, MIT) | faster-whisper's own name map. | `distil-whisper/distil-large-v3.5-ct2` (1.51 GB, MIT) is English-only with no translate, so it is excluded. |
| Diarization model | `pyannote/speaker-diarization-community-1` | WhisperX's default; better error rates than 3.1 on 10 of 12 benchmarks; returns per-Speaker centroid embeddings. | CC-BY-4.0 behind an automatic gate that needs a token and an acceptance. Not 3.1, which is MIT but also gated and needs a second gated repository (`pyannote/segmentation-3.0`) accepted. |
| Compute type | `float16` | INT8 is disabled on this GPU generation. | The research's INT8 speed and memory figures do not apply. |
| Voice activity | WhisperX's bundled pyannote weights | No download, no gate. | Silero downloads unpinned from GitHub at run time; not used. |

Other Blackwell facts the research named: driver 595 has a known sporadic illegal memory access from `cuTensorMapEncodeTiled` on Blackwell for backing allocations under 128 KB (the supervised model process contains it); the HuggingFace alignment models download from third-party repositories that can disappear, so the ones the service uses are pulled and pinned; translation loses word timing by design.

## The runtime

**Processes and stack.** FastAPI on uvicorn for the API, SQLite for the line and the job rows, and the supervised model process that holds the loaded model (see Cancel and the supervised model process). Everything the service stores is under the two mounted folders below.

**Where it ships.** The folder `whisperx-service/` in the app's repository (`TNMD-FDO/gideon-transcribe`):

```
whisperx-service/
  Dockerfile          on nvidia/cuda:12.8.2-base-ubuntu24.04 with the pinned stack
  compose.yaml        the service, its network, its volumes, its healthcheck
  models.yaml         every model pinned to a revision
  .env.example        every setting with a comment; the only environment file tracked
  README.md           for a non-programmer: accept the licence, create the token, run pull,
                      make a Consumer token; the GPU budget line the benchmark gate fills in
  .env                the office's settings (ignored, never committed)
  secrets/            hf_token; tokens (ignored, never committed)
```

The service's `.env` holds `WHISPERX_GPU_UUID`, the limits and timeouts, the voice-activity thresholds, `WHISPERX_BATCH_SIZE`, `WHISPERX_ALIGN_LANGUAGES`, and `HF_TOKEN_FILE`. `./transcribe install` writes the GPU UUID into it from `nvidia-smi -L` and asks for the HuggingFace token.

**The Compose service.** The app's `compose.yaml` `include`s `whisperx-service/compose.yaml`, so one `docker compose up -d` brings everything up, and the service folder still runs on its own for a second Consumer or a test bench. The service name is fixed at `whisperx`, because documented commands use it (`docker compose run --rm whisperx pull`).

| Fact | Value |
|---|---|
| Image | `ghcr.io/tnmd-fdo/gideon-transcribe-whisperx`, tagged with the Release tag and pinned by digest once published; `build:` from `whisperx-service/` beside it with no pull policy, so Compose pulls first and builds only when the pull finds nothing. |
| Runs as | The app user. |
| Network | `whisperx`, declared by the service's Compose file under that fixed name; the app's `app` and `worker` services join it; open to a second Consumer's project as an external network. |
| Port | 8000, inside the `whisperx` network only (the app's `WHISPERX_URL` is `http://whisperx:8000`). No published host port. No hostname of its own while the app is its only Consumer; a public route, hostname, and certificate name for a second Consumer are future work. |
| GPU | One card, reserved by UUID through CDI (`driver: cdi`, `nvidia.com/gpu=<UUID>`, the value from `WHISPERX_GPU_UUID`), never by index. No app container sees a GPU. |
| Volumes | `<App data folder>/models/whisperx/` (the model folder, the CUDA compute cache) and `<App data folder>/whisperx/` (the state folder). The tokens file and `hf_token` reach the container as read-only secrets. |
| Healthcheck | `GET /healthz`. |
| Restart | `unless-stopped`. |
| Memory | A starting limit of 32 GB of RAM, tuned at the build gate. |
| Logging | The Docker daemon's journald driver. |

**GPU memory.** The service uses as much of its card as it needs. The facts: PyTorch's per-process memory fraction does not cover CTranslate2's allocator (CTranslate2 allocates through its own `cuda_malloc_async` or `cub_caching` allocators, and no CTranslate2 setting caps total device memory), and the only hard caps on a card are MIG partitioning or an MPS pinned-memory limit, neither of which is used. So the number is set by configuration (model, batch size) and known by measurement: the status endpoint reports `vram_used_gb` and `vram_free_gb` at all times, and the Phase 1 benchmark gate records the peak at the batch size it chooses in the service README under "GPU budget", the figure IT checks before any other model is placed on that card. When the app's optional Local engine shares the card, its memory fraction (`LLM_LOCAL_GPU_FRACTION`, starting value 0.55) is the ceiling that keeps the two apart. The weights themselves are small (under 4 GB for large-v3 with the diarization model); activation memory follows the batch size.

**Logs.** Job id, Consumer name, stage, timings, reason classes, model loads, token reloads; never file names, transcript text, Vocabulary, the context line, or token values. The service never prints transcript text or Vocabulary at its normal log level. A debug level exists for IT, off by default, and the README states what it reveals (still never text). Logs go to the system journal, are kept as long as the host's journal, and are never the record.

**Versions.** The service has its own version number, reported in every result and on the status endpoint; the API is versioned by path (`/v1/`).

## Operating notes for a second Consumer

The service was built so that another application can use it beside the app without any change to either.

1. **Get a token.** An admin runs `make-token <name>` on the server; the line lands in the tokens file and the service picks it up without a restart. Keep the token as a secret; present it as `Authorization: Bearer <token>`.
2. **Reach the service.** Join the `whisperx` Docker network as an external network and call `http://whisperx:8000/v1/`. There is no published port and no hostname; a route from outside Docker is future work, and `/healthz` is the endpoint any future proxy would check.
3. **Send prepared audio.** Any ffmpeg-decodable audio is accepted, but the expected input is a WAV at 16 kHz, mono, 16-bit PCM, one file per job. Send nothing identifying: no titles, file names, or user names travel to the service. Set `client_reference` to your own id so a repeated submission returns the existing job instead of a second one.
4. **Poll, fetch, delete.** Poll every three to five seconds, or list your jobs in one call. Work out your own wait from `audio_minutes_ahead` times the matching `speed` figure from `/v1/status`; the service never states a wait. Fetch the result within 24 hours, then delete the job; audio is already gone when the job ends, and the result goes at 24 hours whether or not you fetched it.
5. **Expect the line.** You see only your own jobs, but `position` and `audio_minutes_ahead` count everyone's, and one job runs at a time across every Consumer. The service applies no per-Consumer caps; apply your own. A queued job is run when its turn comes even if you stopped polling, so delete jobs you no longer want. Cancelling a running job frees the GPU within seconds and costs the next job a model reload.
6. **Choose settings per job.** Name the model per job or take the service's default (`large-v3`); leave `translate_if_mixed` false and `task` at `transcribe` or `translate` unless you want the three-window detection rules; `translate_if_needed` is there when you want English whatever is spoken. Word timestamps are absent under translate. Speaker labels come as `SPEAKER_00` and on; rename them yourself. Ask for `return_speaker_embeddings` only with `diarize`.
7. **Stay under the ceilings.** 2 GB per request body, 8 hours of audio, and a running time of 30 minutes plus one minute per minute of audio, by default; a service admin can change them in the service's `.env`, and the app's own limits sit below them.
8. **Read every result's `settings_used`, `service`, and `timings_seconds`** for your own provenance; every setting used is echoed, with the pins and the model revision.
9. **When something wedges**, the holder of an admin token can list every job and cancel any of them from a terminal; the status endpoint's `last_failure` and the journal (metadata only) say why.

## Left to the build

- **The benchmark gate.** The Phase 1 benchmark gate on real hardware decides, and records in the service README: the model choice between `large-v3` and `large-v3-turbo` for the app's default; the batch size for `WHISPERX_BATCH_SIZE`; the measured speed figures that replace the research's reference points (about seventy times real time for batched transcription, about half a minute per hour of audio for Diarization on a datacentre card); the measured VRAM peak at the chosen batch size, written under "GPU budget" as the figure IT checks before another model is placed on the card; and the dropped-speech check on the jail-call files, which "may lower the thresholds, and any change is recorded in the settings". The gate also includes the translation leg (four checks defined in the Transcription, translation, and diarization choices chapter) and decides the Phone preprocessing profile, "band filter and gentle noise reduction for narrowband calls", which is "added as a third profile only if the Phase 1 benchmark gate shows it measurably lowers errors on the jail-call and phone files" (the Media handling chapter; it touches the service only through the ASR audio it receives).
- **The first smoke check after install** is a real `pull` of the diarization model with the stored token: "`pull` fetches the diarization model with the stored token" is routed to the build as the first smoke check after `./transcribe install`, where it already sits as step 5 of the first-run list. The licence ticket is reopened only if that pull fails for a reason to do with the gate or the token.
- **The embedding dimension.** The research could not find community-1's embedding dimension (its config sits behind the gate); the build measures the vector length once at first run and reports it as `embedding_dimension`.
- **Progress for aligning and diarizing.** WhisperX offers progress callbacks in all three stages; the contract publishes `percent` only while transcribing. The build may keep the other callbacks for the journal but must not add fields to the status body without a new API version.

## Sources

WhisperX service API and operating contract; Pinned WhisperX stack for the target GPU generation; Accept the diarization model licence and create the HuggingFace token; Translation-to-English behaviour (the contract amendments only); Deployment topology on the rebuilt server (the Compose service name, network, internal port, memory limit, secret file paths, and the journal retention amendment); GitHub distribution and install story (the image name, the repository tree, the egress hosts, and the `./transcribe check` shape); ADR 0002 (a fresh, pinned, ASR-only WhisperX service); ADR 0005 (the serial rule lives in the service); the WhisperX service research file; the pinned stack research file.

## Settled by the build

The points the tickets left open were settled during the Phase 1 build and are
written into the contract above, so that a second Consumer reads one document
and not a history. What was decided, on 2026-09-03:

- The ASR revisions and the alignment checksums are in `models.yaml`, taken
  from what the first `pull` fetched. Every pinned model is loaded from its own
  revision's folder rather than by name.
- `combined` is a mean per language rather than a sum, so it stays between 0
  and 1 whatever number of windows a Run got, and a Consumer can hold it
  against a threshold.
- `translate_if_needed` translates a mixed Run whatever its winning language,
  with `task_reason` `mixed_detected`.
- `word_timestamps` is an object of `present` and `reason`; `speakers` is an
  object of `labels`, with `embeddings` and `embedding_dimension` only when
  they were asked for.
- `current_job` shows another Consumer's stage but neither its id nor its name.
- `make-token` prints a line rather than writing the read-only tokens file.
- The prompt joins with a single space after the context line, which gains a
  full stop when it has none, and `prompt_tokens` is the model's own
  tokenizer's count.
- The single alignment fetch lifts the offline flag around that one call only,
  is tried once per language for the life of the model process, and remembers
  its outcome.
- Language detection is counted inside the `load` timing, because the six
  timings a result carries are fixed and detection is work done before any
  transcription starts. What it cost per job goes to the journal instead.
- The debug log level is described in the service README.

## Amendments applied

- From "Translation-to-English behaviour" to the request fields: `task` gains `translate_if_needed`; new field `translate_if_mixed`, default `false`.
- From "Translation-to-English behaviour" to language detection: three 30-second windows replace detection from the first 30 seconds; the mixed rule (two windows, different languages, each 0.5 or more); the winner by highest combined probability; under translate the non-English language with the highest combined probability is passed to Whisper.
- From "Translation-to-English behaviour" to the result body: `language` gains `windows`, `combined`, `mixed`; `settings_used` gains `task_run` and `task_reason`; `word_timestamps.reason` is `translation` whenever translate ran, including when the service chose it; speed figures stay per model and Diarization setting, translate not separated.
- From "Backup and restore" (recorded on the contract ticket) to retention and state: nothing of the service's state or model cache is backed up; `hf_token` and `tokens` ride in the app's Snapshot; after a restore the job ids mean nothing and the app fails in-flight Runs; the service stops and starts with the stack; `pull` rebuilds the cache.
- From "Accept the diarization model licence and create the HuggingFace token" (recorded on the contract ticket) to `models.yaml` and the reason classes: the diarization model pinned at revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`; one acceptance and one token, no second gated repository; a withdrawn acceptance shows only as a failing `pull`; `model_unavailable` keeps its licence-gate meaning.
- From "Accept the diarization model licence and create the HuggingFace token" to egress: the download hosts are `*.hf.co`, never a list of names; and to the check: a token is tested by fetching a file behind the gate, never by reading its permissions back.
- From "Deployment topology on the rebuilt server" (its amendment to the Audit log ticket) to the logging rule: container logs are kept as long as the host's journal, not 30 days.
- From "Deployment topology on the rebuilt server" and "GitHub distribution and install story" to the runtime: the Compose service `whisperx`, the `whisperx` network, port 8000 inside it, the image `ghcr.io/tnmd-fdo/gideon-transcribe-whisperx` with `build:` beside it, the 32 GB RAM starting limit, `HF_TOKEN_FILE` in the service's `.env`, the secret file paths, and the `.gitignore` rules.

