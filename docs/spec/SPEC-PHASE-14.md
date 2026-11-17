# Gideon Transcribe, Phase 14 specification

What the app makes is part of the client's record. A Case's work leaves the app as one Preservation copy, a zip of Word documents laid out to be saved to the client's file of record as it is.

## About this document

This is the build specification for Phase 14 of Gideon Transcribe. On 2026-11-17 the maintainer asked: "we need to think about preserving data as anything created in the app is now part of the client's record. I want this to be very easy, if anything at the time of case deletion, I'm okay with the owner being emailed a zip with the preservation data ... with instructions saying that the file should be saved to the client's file of record." A plan was drawn up the same day and every choice in it answered by the maintainer; the first release's page was drawn in `docs/spec/mockups/phase-14-preservation-copy-details.html` and agreed ("Your recommendations stand", "Yes, build it"). The documents were to be PDFs; the PDF maker was built and proven on a workstation the same day, the pages it made were compared with Word's, and the maintainer changed the choice: "switch it to export as word". The section "Why Word, and not PDF" says what was found.

The plan is three releases. This document holds them as chapters 1, 2 and 3.

It builds on Phase 1 chapter 11 (Exports), Phase 2 (Cases, Sharing, the Retention policy and the Recycle bin, Email notifications), Phase 6 (Incidents), Phase 8 (Notes, Documents and the Comparison) and Phase 10 (the case chronology). Read it with `CONTEXT.md` (Preservation copy, Export, Case, Recycle bin) and `docs/research/pdf-maker.md`.

Nothing in this document is office-specific. Two tables, five settings and one message template, no service, nothing new in any image.

## Contents

1. The Preservation copy, from the Details tab
2. The Preservation copy at deletion, and Archived
3. The Preservation copy's mail, and one save between several owners

## 1. The Preservation copy, from the Details tab (v1.244.0)

### Principles

1. **Everything made in the app, and nothing that was brought to it.** The copy holds what the app and the people using it made in the Case: the Transcripts with their Summaries and Chats, the Case Chats, the notes, the chronology, each Incident's work, the comparisons, the people and names, and a record of what was done. A Recording that was uploaded is in the office's permanent record already and is listed, not included; so is an uploaded document. A Clip is a piece of an uploaded Recording, so the copy records what was cut and from where, and holds no Clip file.
2. **A Recording made in the app is the exception.** A Dictation, or a Recording made from the New recording page, exists nowhere else, so its sound goes into the copy of the Case it is in. One that is in no Case is not preserved by this.
3. **The owner's to save.** The app makes the copy and says what it is for. Saving it to the client's file of record is the person's act; the app does not check that it was done and holds nothing back until it is.
4. **Word, as every export is.** Every document in the copy is a Word document: the very file the app's Export to Word gives for the same thing, or one written for the copy in the same typography. A Transcript in the copy therefore has the same pages and the same line numbers as the one a person exported and cited from.
5. **One layout for every Case**, so that a person who has opened one copy can find their way in another.

### Words

Added to `CONTEXT.md` with this chapter: **Preservation copy**. The pages never say archive (that word is kept for the next release's Archived, and is not a Backup), backup, bundle or package.

### What is in it

One zip, named `<case name> - preservation copy <yyyy-mm-dd>.zip`. Folders are numbered so their order holds wherever the zip is opened. A folder with nothing to hold is left out, and the numbers of the others do not move.

| In the zip | What it is |
|---|---|
| `00 Read me first.docx` | The Case's name; "Save this file to the client's file of record."; the owner, who the Case is shared with, when it was last used, when and by whom the copy was made; what is in the copy, by count; what is not in it and why; and a paragraph on what made the documents. |
| `01 Recordings/<title>/Transcript.docx` | The Word Transcript export of that Recording, unchanged: the cover, the notices, the numbered lines, the Processing record. One folder per Recording that has a Transcript. |
| `01 Recordings/<title>/Summary ....docx`, `Chat ....docx` | Each Summary that is written and each Chat that has a question, as its own Word export gives it. |
| `01 Recordings/<title>/<the recording's file>` | Only for a Recording made in the app: its original sound, as it was recorded. |
| `02 Case chats/` | Each Case Chat, an Incident's included, as its Word export gives it. |
| `03 Notes and chronology/Notes.docx` | Every note in the Case: the Recording, the time, who wrote it and when, and the note. Left out when the Case has no note. |
| `03 Notes and chronology/Chronology.docx` | The case chronology's Word export for every day, when the Case has one. A proposed event that was kept is an event of the chronology and is there. |
| `04 Incidents/<name>/` | The Incident's Chronology; its Memo when one is written; each of its comparisons. |
| `05 Comparisons/` | Each comparison of the Case that is not an Incident's. |
| `06 Map pictures and timelapses/` | Each picture of the map and each timelapse saved to the case's Documents shelf, as the file it is: these were made in the app. |
| `07 Record of clips.docx` | For each Clip: its name, the Recording's file it was cut from, from when to when and how long, who made it and when, its Incident, whether captions were burned in, its note, and the lines said in it. |
| `08 Recordings and documents, listed.docx` | Every Recording of the Case with its file name, size, length, upload date, who uploaded it and its SHA-256, and every uploaded document (a report) with its file name, size, pages and date: what to match against the permanent record. A Recording made in the app is marked as in the copy. |
| `09 People and names.docx` | The Case's People with their roles and other names, and its places and terms. |
| `10 Activity record.docx` | Every row of the audit log about the Case or anything in it that the log still holds, oldest first: when, who, what, and to what. The page says how far back the log reaches, since the Audit retention setting removes older rows. |

A name that would clash with another in the same folder is told apart with a number, as the zips of v1.242.0 do. Names keep to the characters the Word exports already keep to.

### Making it

- **Who.** The owner and every Collaborator, and an Admin with standing in the Case: whoever can already export each piece. An Admin's is audited with the owner as affected user, as an Admin's exports are.
- **Where.** The case's Details tab, in a part of its own at the foot of the left column, directly above Delete case.
- **In the background.** A large Case has hundreds of documents, and its chronologies and comparisons take longest to write. The press queues the work on the `media` queue and the page shows how far it has got ("16 of 31 documents", counted every eight); the person may leave the page. **Stop** ends it within eight documents and leaves nothing behind.
- **One at a time per Case.** While one is being made the button is the progress line, for everyone who can see the Case.
- **Kept.** The last copy made stays on the Case, with when and by whom it was made, how many documents it holds and its size, until one is made again; the new one replaces it only once it is ready. It is a file in the Case's folder, so it counts toward the owner's room, goes to the Recycle bin with the Case and is wiped with it.
- **Behind the case.** When something in the Case has been added, removed or edited since the copy was made, the part says "behind the case" and offers Make it again first, with the older copy still to download. The app's reckoning is by counts and latest dates of what the copy holds, so opening the Case, which changes nothing in it, never marks a copy behind.
- **When it cannot be made.** A document that cannot be written fails the whole copy, and the part names the document. A copy with a hole in it would be worse than none.
- **Downloading** writes one "export made" audit row of kind `preservation copy` and counts as use of the Case.

### The four states, as the page says them

| State | The part reads |
|---|---|
| None made | "none made yet"; one sentence on what the copy is; **Make the Preservation copy**. |
| Being made | "being made"; "N of M documents" with a bar; **Stop**; "You can leave this page. It will be here when it is done." |
| Ready | "ready"; "Made <when> by <whom> · N documents · <size>"; **Download**, **Make it again**; "Save it to the client's file of record." |
| Behind the case | "behind the case"; the same line, and "the case has changed since"; **Make it again**, **Download the one of <date>**. |

A copy that failed reads "could not be made" with the reason, and **Make the Preservation copy** again.

### Why Word, and not PDF

The maintainer's first choice for the file of record was PDF. The app writes no PDF, so the only free way is to turn its Word exports into PDF with LibreOffice, and that was built and run on 17 November 2026 (`docs/research/pdf-maker.md` has the facts). It works: an archival PDF of every document, in seconds, with no network. But LibreOffice does not lay a page out as Word does, and three differences were found on the first real conversion:

- **Tables** came out in equal columns. Mendable, and mended in the trial.
- **Line numbers** counted the cover's lines, so a Transcript's talk began at line 10. Mendable, and mended in the trial.
- **The lines themselves break differently.** The talk is set in Consolas so that a printed page cites the same way whoever prints it. Consolas is not free; the free face that stands in for it is wider, so long lines wrap that did not wrap in Word, and every line number after the first such line is different. No free face has Consolas's widths, so this cannot be mended.

A Transcript is cited by page and line. A copy for the file of record whose line numbers disagree with the Word export a person cited from would be worse than no PDF. So the copy holds Word documents, and no PDF maker is in the app. If PDF is wanted again, the way is to set the talk in a free fixed-width face in the Word export too, so that both are numbered alike; that changes every Transcript export and is a decision of its own.

### Audit

Category Exports. "preservation copy made" when one is ready, with its documents and size; "preservation copy stopped" and "preservation copy failed" with the reason; "export made" of kind `preservation copy` at each download.

### What it changes in the chapters in force

- Phase 2's "a Case has no zip" (the Case Chat's Export section) is ended: v1.242.0 gave a Case its zip of Transcripts and this chapter gives it the Preservation copy.
- Phase 2 chapter 3's list of what goes to the Recycle bin with a Case, and what a wipe removes, gains the Preservation copy.
- Nothing else. Download all transcripts and every export stay as they are.

### What the next releases add

Decided by the maintainer on 2026-11-17 and not built here:

- **At deletion.** A Preservation copy is made when the owner deletes a Case and when the Retention policy deletes one. It outlives the Case for a number of days an Admin sets (30 by default), in a new place called **Archived** beside the Recycle bin. This will amend "a person's own Delete is final at once".
- **By mail.** The owner is mailed that the copy exists, with the instruction to save it to the client's file of record; the zip is attached when it fits the office's mail limit and a link is sent when it does not. This will amend "no email is sent" on deletion and "a Notification never carries an attachment".
- **Reminders** in the nightly Retention digest for a copy not yet downloaded. The sweep never waits.
- Deleting one Recording or one Chat from a Case that stays makes no copy, now or then.

### As built, where it departs from the drawing

- **A folder for each Recording.** The drawing showed one document per Recording holding its Transcript, Summaries and Chats together. The app has no such combined document, so each Recording has a folder holding its Transcript, each Summary and each Chat as the documents the app already exports.
- **Pictures of the map and timelapses.** Not in the drawing. They are made in the app and saved to the case's Documents shelf, so by the chapter's first principle the files go in, in a folder of their own, and the listed document names only what was uploaded.
- **No count before making.** The drawing's "31 documents, about a minute" beside the button is not shown: counting the documents needs most of the work of planning them, and the page shows the count from the moment the making starts.
- **Not on Home.** The drawing said the copy would also be under Ready to download on Home. It is on the Details tab only; Home's list is of the session's own work.

### Left to the build

How often the making counts and looks for a Stop; the names of the files inside the Recording folders; the wording of the Read me first page within what is fixed above; how the page asks how far the making has got.

## 2. The Preservation copy at deletion, and Archived (v1.245.0)

Drawn first in `docs/spec/mockups/phase-14-preservation-at-deletion.html` and agreed by the maintainer on 2026-11-17 ("They stand"), every choice as recommended. ADR 0030 records the decision, since it changes what Delete means.

### Principles

1. **The Case is deleted as it always was; its copy outlives it.** Nothing of a Case can be brought back from its Preservation copy. The copy is the written work, for the client's file of record.
2. **Made first.** A Case is deleted once its copy exists. When the copy cannot be made, an owner's Delete stops and says why, and the owner may delete without a copy by saying so a second time. The nightly sweep never stops: it bins and wipes with or without a copy.
3. **Kept for a number of days, then gone.** The days are an Admin's to set and are counted from the day the Case was gone for good. The sweep removes a copy when its days are up, downloaded or not.
4. **The owner's, and the Admins'.** A Collaborator sees nothing of a deleted Case, as they see nothing of the Recycle bin.
5. **A setting.** An office that needs Delete to leave nothing turns it Off.

### Words

Added to `CONTEXT.md` with this chapter: **Archived**. The Preservation copy entry is amended. The pages never say archive as a noun for the copy, and never backup.

### The two settings

On the Cases page of the Admin panel, under the Recycle bin's days, greyed while Folder management is Off.

| Setting | Type | Default | Range | When changed |
|---|---|---|---|---|
| Preservation copy at deletion | on or off | On | | The next deletion. Off: nothing is made or kept when a Case is deleted, and copies already in Archived stay their days. |
| Preservation copy kept | whole days | 30 | 1 to 365 | The next sweep. A copy already past the new number is removed that night. |

### An owner's Delete

- **The question** keeps its words and gains one sentence: "A Preservation copy is made first and kept in Archived for N days, for you to save to the client's file of record." With the setting Off the sentence is not there and Delete is as it was.
- **When the Case's kept copy is not behind the case**, that copy is the one kept and the Case is deleted at once.
- **Otherwise the copy is made first**, in the background as chapter 1 makes one. The Details tab's Preservation part says "Deleting this case: its Preservation copy is being made first", with the count, and **Stop, and keep the case**. The person may leave; the Case is deleted when its copy is ready. The Case stays in use until then.
- **Done**: the person, if still there, is taken to the Cases page, which says "<name> is deleted. Its Preservation copy is in Archived for N days."
- **When the copy cannot be made**, the Case is not deleted. The part says "<name> was not deleted" with the document that failed, and offers **Try again** and **Delete without a copy**, the second behind its own confirmation. A Case deleted without a copy says so in its audit row.
- **An Admin's Delete** of somebody else's Case, and the Users page's Delete data, keep the copy the same way; Delete data makes each copy as it goes and does not stop for one that fails.

### The Retention policy's deletion

- **The night a Case is due**, its copy is made before it goes to the Recycle bin, by the sweep itself, unless its kept copy is not behind the case. The Case goes to the bin whether or not the copy could be made.
- **In the Recycle bin** the copy stays with the Case, as the Case's own. The Case's row has a **Preservation copy** column: whether it has been downloaded, **Download**, and, where there is none, **Make the copy**.
- **Restore** brings the Case back with that copy as its own, on its Details tab. Nothing goes to Archived.
- **The wipe**, by the sweep's bin period, by Delete permanently, by Empty recycle bin or by an Admin, moves the copy to Archived. A Case with no copy at its wipe has one made then if it can be; the wipe goes ahead either way.

### Archived

- **Where.** A fourth view of the Cases page, after the Recycle bin: Mine, Everyone's, Recycle bin, Archived. Its tab carries the number of the person's copies not yet downloaded. Hidden while Folder management is Off.
- **What it holds.** The Preservation copies of Cases that are gone for good, one row each: the Case's name; when it was deleted and how ("by you", "by <name>", "by the retention policy"); the copy's documents and size, and when it was made; the day it is kept until and the days left; whether it has been downloaded, when and by whom; **Download**; **Remove now**.
- **Who.** The owner sees their own. An Admin sees everyone's with the owner named and an owner filter, as on the Recycle bin; an Admin's download or removal of somebody else's is audited with the owner as affected user. A copy whose owner has left is the Admins'.
- **Download** writes one "export made" row of kind `preservation copy` and marks the row downloaded. A second download is allowed.
- **Remove now** is behind a confirmation that names the Case and says whether the copy was ever downloaded.
- **The days** are whole days from the day the Case was gone for good, the Off spells left out as the Recycle bin leaves them out.
- **The file** is the zip chapter 1 made, moved out of the Case's folder before the folder goes, into `cases/archived/` in the app's data directory, so it is in every Backup with no change to the Backup.

### The sweep

The 03:30 sweep gains two things. Before it bins a Case, it makes the Case's copy (step 2). After the wipes, it removes every copy in Archived past its days (a step between 3 and 4). Its "Retention sweep ran" row gains `copies_removed`. The sweep does nothing while Folder management is Off, so a copy's days do not run then.

### Audit

Category Cases. "preservation copy archived" when a copy goes to Archived, with why the Case went and the days it is kept; "preservation copy removed" with the cause (its days, owner, or admin) and whether it was ever downloaded. "case deleted" gains `copy`: kept, none (the setting was Off), failed, or declined (deleted without a copy by the person's second word). Category Exports: "export made" of kind `preservation copy` at each download from Archived or the Recycle bin.

### What it changes in the chapters in force

- Phase 2 chapter 3, "A person's own Delete of a Case ... is unchanged: final at once": final for the Case; its Preservation copy is kept in Archived (this chapter).
- Phase 2 chapter 3, "The wipe ... files and rows, nothing left, no recovery": the Case, yes; its Preservation copy goes to Archived for its days.
- Phase 2 chapter 3, the nightly sweep's four steps: as above.
- Phase 2 chapter 2's Delete confirmation gains its sentence.
- Chapter 1's "one at a time per Case" holds: a Delete while a copy is being made waits for that one.

### What the next release adds

The mail: one message to the owner when a copy goes to Archived or a Case to the Recycle bin, with the instruction to save it to the client's file of record, the zip attached when it fits the office's limit and a link when it does not; and a line in the nightly Retention digest for each copy not yet downloaded.

### As built, where it departs from the drawing

- **The wait is on the Details tab, not in a dialog.** The drawing's second and fourth moments were dialogs of their own. As built, the question is the dialog and the wait and the failure are said by the Preservation part on the Details tab, which already counts a copy being made: one place that says how a copy stands, and nothing to dismiss.
- **The Cases page says it is done in a line, without a link.** The Archived tab beside it carries the count.

### Left to the build

The archive's folder; how the Details tab learns the Case has gone (it asks how the copy stands, and is told the Case is gone).

## 3. The Preservation copy's mail, and one save between several owners (v1.246.0)

Drawn first in `docs/spec/mockups/phase-14-preservation-mail.html` and agreed by the maintainer on 2026-11-17 ("They stand, build"), every choice as recommended. Two things the maintainer said shape it: the owner is mailed until the copy is downloaded; and the copy is for the "Owner and also-owner, but I don't want them to double save the preservation".

### Principles

1. **A copy's owners are the Case's Owner and everyone marked Also an owner.** The Owner is not always the person who answers for the client's file. Delete, Restore and Remove now stay the Owner's and the Admins'.
2. **One copy, saved once.** Everyone is told who else has it; the file is not handed to more than one person; one mark, seen by all, says who took it; the others are told it is done; and taking it a second time asks first.
3. **Mail announces, as it always has.** Nothing waits for a message: the copy is in the app whether or not the mail arrives. What changes is that this message may carry the file, when it goes to one person and an Admin has said it may.
4. **Reminded until it is taken, then left alone.**

### Words

No new entry. The Archived, Preservation copy, Also an owner and Notification entries of `CONTEXT.md` are amended.

### Who a copy's owners are

- For a Case that still has its row (in use, or in the Recycle bin): its Owner, and each Collaborator whose Share carries the Also an owner mark, while Sharing is on.
- For a Case that is gone: the same people as they stood when it went. A Case's Shares go with it, so they are written on the archived copy as it is archived.
- **Archived** shows a copy to each of its owners and to Admins. A row whose copy has more than one owner says "Owners:" and their names. **Remove now** is offered to the Case's Owner and to Admins, not to a person marked Also an owner.
- The copy of a Case in the Recycle bin may be downloaded by a person marked Also an owner through the link their message carries; the Recycle bin page itself stays the Owner's and the Admins'.

### One mark

- A copy is **taken** when one of its owners, or an Admin, downloads it from the app, or says they saved it from their message (**Mark as saved**, on the copy's row and by a link in the message, which asks once before it marks). The copy carries who and when. The pages say "downloaded" or "saved" with the name and the day.
- **Taken once, asked after.** A person other than the one who took it who then goes to download it is shown who took it and when, and "If it is already in the client's file of record, you do not need to save it again", with Leave it and Download anyway. The row's button reads **Download again**.
- Marking is not undone, and a second download by the same person asks nothing.

### The message

One kind of Notification, "Preservation copy kept", to each of a copy's owners who is active and has an Email address. Its Subject and Body are templates on the Email page like the others, with placeholders `{name}`, `{case}`, `{happened}`, `{copy}`, `{owners}` and `{link}`; the app writes what the last four stand for:

| Placeholder | What the app writes |
|---|---|
| `{happened}` | "The case "<name>" was deleted on <day> by <who>." For the Retention policy: that it went unused for the Retention period and was deleted by the retention policy, that it waits in the Recycle bin until <day>, and the Recycle bin's address. |
| `{copy}` | Attached: "Its Preservation copy is attached: everything made in the case, as Word documents. Save it to the client's file of record." Not attached because it is too large: its size and the office's limit. Otherwise that it is to be saved to the client's file of record. |
| `{owners}` | Only when it goes to more than one: "This went to <A> (owner) and <B>. Only one of you needs to save it. Whoever downloads it is recorded, and the others are told it is done." |
| `{link}` | Where to download it and until when; and, when the file is attached, "Saved it from this message? Press here so you are not reminded:" with the Mark as saved address. |

- **When.** At once when a copy goes to Archived by a person's Delete (the Owner's or an Admin's). The night the Retention policy bins a Case, for the copy made that night. Not again when a binned Case is wiped and its copy moves to Archived. Not for a copy a person made from the Details tab.
- **The file.** Attached only when all three hold: Attach the Preservation copy is On; the message goes to exactly one person; the zip is no larger than Largest Preservation copy attached. The file is read when the message is sent.
- **Nobody to tell.** When none of a copy's owners is active with an address, the Operator address is sent one message naming the Case and its Owner, never the file.

### The nightly reminder

The Retention digest gains a block, `{copies}`, after the dictations. A digest whose template an Admin has edited and which has no `{copies}` has the block added at its foot, so no office loses the reminder by having edited the message.

- **"Preservation copies not yet saved to the client's file:"** one line for each copy the person is an owner of that is not taken: the Case, the day it is kept until, the days left, and "(the case is in the Recycle bin)" where it is. Every night until it is taken or its days are up.
- **"Preservation copies saved by someone else:"** one line, once, to each other owner, the night after a copy was taken: the Case, who took it and when, and "Nothing more for you to do."
- A person with nothing else to be told is sent the digest for this alone.

### The three settings

On the Email page, greyed while Email notifications are Off.

| Setting | Type | Default | When changed |
|---|---|---|---|
| Preservation copy mail | on or off | On | The next deletion, and the next night's digest. Off: no message and no reminder; the pages are unchanged. |
| Attach the Preservation copy | on or off | Off | The next message. On: the zip is attached when the message goes to one person and fits the limit. |
| Largest Preservation copy attached | whole MB, 1 to 100 | 20 | The next message. |

Attach is Off by default because an attachment puts the office's privileged work through its mail system, which is the office's to decide.

### Audit

Category Email: "Email sent" and "Email failed" of kind `preservation_copy`, with whether the file was attached. Category Cases: "preservation copy marked saved". "export made" at a download, as chapter 2.

### What it changes in the chapters in force

- Phase 2 chapter 8, "no mail when a Case is deleted, restored, or wiped": one, when a Case is deleted and its Preservation copy kept. None at a restore or a wipe.
- Phase 2 chapter 8, a Notification "never carries an attachment" (already excepted for a dictation sent to a colleague): this message may, under the three conditions above.
- Phase 2 chapter 8, the Retention digest: the block above.
- Chapter 2 of this document, "The owner sees their own" in Archived: each of a copy's owners.

### As built, where it departs from the drawing

- **The digest keeps its subject.** The drawing changed it to "cases deleting soon, and copies to save". The subject is an Admin's to edit and an office may have edited it, so the app leaves it.
- **Download again is a page, not a dialog.** The question is asked wherever the download is pressed from, the message's link included, so it is one small page of its own.

### Left to the build

How the "saved by someone else" line knows it has been said (it is said the night after the copy was taken, by the day the copy was taken); the exact wording within the table above.
