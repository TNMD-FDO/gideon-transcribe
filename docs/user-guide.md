# Using Gideon Transcribe

This guide is for everybody who uses the app. It follows the order you will meet things in: signing in, uploading a batch of recordings, waiting for the transcripts, downloading them, and reading or correcting one in the viewer. Admins have a guide of their own, reached from the Admin panel.

Nothing you upload leaves the building. The app runs on the office's own server, the transcription happens on that server's own graphics card, and nothing is sent to any outside service.

## Signing in

The sign-in page carries your office's logo and name when your Admin has set them. Sign in with your office username and password, the same ones you use for your computer. You can sign in if you are in the office's sign-in group. If you are not and think you should be, ask IT.

You land on the Start page, which asks one question, what do you want to do, and offers **Upload files**, **Record now** (when your office has turned recording on), and **Open a case** (when it uses cases). Along the top of every page are **Start**, **Cases**, **My recordings**, **Clips**, the **Panel** for Admins, and this guide under **Help**.

You have one login session at a time. Signing in from a second browser ends the first.

## Uploading a batch

A batch is one upload of one or more recordings that are handled together. It is the ordinary way to use the app: put in everything you have, and come back for the transcripts. **Upload files** on the Start page opens the Upload page.

When your office uses cases, the page starts with one question, **Where do they go?**: **This session only**, or **Into a case**, with the case chosen beside it. Nothing else is chosen for you: a plain transcript needs no settings at all.

Then the three steps. On a wide monitor they are on the page together, files on the left and the settings and the start button on the right; on a laptop they come one at a time, with **Next** between them.

### 1. Choose files

Drop the files on the Upload page, or click **choose files**. Most recordings work: mp4, mov, m4a, mp3, wav, wma, ogg, webm, mkv, avi, flac, amr and 3gp among them. Zip files do not; unzip them first.

The page tells you the limits your Admin has set: how many files a batch may hold, how big one file may be, and how long one recording may run. A file over a limit is refused when you try to start, with the reason beside it, and the rest of the batch goes ahead.

### 2. Settings

This step is optional: nothing here needs changing for a plain transcript. The settings apply to the whole batch. Click **Same as batch** on a file to give that one file different settings; every other file keeps the batch's.

- **Tell the speakers apart.** Off unless you turn it on. It labels each line with who is speaking, and it is not always right: it can run two people together or split one person in two, and the labels are guesses until somebody checks them against the audio. The page says so when you tick it. Turn it on when you need who said what. If you know how many people are talking, saying so helps: **Exactly** two for a phone call, for instance, or **Between** two and four for an interview. **Let the app decide** is right when you do not know.
- **Translate to English.** For a recording in another language, or with more than one. The transcript comes back in English and the original-language text is not kept. A translated transcript is marked in the viewer and carries a notice on every export.
- **Spoken language.** Leave it on **Automatic** unless the app has guessed wrong before on this kind of recording.
- **Vocabulary.** Names and terms the recording is likely to contain, one per line: people, places, case-specific words. The app tries these spellings first. Your Admin may have set an office-wide list; yours is added to it.
- **Context.** One line about what the recording is, in plain words. It helps the model choose between words that sound alike.
- **Audio clean-up.** Which preparation the sound gets before transcription. The default suits most recordings; **Phone** is for calls where it is offered.
- **Add to case** and **Recording type** appear when your office uses Cases. A recording added to a case is kept after you sign out; one without a case goes when you do.
- **Email me when this batch finishes** appears when your office sends mail. Tick it and one message comes when the last recording has ended: how many transcribed, how many failed and why, and where the recordings are. Never a word of a transcript. The tick is remembered from your last batch. If it is greyed with "No email address on your account; ask IT", the office directory has no address for you.

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

## My recordings

**My recordings** in the top bar is the one place to look for anything that is yours. It has two parts, each saying how long it keeps things.

**Recorded here**, when your office has recording on, is everything you recorded at your desk and kept on your own, with what colleagues have sent you under it. It is described under [Recording at your desk](#recording-at-your-desk) below.

**Uploaded this session** is a table of everything you have uploaded and not yet removed, newest first. Click a recording and its details appear beside the table (under the row, on a laptop): the file, its state, its clips, and what you can do with it: **Open** to read it in the viewer, **Process again** to send it through transcription again with new settings, **Move to case** when your office uses cases, and **Delete**. Up and down move along the rows; Enter opens. These stay until you sign out, unless you move them to a case.

**Clear my recordings** removes all the uploaded ones at once, after telling you what would go. **Upload files** starts a new batch.

A recording in a case is not listed here. It is on its case's page.

Any recording of yours can be **renamed** after the fact: **Rename** on its row here, or the pencil beside its title in the viewer. The new title is what every page and export shows; the file keeps the name it arrived with.

## Reading a transcript

Open a recording and the viewer shows the transcript at reading width with the tools on its left. On a wide monitor the video sits at the top of a column on the right, with the **Clips** and **Details** panels under it, so you can read, play and mark clips without anything covering the words; drag the column's left edge to make the picture bigger or smaller. On a laptop the picture sits above the transcript and the panels open as a sheet along the bottom instead. Playing the recording highlights the words being spoken, and the transcript scrolls to keep up.

### Playing

**Play** and the seek buttons are under the picture or the waveform. Click anywhere on the waveform to jump there. **Speed** slows the recording down for a difficult passage or speeds it up for a long one. **Boost** turns the volume above normal, for a quiet jail call. On a two-channel call there is also a control to shift the sound towards one side.

**Follow** keeps the current segment in view as the recording plays. It pauses when you scroll the transcript yourself, and **Resume** or the F key puts it back.

A video can be popped out into its own window, so the transcript can have the whole screen.

### Searching

**Search** finds a word or phrase in the transcript and jumps between the matches. Enter goes to the next one and Shift and Enter to the one before.

### Speakers

Each speaker has a colour, used for their name and their lines. Click a speaker's name in the **Speakers** list to give them a real one; every segment they spoke is renamed. Drag one speaker onto another when two labels turn out to be the same person, and confirm the merge. A rename or a merge can be taken back: **Undo** under the list says what it would undo ("the merge of Speaker 2 into Speaker 1") and puts exactly those lines back under their old name. Each Undo takes back one more change, newest first.

Inside a case, a name means a person: every speaker in the case's recordings given the same name is the same person. Click a speaker's name and a box opens under the list with the case's people under it, each with their role and how many recordings they are in: click a person to give the speaker that name at once, or type a name, which narrows the list as you go and makes a new person if it matches nobody. The box changes this recording only. A small badge after a name is the person's role. To rename someone in every recording at once, use the case's **Speakers** tab, described under Cases.

### Correcting

Click a segment, or press E on the one that is playing, to correct its text. **Save** keeps the correction and marks the segment as corrected; **Cancel** or Esc leaves it. Corrections go into every export. The fact that a correction was made is recorded, but what it said is not: transcript text never goes into any log.

### Exporting

On the right are the exports: **Export to Word** for a document with the speakers and times laid out, **Export as text** for the plain words, and **Captions** for a subtitle file (.srt) that plays with the video in a media player. Each carries the office's notice about machine transcription, and a translated transcript carries its translation notice too.

**Process again** sends the recording back through transcription with new settings, replacing the transcript. **Delete** removes the recording and everything about it.

### The AI assistant

When your office has turned it on, the viewer's right-hand column gains **Summary** and **Chat** tabs, and **Moments** on a video (on a laptop they are tabs of the sheet along the bottom), and the **Speakers** list offers **Suggest names**. Each works from this one transcript and nothing else, runs only when you ask, and arrives whole after a short wait while the page says "Reading the transcript...". Every one opens with a notice that it is AI-generated and unverified: check against the recording before relying on it.

- **Summary.** **New summary** asks what to concentrate on (optional) and how long: Short, Standard or Detailed. If your office has more than one template, you choose one; a recording in a case with a type (a jail call, a body camera recording, an interview, a phone call, a hearing) starts on the template made for that type, and the dialog says so, with the others still on offer. On a video with Moments on, the button reads **Summarise this video** instead: a video without a type starts on the **Video summary**, which writes from the words and the described moments together, with a part **Seen but not said** for what the camera showed that nobody spoke about (a body camera recording keeps its own template, which does the same); the dialog offers **Look at the picture first** and says what it costs in numbers, or says the summary draws on the moments already described. In the summary, a fact from the picture always reads "the camera shows ..." and its time carries a small camera mark; hover it for the description, click it to play from there. The summary never names a person from the picture and never says what a thing is beyond what the description says. A summary lists what happened with a time on each point; a time shown as a link is a **citation** that plays the recording from that moment. **Regenerate** writes it again with the same choices; **Export to Word** keeps it; **Delete** removes it. Summaries live as long as the recording does, so export what you want to keep.
- **Chat.** Ask questions about the transcript: who said what, when something came up, how many times, what a stretch was about. An empty chat may offer a few starter questions your office has chosen; click one, or type your own and press Enter (Shift+Enter for a new line). Your questions sit on the right, the answers on the left, each with its time. A time in an answer is a **play pill**, such as ▶ 12:45: hover it to see the line it points to, click it to play from there, and the transcript scrolls to that line and lights it. While the assistant reads, the panel shows how long it has been and how long it usually takes; if an answer fails, **Try again** asks the same question again. The answer comes from the transcript, and on a video with described moments from those too: ask "what was in his hand at 12:40?" and the answer uses the moment nearest that time within a minute, marked "the camera shows", or tells you no moment has been described there and where to ask for one; asked whether someone consented or was under arrest, it gives what was said and what the camera showed, with times, then says that the conclusion is not something it can answer. Asked for legal advice, an opinion, or anything outside the transcript and the moments, the assistant answers "I can only answer from this transcript." Each chat is named from its first question; **New chat** starts another, **Chats (n)** lists the earlier ones with when they started, **Copy** copies an answer, **Export to Word** keeps the chat. On a laptop, **Expand** in the panel bar gives the chat the height of the window while you read. Inside a case, the link **Ask about the whole case instead** opens the case's Chat tab.
- **Suggest names.** When two or more speakers still have no name, one click asks the assistant who they are, from what is said: a name someone uses, or a role such as Interviewer or Officer. The app first finds the evidence itself, the self-introductions ("this is Detective Ruiz") and the forms of address ("Thanks, Maria"), and hands them to the assistant along with the case's people and the office's roles; a name is suggested only when the transcript backs it, so the assistant often offers a role, or nothing, rather than a guess. Each suggestion shows the line it came from and how sure the assistant is, and the role in brackets when the name is a person already in the case. Nothing changes until you press **Accept**, which renames every segment of that speaker; **Reject** dismisses it.
- **Moments.** On a video recording, when your office has turned Moments on, the assistant can say what the camera showed at a time the words only point at: "look at that", "there's the bag", a handover, a scuffle. Hold the pointer over any transcript line and press its small **describe** button, or press **Describe this moment** in the Moments tab for wherever the player is; a box opens naming the time. Leave it empty and press Describe: the app cuts about ten seconds of the picture around that time, shows it to the assistant with the words spoken in it, and a short description appears under the line, marked **Camera**, and under **Described moments** in the tab; the clip itself is not kept. Or type a question, "is that a gun on the seat?", and the assistant looks at a few close frames at the camera's own detail and answers in three parts: what is **visible**, what that is **consistent with**, and what **cannot be told** and why. It will not tell you a dark shape is a gun when the picture cannot settle it; that is the point. Under **Suggested moments** in the tab, **Find moments** reads the whole transcript once and suggests the lines where the picture would add a fact, each with its reason, the line it was found on, and how sure the finder was; where your office has turned it on, it also scans the picture for sharp changes and the sound for raised voices or a bang. Each suggestion offers **Describe** and **Dismiss**, and its transcript line carries a dashed **Camera?** button that describes it with one press; nothing is described until you ask. **Describe the whole recording**, beside Find moments, makes a description every so often through the whole video (every minute by default) and says how many before you confirm; it skips times already described and the tab counts them as they land. On a video, **Summarise this video** offers the tick **Look at the picture first**, which does that before the summary is written so it can say what was seen as well as what was said (see Summary above); its Word export ends with **What the camera showed**. A description is what the assistant saw, never the transcript: it names people by clothing and position, says "a small bag" rather than what it holds, and "not visible" when it cannot tell; check it against the picture before relying on it. On each card, **Edit** puts your own words in its place and marks it edited, **Describe again** (or **Ask again** for a question) asks once more, **Delete** removes it, and **Make a clip** marks the moment's span in the Clips tool with the description as the note. Camera lines go into the Word and plain-text exports, marked and with a legend, and, when your office has left **Moments in answers** on, into Summary and Chat, labelled.

If a button is greyed with "The assistant is not available right now", the engine cannot be reached; try again later. Nothing you ask or read here is written to the audit log, only that a call was made.

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

**My clips** in the top bar is one table of every clip you have saved, under the place each belongs to: a heading row for each case, one for **Recorded here**, and one for **This session**, the place you touched last on top. A clip you made inside a case is under that case's name, and the heading opens the case's own Clips tab, which also shows what colleagues saved there. Click a clip and it plays beside the table (under its row, on a laptop), with its details and **Download**, **Open in viewer** and **Delete**. Pick a place at the top to see only its clips; **Download all** takes every clip on the page.

## Cases

The Cases page has three tabs: **Mine**, **Everyone's** (Admins only), and the **Recycle bin**. Click a case anywhere on its row and its page opens; the Retention column says when the clock would delete it, and **Keep** sits on a row in its last days. A case's page is the case: what is in it on the left, its recordings and their search, with the Clips, Speakers and Chat tabs; and what is about it on the right: how many recordings, when it was last used, where its clock stands, who it is shared with, and **Rename**, **Transfer** and **Delete case**. A recording opens from there into the viewer, which shows the case's name beside the back arrow and the rest of the case in a rail at the side.

Your office may have Cases turned on. A case is a named page of recordings for one matter, and a recording in a case is kept after you sign out, for as long as the office's retention policy says.

The Cases page lists your cases. **New case** makes one; there is nothing to type but its name. Clicking a case opens its page, which is where **Add recordings**, the search over its transcripts, and **Download all transcripts** for the whole case are.

A recording goes into a case either at upload, with **Add to case**, or afterwards with **Move to case**, from the Recordings page, from the viewer's Details, or from the sign-out dialog. Moving is instant whatever the size, and it takes the transcript, the clips and the corrections along. Nothing ever moves back out of a case; the only way a recording leaves one is **Delete**.

Deleting a case asks first and names what it is taking. It cannot be undone.

### Recording in the app

When your office has Live recording on, **Record** sits beside Upload recordings on the Cases page and beside Add recordings on a case's page. Choose the case, the recording type, a title if you want one (the type and the date otherwise), and the spoken language, then press **Record**. The browser asks once to use the microphone. While it records, the page shows the clock and a level meter; **Pause** and **Resume** cut the pause out of the recording; **Stop** ends it. The sound is sent to the office's server as it goes, so a computer that dies loses at most the last few seconds, and nothing leaves the building.

For a call or a meeting on the computer (Zoom, Teams, a softphone, a jail call played there), tick **Also record what this computer plays** before pressing Record. The browser asks which screen to share: choose the whole screen and tick **Share system audio** (Edge) or **Share audio** (Chrome). Only the sound is recorded, never the picture. The microphone becomes one side of the transcript and the computer the other, so who said what on a call comes out right, and the page shows a level meter for each. If you stop sharing from the browser's own bar, the microphone keeps recording alone and the recording's details say from when.

Before you press Record, the page lists the case's **people** and lets you add anyone else who will speak. While it records, **tap a person as they start talking**: the finished transcript names its speakers from those taps, which is exactly where automatic speaker separation is weakest. Press **M**, or the Mark button, at a moment that matters, and type a word for it if you like; the recording's Details list every mark as a time you can click, with **Make a clip** beside it.

Nothing appears on the page while it records: the transcript is the finished one, never a draft. When you press Stop the recording joins the transcription queue ahead of everything uploaded, and the page says where it stands ("2 recordings ahead, about 4 minutes") until the transcript opens in the viewer. The case page shows the same line on the recording's row. A recording stops by itself at the office's limit, three hours unless your Admin has changed it, and leaving the page ends it with what has been sent. Its details say it was recorded live, from what, and how it ended.

Record works in Edge and Chrome on the office's computers, not on a phone or a tablet.

### Sharing a case

When your office has Sharing on, a case's page has a **Shared with** panel under the facts about the case, and a **Share** button. Share asks for a colleague's name or username, offering everyone in the office who has signed in to the app at least once, and says, before you confirm, what they will be able to do: everything in the case except share, rename, or delete it (add recordings, correct transcripts, name speakers, ask for summaries and chats, save clips), and that recordings they add count against your storage space. There is one kind of sharing; everyone you share with can edit.

The panel lists each person the case is shared with, when they were added, and when they last opened it, with **Remove** beside each. Removing somebody takes the case out of their list; anything they added stays in it. A colleague who has left the office shows greyed with their status.

A case shared with you sits in your own Cases list marked **Shared by** the owner's name, and **New** until you first open it. Inside it you work as the owner does. Nothing in a shared case is private: everyone in it sees the same transcripts, corrections, speaker names, people, summaries, chats and clips. You may delete, process again, or move only the recordings you added yourself; the owner may do that to any. When you add a recording to somebody else's case, at upload or with Move to case, the picker shows how much of their space is left, and an upload that would go over it is refused with their name. **Leave this case**, on its page, takes you off it.

**Transfer**, beside Share, hands the case to a colleague: they become its owner, it counts against their space, and you stay on it as a collaborator until you leave. A case that changes hands keeps its clock where it was.

Using a shared case starts its retention clock over for everyone, and the amber **Keep** button works for collaborators too.

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

When your office sends mail, those same days bring one email a night, the **retention digest**: every case of yours in its last days, and under "Shared with you" every case shared with you, each with its days left. It is a safety message, one a night at most, and Keep or opening the case is what stops it. The last one is the final warning on the night before deletion; nothing is sent about the deletion itself, and the Recycle bin page is where you learn of it.

The night a case reaches the limit, it goes whole to the **Recycle bin**: its recordings, transcripts, corrections and clips together. Nothing in it can be opened until it comes back. From the bin, reached from the Cases page, you can **Restore** it exactly as it was, which starts its clock over, or **Delete permanently**. A case left in the bin is wiped for good after another thirty days, unless your Admin has set it differently. A case in the bin still counts against your quota, because it is still on the disk; **Empty recycle bin** is how you make that room at once.

Your own **Delete** of a case does not go to the bin. It is final, as the confirmation says. The bin is for what the clock takes, so that nothing is lost to neglect that somebody still wanted.

Days while the office has cases turned off do not count against any case.

## Recording at your desk

When your office has it on, **Record now** is on the Start page, and **New recording** is beside **Recorded here** on My recordings. Either opens the New recording page, which asks one question, what are you recording:

- **Dictation.** Just you. The product is the memo, written out as you dictated it.
- **Meeting or interview in the room.** The microphone hears everyone; the people expected are buttons, and you tap who is talking so the transcript names them. The product is the transcript, with an Interview summary one click away.
- **Call or meeting on this computer.** Zoom, Teams, a softphone, a jail call played here. The browser asks to share the screen's sound (choose the whole screen and tick Share system audio); the far side becomes its own side of the transcript. The product is the transcript, with a Meeting summary one click away.

Under the cards is the **Microphone** box. It names the microphone the recording will use and shows its level: say a few words and the bar should move. If it does not, pick another microphone from the list, or check Windows Sound settings; after a Remote Desktop session Windows can be left on "Remote Audio", which carries no sound at the machine itself, and the page says so when it sees that name. Your choice is remembered on that computer. If nothing reaches the app in the first seconds of a recording, the page says so too, and the recording carries on while you check.

Choose a card, add a title if you want one, and press **Record**. Talk; for a dictation, say the punctuation and the layout as you go ("new paragraph", "full stop", "comma", "open quote", "heading"). Press **Stop**. Nothing appears while you talk, but the app is transcribing as you go: every five minutes of the recording is transcribed while the next five record, so at Stop only the last few minutes are left, and the transcript is ready about a minute later, however long the meeting ran. You land on My recordings with the new recording marked on top under **Recorded here**. Its **play** button plays it there, so you can check it is the right one before you send it; **Open** takes you to the transcript. The row offers **Write the memo** for a dictation or **Write the summary** for the others. One click writes it: a dictation comes back as the document you dictated, with the false starts and the "scratch that" taken out and nothing added; a meeting or call comes back summarised in the shape your office's template gives it. **Open the memo** or **Open the summary** shows it in the viewer beside the recording, where **Export to Word** keeps it as a file. **More options** on the New recording page has the spoken language, Translate to English, the recording type (a jail call played on the computer can be typed as Jail call to get the Jail call summary), the computer's sound for a meeting in the room that has a caller on the line too, and **Tell the speakers apart**, which follows the style: on for a meeting in the room, where the people buttons name the voices, and off for a call, whose two sides are its two speakers. Turn it on for a call only when several people are on the far side; separation can split one person into two.

A recording made here is yours. **Send to** hands it to a colleague: pick them from the list, and they see it under **Sent to you** on their own My recordings page and get an email saying it is there; if your office has turned it on, the memo or summary comes attached to that email as a Word file, and so does the recording itself when it is under the size the office allows; a larger one is left out and the email says so, and the link opens it. **Take back** removes it from their page. A colleague you send to can read, play, and export, and nothing more. **Add to a case** puts a recording that belongs to a matter into its case afterwards; it stays under Recorded here with the case's name, and follows the case's clock from then on. Recording from a case's own page, with its **Record** button, puts the recording straight into that case.

A recording made here is kept for as long as the office keeps a case, counted from the last time you or a colleague opened it, wrote its memo or summary, or sent it. In its last days the row turns amber and reads "deletes in N days unless opened", your nightly email lists it, and opening it starts the clock over. There is no recycle bin for these: when the clock runs out it is gone. **Delete** on the row is final too.

## Emails the app sends

If your office has set up mail, the app sends four kinds of message, all plain text, none with an attachment, and none quoting a transcript, a summary, a chat, a speaker's name or a clip: the nightly **retention digest** about cases in their last days; **a case shared with you**, at once, when a colleague shares one; **a case handed to you**, at once, when a case is transferred or reassigned to you, with its days left; and **your batch has finished**, when you ticked the box on the Upload page. Every message names things and says where to go; the app's pages already show everything a message says, so a person without an email address misses the message and nothing else. There is no opt-out: the messages exist for safety and come at most one a night, and the batch tick is the one choice that is yours. Replies go to your office's IT mailbox.

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
