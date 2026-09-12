# Gideon Transcribe, Phase 4 specification

The Moments release, published as `v1.38.0`, its second chapter in `v1.39.0`, and its third in `v1.40.0`.

## About this document

This is the build specification for Phase 4 of Gideon Transcribe: what the camera showed. A transcript carries what was said; a body-worn camera or interview video has moments the words only point at ("look at that", "there's the bag", a handover, a scuffle). Phase 4 lets a person ask the AI assistant to describe such a moment from the picture, beside the words, on request and never by itself. It builds on Phase 1 (`docs/spec/SPEC-PHASE-1.md`, the AI assistant chapter above all), Phase 2 (`docs/spec/SPEC-PHASE-2.md`), and Phase 3 (`docs/spec/SPEC-PHASE-3.md`), and changes nothing in them beyond what "What changes from earlier phases" lists.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 4 terms Moment, Cue, and Camera line), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the seven Phase 4 settings), and `docs/research/moments-vision-engine.md` (what the engine can see, what a clip costs, and the probes that showed it).

Nothing in this document is office-specific. No new environment key is needed and no new service: the engine the office already talks to is a vision model, and the app's worker already carries ffmpeg. The conventions of the Phase 1 document apply here unchanged.

## What Phase 4 adds

- **Moments**: a model's description of what the camera showed at one chosen time of a video Recording, made from a short clip around that time and the words spoken in it, shown beside the Transcript at its time, in Details, in the exports, and, labelled, handed to Summary and Chat.
- **Cues**: the Transcript lines whose words point at something, marked as suggested Moments, described only when a person asks.
- **The engine's priority**: every request the app sends the engine carries a priority, as the shared server's ledger asks of a client.
- **Questions and clips** (chapter 2, v1.39.0): a Moment answers a question about the picture from a few close frames, in a fixed shape that says what is visible, what it is consistent with, and what cannot be told; descriptions are brief unless the office chooses full; and a Moment becomes a Clip with its words as the note and as a caption.
- **The finders** (chapter 3, v1.40.0): Find moments reads the whole Transcript once and suggests the lines where the picture would add a fact, each with its reason, and, when the office turns it on, scans the picture and sound for sharp changes and raised voices; the word list of chapter 1 is withdrawn.

It adds nineteen admin settings, two prompt templates, two audit row features, one Recordings row, two Viewer-edit rows, one reason class, three tables (migrations 0035 to 0037), and no environment key.

## Contents

1. Moments
2. Questions, clearer words, and clips
3. The finders
4. Deferred and ruled out

Appendices: A. Audit rows added in Phase 4. B. Settings added in Phase 4.

## 1. Moments

Written 2026-09-11 at the maintainer's ask: "when something occurs in a video transcript that is abrupt and not explainable by words, a VLM could explain that time snip; or when 'look at that' or 'there's the drugs' is said, the VLM would look at the snip for a description." The maintainer decided the shape on the same day: on demand plus suggested cues, never an automatic sweep; the description counts in the viewer, the exports, and the assistant's answers, always labelled as a description; the input a clip of about ten seconds. Built in v1.38.0.

### Principles

1. **On request only.** A Moment exists because a person pressed a button. Nothing looks at a picture by itself, at upload, at transcription, or on a timer; a Cue is an invitation, not an act.
2. **A description, never the Transcript.** A Moment's words are what a model saw, marked as such everywhere they appear: under the line, in the tab, in the exports, and in what Summary and Chat are told. A Camera line is never a Segment, is never counted among them, and never carries a Speaker.
3. **Nothing image-like is kept.** The clip shown to the engine is cut to a temporary file of the worker's own, read once into the request, and deleted whatever happens. The data directory never holds a frame, a thumbnail, or a clip made for a Moment; the viewer shows the player at that time instead.
4. **Honest about what it cannot see.** The shipped instructions forbid naming people, guessing at a substance or an object ("a small bag", not "drugs"), and filling in what was dark, blurred, or out of frame ("not visible"). An engine that takes text only fails the Moment with "This engine cannot look at video", and a Moment asked before the Playback copy exists says the video is still being prepared.
5. **Content is content.** A Moment's description, the phrase that cued it, and the clip are on the never-logged list. The audit row for a Moment is the AI assistant's usual metadata row and no more.
6. **The engine is the one the app already has.** No second model, no GPU memory of the app's own, no new service: the shared engine's model and the Local engine's default both read video through the same chat-completions call, one video part inside the engine's default limits. Every request carries `priority` 1.

### Words

**Moment**, **Cue**, and **Camera line**, as `CONTEXT.md` defines them. A Moment is **asked for** (a person pressed the camera button on a line, or Describe this moment at the playhead) or **accepted from a Cue**; the difference is recorded as its source and shown in the tab, and nothing else differs.

### The viewer

On a video Recording with a Transcript, while Moments is On:

- **The Moments tab** joins the Bench beside Summary and Chat (on a laptop, a tab of the sheet). Its head has **Describe this moment**, which asks for the playhead's time. Under it the Moments are listed newest last, each with its time as a citation, whether it was asked for or came from a Cue, when it was described, the AI notice, its text, and Edit, Again, and Delete. While a Moment is being described the card says "Looking at the clip..."; a failed one says why in the assistant's words. Under the list, **Suggested moments** lists the Cues: each line's time, the phrase in quotes, and Describe.
- **The rows.** Every transcript row gains a small camera button among its actions, "Describe what the camera shows here", which asks for that line's start. A Cue's row carries a dashed **Camera?** pill after the Speaker's name, which does the same. A described Moment appears as a Camera line under the row nearest its time: the tag Camera, the time as a citation, and the description in italic; while it is being described the line says "looking at the clip...".
- **Details** gains a row, "Camera moments: N described by <model>, M edited by staff", when any exist.
- The buttons grey with the assistant's unavailable line while the engine fails the minute check, as the other features' do. No tab and no buttons on a sound-only Recording, and none while Moments is Off.

### The call

- **The span.** Half the **Moment clip length** setting either side of the chosen time (5 s each side by default), clamped to the Recording; the span is kept on the Moment and shown as the clip's bounds.
- **The clip.** Cut on `llm-worker` from the Playback copy with ffmpeg: seek before the input so the cut is exact and its clock starts at zero, the span's length, no sound, the frames thinned to **Moment frames a second** and scaled to **Moment frame height** (never up), H.264 at the fastest preset, into a temporary file; read into the request as a `data:video/mp4;base64,` URL and deleted in every path.
- **The words.** The system message is the Ground rules, the **Moment** prompt template, and a fixed answer format (plain text, two to five sentences, seconds as the clip runs, never a `[hh:mm:ss]` time). The user message is one text part, the nature line and "This clip runs from [hh:mm:ss] to [hh:mm:ss] of the recording. The words spoken in this clip were:" with the rendered lines that start inside the span (the neighbours either side when none does), then one video part.
- **The budget.** The app's estimate of the clip, `ceil(frames / 2)` times the frame's 28-pixel patches, is added to the text's estimate and the answer cap before the window check, so a Moment is refused before the call when it would not fit. The answer cap is **Moment answer cap**; the time limit **Moment time limit**, which is never doubled: **a Moment never lets the model think**, whatever the Let the model think setting says, because the frames are billed against the same budget, a small model thinks at length over a picture, and a description is perception rather than deduction. Sampling is the assistant's usual.
- **What comes back** is stored whole as the Moment's text, with the model and the time; an empty answer is `llm_bad_output`. The one audit row is "AI assistant call" with feature `moment`, the usual metadata, and whether the Moment was asked for or came from a Cue.

### Cues

**Withdrawn in v1.40.0 and replaced by chapter 3.** As built in v1.38.0, a Cue was found by a fixed list of phrases matched whole in a line's words and never stored. On the office's own footage the list flagged ordinary talk far more often than a pointer at evidence ("what was that" about a sound, "on the ground" in a story), because whether a line points at something is a matter of context, which a word list cannot read. Chapter 3 finds Cues by reading, listening, and watching, stores them, and lets a person dismiss one.

### Exports and the assistant

- **The Word and plain-text Transcript exports** carry each described Moment as a Camera line in time order, before the first line that starts after it and after the last line otherwise: in plain text `[hh:mm:ss] Camera (a model's description, not transcript): ...`; in Word a bold "Camera:" run and the description in italic in the transcript's own type, so the line numbering runs on unbroken. When any Moment is present the notice gains the legend "Lines marked Camera are a model's description of what the picture showed at that time, not the transcript", and the Processing record gains the row "Camera moments". A Summary's export carries whatever the Summary said and nothing more.
- **Summary and Chat** are told the Moments while **Moments in answers** is On (and Moments itself is On): a block after the rendered Transcript, headed "What the camera showed (a model's descriptions, not the transcript):", one line per described Moment as `[hh:mm:ss] [camera] ...`. The block counts in the window check. A time cited from it is a Citation that seeks the player, matched to the Moment's time as a Segment's start would be. The Case Chat is not told (Not in this phase).
- **Edit** replaces the description with a person's own words and marks the Moment edited; **Again** describes the same span afresh; **Delete** removes it. Each writes its Viewer-edit row without a word.

### What changes from earlier phases

- The Phase 1 AI assistant chapter's "three features" are four; its audit-row table gains the `moment` feature; its reason-class table gains `llm_no_vision`; the never-logged list gains a Moment's description, its cue phrase, and its clip; the Shared engine paragraph's "the app sends no `priority`" is overturned: every request carries `priority` 1, as the box ledger's shared-engine paragraph asks, and `engine.complete` takes an `extra` mapping merged into the request's vLLM-only fields.
- Prompt helpers take the budget they are handed: `fits()` an `extra` count for what the estimate cannot read from text, `citations()` the Moments whose times may be cited.
- The Transcript exports interleave Camera lines; nothing about Segments changes.
- A Moment hangs on the Transcript, as a Suggestion does, so Process again takes it with the old Transcript.

### Audit rows

| Category | Row | When | Carries |
|---|---|---|---|
| LLM | AI assistant call, feature `moment` | once per Moment described, whether it succeeded, failed, or was refused | the usual: model, endpoint host, "ground-rules vN; Moment vN", token counts, duration, outcome; and the source, asked or cue; never the description, the phrase, or the clip |
| Viewer edits | Moment edited; Moment deleted | Edit saved; Delete confirmed | the Recording; never the words |

### Settings

Seven on the AI assistant page, in the catalogue: **Moments** (Off), **Moments in answers** (On), **Moment answer cap** (400 tokens), **Moment time limit** (120 s), **Moment clip length** (10 s), **Moment frames a second** (2), **Moment frame height** (360 pixels); all but the first greyed while Moments is Off, each with its default beside it and Reset to default. The **Moment** prompt template joins the Templates page.

### Not in this phase

- An automatic sweep that describes a whole video at intervals, or every Cue without asking. Under the ledger a batch of the app's own over the shared engine belongs in the quiet window, and Principle 1 says nothing looks by itself.
- Dismissing a Cue; a Cue that is not wanted is simply not accepted.
- Camera lines in the Case Chat.
- Still frames as the input, or a choice of span per Moment; the settings shape every Moment alike.
- A Moment as a Clip, or a Clip's captions carrying a Moment.
- Sound in the clip: the words go as text.

### Left to the build

- The cue phrase list (`prompts.CUES`); the app's, extended as the office's recordings show what people say.
- The exact ffmpeg arguments and the temporary file's home (`media.cut_for_description`, `tempfile.mkstemp` on the worker).
- The estimate of a clip's cost (`prompts.video_tokens`), read from the Qwen3-VL report and checked against the office's engine.
- The words that mark an engine's 400 as `llm_no_vision` (`engine.NO_VISION_WORDS`).

## 2. Questions, clearer words, and clips

Written 2026-09-11 after the first Moments on the office's own footage. The maintainer: attorneys and investigators "will want to know was that a baggy of weed in the car or was that a gun in the car"; descriptions "read more clearly, not such verbose explanations"; and "close the loop to the courtroom". Built in v1.39.0.

### Principles

1. **A pointed question gets a shaped answer, not a verdict.** Asked "is that a gun?", the model says what is visible (shape, colour, size, position, how it is held), what that is consistent with, naming the likeliest things plainly, and what cannot be told from the frames and why. It never states as fact what the frames cannot settle, and it never names a person. The reader decides; the app gives them the best look it can.
2. **Look closer, not longer.** A question is answered from a few still frames at the camera's own detail, not the small clip: a bag on a seat is a handful of pixels at 360 and legible at 720 or 1080. The clip stays for descriptions, where motion matters.
3. **Brief by default.** A description leads with the thing pointed at, in one to three short sentences of concrete nouns and plain verbs, without the setting restated or the words summarised; the full style, with the setting and the seconds, is a choice.
4. **The courtroom form is a Clip.** A Moment becomes a Clip in one click, its words the note and, when captions are burned, a caption marked Camera inside the picture. Nothing new is stored for it: a Clip is a Clip.

### Words

A **question** is a Moment that carries one; its answer is its text, and it appears, exported, and told to the assistant like any Moment, with the question in front: `(asked "is that a gun?") Visible: ...`. The Moment's **kind** in the audit row is `question` or `description`, never its words.

### The viewer

- The camera button on a row and **Describe this moment** at the playhead open one box: leave it empty to have the clip described, or type a question. A **Camera?** pill describes at once, since the Cue is the question.
- A question's card in the Moments tab shows "Asked:" and the question above the answer, "a question" in its head, and "Looking closely..." while it runs; a camera line under the row carries `(asked "...")` before the answer.
- **Make a clip** on a described Moment's card marks the Moment's span in the Clips tool and prefills the title ("Camera at hh:mm:ss", or the question) and the note (the description); the person saves it as any Clip. When the Clip burns captions, each described Moment inside its span is a caption marked Camera, shown for up to four seconds from its time.

### The call

- **A question**: the frames are taken at **Look closer frames** times spread a second either side of the chosen time (three by default: one second before, at, one second after), each scaled to **Look closer frame height** (720 by default, never up), as JPEGs from the Playback copy into a temporary folder of the worker's own, sent as image parts and deleted whatever happens. The system message is the Ground rules, the Moment template, the question rules, and the question's fixed shape (Visible, Consistent with, Cannot be told). The user text is the frames' time, the words spoken in the span, and the question. The estimate for the window check counts each frame's patches whole, since stills are not paired. Thinking off, as for every Moment. The answer cap and time limit are the Moment's.
- **A description**: as chapter 1, with the **Moment style** setting choosing the app's format line, brief or full; the Moment template holds the rules both follow, and its shipped wording is the brief one. The shipped answer cap is 250 tokens (chapter 1 shipped 400).
- **The audit row** gains the kind, `question` or `description`; the question itself is content and on the never-logged list with the description.

### What changes from chapter 1

- The Moment table gains `question` (migration 0036). A question does not block a description at the same time, and a description does not block a question.
- The Moment template's shipped wording is rewritten for brevity; an office that edited it keeps its own words and its version.
- The camera lines everywhere (viewer, exports, Summary and Chat) carry `(asked "...")` before a question's answer.
- A Clip's burned captions carry Camera cues.

### Settings

Three more on the AI assistant page, greyed while Moments is Off: **Moment style** (brief or full; brief), **Look closer frame height** (pixels, 360 to 1,080; 720), **Look closer frames** (1 to 5; 3). **Moment answer cap** ships at 250.

### Not in this phase

- A chat over one moment (question after question with memory); each question is its own Moment.
- Pointing at a region of the frame; the frames go whole.
- A Clip made by itself for every Moment; the person makes each one.

### Left to the build

- The spread of the frames' times (`assistant.question_times`), and the JPEG quality (`media.grab_frames`, q 3).
- The caption's length inside a Clip (`clip_work.CAMERA_CAPTION_SECONDS`, four seconds).

## 3. The finders

Written 2026-09-11 after the first day of Moments on the office's footage. The maintainer: "there's too much general conversation that includes things like 'what was that', 'on the ground'"; the answer is a finder that reads context, and a second that needs no words at all. Built in v1.40.0.

### Principles

1. **Context, not words.** A line is a Cue because the picture at that time would add a fact worth a person's look, judged from the whole Transcript by the engine, never because a phrase occurs.
2. **Still on request.** Find moments is one press; nothing is read, scanned, or described by itself. A Cue is an invitation until a person accepts it, and a person may dismiss one for good.
3. **Two finders, each with a switch.** The one that reads the words is On by default and costs one engine call per press. The one that scans the picture and sound uses no engine and runs on the media worker, Off by default until an office has judged it, since a body camera that swings about finds its own changes.
4. **A reason on every suggestion.** Each Cue says why, in a few words, and where it came from, so a person can decide without opening it.

### Words

A **Cue** as `CONTEXT.md` now defines it: a stored suggestion with a time, the line it belongs to when it has one, a kind (object, command, action, pointing, change), a reason, how sure the finder was, and its source (the words, the picture, or the sound). A **finder** is one of the two ways Cues are found. A Cue is **pending** until accepted (it becomes a Moment) or **dismissed**.

### Find moments from the words

- **The call.** One read of the whole Transcript: the Ground rules, the **Find moments** prompt template (editable), and the app's format line; the user message is the nature line, the rendered Transcript, and "List at most N lines", N being **Most suggested moments**. Structured output in a fixed schema (line number, kind, reason of at most 120 characters, confidence), the array bounded to N, deterministic sampling as Suggest names uses, one retry on invalid JSON, `llm_bad_output` after two. The answer cap is **Find moments answer cap**, the time limit **Find moments time limit**, doubled while the model may think.
- **The check.** Every entry is held to the Transcript: the line must exist, the kind and confidence must be from the lists, the reason must not be empty, a line is kept once, entries below **Least sure suggestion kept** are dropped, and the rest are ordered surest first and cut to N. The pending Cues from the words are replaced whole on every press; accepted and dismissed ones stay as they are.
- **The audit row** is "AI assistant call" with feature `moment_finder` and how many were kept; never a reason.

### Find moments from the picture and sound

- **The picture.** ffmpeg reads the Playback copy once at a small size and reports every frame that differs from the one before by more than **Picture change threshold** (a fraction of the picture; 40 percent by default).
- **The sound.** ffmpeg reads the sound once in one-second windows and reports each second's level; a second is loud when it sits **Loudness rise** (12 dB by default) above the recording's median level. Fewer than five seconds of level, and nothing is reported.
- **The thinning.** Times closer together than **Gap between scanned moments** (15 s) become one, first the picture's, then the sound's, then the two together; more than **Most suggested moments** are spread evenly over the recording rather than taken from its start. Each becomes a Cue of kind change, source picture or sound, with the fixed reason "The picture changes sharply here" or "Raised voices or a bang here", on the row nearest its time.
- **Where it runs.** On the media worker, as a Clip render does: not a Job, no place in the line, no Workspace clock. A long recording takes a few minutes. The one audit row is "Picture and sound scanned" under Recordings, with the counts.

### The viewer

- The Moments tab's **Suggested moments** gains **Find moments**, a status line ("Reading the transcript...", "Scanning the picture and sound...", "Nothing in the words calls for a look."), and a list where each Cue shows its time, its kind as a pill, its reason, how sure and where from, with **Describe** and **Dismiss**. A **Camera?** pill on the Cue's row carries the reason as its title. The Describe this moment and camera buttons are unchanged.
- Accepting a Cue makes a Moment at the Cue's time and line, from the cue, its reason kept as the Moment's cue text; the Cue is marked accepted and leaves the list. Dismiss marks it dismissed and it never returns from that press's results; the next Find moments may find the line again.

### Settings

Nine on the AI assistant page, greyed while Moments is Off: **Find moments from the words** (On), **Find moments from the picture and sound** (Off), **Most suggested moments** (12), **Least sure suggestion kept** (medium), **Find moments answer cap** (1,500 tokens), **Find moments time limit** (180 s); and, greyed while the second finder is Off, **Picture change threshold** (40 percent), **Loudness rise** (12 dB), **Gap between scanned moments** (15 s). The **Find moments** prompt template joins the Templates page.

### Not in this phase

- A finder that runs at transcription time or on a timer.
- A learned finder, or one that reads the office's past accepts and dismisses.
- A sound classifier (a siren, a shot, a dog): the loudness scan is the honest first step; a model for sounds is a research note first.

### Left to the build

- The scan's ffmpeg arguments (`moment_scan.scene_changes`, `moment_scan.loud_seconds`), the small size the picture is read at (320 wide), and the one-second window.
- The reasons the scan writes, fixed words rather than the engine's.
- The check's rules (`prompts.keep_cues`).

## 4. Deferred and ruled out

- **A second model for pictures**: ruled out for this phase. The engine the app talks to is a vision model, and a model of the app's own on the shared server's cards would be a ledger change first.
- **Sending a picture anywhere but the engine**: ruled out, as Phase 1's rules have it; nothing leaves the building.
- **Describing the whole video** (a timeline of what was seen): deferred; if wanted, it is a batch and takes the quiet window.
- **Reading text in the picture** (a plate, a label, a document): not asked for; the shipped instructions neither ask nor forbid it, and an office edits them.

## Appendix A. Audit rows added in Phase 4

| Category | Row | Chapter |
|---|---|---|
| LLM | AI assistant call, feature `moment` | Moments |
| LLM | AI assistant call, feature `moment_finder` | The finders |
| Recordings | Picture and sound scanned | The finders |
| Viewer edits | Moment edited; Moment deleted | Moments |

## Appendix B. Settings added in Phase 4

| Setting | Page | Type | Default |
|---|---|---|---|
| Moments | AI assistant | On or Off | Off |
| Moments in answers | AI assistant | On or Off; greyed while Moments is Off | On |
| Moment answer cap | AI assistant | tokens, 100 to 4,000; greyed while Moments is Off | 250 (400 in v1.38.0) |
| Moment time limit | AI assistant | seconds, 30 to 3,600; greyed while Moments is Off | 120 |
| Moment clip length | AI assistant | seconds, 4 to 30; greyed while Moments is Off | 10 |
| Moment frames a second | AI assistant | 1 to 4; greyed while Moments is Off | 2 |
| Moment frame height | AI assistant | pixels, 180 to 720; greyed while Moments is Off | 360 |
| Moment style | AI assistant | brief or full; greyed while Moments is Off | brief |
| Look closer frame height | AI assistant | pixels, 360 to 1,080; greyed while Moments is Off | 720 |
| Look closer frames | AI assistant | 1 to 5; greyed while Moments is Off | 3 |
| Find moments from the words | AI assistant | On or Off; greyed while Moments is Off | On |
| Find moments from the picture and sound | AI assistant | On or Off; greyed while Moments is Off | Off |
| Most suggested moments | AI assistant | 3 to 40; greyed while Moments is Off | 12 |
| Least sure suggestion kept | AI assistant | high, medium, or low; greyed while Moments is Off | medium |
| Find moments answer cap | AI assistant | tokens, 200 to 8,000; greyed while Moments is Off | 1,500 |
| Find moments time limit | AI assistant | seconds, 30 to 3,600; greyed while Moments is Off | 180 |
| Picture change threshold | AI assistant | percent, 10 to 90; greyed while the picture and sound finder is Off | 40 |
| Loudness rise | AI assistant | dB, 3 to 30; greyed while the picture and sound finder is Off | 12 |
| Gap between scanned moments | AI assistant | seconds, 5 to 120; greyed while the picture and sound finder is Off | 15 |
| Find moments (template) | Templates | a prompt template, Reset to default, a version that rises on every save | the chapter's wording |
| Moment (template) | Templates | a prompt template, Reset to default, a version that rises on every save | the chapter's wording |

## Sources

The maintainer's ask and decisions of 2026-09-11; `docs/research/moments-vision-engine.md` (the model card, vLLM's multimodal guide and recipe, the Qwen3-VL report, BodyCam-VQA, and the probes against the office's engine); the Phase 1 AI assistant chapter; the box ledger's shared-engine paragraph and GIDEON's line 17.

## Amendments applied

- From the maintainer, on the v1.38.0 build, chapter 2 (v1.39.0): questions answered from close frames in a fixed shape, the brief style as the default with the answer cap at 250, and Moment to Clip with Camera captions.
- From the maintainer, on the v1.39.0 build, chapter 3 (v1.40.0): the word-list Cues withdrawn for flagging ordinary talk; the finder that reads the Transcript and the scan of the picture and sound, each with its switch and its numbers; Cues stored, with a reason, and dismissable.
