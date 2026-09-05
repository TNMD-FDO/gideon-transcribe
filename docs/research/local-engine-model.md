# The Local engine's model: what fits in 20 GB beside WhisperX

Read on 2026-09-05, for the release that gives the Local engine an on/off
switch and a small model. The maintainer's rule: the model, with its cache,
uses no more than 20 GB of the 96 GB card WhisperX runs on.

## The card

Both cards are NVIDIA RTX PRO 6000 Blackwell Server Edition, 97,887 MiB each
(`nvidia-smi`, on the office server). GPU 0 carries the office's shared vLLM
(88 GB used). GPU 1 carries WhisperX, at 559 MiB idle and more while a
transcription runs. A local engine goes on GPU 1 with a memory share that
leaves WhisperX its room: 20 GB of 96 is `--gpu-memory-utilization 0.21`.

## The chapter's requirement

Any engine that stands in for the Shared engine must offer a window of at
least 131,072 tokens (the AI assistant chapter, "The engine"); the whole
Transcript goes into every call and a six-hour Recording is about 100,000
tokens. So a small model must have that context natively, not by stretching.

## The Qwen families, as published

The Shared engine's model, `Qwen/Qwen3.8-27B-FP8`, has no small sibling: the
Qwen3.8 collection holds the 27B (dense, vision-language, 262,144 native,
Apache-2.0) and a 125B-total mixture, Qwen3.8-Flash-Next, whose 6B active
parameters do not make it small on disk or in memory.

The Qwen3.5 series (February 2026) has the small dense models, all with a
262,144-token native context, all Apache-2.0, all served by vLLM with
`--reasoning-parser qwen3` as the shared engine is:

| Model | Parameters | Weights in bf16 | Official FP8 | Notes |
|---|---|---|---|---|
| `Qwen/Qwen3.5-0.8B` | 0.8B | about 1.6 GB | no | too small to summarise well |
| `Qwen/Qwen3.5-2B` | 2B | about 4 GB | no | |
| `Qwen/Qwen3.5-4B` | 4B | about 8 GB | no | fits the 20 GB rule with the full window |
| `Qwen/Qwen3.5-9B` | 9B | about 18 GB | no | over the rule in bf16; FP8 at load would fit but is a third-party or on-the-fly step |
| `Qwen/Qwen3.5-27B-FP8` | 27B | about 27 GB at FP8 | yes | over the rule |
| `Qwen/Qwen3.5-35B-A3B-FP8` | 35B total, 3B active | about 35 GB at FP8 | yes | over the rule: a mixture's weights all load |

The 4B and 9B are hybrid models (Gated DeltaNet layers with a full-attention
layer every fourth), so their attention cache per token is small: the 9B's
card gives 4 KV heads of dimension 256 on the attention layers, about 32 KB a
token in bf16 across its eight attention layers, so 131,072 tokens of context
is about 4 GB of cache; the 4B is smaller again. Both are vision-language
models; the app sends text only.

## The choice

`Qwen/Qwen3.5-4B` in bf16: about 8 GB of weights and a few GB of cache, inside
20 GB with the chapter's 131,072-token window and no quantisation step, in the
same family and with the same reasoning parser as the shared engine. The
launch the card gives, `vllm serve Qwen/Qwen3.5-4B --max-model-len 262144
--reasoning-parser qwen3`, becomes the app's with `--max-model-len 131072`,
`--gpu-memory-utilization 0.21`, the GPU by UUID, and the served name
`local-engine`. Thinking is on by default at the engine and the app turns it
off per request, as it does for the shared engine.

An office with room for more than 20 GB can put `Qwen/Qwen3.5-9B` in the
same slot with vLLM's `--quantization fp8`; that is a value in `.env`, not a
change to the app, and is not the default because no official FP8 weights
exist and on-the-fly quantisation of a hybrid model was not tried here.

## Sources

- https://huggingface.co/Qwen/Qwen3.8-27B-FP8 (27B, 262,144 native, Apache-2.0, vLLM launch)
- https://huggingface.co/collections/Qwen/qwen38 (the four models of the Qwen3.8 collection)
- https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8 (125B total, 6B active, qwen-community-1.0)
- https://huggingface.co/Qwen/Qwen3.5-4B (4B, 262,144 native, vLLM command, Apache-2.0, February 2026)
- https://huggingface.co/Qwen/Qwen3.5-9B (9B, the architecture figures, 262,144 native, thinking on by default)
- https://huggingface.co/api/models?author=Qwen&search=Qwen3.5 (every Qwen3.5 model id, which have FP8)
