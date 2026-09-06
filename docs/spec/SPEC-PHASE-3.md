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
- **Dictation**: a Live recording of one person's speech whose product is a Memo, written by a shipped Summary template, and handed to a colleague with Send to.
- **Dictation by email**: the one message the app sends that carries content, Off by default, so that a legal assistant gets the Memo in their mailbox when the office decides so.

It adds three admin settings, five audit rows, and no environment key.

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

### Principles

1. **A Dictation is a Live recording** of one person, of the Recording type Dictation, in a Case: everything above applies, with no people buttons and no second source.
2. **The Memo is a Summary.** The shipped Summary template "Dictation memo", for the type Dictation, writes the dictated words out as a memo: the punctuation and paragraphs the speaker asked for, the false starts removed, nothing added and nothing left out. The viewer preselects it for a Dictation, as it preselects any type's template, and the Memo is one click, on request, as every Summary is. Regenerate, Export to Word, and Delete are the Summary's own.
3. **Send to hands it over inside the app**, by the Sharing chapter's own means: the Case is shared with the colleague, and they are mailed that a Dictation is there for them. An attorney who does not want a whole matter shared for one dictation dictates into a Case of their own for dictations.
4. **Dictation by email is the office's decision, Off by default.** When On, the Memo rides with the Send to mail as a Word file, the one message the app sends that carries content. The recipient is always a colleague the directory knows and never a typed address; the audit row says it was sent and to whom, never what it said.

### Words

The Words of the Live recording chapter, with Dictation, Memo, and Send to as defined there.

### The Record page for a Dictation

The Record page with the Recording type Dictation: no people buttons (the speaker is the person recording, whose name the Transcript takes), no "also record what this computer plays", the language and translate choice as before. The title defaults to "Dictation" and the date and time. Stop transcribes it at the front of the queue as any Live recording.

### The Memo

The viewer's New summary for a Dictation preselects **Dictation memo** and says so. The Memo is a Summary: it lists under the Recording's Summaries, exports to Word with the Summary's cover and the AI notice, and is deleted with the Recording. The template is shipped, editable, and resettable, like the other shipped templates, and the office reviews its wording on the Templates page.

### Send to

On a Dictation's page in the viewer, and on the Case page's row for a Dictation: **Send to**, offered while the Dictation has a Memo. It asks for a colleague, from the same list Share offers (people who have signed in at least once and are Active; never Local admins; never a typed address), and says in plain words what will happen before the person confirms:

- the Case will be shared with the colleague, if it is not already, so they can open the Dictation and its Memo in the app;
- they will be mailed that it is there, with a link (when mail is configured); and,
- when Dictation by email is On, the Memo as a Word file will be attached to that mail.

Confirming does those three things at once: a Share, audited as Share granted when new; and one "dictation sent" Notification through the mailer, at once, to the colleague, subject "Gideon Transcribe: {by} sent you a dictation in the case "{case}"", naming the Dictation's title and the Case and carrying the link, and the Word file when the setting is On. The "Dictation sent" row records the colleague's username and whether a file rode with it.

### Dictation by email

The admin setting **Dictation by email**: On or Off, default Off, on the Email page, greyed while mail is not configured. Off: the Send to mail names and links and carries nothing. On: the Memo's Word export is attached. It is the one exception to the Email notifications chapter's rule that a message never carries content, made by the maintainer for the office's legal assistants, and the admin guide says so beside the switch. Nothing else the app sends is affected.

### What changes from Phase 2

- **Recording types**: the shipped list gains **Dictation**.
- **Summary templates**: the shipped templates gain **Dictation memo**, for the type Dictation.
- **The viewer and the Case page**: Send to on a Dictation with a Memo.
- **The mailer**: a fifth Notification kind, "dictation sent", with its template on the Email page (placeholders `{name}`, `{by}`, `{case}`, `{title}`, `{link}`), and the one attachment the app ever sends, behind the setting.
- **Sharing**: unchanged; Send to uses it.

### Audit rows

| Row | Category | When | Details |
|---|---|---|---|
| Dictation sent | Cases | Send to confirmed | the colleague's username, whether a file was attached; the object is the Recording; never the Memo |
| Email sent, kind `dictation_sent` | Email | the mailer, as for every kind | as the Email chapter fixes, plus `attached` |

### Not in this phase

- No typed addresses, no outside recipients: the directory is the only source, as the Email chapter fixed.
- No Memo without the Transcript: the Memo is written from the finished Transcript, on request.
- No attachment on any other message.

### Left to the build

- The Dictation memo template's wording, in the shape of the shipped templates: what to keep, what to drop, how spoken punctuation ("new paragraph", "full stop", "quote") is honoured.
- The Send to dialog's exact sentences, fixed in the app as the Share dialog's are.
- Whether a Dictation may be sent to more than one colleague at once (one at a time is the expectation).

## 3. Admin panel additions in Phase 3

- **Features**: **Live recording**, On or Off, default Off, greyed while Folder management is Off (a Live recording needs a Case). Off hides Record everywhere and stops the Record page; a recording in progress finishes.
- **Limits**: **Longest live recording**, whole minutes, 10 to 480, default 180.
- **Email**: **Dictation by email**, On or Off, default Off, greyed while mail is not configured; and the **Dictation sent** template beside the four.
- **Templates**: the shipped **Dictation memo** template; **Recording types** ships with Dictation.
- **Status page**: no new line; a Live recording is a Recording in the queue.

## 4. Deferred, open, and ruled out

- **A second transcription worker** (a second GPU, or two workers side by side on the same card beside the Local engine): **open, not decided.** The service's contract says it is a change inside the service that every Consumer inherits without code of its own, and the office's second card has room for it. It is not spent until a week of live recordings, with the queue line showing the waits, says the one worker is not enough. Nothing in this phase assumes either answer.
- **A draft on screen while recording**: ruled out (Principle 2). Transcription during the recording, above, is the finished-quality shape of the same wish.
- **Phones and tablets**: ruled out for this phase; the office's computers only.
- **Desk-phone capture**: ruled out; not the app's to solve.
- **Recording in the app without a Case** (into the Workspace): ruled out; a Live recording is made to be kept.
- **Sending a Memo to a typed address**: ruled out; the directory is the only source of addresses.

## Appendix A. Audit rows added in Phase 3

| Category | Row | Chapter |
|---|---|---|
| Recordings | Live recording started; Live recording finished | Live recording |
| Edits | Speakers named from taps | Live recording |
| Cases | Dictation sent | Dictation and Send to |
| Email | Email sent and Email failed, kind `dictation_sent` | Dictation and Send to |

## Appendix B. Settings added in Phase 3

| Setting | Page | Type | Default |
|---|---|---|---|
| Live recording | Features | On or Off; greyed while Folder management is Off | Off |
| Longest live recording | Limits | whole minutes, 10 to 480 | 180 |
| Dictation by email | Email | On or Off; greyed while mail is not configured | Off |
| Dictation sent (template) | Email | a Subject and a Body with `{name}`, `{by}`, `{case}`, `{title}`, `{link}` | the chapter's wording |

## Sources

The maintainer's brief of 2026-09-06: live transcription for staff who today take notes by hand; office computers only; Zoom, Teams, and jail-call platforms played on the computer; attorneys decide what to record; the finished transcript rather than a draft; Spanish as the most frequent other language; dictation shared inside the app and, at the office's option, by email.
