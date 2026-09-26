# Gideon Transcribe

Local transcription, translation-to-English, and speaker diarization for the office, with LLM help, running entirely on one AI server the office runs itself. This glossary is the vocabulary for the app, its tickets, and its documents.

## Language

### Media and output

**Recording**:
An uploaded audio or video file. Its uploaded bytes are never changed; everything the app plays or listens to is made from them.
_Avoid_: file, upload, media (as a noun for the item)

**ASR audio**:
The prepared sound track, made from a Recording, that the WhisperX service listens to. Preprocessed and reduced to one channel; never heard by users.
_Avoid_: normalised audio, wav (implementation terms)

**Playback copy**:
The version of a Recording the browser plays and scrubs. Every Recording gets one; the uploaded bytes are never served to the player.

**Preprocessing profile**:
The named set of audio clean-up steps applied when making the ASR audio. Chosen by an Admin as a default; Phase 1 ships Standard and Off.

**Two-channel call**:
A Recording the app has detected as a phone call with one party per channel. Each channel is a Side, and the Sides are the Speakers unless the user asks for Diarization.

**Side**:
One distinct sound source of a Recording, transcribed on its own: a channel of a Two-channel call, or a separate audio track. Most Recordings have one Side. Speakers are labelled by Side.
_Avoid_: channel, track (those are the technical facts a Side is made from)

**Speaker-count hint**:
The user's guidance to Diarization: let the app decide, exactly a number, or between a minimum and a maximum.

**Provenance**:
The record kept for every Recording of where it came from and how it was processed: the original name, hash, uploader, technical facts, and every setting and model used. Shown in the Details panel and on every export.

**Clip**:
A user-chosen span of a Recording, marked by a start and an end, with its own title and note, rendered as a playable file for use outside the app (hearings and the like). It carries every Side of the Recording and can be made as soon as the Recording plays, before its Transcript exists. Its transcript excerpt and caption file are built from the Transcript at download time; captions can also be burned into the picture, and only those can go out of date.
_Avoid_: excerpt (that is the text that goes with a Clip), cut, segment (that is a Transcript unit)

**Clips page**:
"Clips" in the Rail (the page's heading reads Clips since v1.89.0): one table of every Clip the person saved, under a heading row for each place it lives, with Download all. Before v1.30.0 it listed the Workspace's Clips only. See My clips.
_Avoid_: clip library

**Adjust**:
Changing a saved Clip's start, end, or options, which renders its file again and clears its downloaded mark. Changing only the title or note is a Rename and renders nothing.
_Avoid_: edit (that is a Correction), re-cut

**Transcript**:
The text produced from a Recording: ordered Segments with timestamps and Speaker labels.
_Avoid_: transcription (that is the process), output

**Segment**:
One timed span of a Transcript attributed to one Speaker.

**Speaker**:
A voice label in one Transcript, optionally given a name. Diarization creates Speakers, and the Sides of a Two-channel call are Speakers too. Inside a Case, Speakers given the same name are one Person.

**Diarizer**:
The model that tells a Recording's voices apart: Nemotron 3 Diarization (the default from v1.80.0, up to eight voices, no token) or pyannote community-1 (the diarizer until then, kept reachable). One Panel setting on the Transcription defaults page names it; a Recording's Details tab says which split it. Phase 5 chapter 4.
_Avoid_: engine (the AI assistant's word), model alone, "speaker separation model"

**Diarization**:
The step that separates a Recording into Speakers. Always a user choice per Recording, with a speaker-count hint (pyannote's alone; greyed under the Nemotron Diarizer). The pages call the choice "Diarize" and carry a short warning that automatic speaker separation is sometimes wrong. On a Two-channel call it runs per Side with the app deciding the count; a Side with one Speaker is labelled by its Side alone.
_Avoid_: separate speakers (in a label), speaker identification (that is naming)

**Spoken language**:
The language of the speech in a Recording, chosen by the user at upload or detected by the WhisperX service. A Transcript is in the Spoken language unless Translation applies.
_Avoid_: source language, detected language (detection is one way the Spoken language becomes known)

**Translation**:
Producing an English Transcript from speech in another language, either because the user chose "Translate to English" or because the Recording holds more than one language. Always to English; the original-language text is not kept. A translated Transcript is marked in the viewer and carries the Translation notice on every export.

**Translation notice**:
The admin-set wording printed on every export of a translated Transcript, saying the text is a machine translation and not a certified one.

**Transcription notice**:
The admin-set wording printed on every export of a Transcript that was not translated, saying the text is a machine transcription with Corrections marked and not a certified transcript. An export carries one notice, never both.

**Export**:
A file a user takes out of the app from a Transcript, Summary, or Chat: a Word document, a plain-text file, or Captions. Exports and Clip downloads are the only ways anything leaves a Workspace.
_Avoid_: download (that is the act; the Batch download and Download everything are zips of exports)

**Processing record**:
The Provenance record as printed on the last pages of a Word Transcript export, with the Segment and Correction counts and who exported it when.

**Captions**:
The SRT file exported from a Transcript, one cue per Segment, carrying no notice. A Clip's Captions are timed from the Clip's start, and a Clip can burn them into the picture.

**Download everything**:
The zip offered at sign-out holding, for every Done Recording, its Word Transcript with its Summaries and Chats inside plus its plain-text file, and every Ready Clip with its excerpt.

**Vocabulary**:
Names and terms supplied to improve recognition for a Recording or Batch.
_Avoid_: hotwords, initial prompt (implementation terms)

**Office Vocabulary**:
Names and terms an Admin keeps for the whole office, sent with every Run ahead of the Batch's own Vocabulary.

**Follow mode**:
The viewer behaviour that keeps the current Segment in view while the Recording plays. On by default; pauses while the user scrolls the Transcript by hand and resumes on request.

**Correction**:
A user edit of a Segment's text in the viewer. Marked on the Segment and recorded in the audit log.

**Timeline**:
The waveform strip in the viewer, used to seek and to mark a Clip by dragging; split into one lane per Side on a Two-channel call. The Incident page's strip of lanes is not the Timeline, and a Chronology is a list of Events (Phase 6).

**Stage**:
The viewer's left-hand column on a window 1280 pixels or wider: the picture, the transport under it, the line being spoken, and Describe this moment, resizable by its right edge. On a narrower window the picture sits beside the title and the transport under it; a sound recording has no stage at any width. Avoid: Bench (the right-hand column of v1.4.0 to v1.45.1), player pane, dock (that is the laptop's arrangement of the same things).

**Work area**:
The viewer's tabbed area beside the stage: Transcript, Clips, Summary, Chat, Moments and Details, one at a time at the full width of the area. Avoid: sheet, Bench, panel column, drawer.

**Marking strip**:
The line under the Timeline that shows a marked Clip range with its length, Preview, Save clip and clear. Marking a Clip by any route fills it and never changes the tab; Save clip opens the Clips tab.

**Speakers page**:
A page of its own for one Recording, opened by Manage speakers on the Speakers strip and left by Done, whose one job is saying who each Speaker is: the Recording playing at the top right, a card per Speaker down the left with its Samples and its name box (the Case's People first), a Lane per Speaker under the player, and the Transcript's Ledger under the Lanes filtered to the Speaker in hand. Rename, merge, giving one line to a Speaker, Suggest names and Undo are the viewer's own. Avoid: speaker manager, tagging window, suite (the maintainer's word for the ask, not the page's name).

**Speakers window**:
The Speakers page opened in a window of its own by Open in a window (from v1.50.0; before that, a window of its own opened by Tag speakers, with the player, the line being spoken and a roster with number keys). It plays the Recording; whichever of the recording page and the window played last has the sound, and the other follows. Any tab of the work area opens in a window of its own the same way, kept in step with the page. Avoid: pop-up, dialog, floating panel.

**Lane**:
One Speaker's row on the Speakers page's timeline: the Speaker's name at the left and, across the width of the Recording, a block for every stretch that Speaker talks. The Lanes are the page's scrub bar: a press seeks there, and dragging one Lane's head onto another merges the two Speakers. Avoid: track, swimlane, timeline row.

**Sample**:
One of up to three lines of a Speaker that the Speakers page offers to play to hear the voice, chosen from the first, middle and last thirds of that Speaker's lines and a few seconds long. Playing a Sample plays the Recording from the line's start and pauses at its end. Avoid: snippet, excerpt (that is a Clip's), clip.

**Swap**:
Exchanging two Speakers for a stretch of a Recording on the Speakers page, from one time to another: every line of the first in the stretch becomes the second's and the other way round, in one press, remembered for Undo. The shape a diarizer's error takes when it confuses two voices for a passage, and what the Suggested corrections offer when a run of them lies between the same two Speakers. Since v1.56.0. Avoid: flip, exchange, relabel.

**Voice print**:
Phase 5 chapter 2, not built: one vector per Person in a Case, made from a Speaker's voice when the Speaker is named, that lets the app say an unnamed Speaker in another Recording of the Case "sounds like" that Person. Content, never logged or exported, deleted with the Person. Until the chapter is in force the app keeps no such thing. Avoid: embedding (on a page; the service's word), voice signature, biometric.

**Boost**:
The viewer's volume control above 100%, for quiet Recordings such as jail calls.

**Live recording**:
A Recording made on the Record page in the browser, on an office computer, rather than uploaded as a file: the microphone and, when asked, what the computer plays (the far side of a Zoom, Teams, or jail call), joining a Case as it starts and transcribed at the front of the queue when it ends. Once it ends it is a Recording like any other, marked as recorded live in its Provenance. Phase 3.
_Avoid_: live transcription (nothing is transcribed while it records: the finished Transcript follows), streaming, session recording

**Record page**:
The page a Live recording is made on: the Case and Recording type it will join, what to record, the language, the people expected, and Record, Pause, and Stop. Phase 3.
_Avoid_: recorder, capture page

**Mark**:
A moment a person noted while recording, by one key, with an optional word. Shown in the viewer as a list of times, each a Citation; a Mark can be made a Clip. Phase 3.
_Avoid_: bookmark, flag, tag

**Dictation**:
A Recording made on the Dictate page, kept past sign-out, the person's alone until sent, in no Case unless they add it to one, whose product is a Memo. Its Recording type is Dictation, and the office's Retention period applies to it on its own. Phase 3.
_Avoid_: voice note, voice memo

**Stretch**:
Five minutes of a Live recording, transcribed while the next five record (Phase 3, step five): cut from the pieces already on the server, prepared on its own, and sent as a Run of the recording's one open Job; a pause closes one, and the last is sent at Stop. Nothing is shown before the Transcript is whole.
_Avoid_: chunk, segment (taken), partial transcript

**Interpreter**:
The door on the New recording page beside the three styles, and the feature as a whole: a Session between a Visitor who speaks another language and Staff, heard by Whisper, translated by the office's engine, and (when built) spoken by a Voice on the server, Turn by Turn, kept as a Recording with both languages. Never a substitute for a certified interpreter. Phase 3 chapter 3; built text-only in v1.33.0 to v1.34.0 and withdrawn in v1.35.0 at the maintainer's decision (deferred); the words stay for the chapter.
_Avoid_: translator, bot

**Session**:
One use of the Interpreter, from Start to Stop: a Live recording of that style. Phase 3.
_Avoid_: conversation (say Session for the recording, conversation for what the people had)

**Turn**:
One stretch of speech by one Side in a Session, ended by the pause, with its language, what the app heard, and its translation; a Session's Segments are its Turns. Phase 3.
_Avoid_: utterance, message

**Readback**:
A person's own Turn shown back to them in their own language, as heard, beside its translation, so a misheard word is seen and said again. Phase 3.
_Avoid_: echo, confirmation

**Fast lane**:
A second, smaller transcription service beside the batch one, optional at install, for what must come back in about a second: a Turn, or a piece of a Live recording transcribed during the recording. Phase 3.
_Avoid_: realtime worker, streaming service

**Voice**:
A text-to-speech voice installed on the server for one language, fetched at install and never at run time; a language with no Voice is text-only. Phase 3.
_Avoid_: TTS model (in pages), speaker (taken)

**Quick phrase**:
A ready-made line on the Staff side of a Session, translated once and shown or spoken with one press. Phase 3.
_Avoid_: canned response, macro

**My clips**:
The Clips page in the Rail: one table of every Clip the person saved, under a heading row for each place it lives (a Case, Recorded here, This session), the place touched last on top. A Clip in a Case is here and on the Case's Clips tab both. Before v1.30.0 the page listed the Workspace's Clips only.
_Avoid_: Your clips, clip library

**Home**:
Where sign-in and the brand land, from v1.86.0 (Phase 8 chapter 13): the greeting, the notices, and then only the sections with something in them, in a fixed order: Ready to download, Needs you (the Cases with a warning pill), Running now, This session (the Recordings not in a Case, with the keep-or-lose line said once), Recent cases (every Case, with its Dashboard line's pills). Nothing on it is only a door; the Rail's two actions are the doors.
_Avoid_: Start page (v1.29.0 to v1.85.2), dashboard, landing page, menu

**Rail**:
The column down the left of every page, from v1.86.0: the two actions at its top, Upload files and Record now (with the Record now setting on, or inside a Case with Live recording on), each carrying the Case the person is inside; then the places, each with its icon, its name and one line saying what it is for (Home "What is running, and what needs you"; Cases "Kept for a matter, after sign-out"; My recordings "This session only, then gone"; Clips "Pieces cut for a hearing"; Panel "Settings, status, people"; Help "The guide, at this page"). The place the person is on is lit; an action is not a place and lights nothing. It folds to icons on a narrow window and on the incident page. The top bar keeps the brand, the person's name, Sign out and the theme.
_Avoid_: sidebar, menu, nav, top bar (for the places)

**Ready to download**:
Home's first section, when a Batch of this session has finished with at least one Transcript: the batch, how many transcripts are ready, Download transcripts, Open the batch and Done with these. It stays until Done with these; the Rail's Home item counts such batches. The same download is on My recordings, on the batch's group. Phase 8 chapter 13.
_Avoid_: inbox, notifications, downloads page

**Start page**:
Where sign-in landed from v1.29.0 to v1.85.2: one question, what do you want to do, and three doors, Upload files, Record now, Cases. Superseded by Home; /start follows to Home.
_Avoid_: the old word for Home

**Recorded here**:
The first part of the My recordings page, with the Record now setting on: everything the person recorded from the New recording page and kept on its own, newest first, each with Play, Open, the memo or summary, Send to, Add to a case, Delete; and under them what colleagues have sent, "Sent to you". Kept for as long as the office keeps a case. Phase 3. It was a tab of its own, called Record, and before that Dictations, each for one release.
_Avoid_: Record tab, Dictations page (the earlier names), recorder

**Record now**:
The Rail's second action, the door to the New recording page (the Start page's door before v1.86.0), and the name of the Admin setting (key `dictation`) that turns it and Recorded here on. Phase 3.
_Avoid_: Record tab, Dictation setting

**Memo**:
The document a Dictation becomes: a Summary written by the shipped Dictation memo template, which writes the dictated words out as a memo rather than summarising a conversation. Phase 3.
_Avoid_: transcript (that is the words as spoken), note

**Send to**:
Handing one Dictation to a colleague: they get it under "Sent to you" on their Dictations page, they are mailed that it is there, and, when the Dictation by email setting is On, the Memo rides with the mail as a Word file. Taking it back removes it from their page. Phase 3.
_Avoid_: forward, share (that is a Case's), email (the mail is one part of it)

### Processing

**Batch**:
The set of Recordings a user submits together, with shared settings and per-Recording overrides. Every Job belongs to one Batch, and a user has one unfinished Batch at a time. A finished Batch's download is offered on Home (Ready to download) and on My recordings until Done with these, never only on the Batch page (Phase 8 chapter 13).

**Job**:
One Recording's pass through the Queue, holding one Run per Side. A Job is Queued, Running, Done, Failed, or Cancelled.

**Queue**:
The single office-wide line of Jobs, one at a time and first come first served, with no priority for anyone. It is the WhisperX service's line seen through the app.

**Step**:
The plain-word stage a Running Job shows: loading the model, transcribing, aligning words, separating speakers, finishing, merging sides.
_Avoid_: stage, status (a Step is what the user reads)

**Estimated wait**:
The app's figure for how long until a Job starts, worked out from the audio ahead of it and the WhisperX service's measured speed.

**Retry**:
Submitting a Failed Job again with the same settings. Media work that already succeeded is not repeated.

**Process again**:
Submitting a Done Recording again with different settings. The new Transcript replaces the old one; the old one stays readable but locked until then.
_Avoid_: reprocess, re-transcribe

**Batch download**:
The zip a user takes from a Batch page, or from the sign-out dialog as "Download all transcripts": one plain-text Transcript per Done Recording, each carrying its notice.

**Batch page**:
What the Upload page shows from Submit until every Recording in the Batch has ended: each Recording's state and Step, its place in line and Estimated wait, the count strip, the "everything done by about" line, Cancel, Retry, and the Batch download. There is no list of past Batches.
_Avoid_: queue page, progress page, upload status

**Recordings page**:
"My recordings" in the Rail: everything that is the person's, in two parts, Recorded here (with the Record now setting on) and Uploaded this session, the Recordings they uploaded that are in no Case (the Workspace; from v1.86.1, before which every upload of theirs was listed, the cased ones included), grouped by Batch, each group with its Download transcripts and Open the batch (from v1.86.0), and each row with Open, Process again, Details, and Delete, kept until sign-out unless moved to a Case, and then listed with the Case. Sign-in landed here in Phase 1, on the Start page from v1.29.0, and on Home from v1.86.0. The pages say "my recordings" or "your recordings", never Workspace.
_Avoid_: dashboard, Workspace page, Recordings tab (it is My recordings)

**WhisperX service**:
The independent transcription engine that runs one job at a time for the whole office, consumed by the app and, later, by other Consumers.

**Run**:
One Side's pass through the WhisperX service. A Job has one Run per Side, and the app merges the Runs' Segments into the one Transcript by time.
_Avoid_: request, service job, task (that is the transcribe-or-translate choice)

**Consumer**:
An application that holds a token for the WhisperX service and submits Runs to it. Gideon Transcribe is the first Consumer.

### Holding and keeping

**Login session**:
One authenticated sign-in of a user, ended by logout, idle timeout, or a newer sign-in by the same user. A user has one at a time.

**Workspace**:
A user's holding area for what is not in a Case. Everything in it is discarded when the user's Login session ends, once any running Batch has finished and a grace period has passed; nothing in a Workspace outlives the session. What a user wants to keep, they export before signing out.
_Avoid_: session (that is the login), scratch (that is the disk location)

**Discard**:
The removal of everything in a Workspace once its user's Login session has ended and no Job is running: Recordings, Transcripts, Summaries, Chats, and Clips alike.
_Avoid_: cleanup, purge, sweep (the sweep is the mechanism that carries it out)

**Clear**:
A user removing Recordings from their own Workspace while still signed in, either one Batch of them ("Done with these") or all of them ("Clear my recordings"). Same removal as a Discard and equally final, but asked for by the user rather than done by the app when a Login session ends, and it never touches a Recording in a Case. It exists because an office running batches works in a loop of upload, download, clear, upload again, and every Recording counts against the user's quota until it goes.
_Avoid_: clean up, reset, empty, start over

**Folder management**:
The admin toggle that enables Cases. Off: Workspaces only; every Case is hidden from everyone and kept, its Retention policy clock paused, nothing deleted, and the Rail's Cases and Home's case sections are absent. On: users may keep Recordings in Cases, and everything Off hid comes back as it was.

**Case**:
A named page of retained Recordings for one legal matter, owned by one user, kept under the App data folder, shareable with named colleagues, and subject to the Retention policy. Exists only when Folder management is on. Nothing but the name is typed; users never see the folder behind it, and nothing inside a shared Case is private to one person.
_Avoid_: folder, project, matter (in the UI)

**Add to case**:
The Upload page choice that puts a Recording into an existing Case from the start. A Recording added this way is never in the Workspace.

**Move to case**:
Taking a Done Recording out of the Workspace and into a Case, whole: its Transcript, Summaries, Chats, Clips, and Provenance go with it. Nothing ever moves back; a person takes a Recording out of a Case only by Delete, and the Retention policy takes a Case whole to the Recycle bin.
_Avoid_: save to case, copy

**Description**:
An optional free-text note on a Recording in a Case, asked for when it is moved in and editable afterwards in Details and on the Case page. Never printed in the audit log, never sent in a Notification.
_Avoid_: notes, comment, summary (that is the LLM's)

**Recording type**:
An optional label for a Recording (Body camera, Jail call, Interview, and the like), picked at upload from a list an Admin keeps and changeable later.
_Avoid_: source type, category

**Dashboard line**:
The line of pills under a case's name on the case page, one for everything in the case that has a state (transcribing, preparing, tonight's vision, an incident not synced, events to check, proposals waiting, a memo with newer events, clips rendering or failed, whom it is shared with, the retention warning), each a link to where it is dealt with; absent when nothing is pending. Phase 7 chapter 3. Its pills are drawn on Home's case rows too, and a case with a pill in the warning tone is under Needs you (Phase 8 chapter 13).
_Avoid_: dashboard (the line has no heading), status bar, alerts

**Find**:
The box on the incident page's work panel that searches the synced cameras' words, the Chronology's events and the memo, and whose hits are moments: pressing one seeks every camera there and brings the camera it was heard on to the front with the sound. Never logged. Phase 7 chapter 3. The case page's own box is Search.
_Avoid_: search (on the incident page), query, results

**Work panel**:
The incident page's panel beside the wall: its tabs (Chronology, Memo, Cameras, Details), always there, and the layers that open over a tab for a job in hand. Phase 8 chapter 1.
_Avoid_: sidebar, pane (that is the case page's)

**Player bar**:
The controls drawn on the focus camera's picture when the pointer is over it: a scrub bar over the Incident's span, play, back and forward, the time, which camera is heard, the speed, and Fill the window. Each does what the transport's control of the same name does. Phase 8 chapter 5.
_Avoid_: scrubber, seek bar, overlay controls, HUD

**Said band**:
The block under the filmstrip in the Focus layout that shows the focus camera's Transcript following the clock, the line being said lit, with + event and Clip from here on the lit line. Phase 8 chapter 5.
_Avoid_: live captions, subtitles, ticker, transcript panel (that is the recording page's)

**Clip button**:
The Clip on the transport of the incident page that marks a Clip's start at this moment and, as End the clip here, its end on the second press; the clip box then opens filled in. Phase 8 chapter 5.
_Avoid_: in point, out point, record, mark in, mark out

**Clip track**:
The hatched band under the strip's ruler on the incident page that says in words it takes a drag to make a Clip, and draws the span as it is dragged. Phase 8 chapter 5.
_Avoid_: drop zone, selection bar, range selector

**Clips lane**:
The strip's lane of the Clips already made from this Incident, one block over each span, there only when the Incident has a Clip. Phase 8 chapter 5.
_Avoid_: clip markers, bookmarks

**Handle**:
The grip between the wall and the Work panel on the incident page, and on the left edge of Gideon's panel, that a person drags to size the panel, remembered in that person's browser; a double-press puts the usual width back. Phase 8 chapters 5 and 6.
_Avoid_: splitter, gutter, divider, sash, resizer

**Paragraph card**:
The card that opens in place from any citation to a Paragraph (a Gideon answer, a Comparison row, an Event that rests on a Paragraph, the memo, a Search hit, a Note), showing the Page's picture with the Paragraph lit, the words before and after, and Open the document one press further; one at a time, Escape closes it, and the page under it never moves. Phase 8 chapter 6.
_Avoid_: popup, popover, modal, tooltip, lightbox, preview (the chat's word for its moment player)

**Event card**:
The card that opens from any mark of an Event (the strip's Events lane, the focus camera's scrub bar, the viewer's timeline mark of a noted line) and from the line of a Chronology row. Hovering a mark shows it light: the time, the line and where it came from. A press opens it whole: the detail, the cameras it is seen on, what it rests on, the note with its writer, the why, the clip mark, and the actions (Edit, a note, Clip this event, Remove, Go to the row; Accept and Dismiss on a proposal; Open the line on a note event). One at a time; Close, Escape or a press outside closes it, and the wall, the strip and the rows never move for it. Phase 8 chapter 11.
_Avoid_: tooltip, popup, popover, pop-out, hover card, flyout, modal, dialog, marker (for the mark), label (the lane's old words beside a mark), pinned (that is a camera kept in the Sitting)

**Timeline view**:
The Chronology tab's second shape, a toggle beside Rows kept by the browser per person: a band of the cameras' spans on the Incident clock, then the Events down the page in time order grouped by Spell, each a numbered mark in its camera's colour, its time, its line and its source pill. Pressing a time plays every camera there and brings that camera to the front; pressing the line opens the Event card, which holds every action. Phase 8 chapter 12.
_Avoid_: Gantt, chart, graph, list view

**Spell**:
A run of Events on a Chronology with no gap of ten minutes or more between neighbours, headed by its span on the Timeline view and in the Chronology figure, and named in the spreadsheet's last column. One event alone is a Spell headed by its time. Phase 8 chapter 12.
_Avoid_: phase, segment, section, cluster

**Chronology figure**:
The Timeline view drawn on the Word export's page in the light palette: the band, the Spells, the numbered entries with the note, the why and the source under each in the small type, then the legends. It replaces the strip picture, which is gone. Phase 8 chapter 12.
_Avoid_: strip picture, diagram, chart

**Admin pill**:
The small mark beside a page's title that says an Admin is viewing another person's Case, Workspace or Recording, with the audit sentence one hover or press behind it. It replaces the band across the page. Phase 8 chapter 7.
_Avoid_: banner (the band it replaces), badge, tag, chip

**Gone page**:
The app's one page, in its own frame, for an address that has nothing behind it: the reasons it might be gone and the way back. It never says whether a thing exists that the person may not see. Phase 8 chapter 7.
_Avoid_: 404 page (on a page), error page, not found

**Detail**:
The part of an Event's text after its line: the text past its first line break, or past its first sentence when the text runs long. Shown on the muted line under the Event, edited with the line in one box, printed under it in the exports. The line and the detail are one field read two ways. Phase 8 chapter 8.
_Avoid_: summary, snippet, truncation, description (a Digest's word)

**Neighbour**:
The Speaker whose turns a small Speaker's lines sit inside: the one whose line ends just before, or begins just after, more than half of the small Speaker's lines. The merge hint on the Speakers page names the Neighbour and nobody else. Phase 8 chapter 8.
_Avoid_: cluster, match, similarity, confidence

**Sitting**:
Everything the AI assistant reads of an Incident in one call before it writes the memo, checks the report or answers a question, on the incident page or, from v1.87.0, in the Case Chat: what was said on every synced camera and, as room allows, what each showed. The bar on the incident page's Cameras tab says how full the Sitting is, in hours of camera, against what the engine can hold at once. When it is full, the longest cameras are read by their words alone, and every output written that way says so. Phase 8 chapter 9.
_Avoid_: context, context window, tokens, prompt, budget (on a page a person reads; the Panel keeps tokens)

**Pinned**:
A camera the person has asked to keep in the Sitting with what it showed, whatever else is added; the next longest camera is read by words alone instead. Set with Always read what it showed on the Cameras tab. Phase 8 chapter 9.
_Avoid_: priority, locked, favourite

**Layer**:
One job opened over a tab of the work panel (Proposed events, Sync, an event, a clip, Find), with the same head on every one: Back with the tab's name, the layer's name, its one main button. Back or Escape returns exactly to the tab, its scroll and the row marked. The wall and the strip never move for a layer. Phase 8 chapter 1.
_Avoid_: modal, dialog (a layer is not one), popup, pop-out, sheet (Phase 6's word for what a layer replaced)

**Incident**:
A named group of a Case's videos that ran at the same time, laid on one clock so they play in step on the Incident page. Offered by the app when the videos' clocks overlap, or made by hand with New incident; a video is in at most one. Lives inside one Case and nowhere else, counts as its activity, and goes with it. Phase 6.
_Avoid_: event (that is one entry on a Chronology), scene, sync set, group, session

**Incident clock**:
The time of day, with its date, that an Incident's cameras run on, taken from the clocks burned into their pictures; every camera's place is a number of seconds on it. An Incident with no camera clock counts from its first camera and the page says so. Phase 6.
_Avoid_: timeline, offset, master clock

**Placed**:
How a camera came to sit where it does on the Incident clock, shown as a pill beside it everywhere: From its clock, checked; From its clock, unchecked; Matched by sound; From its file, unchecked; Synced by hand; or Not synced yet (the app's guess, from v1.60.0: the file's time, else the Incident's start, until Sync on the camera fixes it). Every camera in an Incident is on the Wall; the page's control for a camera's place is **Sync**. Phase 6.
_Avoid_: aligned, calibrated, offset

**Wall**:
The Incident page's grid of cameras playing in step, up to the number the office sets (six shipped), one of them with the sound; the rest of the Incident's cameras wait as parked lanes in the strip to swap in (parked tiles until chapter 4). Phase 6.
_Avoid_: multiview, grid (as a name for the whole), mosaic, split screen

**Layout**:
The Incident page's arrangement, chosen from the Layout menu in the transport and remembered in the person's browser: **Focus** (one camera large, the focus camera, with the others in a filmstrip under it, any of them one press from the front), **Side by side** (the cameras in a grid beside the work panel, the strip at the bottom), or **Grid** at 2, 3 or 4 across (the cameras in that many columns beside the work panel; until v1.74.1 a Grid put the panel under the strip). The office's Incident layout setting is what a new person starts with. Phase 6 chapter 4, amended by Phase 8 chapter 5.
_Avoid_: view mode, multiview, mosaic, split screen

**Chronology**:
An Incident's list of Events, in time order, the office's Notes on the synced cameras' lines among them, drawn as the last lane of the Incident page's strip and exported as a Word table with the strip as a picture, or as a spreadsheet. Phase 6 chapter 2.
_Avoid_: timeline (that is the viewer's waveform strip), log, history

**Event**:
One entry on a Chronology: a time of day on the Incident clock, a line of text, its source (a person, the words of one camera, or the camera line of one camera), and the cameras that show it. Added by a person at the moment being watched, from a line under a camera, or from a chat's citation; or proposed by the assistant from a camera's Digest (source assistant, chapter 3), or found by the app's own search for a Watch phrase (source watch phrase, Phase 7 chapter 2); a proposal stays Proposed under the Chronology and joins it only when a person accepts it. Or the office's Note on a line of a synced camera's transcript, which is an Event on that Incident's Chronology at the line's moment by itself, with the source **note** and the writer's name on its pill ("Note by D. Meehan, BWC2-1"): the same words as the note, changed or removed from either place, gone from the Chronology when the camera leaves; Phase 8 chapter 11 calls that row a note event. A press on an Event's mark, its time or its card seeks every camera and brings the camera it came from to the front (Phase 8 chapter 12). Phase 6 chapter 2.
_Avoid_: mark (that is a live recording's), moment (that is a description), bookmark, flag; shadow, mirror, copy, link (for a note event)

**Watch phrase**:
A word or phrase the office always wants an Event for, listed one per line in the Watch phrases setting. On every Propose events run the app itself searches each synced camera's transcript, and its Digest's picture lines, for every watch phrase, whole words and any case, before the engine is asked, and proposes an Event at every line that carries one, with the source **watch phrase** and the line it rests on. A promise the engine's judgement cannot break. Phase 7 chapter 2.
_Avoid_: keyword, trigger, alert, hotword, rule

**Incident memo**:
The memo the AI assistant writes across every synced camera of an Incident, on the Incident page's Memo tab: written in two passes (ADR 0016, v1.91.0), the Facts sheet drawn from the incident record (the cameras' Digests merged onto the Incident clock, made by the app for the call and never stored) and the Chronology's Events, then the memo written from the sheet alone; each sentence that rests on an Event carrying its number, every time the time of day and a citation that plays every camera. One per Incident, replaced by Regenerate (both passes) or Rewrite from the sheet (the second alone), marked stale when the Events or the cameras change, exported to Word with the Facts sheet and the Chronology as its last pages. Its instructions are the Memo facts sheet and Incident memo templates. Phase 6 chapter 3.
_Avoid_: report, narrative, incident summary (a Summary is one recording's), timeline (the Timeline view and the Timeline report are other things)

**Facts sheet**:
What the Incident memo is written from (ADR 0016, v1.91.0): the data the AI assistant draws from the incident record and the Chronology in the memo's first pass, under a schema, and the app checks: the people who matter, a timeline of the moments from the first camera's start to the conclusion, the rights advisements, the questions before rights, the searches, seizures and force, the statements that matter, the gaps, the outcome; every time marked when it is off the record, every quote marked whether the record holds it word for word, the timeline marked when it stops early. Kept with the memo, shown on the Memo tab under a fold, printed in Memo to Word. Its instructions are the Memo facts sheet template.
_Avoid_: extraction, outline, notes (the office's Notes are another thing), summary, the record (the incident record is what the sheet is drawn from)

**Timeline report**:
The Incident's Chronology as a document a person hands over, from Export on the Incident page (Phase 8 chapter 14): the cover, the cameras and the band of their spans, then the Events down the pages in Spells, each entry with a still from its camera at its moment, the words heard on that camera around it, what the camera showed from its Digest, the Note and the why. Made from the Chronology as it stands when it is asked for, never kept; the stills are cut for the document and deleted with it. The Chronology is where the Events are decided; the report only prints them.
_Avoid_: timeline export, incident report, storyboard, slideshow, the memo (the Incident memo is the assistant's account; the report is the office's events)

**Note**:
A person's own line under an Event, or under a line of a Transcript, up to 2,000 characters: what it means for the case, a page cite, a thing to do. Kept with who wrote it and when it last changed; written and changed where it sits (the event box, or the box under the line); printed in the Chronology's exports and in the transcript exports that say "with notes", never in a plain export, a caption or a Clip; told to Gideon as the office's own words and never written or rewritten by it; listed together on the Notes tab. A note on a line of a recording that is a synced camera of an Incident is also an Event on that Incident's Chronology, at the line's moment, one thing in two places (Phase 8 chapter 11); a note on an unsynced camera's line, or on a recording in no Incident, is a line note alone. Phase 7 chapter 1 for an Event, Phase 8 chapter 2 for a line.
_Avoid_: comment, annotation, remark, bookmark, flag

**Notes tab**:
The tab on the Case page that lists every Note in the Case, on lines and on events, newest first, each opening where it was written; with Download notes, a Word document of them all for the office's own reading. Phase 8 chapter 2.
_Avoid_: comments, annotations, notebook

**To check**:
A person's mark on an Event that something needs looking at, shown as a pill on the Chronology tab, counted in its head line, printed in the exports, and told to the memo, which says where a point is unsettled. Cleared only by a person. Phase 7 chapter 1.
_Avoid_: flag, todo, open

**About**:
The Chronology's one paragraph before the events, up to 2,000 characters, kept on the Incident and edited from the top of the Chronology tab: the matter, the date, the cameras' owners as the office knows them. Printed on the export's cover and told to the memo. Phase 7 chapter 1.
_Avoid_: description (that is a Recording's note), summary, introduction

**Sync sheet**:
The one place syncing is done on the incident page (Phase 6 chapter 5): opened by Sync in the transport, on a tile, or on the Cameras tab; one row per camera with its clock, its place, a tick and its controls; Sync all has the app try each camera in the order that works (its clock checked, its clock unchecked, the sound against a camera in step, then a person's hand), and a camera the app could not sync says why and shows what to do next (needs a hand).
_Avoid_: auto-sync, calibrate, align, offset, drift

**Incident clip**:
A Clip cut from an Event of an Incident: the event's cameras over its span, the focus camera large or a grid, the Incident clock and the camera ids burned in, the sound from one camera. A Clip like any other on the Clips page, whose Recording is the sound camera's, carrying besides the Incident, the Event, the cameras and the layout so Render again remakes it. Phase 7 chapter 1.
_Avoid_: montage, multicam export, wall clip

**Person**:
One human being in a Case, as named across its Recordings: every Speaker in the Case's Transcripts given the same name is that Person. Holds an optional Role and notes, lives only inside its Case, and stays until someone deletes or merges it. A Person shows up as a Speaker in each Recording they are in.
_Avoid_: speaker (that is the label in one Transcript), party, participant, contact

**Role**:
The optional part a Person plays in the matter (Defendant, Officer, Interpreter, and the like), picked from a list an Admin keeps. Printed beside the name on a Transcript export's cover.
_Avoid_: title, type (that is a Recording's)

**Speakers tab**:
The tab on the Case page that lists the Case's People, where each appears, and the Recordings whose Speakers are still unnamed; the one place a Person is renamed for the whole Case, merged, or deleted. The viewer's own Speakers panel names one Recording's Speakers only.
_Avoid_: speaker management, people page, Speakers panel (that is the viewer's)

**Last activity**:
The most recent use of a Case by its owner or a Collaborator: opening the Case, opening a Recording in it, adding or moving one in, correcting, naming a Speaker or changing a Person, asking for a Summary or Chat, saving or downloading a Clip, exporting, renaming or sharing the Case, pressing Keep, or restoring it from the Recycle bin. Handing the Case over (Reassign, Transfer) and an Admin's audited opening do not count. The Retention policy's clock starts over at every Last activity.

**Reassign**:
An Admin giving a Case, or every Case a user owns, to a named user. The way a leaver's Cases find a new owner. Does not start the Retention policy's clock over.

**Transfer**:
An owner giving one of their Cases to a named colleague; the old owner stays on it as a Collaborator. Does not start the Retention policy's clock over.

**Share**:
The owner's grant of access to one Case to one named colleague. One kind only: whoever a Case is shared with can do inside it everything the owner can, short of sharing, renaming, transferring, or deleting the Case.
_Avoid_: permission, access level, viewer, editor (there are no levels)

**Collaborator**:
A person a Case is shared with. Their work in the Case counts as its activity, and the Recordings they add count against the owner's room.
_Avoid_: sharer (could mean either person), guest, member

**Sharing**:
The admin toggle that lets owners share Cases. Off hides every Share without ending it.

**Retention policy**:
The admin-set rule that moves a Case to the Recycle bin the night it reaches a set number of days without activity, whatever else is going on. One clock per Case; no exceptions and no holds. The clock pauses while Folder management is off.
_Avoid_: auto-delete, expiry, legal hold

**Retention warning**:
The amber mark a Case carries on the Cases page during its last days before the Retention policy deletes it, with the matching line in the nightly Retention digest.

**Keep**:
The one-click act on a warned Case that starts its Retention policy clock over, as opening the Case would.

**Recycle bin**:
Where a Case the Retention policy has deleted waits, out of every list and unusable, for a set number of days before it is wiped for good. The owner or an Admin can restore it meanwhile; the wait pauses while Folder management is off. Nothing a person deletes goes there.
_Avoid_: trash, soft delete (an implementation term)

**Notification**:
An email the app sends to a person about their own Cases, Shares, or Batches: the Retention digest, a Case shared with them, a Case handed to them, or a Batch finished. It names things and quotes nothing, it never carries an attachment, and nothing in the app ever waits for it.
_Avoid_: alert (that is mail to the Operator address), notice (that is wording printed on exports)

**Retention digest**:
The one Notification a person can get in a night, sent after the nightly sweep and listing every Case, their own or shared with them, that the Retention policy will delete soon. Sent every night while there is something to say; the last one about a Case is the final warning on the night before its deletion, and nothing is sent about a deletion or a wipe.
_Avoid_: reminder, alert

### LLM features

**AI assistant**:
The app's four language-model features together: Summary, Chat, Speaker suggestions, and Moments. Each runs only when a user asks, never by itself, and works from one Transcript, or from every Transcript in a Case as a Case Chat, and nothing else.
_Avoid_: the LLM, the model (in anything a user reads)

**Summary**:
English prose the AI assistant writes about one Transcript when a user asks, in the shape of a Summary template, with every point tied to a time. A Transcript can have several; each can be exported to Word.

**Summary template**:
An admin-kept instruction that fixes the shape of a Summary. "Standard summary", the "Video summary", and one per shipped Recording type are built in; Admins may add more, and users choose one only when more than one is offered.

**Video summary**:
The shipped Summary template for a video Recording without a Recording type, when Moments reach answers: what was said and what the camera showed interleaved, and a part "Seen but not said" for what the camera showed that nobody spoke about. A Recording type still wins: a body camera recording keeps its Body camera summary. The viewer's button reads "Summarise this video" on such a Recording. Phase 4.
_Avoid_: visual summary, combined summary, multimodal summary

**Focus**:
The user's optional steer for one Summary, such as "the timeline of the evening of March 3".

**Chat**:
A conversation with the AI assistant grounded in one Transcript or, as a Case Chat, in every Transcript in a Case, and nothing else: it answers from those Transcripts and declines everything outside them. A Transcript or a Case can have several Chats; each can be exported to Word.

**Citation**:
A time in a Summary or a Chat answer that the app has matched to a Segment, shown as a link that seeks the player. In a Case Chat it names the Recording as well and opens that Recording in the viewer at that moment; a time inside the Recording where no line starts, which is how the Digest cites what the camera showed, is a Citation to that second, and the pill's hover shows the Digest's line for it (v1.82.0).

**Gideon**:
What the chat is called on the pages, as shipped: the value of the Appearance setting What the chat is called, which an office may change. The tab, the Ask button, the drawer's head and a conversation's export title carry it; code, settings, file names and audit rows keep the word Chat. Not the engine: GIDEON, the office's other project, is what the app talks to. Phase 7 chapter 5.
_Avoid_: bot, assistant (as a name), AI (as a name), the engine's name

**Case Chat**:
A Chat grounded in every Transcript in a Case, as the Case stands when each question is asked. It belongs to the Case, is open to whoever can open the Case, and leaves with it; the "Chat across cases" setting turns it on and off.
_Avoid_: cross-Case Chat (would mean several Cases), Case-wide Chat

**Reading**:
One pass of the AI assistant over whole Transcripts that fit together in one call, about six hours of talk. A Case Chat question takes one Reading when the Case fits and otherwise several Readings and a combining step, which the page calls parts. An Incident's synced cameras are one item of a Reading, read as the Incident's record at one Sitting rather than as their own Transcripts and Digests (v1.87.0); each part is told which Recordings it holds, and the combining step joins the parts in time order rather than comparing them.

**Speaker suggestion**:
A name or role the AI assistant proposes for an unnamed Speaker when a user asks, with the Segment that shows why. Nothing changes until the user accepts it. Inside a Case, the AI assistant is told the Case's People, so it can recognise a Person already named elsewhere.

**Speaker check**:
The AI assistant reading a Transcript whose Speakers were told apart, in windows of a few minutes, for lines whose words show they belong to a different Speaker than the voice split gave them (Phase 5 chapter 3). It runs by itself as the Transcript lands, when the office has it on, or from Check the speakers on the Speakers page. It proposes and never applies: its findings are Speaker corrections. It never adds or merges a Speaker and never changes a word. Words to avoid: relabel, re-diarize, auto-correct.

**Speaker correction**:
One line the Speaker check says belongs to another Speaker already on the Transcript: the line's words, its time, who it is labelled as, who it should be, and the assistant's reason in a few words. Listed under Suggested corrections on the Speakers page until a person accepts or dismisses it. Accepting moves the line exactly as the number keys do, with the same audit row and the same Undo; a correction whose line changed since the check is dismissed rather than applied. Words to avoid: reassignment, fix, auto-fix.

**Moment**:
A model's description of what the camera showed at one chosen time of a video Recording, made on request from a short clip around that time and the words spoken in it, or its answer to a question about the picture from a few close frames. It hangs on the Transcript, is shown beside the Transcript at its time, in Details and in the exports, and, labelled, is handed to Summary and Chat. Always a description and never the Transcript; the clip is never kept. Phase 4.
_Avoid_: frame, snapshot, scene, screenshot

**Finder**:
One of the two ways Cues are found: the engine reading the whole Transcript for the lines worth seeing, or ffmpeg scanning the picture for sharp changes and the sound for raised voices. Each has its own switch; neither runs by itself.
_Avoid_: detector, classifier

**Camera line**:
How a Moment is written where it is listed: marked Camera, with its time or its span, in what the AI assistant is told and in the exports' own What the camera showed section at the end. Never among the Transcript's rows (it was, in the viewer and interleaved in the exports, until v1.51.0), and never a Segment.

**Picture record**:
The descriptions that cover one video Recording end to end: the recording cut where the picture and the sound change, each span described once, spans that touch and never overlap, made when a summary is asked for as the foundation the summary is written from. Phase 4 chapter 6. Avoid: sweep, timeline of the picture, frame set, intervals (the clock is only the ceiling).

**Prepared**:
A video whose picture record is complete and whose Digest is current, which is what its summary and chat are written from. It happens by itself as the transcript lands, on first use when a summary or a chat question comes first, or on purpose from the case page; a person never presses anything on the recording page for it. The pages say Prepared, Preparing 12 of 60 with the time left, or Not prepared. Phase 4 chapter 7. Avoid: processed (that is transcription), described, enriched, indexed. On the pages, since Phase 4 chapter 5 (v1.54.0), a prepared video reads Enriched with vision; the field keeps the name.

**Vision**:
The picture step of a video, as every page names it since Phase 4 chapter 5: the scan for where the picture and sound change, the camera's stamp, the descriptions of each span, and the Digest, joined to the words for the Summary and the Chat. A person chooses it with the tick **Enrich with vision** on the upload page; the office chooses when it runs (as each transcript lands, overnight in a window, or only when an Admin allows it); a case page row reads Enriched with vision, Enriching now, Enriching tonight, Requested now, or Not yet enriched with vision. The verb is **enrich**. Words to avoid on pages: prepared, moments, VLM, describe the whole recording.

**Vision request**:
What a person with a case makes when they ask for its vision now rather than tonight: who asked, for which case or video, when, and an optional line of why, waiting until an Admin allows or declines it in the Panel. Anyone with the case may ask; only an Admin may start vision work by day. Words to avoid: urgent, priority, escalation.

**Digest**:
One text per Transcript, made by the AI assistant when a video is prepared: a time-ordered condensation of the words and the camera lines, each line marked said, seen or both, one time per line, exact quotes kept only where the words carry weight, that the Summary, the Chat and the Case Chat are written from. Made in windows of about ten minutes; a window whose part comes back cut off is split in two. Plumbing: nobody reads it but an Admin, under Details; Details says it exists and what it was made from, and it is remade part by part when the Transcript or the described Moments change. Its instructions are a template on the Templates page. Phase 4 chapters 6 and 7. Avoid: summary (that is what a person reads), notes, index, embedding.

**Camera stamp**:
The date, the clock time and the camera id a body-worn or fixed camera burns into its picture, read once per Recording from two frames as the playback copy lands (Phase 6; when the picture record is first made until then), checked against each other, kept on the Recording, shown in Details and on an export's processing record, and told to the AI assistant as the camera's clock so a time can be given as the time of day. Copied as printed, never reordered or guessed. Phase 4 chapter 6. Avoid: overlay, OSD, watermark, metadata (that is the file's).

**Camera rules**:
The fixed instructions Summary and Chat are given whenever Camera lines are handed to them: the two sources kept apart in every sentence, neither winning, a person named only from the words, nothing inferred from the picture, only the listed times looked at, and a camera fact told briefly. Not editable; the templates are. Phase 4.

**Prompt template**:
An admin-editable instruction text the AI assistant works from: the Ground rules, the Chat instructions, the Speaker-suggestion instructions, the Moment and Find moments instructions, the Case chat, Digest and Speaker check instructions, the Proposed events and Incident memo instructions (Phase 6 chapter 3), and every Summary template. Each carries a version.

**AI notice**:
The admin-set wording shown at the top of every Summary and Chat and printed on their exports, saying the text is AI-generated and unverified.

### People

**Admin**:
A user with admin status, held through the Admin group, the manual admin flag, or a Local admin account. An Admin can open any user's material; every such access is recorded in the audit log.

**Local admin**:
An Admin account kept inside the app, independent of the directory, so IT can sign in when the directory is down.

**Admin panel**:
The Admin-only part of the app: the settings pages, the status page, the Queue, the users list, the audit log viewer, and the Installation page. Setting changes collect in a tray and are applied together, each recorded in the audit log.
_Avoid_: dashboard, console, settings screen

**Sign-in group**:
The directory group whose members may sign in. Members of the Admin group may sign in too.

**Admin group**:
The directory group whose members are Admins. Membership adds admin status and its loss removes it; it never removes a manual flag.

**Bind account**:
The read-only directory account the app signs in with to read the Sign-in group and the Admin group. It holds no group memberships and needs no delegation; its password lives in a secrets file named by `.env`, never in the panel.
_Avoid_: service account (in the app's own text), LDAP user

**Directory check**:
The nightly comparison of app accounts against the directory, also run on demand, that deactivates leavers, re-derives group-held admin status, and refreshes each account's Email address.
_Avoid_: reconcile, sync

**Deactivated**:
An account the Directory check found gone, disabled, or outside both groups. It cannot sign in and is reactivated automatically when the directory admits it again.

**Blocked**:
An account an Admin has barred from signing in until an Admin lifts the block. The Directory check never lifts it.

**Email address**:
The mailbox a person's Notifications go to: the directory's `mail` value, read at each sign-in and refreshed by the Directory check. Nobody types one for a directory account; a Local admin's is typed when the account is made. A person without one gets no mail and misses nothing the app's pages show.
_Avoid_: directory address, sign-in address (those are the userPrincipalName, the sign-in identity, which is not a mailbox)

### Record keeping

**Audit log**:
The append-only record of who did what to which item and when, kept as metadata only and read by Admins only. It never holds Transcript text, Chat or Summary text, Vocabulary, search terms, Speaker names, or Clip titles and notes.
_Avoid_: activity log, history, access log, event log

**Snapshot label**:
The short human-readable description an audit row keeps of the item it is about (for a Recording, the original file name and the start of its hash), so the row stays readable after the item is gone.

**Affected user**:
The owner of the item an audit row is about, recorded whenever that person is not the one who acted; the field that answers whose material was opened, and by whom.

**Reason class**:
The fixed short category an audit row records when something is refused or fails (a sign-in, an upload, a Job), in place of free text.
_Avoid_: error message, reason text

**Integrity check**:
The check that the audit log is unbroken from its first row, run from the admin status page or by IT, reporting either unbroken or the first break.
_Avoid_: verify, checksum (implementation terms)

**Audit retention**:
The admin-set period after which audit rows are removed by a sweep that is itself recorded.

### Platform

**Platform project**:
Another project of the office that provisions and operates the server the app runs on: one rendered Compose project, one reverse-proxy ingress, the site file, a local release registry, and, where the office has one, the Shared engine. Gideon Transcribe is a separate stack beside it (ADR 0003).
_Avoid_: the server's own name (that is the box), the AI server (ambiguous)

**App data folder**:
The one folder on the server's data drive that holds everything the app stores: working files, the database, the WhisperX service's models and state, and, in Phase 2, Cases. Nothing the app stores goes anywhere else.
_Avoid_: the mount, scratch (that is one subfolder of it)

**Install home**:
The folder on the server's OS drive that holds the checked-out Release: code, compose files, the environment file, the secrets, and the certificate. Created empty by the server preparation and filled by the clone, so it holds nothing before the clone; nothing the app stores goes there.
_Avoid_: the clone (that is what fills it), /opt (that is where it lives by default, not what it is)

**Shared engine**:
A language-model engine run outside the app that the AI assistant reaches over the network; for example, the engine a platform project on the same box serves. Its address and model name are admin settings.

**Local engine**:
The optional language-model engine shipped with the app for an office that has no Shared engine. Off by default; the AI assistant behaves the same against either.
_Avoid_: temporary vLLM, bundled model (implementation terms)

**Piece**:
One optional part of an installation an office adds when it has what the part needs: Transcription (a card), the Fast lane, an Engine (Local or Shared), the Directory, Mail, the Backup. Each is on, off, or not installed on the Status page's Pieces card, and added on the server with `./transcribe add <piece>`; the page runs nothing. An install without a card has every piece but Transcription: cases, incidents, notes, clips and documents work, and a recording uploaded waits for the card. From v1.83.0 (ADR 0015).
_Avoid_: module, component, add-on, profile (Compose's word for how a piece is switched on, never a page word), stage (the viewer's column)

**Self-signed certificate**:
The certificate `./transcribe install` can make for an office without its own certificate authority: a root the office trusts once on its workstations, and a certificate for the app's name signed by it, replaced later by the office's own without a reinstall. `./transcribe check` notes it and never fails on it.
_Avoid_: internal certificate, Caddy certificate, temporary certificate

**Backup**:
The app's nightly copy of everything it needs to come back after the server is lost: the database, the Cases' files, and the configuration, carried encrypted to a store off the box. Whole-app only: nothing is ever taken out of a Backup for one person, and a restore never brings a Workspace back.
_Avoid_: archive, dump (that is one part of it), export (that is a user's file)

**Snapshot**:
One night's Backup as kept in the store off the box. The app keeps a set number of nights and nothing older; a Case that is gone from the app lingers in Snapshots only that long.

**Backup target**:
The store off the box where Snapshots live, named in the environment file. Typically a shared folder of the app's own on an office file store, reached over SFTP as a dedicated ordinary account that signs in with a key and never a password; it holds only ciphertext.
_Avoid_: backup server, the NAS (that is the office's hardware, which holds other things too)

**Restore drill**:
The monthly, automatic proof that the newest Snapshot restores, run into a throwaway copy of the app beside the live one and torn down afterwards; its result is recorded in the audit log and shown on the status page.
_Avoid_: test restore, backup test

**Operator address**:
The one IT mailbox, named in the environment file, that receives the app's own mail: backup, drill, and restore reports, the nightly lines about Cases whose owner has left, and the test message. Replies to every message the app sends go there. Never a person's Notification.
_Avoid_: admin email, alert address, IT address

**Report**:
A person's own account, sent from any page with Report a problem, of a problem they hit or an idea that would help, kept for the Admins with where they were (the page's path, the Release, the browser, the window's size, their name) when they ticked to include it. Listed on the Panel's Reports page with the marks New, Seen and Done, counted on the rail and the Status page, and mailed to the Operator address when mail is configured. Never a transcript's words, never a screenshot, never anything that leaves the building. Phase 8 chapter 3.
_Avoid_: bug, ticket, issue (GitHub's word for other offices' reports), feedback, complaint

**Document**:
A PDF added to an Incident or a Recording as the police report about it, kept in the Case, read page by page at upload (a scan read by OCR and marked so), split into numbered Paragraphs and drawn as page pictures. Listed on the Case's Documents tab and the Report tab of the Incident or Recording it is linked to; cited by Gideon by page and paragraph; hit by Search; read against the record by the Comparison. Never loose in a Case, never in a Clip or a transcript export. Phase 8 chapter 4.
_Avoid_: attachment, exhibit, file (that is a Recording's), upload (that is the act)

**Paragraph**:
One numbered block of a Document's Page ("page 4, paragraph 2"), split by the gaps on the page: the unit the assistant cites, Search hits, and an Event rests on. Phase 8 chapter 4.
_Avoid_: chunk, passage, snippet

**Comparison**:
The assistant's reading of a Document against the incident record and the Chronology (or one Recording's Transcript and Digest), one Finding per row, each citing the Paragraph and the moment and marked Agrees, Differs, Not on camera or Not in the report; kept on the Incident or Recording, one per Document, replaced by Compare again, stale when the cameras or the Chronology change; a person dismisses or notes a Finding and makes one an Event with the source "From the report", resting on the Paragraph. Phase 8 chapter 4, built in v1.73.0.
_Avoid_: analysis, audit, reconciliation, contradiction report

**Release**:
A tagged version of the app published on GitHub with its notes, the only thing an installer ever installs or upgrades to. The notes always say whether the models or the database change.
_Avoid_: version (that is the number), build, deploy

**Upgrade**:
Moving an installed app from one Release to a newer one with the helper script: a database dump and a copy of the configuration first, then the new Release's code and images, then the database changes. Never touches the office's settings, secrets, or certificate.
_Avoid_: update, deploy, sync

**Roll back**:
Returning an upgraded app to the Release it ran before, restoring the pre-upgrade dump when the database changes cannot be reversed.
