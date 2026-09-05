# Using Gideon Transcribe

This guide is for everybody who uses the app. It follows the order you will meet things in: signing in, uploading a batch of recordings, waiting for the transcripts, downloading them, and reading or correcting one in the viewer. Admins have a guide of their own, reached from the Admin panel.

Nothing you upload leaves the building. The app runs on the office's own server, the transcription happens on that server's own graphics card, and nothing is sent to any outside service.

## Signing in

Sign in with your office username and password, the same ones you use for your computer. You can sign in if you are in the office's sign-in group. If you are not and think you should be, ask IT.

You land on the Upload page. Along the top of every page are your recordings, Cases (if your office has turned them on), Clips, and this guide under Help.

You have one login session at a time. Signing in from a second browser ends the first.

## Uploading a batch

A batch is one upload of one or more recordings that are handled together. It is the ordinary way to use the app: put in everything you have, and come back for the transcripts. On a wide monitor the three steps are on the page together, files on the left and the settings and the start button on the right; on a laptop they come one at a time, with **Next** between them.

### 1. Choose files

Drop the files on the Upload page, or click **choose files**. Most recordings work: mp4, mov, m4a, mp3, wav, wma, ogg, webm, mkv, avi, flac, amr and 3gp among them. Zip files do not; unzip them first.

The page tells you the limits your Admin has set: how many files a batch may hold, how big one file may be, and how long one recording may run. A file over a limit is refused when you try to start, with the reason beside it, and the rest of the batch goes ahead.

### 2. Settings

The settings apply to the whole batch. Click **Same as batch** on a file to give that one file different settings; every other file keeps the batch's.

- **Speakers.** Whether to separate the voices. Leave it on unless the recording is one person. If you know how many people are talking, saying so helps: **Exactly** two for a phone call, for instance, or **Between** two and four for an interview. **Let the app decide** is right when you do not know.
- **Translate to English.** For a recording in another language, or with more than one. The transcript comes back in English and the original-language text is not kept. A translated transcript is marked in the viewer and carries a notice on every export.
- **Spoken language.** Leave it on **Automatic** unless the app has guessed wrong before on this kind of recording.
- **Vocabulary.** Names and terms the recording is likely to contain, one per line: people, places, case-specific words. The app tries these spellings first. Your Admin may have set an office-wide list; yours is added to it.
- **Context.** One line about what the recording is, in plain words. It helps the model choose between words that sound alike.
- **Audio clean-up.** Which preparation the sound gets before transcription. The default suits most recordings; **Phone** is for calls where it is offered.
- **Add to case** and **Recording type** appear when your office uses Cases. A recording added to a case is kept after you sign out; one without a case goes when you do.

### 3. Check and start

The last step shows what will be uploaded and with what settings. **Upload and transcribe** starts it.

## While it runs

Starting a batch takes you to its Batch page. Each recording shows what is happening to it: uploading, being checked, having its audio prepared, in line, transcribing, done, failed, or refused. Above the list is a count of each, and an estimate of when everything will be done.

One transcription runs at a time for the whole office, in the order recordings arrive, with no priority for anybody. Your place in the line is shown. You can leave the page and come back; the batch carries on without you.

Beside the list, **Ready now** names the transcripts that are already finished, each with **Open**, and offers the download of them so far; under it is how many are still to come and when they should be done.

**Cancel batch** stops everything in it that has not finished. A recording that has already finished keeps its transcript.

You have one unfinished batch at a time. The Upload page takes you back to it until it has finished.

## Getting the transcripts out

When the batch has finished, the page says how many transcripts are ready and offers **Download all transcripts**: one zip, one plain-text transcript per recording, each carrying the office's notice. Recordings that failed or were refused are simply left out.

Then two choices:

- **Done with these** removes the batch's recordings and their transcripts and takes you back to the Upload page for the next lot. It asks first, and says exactly what is going and how much space it takes. It cannot be undone, so download anything you want to keep before you agree.
- **Upload more** leaves this batch where it is and starts another.

Every recording counts against your quota until it goes, so an office running batches all day works in a loop: upload, download, done with these, upload again.

## Your recordings

The Recordings page is a table of everything you have uploaded and not yet removed, newest first. Click a recording and its details appear beside the table (under the row, on a laptop): the file, its state, its clips, and what you can do with it: **Open** to read it in the viewer, **Process again** to send it through transcription again with new settings, **Move to case** when your office uses cases, and **Delete**. Up and down move along the rows; Enter opens.

**Clear my recordings** removes all of them at once, after telling you what would go. **Upload recordings** starts a new batch.

A recording in a case is not listed here. It is on its case's page.

## Reading a transcript

Open a recording and the viewer shows the transcript at reading width with the tools on its left. On a wide monitor the video sits at the top of a column on the right, with the **Clips** and **Details** panels under it, so you can read, play and mark clips without anything covering the words; drag the column's left edge to make the picture bigger or smaller. On a laptop the picture sits above the transcript and the panels open as a sheet along the bottom instead. Playing the recording highlights the words being spoken, and the transcript scrolls to keep up.

### Playing

**Play** and the seek buttons are under the picture or the waveform. Click anywhere on the waveform to jump there. **Speed** slows the recording down for a difficult passage or speeds it up for a long one. **Boost** turns the volume above normal, for a quiet jail call. On a two-channel call there is also a control to shift the sound towards one side.

**Follow** keeps the current segment in view as the recording plays. It pauses when you scroll the transcript yourself, and **Resume** or the F key puts it back.

A video can be popped out into its own window, so the transcript can have the whole screen.

### Searching

**Search** finds a word or phrase in the transcript and jumps between the matches. Enter goes to the next one and Shift and Enter to the one before.

### Speakers

Each speaker has a colour, used for their name and their lines. Click a speaker's name in the **Speakers** list to give them a real one; every segment they spoke is renamed.

Inside a case, a name means a person: every speaker in the case's recordings given the same name is the same person. Click a speaker's name and a box opens under the list; as you type it offers the case's people, each with their role and how many recordings they are in, so you pick the person or type a new name. The box changes this recording only. A small badge after a name is the person's role. To rename someone in every recording at once, use the case's **Speakers** tab, described under Cases.

### Correcting

Click a segment, or press E on the one that is playing, to correct its text. **Save** keeps the correction and marks the segment as corrected; **Cancel** or Esc leaves it. Corrections go into every export. The fact that a correction was made is recorded, but what it said is not: transcript text never goes into any log.

### Exporting

On the right are the exports: **Export to Word** for a document with the speakers and times laid out, **Export as text** for the plain words, and **Captions** for a subtitle file (.srt) that plays with the video in a media player. Each carries the office's notice about machine transcription, and a translated transcript carries its translation notice too.

**Process again** sends the recording back through transcription with new settings, replacing the transcript. **Delete** removes the recording and everything about it.

### The AI assistant

When your office has turned it on, the viewer's right-hand column gains **Summary** and **Chat** tabs (on a laptop they are tabs of the sheet along the bottom), and the **Speakers** list offers **Suggest names**. Each works from this one transcript and nothing else, runs only when you ask, and arrives whole after a short wait while the page says "Reading the transcript...". Every one opens with a notice that it is AI-generated and unverified: check against the recording before relying on it.

- **Summary.** **New summary** asks what to concentrate on (optional) and how long: Short, Standard or Detailed. If your office has more than one template, you choose one. A summary lists what happened with a time on each point; a time shown as a link is a **citation** that plays the recording from that moment. **Regenerate** writes it again with the same choices; **Export to Word** keeps it; **Delete** removes it. Summaries live as long as the recording does, so export what you want to keep.
- **Chat.** Ask questions about the transcript: who said what, when something came up, how many times, what a stretch was about. An empty chat may offer a few starter questions your office has chosen; click one, or type your own and press Enter (Shift+Enter for a new line). Your questions sit on the right, the answers on the left, each with its time. A time in an answer is a **play pill**, such as ▶ 12:45: hover it to see the line it points to, click it to play from there, and the transcript scrolls to that line and lights it. While the assistant reads, the panel shows how long it has been and how long it usually takes; if an answer fails, **Try again** asks the same question again. The answer comes from the transcript alone; asked for legal advice, an opinion, or anything outside it, the assistant answers "I can only answer from this transcript." Each chat is named from its first question; **New chat** starts another, **Chats (n)** lists the earlier ones with when they started, **Copy** copies an answer, **Export to Word** keeps the chat. On a laptop, **Expand** in the panel bar gives the chat the height of the window while you read. Inside a case, the link **Ask about the whole case instead** opens the case's Chat tab.
- **Suggest names.** When two or more speakers still have no name, one click asks the assistant who they are, from what is said: a name someone uses, or a role such as Interviewer or Officer. The app first finds the evidence itself, the self-introductions ("this is Detective Ruiz") and the forms of address ("Thanks, Maria"), and hands them to the assistant along with the case's people and the office's roles; a name is suggested only when the transcript backs it, so the assistant often offers a role, or nothing, rather than a guess. Each suggestion shows the line it came from and how sure the assistant is, and the role in brackets when the name is a person already in the case. Nothing changes until you press **Accept**, which renames every segment of that speaker; **Reject** dismisses it.

If a button is greyed with "The AI assistant is not available right now", the engine cannot be reached; try again later. Nothing you ask or read here is written to the audit log, only that a call was made.

### Keyboard shortcuts

Shortcuts work whenever you are not typing in a box, so a corrector or an interpreter can stay on the keyboard. **?** shows this list in the viewer.

| Key | What it does |
|---|---|
| Space | Play or pause |
| B | Back three seconds and keep playing |
| Left and Right | Back or forward five seconds |
| Shift and Left or Right | One second |
| Ctrl and Left or Right | Thirty seconds |
| , and . | One frame back or forward |
| Up and Down | Previous or next segment |
| [ and ] | Slower or faster |
| 0 | Normal speed |
| F | Follow mode |
| E | Correct the current segment |
| Ctrl and Enter | Save the correction |
| Esc | Cancel, or close what is open |
| / | Search |
| Enter | Next match; Shift and Enter for the one before |
| I and O | Clip start or end at the playhead |
| S | Snap the clip to this segment |
| P | Preview the clip |
| D | Details |
| ? | This list |

## Clips

A clip is a chosen stretch of a recording, saved as its own small file for use outside the app: a passage to play in court, or to send to a colleague. Your office may have clips turned off; if so, none of this appears.

In the viewer, **New clip** opens the clip tool. Mark the start and the end by dragging on the waveform, or with I and O at the playhead, or with S to snap to the segment you are on. **Preview** plays just that stretch. Give it a title and, if you like, a note, and **Save clip**. The file is made in the background and appears under the **Clips** tab, and on the Clips page, where every clip you have made is listed and can be downloaded one at a time or all at once.

A clip is part of the recording it came from. Deleting the recording deletes its clips, and so does signing out, unless the recording is in a case.

The Clips page is one table of every clip you have made this session, with the recording each came from. Click a clip and it plays beside the table (under its row, on a laptop), with its details and **Download**, **Open in viewer** and **Delete**. Pick a recording at the top to see only its clips.

## Cases

The Cases page has three tabs: **Mine**, **Everyone's** (Admins only), and the **Recycle bin**. Click a case and its details appear beside the table (under the row, on a laptop) with **Open** and **Case page**; the Retention column says when the clock would delete it. A case's own page puts what is in the case on the left, its recordings and their search, and what is about the case on the right: how many recordings, when it was last used, where its clock stands, and **Rename** and **Delete case**.

Your office may have Cases turned on. A case is a named page of recordings for one matter, and a recording in a case is kept after you sign out, for as long as the office's retention policy says.

The Cases page lists your cases. **New case** makes one; there is nothing to type but its name. Clicking a case opens its newest transcript in the viewer, with the rest of the case beside it; a case with nothing to play yet opens its own page, which is where **Add recordings** is. Each row also has a quiet **Case page** link, for renaming, deleting, searching the case's transcripts, and **Download all transcripts** for the whole case.

A recording goes into a case either at upload, with **Add to case**, or afterwards with **Move to case**, from the Recordings page, from the viewer's Details, or from the sign-out dialog. Moving is instant whatever the size, and it takes the transcript, the clips and the corrections along. Nothing ever moves back out of a case; the only way a recording leaves one is **Delete**.

Deleting a case asks first and names what it is taking. It cannot be undone.

### The Speakers tab

A case's page has a **Speakers** tab beside its recordings and clips. Inside a case a name means a person, so the tab lists the case's **people**: everyone who has been named in any of its recordings, with their **role** (Defendant, Officer, Interpreter and the others your office uses), the first line of any notes, and "in N recordings", which opens to the recording titles, each a link that plays from that person's first words there. A person also comes to be when you accept a suggestion, when a recording with named speakers is moved into the case, or when you type one in with **Add person**; a name already in the case joins that person rather than making a second.

Under each person's row: **Rename everywhere** changes the name in every recording of the case at once (the viewer's rename box changes one recording only); **Save** keeps a changed role or notes; **Merge into** joins two people who turned out to be one, renaming every segment of the first to the second's name and keeping the first's notes under their old name; **Delete person** puts their speakers back to Speaker 1, Speaker 2 and removes them from the list. Merge and Delete ask first.

At the bottom, **Unnamed speakers** lists the recordings with speakers still unnamed, each a link. That list is the way to work through a case: open a recording, use Suggest names or type the names in its Speakers panel, and come back until the list is empty.

### The Chat tab

When your office has the AI assistant on, a case's page also has a **Chat** tab. It works like the Chat in a recording's viewer, but its ground is the whole case: every recording in the case that has a transcript, read whole, as the case stands when you ask. Nothing is picked and nothing is kept between questions; each question reads the transcripts afresh, so a recording added or moved in later is read from the next question on. A recording still transcribing, or one that failed, is skipped, and the answer says so at the top.

Ask about who said what across the calls, when something first came up, how many times, or what one recording says that another does not. "Summarise this case" is a question like any other, and the tab offers your office's starter questions, if it has set some, when a chat is empty. The answer comes from the transcripts alone, in English whatever language they are in, and the case's people and their roles are told to the assistant ahead of the talk. A time in an answer is a **play pill** naming the recording, ▶ Jail call 2, 12:45: hover it to see the line it points to, click it to open that recording in the viewer at that moment. If a recording has since left the case, its citations stay as text marked "(recording removed)". The tab looks and works exactly like the chat in a recording's viewer.

A small case is one reading and takes about as long as a recording's Chat. A large one is read in parts: the tab says "Reading 40 transcripts in 4 parts. This takes a few minutes." and counts the parts as they are read, each part is asked your question, and one final step writes the answer from the parts. There is a ceiling on how much talk one question may read, 120 hours unless your Admin has changed it; over it the question refuses and says so. A question that fails shows why and **Try again**, never half an answer.

The chats belong to the case: everyone who can open the case sees the same ones, and **New chat**, **Copy**, **Export to Word** and **Delete chat** work as in the viewer. Asking a question counts as using the case, so it starts the retention clock over; deleting a chat does not. The export's cover lists the recordings the chat has read, and its citations print as the recording's title and time.

### How long a case is kept

A case is kept for as long as somebody uses it. Every use starts its clock over: opening the case or a recording in it, adding or moving a recording in, correcting, naming a speaker, exporting, saving or downloading a clip, renaming. Looking at the list of cases does not count, and neither does an Admin looking in.

The office sets how long a case may go unused, thirty days unless your Admin has changed it. During the last days before that, seven by default, the case's row on the Cases page turns amber and reads **Deletes in N days unless used**, with a **Keep** button beside it. Keep starts the clock over without opening anything; so does opening the case. The **Expiring** button above the list shows only the cases in their last days.

The night a case reaches the limit, it goes whole to the **Recycle bin**: its recordings, transcripts, corrections and clips together. Nothing in it can be opened until it comes back. From the bin, reached from the Cases page, you can **Restore** it exactly as it was, which starts its clock over, or **Delete permanently**. A case left in the bin is wiped for good after another thirty days, unless your Admin has set it differently. A case in the bin still counts against your quota, because it is still on the disk; **Empty recycle bin** is how you make that room at once.

Your own **Delete** of a case does not go to the bin. It is final, as the confirmation says. The bin is for what the clock takes, so that nothing is lost to neglect that somebody still wanted.

Days while the office has cases turned off do not count against any case.

## Signing out, and what happens to your recordings

Everything that is not in a case belongs to your login session and goes when it ends: the recordings, their transcripts, and their clips. That is by design. Nothing of yours lingers on the server for somebody else to find.

**Sign out** shows what is about to go, and offers **Download all transcripts**, **Download everything**, and **Download clips** first. If your office uses Cases, it also lists the recordings that are not yet in one, with **Move to case** beside each. Take what you want to keep before you press Sign out; there is no way back afterwards.

You are also signed out after a period without activity, eight hours unless your Admin has set it differently. The app warns you before that happens and offers to keep you signed in. A batch that is still running is allowed to finish before anything is removed.

Your recordings count against a quota, fifty gigabytes unless your Admin has set it differently. The Upload page tells you when you are near it. **Done with these** and **Clear my recordings** are how you make room without signing out.

## The guide beside the page

On a wide monitor, the **?** at the top of every page opens this guide in a column on the right, at the part about the page you are on, and the page moves over to make room. It stays open as you move between pages, each time at that page's part, until you close it. On a laptop, **Help** opens the guide as a page instead.

## When something goes wrong

- **Refused.** The file was over a limit, or the app has already got an identical copy of it. The reason is shown beside it. Nothing else in the batch is affected.
- **Failed.** Something went wrong in transcription. **Retry** sends it again. If it fails a second time, tell IT which recording it was.
- **The transcript is wrong.** Correct the segments, or **Process again** with different settings: a speaker count, a vocabulary, the right language.
- **The page says transcription is not available.** The transcription service is down or the server is low on space. Your recordings are safe; try again later, or tell IT.
- **You cannot sign in.** Your account may not be in the sign-in group, or your password may have changed. Ask IT.

## What the app records about you

The app keeps a log of what happened: who signed in, who uploaded what and when, who downloaded, corrected, or deleted. It never records what a recording says, what a correction changed, what you searched for, or the names you gave speakers. Admins can see the log, and an Admin who opens your recordings is recorded doing so.
