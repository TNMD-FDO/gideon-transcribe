# Gideon Transcribe, Phase 3 specification

The Live recording release, published as `v3.0.0`.

## About this document

This is the build specification for Phase 3 of Gideon Transcribe: recording in the browser, on the office's own domain-joined computers, with the finished transcript minutes after the recording ends; and dictation, with its memo handed to a colleague. It builds on Phase 1 (`docs/spec/SPEC-PHASE-1.md`) and Phase 2 (`docs/spec/SPEC-PHASE-2.md`), which stay in force: a Live recording is a Recording, it lives in a Case, and everything the earlier phases say about a Recording in a Case applies to it unchanged.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 3 terms Live recording, Record page, Mark, Dictation, Memo, and Send to), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the three Phase 3 settings), and `docs/whisperx-api.md` (unchanged by this phase).

Nothing in this document is office-specific. No new environment key is needed: recording in the browser needs HTTPS, which the office already has, and nothing else from the server. The conventions of the Phase 1 document apply here unchanged.

## What Phase 3 adds

Everything the app transcribes today arrives as a file. Phase 3 lets a person make the recording in the app itself:

- **Live recording**: a Recording made in the browser on an office computer, from the microphone and, when asked, from what the computer plays, so that a meeting in the room, a Zoom or Teams call, or a jail call played on the computer becomes a Recording in a Case the moment it ends, and its finished Transcript follows minutes later at the front of the queue.
- **Speaker buttons and Marks**: while recording, the people in the room are one tap each, so the finished Transcript names its Speakers; and one key drops a Mark at the moment that mattered.
- **Dictation**: a recording of one person's speech, made from a tab of its own and kept on its own, whose product is a Memo, written by a shipped Summary template, and handed to a colleague with Send to.
- **Dictation by email**: the one message the app sends that carries content, Off by default, so that a legal assistant gets the Memo in their mailbox when the office decides so.

It adds four admin settings, six audit rows, and no environment key.

## Contents

1. Live recording
2. Dictation and Send to
3. Admin panel additions in Phase 3
4. Deferred and ruled out

Appendices: A. Audit rows added in Phase 3. B. Settings added in Phase 3.

## 1. Live recording

### Principles

1. **A Live recording is a Recording.** It joins a Case at the moment it starts, its Transcript is the same Transcript, and every rule about a Recording in a Case (the Retention clock, sharing, exports, Clips, People, deletion) applies to it as to one uploaded. Nothing is kept anywhere but where an uploaded Recording is kept.
2. **The finished transcript, never a draft.** Nothing rougher than the finished Transcript is ever shown. The page records; the pipeline transcribes once the recording has ended, at the front of the queue; the viewer opens when it is done. The office said it would rather wait minutes than read a draft, and the app agrees: a draft on a screen in a client meeting is a draft somebody acts on.
3. **Nothing leaves the building.** The browser sends the audio to the server over the office network as it records, on the same path an upload takes. No service outside the office hears a word of it, whatever platform the meeting is on: a Zoom or Teams call recorded this way is recorded by the office's own server, not by Zoom's or Microsoft's transcription.
4. **The office's computers only.** The Record page works in Edge and Chrome on the office's domain-joined Windows computers, which is where the office's work happens and where the office controls what is installed. Phones and tablets are not offered it.
5. **What to record is the attorney's call.** The app does not ask for consent, show a warning, or refuse a source. The office's attorneys know what they may and may not record; the app records what it is told to and writes down that it did.
6. **What the computer plays is the far side of a call.** Recording the microphone and the computer's sound together makes a two-channel Recording, the microphone on one Side and the computer on the other, which the app already understands: who said what on a call comes out right from the channels, without diarization guessing.

### Words

- **Live recording**: a Recording made on the Record page in the browser rather than uploaded as a file. Once it ends it is a Recording like any other, marked as recorded live in its Provenance.
- **Record page**: the page a person records on: the Case and Recording type it will join, what to record (the microphone, and optionally what the computer plays), the language, the people expected, and the Record, Pause, and Stop controls.
- **Mark**: a moment a person noted while recording, by one key, with an optional word. Marks are shown in the viewer as a list of times, each a Citation, and a Mark can be made a Clip.
- **Dictation**: a Live recording of one person's speech, of the Recording type Dictation, whose product is a Memo (the Dictation and Send to chapter).
- **Memo**: the document a Dictation becomes: a Summary written by the shipped Dictation memo template, which writes the dictated words out as a memo rather than summarising a conversation.
- **Send to**: handing a Dictation to a colleague: the Case is shared with them inside the app, they are mailed that it is there, and, when Dictation by email is On, the Memo rides with the mail.

### The Record page

Reached from the Cases page and from a Case page, as **Record**, beside Upload recordings, and shown only while the Live recording setting is On. It is one page in three states: before, during, and after.

**Before.** The person chooses:

- the **Case** the recording will join (a Case they own or one shared with them; from a Case page, that Case), and the **Recording type**, from the office's list, with the Case's type list as the Upload page offers it;
- **what to record**: the microphone, always; and **also record what this computer plays**, a tick for a call or a meeting on the computer. Ticking it makes the browser ask which screen or window to share and whether to share its sound; the person shares the screen and ticks its sound, and the page records the sound only, never the picture;
- the **language**: Automatic, or one of the languages the Upload page offers, with **Translate to English** as the Upload page offers it; Spanish is the office's most frequent other language and is first in the list;
- the **people expected**: the Case's People, each a button, and a box to add one, so the buttons are ready before anybody speaks;
- a **title**, defaulting to the Recording type and the date and time.

**During.** Record starts the recording and the upload together: the browser encodes the audio and hands it to the server in pieces as it goes, so that a browser that crashes or a computer that sleeps loses at most the last piece. The page shows a clock, a level meter for each source, the people as buttons, and the Mark key:

- tapping a **person** as they start talking records "this person from this moment", and the finished Transcript names its Speakers from these taps (below);
- **Mark** (the M key, or the button) records the moment, and opens a one-line box for a word if the person wants one; the box never stops the recording;
- **Pause** stops both sources and the clock; Record resumes them into the same Recording;
- **Stop** ends the recording. The page says the recording is being transcribed and where it will appear, and offers to open the Case page or record another.

The page never navigates away on its own while recording, and leaving it, closing the tab, or the computer sleeping ends the recording as Stop would with what had arrived; a Recording that ended that way says so in its Provenance ("ended when the page closed"). Refreshing the page during a recording offers to end it or to continue where it was, since the pieces already sent are on the server.

**After.** The Recording goes to the front of the queue: its Job is made with a priority above every uploaded one, so a live recording is transcribed before the night's batches whatever is waiting. The viewer opens it when the Transcript is there; the Case page shows it with its step meanwhile, as it shows an uploaded Recording.

**The queue line.** The service reports every job's position and the minutes of audio ahead of it, and the page says so in words rather than showing a spinner: "2 recordings ahead, about 4 minutes", then "Transcribing", then the link. The Case page's row for a Recording still in the queue says the same. The estimate is the audio ahead divided by the service's measured speed (the last twenty jobs' ratio of audio length to time taken, kept by the app; the published figure of about sixty times real time until there are twenty), rounded up to the minute, and never promised: "about".

### What the recording is

- One Recording, in the Case, uploaded through the sidecar as pieces arrive, with the title, the type, the language, the translate choice, and the Case's Speaker hint (the people expected, as the number of speakers).
- With "also record what this computer plays": a two-channel Recording, the microphone on Side 1 ("This side") and the computer on Side 2 ("The other side"), transcribed as the app transcribes a Two-channel call, with a Side per channel and the Speaker names from the taps applied per Side.
- Without it: one channel, diarized as any other Recording, with the taps naming the diarized Speakers.
- Its Provenance says "Recorded live on the Record page" with the sources (microphone; microphone and the computer's sound), the browser, the pauses, and whether it ended by Stop or when the page closed. The Word export prints it as it prints every Provenance.
- Paused stretches are not in the recording: a pause is a cut, not silence, and the Provenance lists the cuts with their times.

### Speaker names from the taps

The taps are a list of moments, each with a person. When the Transcript arrives:

- for a one-channel Recording, every diarized Speaker label is given the name of the person whose taps cover most of its speech (a tap covers from its moment to the next tap); a label nobody's taps cover keeps its "Speaker N" name;
- for a two-channel Recording, the same per Side, so Side 1's labels are named from the taps and Side 2's, the far side of the call, stay as the diarization found them unless a person was tapped for them;
- the naming writes the ordinary Speaker rows (a rename per label), and a tapped person who is not yet a Person of the Case becomes one, as accepting a suggestion does;
- a Transcript with no taps is untouched.

Nothing about a tap is content: a tap is a moment and a person, and it is stored on the Recording (`speaker_taps`) until the Transcript is named, then kept for the Provenance's "named from taps" line.

### Marks

A Mark is a moment and an optional word, stored on the Recording (`marks`), shown in the viewer's Details as a list of times each a Citation that seeks the player, with the word beside it. **Make a clip** on a Mark, while Clips are on, opens the Clip tool at the Mark with thirty seconds either side and the word as the Clip's title. A Mark's word is content: it is never in an audit row or a message, and the "Live recording finished" row carries the count of Marks alone.

### Room and limits

- A Live recording counts against the Case owner's quota as any Recording in the Case does; the Record page shows the owner's remaining room for somebody else's Case, as the Upload page does, and refuses to start when it is full, with the over-quota reason class and the owner's name.
- **Longest live recording** (a Limits setting, default 180 minutes, 10 to 480): the page stops the recording at the limit, saying so, and the Recording is complete to that moment. It exists so a page left recording overnight does not fill the disk.
- The largest-file limit does not apply to a Live recording; the longest-recording limit does, as the smaller of it and the setting above.
- The disk floor applies: a Live recording does not start while the disk is below it, and one in progress is ended by the sidecar refusing the next piece, with the Provenance saying so.

### What changes from Phase 2

- **The Cases page and the Case page** gain **Record** beside Upload recordings while Live recording is On.
- **The Recording** gains `recorded_live` (with its sources and how it ended), `speaker_taps`, and `marks`; the Provenance and the Details panel show them; the viewer's Details lists the Marks.
- **The queue** gains a priority: a Live recording's Job is made ahead of every uploaded one.
- **The sidecar** accepts an upload of unknown length, appended as pieces arrive, which it already can (deferred length); the app's hooks learn that a Recording may be finished by the page rather than by the upload's declared size.
- **Provenance and exports** print the live facts.
- **The Speaker hint** may come from the people expected.

### Audit rows

| Row | Category | When | Details |
|---|---|---|---|
| Live recording started | Recordings | Record pressed, with the Recording made | the Case (snapshot label), the sources (microphone; microphone and computer), the language and translate choice; never the title |
| Live recording finished | Recordings | Stop, the limit, or the page closing | how it ended, the duration, the pauses, the count of taps and of Marks |
| Speakers named from taps | Edits | the Transcript named from the taps | the count of labels named; never a name |

The ordinary rows follow: Batch submitted, Job completed, Recording opened, and the rest.

### Transcription during the recording

The finished Transcript, sooner: while a recording continues, every closed stretch of it is transcribed at finished quality, so that at Stop only the last stretch remains. This is how a five o'clock pile-up of hour-long meetings clears in minutes rather than the GPU meeting all of them at once, and it never shows a draft: nothing appears on the Record page while it records, and the Transcript appears whole when it is done.

- **A stretch** is five minutes of recorded audio, closed when the next begins or at Stop; a pause closes one. Each closed stretch is sent to the service as a job of its own (a Run of the Recording), at the live priority, as soon as it closes; the media step prepares each stretch as it prepared whole Recordings.
- **At Stop**, the last stretch is sent, and the whole Recording is prepared once for playback and for diarization: the Speaker labels are found over the whole audio in one pass, so a speaker keeps one label across the stretches, and the taps name them as above. The stretches' Segments are merged into the one Transcript by time, as the Sides of a Two-channel call are merged today, and the alignment is each stretch's own.
- **What the person sees**: nothing until the Transcript is whole; then the viewer as for any Recording. The queue line during the last stretch says "Finishing: about 1 minute".
- **What it costs**: the same GPU minutes, spread over the hour; and a diarization pass over the whole audio at the end, which is a fraction of the transcription.
- **Ordering**: a stretch of a recording in progress goes ahead of a whole Recording that has ended, which goes ahead of an uploaded one, so the recording that ends next is the one whose last stretch is transcribed first.
- **Provenance** says "transcribed in N stretches while recording".

Built as the fifth step, after the four of the order of work, once a week of live recordings has shown the queue.

### Not in this phase

- No draft on the screen while recording: the finished Transcript or nothing (Principle 2).
- No phones or tablets, and no Firefox for the computer's sound: Edge and Chrome on the office's computers.
- No recording of a desk phone: a call on a desk phone never touches the computer. The jail's own recordings of those calls upload as before.
- No consent notice, no warning, no refusal of a source: the attorney decides.
- No automatic Summary at the end: the AI assistant works on request, as Phase 1 fixed; a Dictation's Memo is one click (the next chapter).

### Left to the build

- The encoding the browser records in (Opus in WebM is the expectation), the piece length (five to ten seconds), and how the page keeps unsent pieces until the sidecar has them, so that a lost connection resumes rather than loses.
- How the two sources become two channels in the browser (the Web Audio API's channel merger is the expectation) and what happens when the computer's sound is stereo (mixed to one channel).
- The level meters' look, the Mark key's word box, and the people buttons' size on a laptop screen.
- The exact priority number for a Live recording's Job, and whether a Process again on a Live recording keeps it.
- How "ended when the page closed" is detected (the page's unload beacon; the sidecar's silence for a minute), and the wording of the Provenance lines.

## 2. Dictation and Send to

Rewritten on 2026-09-07 from the maintainer's decision: a Dictation is a thing of its own, with a tab of its own, and not a Recording filed under a matter. Somebody who only ever dictates uses the Dictations page and nothing else; a Dictation that belongs to a matter is added to its Case afterwards, from the row, as a later choice and never a prerequisite. The earlier shape (Dictation as a Recording type on the Record page, in a Case, with Send to through Sharing) is superseded.

### Principles

1. **One tab, one door.** The Dictations page is where a person dictates, reads the memo, sends it to a colleague, and, if they want, adds the dictation to a case. It asks for nothing before Record but a title, and even that is optional.
2. **A Dictation stands on its own.** It is a Recording kept past sign-out, the person's alone, in no Case unless they add it to one. It counts against their space like anything they keep.
3. **The Memo is the product.** One click writes it, by the shipped Dictation memo template, which writes the dictated words out as the memo they dictated and never summarises; it opens in the viewer and exports to Word.
4. **Send to is per Dictation.** A colleague the directory knows gets that one Dictation under "Sent to you" on their own Dictations page, and a mail saying it is there; with Dictation by email On, the Memo rides along as a Word file. Never a typed address.
5. **The office's retention applies to each Dictation on its own**: the Retention period after it was last used, with the same warning window, the same amber mark, the same nightly digest line, and no Recycle bin, since it is one recording and not a matter. One rule for the whole office, nothing new to set.
6. **Simple first.** The Dictate page is the Record page with everything but Record put behind "More options": the computer's sound, the language, the people, for the person who dictates a meeting there too.

### Words

- **Dictation**: a Recording made on the Dictate page, kept past sign-out, the person's alone until sent, in no Case unless added to one. Its Recording type is Dictation.
- **Dictations page**: the tab where a person's Dictations are, newest first, with those colleagues have sent them under "Sent to you".
- **Memo**: the document a Dictation becomes: a Summary written by the shipped Dictation memo template.
- **Send to**: handing one Dictation to a colleague: they get it under "Sent to you", a mail saying it is there, and, when Dictation by email is On, the Memo as a Word file. Taking it back removes it from their page.
- **Add to a case**: moving a Dictation into a Case afterwards, by the existing Move to case; from then on it is that Case's Recording, under the Case's clock and sharing, and still listed on the person's Dictations page with the Case's name.

### The Dictations page

In the top bar as **Dictations**, while the Dictation setting is On. At the top, **New dictation**. Then the person's Dictations, newest first, one row each: the title, when, the length, the state while it is on its way (the queue line, as the Record page shows it), whether the Memo is written, who it was sent to, and, when it is in a Case, the Case's name. Under them, **Sent to you**: the Dictations colleagues have sent, with who sent each and when. A Dictation in its last days carries the amber mark and "deletes in N days unless opened".

Each of the person's rows offers:

- **Open**: the viewer, with the Dictation's transcript and its Memo.
- **Write the memo**, until one exists; then **Open the memo**. Writing it is one click: the Summary is made with the Dictation memo template and the viewer's Summary panel shows it when it is done.
- **Send to**: a colleague from the same list Share offers; the dialog says, before confirming, that they will see this dictation and its memo under Sent to you, that they will be mailed that it is there, and, when the setting is On, that the memo will be attached. Beside each recipient, **Take back**.
- **Add to a case**: the Move to case picker, over the Cases the person may put a Recording into.
- **Delete**: final, as a Recording's Delete is.

A row under "Sent to you" offers Open and Open the memo, and nothing more: a recipient reads, exports, and plays, and does not send, add, or delete.

### The Dictate page

The Record page in dictation mode, reached from New dictation: a title (optional; "Dictation" and the date otherwise), and Record. Under **More options**, folded: the spoken language and Translate to English, "also record what this computer plays", and the people expected. Everything of the Live recording chapter applies: the sound goes to the server as it is made, Pause cuts, the longest length stops it, leaving the page ends it, the queue line follows, and the finished Transcript is the only transcript shown. The Dictation is made in no Case, with the Recording type Dictation, its own Batch, and last used now.

### The Memo

The shipped Summary template **Dictation memo**, for the Recording type Dictation, built in, editable and resettable, reviewed by the office on the Templates page. It writes the dictated words out as the memo dictated: every fact, name, date, number, and instruction kept and nothing added; false starts, repeats, filler, and asides to the typist removed, applying what they ask ("scratch that"); spoken punctuation and layout honoured ("new paragraph", "full stop", "comma", "open quote", "bullet", "heading"); no greeting, sign-off, or date unless dictated; an unclear word kept and marked. Write the memo asks for it at the Detailed length, so nothing is cut short. The Memo is a Summary: Regenerate, Export to Word, Delete as any; the viewer preselects the template for a Dictation as for any type.

### Send to

`Send to` makes a **DictationShare** (the Dictation, the person, who sent it, when, last opened) and one "dictation sent" Notification through the mailer, at once, to the recipient: subject "Gideon Transcribe: {by} sent you a dictation", the title and the link, and the Memo as a Word file when Dictation by email is On and a Memo exists (a Dictation sent before its Memo is written is sent with the link alone). The recipient opens the Dictation and its Memo through the ordinary gates: they stand to it as their own for reading, playing, and exporting, and not for changing, sending, adding, or deleting. Sending again to the same person changes nothing. **Take back** deletes the share; nothing is mailed. Sending and taking back are use, for the clock.

### Retention

Each Dictation not in a Case has its own clock: `last_used`, moved by opening it (the viewer), writing its Memo, sending it, taking a share back, and pressing Keep on its row; a recipient's opening moves it too. The nightly sweep (the retention sweep's minute, and independent of Folder management, since Dictations do not depend on Cases) deletes every Dictation whose days since last use reach the Retention period, for good, writing the Recording's own "Recording deleted" row with the cause `retention`, and nothing else: no Recycle bin. Inside the Warning-before-deletion window the row is amber with "deletes in N days unless opened", and the person's nightly digest carries a "Dictations deleting soon" block, one line per Dictation (the title and the days left), in the same message as their Cases. A Dictation added to a Case leaves its own clock and follows the Case's.

### What changes from the earlier phases

- **The Recording** gains `is_dictation` and `last_used`; the Workspace's lists, discard, and sign-out counts leave Dictations out; the Recordings page does not list them.
- **The navigation** gains Dictations while the setting is On.
- **The gates** (`cases.standing`) count a DictationShare's recipient as standing to the Dictation as their own.
- **Recording types** ship with Dictation; **Summary templates** ship with Dictation memo, for that type.
- **The mailer** gains the kind `dictation_sent`, its template (placeholders `{name}`, `{by}`, `{title}`, `{link}`) on the Email page, and the one attachment the app ever sends, behind the setting.
- **The digest** gains the `{dictations}` block.
- **The retention sweep** gains the Dictations' pass.

### Audit rows

| Row | Category | When | Details |
|---|---|---|---|
| Dictation sent | Recordings | Send to confirmed | the colleague's username, whether a file was attached; the object is the Recording; never the Memo |
| Dictation taken back | Recordings | Take back | the colleague's username |
| Email sent, kind `dictation_sent` | Email | the mailer, as for every kind | as the Email chapter fixes, plus `attached` |
| Recording deleted, cause `retention` | Recordings | the sweep deletes a Dictation | the Recording's own row |

### Not in this phase

- No typed addresses, no outside recipients.
- No Memo without the Transcript.
- No attachment on any other message.
- No Recycle bin for a Dictation.

### Left to the build

- The exact sentences of the Send to dialog, fixed in the app.
- Whether a Dictation may be sent to more than one colleague at once (one at a time is the expectation).
- How the Dictations page shows a Memo in progress (the queue line's words, the expectation).

## 3. Admin panel additions in Phase 3

- **Features**: **Live recording**, On or Off, default Off, greyed while Folder management is Off (a Live recording needs a Case). Off hides Record everywhere and stops the Record page; a recording in progress finishes. **Dictation**, On or Off, default Off, greyed while Live recording is Off. Off hides the Dictations tab and the Dictate page and keeps every Dictation.
- **Limits**: **Longest live recording**, whole minutes, 10 to 480, default 180.
- **Email**: **Dictation by email**, On or Off, default Off, greyed while mail is not configured; and the **Dictation sent** template beside the four.
- **Templates**: the shipped **Dictation memo** template; **Recording types** ships with Dictation.
- **Status page**: no new line; a Live recording is a Recording in the queue.

## 4. Deferred, open, and ruled out

- **A second transcription worker** (a second GPU, or two workers side by side on the same card beside the Local engine): **open, not decided.** The service's contract says it is a change inside the service that every Consumer inherits without code of its own, and the office's second card has room for it. It is not spent until a week of live recordings, with the queue line showing the waits, says the one worker is not enough. Nothing in this phase assumes either answer.
- **A draft on screen while recording**: ruled out (Principle 2). Transcription during the recording, above, is the finished-quality shape of the same wish.
- **Phones and tablets**: ruled out for this phase; the office's computers only.
- **Desk-phone capture**: ruled out; not the app's to solve.
- **Recording in the app without a Case** (into the Workspace): ruled out; a Live recording is made to be kept. A Dictation is kept without a Case, on its own clock, which is the one exception, decided by the maintainer.
- **Sending a Memo to a typed address**: ruled out; the directory is the only source of addresses.

## Appendix A. Audit rows added in Phase 3

| Category | Row | Chapter |
|---|---|---|
| Recordings | Live recording started; Live recording finished | Live recording |
| Edits | Speakers named from taps | Live recording |
| Recordings | Dictation sent; Dictation taken back | Dictation and Send to |
| Email | Email sent and Email failed, kind `dictation_sent` | Dictation and Send to |

## Appendix B. Settings added in Phase 3

| Setting | Page | Type | Default |
|---|---|---|---|
| Live recording | Features | On or Off; greyed while Folder management is Off | Off |
| Dictation | Features | On or Off; greyed while Live recording is Off | Off |
| Longest live recording | Limits | whole minutes, 10 to 480 | 180 |
| Dictation by email | Email | On or Off; greyed while mail is not configured | Off |
| Dictation sent (template) | Email | a Subject and a Body with `{name}`, `{by}`, `{case}`, `{title}`, `{link}` | the chapter's wording |

## Amendments applied

- **From the build, v1.23.0 (step one: the Record page with the microphone alone), the decisions it left to the build:**
  - **The encoding** is Opus in WebM at 48 kbit/s, one channel, as `MediaRecorder` makes it in Edge and Chrome; the recorder emits a piece every five seconds and the upload client sends 64 KB at a time, about ten seconds of speech, so a page that dies loses at most that.
  - **The upload** is one tus upload of deferred length into the existing sidecar, with `live=1` in its metadata; the sidecar's pre-create hook takes a deferred-length upload only for a Live recording still recording, tests the disk floor, and tests the Case owner's room against the longest allowed recording at the encoding's rate. The post-finish hook is unchanged; a Recording the page already ended is not taken twice.
  - **How an early end is detected**: the page sends a beacon on `pagehide` (a form carrying the CSRF token, since a beacon carries no headers) with how it ended; the app moves the sidecar's partial file into place and starts the pipeline from it. A recording that ends with nothing arrived is marked failed, "ended before any sound arrived". The sidecar's silence is not watched: a computer that sleeps sends the beacon when it wakes or the tab is closed.
  - **The priority** is 100, the service's `priority` field (service 0.2.0): the line runs a higher priority first and equal priorities in arrival order; `position` and `audio_minutes_ahead` count what runs before a job under that rule. The app asks 100 for every Run of a Live recording and 0 otherwise, so a Process again on one keeps it.
  - **The queue line's estimate** divides the minutes of audio ahead plus the recording's own by the speed measured over the last twenty finished jobs, sixty times real time until there are any, rounded up to the minute, "about".
  - **The page and the pauses**: the clock counts recorded time only; a pause is `MediaRecorder.pause`, a cut in the file, listed in the Provenance as "at m:ss for N s"; the level meter is an `AnalyserNode` over the microphone; the longest length is enforced by the page's clock. The Record button asks for the microphone before the Recording is made, so a refused microphone makes nothing.
  - **Provenance** rows: "Recorded live" (the sources and how it ended), "Recorded with" (the browser's user agent, trimmed), "Pauses".
  - **A Live recording's Batch** is marked `is_live` and left out of the one-unfinished-Batch rule, so recording and uploading never block each other.
- **From the build, v1.24.0 (step two: the computer's sound):** the browser offers the computer's sound only through `getDisplayMedia` with video, so the page asks for the screen and drops the picture at once, and a share made without its sound is refused with the words to tick ("Share system audio" in Edge, "Share audio" in Chrome). The two sources are merged in the browser with a `ChannelMergerNode`, the microphone on channel 1 and the computer on channel 2, each mixed down to mono, into a stereo Opus stream at 96 kbit/s. The pipeline's `_find_sides` makes such a Recording a Two-channel call by the fact of its sources, never by the heuristic, with the Sides named "This side" and "The other side". Sharing stopped from the browser's own bar ends the computer's channel alone: the microphone goes on, and the Provenance says from when ("The computer's sound: stopped at m:ss"). A meter per source.
- **From the build, v1.25.0 (step three: the people buttons and Marks):** the people expected are the Case's People (`/record/people`) plus anyone typed on the page; while recording they are buttons, one lit while that person talks; the taps and the Marks ride with the end-of-recording call (JSON, or JSON strings in the beacon's form) and are kept on the Recording as `speaker_taps` and `marks` (migration 0028), cleaned and capped at five hundred each, a Mark's word at eighty characters. The naming runs when the Transcript is stored (`queue.merge`, after `_store`): each label takes the name whose taps cover most of its speech, the ordinary rename (`segments.update(speaker=...)` plus `people.on_named`), one "Speakers named from taps" row with the count; on a Two-channel call only the first Side's Segments are named. Marks reach the viewer through the Details answer (`marks`: at, clock, word) and are drawn as times that seek the player, with Make a clip opening the Clip tool thirty seconds either side and the word as the title. The M key drops a Mark unless a field has the focus; the word box never stops the recording. Provenance gains "Speakers named from taps" and "Marks" counts.
- **From the build, v1.26.0 (step four: the Dictation tab):** `core/dictation.py` holds the DictationShare (migration 0029, with the Recording's `is_dictation` and `last_used`), the setting `dictation` (Features, under Live recording), Send to and Take back, the Memo (a Summary at the Detailed length with the shipped `dictation` template, which ships with the Recording type Dictation), the per-Dictation clock (`days_left` from `last_used`, the Retention period and warning window), the sweep (`dictation.sweep()`, run from the retention task's minute whatever Folder management says, deleting through `lifecycle.remove_recording` with cause `retention`), and the digest's block (`for_tonights_digest`, the `{dictations}` placeholder, "- (none)" under the cases line when a person has only dictations to hear about). The Dictate page is the Record page with `mode="dictation"`: the case and type hidden, everything else under More options, the start call carrying `dictation: true`, no case, no diarization. The Dictations page lists the person's Dictations newest first with the queue line, the Memo's state (Write the memo, Writing, Open the memo), who it was sent to with Take back, Add to a case (the Move to case picker), Delete; and "Sent to you". A recipient stands to the Dictation as their own through `cases.standing`, reads and exports, and cannot send, add, or delete (the owner alone, through `_my_dictation`). The mail kind `dictation_sent` and its template; the one attachment is built when the mail goes (`mail._memo_file`, the Memo's Word export), so the file is the Memo as it stands then, and the row and the share say `attached`. Send to is one colleague at a time. The Workspace's queries (`lifecycle.in_the_workspace`), the Recordings page, and the sign-out dialog leave Dictations out.
- **From the build, v1.27.0 (the Record tab and the three styles), from the maintainer's decision that the tab should hold meetings and calls as well as dictations and ask the person what they are recording:** the Dictations tab is the **Record tab** (`/record`), listing everything a person recorded from it with the style on each row; the **New recording page** (`/record/new`, also opened from a Case page with the Case preset) asks "What are you recording?" and offers three styles, each a preset in `live.STYLES` over settings that exist: `dictation` (type Dictation, no diarization, the product a memo), `meeting` (type Interview, diarization, the people to tap, the product a summary), `call` (type Meeting, the computer's sound forced on, the product a summary). A Recording type chosen under More options wins over the style's. The style is kept in the Recording's `live["style"]`; the row's button reads "Write the memo" or "Write the summary" by `dictation.product_of`, and Write makes one Summary with the template the viewer would choose for the type (the Dictation memo for a dictation, at the Detailed length; the type's summary otherwise, Standard). A shipped Recording type **Meeting** and a shipped **Meeting summary** template (what was decided, who is to do what, questions left open, what each person said) join the list. The Features setting is named **Record tab** (key `dictation`); the Send to mail reads "sent you a recording" and the template's name is "Recording sent"; the old addresses `/dictations` and `/dictate` redirect. The Cases page's Record button is gone: the Record tab is the door for a recording kept on its own, and a Case page's Record button puts a recording into that Case.
- **From the maintainer, on the v1.27.0 build, to Send to:** with Dictation by email On, the mail carries the recording itself as well as the memo or summary. Built in v1.28.0: the recording's playback copy (its original when there is none yet), attached when it is no larger than the new Email setting **Largest recording attached** (whole MB, 1 to 100, default 20, greyed under Dictation by email); a larger one is left out and one line is added to the body before the footer saying its size, the limit, and that the link opens it. Attachments are built when the mail goes, and the "Email sent" row lists the file names (never the content). The maintainer heard the caution (privileged audio in mailboxes; relay size limits) and decided so.
- **From the maintainer, on the v1.28.0 build, to the Record tab:** Stop lands on the Record tab, not the viewer, for a recording kept on its own (a case's still opens in the viewer beside its case); the new recording is marked "Just recorded" on top, and every row has a play button that plays the recording's playback copy in place, so a person checks it is the right one before Send to. Built in v1.28.1.
- **From the maintainer, on the v1.28.1 build, to the whole top bar:** "the top panel is getting a bit confusing, one says recordings, the other says record"; and the Upload page should let a person say what they are doing, as the New recording page does. Built in v1.29.0: the top bar reads **Start, Cases, My recordings, Clips, Panel, Help**. Sign-in lands on the **Start page**, which asks one question and offers Upload files, Record now (under the setting, renamed from Record tab), and Open a case (under Folder management); nothing else is on it. The Record tab is gone: its content is **Recorded here**, the first part of **My recordings**, above **Uploaded this session** (the Phase 1 Recordings page), each part saying how long it keeps things; Stop lands there, and the old addresses redirect. The **Upload page** opens with two questions above its three steps, **What are these?** (one card per Recording type the office lists, and Something else; each presets Diarize and the speaker count, and labels the recordings when they go into a case) and **Where do they go?** (This session only, or Into a case; only with Folder management on); step 2 becomes "Anything else? (optional)". The glossary gains Start page, Recorded here, and Record now, and the Recordings page entry says where sign-in lands now.
- **From the maintainer, on the v1.30.0 build, to the Upload page:** "speaker diarization can be spotty enough that for now I never want it selected by default. So I don't want to give them a bunch of mode choices"; the Start page's upload door should say a batch is fine; "one simple clean page"; and "a clear indicator that diarization isn't perfect when they decide to turn it on themselves". Built in v1.30.1: the What are these? cards and their presets are gone; the page asks only where the files go (when Folder management is on) and then takes the files; Diarize is "Tell the speakers apart", off unless ticked, with an amber notice shown while it is on saying it is not always right and the labels are guesses until checked; step 2 is "Settings (optional)"; the Start page's card reads "One recording or a whole batch".
  - Still to come: transcription during the recording (step five).

## Sources

The maintainer's brief of 2026-09-06: live transcription for staff who today take notes by hand; office computers only; Zoom, Teams, and jail-call platforms played on the computer; attorneys decide what to record; the finished transcript rather than a draft; Spanish as the most frequent other language; dictation shared inside the app and, at the office's option, by email.
