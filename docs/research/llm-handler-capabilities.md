# LLM handler capabilities and long-transcript strategy

Research date: 2026-09-01. Resolves `.scratch/build-plan/issues/03-llm-handler-capabilities.md`.

Versions this is written against: vLLM v0.28.0 (latest stable, released 2026-08-26 [S1]); Gemma 4 support landed in vLLM v0.19.0 (2026-04-03, requires Transformers 5.5.0 or newer) [S2], [S3]; `openai` Python client v3.6.0 (2026-08-28) [S34]. Model id: the ticket says `google/gemma-4-31b-it`; the canonical HuggingFace id is `google/gemma-4-31B-it` (capital B). The lowercase URL resolves to the same card; configs should use the canonical spelling [S12].

## Capability table

| Capability | Supported? | Notes | Source |
|---|---|---|---|
| Chat completions `/v1/chat/completions` | Yes | Plus `/v1/completions`, `/v1/responses`, `/v1/chat/completions/batch` | [S4] |
| Streaming | Yes | `stream` field on ChatCompletionRequest, default `False`; reasoning also streams in `delta` | [S5], [S9] |
| JSON / structured output | Yes | `response_format` `json_object`, `json_schema`, `structural_tag`; or `extra_body={"structured_outputs": {"json"/"regex"/"choice"/"grammar": ...}}`; backends xgrammar or guidance, default `auto` | [S5], [S7] |
| Tool calling | Yes | Needs `--enable-auto-tool-choice --tool-call-parser gemma4 --chat-template examples/tool_chat_template_gemma4.jinja`; parser registered as `gemma4` in source | [S10], [S11] |
| Thinking mode | Yes, off by default | `--reasoning-parser gemma4`; per request `chat_template_kwargs={"enable_thinking": true}`; vLLM template defaults `enable_thinking` to false | [S9], [S10], [S11] |
| System role | Yes | Model card: native `system` role | [S12], [S14] |
| Context length | 256K (262,144) | `max_position_embeddings` 262144; the served cap is `--max-model-len` (default derived from config) | [S13], [S17] |
| Max output tokens | No fixed figure | Model card states none; vLLM default is `max_model_len - prompt_tokens` when `max_completion_tokens` is omitted | [S12], [S6] |
| Image input | Yes | 31B is text + image; no audio on 31B | [S12], [S14] |
| Embeddings from the chat process | No | "Each vLLM instance only supports one model runner"; needs a second `--runner pooling` process or another service | [S17], [S23] |
| Concurrency | Yes, continuous batching | Defaults on a 70 GiB+ non-A100 GPU: 8192 batched tokens per step, 1024 sequences for the API server | [S18], [S22] |
| Prefix caching | On by default | `enable_prefix_caching` defaults True; hybrid sliding-window + full-attention models (Gemma 3/4) are supported by the hybrid KV cache manager | [S19], [S18], [S21] |
| Python client | `openai` v3.6.0 | Apache-2.0, Python 3.10+, `base_url` + `api_key`, `extra_body` for vLLM extras, `chat.completions.parse` with pydantic | [S34] |

## vLLM OpenAI-compatible endpoints

vLLM's docs list `/v1/completions`, `/v1/chat/completions`, `/v1/chat/completions/batch`, `/v1/responses`, `/v1/embeddings` (embedding models only), `/v1/audio/transcriptions` and `/v1/audio/translations` [S4]. Non-OpenAI parameters (`top_k`, `repetition_penalty`, `structured_outputs`, `chat_template_kwargs`) go through the client's `extra_body` [S4], [S5]. `max_tokens` is deprecated in favour of `max_completion_tokens`; `parallel_tool_calls` defaults True [S5]. The server applies the repo's `generation_config.json` (Gemma 4: temperature 1.0, top_p 0.95, top_k 64) unless `--generation-config vllm` is passed [S4], [S12]. Over-long prompts fail with "Input length (N) exceeds model's maximum context length (M)" [S6].

Structured outputs: `choice`, `regex`, `json`, `grammar` and `structural_tag`; the old `guided_*` names were deprecated in v0.12.0 [S7]. With the `gemma4` reasoning parser the schema "is only enforced after the reasoning section", and tool calls are parsed from `content`, not `reasoning` [S9]. Named tool choice compiles an FSM on first use (several seconds of latency); strict argument enforcement needs `VLLM_ENFORCE_STRICT_TOOL_CALLING=true` plus `strict: true` on the tool [S8]. Gemma-specific: the docs' tool-calling page lists only `functiongemma` [S8], but the `gemma4` tool and reasoning parsers and `tool_chat_template_gemma4.jinja` exist in the v0.28.0 source and the recipe uses them [S10], [S11]. Google documents the token format (`<|tool_call>call:name{...}<|tool_call|>`) [S15]. Google's prompt-structure page (2025-03-21) still says no system role; the Gemma 4 model card supersedes it [S35], [S14].

## Context length and maximum output

Gemma 4 31B: 30.7B dense parameters, 60 layers, hybrid attention with a 1024-token sliding window and a full-attention layer every sixth layer, 256K context, Apache 2.0, training cutoff January 2025 [S12], [S13], [S14], [S16]. No maximum output length is published; in vLLM the output budget is whatever remains of `--max-model-len` after the prompt [S6]. The vLLM recipe's 31B examples use `--max-model-len 32768` and `16384` on one 80 GB GPU and advise raising it when thinking is on [S10]. Long-context quality: 66.4% on MRCR v2 at 128K [S14].

## Concurrency and batching

vLLM batches all active requests each step (continuous batching over PagedAttention) [S22]. On a GPU with 70 GiB or more that is not an A100, the API server defaults to `max_num_batched_tokens` 8192 and `max_num_seqs` 1024; 160 GiB+ raises tokens to 16384 [S18]. Chunked prefill is on by default and decode requests are scheduled first, so one user's 40k-token prefill is chunked around other users' generation [S20]. When KV cache runs out, requests are preempted and recomputed [S20]. `gpu_memory_utilization` defaults to 0.92 [S19]. Real concurrency is bounded by KV memory left after ~61 GB of bf16 weights (30.7B x 2 bytes, arithmetic); measure it in the server-layout task.

## Embeddings

`/v1/embeddings` is served only by pooling-runner models, and one vLLM instance supports one runner [S23], [S17], so embeddings need a second process. Free options: a second `vllm serve --runner pooling` [S23]; HuggingFace Text Embeddings Inference (Apache-2.0, exposes `/embed` and `/v1/embeddings`, lists `google/embeddinggemma-300m`) [S26]; `sentence-transformers` in-process (Apache-2.0, Python 3.10+) [S27]; Ollama's `/v1/embeddings` [S29]. Candidate models: EmbeddingGemma-300m (768-d, Matryoshka 512/256/128, 2048-token input, Gemma licence) [S25]; BAAI/bge-m3 (MIT, 8192 tokens, 1024-d, 100+ languages) [S28]. Gemma rows in vLLM's pooling table: not found at fetch time [S24].

## Long-transcript strategies

A three-hour transcript at 30k to 40k tokens is well inside 256K, so whole-transcript prompting is viable if the served `--max-model-len` is at least ~64K. Evidence: models use content best at the start or end of context and worst in the middle [S31]; recursive summarize-the-summaries handles inputs beyond any window [S30]; prefix caching reuses a shared prefix's KV cache, so a transcript placed before the chat turns is prefilled once [S19], [S21]. Timestamp citation: no primary source found; it is app design.

## Speaker-name inference

Google's DiarizationLM names "autofilling speaker names" and roles from conversational context as an LLM capability [S32]; a 2025/2026 training-free pipeline uses structured prompting over diarized ASR to assign identities [S33]. vLLM's `choice` and `json` structured outputs constrain the answer to a known-name list plus `unknown` and force a confidence field [S7].

## Python client

`openai` v3.6.0: `OpenAI(base_url="http://host:8000/v1", api_key="...")`, `stream=True`, `extra_body` for vLLM-only fields, `chat.completions.parse(response_format=PydanticModel)` returning `message.parsed`, and `.stream()` helpers [S34]. vLLM accepts the `json_schema` response format that `parse` sends [S5]; the openai docs do not state non-OpenAI server compatibility.

## Recommended long-transcript approach

1. Serve with `--max-model-len` of at least 65536 (transcript plus history plus answer), `--reasoning-parser gemma4`, thinking off by default; enable tool flags only if Chat needs tools.
2. Render the Transcript as numbered lines `[n] [hh:mm:ss] Speaker: text`, put it in the first user turn after a short system message, and append chat turns after it so the prefix stays cacheable and the question sits at the end.
3. Chat and Summary use the whole Transcript in one call while it fits; when it does not (multi-Recording Cases or a context cap), split on Segment boundaries into ~8k-token chunks with a 2-Segment overlap, summarize each, then summarize the summaries (map-reduce).
4. Answers use `response_format` json_schema with `answer` and `citations: [{line, start, end, speaker}]`; the app validates citations against real Segments before display.
5. Speaker suggestion: one call per Speaker over a window of its turns, schema `{name: enum(known names + "unknown"), confidence: enum(high, medium, low), evidence: {line, quote}}`, temperature 0 via explicit request parameters.
6. Sliding-window chat: keep the Transcript prefix fixed, trim the oldest chat turns first, never the Transcript.
7. Embeddings only if retrieval is needed later; run TEI or a second vLLM pooling process, not the chat instance.

## Open risks

- The served `--max-model-len` after the rebuild is unknown; the default derives 262144 from config and may not fit KV memory alongside 61 GB of weights. Verify in the server-layout task.
- Thinking mode consumes the output budget and delays schema enforcement; keep it off for extraction calls.
- The docs' tool-calling page lags the source; `gemma4` parser behaviour is documented only in the recipe.
- `generation_config.json` sets temperature 1.0 by default; extraction calls must pass explicit sampling.
- 128K-context recall is 66.4% on MRCR v2, so citations must be validated, not trusted.
- Embeddings share GPU memory with the 31B model; sizing is unmeasured.
- Transformers 5.5.0 or newer is required for Gemma 4 in vLLM.

## Sources

GitHub source links point at `main` as fetched on 2026-09-01; docs.vllm.ai links are the "latest" build.

- [S1] vLLM releases, https://github.com/vllm-project/vllm/releases (v0.28.0, 2026-08-26)
- [S2] vLLM v0.19.0 notes, https://github.com/vllm-project/vllm/releases/tag/v0.19.0 (2026-04-03)
- [S3] vLLM blog, Gemma 4 day-0, https://github.com/vllm-project/vllm-project.github.io/blob/main/_posts/2026-04-02-gemma4.md
- [S4] vLLM OpenAI-compatible server doc, https://github.com/vllm-project/vllm/blob/main/docs/serving/online_serving/openai_compatible_server.md- [S5] vLLM ChatCompletionRequest, https://github.com/vllm-project/vllm/blob/main/vllm/entrypoints/openai/chat_completion/protocol.py- [S6] vLLM `get_max_tokens`, https://github.com/vllm-project/vllm/blob/main/vllm/entrypoints/serve/utils/api_utils.py- [S7] vLLM structured outputs, https://docs.vllm.ai/en/latest/features/structured_outputs.html
- [S8] vLLM tool calling, https://docs.vllm.ai/en/latest/features/tool_calling.html
- [S9] vLLM reasoning outputs, https://docs.vllm.ai/en/latest/features/reasoning_outputs.html
- [S10] vLLM recipe, Gemma 4, https://docs.vllm.ai/projects/recipes/en/latest/Google/Gemma4.html
- [S11] vLLM source: `vllm/parser/gemma4.py` (name="gemma4"), `vllm/tool_parsers/gemma4_engine_tool_parser.py`, `vllm/reasoning/gemma4_engine_reasoning_parser.py`, `examples/tool_chat_template_gemma4.jinja`, https://github.com/vllm-project/vllm/tree/main
- [S12] HF model card, https://huggingface.co/google/gemma-4-31B-it
- [S13] HF config.json, https://huggingface.co/google/gemma-4-31B-it/blob/main/config.json
- [S14] Google Gemma 4 model card, https://ai.google.dev/gemma/docs/core/model_card_4
- [S15] Google Gemma function calling, https://ai.google.dev/gemma/docs/capabilities/function-calling (updated 2026-06-04)
- [S16] Gemma 4 Technical Report, https://arxiv.org/abs/2607.02770 (2026-07-02, v2 2026-07-24)
- [S17] vLLM engine args, https://docs.vllm.ai/en/latest/configuration/engine_args.html
- [S18] vLLM `EngineArgs.get_batch_defaults`, https://github.com/vllm-project/vllm/blob/main/vllm/engine/arg_utils.py- [S19] vLLM CacheConfig, https://github.com/vllm-project/vllm/blob/main/vllm/config/cache.py- [S20] vLLM optimization and tuning, https://docs.vllm.ai/en/latest/configuration/optimization.html
- [S21] vLLM hybrid KV cache manager, https://docs.vllm.ai/en/latest/design/hybrid_kv_cache_manager.html
- [S22] Kwon et al., PagedAttention, https://arxiv.org/abs/2309.06180 (2023-09-12)
- [S23] vLLM pooling models, https://docs.vllm.ai/en/latest/models/pooling_models.html
- [S24] vLLM supported models, https://docs.vllm.ai/en/latest/models/supported_models.html
- [S25] EmbeddingGemma-300m, https://huggingface.co/google/embeddinggemma-300m
- [S26] Text Embeddings Inference, https://github.com/huggingface/text-embeddings-inference and https://huggingface.github.io/text-embeddings-inference/openapi.json
- [S27] sentence-transformers, https://github.com/UKPLab/sentence-transformers
- [S28] BAAI/bge-m3, https://huggingface.co/BAAI/bge-m3
- [S29] Ollama OpenAI compatibility, https://docs.ollama.com/api/openai-compatibility
- [S30] Wu et al., Recursively Summarizing Books with Human Feedback, https://arxiv.org/abs/2109.10862 (2021)
- [S31] Liu et al., Lost in the Middle, https://arxiv.org/abs/2307.03172 (2023)
- [S32] Wang et al. (Google), DiarizationLM, https://arxiv.org/abs/2401.03506 and https://arxiv.org/html/2401.03506v4
- [S33] Chen et al., Identity-Aware LLM Refinement of Speaker Diarization, https://arxiv.org/abs/2509.15082 (rev. 2026-08-02)
- [S34] openai-python, https://github.com/openai/openai-python (README, helpers.md, releases: v3.6.0 2026-08-28)
- [S35] Google Gemma prompt structure page, https://ai.google.dev/gemma/docs/core/prompt-structure (last updated 2025-03-21)
