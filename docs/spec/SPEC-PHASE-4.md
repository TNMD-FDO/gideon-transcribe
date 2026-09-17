# Gideon Transcribe, Phase 4 specification

The picture: what the camera showed. Released as `v1.38.0` and refined through `v1.54.0`, which built chapter 5 (Vision).

## About this document

This is the build specification for Phase 4 of Gideon Transcribe as it stands, rewritten whole on 2026-09-14. A transcript carries what was said; a body-worn camera or interview video has moments the words only point at. Phase 4 gives the AI assistant eyes: the picture of a video is scanned for where it changes, described span by span by the vision model the office already talks to, joined with the words into a Digest, and the Summary and the Chat are written from both. The Case Chat reads the same.

Phase 4 was first written as a diary, one chapter per release from `v1.38.0` on, and each chapter kept the earlier ones in place. By `v1.52.0` most of what the first five chapters built had been withdrawn (the Moments tab, the Cues, the finders, the questions about a frame, the summary's tick), and the document led a reader into a product that no longer existed. This rewrite says only what is in force, with one chapter for what is proposed. The diary is kept whole as `docs/spec/history/SPEC-PHASE-4-AS-WRITTEN.md`, for the record of what was tried and why it was dropped; nothing is built from it. Chapter numbers cited in the code's comments and in the changelog up to v1.53.2 are the diary's.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 4 words Moment, Prepared, Digest, Camera stamp, Vision, Vision request), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (every setting), and `docs/research/moments-vision-engine.md` (the model card, vLLM's multimodal interface, and the probes against the office's engine that settled the shape of a request).

Nothing in this document is office-specific. No new environment key is needed and no new service: the engine the office already talks to is a vision model, and the app's worker already carries ffmpeg. The conventions of the Phase 1 document apply here unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing leaves the building.

## What Phase 4 adds

- **A video is enriched with vision.** Its picture is scanned once for where the picture and the sound change; the recording is cut at those points into spans that touch and never overlap; each span is shown to the engine as a short silent clip and described once, told what the span before it showed; the date, time and camera id many body cameras burn into the picture are read from two frames and checked; and the words and the descriptions are condensed, window by window, into a Digest. Nothing image-like is kept.
- **A memo, not a play-by-play.** A video's summary is a memo a member of staff hands to an attorney, written from the words and the picture as one account: a summary paragraph, the people as the recording identifies them, what happened by subject, the statements that matter, the names and dates, the unclear stretches. A person is named, or given a role, only as the words give it.
- **A chat that has seen the video.** A question is answered from the transcript, the Digest, and the descriptions nearest the times asked, under fixed rules that keep the two sources honest.
- **The wait is said in numbers**, everywhere the work shows: how many descriptions and parts are left and about how long, measured on the office's own engine.
- **Admins read the Digest** under Details, and every instruction the app builds on is a template they can edit, reset, and that follows each release's wording while unedited.
- **Vision on the office's terms** (chapter 5, v1.54.0): a tick on the upload page, a schedule (as each transcript lands, overnight, or only when an Admin allows it), requests an Admin allows or declines, two mails, and a Vision page in the Panel.

Every request the app sends the engine carries `priority` 1, as the shared server's ledger asks of a client, and an engine that cannot take a picture says so with the reason class `llm_no_vision`.

## Contents

1. Principles
2. Words
3. What runs when a video is enriched
4. The memo and the chat
5. Vision: the tick, the night, and what an Admin allows
6. The pages, the exports, and the mail
7. The Panel: the Vision page and the templates
8. Audit rows and reason classes
9. Deferred and ruled out

Appendices: A. Audit rows in force. B. Settings in force. C. What was tried and withdrawn.

## 1. Principles

1. **Nobody presses anything on the recording page.** The picture record and the Digest are the foundation a video's summary and chat stand on, and a foundation is laid by the app. The person asks for a summary or a question, or opens the case, and never has to know how the picture was read.
2. **Once, and only where the picture changes.** Every second of a video falls inside exactly one description's span; a span where the picture holds still is one description however long it runs, up to a ceiling; a span is never described twice; each description says what is new.
3. **Every scene informs; nothing is listed.** The summary is written from a Digest made from all of the words and all of the record, so no stretch is left out of what it draws on, and the summary's shape stays its template's.
4. **One account, honest about its sources.** A summary never says which sentence came from the words and which from the picture. The guardrails stay: a person is named, or given a role, only as the words give it; an object is what the description saw and never more; a stretch the camera could not make out is not visible, not filled in; never a legal conclusion.
5. **Nothing image-like is kept.** A clip or a frame shown to the engine is cut to a temporary file of the worker's own, read once into the request, and deleted whatever happens. The data directory never holds a frame, a thumbnail, or a clip. Descriptions, the Digest and the stamp are content: never logged, never in an audit row.
6. **The engine is the one the app already has.** No second model, no GPU memory of the app's own, no new service. Every request carries the lowest priority, and a description never lets the model think.
7. **The wait is said in numbers.** Everywhere the work shows, the count done and left and about how long, from what descriptions and parts have taken on this engine, never a guess once one has been measured.
8. **Every part is a switch, and Admins can read the plumbing.** The record, the Digest, the stamp, and the whole of vision have their switches; the Digest and the descriptions are readable by an Admin under Details; the instructions are templates.
9. **The picture is the office's choice and the night is where its bulk belongs** (chapter 5). The engine is shared with its owner's own users by day.

## 2. Words

As `CONTEXT.md` defines them:

- **Moment**: the app's own name for one description row: a span of the recording, the text the model wrote for it, its source, and who asked. It appears on no page by that name; the pages say description. The rows of the withdrawn features (asked moments, questions) stay as they were, printed by the exports.
- **Picture record**: the descriptions of a video's spans, complete when every second is covered.
- **Digest**: one text per Transcript, a time-ordered condensation of the words and the descriptions in numbered lines, made in windows, that the Summary, the Chat and the Case Chat are written from.
- **Camera stamp**: the date, clock time and camera id burned into the picture, read once and checked.
- **Prepared**: the field's name for a video whose record is complete and whose Digest is current; on the pages, since chapter 5, Enriched with vision.
- **Vision** (chapter 5): the picture step as every page names it; **enrich** its verb; **Vision request**, what a person makes when they ask for it now.
- **Narrative rules** and **camera rules**: the fixed instructions of chapter 4.

## 3. What runs when a video is enriched

In the vision lane, one video after another, in this order; the whole of it is what chapter 5 schedules and what the pages call enriching.

### The scan

- ffmpeg reads the Playback copy once at a small width and reports every frame that differs from the one before by more than **Picture change threshold** (a fraction of the picture, 40 percent shipped), and reads the sound once in one-second windows, reporting each second that sits **Loudness rise** (12 dB) above the recording's median level; fewer than five seconds of level, and nothing is reported. Times closer together than **Gap between scanned moments** (3 s) become one. The change points are kept on the Transcript, remade only by Process again, and the audit row "Picture and sound scanned" is written with the counts.
- It runs on the media worker, as a Clip render does: not a Job, no place in the line.

### The stamp

- Many body-worn cameras burn a date, a clock time and the camera's id into the picture, usually along its top edge, in an order that varies by camera. When the record is first made, after the scan, one frame two seconds in is shown at 720 pixels high with fixed instructions to transcribe exactly what is burned in, character for character, never guessing a digit, as JSON with a date, a time, a camera id, and anything else. When the time reads as a clock, a second frame a minute on is read the same way: the clock must have moved on by that minute within a few seconds, and then the stamp is **checked**; a clock that did not move is not a clock, and the time is dropped while the camera id is kept. Kept on the Transcript with the second it was read at; an empty stamp is kept too, so nothing is read twice; a read that fails, or an engine that cannot see, leaves it empty and never stops the record. From Phase 6 chapter 1 the stamp is the Recording's, read as the playback copy lands while Stamp reads early is On, and the record reads it only when none has been read.
- **Told, never reinterpreted.** The Summary, the Chat, and every Digest part are given a clock line after the nature line: the stamp as printed, the second it was read at, and the rule that the recording's zero was that clock less that second, so a time may be given as the time of day; the date is copied as printed and never reordered. Details and the export's processing record show it ("Camera stamp: 06/07/2025, 21:56:19 at [00:00:02], camera BWC2-098679 (checked against a second frame)"). The frames are never kept. The switch is **Camera stamp**.

### The record

- **The cut.** The recording is cut at the change points into spans; a span longer than **Picture record: longest span** (15 s) is cut into equal pieces no longer than that; a span shorter than **Picture record: shortest span** (3 s) is joined to its neighbour. The spans touch, never overlap, and cover the whole recording, at most **Picture record: most descriptions** (600) of them, the longest cut coarser first when there would be more. Until the picture is scanned the count is by the clock alone and the pages say "up to".
- **The clip.** Cut on the worker from the Playback copy with ffmpeg: seek before the input so the cut is exact and its clock starts at zero, the span's length, no sound, the frames thinned to **Description frames a second** (2) and, over a long span, to at most **Picture record: frames per description** (16) in all, as a fraction of a frame a second where that is what it comes to, scaled to **Description frame height** (360, never up), H.264 at the fastest preset, into a temporary file; read into the request as a `data:video/mp4;base64,` URL and deleted in every path.
- **The words.** The system message is the Ground rules, the **Moment** prompt template, the app's format line for the **Description style** (brief shipped: the thing pointed at first, one to three short sentences of concrete nouns and plain verbs; full adds the setting and the seconds), and the record's own line: this clip is one span of a record that covers the whole recording, here is what the clip before it showed, say only what is new (what moved, what came into view or left it, what was handled, shown or pointed at, where the camera went), and a span where nothing changed is one line beginning "Unchanged:". The user message is one text part, the nature line, the clock line, "This clip runs from [hh:mm:ss] to [hh:mm:ss] of the recording. The words spoken in this clip were:" with the rendered lines that start inside the span (the neighbours either side when none does), then one video part. The shipped Moment template forbids naming people, guessing at a substance or an object ("a small bag", not "drugs"), and filling in what was dark, blurred or out of frame.
- **The budget.** The app's estimate of the clip, `ceil(frames / 2)` times the frame's 28-pixel patches, is added to the text's estimate and the answer cap before the window check, so a description is refused before the call when it would not fit. The answer cap is **Description answer cap** (250 tokens); the time limit **Description time limit** (120 s), never doubled: a description never lets the model think, whatever Let the model think says, because the frames are billed against the same budget and a description is perception rather than deduction. Sampling is the assistant's usual. What comes back is stored whole as the Moment's text, with the model, the time and the seconds it took; an empty answer is `llm_bad_output`; an engine that refuses a picture is `llm_no_vision`.
- **Never twice.** A span already described, or covered by a description's span, is skipped. Time order, one lane; a single failed description is left failed and the rest go on; the run stops when the engine goes away.
- **What it costs** is proportional to change: an interview in a room is a handful of descriptions; a foot pursuit is one every longest span. On the office's engine a description has taken about two seconds.
- The switch is **Picture record for summaries** (On shipped). Off, nothing is described, and a summary draws on whatever descriptions exist.

### The Digest

- **What it is.** One text per Transcript: a time-ordered record of what happened, condensed by the model from the Transcript and the descriptions, in numbered lines of the form `[hh:mm:ss]-[hh:mm:ss] (said | seen | both) ...`, one time per line, the span's, and no other; in the third person and the past tense; the exact words kept inside quotation marks only where they carry weight (a statement about the case or the events behind it, a request, an instruction, a warning, a threat, an admission, a denial, a promise, an advisement of rights) with the speaker as the transcript labels them; everything else in the model's own words, agreement, filler, repetition and small talk folded into a phrase; every name, place, date and time of day the words give kept; a person named only as the words name them, a person the camera shows by clothing and position; a camera line only where it adds what the words do not, and a run of "Unchanged:" descriptions no line at all. Under the camera rules throughout.
- **How it is made.** After the record. The Transcript is cut into windows of about **Digest window** tokens (4,000, about ten minutes of talk) on Segment boundaries; each window is sent with the descriptions whose spans fall in it, the nature line, the clock line, the **Digest** prompt template and the camera rules, one call per window, answer capped at **Digest part cap** (1,200); the parts join in order. A window without descriptions is condensed from the words alone. Thinking is never on for a Digest.
- **A part that comes back cut off** at the cap means the window held more than the cap could condense: the window is split in two at its middle line, and so is every later window no part has been made for yet (they were cut to the same budget from the same talk), the later ones held at their starts so the budget does not repack them; the splits are kept on the Transcript, the count the pages show grows by as many, and the plan starts over with the parts already made kept by their signatures. A one-line window still cut is kept and marked cut, and the Admin's fold says which part and how many splits.
- **What is kept.** The parts, each with the window it covers, a signature of the Segments and the descriptions it was made from, the model, when it was made, the seconds it took, and whether it was cut. Content, never logged. Replaced part by part: a part is current while its signature matches; a preparation remakes only the stale parts. The Chat and the Case Chat never make or remake one.
- The switch is **Digests** (On shipped). Off, the summary and the chat work from the transcript and a camera block of the descriptions, under the camera rules.

### The preparation

- **What it does**, in one lane: the scan once per Transcript; the stamp once, while its switch is on; the record, span by span; then the Digest, part by part, while Digests are on and there are descriptions to condense. The count of things left (spans and stale parts) and the count done are kept on the Transcript as it goes, with when it started and ended, and one audit row, **Video prepared** (Video enriched from chapter 5), with the descriptions and the parts made and whether it ended prepared or not. A preparation that fails keeps its reason and is prepared no further until asked again; nothing blocks a summary from being written from the words alone.
- **When it runs**, today: as the Transcript lands, when a Job ends with a Transcript on a video (the probe says it has a picture) and the record is on, queued before the Batch is looked at, its task waiting a minute at a time for the Playback copy, up to two hours. Sound alone, and a video while the record is off, are never queued. Chapter 5 makes this one of three positions.
- **On first use.** A summary or a chat question on a video that is not prepared prepares it first, in that call's lane, the card saying "Preparing the recording (12 of 60), about 18 minutes". When the transcript's own task is at it, the call waits for it, up to three hours, rather than running a second preparation; a summary deleted while it waits is neither written nor brought back, and the preparation stands, since it is the transcript's. Chapter 5 keeps this rule under as-each-transcript-lands only.
- **After a worker stops** (an upgrade restarts the workers), the queue gives the job back and the preparation goes on from the descriptions that stand; the spans the last attempt left queued, running or failed are cut and described afresh.
- **The estimate** is the count of spans times what one description has taken on this engine (the last fifty), plus the stale parts times what one part has taken, with the chapter's guesses until something has been measured.

## 4. The memo and the chat

### The memo

- **The templates.** The **Standard summary**, the **Video summary** and the **Body camera summary** are written as a memo a member of staff hands to an attorney: what the recording is, who took part, what happened, and what was said (and, for a video, seen) that matters, so the reader knows the situation without listening to it. Third person, past tense, plain words. Grouped by subject, never minute by minute, never the recording retold line by line. A time as `[hh:mm:ss]` only where a reader would want to check the recording, after the sentence it supports. The parts, in order: **Summary** (one paragraph a reader in a hurry could stop at); **People** (each person who speaks, is spoken of, or is in view, with how the recording identifies them and where: a name only as the words give it, a role only as the words give it, otherwise the transcript's own label; a person seen only in the picture by clothing, position or what they did, never named; never inferred from what someone does or wears); **What happened** (the substance in a few paragraphs, each on one subject, quoting only where the words themselves matter); for the Body camera summary, **Commands, warnings, and rights** (every command, warning and advisement of rights spoken, quoted exactly with the speaker's label and the time); **Statements that matter** (exact quotes that carry weight, with the speaker's label and the time, and for the person contacted whether it answered a question or was said unprompted); **Names, places, and dates**; **Unclear parts**. No closing section of points for the attorney, at the maintainer's decision: the memo ends at the facts. The other shipped templates (Jail call, Interview, Phone call, Hearing, Dictation, Meeting) keep their shapes.
- **The narrative rules** (`prompts.NARRATIVE_RULES`, fixed) follow the answer format in the system message of a Summary written from a Digest: write one account from both and do not label the source of a sentence; names and roles only as the words give them, and the memo says where, otherwise the transcript's label as it is, a person only the camera shows by clothing, position or what they do; a thing stays what the description saw; never a legal fact such as consent, arrest, search or force as a conclusion; a stretch the camera could not make out reported as not visible; a time copied from the record, given only where a reader would want to check.
- **The camera rules** (`prompts.CAMERA_RULES`, fixed) follow the answer format only when a Summary or a Chat still reads a camera block rather than a Digest (Digests off, or a sound recording with asked descriptions): the two sources kept apart, a fact from the camera written as "the camera shows ..." with its time, neither source winning where they differ, names from the words only, only the listed times, brevity. A sound-only recording pays nothing.
- **What the summary is given.** The nature line, the clock line, the Transcript when it fits the engine's window beside everything else, the Digest under its heading ("The record of this recording ..."), the template, the Length line (under about 250, about 600, up to about 1,500 words) and the Focus; the Digest alone when the Transcript would not fit, so a long recording is never refused. The answer caps are **Summary answer cap** Short, Standard and Detailed (800, 1,600, 3,500 tokens); a cap hit is shown with "The answer was cut short." A Summary remembers how many Digest parts it drew on.
- **The template chosen.** A Recording type wins (a body camera recording in a case gets the Body camera summary); a video of any other type or none gets the Video summary while descriptions reach answers and the template is Enabled; the dialog says why ("This is a video, so the Video summary is chosen."); a summary asked for without a template named gets that same choice, never the office's Default over it.
- **Citations.** A time cited in a summary or a chat answer is a citation that seeks the player; one that falls inside a description's span carries the camera glyph and the description as its hover title.

### The chat

- **What the chat is given.** The transcript (or the Digest alone when the transcript would not fit), the Digest, and the descriptions whose spans hold the times a question names (or the nearest within a minute), up to **Chat: descriptions near a question** (6), under the camera rules. The **Chat** template (editable) answers from the transcript and, when given, the record; asked what was visible at a time it uses the description there or says none was described there; asked for a legal conclusion (consent, arrest, a lawful search) it gives what was said and what the camera showed, with times, then says in one sentence that the conclusion is not something it can answer; legal advice, guilt, credibility, and anything outside both feeds get "I can only answer from this transcript". A question on a video not yet prepared prepares it first, as chapter 3 has it, the waiting line saying so.
- **The Case Chat** reads, after each Transcript, that recording's Digest; a recording still preparing reads as its transcript alone; over the hours ceiling, or when a transcript will not fit, the Digest stands in for it. It never makes or remakes a Digest and says when one was made. The camera rules join its instructions when any Digest is present. Its answer opens by naming the videos it read from the transcript alone (v1.57.0), said as the summary card says it, without what they lack.
- **The lines.** The chat's grounding line reads "Answers come from this transcript and its n described moments, not from any other recording. What the camera showed is a model's description."; the waiting line "Reading the transcript and n moments..." or, while the video is prepared, the preparation's own words.

## 5. Vision: the tick, the night, and what an Admin allows

Written 2026-09-14, after the maintainer had judged the first memos and turned to the cost of the picture: "I'm wondering if we should build in some scheduling, where the vlm part runs overnight ... I think we need a tick that turns on this part of the processing. Someone may just want transcripts completed." The decisions that followed, in the maintainer's words: the option needs a better name, "maybe something like 'enrich with vision'"; the person is told it runs overnight and that an email follows; "only an admin should be able to make this urgent, otherwise everyone will just click it", with a request an Admin can allow; two mails, one when each stage is complete; "intuitive but not overexplanatory" communication of what has occurred and what will occur; a user may change their mind after a case is made ("not yet enriched with vision"); and, on session recordings, that vision runs for recordings in a case, and for session recordings too when the office sets it to run as each transcript lands. The engine is GIDEON's, shared with its own users by day; every description is a request on it; the night is where the bulk of that work belongs, and a person's need for it now is a decision an Admin makes.

### Principles

1. **The picture is a choice, made on the upload page.** A tick, **Enrich with vision**, says whether the picture is described and joined to the words. Its starting position is the office's. An office that wants transcripts alone never sees it ticked, and a batch with it off is finished when the transcripts are, mail and all, as a batch of sound recordings is today.
2. **The office says when.** Vision runs as each transcript lands, or overnight in a window the Admin sets, or only when an Admin allows it. The shipped position is as each transcript lands, which is what chapter 3 runs today; the day a dedicated model arrives, the office turns the schedule off and nothing else changes.
3. **The night needs a case.** A session's recordings are gone at sign-out or after the idle hours, so under the two scheduled positions vision is offered only for a recording in a case. As each transcript lands, a session video is enriched straight away, as today, and dropped with the session if not reached.
4. **Urgency is an Admin's.** Anyone with a case may queue its videos for tonight; only an Admin may start the work by day. Anyone may ask; the Admin allows or declines; the asker is told. Nothing a person can press on their own makes the shared engine work by day, and a summary or a chat question never starts the vision work under a scheduled position.
5. **The transcript is usable at once.** Reading, search, Speakers, clips, exports, Summary and Chat are all there the moment the transcript lands, the summary and the chat written from the transcript alone until the vision is, and Regenerate takes the vision in afterwards.
6. **Two mails, each a few lines.** A case batch's people hear when it is transcribed and again when it is enriched; a session batch's, once. Each message says what has happened and, in one line, what will.
7. **The pages say the state in one family of words.** Enrich with vision, Enriching tonight, Enriching now, Enriched with vision, Not yet enriched with vision. "Prepared" leaves the pages; the field keeps its name.

### The tick

- **On the upload page**, for videos only and while Vision is On: **Enrich with vision**, starting in the position **Enrich with vision starts ticked** gives it. Its caption is one line, worded from the office's schedule: "The picture is described and joined to the words as each transcript lands." / "... tonight between 20:00 and 06:00. You get an email when it is done." / "... when an Admin allows it for this case." A batch is ticked as one; a tick applies to its videos and means nothing for its sound recordings.
- **Under the scheduled positions the tick appears when Into a case is chosen.** With This session only chosen it is not there, and one muted line says why: "Vision runs tonight and needs a case; a session's recordings are gone by then. Put it in a case to enrich it." Under as-each-transcript-lands the tick is offered for both.
- **What the tick does.** As each transcript lands: the video is queued for vision the moment its transcript lands, as chapter 3 has it. Overnight: it is marked **tonight** and waits for the window. Only when asked: the tick is absent; the case page offers the asking.
- **A video uploaded without the tick** is transcribed and finished. Its case page row reads Not yet enriched with vision, with the ways to change that below. Nothing decided at upload is final.

### When vision runs

- **The setting** is **Vision runs**, on the Vision page: **as each transcript lands** (shipped), **overnight**, or **only when asked**.
- **Overnight** runs between **Overnight from** and **Overnight until**, two clock times in the server's time zone (20:00 and 06:00 shipped; the page shows the server's current time beside them so nobody sets a window in the wrong zone). Inside the window the app takes the videos marked tonight, oldest first, one at a time in the vision lane, and enriches each as chapter 3 prepares it. At the window's close a video part-way finishes; the rest keep their place for the next night. A video not reached says so on its row ("Not reached last night; tonight again") and is first in line the night after. The count ahead of a video is on its row.
- **The engine unreachable during the night** puts the video back to tonight rather than failing it; any other failure keeps its reason as chapter 3 has it. How the app should behave across GIDEON's own maintenance nights is parked, at the maintainer's word, for a later chapter.
- **Only when asked** queues nothing by itself. Every video waits as Not yet enriched with vision until an Admin's Enrich now, or a request allowed.
- **Switching the position** changes nothing already enriched or running. Videos marked tonight under overnight are queued at once, oldest first, when the position moves to as-each-transcript-lands, and wait for an Admin when it moves to only-when-asked.

### On the case page

- **The column** is **Vision** (Prepared before), with one of: **Enriched with vision**; **Enriching now, 12 of 60, about 18 minutes**; **Enriching tonight** (with "3 ahead of it" when there are); **Requested now, waiting for an Admin**; **Not yet enriched with vision**; **Not enriched: <reason>** after a failure; nothing for sound alone. The State pill says Preparing only while the vision is running now; a video waiting for tonight is Ready.
- **The line above the list**, while any video is not yet enriched: "3 videos not yet enriched with vision", with the buttons below for all of them at once; the Prepare them now of chapter 6 is withdrawn in favour of these.
- **Enrich tonight** (overnight only), on a row and on the line: marks the video, or all of them, tonight. Anyone with the case may press it; it costs nothing by day. Its confirm is one line: "Enriched tonight, between 20:00 and 06:00; the people on this case get an email when it is done."
- **Ask for it now** (overnight and only-when-asked), on a row and on the line: records a Vision request, with an optional line of why, and the row reads Requested now, waiting for an Admin. Anyone with the case may ask; one open request per case or video at a time. A request is for a case's videos as they stand when it is made, or for one video.
- **Enrich now**, an Admin's only, on a row and on the line: queues the work now, whatever the position. The row reads Enriching now.
- **Declined**: the row reads "Not yet enriched with vision; the request was declined" with the Admin's line if there is one, until the next request or the vision itself. No mail for a decline.
- **Shares.** Anyone the case is shared with sees the state and may press Enrich tonight and Ask for it now; Enrich now stays an Admin's on any case.

### Requests

- **What a request is**: who asked, for which case or video, when, and an optional line of why; its state, waiting, allowed, or declined; who decided and when. A request is a row, never a mail alone, so the Panel can show what is waiting.
- **Where an Admin sees them**: the Vision page of the Panel carries **Requests** at the top: each with the asker, the case or video, how long the work would take (chapter 3's estimate), the line of why, and **Allow** and **Decline** with an optional line back. The Panel's rail shows the count of waiting requests beside Vision. Allow queues the work at once as Enrich now does; Decline records the line.
- **Mail.** When a request is made, every Admin with an email address gets one message, "Vision requested now", with the asker, the case or video, the estimate, the line, and a link to the Panel; the operator's address is the fallback when no Admin has one. When it is allowed, the asker gets one, "Vision allowed", with the estimate and a link to the case; when the work is done, the asker gets the Vision done message below. Each only while Email notifications are on, and the three are templates on the Email page like the others.
- **Audit rows**: Vision requested (the asker), Vision allowed and Vision declined (the Admin), each with the case or recording as its object and no words of why.

### Before the vision, and after

- **Summary and Chat** on a video not yet enriched are written from the transcript, at once, under the two scheduled positions; the summary card says "Written from the transcript", and nothing about what it lacks. Once the video is enriched the same card says "Written from the transcript; Regenerate to include the vision", and Regenerate writes the memo from both, its card saying "Written from the transcript and the vision". A chat answer is dated by nature and needs no line. As each transcript lands, chapter 3's rule stands: the summary and the chat prepare the video first and wait.
- **The case chat** reads what is enriched, and the words of what is not, as chapter 4 has it.
- **Nothing on the recording page** starts the vision work under a scheduled position.

### Mail

- **A case batch, under a scheduled position**, gets two messages. When its transcripts are done: the Batch finished message of Phase 3, its `{prepared}` line now saying "The 4 videos are enriched with vision tonight; you will get a second message when that is done." (or "... when an Admin allows it."). When its ticked videos are all enriched, or could not be: **Vision done**, "Enriched with vision: 4 videos in the batch Grove Loop are ready for summaries and chat." with a line for any that could not be, and a link to the case.
- **A case batch, as each transcript lands**, gets the one message that waits, as chapter 6 has it.
- **A session batch** gets one message with no line about vision.
- **A video enriched by a press or a request** sends the Vision done message to the person who pressed or asked, for what they pressed or asked; a batch's second message goes when the batch's videos are all done, whoever caused it.
- The words are shipped as templates on the Email page: Batch finished (amended), Vision done, Vision requested, Vision allowed, each a Subject and a Body with a fixed set of placeholders, edited like the others.

### What moves with the recording

- **Move to case.** A session recording moved into a case becomes eligible: its row reads Not yet enriched with vision, with the buttons.
- **Process again** makes a new transcript and the vision starts over. A video that was ticked, or enriched, is marked tonight again (or queued at once, by the position) without being asked; its row says so.
- **Retention and the recycle bin.** A case that expires or is deleted takes its waiting vision and its open requests with it; a restored case's videos come back Not yet enriched with vision, to be queued by hand.
- **The sweep during the window.** A video being enriched when its case is deleted stops cleanly at the next span and is not marked failed.

### What changes from the chapters in force

- Chapter 3's "as the Transcript lands" becomes one of three positions, and its prepare-first rule for the summary and the chat holds under that position only. Chapter 6's case page Prepared column becomes Vision with the words above, its Prepare them now becomes Enrich tonight, Ask for it now and Enrich now, and its one waiting mail becomes two under the scheduled positions. Chapter 7's page is where the settings land. Chapter 8's Video prepared row becomes Video enriched for new rows.

### Not in this phase

The engine unreachable across GIDEON's maintenance nights (parked); a per-person or per-case priority in the night's line; a cap on requests; vision for a session recording under a scheduled position; Enrich now for anyone but an Admin.

### Left to the build

The night runner's tick (a periodic task each minute, one video at a time in the vision lane); the request model's shape; the exact caption wordings within the words fixed here; where the count badge sits in the rail; the Vision done mail's placeholders.

## 6. The pages, the exports, and the mail

As they stand at v1.53.2; chapter 5 changes the words on the case page, the batch page and in the mail.

### The recording page

- **The Summary tab.** On a video with the record on and descriptions reaching answers, the button reads **Summarise this video**; otherwise New summary. The dialog carries one line in place of any tick: what preparing will do first, in numbers, while the video is not prepared ("The recording is prepared first: 60 descriptions where the picture changes, none longer than 15 s, then the digest the summary is written from, about 18 minutes."); "The recording is being prepared first: ..." while it is; "Written from the words and the camera's descriptions together; the camera's clock is known." once it is; and, after a failed preparation, that the summary is written from the words alone. The card says "Preparing the recording (12 of 60), about 18 minutes..." then "Condensing the recording (2 of 5)..." then "Reading the transcript..." while the one call runs; its head says "from the words and the camera" when the summary drew on a Digest.
- **The Chat** reads the same words while it waits; its lines are chapter 4's.
- **The transcript** carries nothing of the camera: no camera lines among the rows, no describe button, no tab of moments.
- **Details** shows "Digest: made <when> from the transcript and n descriptions, in m parts", the camera stamp, and, to an Admin and nobody else, **The digest and the descriptions (admins only)**, folded at the top of Details: the Digest's parts as the model wrote them, each with its span, when it was made, by which model, and whether it was cut short; every description with its span and source; whether the video is prepared; how many times the transcript was split; and the versions of the Ground rules, the Moment and the Digest templates that made them. The audit row written when an Admin opens somebody's recording covers the look.

### The case page

- The recordings list has a **Prepared** column (Prepared; Preparing 12 of 60, about 18 minutes; Not prepared; nothing for sound alone), and its State pill reads **Preparing**, not Ready, while the picture is being prepared, since the transcript can be read but the summary and the chat wait. Above the list, while any video is unprepared, "3 videos not yet prepared for summaries and chat, about 2 h 10 min" with **Prepare them now**, which queues them one after another. While any video is being prepared the page refreshes the rows' State and Prepared cells and that line every fifteen seconds by itself. The recordings table scrolls inside its own pane when it is wider than the pane, and never runs under About this case.

### The batch page

- Per recording, after its transcript, "preparing 12 of 60, about 18 minutes" or "prepared", its state reading Transcribed, preparing rather than Done meanwhile; at the top, once transcribed, "Transcribed. Preparing 3 videos for summaries and chat, about 2 h 40 min", polling until they are done. A batch that went into a case carries no sign-out warning, since the case keeps it.

### The exports

- The Transcript's Word and text exports and a Summary's Word export end with the section **What the camera showed**, one line per description with its span, under the legend that it is a model's description of the picture and not the transcript, and the processing record's row "Camera moments" and the stamp's row. The transcript itself carries nothing of the camera. Chapter 5 adds the switch that leaves the section out.

### The mail

- The Batch finished message of Phase 3 waits until none of the Batch's videos is queued or preparing, and its body carries `{prepared}`: "3 videos prepared for summaries and chat in 2 h 10 min; 1 could not be prepared." A video prepared later, on purpose or on first use, sends no mail. Chapter 5 makes this two messages under a schedule.

## 7. The Panel: the Vision page and the templates

### The settings, and where they are

- Today every picture setting sits on the AI assistant page under the names of the diary's chapters (Moments, Moments in answers, the Moment prefix). Chapter 5 gives them **a page of their own**, **Vision**, in the Settings group between AI assistant and Email, grouped: **Vision** (the switch, Vision runs, the window, the tick's starting position); **The descriptions** (frames a second, frame height, brief or full, the answer cap, the time limit, descriptions reach summaries and chat); **The scan** (the picture change threshold, the loudness rise, the gap); **The record** (longest span, shortest span, most descriptions, frames per description); **The digest** (Digests, the window, the part cap); **The chat** (descriptions near a question); **The camera stamp**; **Exports** (Exports carry what the camera showed). Every one keeps its key; the catalogue records each move and rename: Moments becomes **Vision**, Moments in answers becomes **Descriptions reach summaries and chat**, the Moment prefix becomes Description. Three settings whose features are gone are retired with the page: Moment clip length, Look closer frame height, Look closer frames; a stored value is ignored.
- **Requests** sit at the top of the Vision page, as chapter 5 has them, with the count in the rail.
- Appendix B lists every setting with its page and default.

### The templates

- **Prompt templates** on the Templates page: the Ground rules every call starts from, and the **Chat**, **Speaker suggestions**, **Case chat**, **Moment** (the description's instructions) and **Digest** instructions. **Summary templates**: the nine shipped (Standard, Video, and one per shipped Recording type), built in, editable, resettable, never deleted, and the office's own. Each is plain text with Reset to default and a version that rises on every save; changes apply at once, outside the tray; the audit log records the template and its version, never the words.
- **Templates follow the shipped wording.** Every built-in template keeps the hash of the shipped wording it last took (made, reset, or followed). An unedited copy takes a later release's wording by itself the first time it is asked for, its version rising as if reset; an edited copy keeps the office's words, and the Templates page marks it "shipped wording changed" so Reset to default is a choice. The migration that added the hash recognises every wording the app has ever shipped, so a copy stored before then is told unedited by its text alone. An office reads the shipped wording on the page and edits it in its own voice; the fixed rules (the narrative rules, the camera rules, the record's line, the stamp's instructions) are the app's and never edited.

## 8. Audit rows and reason classes

- **AI assistant call** rows, category LLM, one per engine call, with the usual metadata (model, endpoint host, the templates line "ground-rules vN; Moment vN" or "...; Digest vN", token counts, duration, outcome) and the feature: `moment` for a description (with its source), `stamp` for a stamp read, `digest` for a part (with the part's number, the count, whether it was cut, and whether it split its window), `summary`, `chat_turn`, `case_chat` as before. Never a word of a description, a Digest, a stamp, or a question.
- **Picture and sound scanned** (Recordings), with the counts. **Video prepared** (Recordings), with the descriptions and the parts made and the outcome; Video enriched from chapter 5, and Vision queued, Vision requested, Vision allowed, Vision declined.
- **Reason classes**: `llm_no_vision` (an engine that refuses a picture: "This engine cannot look at video"), `media_not_ready` (no Playback copy yet), `media_failed` (a cut that failed), beside the assistant's own (`llm_unreachable`, `llm_timeout`, `llm_too_long`, `llm_bad_output`).
- **The never-logged list** gains a description, the clip and the frames it was made from, a Digest and its parts, the stamp's frames, and a Vision request's line of why.

## 9. Deferred and ruled out

- **A second model for pictures**: ruled out for this phase. The engine the app talks to is a vision model, and a model of the app's own on the shared server's cards would be a ledger change first. When one arrives, chapter 5's schedule is turned off and nothing else changes.
- **Sending a picture anywhere but the engine**: ruled out, as Phase 1's rules have it; nothing leaves the building.
- **Reading text in the picture** (a plate, a label, a document): the camera's stamp is read; the rest is not asked for, the shipped instructions neither ask nor forbid it, and an office edits them.
- **A section in the memo for the attorney's attention**, or on where the words and the picture disagree: ruled out by the maintainer; either could steer the memo. The memo ends at the facts.
- **Inferring a name or a role from the picture or from what someone does**: ruled out; a misidentified officer is the harm the rules exist to prevent.
- **GIDEON's maintenance nights** and an engine unreachable overnight: parked for a later chapter.
- **Asking the picture a question, describing one chosen moment, suggested moments, camera lines among the rows, the summary's tick**: tried and withdrawn; Appendix C says when and why.

## Appendix A. Audit rows in force

| Category | Row | Since |
|---|---|---|
| LLM | AI assistant call, feature `moment` (a description) | v1.38.0 |
| LLM | AI assistant call, feature `digest`; feature `stamp` | v1.51.0 |
| Recordings | Picture and sound scanned | v1.40.0 |
| Recordings | Video prepared (Video enriched from chapter 5) | v1.52.0 |
| Recordings | Vision queued; Vision requested; Vision allowed; Vision declined | v1.54.0 |

Withdrawn: AI assistant call, feature `moment_finder` (v1.51.0); Viewer edits, Moment edited and Moment deleted (v1.52.0).

## Appendix B. Settings in force

Today on the AI assistant page; on the Vision page under the names in the second column from chapter 5. Keys never change.

| Setting today | Name from chapter 5 | Type | Default |
|---|---|---|---|
| Moments | Vision | On or Off | Off |
| Moments in answers | Descriptions reach summaries and chat | On or Off; greyed while Vision is Off | On |
| Moment answer cap | Description answer cap | tokens, 100 to 4,000 | 250 |
| Moment time limit | Description time limit | seconds, 30 to 3,600 | 120 |
| Moment frames a second | Description frames a second | 1 to 4 | 2 |
| Moment frame height | Description frame height | pixels, 180 to 720 | 360 |
| Moment style | Description style | brief or full | brief |
| Picture change threshold | (unchanged) | percent, 10 to 90 | 40 |
| Loudness rise | (unchanged) | dB, 3 to 30 | 12 |
| Gap between scanned moments | (unchanged) | seconds, 1 to 120 | 3 |
| Picture record for summaries | (unchanged) | On or Off | On |
| Picture record: longest span | (unchanged) | seconds, 5 to 600 | 15 |
| Picture record: shortest span | (unchanged) | seconds, 1 to 60 | 3 |
| Picture record: most descriptions | (unchanged) | 5 to 2,000 | 600 |
| Picture record: frames per description | (unchanged) | 4 to 64 | 16 |
| Digests | (unchanged) | On or Off | On |
| Digest window | (unchanged) | tokens, 1,000 to 40,000 | 4,000 |
| Digest part cap | (unchanged) | tokens, 300 to 4,000 | 1,200 |
| Chat: descriptions near a question | (unchanged) | 0 to 30 | 6 |
| Camera stamp | (unchanged) | On or Off | On |
| Summary answer cap, Short; Standard; Detailed (AI assistant page, stays there) | | tokens, 100 to 16,000 | 800; 1,600; 3,500 |
| Vision runs | (new, chapter 5) | as each transcript lands, overnight, only when asked | as each transcript lands |
| Overnight from; Overnight until | (new, chapter 5) | two clock times, server time | 20:00; 06:00 |
| Enrich with vision starts ticked | (new, chapter 5) | On or Off | On |
| Exports carry what the camera showed | (new, chapter 5) | On or Off | On |
| Moment; Digest (prompt templates, Templates page) | | Reset to default, a version | the shipped wording |
| Video summary; Body camera summary; Standard summary (Templates page) | | Summary templates, built in | the memo wording |
| Vision done; Vision requested; Vision allowed (Email page) | (new, chapter 5) | a Subject and a Body each | the chapter 5 wording |

Retired with chapter 5: Moment clip length (10 s), Look closer frame height (720), Look closer frames (3). The catalogue keeps every row's history, limits and consequences.

## Appendix C. What was tried and withdrawn

The diary of these is `docs/spec/history/SPEC-PHASE-4-AS-WRITTEN.md`. In one table, so nobody rebuilds one by accident:

| Feature | Built | Withdrawn | Why |
|---|---|---|---|
| The Moments tab; Describe this moment at the playhead; the row's describe button; camera lines under the rows | v1.38.0 | v1.51.0 (camera lines), v1.52.0 (the rest) | The record covers every second a row could point at; the tab was something nobody would reference; the intent was getting lost in buttons. |
| Cues from a word list | v1.38.0 | v1.40.0 | Flagged ordinary talk; whether a line points at something is context, not a phrase. |
| Find moments from the words (the finder that reads the transcript) and the stored Cues with Describe and Dismiss | v1.40.0 | v1.51.0 | "Too many pointless cues"; the picture decides where to look, not the words. The scan of the picture and sound stayed as the record's cut. |
| Questions about a frame ("is that a gun?") from close frames, with the look-closer settings; Moment to Clip with Camera captions | v1.39.0 | v1.52.0 | Went with the tab; nobody presses anything on the recording page. |
| Describe the whole recording, at intervals, on a press; the summary's tick "Look at the picture first" and the setting "Summaries describe the moments first" | v1.41.0 | v1.51.0 (intervals became the record), v1.52.0 (the press and the tick) | The record is made by the app, once, where the picture changes; a foundation is laid by the app, not by a person. |
| The Video summary as a timeline with "Seen but not said"; per-length caps on camera lines; "Enough moments for a video summary" | v1.43.0 | v1.51.0 and v1.52.0 | The Digest does the choosing; one account, not two columns. |
| The Video summary as one account in time order with an Executive summary | v1.52.0 | v1.53.0 | It read like a screenplay; the memo replaces it. |
| Digest windows of 12,000 tokens with a time on every quotation | v1.51.0 | v1.53.0 | The parts ran out of room at minute four of thirty-seven and nobody was told. |
| Moment edited and Moment deleted (a person's edit of a description) | v1.38.0 | v1.52.0 | Went with the tab; an Admin reads the descriptions under Details instead. |

## Sources

The maintainer's asks and decisions of 2026-09-11 (Moments), 2026-09-12 (the record, the Digest, the stamp, prepared videos, one account), 2026-09-14 (the memo, the digest's economy, the Vision flow); `docs/research/moments-vision-engine.md` (the model card, vLLM's multimodal guide and recipe, the Qwen3-VL report, BodyCam-VQA, and the probes against the office's engine); the Phase 1 AI assistant chapter; the box ledger's shared-engine paragraph and GIDEON's line 17; the diary in `docs/spec/history/SPEC-PHASE-4-AS-WRITTEN.md`, whose amendments list records every change from v1.38.0 to v1.53.2.

## Amendments applied

- 2026-09-14: the document rewritten whole as what stands, from the maintainer's reading of the diary ("I see a lot of mentions related to moments which I thought we went away from"); the diary kept under `docs/spec/history/`. Chapter 5 (Vision) carried over from the diary's chapter 8, proposed the same day. Later amendments are recorded here, one line each, as before.
- Chapter 5 built as v1.54.0, the same day, with these decisions left to the build: the night's tick is a periodic task each minute on the default queue, one video at a time, the oldest transcript first; the videos still waiting are marked not reached in the three minutes after the window closes; a request is one open at a time per case or video; the Vision requested message goes to every Admin with an address and to the operator when none has one; the summary's card carries `written_from`; the retired settings' values live on as constants for the code paths that still read them (an asked moment's span of 10 s, a question's 3 frames at 720 pixels, the stamp's 720 pixels).
- 2026-09-17 (Phase 6 chapter 1, written for the build): the camera stamp moves to the Recording and is read as the playback copy lands while the Incidents page's Stamp reads early is On; the record reads it only when none has been read. The words the assistant is given do not change.
- 2026-09-16 (v1.57.0): the Case Chat's answer opens with the videos read from the transcript alone; a transcript's exports carry the camera section only under a switch of their own (Off), so a transcript export is the words unless the office asks otherwise; the existing switch keeps the summary's export and a clip's captions.
