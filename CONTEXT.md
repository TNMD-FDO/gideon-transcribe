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
The list of every Clip in a user's Workspace, with Download all. A Case's Clips are listed on the Case page instead, so a Clip appears in one place only.
_Avoid_: My Clips (the working name), clip library

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

**Diarization**:
The step that separates a Recording into Speakers. Always a user choice per Recording, with a speaker-count hint. The pages call the choice "Diarize" and carry a short warning that automatic speaker separation is sometimes wrong. On a Two-channel call it runs per Side with the app deciding the count; a Side with one Speaker is labelled by its Side alone.
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
The waveform strip in the viewer, used to seek and to mark a Clip by dragging; split into one lane per Side on a Two-channel call.

**Bench**:
The viewer's right-hand column on a window 1280 pixels or wider: the video at the top and, under it, one of the Clips, Details, Summary and Chat panels, chosen by tabs. On a narrower window the same panels are the bottom sheet. Avoid: sidebar (that is the left one), drawer, inspector.

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
The Clips page in the top bar: one table of every Clip the person saved, under a heading row for each place it lives (a Case, Recorded here, This session), the place touched last on top. A Clip in a Case is here and on the Case's Clips tab both. Before v1.30.0 the page listed the Workspace's Clips only.
_Avoid_: Your clips, clip library

**Start page**:
Where sign-in lands: one question, what do you want to do, and three doors, Upload files, Record now (with the Record now setting on), Open a case (with Folder management on). Nothing else is on it. The top bar reads Start, Cases, My recordings, Clips, Panel, Help.
_Avoid_: home, dashboard, landing page, menu

**Recorded here**:
The first part of the My recordings page, with the Record now setting on: everything the person recorded from the New recording page and kept on its own, newest first, each with Play, Open, the memo or summary, Send to, Add to a case, Delete; and under them what colleagues have sent, "Sent to you". Kept for as long as the office keeps a case. Phase 3. It was a tab of its own, called Record, and before that Dictations, each for one release.
_Avoid_: Record tab, Dictations page (the earlier names), recorder

**Record now**:
The Start page's door to the New recording page, and the name of the Admin setting (key `dictation`) that turns it and Recorded here on. Phase 3.
_Avoid_: Record tab, Dictation setting

**Memo**:
The document a Dictation becomes: a Summary written by the shipped Dictation memo template, which writes the dictated words out as a memo rather than summarising a conversation. Phase 3.
_Avoid_: transcript (that is the words as spoken), note

**Send to**:
Handing one Dictation to a colleague: they get it under "Sent to you" on their Dictations page, they are mailed that it is there, and, when the Dictation by email setting is On, the Memo rides with the mail as a Word file. Taking it back removes it from their page. Phase 3.
_Avoid_: forward, share (that is a Case's), email (the mail is one part of it)

### Processing

**Batch**:
The set of Recordings a user submits together, with shared settings and per-Recording overrides. Every Job belongs to one Batch, and a user has one unfinished Batch at a time.

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
"My recordings" in the top bar: everything that is the person's, in two parts, Recorded here (with the Record now setting on) and Uploaded this session, the list of their uploaded Recordings with Open, Process again, Details, and Delete, kept until sign-out unless moved to a Case. Sign-in landed here in Phase 1 and lands on the Start page from v1.29.0. The pages say "my recordings" or "your recordings", never Workspace.
_Avoid_: home, dashboard, Workspace page, Recordings tab (it is My recordings)

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
A user's holding area while Folder management is off. Everything in it is discarded when the user's Login session ends, once any running Batch has finished and a grace period has passed; nothing in a Workspace outlives the session. What a user wants to keep, they export before signing out.
_Avoid_: session (that is the login), scratch (that is the disk location)

**Discard**:
The removal of everything in a Workspace once its user's Login session has ended and no Job is running: Recordings, Transcripts, Summaries, Chats, and Clips alike.
_Avoid_: cleanup, purge, sweep (the sweep is the mechanism that carries it out)

**Clear**:
A user removing Recordings from their own Workspace while still signed in, either one Batch of them ("Done with these") or all of them ("Clear my recordings"). Same removal as a Discard and equally final, but asked for by the user rather than done by the app when a Login session ends, and it never touches a Recording in a Case. It exists because an office running batches works in a loop of upload, download, clear, upload again, and every Recording counts against the user's quota until it goes.
_Avoid_: clean up, reset, empty, start over

**Folder management**:
The admin toggle that enables Cases. Off: Workspaces only; every Case is hidden from everyone and kept, its Retention policy clock paused, nothing deleted. On: users may keep Recordings in Cases, and everything Off hid comes back as it was.

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
An admin-kept instruction that fixes the shape of a Summary. "Standard summary" is built in; Admins may add more, and users choose one only when more than one is offered.

**Focus**:
The user's optional steer for one Summary, such as "the timeline of the evening of March 3".

**Chat**:
A conversation with the AI assistant grounded in one Transcript or, as a Case Chat, in every Transcript in a Case, and nothing else: it answers from those Transcripts and declines everything outside them. A Transcript or a Case can have several Chats; each can be exported to Word.

**Citation**:
A time in a Summary or a Chat answer that the app has matched to a Segment, shown as a link that seeks the player. In a Case Chat it names the Recording as well and opens that Recording in the viewer at that moment.

**Case Chat**:
A Chat grounded in every Transcript in a Case, as the Case stands when each question is asked. It belongs to the Case, is open to whoever can open the Case, and leaves with it; the "Chat across cases" setting turns it on and off.
_Avoid_: cross-Case Chat (would mean several Cases), Case-wide Chat

**Reading**:
One pass of the AI assistant over whole Transcripts that fit together in one call, about six hours of talk. A Case Chat question takes one Reading when the Case fits and otherwise several Readings and a combining step, which the page calls parts.

**Speaker suggestion**:
A name or role the AI assistant proposes for an unnamed Speaker when a user asks, with the Segment that shows why. Nothing changes until the user accepts it. Inside a Case, the AI assistant is told the Case's People, so it can recognise a Person already named elsewhere.

**Moment**:
A model's description of what the camera showed at one chosen time of a video Recording, made on request from a short clip around that time and the words spoken in it, or its answer to a question about the picture from a few close frames. It hangs on the Transcript, is shown beside the Transcript at its time, in Details and in the exports, and, labelled, is handed to Summary and Chat. Always a description and never the Transcript; the clip is never kept. Phase 4.
_Avoid_: frame, snapshot, scene, screenshot

**Cue**:
A suggested Moment: a time, and the Transcript line it belongs to when it has one, where the picture would tell what the words cannot, with a reason, how sure the finder was, and where it came from (the words, the picture, or the sound). Found by a finder when a person presses Find moments, never by a word list; stored; pending until a person accepts it (it becomes a Moment) or dismisses it.
_Avoid_: trigger, keyword, hit, phrase

**Finder**:
One of the two ways Cues are found: the engine reading the whole Transcript for the lines worth seeing, or ffmpeg scanning the picture for sharp changes and the sound for raised voices. Each has its own switch; neither runs by itself.
_Avoid_: detector, classifier

**Camera line**:
How a Moment appears among Transcript lines: marked Camera, in italic, in the viewer, in the exports, and in what the AI assistant is told. A Camera line is never a Segment.

**Prompt template**:
An admin-editable instruction text the AI assistant works from: the Ground rules, the Chat instructions, the Speaker-suggestion instructions, the Moment and Find moments instructions, and every Summary template. Each carries a version.

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

**Release**:
A tagged version of the app published on GitHub with its notes, the only thing an installer ever installs or upgrades to. The notes always say whether the models or the database change.
_Avoid_: version (that is the number), build, deploy

**Upgrade**:
Moving an installed app from one Release to a newer one with the helper script: a database dump and a copy of the configuration first, then the new Release's code and images, then the database changes. Never touches the office's settings, secrets, or certificate.
_Avoid_: update, deploy, sync

**Roll back**:
Returning an upgraded app to the Release it ran before, restoring the pre-upgrade dump when the database changes cannot be reversed.
