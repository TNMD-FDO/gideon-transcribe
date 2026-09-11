# Moments: what the engine can see, and what it costs

Read and probed on 2026-09-11, for the Phase 4 release that describes what the
camera showed at a chosen time of a video Recording (`docs/spec/SPEC-PHASE-4.md`).
The question was whether the office needs a second model to look at pictures.
It does not.

## The shared engine is a vision model

The shared engine serves `Qwen/Qwen3.8-27B-FP8` under vLLM 0.27. The model card
says the model "natively supports image and video inputs through its vision
encoder"; its licence is Apache 2.0; video is sampled at `fps=2` by default
with `do_sample_frames=True`, and its window is 262,144 tokens
(https://huggingface.co/Qwen/Qwen3.8-27B, read 2026-09-11). vLLM's recipe for
the model verifies text serving and names the architecture
`Qwen3_5ForConditionalGeneration` with vision support
(https://recipes.vllm.ai/Qwen/Qwen3.8-27B, read 2026-09-11).

The app's own Local engine, `Qwen/Qwen3.5-4B`, is a vision model as well
(`docs/research/local-engine-model.md`), so the same code serves an office
that runs it. An engine that takes text only answers a 400; the app reads it
as `llm_no_vision`, "This engine cannot look at video."

## What the OpenAI-compatible API takes

vLLM's multimodal guide (https://docs.vllm.ai/en/stable/features/multimodal_inputs/,
read 2026-09-11): a message's `content` may be a list of parts; an image is
`{"type": "image_url", "image_url": {"url": ...}}` and a video
`{"type": "video_url", "video_url": {"url": ...}}`; a data URL is accepted for
both, so the server fetches nothing; per-request sampling goes through
`extra_body` (`mm_processor_kwargs`, for example `{"fps": 1.0}`); the number of
images and videos a request may carry is the server's `--limit-mm-per-prompt`,
one of each by default. An older report of base64 video failing for Qwen3-VL
(https://github.com/QwenLM/Qwen3-VL/issues/1762, vLLM 0.11) does not apply to
the engine's version; see the probes.

## The probes, from llm-worker against the office's engine

Run on 2026-09-11 with the app's own client and token, thinking off, and
nothing stored:

| Sent | Answer | Prompt tokens |
|---|---|---|
| one 1 by 1 PNG as an `image_url` data URL, "What colour is this image?" | "white" | 87 |
| two such images in one message, "same or different?" | "Same" | not read |
| a 3 s 320 by 180 test-pattern mp4 (35,709 bytes) as a `video_url` data URL, "Describe this short video in one sentence." | a correct sentence about coloured vertical stripes | 226 |
| the same with `mm_processor_kwargs: {"fps": 1.0}` | the same | 226 |

So the engine as GIDEON runs it takes a video data URL and more than one image
without any change to its flags, and no server-side fetch or timeout is
involved.

## What a clip costs

The Qwen3-VL report (https://arxiv.org/pdf/2511.21631, read 2026-09-11) has
each frame cut into 14 by 14 pixel patches merged 2 by 2 into one visual token
(so one token per 28 by 28 pixels), every two consecutive frames grouped by a
3D convolution, and frames sampled at 2 fps for most benchmarks, with each
frame's timestamp written in front of its tokens. The app's estimate,
`prompts.video_tokens(frames, height)`, is therefore `ceil(frames / 2)` times
the frame's patches, `ceil(h / 28) * ceil(w / 28)` with a 16:9 width:

| Clip | Frames | Estimate |
|---|---|---|
| 3 s at 2 fps, 320 by 180 | 6 | 3 x 12 x 7 = 252 (the engine charged 226) |
| 10 s at 2 fps, 640 by 360 | 20 | 10 x 23 x 13 = 2,990 |
| 30 s at 4 fps, 1280 by 720 (the settings' maxima) | 120 | 60 x 46 x 26 = 71,760 |

The estimate is deliberately a little high and goes into `prompts.fits()` as
`extra`, so a Moment is refused before the call when it would not fit the
Engine window setting.

## Why the prompt says "not visible" and "a small bag"

BodyCam-VQA (https://arxiv.org/abs/2609.10815, read 2026-09-11) finds that
vision-language models on body-worn camera footage "frequently overlook
critical forensic details" and struggle with "chaotic scenes, low visual
quality, rapid interactions", and a prosecutor's guide to the same footage
puts the guard plainly: ground every claim in the footage and its offset, and
treat a machine's summary as a lead for review, never a finding of fact
(https://vidizmo.ai/blog/body-worn-camera-ai-analysis, read 2026-09-11). The
shipped Moment template therefore forbids naming people, guessing at a
substance or an object, and filling in what was not visible, asks for seconds
as the clip runs, and gives the spoken words only so the model can tell what
is being pointed at. The app labels every description as a model's, never the
transcript, everywhere it appears.

## What the app does with all this

- The clip is cut by ffmpeg on `llm-worker` (the app image carries ffmpeg)
  from the Playback copy: `-ss` before `-i`, `-t`, no sound, `fps=2`,
  scaled to 360 pixels high and never up, libx264 ultrafast at CRF 28, into a
  temporary file of the container's own, read into the request as base64 and
  deleted whatever happens. Nothing image-like touches the data directory.
- One video part per request, inside the engine's default limits; thinking
  off; the answer cap 400 tokens; the time limit 120 s.
- The descriptions are content: never in a log or an audit row, shown and
  exported marked Camera, and handed to Summary and Chat only while the
  office's Moments in answers setting is On.
