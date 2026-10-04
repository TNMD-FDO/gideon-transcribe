# Gideon Transcribe, Phase 9 specification

The review of many recordings. A Case of hundreds of recordings reviewed by a team: the case page fit for them, the names the engine mishears, the team and the assignments, one page for the notes, a summary for every recording overnight, and a Case Chat that reads what fits. Six chapters, each a release, written 2026-10-04 for the build.

## About this document

This is the build specification for Phase 9 of Gideon Transcribe. One of the office's departments receives dumps of 800 or more jail calls and reviews them as a team of up to ten, today with a spreadsheet of assignments and notes compared by hand. On 2026-10-03 the maintainer asked how the app could carry that work without "introducing workflow into it", then settled over two days of planning what it should carry: the calls in one shared Case, the team visible, the calls divided among the team by an owner, one mark when a person is done with a recording, the notes of every recording read in one place, and Gideon answering across the calls in ways the engine can bear. Every structural change was drawn as a mock-up first (`docs/spec/mockups/phase-9-mockups.html`, one page in the app's own look) and picked by the maintainer before this document was written.

It builds on Phase 1 (`docs/spec/SPEC-PHASE-1.md`, the Upload page, the Queue, the AI assistant), Phase 2 (`docs/spec/SPEC-PHASE-2.md`, Cases, Sharing, the Case Chat), Phase 7 (`docs/spec/SPEC-PHASE-7.md`, Search across a case, Gideon) and Phase 8 (`docs/spec/SPEC-PHASE-8.md`, Notes, the work panel, Home), and changes nothing in them beyond what each chapter's "What changes from earlier phases" lists.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 9 words Case vocabulary, Also heard as, Team, Also an owner, Assigned to, Divide among, Mine, Reviewed, Notes page, Open as a page, Overview, Scope, Pointed to, Summaries tonight), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the Phase 9 rows carry 9 in their Phase column), the mock-up page, and the two decisions this phase records, `docs/adr/0017-every-recording-gets-its-summary-overnight.md` and `docs/adr/0018-over-the-ceiling-the-case-chat-reads-the-overviews-first.md`. The conventions of the Phase 1 document apply unchanged: the spec wins over the code until the maintainer changes it, a decision left to the build is written down, and nothing office-specific enters the repository.

Nothing in this document is office-specific. No new environment key and no new service: everything here is rows, pages and calls the app already makes.

## What Phase 9 adds

- **Fit for 800** (chapter 1): a case page that draws 800 recordings in a moment, a filter box over them, a Notes column, and Download the list, a spreadsheet of the recordings for the office's own tables.
- **Names across many recordings** (chapter 2): the Case vocabulary, names and places with the spellings the engine has been heard to give them, carried into recognition, Search and Gideon; and one sentence that names a Side across every call in the case. No transcript is ever rewritten.
- **The Team, Assigned to and Reviewed** (chapter 3): who is on a case and who owns it, plain to everyone; one mark on a Share, Also an owner; a recording given to one team member, singly, by ticked rows, or by Divide among; and the one mark of completion, Reviewed, made by the assignee on purpose and taken back when wrong.
- **The Notes page** (chapter 4): the incident page's shape without the wall: one recording at one moment on the left, every note of the case on the right, stepping through notes or through a person's calls, the whole call in a pop-out, never a jump away.
- **Summaries tonight** (chapter 5): a tick at upload that writes every recording's summary in the overnight window, the backbone of chapter 6 (ADR 0017).
- **Gideon reads what fits** (chapter 6): the Case Chat reads the recordings a person has narrowed to, and on a whole case over the ceiling reads every recording's Overview first and then the recordings it points to, whole; it says what it read and never refuses for size (ADR 0018).

## Contents

1. Fit for 800
2. Names across many recordings
3. The Team, Assigned to and Reviewed
4. The Notes page
5. Summaries tonight
6. Gideon reads what fits
7. Deferred and ruled out

Appendices: A. Audit rows added in Phase 9. B. Settings added or changed in Phase 9.

## 1. Fit for 800

Written 2026-10-04. The case page was laid out for a case of a dozen recordings. A case of 800 calls has to open as fast, be narrowed as easily, and give the office a list it can take into its own spreadsheet. Nothing in this chapter changes what a page says; it changes how fast and how many.

### Principles

1. **The page opens in a moment whatever the count.** A case of 800 recordings draws its rows from a handful of queries, not one per row. The target is under half a second for the rows.
2. **A long list is narrowed by typing.** The Cases list filters as you type (v1.111.0); the Recordings tab does the same.
3. **The office keeps its spreadsheets.** The app does not replace a department's own table; it gives them the list to put in it.

### The rows

- `_rows_for` is built once per page and from a handful of queries: the recordings with their transcript and uploader, the newest job with its batch per recording, one grouped query for the speakers, one for the incident cameras, one for the notes (count and distinct writers). The two passes over the rows become one.
- **A filter box** over the Recordings tab, "Filter these recordings", narrowing the rows as the person types to those whose title, type or added-by holds the typed text; Enter asks the server for an address that can be shared, as the Cases list does. The box is the Scope of chapter 6.
- **A Notes column**: "3 notes, A. Okafor and D. Chen", two writers named and then "and N more"; "none" muted when there are none. The notes on lines and the notes at moments are counted together; the column links to the Notes tab filtered to that recording's writer when one.
- **Download the list**, a small button at the head of the Recordings tab: a CSV file, `<case>-recordings.csv`, UTF-8 with a byte order mark so a spreadsheet opens it with its accents intact, one row per recording: title, type, date added, added by, length, state, speakers (named and unnamed counts), notes (count), note writers, and from chapter 3 the assignee, reviewed by and reviewed on. One audit row, **Case list downloaded**, with the count; never a title in the row.
- **The Notes tab's rows** gain what chapter 4 needs and the tab does not show: the recording's id, its type, the moment in seconds and the writer's id; the one incident-camera query per row becomes one per case.

### In and out

- **In**: the queries, the filter box, the Notes column, Download the list, the Notes tab's hidden fields.
- **Out**: paging the Recordings tab (every row is drawn, the filter narrows); a spreadsheet in Excel's own format (a CSV opens in Excel with one click and needs no new package); any change to what a row says.

### What changes from earlier phases

- **Phase 2 chapter 1**, the Recordings tab: the filter box, the Notes column and Download the list. The chapter's "left to the build" default sort stands: newest added first.
- Nothing else.

### Audit rows

Category Exports: **Case list downloaded**, with the recordings' count. Never a title.

### Settings

None.

### Left to the build

- The CSV's column order and the exact words of its header row, in the glossary's words.
- Whether the filter box also matches the Description. The picture here is title, type and added-by.

## 2. Names across many recordings

Written 2026-10-04 from the maintainer's words of the same day: "across 800 calls things like names and places can be close but not appear the same; 'von carutthers' might be heard as 'voncaruther'". The engine mishears names, and nothing in the app lets a case say what it has learned about them. This chapter gives the case a list of names and places with the spellings the engine has given them, used everywhere the app reads, and one sentence that names a voice across every call.

### Principles

1. **The transcript is never rewritten.** What the engine heard stays what the engine heard, marked where a person corrected one line by hand (Phase 1's Correction). The app learns the spellings and uses them when it recognises, searches and reads; it does not change the record.
2. **Told once, used everywhere.** A spelling typed on the case is carried into the next upload's recognition, into Search and Find, and into what Gideon is told, without a second typing anywhere.
3. **The People are the names.** A Person named on the Speakers tab is a vocabulary entry by itself; the Case vocabulary adds the places and the people who never speak.
4. **One voice, many calls.** On a jail call one side is the same person on every call and the other is anyone. The case says so once.

### Words

**Case vocabulary**: the list a Case keeps of names and places, each with its **Also heard as** spellings, carried into every recording added to the Case, into Search and into Gideon. **Also heard as**: the spellings the engine has been heard to give a name, listed on its entry; a Search hit by one is marked so. **Named across the case**: the rule, set once on the Speakers tab, that a Side of every two-channel call in the Case is one Person.

### The Case vocabulary

- **Where.** A block of its own in the case page's right pane, under the Team (chapter 3), "Case vocabulary, 14 names and places", with one sentence under the heading saying what it does: "They go with every recording added here and with Process again. Search and Gideon read the spellings too. The People from the Speakers tab are here by themselves." The Notes page's Details tab (chapter 4) shows the same block.
- **An entry** is a name or a place, up to 120 characters, and its Also heard as spellings, up to twenty, each up to 120 characters, typed with commas. A Person of the Case is an entry by itself, shown with its Role and "from the Speakers tab", its name not editable here (the Speakers tab renames it) and its spellings editable here. A removed Person's entry goes with it.
- **Who.** Everyone with the case may add an entry or a spelling; the Owner and an also-owner (chapter 3) may remove one, as they alone remove a person from the Team. An Admin as the Admin.
- **Recognition.** Every recording added to the Case, at upload or by Move to case followed by Process again, carries the Case vocabulary as its Vocabulary ahead of the Batch's own and after the Office Vocabulary (Phase 1 chapter 7's order gains the Case's list between the two). The names go, not the spellings: a spelling is what the engine got wrong, and is never sent as a thing to recognise. The Upload page's Add to case says in one line "This case's 14 names go with these recordings". Process again on a recording in the case carries the list as it stands, so the calls that matter can be transcribed again once the team knows who is in them.
- **Search and Find.** The close forms (Phase 7 chapter 3, v1.97.0) gain the spellings as forms of their name: a search for a name also lights its Also heard as spellings, marked **also heard as** the way a near spelling is marked close, after the exact hits, and only where the spelling is written in what is searched. A typed name of two words is also tried joined ("voncarutthers") and a typed word that holds a listed name joined is tried split, since a joined or split name is the engine's commonest slip. The trigram rule and its floor stay as measured (`docs/research/close-matches.md`). The Search tab's line under the count says how many hits are marked also heard as and which spellings were looked for. The Notes page's Find (chapter 4) reads the same way.
- **Gideon.** The People line that opens every Case Chat call carries each entry's spellings, "Von Carutthers (Defendant), also heard as voncaruther, van caruthers", and the places after the people. The Case chat template and chapter 6's selection template gain one sentence: names and places may be misheard, and a spelling listed as also heard as is the same person or place. The overviews read first (chapter 6) carry the slips, so the sentence matters there most.

### Named across the case

- **Where.** On the Speakers tab, over the Recordings still unnamed, one line for a Case holding two-channel calls: "On every call in this case, Side 1 is [a Person]", with the Person picked or typed as the Speakers page's name box has it, and the Side chosen (1 or 2). Saving it names that Side's Speaker on every two-channel call in the Case that has a transcript, now and as each later one lands, as that Person; the other Side stays its label ("Caller", the engine's) until a person names it on that call.
- **The rule is the Case's**, shown on the tab with Change and Remove; a call whose Side was named by hand keeps the hand's name, and the tab says how many calls the rule named. Remove leaves the names as they stand.
- **Recordings that are not two-channel calls** are untouched by the rule.

### In and out

- **In**: the Case vocabulary block, its entries and spellings, who may do what; the names into recognition; the spellings into Search, Find and Gideon; the joined and split forms; the Side named across the case.
- **Out**: find-and-replace across transcripts; a spelling sent to the engine as a thing to recognise; a Case vocabulary outside a Case (the Workspace keeps the Batch's Vocabulary alone); matching by sound.

### What changes from earlier phases

- **Phase 1 chapter 7**, Vocabulary: the order becomes Office Vocabulary, Case vocabulary, the Batch's Vocabulary. Process again carries the Case's list.
- **Phase 2 chapter 5**, People: a Person is a Case vocabulary entry by itself and may carry Also heard as spellings; the Speakers tab gains the rule that names a Side across the case.
- **Phase 7 chapter 3**, close matches: the spellings as forms, marked also heard as; the joined and split forms.
- **Phase 2 chapter 7**, the Case Chat: the People line carries the spellings; the template's sentence.

### Audit rows

Category Cases: **Case vocabulary added**, **Case vocabulary changed**, **Case vocabulary removed**, with the count of entries after the change and never a name or a spelling (as Vocabulary is treated today); **Side named across the case** with the Side's number and the count of calls named, never the Person's name.

### Settings

None.

### Not in this chapter

- **A vendor's metadata sheet** for a dump (the number dialled, the inmate's id): a later chapter, when an office has one to read.
- **A spelling corrected across transcripts**: ruled out; a Correction is one line, by hand, marked.

### Left to the build

- The joined and split forms' exact rule (how many words a name may hold; whether a joined form under four letters is tried).
- The rule's wording when a Case holds both two-channel calls and single-channel recordings.

## 3. The Team, Assigned to and Reviewed

Written 2026-10-04 from the maintainer's words over two days. First: "I don't want to recreate their workflow"; then: "I want to be able to create assignments but I don't want to start getting into roles and who can assign and this that and the other. But I want it to be transparent as to who is going to work on each; maybe the owner could add the folks and be the one who assigns, and could indicate someone as an owner so they could do it instead. I just want it to be clear to all who is on the team and who the owner is"; then: "how does an assignee mark it complete? I don't want it to be so easy that they accidentally mark it complete, but intuitive enough that it in fact gets marked when complete". The mock-ups were drawn from these words and picked the same day.

### Principles

1. **Who is on the case and who owns it is plain to everyone.** The Team is one list every member sees, the Owner first.
2. **One mark, not a role.** An Owner may mark a Collaborator also an owner, so they may add people and assign as the Owner does. Nothing is narrower than a Collaborator: the glossary's rule that a Share has no levels stays true, and this one mark widens.
3. **Assigned says who, never whether.** A recording's assignee is one team member. The notes on it and their writers stay the signal of work, as before this chapter.
4. **Reviewed is one mark, made on purpose and taken back when wrong.** The assignee marks a recording Reviewed when done with it; the mark asks one question that carries what the app knows, and it is reversible. There is no other state: no taken, no in progress, no done.
5. **Nothing is overdue.** A recording assigned and not yet reviewed is work, not a warning; it never puts a case under Needs you.

### Words

**Team**: everyone with a Case, the Owner first and then each Collaborator, each with when they last opened the case, how many recordings are assigned to them, how many they have reviewed and how many they have noted; one list seen by all of them. **Owner**: the one person a Case belongs to, who created it or was handed it; the quota and the retention clock are theirs, with Rename, Transfer and Delete. **Also an owner**: the one mark an Owner may put on a Collaborator's Share so they may add people and assign; Rename, Transfer, Delete and the mark itself stay the Owner's. **Assigned to**: the one team member an owner has given a Recording to work on. **Divide among**: the owner's one press that deals the Case's unassigned recordings evenly, in date order, among the ticked team members. **Mine**: the Recordings tab's filter for the recordings assigned to the person looking. **Reviewed**: the assignee's mark that their work on a Recording is complete, with who and when; taken back with **Not reviewed after all**. Not "Done": that word is a Recording's transcription state.

### The Team

- **Where.** The owner's "Shared with" panel becomes the **Team** block in the case page's right pane, seen by every member, with **Add people** beside the heading for those who may. The Team block is the first in the pane after the case's own facts; the Case vocabulary (chapter 2) follows it.
- **The rows.** The Owner first with an **Owner** pill; then each Collaborator by name, an **Also an owner** pill when marked, and a muted line: when they last opened the case, "80 assigned", "61 reviewed", "70 noted", the first two linking to the Recordings tab filtered to that person. A Collaborator who is deactivated or blocked is greyed with the status pill, as the panel showed them. The person looking sees "(you)" on their own row and, as a Collaborator, **Leave this case** there.
- **The controls** are by standing, not by a second page: an Owner sees an **Also an owner** tick and **Remove** on each Collaborator's row; an also-owner sees Remove alone; a Collaborator sees the list. Add people is the share flow as it stands (the picker of colleagues, the "case shared with you" mail, the audit row); the page says Add people, the dialog and the mail keep saying shared.
- **Also an owner.** The tick sets `also_owner` on the Share. An also-owner may add and remove people and may assign, unassign and divide; they may not rename, transfer or delete the Case, and may not mark or unmark the tick. Transfer to an also-owner clears their mark, since the Owner needs none. Removing a Collaborator who is also an owner removes both.
- **Removing a Collaborator** clears their assignments: the confirm says so with the count ("M. Lindqvist will no longer see this case. Anything they added stays in it; their 80 assigned recordings become unassigned."). Transfer leaves every assignment as it is.

### Assigned to

- **The fields.** On a Recording in a Case: the assignee, who assigned, when. Empty outside a Case, like the Recording type. No history table: the audit log is the history.
- **Folded until used** (v1.121.2, at the maintainer's word after the first walk: an incident case reviewed by one person was wearing the whole apparatus). While nothing in the case is assigned, an owner sees one secondary button on the Recordings tab, **Divide the work**, and no tick column, bar, pills or Assigned to column; the button unfolds them on the page. Once any recording is assigned, or the list is narrowed by a pill, the tools are open for everyone with the case. A collaborator never sees the button.
- **Three ways to assign**, all an owner's or an also-owner's: a select in the row's detail fold beside the Type ("Assigned to: nobody, M. Lindqvist, ..."); a tick column on the Recordings tab with a bar that reads "3 ticked: Assign to..., Unassign" (Assign to opens the app's prompt over the team's names, "Assign 3 recordings to", with one line of words: "They see them under Mine and on Home; nothing else changes"); and **Divide among**, a card under the bar: "Divide the 240 unassigned recordings among the people you tick, in date order", a tick per team member, the count each would get, Divide and Cancel. Divide deals only the unassigned recordings, oldest added first, one to each ticked person in turn, the remainder to the first ticked; it never moves an assignment somebody made.
- **Unassign** on ticked rows or "nobody" in the fold clears the assignee. A new assignee on a reviewed recording clears its Reviewed mark (the review was the old assignee's).
- **Handing over.** When a reviewer is away, the owner filters to that person and not reviewed, ticks all, and assigns to another. The filters combine (a person, a state) to make this one motion.
- **Where it shows.** An **Assigned to** column on the Recordings tab beside the Notes column (chapter 1), "M. Lindqvist", or "nobody" muted; the filter pills over the table, **All**, **Mine**, **Mine, not reviewed**, **Reviewed**, **Unassigned**, and one person's via the Team's links (`?who=<username>`), combining with the filter box; a pill in the recording page's head, **Assigned to you** or **Assigned to M. Lindqvist**; on the Notes page (chapter 4) the group heads and the Recordings tab carry the assignee; in Download the list (chapter 1) the three columns.
- **On Home and the Dashboard line**: "412 of 812 reviewed" for everyone with the case, and for the person looking "6 of 80 left for you", both plain pills linking to the Recordings tab (the second to Mine, not reviewed), never in the warning tone.
- **What assigning is not.** Not a mail: Home is the signal, and a Divide across ten people would otherwise send ten mails at once. Not a lock: anyone with the case may open, play and note any recording. Not a state: the Notes column is the only sign of work until Reviewed.

### Reviewed

- **Where it is made.** A button **Mark reviewed** in the recording page's action line, after Find in transcript and before New clip, shown to the assignee and to owners on an assigned recording (to owners it reads the same and marks for the assignee); and the same button in the Notes page's foot (chapter 4). A plain secondary button, never the page's primary: found when looked for, not pressed by reflex. The key **R**, with a row not being typed in, opens the same question and never marks without it.
- **One question first**, with what the app knows: "Mark call 0417 as reviewed? You have left 2 notes on it. The team will see it as reviewed by you, today." with **Mark reviewed** and **Not yet**; when the person has left no note on it: "You have left no note on it. Mark it reviewed with nothing to note?" with **Nothing to note, mark it** and **Not yet**. The answer is recorded with the mark, so the record says which recordings were heard and had nothing in them.
- **Taken back.** A toast, "Marked reviewed. Undo", for a few seconds; after it, **Not reviewed after all** stands in the action line as a quiet ghost button, for the assignee and for owners. Both are audited. Nobody else's note or press ever marks or unmarks a recording.
- **After the mark**, the toast on the recording page carries "Next: call 0526", the person's next assigned recording not yet reviewed, in date order, so the loop of listen, note, mark, next is one press on the recording page as it is on the Notes page. On the Notes page in call mode the next call opens by itself (chapter 4), Undo still there.
- **Where it shows.** A green **Reviewed** pill with the date in the Assigned to column; **Reviewed by you, 4 Oct** in the recording page's head in place of Assigned to you; the Team's "reviewed" count; the filters; the Notes page's group heads; Download the list's two columns.
- **For any recording in a Case**, not only calls: a body camera video is assigned and reviewed the same way, on its own recording page. An Incident is not a recording and is not assigned; its cameras are.

### In and out

- **In**: the Team block and its rows; Add people as the share flow's name on the page; the Also an owner mark and its gate; Assigned to by fold, by ticked rows and by Divide among; Unassign; the filters and their combining; the pills on the recording page, Home and the Dashboard line; Reviewed with its question, Undo, Not reviewed after all and Next; the key R; the audit rows.
- **Out**: a mail for an assignment or the mark; a second level of Share; a Reviewed mark by anyone but the assignee or an owner; an in-progress, taken or done state; a recording assigned to two people; an Incident assigned; a case under Needs you for work waiting.

### What changes from earlier phases

- **Phase 2 chapter 2**, Sharing: principle "one level" gains "with one mark, also an owner, which widens"; the who-may table splits its last row (Share and remove: Owner, also-owner, Admin; Rename, Transfer, Delete, and the mark: Owner and Admin) and gains "Assign, unassign, divide: Owner, also-owner, Admin" and "Mark reviewed: the assignee, Owner, also-owner, Admin"; "the owner's Shared with panel" becomes the Team, seen by everyone; "Removing a Collaborator: anything they added stays" gains "their assignments clear".
- **Phase 2 chapter 1**, the Recordings tab: the tick column, the bar, the Divide among card, the Assigned to column, the filter pills, the fold's select.
- **Phase 1 chapter 8**, the recording page: the pill in the head, Mark reviewed in the action line, Not reviewed after all, the key R in the shortcuts overlay.
- **Phase 7 chapter 3**, the Dashboard line, and **Phase 8 chapter 13**, Home: the two plain pills.
- **Phase 2 chapter 3**, Retention: assigning and marking count as Last activity.

### Audit rows

Category Cases, metadata only: **Recording assigned** (the assignee's username, the cause: one, ticked, divided), **Recording unassigned** (the cause: owner, share revoked, moved, reassigned), **Recording marked reviewed** (the cause: assignee, owner; whether with nothing to note), **Recording marked not reviewed**, **Case owner added**, **Case owner removed** (the Collaborator's username). Divide writes one Recording assigned row per recording, as the Recycle bin writes one per recording, so the record says who was given what; the Audit log page groups the rows of one Divide under one line, "Recordings divided among 4 people: 240", opened to the rows. Never a title, never a note's words.

### Settings

None. The Team needs Sharing, as the panel did; assigning needs Folder management, as the case page does.

### Not in this chapter

- **A mail or a digest of what is assigned to you**: a later chapter if the office asks; Home carries it today.
- **A mark on a note for the attorney's attention**: a later chapter.
- **Assigning by caller or by number**: the dump's metadata is not read (chapter 2, Not in this chapter); Divide deals in date order.

### Left to the build

- The prompt's exact words for Assign to and the Remove confirm, within the words above.
- The toast's duration and the key R's place in the shortcuts overlay.
- Whether the Team block folds past ten people ("4 more: ...") or scrolls; the picture here folds.

## 4. The Notes page

Written 2026-10-04 from the maintainer's question of 2026-10-03, "how do we have that info land in a single pane, something like we already do for incidents without the video features", and from three mock-ups and a working demo, of which A was picked: the incident page's shape without the wall. On 2026-10-04 the maintainer asked that Open the call never leave the page abruptly: "a popout like we've already done for case chat, with the option to open the full call from that popout". The Memo tab the first drawing carried was dropped the same day: the maintainer saw no purpose in a memo across the case, and Gideon over the transcripts and the notes, with Download notes, is enough.

### Principles

1. **The Note is the spine**, as the Event is on an incident. The page is the office's notebook for the case on the right and the recording opened to whichever page of the notebook you are pointing at on the left.
2. **The wall is gone; the rule stays.** The incident page's rule (Phase 8 chapter 1) holds: tabs for what is always there, layers for a job in hand, Back and Close return exactly, and nothing opens above the left side or pushes it.
3. **Never a jump away.** Opening the whole call is a pop-out over the page; the page is where the person came back to.
4. **It is the Case's page**, not a new grouping. Every recording in the case is on it, and the type pills narrow.
5. **No state the app invents.** The page shows the assignments and the Reviewed marks of chapter 3 and the notes; nothing more.

### Words

**Notes page**: the Case's work page for its notes, reached by **Open as a page** on the Notes tab: the recording in hand on the left, the work panel (Notes, Recordings, Details) on the right. "Pane" is not its name: the glossary gives that word to the case page's right column.

### Reached

- A secondary button **Notes page** in the case page's head beside Add recordings, on every case (since v1.121.1, from the walk of 2026-10-04; until then Open as a page beside Download notes on the Notes tab, which read as an export and was absent on a case with no notes), and each Notes tab row's link may carry the note so the page opens on it; else the page opens on the first note in call order. The rail folds to icons on the page, as on the incident page, and the page takes the whole width.

### The left: the recording in hand

- **The head**: the recording's title, its type pill, its length, Summarised when it is, **Assigned to you** or the assignee's name and **Reviewed** when marked, and the muted facts (date added, added by, note count). **Open the call** opens the pop-out below.
- **The player bar** is the page's: Play, -5s, +5s, the time over the length, Speed, Boost, the sides on a two-channel call. The waveform under it carries every note of the recording as a mark and the playhead.
- **The lines around the moment**, as the Preview shows them (Phase 7 chapter 5, v1.98.0), following the sound, with the lit line's note in its box under it, editable and removable where it sits, and a new note written on any line as on the recording page. The line cap the floating Preview has is lifted here.
- **The foot**, two modes. From the Notes tab: **Previous note**, **Next note**, "Note 212 of 1,204" ("of 312 shown" when the list is filtered), stepping through the notes listed on the right in call order, into the next recording when the notes run out. From the Recordings tab (Listen on a row, or the Mine, not reviewed filter): **Previous call**, **Next call**, "Call 3 of 6 left for you", each opened at its start. In both modes **Mark reviewed** stands at the right of the foot, with chapter 3's question, and after the mark the next call opens by itself with Undo in the toast. The Overview of the recording's summary (chapter 6's word) is under a fold at the foot.
- **Call order** is the order recordings were added, oldest first, then the moment within a recording. (A date read from the file is not in this phase; see chapter 7.)

### The pop-out: the whole call

- **Open the call**, in the head or on a group head's Open, opens the whole call over the Notes page, which stays behind, dimmed, exactly as it was: the Preview grown to the whole recording. The pop-out carries the head's facts and pills, **Mark reviewed**, **Export** and **Open the full call** in its head with Close; the player bar with Follow; the waveform with the notes marked; the full transcript, the current line lit with its note editable under it and a **note** mark on every noted line; beside the transcript, the recording's summary in its parts and the Speakers with their sides.
- **Playback moves with it.** The pop-out takes the sound from the left at the same moment and hands it back on Close, so nothing plays twice.
- **Two ways out.** Esc or Close returns to the notes exactly where they were, the layers' rule. **Open the full call** leaves for the recording page, for its clips, its Speakers page and its chat, the one door out.

### Notes on events

Since v1.121.1: a note on an incident's event is on the page too, listed under the camera the event sits on (its own camera, else the placed camera running at that moment), at the event's moment on that camera's clock, marked "on the event" with the event's time of day; pressing it plays the camera there and the note is shown under the nearest line read-only, since the chronology owns it, with a link to the event. The lead counts them apart ("7 notes on 3 of 4 recordings: 4 on lines, 3 on events").

### The right: the work panel

- **The tab bar**: **Notes** with its count, **Recordings** with its count, **Details**, and the Find box at the right end. The incident page's bar and panels, drawn the same.
- **Notes.** Filter pills by writer (All, each person with their count, folded past four) and by Recording type; the list of every note in the case grouped under its recording, in call order, scrolled whole without paging. A group head: the recording's date and time, its number or title, its note count, the assignee and a Reviewed pill when marked, and Open; the group whose recording is in hand is tinted and carries a small play mark. A row: the time in the recording, the note's words, the line's words in italics, the writer and the date; the row in hand is lit, scrolled into view as the left moves. Pressing a row opens that moment on the left. The foot: "388 recordings have no note yet", Download notes (the Notes tab's Word document) and Download the list (chapter 1).
- **Recordings.** The case's recordings with the filter box and the pills of chapter 3 (All, Mine, Mine, not reviewed, Reviewed, and the type pills); a row: title, date, assignee, length, notes ("2 notes, you and J. Brennan", "none yet"), **Listen**, which opens the recording on the left at its first note or at its start and puts the foot in call mode.
- **Details.** The case's figures (recordings, hours, size, summaries written and tonight's), the Team block and the Case vocabulary block as the case page has them, and the downloads.
- **Find.** The box in the tab bar searches the case's notes and the recordings' words, exact hits then close matches and the Case vocabulary's spellings (chapter 2), after 300 ms and two characters; hits open as a layer over the tabs with the incident page's head (Back, the count, Enter for the next), and a press opens the moment on the left. Never logged. The case page's Search keeps the rest (memos, summaries, clips, documents).
- **Gideon** is the drawer as on the case page, reading the Scope the pills and the filter set (chapter 6).

### Keyboard

- Space plays and pauses; the arrow keys, or J and K, step to the next and previous note or call as the foot's mode has it; N writes a note on the lit line; R opens Mark reviewed's question; Esc closes the pop-out or a layer. The recording page's **Keyboard shortcuts** overlay, under More, is on this page too with this page's list; a person who has never opened it is told once, in a quiet line at the foot, that it exists.

### Layout

- A grid like the incident page's desk: the left `minmax(0, 1fr)`, a grip, the work panel 460 pixels wide and resizable from 360 to three fifths, its width kept in the browser under the page's own key. At 1366 wide the left is about 780 pixels. Under 1280 wide one column, the left first with its player bar sticky at the top so stepping stays reachable while reading the list below; under 700 the Recordings tab's rows are cards, as every table is. The pop-out is a sheet from the bottom under 900 wide, as the Preview is.

### In and out

- **In**: Open as a page; the left with its head, player bar, waveform, lines, note box and two-mode foot; the pop-out with its two ways out; the three tabs, the Find layer, the pills and the grouped list; Gideon; the keys and the overlay; the layout at every width.
- **Out**: a Memo tab (dropped 2026-10-04); a note the page writes for anyone; paging the list; a new grouping of recordings; any state beyond chapter 3's.

### What changes from earlier phases

- **Phase 8 chapter 2**, the Notes tab: Open as a page. **Phase 7 chapter 5**, the Preview: it mounts into a page as well as floating, and grows to the whole recording as the pop-out. **Phase 8 chapter 1**: the work panel's shape on a second page. **Phase 1 chapter 8**: the shortcuts overlay on a second page.

### Audit rows

None new. Opening the page as an Admin who is not a member writes the admin access row the case page writes; note writes are audited as Phase 8 chapter 2 has them, never a word; Download notes and Download the list are their own rows. Nothing for a read, a find or a filter.

### Settings

None. The page needs Folder management, as the case page does.

### Not in this chapter

- **A memo across the case**: dropped; see chapter 7.
- **The page for a case of videos with incidents**: the page works for any recording, and an incident's cameras are recordings; the incident page stays the place for the cameras in step.

### Left to the build

- The pop-out's size on a desk monitor and whether it may be dragged, as the Preview may.
- How a note of many lines is drawn in its row, and how a long line's words are shortened under it.
- The quiet line that tells of the shortcuts overlay, and when it stops showing.

## 5. Summaries tonight

Written 2026-10-04. Phase 1 chapter 17 ruled out "Summarise all": summaries were asked for one recording at a time, and the answer to "tell me about all of these" was the Case Chat. A case of 800 calls has no Case Chat that fits (chapter 6), and 800 presses of New summary is not a thing a person does. This chapter writes every recording's summary in the overnight window, the Vision flow's own pattern, and ADR 0017 records the reversal.

### Principles

1. **Asked for once, written at night.** One tick at upload; the engine's daytime is untouched, so the reviewers' questions and the office's other project run as before.
2. **The summary is the one the person would have asked for.** The recording type's template, Standard length, no Focus; the same Summary a press of New summary gives.
3. **Not reached means tonight again.** A night that runs out leaves nothing failed.

### Words

**Summaries tonight**: the tick on the Upload page that writes each recording's summary in the overnight window, and the night's run of them. **Overview**: the first part of a Summary (its Overview or Summary heading), read in place of the Transcript by chapter 6.

### The tick and the mark

- **On the Upload page**, under the Vision tick, **Write each recording's summary tonight**, offered when the Summary is On and the upload goes into a Case (a session recording is gone by night), with the line "Written in the overnight window, oldest first; on Home and the case page you see how many are left". Its default is the setting below. The Batch keeps the tick and each Recording the mark.
- **On the case page**, when recordings in the case have no summary, the head offers **Write the 388 missing summaries tonight** to anyone with the case; one press marks them.
- **When a transcript lands** with the mark, a Summary row is made in the state **tonight** with the template `chosen_for` the recording, Standard length and no Focus. The case page's row shows "summary tonight" in the muted tone; the Dashboard line and Home carry "Summaries tonight: 198".

### The night

- `mind_the_night` gains a second branch: inside the window, when the night's vision work is not running, the oldest tonight summary is handed to the summary worker; one at a time by default, two at a time when the setting below says so. A recording whose vision is also tonight waits until its picture is done, so its summary is written from the words and the picture together. When the window closes with summaries waiting, each is marked not reached and tried the next night, as a video is.
- **The window** is the Vision page's, Overnight from and Overnight until; the page's wording says "the overnight window: vision, then summaries".
- **The mail.** The Batch-finished mail gains one line when summaries are scheduled, "Each recording's summary will be written tonight". No new mail.
- **How heavy.** A 15-minute call is about 3,000 to 4,000 tokens read and up to 1,600 written; the app's starting figure is 90 seconds a summary (the Expectation's own) and once the office has three runs behind it the real median is used. The window is ten hours. One at a time, 800 calls take about two nights; two at a time, one night. The real figure is read from the office's expectation rows after the first night and written in the box ledger's log, since GIDEON owns the engine.

### In and out

- **In**: the tick, the mark, the case page's offer, the tonight state, the night's branch, the waiting on vision, not reached, the mail's line, the pills.
- **Out**: summaries written in the daytime by this flow (New summary is as it was); a summary of a session recording tonight; a second window.

### What changes from earlier phases

- **Phase 1 chapter 17**: "no Summarise all" is reversed for the overnight window alone (ADR 0017). **Phase 1 chapter 5**: the Upload page's tick. **Phase 4 chapter 5**: the overnight window is shared and its page says so. **Phase 2 chapter 8**: the Batch-finished mail's line.

### Audit rows

Category AI: **Summaries scheduled** (the count, the case), and the summary rows as they are written today.

### Settings

- **Summaries tonight starts ticked** (AI assistant page): On or Off, default Off.
- **Summaries at once overnight** (Vision page): 1 or 2, default 1.

### Left to the build

- The exact order between vision and summaries inside the window (vision first, then summaries, or interleaved), within "one or two at a time and the summary waits for its picture". Decided in v1.120.0: vision first; a summary is handed over only on a minute when no video is queued or being enriched, and a recording whose own vision is tonight keeps its summary until its picture is done.

## 6. Gideon reads what fits

Written 2026-10-04 from the maintainer's words of 2026-10-03: "the context window may not allow it; we need to find smart ways chat could work and build out so the limitations are implicit and not forced; the app only does what it can do". Phase 2 chapter 7 reads every Transcript in the Case in Readings and refuses over a ceiling of hours. A case of 800 calls is 200 hours of talk, more than thirty Readings a question and a refusal at the default ceiling. This chapter makes the limit implicit: Gideon reads the recordings a person has narrowed to, and on a whole case over the ceiling reads every recording's Overview first and then the recordings the overviews point to, whole. ADR 0018 records the decision.

### Principles

1. **Never a refusal for size.** A question always has a way to be answered; the drawer says what was read.
2. **The person's narrowing is the scope.** What is in view on the page is what Gideon reads, without a picker.
3. **The Overview is the Summary's first part, not a new artefact.** Nothing is indexed, embedded or kept for this.
4. **The words are read whole.** The recordings the overviews point to are read as the Case Chat reads today, so citations are to real lines.
5. **Honest about what was not read.** Recordings without a summary are named, and "Write the summaries tonight" is one press away.

### Words

**Scope**: the recordings a question is put to: the whole Case, or the recordings narrowed to on the page by the filter box, a Search's hits, or the Notes page's pills. **Pointed to**: the recordings the overview pass names as bearing on the question, in order of relevance. **Overview**: chapter 5's word.

### The scope

- **The page keeps one scope.** The case page's Recordings tab (the filter box, the pills of chapter 3), its Search tab (the hits' distinct recordings) and the Notes page (the writer and type pills, the Recordings tab's filters) each set it as the person narrows; clearing them clears it.
- **The drawer's head** says what it will read: "This case", "Reads the 14 calls you have narrowed to", or "Reads the overviews of 812 calls first, then the calls they point to". The question is posted with the scope's recordings; the server keeps only those in this Case with a Transcript and names the rest as skipped.
- **Per question, not per chat.** The scope is kept on the turn, so one chat may mix a narrowed question and a whole-case one, and the export prints under each question what was read.

### The routes

Decided by one rule the page's expectation and the task both use:

- **Narrowed, within the ceiling**: the narrowed recordings read whole, in Readings as today; one Reading when they fit, and the answer is one call.
- **Whole case, within the ceiling**: as today.
- **Over the ceiling, with any Overview available**: the two passes below, over the whole case or over the narrowed set when a narrowed set is itself over the ceiling.
- **Over the ceiling, with no Overview at all**: today's Digest fallback and, failing that, the refusal, the one place `llm_case_too_large` survives; the answer says "No recording in this case has a summary yet" and offers Write the summaries tonight.

### Pass one: the overviews

- **The input**: the People line with the spellings (chapter 2); one short line per recording (its number, title, type, date, length) and its Overview, cut at a sentence end to a per-recording budget so that every recording fits one Reading (about 100 tokens each at 812 recordings; only under 60 tokens is pass one itself split into two selection Readings and the picks merged by rank); the chat's earlier questions, not their answers; the question.
- **The answer**, under a schema: the recordings that bear on the question in order of relevance, each with one line of why, at most the setting "most recordings the overviews may point to"; or none, with a note. Written without thinking and with the facts sheet's sampling (ADR 0016), as a selection is data, not prose.
- **The template** "Case chat: which recordings", on the Templates page with Reset to default, carries chapter 2's sentence about misheard names.

### Pass two: the recordings pointed to, whole

- The picks in relevance order are taken until their whole transcripts fill the allowed Readings (the setting "Readings after the overviews", default one), then put back in upload order and read exactly as today's Readings are: the same header lines, the notes blocks, the incident blocks, the combining call when there is more than one Reading, the same citation rules and checks.
- **The answer's first line** says what was read: "Read the overviews of 812 calls, then 11 calls whole", or "read 20 of the 31 it pointed to; narrow the question for the rest", and "17 recordings have no summary yet and were not read" with the offer. The turn keeps the picks, their reasons, the counts and the recordings read, so the page and the export can say it again.
- **A whole-case question is two large calls**, about 100,000 tokens in each, three to four minutes expected against the fifteen-minute question limit: lighter than today's worst legal question of twenty Readings, and new load where there was a refusal. One line in the box ledger's log at the Release says the load's shape changed.

### The Overview

- From the newest done Summary of the current Transcript (a Summary of an earlier Transcript is of other words and is marked so); the part after its Overview or Summary heading up to the next heading; failing that heading, the first part; a text with no heading, its first 600 characters cut at a sentence end. "Overview" joins the headings the app knows.

### In and out

- **In**: the scope and its sources; the drawer's head line; the four routes; the two passes with their template, schema, budget and settings; the Overview's rule; the first line of the answer; the turn's record; the audit fields.
- **Out**: an index, embeddings or anything kept between questions; a picker of recordings; a summary written by this chapter; reading the overviews within the ceiling (the words are read whole whenever they fit).

### What changes from earlier phases

- **Phase 2 chapter 7**: the size rule's "The ceiling" bullet is rewritten: the setting "Case chat: most hours of talk per question" becomes **Case chat: hours of talk read whole per question** (the same key and range), the size at which the two passes take over, and refuses only when no Overview exists; a Scope bullet and an "Over the ceiling, the overviews first" bullet are added; "Nothing between questions" stands with one sentence: the Overviews are the Summaries the office already asked for, kept for their own sake, and no index; the Deferred chapter's "a picker to narrow a Chat" is replaced by the page's narrowing; the Reason classes row narrows `llm_case_too_large` to the no-summary fallback.
- **Phase 7 chapter 5**, Gideon: the head line says what it reads.
- **Phase 8 chapter 2**: the notes are read in pass two as today.

### Audit rows

The **case chat turn** row gains the route, the counts of overviews read, recordings pointed to, read whole and without a summary, and the scope's kind and count. Never the question, a reason, a filter's or a Search's words, or an Overview.

### Settings

- **Case chat: hours of talk read whole per question** (Limits): the row renamed, same key, 6 to 600 hours, default 120.
- **Case chat: most recordings the overviews may point to** (Limits): 5 to 60, default 30.
- **Case chat: Readings after the overviews** (Limits): 1 to 4, default 1.
- **Case chat: which recordings** (Templates): the selection template, version 1, Reset to default.

### Before it ships

No wording ships untried, the repository's rule. From `llm-worker` on the office's largest case: the Overview lengths the Jail call template gives, pass one's seconds and picks for five questions the maintainer writes and judges by ear and by eye, pass two's seconds; recorded as counts in `docs/research/case-reads-what-fits-probe.md`, the selection template's wording settled there. The chapter is the last release of the phase and is held if the probe disappoints; the review loop of chapters 1 to 5 does not depend on it.

### Left to the build

- The per-recording budget's exact arithmetic and the threshold for splitting pass one. Decided in v1.121.0: the budget is the Reading size less the fixed parts (the system message, the People line, the earlier questions, the question, the selection cap and a margin) divided by the recordings, never under 24 tokens; under 60 tokens pass one is split into two halves and the picks merged by rank (the first pick of each half, then the second); an Overview is cut at the last sentence end inside about three characters a token.
- The schema's field lengths and the selection answer's cap. Decided in v1.121.0: a why of 160 characters, a note of 240, the picks capped by the setting, the answer capped at 4,000 tokens.
- The words of the drawer's head line while a question is in flight ("Reading the overviews of 812 calls..."). Decided in v1.121.0: "Reading the overviews of 812 recordings..." while pass one runs, "Reading 11 recordings whole..." while pass two does.

## 7. Deferred and ruled out

- **A memo across the case** (a facts sheet from the notes and the overviews, then a memo, like the Incident memo): dropped on 2026-10-04 at the maintainer's word; no purpose was seen in one, and Gideon over the transcripts and the notes with Download notes is enough. The glossary's "A Summary of the whole Case: not a feature" stands.
- **Review states beyond Reviewed**: taken, in progress, done, overdue: ruled out. One mark, made on purpose and taken back when wrong.
- **Roles in assigning**: ruled out beyond the one mark, Also an owner.
- **A date read from the file** (Recorded on, from the file's header or its name) and the sort by it: deferred; a case's order is the order its recordings were added. The maintainer did not keep it from the 2026-10-04 assessment; it returns when a dump's order proves wrong.
- **The Upload page taking a whole folder and feeding it in Batches of 200 by itself**: deferred; Files per Batch and the one-unfinished-Batch rule stand, and a dump is four uploads.
- **The Overview shown in a row's fold for triage**, and **Reviewed with nothing to note drawn apart from Reviewed with notes**: deferred; the answer to the question is recorded with the mark either way.
- **A vendor's metadata sheet** for a dump: deferred to a chapter of its own when an office has one to read.
- **A mail or digest of what is assigned to you**, **a mark on a note for the attorney**, **starter questions for a case of calls**: deferred.
- **Find-and-replace across transcripts**, **matching by sound**, **an index or embeddings behind the Case Chat**, **a picker of recordings for a chat**: ruled out.

## Appendix A. Audit rows added in Phase 9

| Row | Category | Details kept | Never |
|---|---|---|---|
| Case list downloaded | Exports | the case, the recordings' count | a title |
| Case vocabulary added, changed, removed | Cases | the case, the count of entries after | a name, a spelling |
| Side named across the case | Cases | the case, the Side's number, the calls named | the Person's name |
| Recording assigned | Cases | the recording, the assignee's username, the cause (one, ticked, divided) | a title |
| Recording unassigned | Cases | the recording, the cause (owner, share revoked, moved, reassigned) | a title |
| Recording marked reviewed | Cases | the recording, the cause (assignee, owner), nothing to note or not | a note's words |
| Recording marked not reviewed | Cases | the recording, the cause | |
| Case owner added, removed | Cases | the case, the Collaborator's username | |
| Summaries scheduled | AI | the case, the count | |
| Case chat turn (fields added) | AI | the route, the counts (overviews read, pointed to, read whole, without a summary), the scope's kind and count | the question, a reason, a filter's words, an Overview |

## Appendix B. Settings added or changed in Phase 9

| Setting | Page | Type | Default | Chapter |
|---|---|---|---|---|
| Summaries tonight starts ticked | AI assistant | On or Off | Off | 5 |
| Summaries at once overnight | Vision | 1 or 2 | 1 | 5 |
| Case chat: hours of talk read whole per question | Limits | hours, 6 to 600 (renamed; same key) | 120 | 6 |
| Case chat: most recordings the overviews may point to | Limits | 5 to 60 | 30 | 6 |
| Case chat: Readings after the overviews | Limits | 1 to 4 | 1 | 6 |
| Case chat: which recordings | Templates | prompt template, Reset to default | shipped wording | 6 |

## Sources

- The maintainer's words of 2026-10-03 and 2026-10-04, in the planning conversation, quoted at the head of each chapter.
- `docs/spec/mockups/phase-9-mockups.html`: the eight screens picked on 2026-10-04.
- `docs/adr/0016-the-memo-is-written-in-two-passes.md`: the facts-sheet pattern chapter 6's selection pass copies.
- `docs/research/close-matches.md`: the measurement behind chapter 2's search rule.
- `docs/adr/0017-every-recording-gets-its-summary-overnight.md`, `docs/adr/0018-over-the-ceiling-the-case-chat-reads-the-overviews-first.md`.

## Amendments applied

None yet.
