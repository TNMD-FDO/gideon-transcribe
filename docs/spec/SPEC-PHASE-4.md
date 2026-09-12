# Gideon Transcribe, Phase 4 specification

The Moments release, published as `v1.38.0`, its second chapter in `v1.39.0`, its third in `v1.40.0`, its fourth in `v1.41.0`, and its fifth in `v1.43.0`.

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
- **Intervals and the summary** (chapter 4, v1.41.0): the whole recording described at intervals, one lane, one call each; a Summary that describes the moments first when asked, and draws on what was seen; and a "What the camera showed" section in the Summary's Word export.
- **The video summary and the video-aware chat** (chapter 5, v1.43.0): a shipped Video summary template that writes from the words and the described Moments together, fixed camera rules that keep the two sources apart whenever Camera lines are handed to Summary or Chat, a Chat that answers "what was in his hand at 12:40?" from both feeds, a look-first line in the summary dialog that says the cost in numbers and starts ticked by a rule, and camera citations drawn with the camera glyph.
- **The picture record and the Digest** (chapter 6, proposed, not yet built): the recording cut where the picture and the sound change and described once per span, never twice and never overlapping, as the foundation a video's summary is written from, made when a summary is asked for; one Digest per Transcript, a model's time-ordered condensation of the words and the camera that the Summary, the Chat and the Case Chat are written from; Cues and the camera lines among the transcript's rows withdrawn.

It adds twenty-three admin settings, two prompt templates, one shipped Summary template, two audit row features, one Recordings row, two Viewer-edit rows, one reason class, three tables (migrations 0035 to 0039), and no environment key.

## Contents

1. Moments
2. Questions, clearer words, and clips
3. The finders
4. Intervals and the summary
5. The video summary and the video-aware chat
6. The picture record and the Digest (proposed 2026-09-12, not yet built)
7. Deferred and ruled out

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

- **The Moments tab** joins the Bench beside Summary and Chat (on a laptop, a tab of the sheet) as two panels, the shape the Clips tab has. The first has the head with **Describe this moment**, which asks for the playhead's time, a line in words while the engine is unreachable, and **Suggested moments**: **Find moments** and **Describe the whole recording** together, each with a caption saying what it does and what it costs in numbers and a line under it that says what the press did, then the Cues, each with its time, its kind, its reason, how sure and where from, the transcript line it was found on in quotes, and Describe and Dismiss. The second, **Described moments (n)**, lists the Moments newest last, each with its time as a citation, whether it was asked for, a question, from a suggestion, or from the whole recording, when it was described, the AI notice, its text, and Edit, Describe again (Ask again on a question), Make a clip, and Delete; a foot line says a Moment is what the assistant saw and where Moments print. While a Moment waits its card says "Waiting its turn...", while it is being described "Looking at the clip..."; a failed one says why in the assistant's words.
- **The rows.** Every transcript row gains a small **describe** button among its actions, "Describe the picture at this line, or ask a question about it", which opens the box for that line's start. A Cue's row carries a dashed **Camera?** button after the Speaker's name, the reason as its title, which describes at once and reads "Looking..." until the Camera line replaces it (v1.42.0). A described Moment appears as a Camera line under the row nearest its time: the tag Camera, the time as a citation, and the description in italic; while it waits the line says "waiting its turn...", and while it is being described "looking at the clip...".
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
- **Edit** replaces the description with a person's own words and marks the Moment edited; **Describe again** (**Ask again** on a question) describes the same span afresh after a confirm that says it costs one engine call and replaces any edit; **Delete** removes it. Each writes its Viewer-edit row without a word.

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

- The **describe** button on a row and **Describe this moment** at the playhead open one box, named for the time ("Describe the picture at 12:45"): leave it empty to have the clip described, or type a question. A **Camera?** button describes at once, since the Cue is the question.
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

- The Moments tab's **Suggested moments** gains **Find moments**, a status line ("Reading the transcript...", "Scanning the picture and sound...", "Nothing in the words calls for a look."), and a list where each Cue shows its time, its kind as a pill, its reason, how sure and where from, with **Describe** and **Dismiss**. A **Camera?** button on the Cue's row carries the reason as its title. The Describe this moment and describe buttons are unchanged.
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

## 4. Intervals and the summary

Written 2026-09-11 after the finders' first day: the maintainer found the word finder "hit or miss" and asked that summaries "do a decent or good job of picking the moments that are then described". The answer lets the picture decide: describe the recording throughout, and let the Summary, which reads everything, pick what mattered. Built in v1.41.0.

### Principles

1. **One lane, one call each.** Describe the whole recording makes one Moment per interval and describes them one after another in a single lane of the AI assistant, so a long recording never takes the four lanes from everyone else. It is a press, never automatic.
2. **Nothing described twice.** A time within half an interval of a Moment already described, or being described, is skipped; the most allowed are spread evenly over the recording rather than taken from its start.
3. **The Summary picks.** A Summary asked to describe the moments first runs the intervals in its own lane before it writes, then receives every described Moment as camera lines and is told it may draw on them, citing their times and saying "the camera shows". What mattered is the Summary's judgement, made from everything seen and said.
4. **The export shows its evidence.** A Summary's Word export ends with "What the camera showed": every described Moment with its time, under the legend, so a reader sees what the summary drew on.

### Describe the whole recording

- **The button**, under Suggested moments beside Find moments, carries a caption that says the interval in words and how many Moments it would make now ("A description every minute, 23 in all for this recording, one engine call each. Times already described are skipped."; the state answer carries the interval and the count), asks once in the same words, and starts a run; when nothing is left to describe the caption says so and the button waits. The times are every **Describe at intervals: every** seconds from half an interval in, skipping times already described, at most **Describe at intervals: at most**, spread evenly when more. Each becomes a Moment of source interval, described as chapter 1 describes one; a failed Moment is left failed and the run goes on; the run stops when the engine goes away, the rest marked unreachable.
- **The run** is a CueRun of source interval with a total and a count; the tab says "Describing the recording: n of m..." and the button waits; "Every interval is described already." when there was nothing to do.

### The Summary

- The summary dialog on a video with Moments on gains the tick **Describe the moments first**, starting as the **Summaries describe the moments first** setting says (Off), with a line on the cost. A Summary made with it ticked runs the intervals in its own lane before it writes (the card says "Looking at the picture first (n of m)..."), then writes with the camera block as chapter 1 has it; the engine going away during the intervals fails the Summary as unreachable.
- The app's summary format line now tells the model that a "What the camera showed" block may be drawn on, cited by time, and said to be from the camera. The editable templates are unchanged; an office may say more in its Body camera template.
- The Summary's Word export gains the section **What the camera showed** after the summary's body when any described Moment exists: the legend, then one line per Moment, time and words.

### Settings

Three on the AI assistant page, greyed while Moments is Off: **Describe at intervals: every** (60 s, 20 to 600), **Describe at intervals: at most** (40, 5 to 200), **Summaries describe the moments first** (Off).

### Not in this phase

- Choosing which interval Moments a Summary uses; it receives all of them, as Moments in answers has it. (Chapter 5, v1.43.0: the model picks under a per-length cap, and the app thins the block only past its budget.)
- Describing at intervals on a timer or at transcription.
- Deleting the interval Moments in one press; each is a Moment like any other.

### Left to the build

- The first time (half an interval in), the skip rule (half an interval), and the spreading (`assistant.interval_times`).
- The order (time order) and the stop rule (`assistant.describe_intervals`).

## 5. The video summary and the video-aware chat

Written 2026-09-12 after chapter 4 shipped and the maintainer asked for "a smart way to summarize all the moments in conjunction with the transcript for a comprehensive summary of a video", intuitive, "not overly verbose", with a chat "that also uses the smart combo", and "some good prompting". Chapter 4 built the plumbing: the intervals, the tick, the camera block after the Transcript. What was missing was the choosing, the prompting, and the words on the screen. Built in v1.43.0.

### Principles

1. **Two sources, kept apart.** The Transcript is the record of what was said; a Moment is a model's description of what was visible. The model is told both and never lets them blur: a fact from the words carries its line's time, a fact from the camera is written as "the camera shows ..." with the camera line's time, and never the two in one unmarked clause.
2. **Neither wins.** When the words and the picture disagree, the answer gives both with their times and says that they differ. The reader judges.
3. **Names from the words only.** The camera's "a man in a grey hoodie" stays that even when the words name him; the two are joined only side by side. Nothing is inferred from the picture: not who someone is, not what they intend, not what an object is beyond what the description says, and never a legal fact.
4. **Only the listed times.** The camera was looked at only where a Moment exists. Asked about any other time, the assistant says no moment was described there, and where to ask for one.
5. **Brevity.** A camera fact earns a clause, not a paragraph; a summary of each length draws on a stated number of camera lines and leaves the rest out rather than listing them. The maintainer's "not overly verbose" is a rule the model is given, not a hope.
6. **The rules are the app's; the shape is the office's.** The camera rules are fixed and never edited; the Video summary and the Body camera summary are templates an office edits or resets like any other, and every other template is still governed by the rules when a block is present.

### Words

**Video summary** and **Camera rules** are added to the glossary.

### The templates and the rules

- **The Video summary**, a shipped template for no Recording type: Overview; **What happened**, each point ending with its time, and where the camera showed the thing said or done, "the camera shows ..." added to the same point with the camera line's time, camera lines that only repeat the scene left out; **Seen but not said**, what the camera showed that nobody spoke about, each as "the camera shows ..." with its time, "None noticed" when there are none; Notable statements; Names, places, and dates, mentioned in the words, never a name from the camera; Unclear parts, the audio's and the camera's.
- **The Body camera summary** gains the same two things: its Timeline draws on the camera the same way, and Seen but not said follows What officers say to each other. An office that edited its Body camera summary keeps its words and version, and gets the new parts with Reset to default.
- **The camera rules** (`prompts.CAMERA_RULES`, fixed) follow the answer format in the system message of Summary and of Chat only when a camera block is given, so a sound-only Recording pays nothing: the six principles above as instructions, with the worked example of a name joined side by side.
- **The block** keeps its heading and gains a legend line: one line per described Moment, in time order; times not listed were not looked at. A line staff edited ends "(edited by staff)" in the block only, so the heading's "a model's descriptions" is honest for every line; the exports have their legend and provenance row already.
- **The length line** gains, when a block is given, how many camera lines to draw on: 5 for Short, 12 for Standard, 30 for Detailed, "the ones that add a fact the words do not; leave the rest out rather than listing them"; when the block has no more than that, "draw on the ones that add a fact the words do not".
- **The block's budget**: past `CAMERA_BLOCK_TOKENS` (6,000 by the app's estimate) the block is thinned, every asked and suggested Moment kept and the interval Moments spread evenly, fewer each step, until it fits. At the shipped numbers nothing is thinned; the budget exists for the office that sets two hundred intervals in the full style.
- **The summary format line** loses its one sentence on the camera block, which the rules replace, and says that a part asking for what the camera showed reads "No moments were described" when no block was given.
- **The Chat template** (editable) answers from the Transcript and, when given, the block; asked what was visible at a time it uses the camera line nearest it within a minute or says none was described there and that one can be asked for on the Moments tab; asked for a legal conclusion (consent, arrest, a lawful search) it gives what was said and what the camera showed, with times, then says in one sentence that the conclusion is not something it can answer from a transcript; legal advice, guilt, credibility, and anything outside both feeds still get "I can only answer from this transcript". The Case Chat is untouched (chapter 1's Not in this phase stands).

### The viewer

- **The button.** On a video with Moments on and Moments in answers on, the Summary tab's button reads **Summarise this video**; otherwise New summary. The empty state says what it does: "Summarise this video looks at the picture at intervals, then writes from the words and the moments together."
- **The template chosen.** A Recording type wins (a body camera recording gets the Body camera summary); a video of any other type or none gets the Video summary while Moments reach answers and the template is Enabled; the type line reads "This is a video, so the Video summary is chosen."; the state answer carries the chosen template's key.
- **The look-first line** replaces the tick's caption, in one of three forms the page chooses from the state: while intervals are left to describe, the tick **Look at the picture first** with "n descriptions, one every minute, one engine call each, about m minutes. k moments are described already."; when none are left, "The summary draws on the k described moments."; when the office hands no Moments to answers, "Your office does not hand moments to summaries, so this one is written from the words alone." The minutes are `count` times a code guess of twenty seconds a description (`assistant.MOMENT_SECONDS_GUESS`), a note and never a limit.
- **The tick's start** is a rule, not a bare toggle: ticked when **Summaries describe the moments first** is On, something is left to describe, and fewer Moments are described than **Enough moments for a video summary** (0 meaning always). The state answer carries `cue_runs.described`, `cue_runs.answers_use_moments`, `cue_runs.intervals.minutes`, and `describe_first_default` computed by the rule.
- **The card** says "Reading the transcript and n moments..." while the one call runs (after "Looking at the picture first (n of m)..." while the intervals run), and its head says how many moments the summary drew on; a Summary remembers the number (`moments_used`, migration 0039).
- **Camera citations.** A time cited in a summary or a chat answer that is a described Moment's time is drawn with the camera glyph before it and the description as its hover title; a word citation is as before; both seek the player. The Chat's play pill carries the glyph in place of the play mark.
- **The Chat's lines.** The grounding line reads "Answers come from this transcript and its n described moments, not from any other recording. What the camera showed is a model's description."; the waiting line "Reading the transcript and n moments..."; without Moments, both as before.

### Settings

One new on the AI assistant page, greyed while Moments is Off: **Enough moments for a video summary** (10, 0 to 200). **Summaries describe the moments first** starts On (Off in v1.41.0), reworded to say what it now governs.

### Not in this phase

- The Case Chat being told Moments.
- A Templates page notice that a newer shipped wording exists for a template an office edited.
- Choosing the Video summary for a video whose office writes from the words alone; it gets the Default, and the dialog says why.

### Left to the build

- The per-length numbers (`prompts.CAMERA_MOST`), the block budget (`prompts.CAMERA_BLOCK_TOKENS`), and the thinning (`prompts.trim_camera_lines`).
- The "within a minute" rule for a question about a time, in the Chat template.
- The seconds-a-description guess behind the dialog's minutes.

## 6. The picture record and the Digest

Proposed 2026-09-12, while v1.50.0 built, from the maintainer's ask to "make summarization smart. One that combines moments and the transcription for awesome narratives of events", and their answers to the build's questions: the foundation is "good VLM explanations of snippets taken every so often" joined with the transcript, and it serves "both the overarching case chat as well as the single summaries for individual videos"; no scene-by-scene breakdown, "but every scene should inform the overall summary"; no section on where the words and the picture disagree; a sound-only Recording's summary is a summary as it is today, and for a video "we are still talking about summaries"; the picture record is made for "those creating summaries" and never on its own; every feature has its switch on the Admin panel; the interval is the setting that exists, "for now let's say every 15 seconds"; the Digest is plumbing nobody reads. Reshaped the same day at the maintainer's second reading: Cues left out ("too many pointless cues", and "drawing cues only from a transcript does not seem optimal"); no overlapping descriptions; "a focus should always be smart optimization"; no Moment shown in line with the transcript; "the whole theme and plan should center around optimized usage of the transcript and vlm capabilities without onerous tasking that causes overlap". Not yet built.

### Principles

1. **Made for the person asking.** The picture record of a video is made when someone asks for its summary, in that summary's lane. Nothing describes a picture on a timer or at transcription; chapter 1's first principle stands. Describe this moment and a question about the picture remain, on request, beside the record.
2. **Once, and only where the picture changes.** Every second of a video that is summarised falls inside exactly one description's span: the record cuts the recording into spans that touch and never overlap. A span where the picture holds still is one description however long it runs, up to a ceiling; a span is never described twice; and each description is told what the one before it said, so it reports what is new rather than the room again.
3. **The picture decides, not a word list.** Where to look is settled by the scan of the picture and sound (chapter 3's second finder), which marks the seconds where the picture or the sound changes sharply; the clock is only the ceiling between them. Cues, the word finder, and everything that grew from them are withdrawn when this chapter is built.
4. **Every scene informs; nothing is listed.** A Summary is written from a Digest made from all of the words and all of the record, so no stretch is left out of what it draws on; the Summary's shape stays its template's, and no part walks the recording scene by scene unless the template asks. The per-length caps on camera lines (chapter 5) go, because the Digest has already done the choosing.
5. **The two sources survive the condensing.** Every line of a Digest says whether it came from the words, the camera, or both, and the camera rules govern the Digest as they govern an answer.
6. **The transcript stays the transcript.** No Camera line sits among the rows any more, in the viewer or interleaved in an export; the Moments tab lists the record, and an export carries it in its own section at the end. The row's describe button stays as the way to ask about that line's time.
7. **Plumbing, made once, refreshed only where stale.** Nobody reads a Digest. Its parts are kept per window with what each was made from, and only a part whose words or descriptions changed is remade.
8. **Every feature is a switch, and the cost is said in numbers.** The record and the Digest each have their switch on the AI assistant page; the dialog says how many descriptions and how many Digest parts a press will make and about how long; the catalogue and the ledger say what the engine is asked for.

### Words

**Picture record** and **Digest** are added to the glossary. A description's **span** is the stretch of the recording it covers; a Digest's **part** is one window of the Transcript condensed by one call. **Cue** leaves the glossary when this chapter is built.

### What is withdrawn

- **Cues**: the word finder (Find moments from the words) and its settings, the Cue rows, the Suggested moments list, the Camera? pill, Dismiss, and the audit feature `moment_finder`. The scan of the picture and sound stays, with its thresholds, and no longer makes Cues: its change points are what the record is cut by, and the row "Picture and sound scanned" is written as before.
- **Camera lines among the rows**: the viewer's Camera line under the nearest row (chapter 1) and the exports' interleaved camera lines (chapter 1). The Transcript export and the Summary export keep the section "What the camera showed" at the end (chapter 4), one line per description with its span.
- **Enough moments for a video summary**, the tick's count rule, and the per-length camera counts (chapter 5).

### The picture record

- **The cut.** When a summary asks for the record, the scan runs over the whole recording once if it has not, and its change points (scene changes above the threshold, and loud seconds) are kept on the Transcript, remade only by Process again. The recording is cut at the change points into spans; a span longer than **Picture record: longest span** is cut into equal pieces no longer than that; a span shorter than **Picture record: shortest span** is joined to its neighbour. The spans touch, never overlap, and cover the whole recording, at most **Picture record: most descriptions** of them, the longest cut coarser first when there would be more.
- **The description.** One Moment per span, of source interval, its time the span's start and its span kept on it (the fields chapter 1 gave a Moment). The clip is the span itself, its frames thinned to at most **Picture record: frames per description**, so a long still span costs the engine no more than a short busy one. The instructions give the previous span's description and ask for what is new in this one: what moved, what came into view, what was handled, where the camera went; a span where nothing changed is one line beginning "Unchanged:". Never twice: a span already described, or covered by a Moment's span, is skipped. The order is time order, one lane, and the run stops when the engine goes away, as chapter 4 has it.
- **What it costs** is proportional to change: an interview in a room is a handful of descriptions; a foot pursuit is one every longest span. The dialog says the count and the minutes before the press, from the cut, which is cheap and runs when the dialog opens.
- **Asked Moments and questions** (chapters 1 and 2) are unchanged and sit beside the record on the Moments tab; the Digest takes them in with the rest.
- **The switch**: **Picture record for summaries** (On or Off, greyed while Moments is Off). Off, the dialog offers no tick and a Summary draws on whatever Moments exist.

### The Digest

- **What it is.** One text per Transcript: a time-ordered record of what happened in the recording, condensed by the model from the Transcript and the camera lines, in numbered lines of the form `[hh:mm:ss]-[hh:mm:ss] (said | seen | both) ...`, with the exact words kept inside quotation marks for any statement about the case, a request, an instruction, a name, a place, or a date, so that a Summary written from the Digest can still quote. Under the camera rules throughout; a run of "Unchanged:" descriptions is one line.
- **How it is made.** In the summary's lane, after the record and before the Summary writes. The Transcript is cut into windows of about **Digest window** tokens on Segment boundaries; each window is sent with the camera lines whose spans fall in it, the nature line, the fixed Digest instructions, and the camera rules, one call per window, answer capped at **Digest part cap**; the parts join in order. A window without camera lines is condensed from the words alone. A short recording is one window. Thinking is never on for a Digest.
- **What is kept.** A Digest row on the Transcript: the parts, each with the window it covers and a signature of the Segments and the Moments it was made from, the model, when each was made. Never logged; content. Replaced part by part.
- **When it is current.** A part is current while its signature matches; a summary press remakes only the stale parts, and the card says "Condensing the recording (n of m)...". The Chat and the Case Chat never make or remake one; they use the Digest as it stands and say when it was made.
- **The switch**: **Digests** (On or Off, greyed while Moments is Off). Off, nothing is made and the three features work as chapter 5 has them.

### The Summary

- A Summary on a Recording with a current Digest is written from the nature line, the Transcript when it fits the window beside everything else, the Digest headed "The record of this recording (a model's condensation of the words and the camera, in time order; every time is the transcript's):", the template, and the camera rules. When the Transcript does not fit, the Digest stands alone for it, and the Summary is no longer refused as too long. No per-length camera count is sent; the length line says the Digest is complete and the Summary chooses what matters.
- A sound-only Recording, or one without a Digest, is summarised as today.
- Details gains "Digest: made <when> from the transcript and n descriptions, in m parts"; the Summary's head says it was written from the Digest.

### The Chat

- A Chat on a Recording with a Digest is told the Transcript, the Digest in place of the camera block, and then the **descriptions whose spans hold the times the question names**, up to **Chat: descriptions near an asked time**, so that "what was in his hand at 12:40?" is answered from the description itself. A question that names no time gets the Digest alone for the picture.
- The grounding line reads "Answers come from this transcript and its record of n descriptions, made <when>."; a Digest older than the Transcript or the record says so in the line.

### The Case Chat

- A Recording's contribution to a Reading is its Transcript and, when it has a Digest, the Digest after it under the record heading, so the picture reaches the case-wide answer labelled. When the Case would exceed the hours ceiling, or a Transcript alone does not fit, a Recording that has a Digest contributes the Digest alone, which is how a case of many videos fits; a Recording without one is read or refused as the Case Chat chapter has it.
- Chapter 1's "The Case Chat is not told" is withdrawn by this; the Case Chat template's wording is unchanged, and the camera rules follow its format when any Digest is present.

### Settings

On the AI assistant page, greyed while Moments is Off: **Picture record for summaries** (On), **Digests** (On), **Picture record: longest span** (15 s, 5 to 600; the renamed Describe at intervals: every), **Picture record: shortest span** (3 s, 1 to 30), **Picture record: most descriptions** (600, 5 to 2,000; the renamed Describe at intervals: at most), **Picture record: frames per description** (16, 4 to 64), **Digest window** (12,000 tokens, 4,000 to 40,000), **Digest part cap** (1,200 tokens, 300 to 4,000), **Chat: descriptions near an asked time** (6, 0 to 30). The scan's thresholds stay as chapter 3 has them. Withdrawn: **Enough moments for a video summary** and the word finder's settings.

### Audit rows

AI assistant call, feature `digest`, one per part, the usual metadata and never the text. Withdrawn: feature `moment_finder`.

### What changes from earlier chapters

- Chapter 1: Cues, the Camera? pill, the Camera line under a row, and the interleaved camera lines in exports; chapter 3: the word finder and the Cue rows, the scan kept and repurposed; chapter 4: the tick rule; chapter 5: the per-length counts and the Enough setting; chapters 1 and 5: "The Case Chat is not told".
- The block budget and thinning (chapter 5) stay for a Recording without a Digest.
- The ledger: the engine is asked, per video summarised for the first time, for one description per span of change, at the ceiling one per longest span, about four thousand tokens and ten to twenty seconds each, in one lane; "For GIDEON" in the next entry.

### Not in this phase

- Showing the Digest to a person, or exporting it.
- A Digest on a timer, at transcription, or for a Case as a whole.
- Choosing descriptions for the Case Chat by the times a question names.
- Anything that recognises a face or a voice.

### Left to the build

- The Digest instructions (`prompts.DIGEST`), the record heading, and the description instructions with the previous span given.
- The cut: the join rule for short spans, the coarser cut past the ceiling, the frame thinning of a long span (`moment_scan` and `media.cut_for_description`).
- The window cut on Segment boundaries, the part signatures, and the wording of the dialog's count line for the descriptions and the parts.

## 7. Deferred and ruled out

- **A second model for pictures**: ruled out for this phase. The engine the app talks to is a vision model, and a model of the app's own on the shared server's cards would be a ledger change first.
- **Sending a picture anywhere but the engine**: ruled out, as Phase 1's rules have it; nothing leaves the building.
- **Describing the whole video** (a timeline of what was seen): built on request in chapter 4 and made the foundation of a summary in chapter 6; never on a timer.
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
| Describe at intervals: every | AI assistant | seconds, 20 to 600; greyed while Moments is Off | 60 |
| Describe at intervals: at most | AI assistant | 5 to 200; greyed while Moments is Off | 40 |
| Summaries describe the moments first | AI assistant | On or Off; greyed while Moments is Off | On (Off in v1.41.0) |
| Enough moments for a video summary | AI assistant | 0 to 200; greyed while Moments is Off | 10 |
| Video summary (template) | Templates | a Summary template for no Recording type, editable, resettable, not deletable | the chapter 5 wording |
| Moment (template) | Templates | a prompt template, Reset to default, a version that rises on every save | the chapter's wording |

## Sources

The maintainer's ask and decisions of 2026-09-11; `docs/research/moments-vision-engine.md` (the model card, vLLM's multimodal guide and recipe, the Qwen3-VL report, BodyCam-VQA, and the probes against the office's engine); the Phase 1 AI assistant chapter; the box ledger's shared-engine paragraph and GIDEON's line 17.

## Amendments applied

- From the maintainer, on the v1.38.0 build, chapter 2 (v1.39.0): questions answered from close frames in a fixed shape, the brief style as the default with the answer cap at 250, and Moment to Clip with Camera captions.
- From the maintainer, on the v1.39.0 build, chapter 3 (v1.40.0): the word-list Cues withdrawn for flagging ordinary talk; the finder that reads the Transcript and the scan of the picture and sound, each with its switch and its numbers; Cues stored, with a reason, and dismissable.
- From the maintainer, on the v1.40.0 build, chapter 4 (v1.41.0): the whole recording described at intervals in one lane, the Summary's tick to describe the moments first, the summary format line that lets it draw on the camera block, and the export's "What the camera showed" section.
- From the maintainer, on the v1.42.0 build ("a smart way to summarize all the moments in conjunction with the transcript"), chapter 5 (v1.43.0): the Video summary template and the Body camera summary's two camera parts; the fixed camera rules given to Summary and Chat whenever a block is present; the block's legend line and the edited mark; the per-length count of camera lines to draw on and the block's budget; the Chat template answering from both feeds, with the "within a minute" rule and the facts-then-decline shape for a legal conclusion; Summarise this video, the template chosen for a video, the three-form look-first line, the tick's rule with Enough moments for a video summary, Summaries describe the moments first starting On, the summary's count of moments used, and camera citations with the glyph.
- From the maintainer, on the v1.41.0 build ("the page is sort of getting congested"), the Moments tab refined (v1.42.0): two panels behind the one tab, as the Clips tab has, Suggested moments with the Cues and Described moments with the Moments; Find moments and Describe the whole recording together under Suggested moments, each with a caption that says what it does and what it costs in numbers (the state answer's `cue_runs.intervals` carries the interval and how many Moments the press would make now) and a result line under it ("7 lines suggested from the words.", "3 changes found in the picture and sound.", "20 moments described across the recording.", "Both finders are off for your office."); a Cue quotes the transcript line it was found on and says sure, fairly sure, or unsure; Again reads Describe again, or Ask again on a question, and waits while the Moment is being described; a card says from a suggestion or from the whole recording and Waiting its turn... while queued; the row's button reads describe and, like Describe this moment, opens a box that names the time, with Describe as its OK; the Camera? pill is a button that says "Looking..." after the press; the Camera line has no coloured bar of its own, its tag in the muted colour, and says "waiting its turn..." while queued; the summary dialog's tick says the interval and the count in its note.
