# Gideon Transcribe, Phase 14 specification

What the app makes is part of the client's record. A Case's work leaves the app as one Preservation copy, a zip of PDFs laid out to be saved to the client's file of record as it is.

## About this document

This is the build specification for Phase 14 of Gideon Transcribe. On 2026-11-17 the maintainer asked: "we need to think about preserving data as anything created in the app is now part of the client's record. I want this to be very easy, if anything at the time of case deletion, I'm okay with the owner being emailed a zip with the preservation data ... with instructions saying that the file should be saved to the client's file of record." A plan was drawn up the same day and every choice in it answered by the maintainer; the first release's page was drawn in `docs/spec/mockups/phase-14-preservation-copy-details.html` and agreed ("Your recommendations stand", "Yes, build it").

The plan is three releases. This document holds the first as chapter 1, and says under "What the next releases add" what the maintainer has already decided for the two that follow, so that nothing built here has to be undone for them.

It builds on Phase 1 chapter 11 (Exports), Phase 2 (Cases, Sharing, the Retention policy and the Recycle bin, Email notifications), Phase 6 (Incidents), Phase 8 (Notes, Documents and the Comparison) and Phase 10 (the case chronology). Read it with `CONTEXT.md` (Preservation copy, Export, Case, Recycle bin) and `docs/research/pdf-maker.md`.

Nothing in this document is office-specific. One table, no setting, no service, one more program in the app image.

## Contents

1. The Preservation copy, from the Details tab

## 1. The Preservation copy, from the Details tab (v1.244.0)

### Principles

1. **Everything made in the app, and nothing that was brought to it.** The copy holds what the app and the people using it made in the Case: the Transcripts with their Summaries and Chats, the Case Chats, the notes, the chronology, each Incident's work, the comparisons, the people and names, and a record of what was done. A Recording that was uploaded is in the office's permanent record already and is listed, not included; so is an uploaded document. A Clip is a piece of an uploaded Recording, so the copy records what was cut and from where, and holds no Clip file.
2. **A Recording made in the app is the exception.** A Dictation, or a Recording made from the New recording page, exists nowhere else, so its sound goes into the copy of the Case it is in. One that is in no Case is not preserved by this.
3. **The owner's to save.** The app makes the copy and says what it is for. Saving it to the client's file of record is the person's act; the app does not check that it was done and holds nothing back until it is.
4. **PDF, of the archival kind.** Every document in the copy is a PDF/A-2b: fixed pages, with their typefaces inside the file, made to open the same in years. They are the app's own Word exports turned into PDF, so a document in the copy reads as the Word export of the same thing does.
5. **One layout for every Case**, so that a person who has opened one copy can find their way in another.

### Words

Added to `CONTEXT.md` with this chapter: **Preservation copy**. The pages never say archive (that word is kept for the next release's Archived, and is not a Backup), backup, bundle or package.

### What is in it

One zip, named `<case name> - preservation copy <yyyy-mm-dd>.zip`. Folders are numbered so their order holds wherever the zip is opened. A folder with nothing to hold is left out, and the numbers of the others do not move.

| In the zip | What it is |
|---|---|
| `00 Read me first.pdf` | The Case's name; "Save this file to the client's file of record."; the owner, who the Case is shared with, when it was last used, when and by whom the copy was made; what is in the copy, by count; what is not in it and why; and a paragraph on what made the documents. |
| `01 Recordings/<title>/Transcript.pdf` | The Word Transcript export of that Recording, unchanged: the cover, the notices, the numbered lines, the Processing record. One folder per Recording that has a Transcript. |
| `01 Recordings/<title>/Summary ....pdf`, `Chat ....pdf` | Each Summary that is written and each Chat that has a question, as its own Word export gives it. |
| `01 Recordings/<title>/<the recording's file>` | Only for a Recording made in the app: its original sound, as it was recorded. |
| `02 Case chats/` | Each Case Chat, an Incident's included, as its Word export gives it. |
| `03 Notes and chronology/Notes.pdf` | Every note in the Case: the Recording, the time, who wrote it and when, and the note. Left out when the Case has no note. |
| `03 Notes and chronology/Chronology.pdf` | The case chronology's Word export for every day, when the Case has one. A proposed event that was kept is an event of the chronology and is there. |
| `04 Incidents/<name>/` | The Incident's Chronology; its Memo when one is written; each of its comparisons. |
| `05 Comparisons/` | Each comparison of the Case that is not an Incident's. |
| `06 Map pictures and timelapses/` | Each picture of the map and each timelapse saved to the case's Documents shelf, as the file it is: these were made in the app. |
| `07 Record of clips.pdf` | For each Clip: its name, the Recording's file it was cut from, from when to when and how long, who made it and when, its Incident, whether captions were burned in, its note, and the lines said in it. |
| `08 Recordings and documents, listed.pdf` | Every Recording of the Case with its file name, size, length, upload date, who uploaded it and its SHA-256, and every uploaded document (a report) with its file name, size, pages and date: what to match against the permanent record. A Recording made in the app is marked as in the copy. |
| `09 People and names.pdf` | The Case's People with their roles and other names, and its places and terms. |
| `10 Activity record.pdf` | Every row of the audit log about the Case or anything in it that the log still holds, oldest first: when, who, what, and to what. The page says how far back the log reaches, since the Audit retention setting removes older rows. |

A name that would clash with another in the same folder is told apart with a number, as the zips of v1.242.0 do. Names keep to the characters the Word exports already keep to.

### Making it

- **Who.** The owner and every Collaborator, and an Admin with standing in the Case: whoever can already export each piece. An Admin's is audited with the owner as affected user, as an Admin's exports are.
- **Where.** The case's Details tab, in a part of its own at the foot of the left column, directly above Delete case.
- **In the background.** Turning a Word file into a PDF takes seconds, and a large Case has hundreds of documents. The press queues the work on the `media` queue and the page shows how far it has got ("12 of 31 documents"); the person may leave the page. **Stop** ends it at the next batch and leaves nothing behind.
- **One at a time per Case.** While one is being made the button is the progress line, for everyone who can see the Case.
- **Kept.** The last copy made stays on the Case, with when and by whom it was made, how many documents it holds and its size, until one is made again; the new one replaces it only once it is ready. It is a file in the Case's folder, so it counts toward the owner's room, goes to the Recycle bin with the Case and is wiped with it.
- **Behind the case.** When something in the Case has been added, removed or edited since the copy was made, the part says "behind the case" and offers Make it again first, with the older copy still to download. The app's reckoning is by counts and latest dates of what the copy holds, so opening the Case, which changes nothing in it, never marks a copy behind.
- **When it cannot be made.** A document that cannot be written or turned into a PDF fails the whole copy, and the part names the document. A copy with a hole in it would be worse than none.
- **Downloading** writes one "export made" audit row of kind `preservation copy` and counts as use of the Case.

### The four states, as the page says them

| State | The part reads |
|---|---|
| None made | "none made yet"; one sentence on what the copy is; **Make the Preservation copy**. |
| Being made | "being made"; "N of M documents" with a bar; **Stop**; "You can leave this page. It will be here when it is done." |
| Ready | "ready"; "Made <when> by <whom> · N documents · <size>"; **Download**, **Make it again**; "Save it to the client's file of record." |
| Behind the case | "behind the case"; the same line, and "the case has changed since"; **Make it again**, **Download the one of <date>**. |

A copy that failed reads "could not be made" with the reason, and **Make the Preservation copy** again. Where the PDF maker is not in the build (a development machine), the button is greyed and says so.

### The PDF maker

LibreOffice Writer's no-GUI packages from the Debian the app image is built on, run by the worker as a command, one start for a batch of documents, each start with a profile of its own that is removed after. The facts and their sources are in `docs/research/pdf-maker.md`. Carlito stands in for Calibri, being drawn to the same widths, and DejaVu Sans Mono for Consolas. The image's build converts a document and fails if the result is not a PDF/A, so a broken maker never reaches a server. The maker reaches nothing outside the container.

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

- **A folder for each Recording.** The drawing showed one PDF per Recording holding its Transcript, Summaries and Chats together. The app has no such combined document, so each Recording has a folder holding its Transcript, each Summary and each Chat as the documents the app already exports.
- **Pictures of the map and timelapses.** Not in the drawing. They are made in the app and saved to the case's Documents shelf, so by the chapter's first principle the files go in, in a folder of their own, and the listed document names only what was uploaded.
- **No count before making.** The drawing's "31 documents, about a minute" beside the button is not shown: counting the documents needs most of the work of planning them, and the page shows the count from the moment the making starts.
- **Not on Home.** The drawing said the copy would also be under Ready to download on Home. It is on the Details tab only; Home's list is of the session's own work.

### Left to the build

The batch size and the time allowed per document; the names of the files inside the Recording folders; the wording of the Read me first page within what is fixed above; how the page asks how far the making has got.
