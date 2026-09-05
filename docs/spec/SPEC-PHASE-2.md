# Gideon Transcribe, Phase 2 specification

The Case folders release, published as `v2.0.0`.

## About this document

This is the build specification for Phase 2 of Gideon Transcribe. It builds on Phase 1 (`docs/spec/SPEC-PHASE-1.md`), which stays in force: every Phase 1 rule holds unless a chapter here says which rule changes and how. Like the Phase 1 document, it was assembled from the resolved planning tickets so that a build session can start with nothing left to decide; what was left to the build is under "Left to the build" in each chapter.

Read it with the same companions: `CONTEXT.md` (the glossary; the Phase 2 terms Case, Collaborator, Person, Role, Last activity, Retention policy, Recycle bin, Notification, Backup, Snapshot, and the rest are defined there), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (the Phase 2 rows carry Phase 2 in their Phase column), `docs/whisperx-api.md` (unchanged by Phase 2), `docs/adr/`, and `docs/research/`.

Nothing in this document is office-specific; the Phase 2 install asks for the new office facts (the backup store, the mail relay, the Operator address) and writes them to `.env` and the secrets files.

The conventions of the Phase 1 document apply here unchanged.

## What Phase 2 adds

Phase 1 keeps nothing past a Login session. Phase 2 is the release in which the office may keep Recordings, under rules that delete them again on a clock:

- **Cases**: a named page of retained Recordings for one matter, owned by one user, with Recordings joining at upload or by Move to case once Done, and leaving only by Delete.
- **Sharing**: a Case shared with named colleagues who can do inside it everything the owner can, short of sharing, renaming, transferring, or deleting it.
- **The Retention policy and the Recycle bin**: one clock per Case counting days without activity; the night it runs out the Case goes whole to the Recycle bin, whatever else is going on, and is wiped after a second wait unless restored.
- **The Folder management toggle**: the admin switch that turns all of this on, and off again without deleting anything.
- **People and the Speakers tab**: inside a Case, every Speaker given the same name is one Person, with an optional Role, managed in one place.
- **Clips in Cases**: a Clips tab on the Case page, so every Clip is listed in one place.
- **The Case Chat**: a Chat grounded in every Transcript in a Case, read whole, in parts when the Case is large.
- **Email notifications**: the nightly Retention digest, share and handover mail, an optional batch-finished mail, and the Operator's own mail, all naming things and quoting nothing.
- **Backup and restore**: the app's own nightly encrypted Snapshot to a store off the server, a restore that brings the whole app back to one night, and a monthly Restore drill.

Each feature has its own admin settings, audit rows, and environment keys, consolidated in the appendices. The features that are neither phase's are in the Deferred and ruled out chapter.

## Contents

1. Cases
2. Sharing
3. Retention policy and the Recycle bin
4. The Folder management toggle
5. People and the Speakers tab
6. Clips in Cases
7. Case Chat
8. Email notifications
9. Backup and restore
10. Admin panel additions in Phase 2
11. Upgrading from Phase 1
12. Build gates and deliverables
13. Deferred and ruled out

Appendices: A. Environment keys added in Phase 2. B. Audit rows added in Phase 2. C. Reason classes added in Phase 2. D. Sources.

## 1. Cases

Phase 1 keeps nothing past a Login session: a user exports what they want to keep before signing out. Phase 2 adds Cases, the one place anything is kept. With Folder management on, a user puts a Recording into a Case, where it stays, under the Retention policy, until a person deletes it or the clock does. This chapter fixes what a Case is, how a Recording joins and leaves, what is on disk and what is in the database, the Cases page and the Case page, search, the one per-user quota, owners and leavers, Last activity, and every Phase 1 rule that changes. Everything in it exists only while Folder management is on; while it is off, all of it is hidden and none of it is deleted.

### Principles

1. **A Case is a page, not a folder.** A named list of retained Recordings for one legal matter, opened like any other page. Users never see or browse a folder on disk; the folder behind a Case is the app's own business.
2. **The Recording is the unit.** It joins a Case whole, with its Transcript, Corrections, Speaker names, Summaries, Chats, Clips, and Provenance. It belongs to one Case at a time. It never goes back to the Workspace, and a person takes it out only by Delete. A Clip, a Summary, or a Chat is never saved to a Case on its own.
3. **Only the name is typed.** No case number, no description of the Case, no tags, no Open or Closed mark, no Recorded on date.
4. **One hard quota per user.** The per-user quota covers the Workspace and every Case the user owns together. A user who runs out of room makes room by deleting.
5. **Retention runs on inactivity.** A Case goes to the Recycle bin after an admin-set number of days without activity, and everything about that clock is admin-editable. The Retention policy and the Retention policy and the Recycle bin chapter owns the clock, the warnings, the bin, and the wipe.

No new ADR: nothing here is hard to reverse or surprising. The Recording-as-unit rule and the single quota are app rules a later Release could change.

### Words

- **Case**: a named page of retained Recordings for one legal matter, owned by one user, kept under the App data folder, shareable with named colleagues, and subject to the Retention policy. It exists only when Folder management is on, and nothing but its name is typed.
- **Add to case**: the Upload page choice that puts a Recording into an existing Case from the start. A Recording added this way is never in the Workspace.
- **Move to case**: taking a Done Recording out of the Workspace and into a Case, whole. Nothing moves back.
- **Recording type**: an optional label for a Recording, picked at upload from an Admin-kept list and changeable later.
- **Description**: an optional free-text note on a Recording in a Case.
- **Last activity**: the most recent use of a Case by its owner or a Collaborator; the Retention policy's clock. An Admin's audited opening does not count, and neither does handing the Case over.
- **Reassign**: an Admin giving a Case, or every Case a user owns, to a named user.
- **Transfer**: an owner giving one of their Cases to a named colleague; the old owner stays on it as a Collaborator.
- **Collaborator**: a person a Case is shared with (see the Sharing chapter).

### What a Case is and is not

| Fact | Rule |
|---|---|
| Name | Required, typed by the user (for example `SmithJohn`). Not unique: the app warns when another Case the user can see has the same name, then allows it. Renamed by the owner or an Admin. A rename never touches disk. |
| Typed by the user | The name, and nothing else. No case number, no description of the Case, no tags, no Open or Closed mark, no Recorded on date. Custodian, source, and anything else a person wants to note go into a Recording's Description. |
| Kept by the app | Owner, created, Last activity, Recording count, size on disk, and a deleted-on date that stays empty until the Retention policy moves the Case to the Recycle bin. Nothing else. |
| Created | On the Cases page, by any signed-in user while Folder management is on, or in the "New case" box of the Move to case picker. Never from the Upload page: Add to case lists existing Cases only. |
| Owner | Exactly one. Changes only by Reassign or Transfer. |
| Open or Closed | None. A Case is a name and its Recordings. |
| Delete | By the owner or an Admin, behind a confirmation naming the counts. Everything goes at once, files and rows, with no Recycle bin: a person's Delete is final. Deleting a Case ends its Shares and takes its People and Case Chats with it. |
| The clock | The Retention policy moves a Case whole to the Recycle bin the night it reaches the admin-set number of days without activity; the owner or an Admin may restore it there for the bin period. Only the clock's deletions go to the bin. |

The Delete confirmation names the counts in this shape; the chat count includes the Case's Case Chats:

```
This deletes 12 recordings and their transcripts, 4 summaries, 2 chats, and 3 clips, 18 GB
```

### A Recording in a Case

- **Title**: the uploaded file name, as everywhere in the app.
- **Recording type** (optional): a dropdown on the Upload page, shown only when Folder management is on, set once per Batch with a per-Recording override like the other Batch settings, and changeable later in the Details panel. The list is the admin setting "Recording types", one per line, shipping with these six:

```
Body camera
Jail call
Interview
Phone call
Hearing
Other
```

  Removing a type from the list leaves the Recordings that hold it unchanged.

- **Description** (optional, free text): asked for, and skippable, when a Recording is moved to a Case, and editable later in Details. Custodian, source, and anything else go here.
- **No Recorded on date.** The app cannot know when a recording was made, and nobody types a date. The Word cover page keeps printing the upload date only. The export of a Recording in a Case adds the Case name to the cover and is otherwise the same document. The Provenance on an export lists the Clips that exist at export time.
- **Everything else is the Workspace's**: the same viewer, Corrections, Speaker names, Summaries, Chats, Clips, Process again, Retry, exports, and Delete (audited, with the cause owner or admin). Details shows the Case name, the Recording type, the Description, and, in a shared Case, "Added by".
- Inside a Case every Speaker given the same name is one Person (see the People and the Speakers tab chapter).

### Two ways in

#### Add to case, at upload

When Folder management is on, the Upload page carries an "Add to case" dropdown listing the user's existing Cases and every Case shared with the user. Its default is "This session only". It is set once per Batch with a per-Recording override, like the other Batch settings.

- A Recording added this way belongs to the Case from the first byte: its files land in the Case's folder, it appears on the Case page with its Step while its Job runs, and it never appears on the Recordings page. It is never in the Workspace.
- The Batch page still shows it, since the Batch is the user's.
- Cancel removes it as if it had never been uploaded. A Failed Job keeps its files, and its Retry, inside the Case.
- The "duplicate file" refusal applies per destination: the same file already live in that Case, or in the Workspace for a Workspace upload, is refused; the same file in another Case is allowed.
- The Case page carries an "Add recordings" button that opens the Upload page with the Case preselected.
- When the target is someone else's Case, the dropdown and the Upload page show that owner's remaining room (see the Sharing chapter).

#### Move to case, once Done

A Done Recording offers "Move to case" in three places: the Recordings page list, its Details panel, and the sign-out dialog. The button opens a picker of the user's Cases and every Case shared with the user, with a "New case" box.

- Only Done Recordings are offered. A Queued, Running, or Failed one is not: Retry or Delete it first.
- The move takes the Recording whole: its Transcript with Corrections and Speaker names, its Summaries, its Chats, its Clips (a Clip made in the Workspace rides in with its Recording), and its Provenance.
- On disk it is a folder rename on the same filesystem, instant whatever the size. In the database it re-keys the Recording's rows. It writes the audit row "Recording moved to case".
- The Description is asked for at the move and may be skipped.
- Each named Speaker becomes or joins a Person in the Case by name (see the People and the Speakers tab chapter).
- A Recording moved during a Login session leaves the Recordings page at once.
- The sign-out dialog lists the Done Recordings not yet moved, with "Move to case" beside "Download all transcripts" and "Download everything".

#### Between Cases

The owner or an Admin can move a Recording to another Case, with the same mechanics, writing the audit row "Recording moved between cases". In the new Case each named Speaker becomes or joins a Person there, while the old Case's People stay. A Collaborator may move only the Recordings they added themselves, and only to a Case they own or one shared with them (see the Sharing chapter).

### One way out

- Nothing ever moves back to the Workspace.
- A person's only way to take a Recording out of a Case is Delete, and it is final: no Recycle bin. Deleting a Recording leaves the Case's People in place.
- The only other way out is the Retention policy's, and it takes the whole Case to the Recycle bin (see the Retention policy and the Recycle bin chapter).
- Recordings not moved by the end of the Login session are discarded exactly as in Phase 1. The Discard and the sweepers skip any Recording that has a Case.

### On disk and in the database

| Where | What |
|---|---|
| `<App data folder>/cases/<case id>/<recording id>/` | The Workspace's file set, unchanged: uploaded bytes, probe output, ASR audio per Side, Playback copy, waveform peaks, and `clips/`. The Case id is the database id, never the name. |
| Postgres | The Case (name, owner, created, Last activity, deleted-on); the Recording's Case link, Recording type, and Description; and all text as in the Workspace: the Transcript with Corrections and Speaker names, Summaries, Chats, Clip definitions, Provenance, Batches and Jobs. The Case's People, Shares, and Case Chats are Case rows too (see the People and the Speakers tab, Sharing, and Case Chat chapters). |
| Nowhere | Exports. They are rendered on demand and never stored, in a Case as in the Workspace. |

```
<App data folder>/
  scratch/                          Workspaces, as in Phase 1
  cases/
    <case id>/
      <recording id>/               uploaded bytes, probe output, ASR audio per Side,
                                    Playback copy, waveform peaks
        clips/
```

- Cases live at `<App data folder>/cases/`, beside `scratch/`.
- The uploaded bytes stay in the Case because Process again with a different Preprocessing profile needs them. They remain never served and never downloadable, in a Case as in the Workspace.
- Transcripts stay keyed to the Case, which is what Case Chat needs.
- The 03:30 sweeper treats `cases/` as it treats `scratch/`: any folder with no Recording row is removed and counted.
- `cases/` is the only retained media in the app and joins the backup set. It is copied to the Backup target every night at 02:00 as part of an encrypted Snapshot, deduplicated so an unchanged Recording costs nothing after its first night. A Case that is gone from the app lingers in Snapshots for 30 days. Nothing is ever picked out of a Snapshot for a person: there is no per-Case restore. After a restore, a Recording half-added to a Case at the Snapshot comes back Failed with the reason `restored` and Retry when its rows are there and its files are not, and files with no rows are removed by the next daily sweeper (see the Backup and restore chapter).

### The Cases page

When Folder management is on, the Cases page is the landing page at sign-in, with "your recordings" (the Workspace) reachable at the top.

- One list holds the user's own Cases and the Cases shared with them: Name, Recordings, size, Last activity, Retention (the clock's line), and the owner when it is someone else. Sortable by any column, with a text filter on the name. The page has three views in one strip of tabs, Mine, Everyone's (an Admin's alone), and Recycle bin, so the bin is a view of this page rather than a page to find. The chosen Case's details (the same facts, with Open, Case page, and Keep in its last days) sit in a pane beside the table from 1280 pixels, or open under its row on a narrower window; Up and Down move along the rows and Enter opens.
- A shared Case shows the owner's name and a Shared mark, New until first opened (see the Sharing chapter).
- A Case in its last days carries the amber Retention warning on its row, with Keep (see the Retention policy and the Recycle bin chapter).
- This is where a Case is created: the name is typed, nothing else.
- There is no search across all Cases from this page.
- **Admins** see every Case, with an owner filter, an "Owner deactivated" filter, and an "Expiring" filter (the Retention policy and the Recycle bin chapter's). Opening another user's Case shows the banner, writes the Admin access row (ADR 0004), and does not count as activity, matching the Workspace rule. An Admin the Case is shared with is a colleague on it instead (see the Sharing chapter).

### The Case page

Four tabs, one search box, and the Case's own controls. From 1280 pixels the page is two panes: what is in the Case on the left (the tabs, the search box and its hits, the list), and what is about the Case on the right (owner, count and size, Last activity, the Retention line with Keep, Download all transcripts, Rename, Delete case; Add recordings stays in the header). On a narrower window the right pane follows the list. A Recording's details (Description, type, and its actions) open under its row on every width, because the pane is the Case's.

- **Recordings** tab: the list with title, Recording type, Description, length, Speakers (reads `2 named, 1 unnamed`), Transcript state (a Recording added at upload shows its Step while its Job runs), and last opened. Per Recording: Move to another case, for those allowed to move it. Opening, Process again, Retry, Details, exports, and Delete are the Workspace's own, unchanged.
- **Speakers** tab: the Case's People (name, optional Role, notes, where they appear) and the Recordings with unnamed Speakers; the one place a Person is renamed for the whole Case, merged, or deleted (see the People and the Speakers tab chapter).
- **Clips** tab: the Clips page's columns plus "Saved by", a Download all for the Case, and no Downloaded column. The Clips page in the navigation stays the Workspace's list only, so a Clip is listed in one place (see the Clips in Cases chapter).
- **Chat** tab: the Case's Case Chats, each grounded in every Transcript in the Case as it stands when each question is asked; present while its own setting, "Chat across cases", is on (see the Case Chat chapter).
- Controls: "Add recordings"; Rename; Delete case; Transfer, for the owner; Share and the "Shared with" panel, for the owner and Admins; Reassign, for Admins.
- A Collaborator sees "Shared by <owner>" and the names of the other Collaborators, read-only.

### Search inside one Case

One box on the Case page searches Transcript text and Speaker names across that Case's Recordings. Every hit is a Segment that opens the viewer at that time. Whoever can open the Case can search it: the owner, its Collaborators, and Admins. There is no search across all Cases. Search terms are never logged.

### Room: the per-user quota

One hard per-user quota, the media handling chapter's (default 50 GB, with per-person overrides on the users list), counts everything on disk under the user's Workspace and the Cases they own, whoever uploaded it. A Collaborator's Recordings in a Case count against the Case owner's quota.

- When it is full, uploads are refused with the media handling chapter's over-quota reason class.
- A Move to case between a user's own Workspace and Cases never changes their count, so such a move never fails. A Collaborator's move into a shared Case is the Sharing chapter's.
- The user makes room by deleting Recordings or Cases.
- The users list's Recordings and GB figures include Cases, shown as `3 in session, 41 in cases`.
- The "Minimum free disk space" floor applies unchanged.
- Cases hidden while Folder management is Off keep counting.

### Owners and leavers

- Every Case has exactly one owner.
- **Reassign**: an Admin gives one Case, or every Case a user owns, to a named user, from the Case page or from the users list, where the "Reassign to a named user" action (greyed out in Phase 1) now has its target. Reassign adds nobody to the Case.
- **Transfer**: an owner gives one of their Cases to a named colleague, from the Case page. The old owner stays on the Case as a Collaborator and may remove themselves.
- Both change the owner and the quota the Case counts against, and nothing else: Shares stay as they are, and People and Case Chats are carried unchanged. Neither starts the Retention clock over. The new owner inherits the days left and opens the Case to start it over.
- Both write the audit row "Case reassigned", with the affected user set to the old owner and the details naming the new one.
- Both send one "case handed to you" Notification to the new owner at once, naming the Case, who handed it (the old owner's display name, or the Admin's), and the days left on its clock. The old owner gets nothing (see the Email notifications chapter).
- **A leaver's Cases** stay untouched when the Directory check deactivates the owner, and when an Admin blocks them: readable by Admins, still under the Retention policy, flagged "Owner deactivated" for Admins until an Admin reassigns or deletes them. Collaborators keep working meanwhile. Nothing is automatic. While such a Case is inside the Retention warning window it is listed in the Operator address's nightly section, which points Admins at the Cases page's "Owner deactivated" and "Expiring" filters to Reassign or Keep.
- The users list's "Delete data" action, greyed out in Phase 1, deletes the user's Cases behind a confirmation naming the counts.

### Last activity

Last activity is the Retention policy's clock. The Retention policy and the Retention policy and the Recycle bin chapter owns the clock, its period, the warnings, and the bin; this chapter fixes what counts.

- Counts, when done by the owner or a Collaborator: opening the Case page; opening a Recording in it; adding or moving a Recording in; making a Correction; naming a Speaker or changing a Person; asking for a Summary or a Chat; starting or continuing a Case Chat; saving a Clip; exporting; renaming the Case; sharing it; pressing Keep; restoring it from the Recycle bin.
- Does not count: an Admin's opening under the Admin access rule (ADR 0004), matching the Workspace rule; Reassign; Transfer.
- An Admin the Case is shared with counts as a colleague.

### While Folder management is Off

Turning Folder management Off with Cases present hides every Case from everyone, owners included, and deletes nothing: files under `cases/`, rows in Postgres, Descriptions, Recording types, Shares, and People stay exactly as they were. An upload or a Job in flight finishes into its Case, hidden. The Cases keep counting against their owners' quotas. The toggle never touches `cases/` on disk. Turning On brings everything back as it was, with no announcement beyond the empty Cases page's own text. What Off does to the Retention clock is the Retention policy and the Recycle bin chapter's; the rest of the transition is in The Folder management toggle chapter.

### What changes from Phase 1

Every Phase 1 rule holds except these. Each change applies only while Folder management is on unless the line says otherwise.

- **Landing page.** Phase 1 lands on the Recordings page. Phase 2 lands on the Cases page, with "your recordings" reachable at the top.
- **Upload page.** Phase 1 shows no Add to case and no Recording type. Phase 2 adds both dropdowns, each set once per Batch with a per-Recording override. The Upload page never creates a Case.
- **The duplicate file refusal.** Phase 1 refuses a file already live in the Workspace. Phase 2 applies the refusal per destination: the Case chosen, or the Workspace.
- **Recordings page and Details panel.** A Done Recording gains "Move to case" in the list and in Details. Details shows the Case name, the Recording type, and the Description, both editable there, and "Added by" in a shared Case. A Recording added at upload with Add to case is never on the Recordings page.
- **The viewer.** Unchanged, and now also reached from a Case page and from a search hit inside a Case. Delete in a Case is audited with the cause owner or admin, as in the Workspace.
- **Sign-out dialog.** Phase 1 offers "Download all transcripts" and "Download everything". Phase 2 also lists the Done Recordings not yet moved, with "Move to case" beside those two buttons. What is not moved is discarded exactly as in Phase 1.
- **The Discard and the sweepers.** The Discard skips Recordings with a Case, a skip Phase 1 carried with nothing to skip. The 03:30 sweeper now walks `cases/` as well as `scratch/`.
- **Word export.** The cover of a Recording in a Case prints the Case name. The upload date stays the only date printed.
- **The per-user quota.** Phase 1 counts the Workspace. Phase 2 counts the user's Cases too, whoever uploaded into them; the setting's description says so; the users list's figures read `3 in session, 41 in cases`.
- **Users list.** "Reassign to a named user" and "Delete data", greyed out in Phase 1, become live with the meanings above. A leaver's Cases are flagged "Owner deactivated".
- **Status page.** Gains "Cases: N, X GB" (see the Admin panel additions in Phase 2 chapter).
- **Settings panel.** "Recording types" appears in the panel.
- **Admin access.** The banner and the Admin access row (ADR 0004) now cover Cases: an Admin opening another user's Case is audited the same way and does not count as activity. The Sharing chapter adds one exception, an Admin who is a Collaborator on that Case.
- **Backup.** `cases/` joins the backup set as the only retained media. The restore rule for Workspaces (end Login sessions, run the Discard) leaves Cases alone.
- **Audit log.** The Cases category's placeholder rows become live (see Audit rows).

### What Phase 1 carried

Phase 1 built the shape and showed none of it:

- Every Recording row has a Case link, empty in Phase 1; empty means Workspace.
- The Recording type and Description columns exist unused.
- The Discard and the sweepers skip any Recording with a Case.
- The disk convention reserves `cases/` beside `scratch/`.
- The settings catalogue lists "Recording types" among the Phase 2 rows, absent from the Phase 1 panel.
- The Case table's deleted-on date, empty.
- The users list's "Reassign to a named user" and "Delete data" actions, greyed out.
- The Upload page prototype's README notes where the per-Batch dropdowns and their per-Recording overrides go; nothing rendered.
- Turning Folder management on adds pages, not tables.

### Not in this phase

- No Case number, Case description, tags, or Open or Closed mark: the name is the only typed field of a Case.
- No Recorded on date on a Case or a Recording, and no Source or Custodian field: a Recording's Description holds such notes.
- No "Save to a case": the act, in the sign-out dialog as elsewhere, is Move to case.
- No separate Case storage quota: the one per-user quota covers Cases.
- No search across all Cases from the Cases page.
- No Recycle bin for a person's Delete, and no per-Case restore from a Snapshot.

### Environment keys

None are named by the sources. The App data folder's location is fixed at installation, as in Phase 1; this chapter adds only the `cases/` subfolder under it.

### Audit rows

Every row uses the Audit log and logging chapter's fixed field set (time, actor, category and event, outcome, affected user, object with a snapshot label, login session, client, details). A Case's snapshot label is its name at the time, as a Recording's is its file name. The affected user is the Case's owner whenever someone else acts.

| Row | Written when |
|---|---|
| Case created | a Case is made, on the Cases page or in the "New case" box |
| Case renamed | the owner or an Admin renames a Case |
| Case deleted (N recordings, X GB) | a person deletes a Case: the owner, an Admin, or "Delete data" on the users list; one row per Case |
| Recording deleted (cause: owner or admin) | the existing row, one per Recording deleted in a Case, alone or with its Case, in the way the Discard writes one per Recording it removes |
| Case reassigned | Reassign or Transfer; the affected user is the old owner and the details name the new one |
| Recording moved to case | Move to case from the Workspace |
| Recording moved between cases | a Recording is moved to another Case |
| Admin access (ADR 0004) | the existing row, when an Admin opens another user's Case; not activity |
| Recording opened | the existing row, unchanged, when a Recording in a Case is opened |

Never logged: search terms, Descriptions, Transcript text. Audit retention defaults to three months, so the log will not cover the life of a Case unless the office raises the setting; nothing this chapter shows users is read from the log. The Retention policy's rows belong to the Retention policy and the Recycle bin chapter, People's rows to the People and the Speakers tab chapter, and Case Chat's to the Case Chat chapter.

### Settings

The admin settings catalogue holds the rows; this chapter depends on these:

- **Folder management**: the toggle that enables everything in this chapter. Off hides every Case and deletes nothing.
- **Recording types**: the list behind the Recording type dropdown, one per line, shipping with the six above. A Phase 2 row.
- **The per-user quota** (the media handling chapter's, default 50 GB, per-person overrides on the users list): now counts the user's Cases too.
- **Minimum free disk space**: the floor, unchanged.
- **The Retention policy's settings** (the period in days without activity and the bin period): the Retention policy and the Recycle bin chapter's.
- **Sharing**: the Sharing chapter's, for the Case page's Share controls and the shared Cases on the Cases page.
- **Chat across cases**: the Case Chat chapter's, for the Chat tab.

### Left to the build

- The Delete confirmation's exact sentence. Fixed: it names the counts of recordings and their transcripts, summaries, chats (Case Chats included), and clips, and the size in GB, in the shape shown above.
- The wording of the duplicate-name warning. Fixed: it warns when another Case the user can see has the same name, then allows the name.
- The label of the Cases page's create control. Fixed: a Case is created on the Cases page with only a name typed, and the Move to case picker's box is called "New case".
- The empty Cases page's own text. Fixed: it is the only announcement when Folder management is turned On.
- The Description prompt at Move to case. Fixed: it is asked for and skippable.
- Which rows "re-keys its rows" covers at Move to case. Fixed: the Recording's Case link changes, the move is a folder rename, and the Batch stays the user's.
- The default sort order of the Cases page and of the Case page's Recordings list. Fixed: the Cases page is sortable by any column with a text filter on the name.
- How the Recording count and size on disk are kept current. Fixed: the app keeps both, and the users list and the status page print them.

### Sources

Case folder model on the mount (with its amendments from the Sharing model, Retention policy, Speaker management panel, Folder management toggle transitions, Backup and restore, Clips, Email notifications over SMTP, and Chat across a whole Case tickets).

### Amendments applied

- From the Sharing model ticket, to the words and the ways in: "sharer" reads Collaborator; Add to case and Move to case list every Case shared with the user; Transfer keeps the old owner as a Collaborator and Reassign adds nobody; a Collaborator may delete, Process again, or move only the Recordings they added.
- From the Retention policy ticket, to Last activity and the way out: opening the Case page, sharing, Keep, and restoring count; Reassign and Transfer do not start the clock over; the Retention policy moves a Case to the Recycle bin, so Delete is no longer the only way out; a person's Delete stays final; the Case table gains a deleted-on date.
- From the Speaker management panel ticket, to the Case page and the ways in: the Speakers tab; People as Case rows; the Speakers column reads "2 named, 1 unnamed"; what happens to People at a move, between Cases, and at Delete; People go to the bin with the Case and are carried by Reassign and Transfer.
- From the Folder management toggle transitions ticket, to the Off rule: hiding without deleting, in-flight work finishing hidden, quotas still counting, On bringing everything back.
- From the Backup and restore ticket, to the disk section: the nightly 02:00 encrypted, deduplicated Snapshot; 30 days in Snapshots after deletion; no per-Case restore; the `restored` Failed state and the sweeper after a restore.
- From the Clips ticket, to the Case page and Move to case: the Clips tab with "Saved by" and Download all; the Clips page stays the Workspace's; a Clip rides in with its Recording; the Provenance lists the Clips at export time.
- From the Email notifications over SMTP ticket, to owners and leavers: the "case handed to you" mail; the old owner gets nothing; the Operator address's nightly section and the "Expiring" filter.
- From the Chat across a whole Case ticket, to the Case page, the database, and Delete: the Chat tab; Case Chats as Case rows that move, go to the bin, and are deleted with the Case; the Delete confirmation's chat count includes them.
- From the maintainer, on the v1.6.0 build, to the Cases page and the Case page: the Workbench Layout's third page. The Cases page's three views (Mine, Everyone's, Recycle bin) in one strip of tabs, a Retention column, and the chosen Case's details in a pane from 1280 pixels; the Case page in two panes, what is in the Case and what is about it. Below 1280 pixels the details open under the row and the panes stack.

## 2. Sharing

In Phase 1 nothing is shared: a Workspace is one person's, and nothing leaves it but exports and Clip downloads. Phase 2 lets the owner of a Case share it with named colleagues inside the office, who can then do inside it everything the owner can, short of sharing, renaming, transferring, or deleting the Case. This chapter fixes who may be shared with, what a Collaborator may and may not do, what each page shows, how room and the Retention clock work for Collaborators, what happens when people leave or Cases change hands, the audit rows, the Sharing toggle, and every Phase 1 rule that changes. Sharing needs Folder management and its own toggle, Sharing.

### Principles

1. **A Share names a person.** One colleague who has signed in to the app at least once. Internal users only, never anyone outside the office; no directory groups and no typed addresses.
2. **Everyone shared with can edit.** One level, and the Share dialog says so before the owner confirms.
3. **Nothing is private inside a shared Case.** One Case, one page: everyone who can open it sees the same Transcripts, Corrections, Speaker names, People, Summaries, Chats, Case Chats, and Clips.
4. **The Case stays the owner's.** Sharing, renaming, transferring, and deleting the Case belong to the owner and to Admins. A Collaborator never passes a Case on.
5. **Sharing is per Case**, never per Recording. To share one Recording, put it in a Case of its own.

No new ADR: a view-only level or a private Chat could be added later without unpicking anything, since a Share is one row naming one person.

### Words

- **Share**: the owner's grant of access to one Case to one named colleague. One kind only: whoever a Case is shared with can do inside it everything the owner can, short of sharing, renaming, transferring, or deleting the Case.
- **Collaborator**: a person a Case is shared with. Their work in the Case counts as its activity, and the Recordings they add count against the owner's room.
- **Sharing** (the setting): the admin toggle that lets owners share Cases; needs Folder management. Off hides every Share without ending it.

### Sharing a Case

| Step | Rule |
|---|---|
| Who may share | The owner, from the Case page. An Admin, from any Case page, with the audit row carrying the owner as affected user. |
| Picking a person | A search box over the app's accounts: people who have signed in at least once and are Active, minus the owner and the existing Collaborators. Deactivated and Blocked accounts and Local admins are not offered. Someone not yet listed signs in once and can then be picked. |
| The dialog's words | Before the owner confirms, the dialog says in plain words what the person will be able to do (below). Fixed wording in the app and the user guide, not a setting. |
| Removing | The owner or an Admin removes a Share from the Case page. The Collaborator loses the Case on their next request. Anything they added stays in the Case. |
| Limits | No limit on Collaborators per Case and no time limit on a Share. The Retention policy ends the Case, not the Share. |

The words the owner reads before confirming say:

- that the person will be able to do everything in the case except share, rename, or delete it: add recordings, correct transcripts, name speakers, ask for summaries and chats, and save clips;
- that recordings they add count against the owner's space.

The "case shared with you" Notification repeats the same words (see Notifications below).

### What a Collaborator may and may not do

| Action | Owner | Collaborator | Admin who is not a Collaborator |
|---|---|---|---|
| See the Case on the Cases page | in their own list | in their own list, marked "Shared by <owner>", New until first opened | in the every-Case list, with the owner filter |
| Open the Case; open, play, and search its Recordings | yes | yes | yes, with the banner and the Admin access row (ADR 0004); not activity |
| Export (Word, plain text, Captions); download Clips | yes | yes | yes, audited |
| Add Recordings (Add to case at upload, "Add recordings" on the Case page); Move to case of their own Done Recordings | yes | yes; counts against the owner's quota | yes, with the owner's powers |
| Correct Segments; rename, merge, and accept suggestions for Speakers; add, rename, edit, merge, and delete People on the Speakers tab and in the viewer's rename box; edit Recording type and Description | yes | yes | yes |
| Ask for a Summary, a Chat, or Speaker suggestions; start, continue, export, and delete a Case Chat | yes | yes | yes |
| Save, Adjust, download, and delete Clips | yes | yes, any Clip | yes |
| Delete a Recording; Process again; move a Recording to another Case | yes | only the Recordings they added themselves | yes |
| Rename the Case; Share and remove Shares; Transfer; Delete the Case | yes | no | Rename, Share, remove, Delete, and Reassign in place of Transfer |

One rule sits behind the destructive row: an action that throws away someone else's work (a Recording, or its Transcript through Process again) belongs to the owner, an Admin, or the person who brought that Recording in. The Provenance already names the uploader, and the Details panel shows "Added by" in a shared Case. Everything else in a shared Case is open to everyone in it, Clips included, because it can be redone. A Collaborator moving a Recording they added to another Case may pick only a Case they own or one shared with them.

### Nothing private inside a shared Case

A Chat with the AI assistant is the Case's, not the person's: a Collaborator sees the owner's Chats and the owner sees theirs. The same holds for Case Chats, Summaries, Corrections, Speaker names, People with their Roles and notes, and Clips. One Case, one page; everyone sees the same thing. Hiding any of it would surprise more than it protects.

### The Collaborator's Cases page

- A shared Case sits in the Collaborator's one list, with the owner's name and a Shared mark, New until first opened. There is no separate "Shared with me" page; the owner column does the work.
- Nothing else is sent in the app. The "case shared with you" mail is the Email notifications chapter's.
- The Case page shows the Collaborator "Shared by <owner>" and the names of the other Collaborators, read-only.
- Collaborators see the same amber Retention warning on their Cases page row as the owner and may press Keep, since their use is Last activity (see the Retention policy and the Recycle bin chapter).

### The owner's Shared with panel

On the Case page, for the owner and Admins: a "Shared with" panel listing each Collaborator with when they were added and when they last opened the Case, Remove beside each, and the Share button.

- "Last opened" is kept on the Share itself, not read from the audit log, so it outlives Audit retention.
- This panel is the owner's whole answer to "who has seen this". Users still see nothing of the audit log.

### Room and the clock

- Recordings a Collaborator adds live in the Case and count against the owner's quota: the quota counts everything under the Cases a user owns, whoever uploaded it (see the Cases chapter).
- The Add to case dropdown and the Upload page show the owner's remaining room when the target is someone else's Case. When it is full, the upload is refused with the media handling chapter's over-quota reason class, and the message names whose space is full.

- **A Collaborator's Move to case is never refused for room**, even when the owner's quota is already full (settled 2026-09-03; the Cases and Sharing sources disagreed and "a move never fails" was chosen). The Recording exists already and the work on it is done, so refusing the move would strand it in a Workspace that is about to be discarded. The quota bites at the next upload into that Case, as it does for the owner's own Cases, and the count rises above the limit until something is deleted.

- A Collaborator's use is Last activity for the Retention policy: opening the Case page or a Recording in it, adding or moving one in, correcting, naming a Speaker or changing a Person, asking for a Summary or Chat, starting or continuing a Case Chat, saving a Clip, exporting, pressing Keep. An Admin's opening under the Admin access rule (ADR 0004) still does not count; an Admin who is a Collaborator counts as a colleague.

### People leaving, Cases moving

- Shares outlive Reassign and Transfer: the new owner inherits them as they are.
- Transfer keeps the old owner on the Case as a Collaborator, so nobody loses access by handing a Case over; they can remove themselves. Reassign, the Admin's action for leavers, adds nobody.
- Owner Deactivated or Blocked: the Case stays, Collaborators keep working, Last activity keeps ticking, until an Admin reassigns or deletes it.
- Collaborator Deactivated or Blocked: the Share stays listed, greyed with the status, and works again if the directory readmits them or the block is lifted. The owner can remove it meanwhile. A Deactivated or Blocked Collaborator is not mailed.
- Deleting a Case ends its Shares. "Delete data" on a leaver removes their Cases and with them the Shares on those Cases; Shares they held on other people's Cases stay listed greyed until removed.
- A Case in the Recycle bin disappears from Collaborators' lists and its Shares stop working; Restore brings the Shares back as they were. Collaborators see nothing of the Recycle bin.
- Sharing touches Cases only. A Workspace is never shared.

### Admins

- An Admin the Case is shared with is a colleague on that Case: no banner, no Admin access row (ADR 0004), and their use counts as Last activity. Their openings are still "Recording opened" rows, so every access stays in the log in the plain sense.
- An Admin opening any other Case keeps the banner and the row and acts with the owner's powers, sharing included. Such an Admin downloads a Case's Clip under the audit banner, audited with the affected user, exactly as in a Workspace.

### The Sharing toggle

The admin setting **Sharing**: On or Off, default Off, in the Cases section of the panel, greyed while Folder management is Off. Its effect is immediate.

- Off hides the Share button, the "Shared with" panel, and shared Cases from Collaborators' lists. The Shares are kept, never deleted, so On restores them: a feature turned Off hides and never deletes.
- A Collaborator's Recording in a hidden Case stays in the Case.
- While Folder management is Off the owner sees nothing of their Cases, shared or not, exactly as Collaborators see nothing. Shares survive both toggles, and the Sharing toggle keeps its value while greyed, so On brings every Share back as it was (see The Folder management toggle chapter).

### Notifications

The Email notifications chapter holds the wording, the timing, and the mechanics. This chapter's events send:

- **"case shared with you"**: one mail to the new Collaborator, at once, when the Share dialog is confirmed, naming the Case and the owner and repeating the dialog's words on what a Collaborator may do. Removing a Share sends nothing.
- **The Retention digest**: Cases shared with a person appear in that person's own nightly digest under "Shared with you", with the owner's name. Owner and Collaborators alike are warned, each in their own digest, never in a separate mail.
- A message may name the Case and the owner and nothing more. A Deactivated or Blocked Collaborator is not mailed.

### What changes from Phase 1

- **Nothing shared becomes Cases shared.** Phase 1 shares nothing and renders nothing of this chapter. Phase 2 adds the Share button and the "Shared with" panel to the Case page, shared Cases to the Cases page, and "Shared by <owner>" for Collaborators. A Workspace stays unshared.
- **Admin access.** Phase 1's rule that every Admin access to another user's material shows the banner and writes the Admin access row (ADR 0004) gains one exception: an Admin who is a Collaborator on that Case is a colleague there, with no banner and no row, and their use counts as activity.
- **"Recording opened".** Now also written when a Collaborator opens a Recording, with the owner as affected user, so the audit log viewer's "Access to their material" filter shows Collaborators' openings beside Admins'.
- **Details panel.** Shows "Added by" in a shared Case.
- **Upload page.** The Add to case dropdown lists every Case shared with the user and shows the owner's remaining room for someone else's Case; the over-quota refusal's message names whose space is full.
- **Move to case.** The picker lists every Case shared with the user.
- **Settings panel.** The Sharing placeholder becomes a live row: On or Off, default Off, Cases section, greyed while Folder management is Off.
- **Audit log.** The placeholder rows "Share granted" and "Share revoked" become live, with the details below. There is no "Share changed".
- **Users list and the Directory check.** A Collaborator's deactivation or block greys their Shares; "Delete data" on a leaver removes the Shares on the leaver's Cases.
- **Notifications.** The "case shared with you" mail and the digest's "Shared with you" section (see the Email notifications chapter).

### What Phase 1 carried

- The Share table exists empty: Case, person, added by, added on, last opened. Turning Folder management on adds pages, not tables.
- The Sharing row sits among the settings catalogue's Phase 2 placeholders.
- Nothing rendered.

### Not in this phase

- No levels: no Can view, no Can edit, and so no "Share changed" audit row.
- No private Chats, Summaries, or Speaker names inside a shared Case.
- No Shares to directory groups, and no typed addresses (see the Deferred and ruled out chapter).
- No "Shared with me" page.
- No per-Recording sharing.
- No sharing outside the office.

### Environment keys

None are named by the sources.

### Audit rows

Both new rows sit in the Cases category and use the Audit log and logging chapter's fixed field set. The object is the Case's snapshot label (its name at the time), the details block names the Collaborator's username, and the affected user is the owner whenever an Admin acts on someone else's Case.

| Row | Written when |
|---|---|
| Share granted | the owner or an Admin confirms the Share dialog |
| Share revoked | the owner or an Admin removes a Share |
| Recording opened | the existing row, when a Collaborator opens a Recording; the affected user is the owner |
| The People rows (the People and the Speakers tab chapter's) | a Collaborator adds, renames, edits, merges, or deletes a Person; the affected user is the owner |

Nothing else is new, and nothing carries content.

### Settings

- **Sharing**: On or Off, default Off, Cases section, greyed while Folder management is Off; Off hides and never deletes.
- **Folder management**: Sharing needs it. Off hides every Case from owners and Collaborators alike and keeps the Shares.
- **The per-user quota**: the owner's, which a Collaborator's Recordings count against.
- **The Retention policy's settings**: the Retention policy and the Recycle bin chapter's; a Collaborator's use starts the clock over.
- **Chat across cases**: the Case Chat chapter's; Collaborators use the Chat tab as the owner does.

### Left to the build

- The exact sentences of the Share dialog's words. Fixed: they say, in plain words, that the person will be able to do everything in the case except share, rename, or delete it (add recordings, correct transcripts, name speakers, ask for summaries and chats, save clips) and that recordings they add count against the owner's space; fixed wording in the app and the user guide, not a setting; the "case shared with you" mail repeats them.
- The over-quota message for an upload into someone else's full Case. Fixed: it uses the over-quota reason class and names whose space is full.
- How the account search box matches (display name, username, or both). Fixed: who is offered and who is not.
- The look of the Shared mark and the New flag on the Cases page, and the greyed status text on a Deactivated or Blocked Collaborator's Share. Fixed: that they exist and what they mean.
- The cause recorded on "Recording deleted" when a Collaborator deletes a Recording they added. Fixed: the sources name only the causes owner and admin.
- Whether Transfer's automatic Share for the old owner writes "Share granted" beside "Case reassigned". Fixed: the old owner becomes a Collaborator and the Share appears in the "Shared with" panel.

### Sources

Sharing model (with its amendments from the Retention policy, Speaker management panel, Folder management toggle transitions, Clips, Email notifications over SMTP, and Chat across a whole Case tickets); Case folder model on the mount (the one-owner rule, the quota, Last activity, Reassign and Transfer, Delete ending Shares, search inside a Case, and the owner shown on the Cases page).

### Amendments applied

- From the Retention policy ticket, to the Collaborator's Cases page and to leaving and moving: the amber warning and Keep for Collaborators; a Case in the Recycle bin leaves Collaborators' lists and its Shares stop until Restore; Collaborators see nothing of the bin. Its line "the owner alone gets the warning email" is superseded by the Email notifications over SMTP ticket.
- From the Speaker management panel ticket, to the table of what a Collaborator may do: Collaborators add, rename, edit, merge, and delete People on the Speakers tab and in the viewer's rename box; each act is Last activity and is audited with the owner as affected user.
- From the Folder management toggle transitions ticket, to the toggle: the owner sees nothing while Folder management is Off; Shares survive both toggles; the Sharing toggle keeps its value while greyed.
- From the Clips ticket, to the table and to Admins: a Collaborator's Clips appear on the Case's Clips tab with "Saved by", never on their own Clips page; an Admin who is not a Collaborator downloads a Case's Clip under the audit banner, audited with the affected user.
- From the Email notifications over SMTP ticket, to Notifications: the "case shared with you" mail; removing a Share sends nothing; the digest's "Shared with you" section; owner and Collaborators warned each in their own digest; a Deactivated or Blocked Collaborator is not mailed.
- From the Chat across a whole Case ticket, to the table and Last activity: "cross-Case Chat" reads Case Chat; every Collaborator may start, continue, export, and delete one; starting or continuing is Last activity.
- From the Case folder model on the mount ticket, as routed facts: one owner per Case; a Collaborator's uploads count against the owner's quota; a Collaborator's use is Last activity; Reassign and Transfer keep Shares; Delete ends them; search inside a Case for whoever can open it; the Cases page shows the owner on shared Cases.


## 3. Retention policy and the Recycle bin

This chapter fixes how the app deletes Cases by itself once Folder management is On: one Retention policy for the whole office, set by an Admin, with a Recycle bin behind it. The policy applies to Cases only. A Workspace keeps nothing past its Login session, so nothing in Phase 1 is timed by this policy and nothing from Phase 1 is absorbed into it. Audit retention (default three months, see the Audit log and logging chapter) is a separate setting and is independent of the Retention policy.

Two words are used with one meaning throughout: **deleted** means moved to the Recycle bin, where a Case can still be restored; **wiped** means gone for good, files and rows.

### Principles

1. **One clock per Case**: days since the Case's Last activity. Nothing inside a Case is timed on its own.
2. **The policy sticks**: the night a Case reaches the Retention period, it goes whole to the Recycle bin. No exception, no hold, no "fresh warning first". If an Admin shortens the period, every Case already past the new number goes to the Recycle bin that night. The Recycle bin is the safety net.
3. **Only use starts the clock over**: opening the Case counts, and so does anything done inside it. Handing it over (Reassign, Transfer) does not, and an Admin's audited opening does not.
4. **Warned twice**: the amber mark on the Cases page and the nightly Retention digest by email both start Warning-before-deletion days ahead.
5. **The Recycle bin follows the clock only**: a Case the clock deletes waits there, restorable, for the bin period, then is wiped for good. A person's own Delete stays final.

The clock, the warning, the digest, and the Recycle bin's wait all pause while Folder management is Off, and the days Off do not count (see The Off spells below, and the Folder management toggle chapter).

### Words

- **Retention period**: the admin setting for the number of whole days a Case may go unused before the app deletes it.
- **Retention policy**: the admin-set rule that moves a Case to the Recycle bin the night it reaches the Retention period without activity, whatever else is going on. One clock per Case; no exceptions and no holds. The clock pauses while Folder management is Off.
- **Last activity**: the most recent use of a Case by its owner or a Collaborator, opening the Case included; handing it over (Reassign, Transfer) and an Admin's audited opening excluded. The clock starts over at every Last activity.
- **Retention warning**: the amber mark a Case carries on the Cases page during its last days before deletion, with the matching line in the nightly Retention digest.
- **Keep**: the one-click act on a warned Case that starts its clock over, as opening the Case would.
- **Recycle bin**: where a Case the clock has deleted waits, out of every list and unusable, for a set number of days before it is wiped for good. The owner or an Admin can restore it meanwhile. Nothing a person deletes goes there. The wait pauses while Folder management is Off.
- **Retention digest**: the one Notification a person can get in a night, sent after the nightly sweep and listing every Case, their own or shared with them, that the Retention policy will delete soon. Owned by the Email notifications chapter.
- **Off spell**: a build term fixed in the Folder management toggle chapter: a span of days the app leaves out of every Retention count, recorded while Folder management is Off and for the outage a restore covers.

### The three settings

On the Cases page of the Admin panel, editable by an Admin, greyed while Folder management is Off, and absent from the Phase 1 build. Retention period and Warning before deletion fill the two placeholders the admin settings catalogue already held for this page; Recycle bin is added beside them. There is no per-Case value anywhere: one office-wide number is one rule.

| Setting | Type | Default | Range | When changed |
|---|---|---|---|---|
| Retention period | whole days | 30 | 7 to 3650 | The next sweep. A Case already past the new number goes to the Recycle bin that night. |
| Warning before deletion | whole days | 7 | 1 to 30, always shorter than the Retention period | The next page load for the amber mark; the next sweep for the Retention digest. |
| Recycle bin | whole days | 30 | 1 to 365 | The next sweep. Anything in the bin longer than the new number is wiped that night. |

### The clock

| Question | Rule |
|---|---|
| What starts it over | Any use of the Case by its owner or a Collaborator: opening the Case page; opening a Recording in it; adding or moving one in; a Correction; naming a Speaker or changing a Person; asking for a Summary, a Chat, or a Speaker suggestion; starting or continuing a Case Chat; saving or downloading a Clip; exporting; Retry; Process again; editing a Recording type or Description; deleting a Recording; renaming or sharing the Case; Keep; Restore from the Recycle bin. |
| What does not | Looking at the Cases page (the list). An Admin's audited opening of the Case under ADR 0004, and an Admin's use of a Case Chat under ADR 0004. Deleting a Case Chat. Reassign and Transfer: a new owner inherits the days left and opens the Case to start over. The Directory check deactivating the owner. Backups, sweeps, and anything else the app does by itself. |
| How it counts | Whole days from the Case's Last activity, judged at the nightly sweep: a Case whose Last activity is at least Retention-period days old is due. The days of any Off spell inside that span are left out. |
| Collaborators | Their use counts like the owner's. A leaver's Case keeps ticking through its Collaborators; with none, it runs down and goes to the Recycle bin like any other. |
| Empty Cases | Timed like any other; nothing is lost when one is deleted. |
| Jobs | A Case cannot be due while a Job runs in it: adding the Recording was activity, at most hours ago. |

#### The Off spells

The Retention policy counts days of neglect, and days nobody could use a Case are not neglect. The app records every Off spell as a row in Postgres; the Folder management toggle chapter fixes the rows (one from each change to Off until the next change to On, with cause `toggle`; one for the outage a restore covers, with cause `restore`). When the sweep counts a Case's days without use, it takes the whole days from the Case's Last activity to now and subtracts the days of every Off spell inside that span. A binned Case's days in the bin are counted from its deleted-on date the same way. Both causes are subtracted the same way. Last activity and deleted-on dates are never moved, so the dates on the Cases page stay true.

In plain words: a Case last used 20 days ago has 10 days left under the default period. If Folder management then goes Off for six weeks, the Case still has 10 days left when On returns; the owner gets the usual warning and can open the Case, or press Keep, to keep it.

### The warning

- **Where**: the Case's row on the Cases page turns amber and reads the line below once fewer than Warning-before-deletion days remain, with a **Keep** button beside it. The owner, every Collaborator, and Admins (on the Admin's Cases page, under the Expiring filter) see the same mark. There is no banner on the Case page: opening the Case page has already started the clock over, so the warning is gone by then.

```
Deletes in N days unless used
```

- **Keep**: starts the clock over for the full period, exactly as opening the Case would; it saves the person a click into the Case. Available to whoever sees the mark; an Admin's Keep is audited with the owner as affected user. It exists so a person who has seen the warning and knows they still need the Case does not have to open a Recording to prove it. That is all it is.
- **Email**: the warning by email is the nightly Retention digest, owned by the Email notifications chapter. What this chapter fixes: the 03:30 sweep, once it has marked and deleted, hands the `worker` one digest per person who owns or shares a Case inside the warning window, every night while there is one, one line per Case (the line above, with the days the Cases page shows, when the Case was last used, and its Recordings count). The digest starts the same night the mark appears. The last mail about a Case is the final warning on the night before its deletion; nothing is sent when the sweep deletes a Case into the Recycle bin, when it is restored, or when the bin wipes it. Cases whose owner is Deactivated or Blocked go to the Operator address's own nightly section instead of to the person. Wording and the rest of the cadence are in the Email notifications chapter.
- **Nothing else**: no sign-in interstitial and no count on other pages. The Cases page is the landing page while Folder management is On, so the mark is seen.

### Deletion into the Recycle bin

- **What the bin holds**: Cases the clock has deleted, whole. Nothing else: not anything a person deletes, not anything from a Workspace (nothing there is kept, so nothing there is binned), and never a single Recording on its own.
- **The night a Case is due**, the sweep deletes it into the Recycle bin, whole: Recordings, Transcripts, Corrections, Speaker names, People, Summaries, Chats, Case Chats, Clips (files and definitions together), Provenance, Descriptions, Recording types, and Shares go together. The Case leaves the Cases page, search, the Add to case and Move to case pickers, and every Collaborator's list; its Shares stop working; nothing in it can be opened, exported, or chatted, and a binned Case cannot be asked in a Case Chat. Its files stay in `cases/<case id>/` and its rows stay in Postgres, marked with a deleted-on date; the file sweeper leaves a binned Case's folder alone. Audit: "Case deleted (cause: retention)" with the counts. No email is sent.
- **The Recycle bin page**: reached from the Cases page; hidden while Folder management is Off. The owner sees their own deleted Cases: name, Recordings, size, deleted on, days left, **Restore**, **Delete permanently** (behind a confirmation naming the counts), and **Empty recycle bin** (behind a confirmation). Admins see every user's deleted Cases on the same page with an owner filter and the "Owner deactivated" mark, and may restore or permanently delete any. Collaborators see nothing of the bin.
- **Restore**: puts the Case back exactly as it was, Recordings, text, Clips, People, Case Chats, Shares, and all, and starts its clock over (otherwise it would be deleted again that night). Audit: "Case restored". A full quota never blocks a Restore: the Case never left the disk.
- **Room**: a binned Case counts against its owner's quota, since it is still on disk; Delete permanently and Empty recycle bin are how the owner makes room at once. The "Minimum free disk space" floor is unchanged.
- **The wipe**: the sweep wipes a Case that has sat in the bin for Recycle-bin days (Off spells left out): files and rows, nothing left, no recovery. Delete permanently and Empty recycle bin wipe at once in the same way, and the users list's Delete data wipes a leaver's binned Cases too. Audit: "Case permanently deleted" with the cause (recycle bin period, owner, or admin) and the counts, plus one "Recording deleted (cause: retention)" row per Recording, as Case delete writes. No email is sent.
- **A person's own Delete** of a Case or a Recording is unchanged: final at once, behind its confirmation (see the Cases chapter). Only the clock's deletions go to the bin.
- **Not affected**: Workspaces; the rules for the uploaded bytes; Backups (a binned Case rides in every Backup until it is wiped).

### Backups and the bin

The Backup and restore chapter owns the Backup. What touches this chapter:

- A Case the clock deletes waits its bin period, is wiped, and then stays in Snapshots for `BACKUP_KEEP_DAYS` (default 30) after the wipe. With the defaults a Case is gone from everywhere at most 90 days after its Last activity. A person's own Delete is final in the app and lingers in Snapshots for `BACKUP_KEEP_DAYS` too, unreachable.
- A restore can bring back a Case that was wiped after the Snapshot was taken. The app judges it by its dates, with the Off spells subtracted, including the `restore` spell the restore itself writes for the outage. Deleted-on dates are never reset at restore. A Case that was already due goes to the Recycle bin the first night after the restore, and the restore report lists what that night's sweep will do.

### The nightly sweep

One job at 03:30 in the quiet hour, before the file sweeper and the audit sweep, working from database state so a restart never skips or doubles anything. It checks the Folder management toggle first: while Off it does nothing, no marks, no deletions, no wipes, no mail, no audit row. While On, in order:

1. Mark the Retention warning on every Case newly inside its warning window and write one "Retention warning" row each.
2. Delete every Case that is due into the Recycle bin, one "Case deleted (cause: retention)" row each.
3. Wipe every binned Case past the Recycle bin period, one "Case permanently deleted" row each with its per-Recording rows.
4. Write one "Retention sweep ran" row with the counts: warned, deleted, wiped, GB freed.

Once it has marked and deleted, the sweep hands the `worker` the night's Retention digests (see The warning). Every count of days in steps 1 to 3 leaves the Off spells out. The first sweep after Folder management returns to On resumes where the clocks stopped: a Case with 12 days left when Off was applied has 12 days left, its amber mark and digest line pick up where they were, and a Case that is due goes to the bin that night, since the policy sticks from the moment On is applied.

### Admins

- The Admin's Cases page: an **Expiring** filter (Cases in the warning window) beside "Owner deactivated"; Keep on any row, audited with the owner as affected user.
- The Recycle bin page with the owner filter, as above; an Admin may restore a leaver's Case from it.
- The status page's Cases line:

```
Cases: N, X GB; M expiring; K in the recycle bin, Y GB
```

- Leavers: a leaver's Cases stay under the policy untouched until an Admin acts. Reassign hands them to a named user without starting the clock over. With Collaborators, the Case keeps ticking through them; with none, it runs down and goes to the bin like any other, with the warning showing on the Admin's Cases page under "Owner deactivated" and "Expiring", and its digest lines go to the Operator address. The users list's Delete data wipes a leaver's binned Cases too.
- No approval step anywhere: the policy runs by itself.

### What changes from Phase 1

Phase 1 rendered nothing of this. What Phase 1 carried: the Case table, empty in Phase 1, has a deleted-on date; the three settings sit among the admin settings catalogue's Phase 2 rows and are absent from the Phase 1 build. Phase 2 changes these Phase 1 rules and pages:

- **The nightly 03:30 job**: the retention sweep runs first, then the file sweeper, then the audit sweep. The file sweeper still removes only folders with no Recording row, and now leaves a binned Case's folder alone; the Discard and the sweepers skip every Recording with a Case.
- **The Admin panel**: the Cases page gains the three settings; the Recycle bin page is added, reached from the Cases page; the Admin's Cases page gains the Expiring filter; the status page's Cases line gains "M expiring; K in the recycle bin, Y GB".
- **The users list**: Delete data also wipes a leaver's binned Cases.
- **The audit log**: the two Phase 2 placeholders (retention warning, retention deletion) are replaced by the six rows below.
- **The Upload page**: the Add to case dropdown never lists a binned Case; adding a Recording to a Case is activity.
- **Backups**: a binned Case rides in every Backup until it is wiped.
- **Unchanged**: Workspaces and the Discard; the rules for the uploaded bytes; the "Minimum free disk space" floor; Audit retention.

### Rules changed in other chapters

- **Case folder**: opening the Case page counts as Last activity; Reassign and Transfer do not; the Retention policy is a second way out of a Case, into the Recycle bin, beside a person's Delete; the Case table carries deleted-on.
- **Sharing**: Collaborators see the mark and may Keep; a binned Case hides from them and its Shares stop working; Restore brings the Shares back.
- **Clips**: retention never touches a Clip alone; a Case goes to the bin whole with its Clips, files and definitions, and comes back whole. Downloading a Clip in a Case is Last activity, like an export.
- **Speakers tab**: any per-Case Speaker record (the Case's People) goes to the bin with its Case and comes back with it; nothing on the tab is timed on its own.
- **Case Chat**: a binned Case cannot be asked; asking a Case Chat is activity; Case Chats go to the bin and come back with their Case.
- **Email notifications**: the Retention digest, as above.
- **Backup and restore**: as above.

### Not in this phase

- No hold and no per-Case exception of any kind, now or later: nothing in the app can exempt a Case from the clock, and no owner or Admin can set a longer period for one Case. The way to keep a Case is to use it or press Keep.
- No Recycle bin for a person's own Delete: it is final. The bin is an app rule a later Release could widen to manual deletes without unpicking anything.
- No per-Recording clock: nothing inside a Case is timed on its own.
- No safeguard window before deletion, no fresh warning window after a shortened period, and no new-owner restart.
- No banner with Keep on the Case page; no sign-in interstitial.
- No Admin approval step.

### Environment keys

| Key | Read here for | Defined in |
|---|---|---|
| `BACKUP_KEEP_DAYS` | How long a wiped Case, or a Case a person deleted, lingers in Snapshots (default 30 days). | The Backup and restore chapter. |

### Audit rows

The Audit log chapter's fixed field set applies. No row carries a Description, a Speaker name, a Clip title, or any text; nothing is logged beyond the Case's name as its snapshot label.

| Row | Actor | Object and details | When it is written |
|---|---|---|---|
| Retention warning | system (retention sweep) | the Case, its name as snapshot label; affected user the owner; days left | Step 1 of the sweep, the night a Case first comes inside its warning window |
| Case kept | the person who pressed Keep | the Case; affected user the owner when it is someone else | When Keep is pressed |
| Case deleted (cause: retention) | system (retention sweep) | the Case; N recordings, X GB; affected user the owner | Step 2 of the sweep, the night a Case is due |
| Case restored | the person who restored | the Case; affected user the owner when an Admin restored | When Restore is pressed |
| Case permanently deleted | system, or the person | the Case; cause (recycle bin period, owner, admin); N recordings, X GB; plus one "Recording deleted (cause: retention)" row per Recording, as Case delete writes | Step 3 of the sweep for the bin period; at once for Delete permanently and Empty recycle bin |
| Retention sweep ran | system (retention sweep) | counts: warned, deleted, wiped, GB freed | Step 4 of the sweep, once a night; never while Folder management is Off |

### Settings

The admin settings catalogue holds the tables. This chapter depends on:

- **Retention period**, **Warning before deletion**, **Recycle bin**: fixed in this chapter (The three settings above).
- **Folder management**: the Folder management toggle chapter. While Off, the clock, the warning, the digest, and the bin's wait pause, the sweep does nothing, the Recycle bin page hides, and the three settings above are greyed.
- **Sharing**: the Sharing chapter. Collaborators' use is activity, and they see the mark and may Keep.
- **Minimum free disk space**: unchanged; a binned Case counts toward its owner's quota.
- **Audit retention**: separate from the Retention policy, default three months; the Audit log and logging chapter.

### Left to the build

- Where in the sweep the hand-off of the Retention digests to the `worker` sits: the sources fix only that it comes once the sweep has marked and deleted (steps 1 and 2), and that the Email notifications chapter owns the digest.
- How the amber mark and its N are shown between sweeps: the Warning before deletion setting takes effect "at the next page load", while the sweep writes the Retention warning row for Cases newly inside the window each night; the days shown must leave the Off spells out and match the digest's line.
- The wording of the Delete permanently confirmation (it "names the counts") and of the Empty recycle bin confirmation.
- The layout of the Recycle bin page beyond the columns and buttons listed (name, Recordings, size, deleted on, days left, Restore, Delete permanently, Empty recycle bin; the owner filter and the "Owner deactivated" mark for Admins).
- Which of the three causes the "Case permanently deleted" row carries when the users list's Delete data wipes a leaver's binned Cases; the sources fix the causes as recycle bin period, owner, and admin, and say nothing more.
- The user guide and admin guide text (the Repository, releases, and distribution chapter): the user guide explains the clock in plain words ("opening a case starts the clock over"), the warning, Keep, the Recycle bin, and that a person's own Delete is final; the admin guide documents the three settings, the sweep, the Recycle bin page, the audit rows, and that shortening the period deletes that night.

### Sources

Retention policy; Folder management toggle transitions.

### Amendments applied

- From Folder management toggle transitions to The clock, The warning, The nightly sweep, and Deletion into the Recycle bin: the clock, the warning, the digest, and the bin's wait pause while Folder management is Off through Off spells; the sweep checks the toggle first and writes no row while Off; the Recycle bin page is hidden while Off.
- From the backup ticket (recorded on both source tickets) to Backups and the bin and The Off spells: the keep rule (`BACKUP_KEEP_DAYS` after the wipe, 90 days with the defaults); the outage a restore covers is an Off spell with cause `restore`; deleted-on dates are never reset at restore; the restore report lists what the first night's sweep will do.
- From the Clips ticket to The clock: downloading a Clip in a Case is Last activity, like an export.
- From the email notifications ticket to The warning and The nightly sweep: the email is the nightly Retention digest to everyone who owns or shares a warned Case; the last mail is the final warning the night before deletion; nothing is sent on deletion, restore, or wipe; Deactivated or Blocked owners' Cases go to the Operator address; no digest while Folder management is Off, and the first sweep after On sends it as on any other night.
- From the Case Chat ticket to The clock and Deletion into the Recycle bin: starting or continuing a Case Chat is Last activity, deleting one is not, an Admin's use under ADR 0004 is not; a binned Case cannot be asked; Case Chats go to the bin and come back with their Case.
- From the maintainer, on the v1.6.0 build, to the Recycle bin page: reached as the third tab of the Cases page's strip (Mine, Everyone's, Recycle bin) as well as by its own address; its columns and controls unchanged.

## 4. The Folder management toggle

Folder management is the admin toggle that enables Cases. This chapter fixes what happens when an Admin turns it On or Off: what appears, what hides, what pauses, and what the audit log records. It is a Phase 2 setting, default Off, absent from the Phase 1 build. Nothing about it is hard to reverse: the toggle hides and pauses, and never deletes.

### Principles

1. **Off hides, never deletes.** The rule every feature toggle follows applies to Cases whole: every Case, and everything in it, goes out of reach for everyone until On, and nothing on disk or in the database changes.
2. **Off pauses the clock.** The Retention policy counts days of neglect, and days nobody could use a Case are not neglect. The warnings, the emails, and the Recycle bin's wait pause with it.
3. **The toggle is an ordinary setting.** It changes through the tray, at once, with the ordinary Setting changed audit row and the tray's optional note. No confirmation, no schedule, no note required.
4. **On restores exactly what Off hid.** Nothing is re-created or re-keyed; the pages come back over the same rows and files.

### Words

- **Folder management**: the admin toggle that enables Cases. Off: Workspaces only; every Case is hidden from everyone and kept, its Retention policy clock paused, nothing deleted. On: users may keep Recordings in Cases, and everything Off hid comes back as it was. "Folder management" is the setting's name in the Admin panel; the app says "cases" to users, never "folders".
- **Off spell** (a build term, not a glossary word): the span between a change to Off and the next change to On, kept by the app as a row in Postgres so the days inside it are left out of every Retention count. A row carries a cause, `toggle` or `restore`.

### Turning On

| Question | Rule |
|---|---|
| When | At once: every page served after Apply follows the new value. The Cases link and the Move to case buttons appear on the next page load; the Cases page is the landing page from the next sign-in. |
| What users get | The Cases page (the landing page, with "your recordings" reachable at the top), Case pages with the Speakers tab, "Add to case" and Recording type on the Upload page, "Move to case" on Done Recordings, in Details, and in the sign-out dialog, "Add recordings" on each Case page, and the Recycle bin page from the Cases page. The Chat tab on Case pages follows the Chat across cases setting. |
| What Admins get | The Cases page of the Admin panel with the Expiring and Owner deactivated filters, the Recycle bin page, Reassign and Delete data on the users list, and the Cases rows un-greyed (Sharing, Retention period, Warning before deletion, Recycle bin, Recording types, Speaker roles), each holding the value it held before. |
| Workspaces | Untouched. What is in "your recordings" stays there until it is moved or the Login session ends. |
| Announcement | None: no banner, no email, no interstitial. The empty Cases page says the line below and nothing else. |
| The clocks | Resume where they stopped. The first sweep after On counts from the end of the Off spell; a Case due that night goes that night, since the policy sticks from the moment On is applied. |
| Audit | The ordinary Setting changed row (Folder management, Off to On, the tray's note if any) with the counts shown again in the details block. |

```
No cases yet. A case keeps recordings after you sign out.
```

### Turning Off

**Hidden means**: out of every list, page, picker, search, export, download, Chat, and zip, for everyone, owner, Collaborator, and Admin alike. Nothing in a hidden Case can be opened, moved, or deleted until On. The owner sees nothing of their shared Cases while Off, exactly as Collaborators see nothing. The app looks like Phase 1 again, Workspace only.

| What | While Off |
|---|---|
| Cases, the Recordings in them, Transcripts, Summaries, Chats, Case Chats, Clips, Provenance, Descriptions, Recording types | Kept exactly as they were, files under `cases/` and rows in Postgres. The toggle never touches `cases/`; the 03:30 file sweeper still removes only folders with no Recording row; the Discard and the sweepers still skip every Recording with a Case. |
| Shares, People, Roles | Kept. Shares survive both toggles. The Sharing toggle keeps its value, greyed. |
| Binned Cases | Kept, with their wait paused. |
| The Cases pages, Case pages, Speakers tabs, Recycle bin page, Cases link, "Add to case", Recording type, "Move to case", "Add recordings" | Gone from the next page load. Anyone who asks for a Case page or a Recording in a Case lands on "your recordings" with the first line below; someone on a Case page when Off is applied lands there at their next click. |
| The Batch page | A row for a Recording in a Case reads the third line below, with no link; the Batch download ("Download N transcripts") leaves such Recordings out. The sign-out dialog counts Workspace items only, as it already does. |
| The Clips page | Workspace Clips only. The Clips of Recordings in Cases are unreachable; nothing is re-rendered at On. |
| Quotas | Cases keep counting against their owner's quota, since they are still on disk; a user at quota makes room in the Workspace or asks IT. |
| Recordings still uploading, and Jobs in flight | Finish into their Case, hidden: a Recording added to a Case belongs to it from the first byte, and a queued Job runs as submitted. A Chat, a Summary, or a Case Chat question in flight for a Case finishes and is hidden with it. Nothing is bounced back to the Workspace. |
| Admins | The Cases page of the Admin panel and the Recycle bin page are gone too; Reassign and Delete data grey out again, as in Phase 1. The users list keeps its "N in session, M in cases" figure and the status page keeps its Cases line, followed by the second line below, so IT can see what is parked. Open their Workspace (ADR 0004) is unchanged. To act on a Case, turn On. A leaver's Cases wait hidden as they would have waited visible. |

```
Cases are turned off. Ask IT if you need them.
```

```
Folder management has been off since <date>
```

```
in a case (cases are off)
```

### The pauses

The Retention policy's clock, the Retention warning, the Retention digest, and the Recycle bin's wait all pause while Off, and the days Off do not count.

- The app records every Off spell (started when the toggle goes Off, ended when it goes On) as a row in Postgres with cause `toggle`.
- A Case's days without use are the whole days from its Last activity to now, minus the days of any Off spell inside that span. A binned Case's days in the bin are counted from its deleted-on date the same way. Last activity itself is never moved, so the dates on the Cases page stay true.
- The 03:30 retention sweep checks the toggle first and does nothing while Off: no marks, no deletions, no wipes, no mail, no audit row. The next sweep after On resumes: a Case with 12 days left when Off was applied has 12 days left, its amber mark and digest line pick up where they were, and a Case that is due goes to the bin that night.
- Email: while Off no Retention digest is built, because the sweep does nothing; the first sweep after On sends the digest as on any other night, with the days that were left, and nothing special is sent on the change. Share and handover mails cannot happen while Off, since Cases are hidden; "batch finished" mails continue, since they belong to the Workspace. The Email notifications chapter owns the mails.

### The setting in the tray

Folder management is an ordinary setting in the tray of the Admin panel. Its tray row carries the counts at the time of the change; the note stays optional; Apply writes it at once with the rest of the tray; nothing is scheduled, and an Admin who wants a quiet moment picks one. No setting confirms: the tray is the confirmation. The audit row is the ordinary Setting changed row (name, old value, new value, the note if typed) with the counts of Cases, GB, and owners hidden (Off) or shown again (On) in the details block. The tray row on a change to Off, with the counts of that moment:

```
Folder management: On to Off. Hides 14 cases, 210 GB, for 6 users. Nothing is deleted.
```

#### The catalogue row

| Setting | Type | Default | Phase | What it does | When changed |
|---|---|---|---|---|---|
| Folder management | On or Off | Off | 2 | Users may keep Recordings in Cases past sign-out. | At once. On: the Cases pages appear and the paused clocks resume. Off: every Case is hidden from everyone and kept, its Retention clock paused, nothing deleted; the tray row shows the counts. Greys Sharing, Retention period, Warning before deletion, Recycle bin, Recording types, Speaker roles, Reassign, and Delete data while Off. |

### On again after Off

Everything comes back exactly as it was, People and Shares included, the Sharing toggle at the value it held, and the first sweep after On resumes the paused clocks. A Case whose owner was deactivated meanwhile shows under Owner deactivated. Nothing is re-created or re-keyed.

### Off spells and a restore

Off spells are rows in Postgres, so they ride in every Backup's database dump and come back with a restore, and the counts stay right. The after-restore step writes an Off spell with cause `restore`, from the Snapshot's timestamp to the restore's completion, when Folder management was On at the Snapshot; when it was Off, the still-open `toggle` spell already covers the gap and nothing is added. Both causes are subtracted the same way, so a restored Case's days are judged with the Off spells subtracted, as the app always does. The Backup and restore chapter owns the restore.

### What the user pages show while Off

- The Recordings page ("your recordings") is the landing page again, as in Phase 1. It shows the line "Cases are turned off. Ask IT if you need them." to anyone who arrives from a Case page or a Recording in a Case.
- The Upload page has no "Add to case" and no Recording type.
- Done Recordings, Details, and the sign-out dialog have no "Move to case".
- The Batch page shows "in a case (cases are off)" with no link for a Recording that went into a Case, and the Batch download leaves it out.
- The Clips page lists Workspace Clips only.
- Search finds nothing in a Case.
- There is no Cases link, no Case page, no Speakers tab, no Chat tab, and no Recycle bin page.
- The user guide (the Repository, releases, and distribution chapter) says that if the Cases pages disappear, IT has turned them off and nothing is lost.

### What changes from Phase 1

Phase 1 rendered nothing of this. What Phase 1 carried: the Off spell table, empty in Phase 1 like the Case and Share tables, so turning Folder management On adds pages, not tables; and the Folder management setting absent from the Phase 1 build. Phase 2 changes these Phase 1 rules and pages:

- **The Admin panel**: gains the Folder management row (default Off, the catalogue row above) and the Cases rows it greys.
- **The users list**: Reassign and Delete data, greyed in Phase 1, un-grey while On and grey again while Off; the "N in session, M in cases" figure stays.
- **The Batch page**: a Recording in a Case reads "in a case (cases are off)" with no link while Off, and the Batch download leaves it out.
- **The Recordings page**: shows "Cases are turned off. Ask IT if you need them." to anyone who lands there from a hidden Case.
- **The status page**: its Cases line is followed by "Folder management has been off since <date>" while Off.
- **The audit log**: the Phase 2 placeholder "Folder management toggled, the toggle's mandatory note goes in the details block" is replaced by the ordinary Setting changed row, with no mandatory note.
- **Unchanged**: Workspaces and the Discard (the toggle never touches them); Open their Workspace (ADR 0004); the 03:30 file sweeper's rule; the sign-out dialog's counts; "batch finished" mails.

### Rules changed in other chapters

- **Admin settings catalogue and panel**: the Folder management placeholder gets its row; Reassign and Delete data greyed while Off; the status page's Cases line gains the off-since line; the tray row's counts.
- **Case folder**: turning Off with Cases present hides them; the toggle never touches `cases/`.
- **Sharing**: the owner sees nothing of their shared Cases while Off, exactly as Collaborators; Shares survive both toggles; the Sharing toggle keeps its value while greyed.
- **Retention policy**: the clock, the sweep, the warnings, and the bin's wait pause while Off through Off spells (the Retention policy and the Recycle bin chapter).
- **Clips**: while Off, the Clips of Recordings in Cases are unreachable and the Clips page shows Workspace Clips only; nothing is re-rendered at On.
- **Upload page**: "Add to case" and Recording type appear only while Folder management is On.
- **Case Chat**: unreachable while Off; a question in flight finishes and is hidden with the Case. The **Chat across cases** toggle is narrower: Off hides the Chat tab on every Case page and keeps the Chats, touching nothing else.
- **Speakers tab**: People follow their Cases, hidden with them and shown again with them; the "Speaker roles" setting is greyed while Off.
- **Workspace lifecycle**: confirmed, no change: the toggle never touches Workspaces, and their contents are discarded at the end of the Login session either way.
- **Backup and restore** and **Email notifications**: as above.

### Not in this phase

- No confirmation dialog and no mandatory note: the tray is the confirmation, and the note is optional as for every other setting.
- No scheduled toggle: the change applies when Apply is pressed.
- No read-only mode for Cases, no refusing Off while Cases exist, and no export or deletion of Cases at Off: Off hides and keeps.

### Environment keys

None named by the sources. Folder management is a setting in the Admin panel, not a key in the environment file.

### Audit rows

| Row | Actor | Object and details | When it is written |
|---|---|---|---|
| Setting changed | the Admin who pressed Apply | setting name Folder management, old and new value, the tray's note when one was typed; in the details block the counts of Cases, GB, and owners hidden (Off) or shown again (On) | When Apply writes a tray holding a change to Folder management, in either direction |

The retention sweep writes no row while Off. Nothing else is new.

### Settings

The admin settings catalogue holds the tables. This chapter depends on:

- **Folder management**: fixed in this chapter (The catalogue row above).
- **Sharing**: keeps its value, greyed, while Off; the Sharing chapter.
- **Retention period**, **Warning before deletion**, **Recycle bin**: greyed while Off; the Retention policy and the Recycle bin chapter.
- **Recording types**, **Speaker roles**: greyed while Off, holding their values.
- **Chat across cases**: the narrower toggle for the Chat tab; the Case Chat chapter.

### Left to the build

- The wording of the tray row on a change to On: the sources fix the Off wording and that both directions carry the counts (Cases, GB, owners).
- The exact text of the status page's Cases line while Off beyond the off-since line quoted above.
- The admin guide text (the Repository, releases, and distribution chapter): Off means hidden, paused, nothing deleted, the counts in the tray, turn On to act on a leaver's Cases; On means the pages appear and the clocks resume. And the user guide's line that if the Cases pages disappear, IT has turned them off and nothing is lost.
- The Upload page prototype's README note (the Upload page and Batch page chapter): "Add to case" and Recording type appear only while Folder management is On; nothing rendered.

### Sources

Folder management toggle transitions; Retention policy.

### Amendments applied

- From the backup ticket to Words and Off spells and a restore: the Off spell row gains a cause, `toggle` or `restore`; the after-restore step writes a `restore` spell only when Folder management was On at the Snapshot.
- From the email notifications ticket to The pauses: no digest while Off; the first sweep after On sends it as on any other night with the days that were left; nothing special on the change; Share and handover mails impossible while Off; "batch finished" mails continue.
- From the Case Chat ticket to Turning Off and Rules changed in other chapters: Case Chats hide with their Cases and a question in flight finishes hidden; the Chat across cases toggle is narrower.
- From Folder management toggle transitions to the Audit log's placeholder: the "Folder management toggled" row with a mandatory note is replaced by the ordinary Setting changed row with an optional note; the mandatory note asked for at charting is withdrawn.
- From Folder management toggle transitions to the Retention policy: the pause through Off spells, recorded in the Retention policy and the Recycle bin chapter.


## 5. People and the Speakers tab

Inside a Case, a Speaker's name means a person. This chapter fixes the Person (the Case row behind a name), the Speakers tab on the Case page where People are managed, what the viewer does differently inside a Case, and how People follow the Case through sharing, Last activity, the Recycle bin, handing over, exports, and the audit log. All of it exists only while Folder management is On. Nothing in this chapter changes the Workspace: a Transcript there has its Speakers (Speaker 1, Speaker 2), the user names them in the viewer, and Suggest names works from that one Transcript, as Phase 1 fixed.

### Principles

1. **Inside a Case, a name means a person.** Every Speaker in the Case's Transcripts given the same name is the same Person; the name is the link, and there is no separate "assign this speaker to a person" step.
2. **People live inside one Case.** Nothing links a name across Cases, and there is no office-wide list.
3. **The tab manages names; the AI assistant stays in the viewer.** Suggest names remains one Transcript per click, on request, as the Phase 1 AI assistant chapter fixed; inside a Case it is told the Case's People. The Speakers tab shows who is in the Case, where, and which Recordings still have unnamed Speakers.
4. **Nothing is kept for voice matching.** The app requests and stores no speaker embeddings in either phase; voice matching is out of scope (see the Deferred and ruled out chapter).
5. **Everything else follows the Case rules already made**: sharing, Last activity, the Recycle bin, Reassign and Transfer, and the audit log's no-names rule.

### Words

- **Person**: one human being in a Case, as named across its Recordings. Holds a name, an optional Role, and optional notes. A Person shows up as a Speaker in each Recording they are in, which is why the two words differ.
- **Role**: the optional part a Person plays in the matter (Defendant, Officer, Interpreter), picked from the admin-kept "Speaker roles" list.
- **Speakers tab**: the tab on the Case page that lists the Case's People. The viewer's sidebar section keeps its Phase 1 name, the Speakers panel; the two do different jobs, and this chapter says "tab" for the Case page and "panel" for the viewer throughout.
- **Speaker** (sharpened): still a voice label in one Transcript, optionally given a name. Inside a Case, Speakers given the same name are one Person.

### What changes from Phase 1

Every Phase 1 rule about Speakers holds unchanged in the Workspace. Inside a Case these rules change:

- **The viewer's rename box** (Phase 1 Transcript viewer and player chapter) was built as a pick-or-type box with nothing to list. Inside a Case it lists the Case's People as the user types, and a name that matches a Person joins that Person. It still changes that Recording only.
- **The viewer's Speakers panel** shows each Speaker's Role as a small badge after the name. In the Workspace there is no badge.
- **The "Known names:" line** that Suggest names sends (Phase 1 AI assistant chapter) was built from a list that Phase 1 fills with Vocabulary only. Inside a Case the list is the Case's People first, each as "Name (Role)" when a Role is set, then the Batch's Vocabulary, then the Office Vocabulary. The Speaker-suggestion prompt template's wording does not change.
- **The kept-suggestion rules** are unchanged, with one clarification: "never a name already held" means held by a Speaker in that Transcript. A name held elsewhere in the Case is allowed and expected, since a Person may appear in many Recordings.
- **The suggested pill** shows the Role when the suggestion matches a Person; Accept joins that Person or creates one.
- **Merge in the viewer** works as in Phase 1 and, inside a Case, the surviving Speaker's Person applies.
- **The Speaker row's Person link**, empty throughout Phase 1, is filled for every named Speaker inside a Case and kept equal to the Speaker's own name.
- **The Word Transcript export's Appearances table** (Phase 1 Exports chapter) has a Role column that Phase 1 hides while empty; inside a Case it is filled from the Person when the Person holds a Role.
- **The audit log** (Phase 1 Audit log and logging chapter) gains five rows in the Cases category, listed under Audit rows below.
- **The admin panel** (Phase 1 Admin panel chapter) gains one settings row, "Speaker roles", on the Cases page; no page and no rail entry is added.

#### What this chapter fixes for the other Phase 2 chapters

- **Cases**: the Case page gains the Speakers tab; its Recordings list reads "2 named, 1 unnamed" in its Speakers column; People are Case rows; Move to case and Add to case make a Recording's named Speakers become or join People.
- **Sharing**: Collaborators act on People exactly as the owner does.
- **Retention policy and the Recycle bin**: Last activity widens to adding, renaming, editing, merging, or deleting a Person; People ride with the Case into the Recycle bin and back.
- **The Folder management toggle**: People are Case rows and follow their Case through Off and On; nothing about them needs a rule of its own.
- **Clips in Cases**: nothing changes; a Clip's excerpt and captions carry Speaker names as today and no Role.
- **Case Chat**: the Case Chat is told the Case's People.
- **Backup and restore**: People and the Speaker links are Postgres rows inside the dump; nothing on disk.

### What Phase 1 already carries

The Phase 1 build carries the shape and shows none of it: the Speaker row has an empty Person link; the viewer's rename box is built as a pick-or-type box with nothing to list; the Known names line is built from a list that Phase 1 fills with Vocabulary only; the Appearances table has a Role column hidden while empty; the settings catalogue lists "Speaker roles" among the Phase 2 rows. Turning Folder management on adds the tab, not tables.

### The Person

#### Fields

Name (required), Role (optional, one of the Speaker roles), notes (optional plain text, a few lines). Who added it and when, and when it last changed, are kept for the tab's own display; nothing else.

#### One name, one Person

Names match ignoring letter case and surrounding spaces; a Person keeps the spelling it was first given, and Rename changes it everywhere. So a name is unique inside a Case, and two people who share one are told apart by what is typed, such as "John Smith (officer)".

#### How a Person comes to be

Any of:

- naming a Speaker in the viewer inside the Case (typing a name or accepting a suggestion);
- a Recording moved into the Case carrying named Speakers;
- Add person on the Speakers tab.

A name that matches a Person joins it; a name that matches none creates one.

#### How a Speaker is tied to a Person

A Transcript's Speaker keeps its own name, as in Phase 1, and inside a Case also points at its Person; the app keeps the two equal in the same transaction. An unnamed Speaker points at nothing. The Sides of a Two-channel call are Speakers like any other: unnamed until named.

#### A Person stays

A Person stays until someone deletes or merges it, even with no Recording left ("in 0 recordings" on the tab), so a Person added before any Recording is named is offered to the rename box and the AI assistant from the start.

### The Speakers tab

The Case page gets a tab beside the Recordings list, labelled "Speakers" with the number of People, and a header line such as "5 people, 2 recordings with unnamed speakers".

- **The People list**, sorted by name. Each row: the name, the Role, the first line of the notes, and "in N recordings", which expands to the Recording titles, each a link that opens the viewer at that Person's first Segment there. Row actions: Rename, Edit (Role and notes), Merge into, Delete.
- **Add person**: a name (refused with "already in this case" when it matches a Person), a Role, notes.
- **Unnamed speakers**: under the list, one line per Recording whose Transcript has at least one unnamed Speaker ("<title>: 2 unnamed"), each a link to that viewer. A Recording without Speakers (no Diarization, one Side) appears nowhere on the tab. This list is the review workflow across the Case: open the Recording, use Suggest names or type the names, come back.
- **The Recordings list** (the Case page's first tab, see the Cases chapter) reads "2 named, 1 unnamed" in its Speakers column.
- **Search**: the Case page's search box already finds Speaker names; the tab has no search of its own, since a Case holds a handful of People.
- **No Suggest names on the tab** (see Not in this phase).

### In the viewer, inside a Case

- The sidebar's Speakers panel (Phase 1) shows each Speaker's name with the Role as a small badge after it. Notes are shown on the Speakers tab only.
- The rename box is a pick-or-type box: as the user types it lists the Case's People (name, Role, "in N recordings") plus "New person: <typed>". Picking or typing a name that matches a Person joins it, without a confirmation, since the list shows it is an existing Person. Under the box: "Changes this recording only. To rename <name> in every recording, use the case's Speakers tab", with the link.
- A suggested pill shows the Role when the suggestion matches a Person ("Suggested: John Smith (Defendant)"); Accept joins that Person, or creates one when the name is new. Accepting a role suggestion ("Officer") creates or joins a Person of that name; the Role field is not set by itself, the user sets it on the tab.
- Merge in the viewer (two Speakers of one Transcript, confirmed) works as in Phase 1: the surviving Speaker's Person applies; the other Person stays in the Case and may now be empty.

### Rename, merge, split, delete

- **Rename (tab).** Changes the Person's name and every linked Speaker across the Case in one transaction. Refused when the new name matches another Person ("already in this case; merge instead").
- **Rename (viewer).** Changes that Recording's Speaker only: it becomes, or joins, another Person, and never touches the other Recordings. This is the split; there is no split control.
- **Merge (tab).** Drag one Person onto another, or Merge into, then confirm ("Merge Jon Smith into John Smith? 4 speakers in 3 recordings become John Smith."). Every Speaker of the merged Person is relinked and renamed; the survivor keeps its Role; the merged Person's notes, if any, are appended to the survivor's notes under its old name; the merged Person is deleted. A Person merge never merges two Speakers inside one Transcript: when both were in the same Recording, that Transcript now shows two Speakers with the same name, and the viewer's Merge control joins them, confirmed as today.
- **Delete (tab).** Confirmed. The Person's Speakers go back to their labels (Speaker 1, Side 1 Speaker 1); the row goes.
- **Edit (tab).** Role and notes.

### The AI assistant inside a Case

- Suggest names is unchanged in shape: in the viewer, on request, one call per Transcript, whenever two or more Speakers have no name.
- Inside a Case, the "Known names:" line the app adds becomes: the Case's People first, each as "Name (Role)" when a Role is set, then the Batch's Vocabulary, then the Office Vocabulary, duplicates removed, "none" when empty. The Speaker-suggestion prompt template (version 1) already says "Use the known names below when the talk points to one of them", so it does not change.
- The kept-suggestion rules stand: high or medium only, one per Speaker, never a name already held by a Speaker in that Transcript, never the same name for two Speakers in one call. A Person may appear in many Recordings, so a name held elsewhere in the Case is allowed and expected.
- No Suggest names on the Speakers tab. Should the unnamed list prove too much clicking, a Case-level button that runs one call per Recording is a later addition, not a Phase 2 one.
- Summary and the per-Recording Chat are unchanged: the rendered Transcript carries Speaker names as today. The Case Chat is told the Case's People: one line ahead of the Transcripts, "People in this case: John Smith (Defendant), Maria Lopez (Interpreter)", Roles in brackets when set, notes never, "none yet" when the Case has no People (the Case Chat chapter has the rest). Notes are for people, not the AI assistant.

### Moving, Process again, Delete

- **Move to case and Add to case.** A Recording moved in brings its Speaker names, and each becomes a Person or joins one by name. A Recording added at upload starts with unnamed Speakers. Moved on to another Case, each named Speaker becomes or joins a Person there (a new Person there takes the Role and notes along; an existing one keeps its own); the links to the old Case's People are dropped, and those People stay until deleted.
- **Process again** inside a Case: the new Transcript's Speakers are unnamed (the Phase 1 rule); the People stay; the Recording appears under Unnamed speakers again. Retry behaves the same for a new Transcript.
- **Delete Recording**: its Speakers go; the People stay.
- **Upload**: nothing changes on the Upload page; People arrive after transcription, and Add to case picks none.

### Sharing, Last activity, the Recycle bin, handing over

- Collaborators see and do everything on the Speakers tab and in the rename box that the owner can: add, rename, edit, merge, delete. Nothing inside a shared Case is private, and naming Speakers was already theirs.
- Adding, renaming, editing, merging, or deleting a Person by the owner or a Collaborator is Last activity. An Admin's act in someone else's Case is audited with the owner as affected user and does not count, as an Admin's opening does not.
- People ride with the Case into the Recycle bin, come back on Restore, and are wiped at permanent deletion. Reassign and Transfer carry them unchanged.
- People are Case rows and follow their Case through Folder management Off and On; nothing about them needs a rule of its own (see The Folder management toggle chapter).

### Admins

Admins may open any Case's Speakers tab and act on it under ADR 0004, every act audited with the owner as affected user. No admin page is added: the admin panel's rail is unchanged apart from the Speaker roles row on the Cases page.

### Exports, Clips, and search

- **Word Transcript export**: the cover's Appearances table gains a Role column, filled from the Person when the Recording is in a Case and the Person holds a Role, blank otherwise; the cover's "Speakers" fact line and everything else are unchanged.
- **Plain text, Captions, Clip excerpts and captions, and the Summary and Chat exports**: unchanged. A Clip's excerpt and captions carry Speaker names as today and no Role.
- **Case page search**: unchanged; it already covers Speaker names.

### In the database

Postgres only, nothing on disk: a Person table (Case, name, Role as text, notes, added by, added when, changed when; the name unique per Case ignoring letter case and surrounding spaces) and a Person link on the Transcript's Speaker row (empty in the Workspace and for an unnamed Speaker). The Speaker's own name column stays and is kept equal to its Person's. People and the Speaker links are backed up with the database, as rows inside the dump (see the Backup and restore chapter).

### Environment keys

None. Nothing in this chapter is configured in `.env`.

### Audit rows

Cases category, metadata only, the Phase 1 audit log's field set. The object is the Person by id with the snapshot label "Person <id> in <Case name>" (the Case name is already a snapshot label; a Person's name and notes never appear in any log, beside Speaker names). Affected user: the owner whenever a Collaborator or an Admin acts.

| Row | When it is written | Actor | Details |
|---|---|---|---|
| Person added | when a Person comes to be, by any of its ways | the person who acted | how: typed on the tab, named in the viewer, suggestion accepted, moved in |
| Person renamed | when a Person is renamed on the tab | the person who acted | from the tab; count of Speakers relinked |
| Person edited | when a Person's Role or notes are changed on the tab | the person who acted | which field changed, role or notes; never the value |
| Person merged | when one Person is merged into another on the tab | the person who acted | survivor id, merged id, count of Speakers relinked, count of Recordings |
| Person deleted | when a Person is deleted on the tab | the person who acted | count of Speakers unnamed |

The viewer's existing rows (Speaker renamed, Speakers merged, Speaker suggestion accepted or rejected) keep firing for acts in the viewer; a viewer rename that creates a Person writes its own row and Person added. A change to the Speaker roles setting writes the ordinary Setting changed row.

### Settings

By their catalogue names; the admin settings catalogue defines each.

- **Speaker roles** (Cases section, a Phase 2 row): the list the Role field is picked from. A list, one per line, shipped with Defendant, Witness, Victim, Officer, Attorney, Interpreter, Interviewer, Caller. A change applies to the next Role pick; a Role removed from the list stays on the People that hold it (the Recording types rule). Greyed while Folder management is Off; absent from the Phase 1 build like every Phase 2 row.
- **Folder management** (Cases section): the Speakers tab, the rename box's list of People, and the People in the Known names line exist only while it is On.
- **Sharing**: whether Collaborators exist to act on People.
- **Office Vocabulary**, the **Speaker suggestions** switch, and the **Speaker-suggestion prompt template** (all Phase 1; the template stays at version 1): whether Suggest names runs and what it is sent after the People.

### Not in this phase

- An office-wide list of People, or any link between names across Cases: ruled out (see the Deferred and ruled out chapter).
- Voice matching of the same Speaker across Recordings: ruled out; a later effort decides for itself and may Process old Recordings again.
- Storing speaker embeddings: the WhisperX service keeps its `return_speaker_embeddings` door and the app never opens it in either phase.
- A Suggest names button on the Speakers tab that runs one call per Recording with unnamed Speakers: a later addition if the unnamed list proves too much clicking.

### Left to the build

- The size of the notes field: the tickets fix "optional plain text, a few lines", and that the tab's row shows its first line.
- Where the tab shows who added a Person and when, and when it last changed: the tickets fix that these are kept for the tab's own display and for nothing else.
- Whether the Person table itself ships in the Phase 1 build or arrives with the Phase 2 Release's database changes: the tickets fix that the Speaker row's Person link exists, empty, in Phase 1, and that turning Folder management on adds the tab and no tables.

### Sources

Speaker management panel; Chat across a whole Case (the People line amendment).

### Amendments applied

- From Chat across a whole Case to Speaker management panel, "The AI assistant": the Case Chat is told the People line, Roles in brackets when set, notes never, "none yet" when the Case has no People.
- Within Speaker management panel: the round-1 name "Speakers panel" for the Case page's tab replaced by "Speakers tab" at resolution, the viewer's sidebar section keeping "Speakers panel".
- From Speaker management panel to the audit log rules: the five Person rows.
- From Speaker management panel to the LLM features rules: the Known names line inside a Case lists the Case's People with Roles first.
- From Speaker management panel to the Word export rules: the Role column in the Appearances table.
- From Speaker management panel to the settings catalogue: the Speaker roles row.
- From Speaker management panel to the Case folder rules: the Speakers tab, People as Case rows, Move to case creates or joins People, the Recordings list's Speakers column.
- From Speaker management panel to the sharing rules: Collaborators act on People; Last activity widened to changing a Person.
- From the v1.11.0 build, which shipped this chapter ahead of the Cases release because Suggest names needed the People (`docs/research/speaker-suggestions.md`), the decisions left to it and three departures the maintainer accepted:
  - **The name is the link, and there is no Person column on the Speaker row.** The chapter's "Person link" was to be kept equal to the Speaker's name in every transaction; the build keeps the name alone and finds a Speaker's Person by matching the name inside the Case, ignoring letter case. Every rule that spoke of relinking is met by renaming: Rename on the tab renames the Person and every Segment of that name in the Case in one transaction; Merge renames the merged Person's Segments to the survivor's name; a Recording moved to another Case needs no links dropped. One table (`core_person`, migration 0019) instead of two changes.
  - **Delete puts Speakers back to their labels by working them out again from the engine's own labels**, per Side, exactly as at storage (`queue.unname`), so a deleted Person's Speakers read Speaker 1, Speaker 2 in the order the engine gave, not in the order they were named.
  - **The notes field holds up to 1,000 characters**; the tab's row shows the first line. Who added a Person and when, and when it last changed, are kept and shown on no page yet.
  - **The Person table ships with this Release**, not with the Cases release; it stays hidden while Folder management is Off like every Cases page.
  - **The rename box** lists the Case's People through the browser's own suggestion list under the field (a `datalist`), each as "Name (Role), in N recordings"; there is no "New person: <typed>" entry, since typing any other name makes one, and the note under the box says so. In the Workspace the box is the browser's prompt, as in Phase 1.
  - **Merge on the tab is the Merge into control only**; dragging one Person onto another is not built.
  - **The People come first in the "Known names:" line**, and Suggest names also sends two lines the chapter did not know: "Roles to choose from:", the Speaker roles list, and "Evidence found in the transcript:", the self-introductions and forms of address the app finds itself, each with its line number. A kept-suggestion rule was added: a name (not a role) is dropped unless some evidence line carries it. The Speaker-suggestion prompt template stays at version 1; the added lines are the app's, outside the template. A new setting, Speaker suggestion method, names the way this works ("evidence") so a better method can be added and chosen later; the catalogue defines it.


## 6. Clips in Cases

Phase 2 adds Cases (the Folder management toggle On), and with them a second place a Clip can live. Everything in the Clips chapter stands unless this chapter says otherwise.

### What changes from Phase 1

| Phase 1 rule | Phase 2 |
|---|---|
| A Clip is listed in one place, the Clips page. | A Clip is still listed in one place, but that place depends on where its Recording is: the Clips page for the Workspace's Clips, the Case's Clips tab for a Case's. The Clips page in the navigation stays the Workspace's list only. |
| Saved by and saved on are recorded but not shown. | In a Case the Clips tab shows "Saved by", because Collaborators exist. |
| A Clip and its file go with the Recording at the Discard. | A Clip on a Recording in a Case is never discarded at sign-out. It is retained, moved to the Recycle bin, restored, and wiped with its Case. |
| The Clips page shows a Downloaded column and the sign-out dialog counts undownloaded Clips. | The Case's Clips tab has no Downloaded column, since nothing is lost at sign-out there. The sign-out dialog's count and zips cover Workspace Clips only. |
| An Admin does not adjust, rename, or delete another user's Workspace Clip. | The same holds in a Case for an Admin who is not a Collaborator. An Admin who is a Collaborator acts as any Collaborator does. |
| "Clips available" Off hides New Clip, the Clips sheet, and the Clips page. | It also hides the Case's Clips tab. |
| Workspace Clips are never backed up. | Clips inside a Case ride in the nightly Snapshot with their Recording and come back with a restore. |

New in Phase 2: saving or downloading a Clip in a Case is Last activity for the Retention policy, like an export.

### The Clips tab

- The Case page gets a **Clips tab** beside Recordings and Speakers, listing every Clip of every Recording in the Case.
- It carries the Clips page's columns (Title, Recording, Span, Length, Options, Status, Size, Saved) plus **Saved by**, and no Downloaded column.
- It has a Download all for the Case: the same flat zip as the Clips page's, with one "Clip downloaded" audit row per Clip.
- Per Clip, the Clips page's controls apply (Play, Download, Open in viewer, Rename, Adjust, Delete), since every Collaborator may download, save, re-render, and delete any Clip in the Case.
- The tab is hidden while "Clips available" is Off.

### A Clip follows its Recording

- The Recording is the unit of a Case, so a Clip lives with its Recording in a Case and never moves alone.
- A Clip made in the Workspace rides into the Case with its Recording at Move to case, with its file and definition. Nothing ever moves back; Delete is the only way out of a Case.
- A Clip made on a Recording that is already in a Case (added at upload with Add to case, or moved in) is the Case's from the start and appears on the Clips tab, never on the Clips page.
- Rendering, the excerpt and captions built at download time, Adjust, Rename, "Captions out of date", the "Longest Clip" limit, the reason class `clip_render_failed`, and the media worker rules are unchanged inside a Case.
- Nothing about a Clip changes for Speakers named as People in the Case: the excerpt and captions carry the Speaker names as the Transcript shows them, and a Person's Role is never printed on them.

### Collaborators and Clips

- Sharing a Case shares its Clips: every Collaborator can download, save, re-render, and delete any Clip in the Case. A Clip can be remade, so the owner-or-adder rule that guards Recordings does not apply to Clips.
- A Collaborator's Clips show on the Case's Clips tab, never on their own Clips page. "Saved by" says who saved each one.
- A Collaborator's Clip work in the Case is the Case's activity (see the Sharing chapter and the Retention policy and the Recycle bin chapter).

### Admins

- An Admin who is not a Collaborator sees the Case's Clips tab and every Recording's Clips sheet under the audit banner, and may play and download, each download an audit row with the affected user; such an Admin does not adjust, rename, or delete a Clip in the Case. An Admin's audited opening of a Case is not Last activity.

### Retention, the Recycle bin, and Backup

- Retention never touches a Clip alone. A Case goes to the Recycle bin whole with its Clips, files and definitions, comes back whole on Restore, and is wiped whole. Nothing in a Case is deleted piecemeal by the clock.
- Clips inside a Case (`cases/<case id>/<recording id>/clips/`) ride in the nightly Snapshot with their Recording and come back with a restore. Workspace Clips are never backed up: `scratch/` is excluded and a restore discards every Workspace.

### Folder management Off

- While Folder management is Off, the Clips of Recordings in Cases are unreachable with their Cases; the Clips page shows Workspace Clips only; nothing is re-rendered when On returns.
- A Clip render in flight for a Recording in a Case finishes and is hidden with it.

### Files on disk

```
cases/<case id>/<recording id>/
  clips/
    <clip id>.mp4        (video Recording)
    <clip id>.mp3        (audio Recording)
```

The rendered file sits under the Recording's `clips/` folder inside `cases/<case id>/<recording id>/` and is retained and deleted with the Case.

### Not in this phase

- Combining several Clips into one file is not part of Phase 2 as planned.
- A Clip never moves out of a Case, alone or with its Recording.

### Audit rows

No new row. The Clips chapter's rows (Clip created, Clip re-rendered, Clip downloaded, Clip deleted, Clip render failed) apply inside a Case; a download by an Admin who is not a Collaborator carries the affected user, and the Download all for the Case writes one "Clip downloaded" row per Clip.

### Settings

By their names in the admin settings catalogue:

- **Folder management**: Off makes every Case, and its Clips, unreachable.
- **Sharing**: Off hides every Share without ending it; Collaborators' access to a Case's Clips goes with it.
- **Clips available**: Off also hides the Case's Clips tab.
- **Retention policy**: saving or downloading a Clip in a Case starts its clock over.
- **Longest Clip** and **Longest Recording** (Limits): unchanged.

No environment key belongs to this chapter.

### Left to the build

- The Clips tab's per-Clip controls: the sources fix its columns, "Saved by", the Download all, and the absence of a Downloaded column, and grant every Collaborator download, save, re-render, and delete; they do not list the tab's controls separately. Carry the Clips page's controls over.
- Whether the downloaded mark is still recorded for a Clip in a Case: the tab never shows it and nothing in a Case depends on it.
- Whose quota a Collaborator's Clip counts against: the Sharing chapter's rule for Recordings a Collaborator adds ("count against the owner's room") is the only guide the sources give.
- Whether "Download everything" at sign-out ever includes a Case's Clips: the sources tie it to the Workspace and say nothing in a Case is lost at sign-out.

### Sources

Clips: model, lifecycle, and management (its Phase 2 section, and the facts it records from the Case folder model, Sharing model, Retention policy, toggle transitions, backup, and Speaker management panel tickets).

### Amendments applied

- From the Clips ticket to the Case page rules: the Clips tab, "Saved by", the Download all for the Case, no Downloaded column.
- From the Clips ticket to the Sharing rules: a Collaborator's Clips appear on the Case's tab only; an Admin who is not a Collaborator downloads under the banner.
- From the Clips ticket to the Retention policy rules: downloading a Clip in a Case is Last activity.
- From the Clips ticket to the admin settings rules: "Clips available" Off also hides the Case's Clips tab.


## 7. Case Chat

A Case Chat is a Chat whose ground is the whole Case: a question is answered from every Transcript in the Case as it stands when the question is asked, read whole, in one Reading when the Case fits and in parts when it does not. This chapter fixes the Chat tab on the Case page, what a question reads, the size rule, Citations, whose the Chat is, its export, its prompt template, its limits and failures, its settings, and its audit row. The Phase 1 Chat rules stand wherever this chapter is silent.

### Principles

1. **A Case Chat is a Chat whose ground is the Case**: every Transcript in the Case as it stands when the question is asked, nothing to pick, nothing outside it.
2. **Whole Transcripts, never an index**: the AI assistant reads Transcripts whole, in one Reading when the Case fits and in parts when it does not; nothing is embedded, indexed, or kept between questions.
3. **The Case's People go ahead of the talk**, with their Roles and never their notes.
4. **Its own switch**: "Chat across cases", so the heavy feature can be stopped alone.
5. **No Summary of the whole Case**: "Summarise this case" is a question to the Case Chat.
6. **The Phase 1 Chat rules stand wherever this chapter is silent**: whole answers by worker and polling, no streaming, the AI notice, Ground rules first, editable instructions and fixed plumbing, metadata-only audit rows, nothing logged.

### Words

- **Case Chat**: a Chat grounded in every Transcript in a Case, as the Case stands when each question is asked. It belongs to the Case, is open to whoever can open the Case, and leaves with it. One Case only: a Case Chat never reads across several Cases.
- **Reading**: one pass of the AI assistant over whole Transcripts that fit together in one call, about six hours of talk. A question takes one Reading when the Case fits and otherwise several Readings and a combining step; the page calls Readings "parts" when there are several.

### What changes from Phase 1

- **Chat** (Phase 1 AI assistant chapter) was grounded in one Transcript. It is now grounded in one Transcript or, as a Case Chat, in every Transcript in a Case. The per-Recording Chat and its overlay do not change.
- **Citation**: in a Case Chat it names the Recording as well as the time and opens that Recording in the viewer at that moment, where a Phase 1 Citation seeks the player of the open Recording.
- **The prompt inventory** gains the Case chat template (editable, version 1) and the fixed combining instruction. The Phase 1 line that Chat across a Case is Phase 2 fog is superseded by this chapter.
- **Reason classes** gain `llm_case_too_large`; `llm_too_long` gains a second use, one Transcript that cannot fit a Reading even alone.
- **Time limits**: a Phase 1 Chat call keeps two minutes; a Case Chat question runs up to 15 minutes as one task, each engine call inside it keeping the two minutes; "Let the model think before answering" doubles both.
- **Four in flight**: a Case Chat's Readings run two at a time inside the four.
- **Answer caps**: a Phase 1 Chat answer is capped at 1,500 tokens; a Case Chat's combined answer at 2,000.
- **The audit log** (Phase 1 Audit log and logging chapter) gains `case_chat_turn`; the "export made" row gains the kind `case chat`; the Chat delete row applies to Case Chats.
- **Exports** (Phase 1 Exports chapter): the Chat export gains a Case form with the Case's cover facts and its own file name. "Download everything" is untouched; a Case has no zip.
- **The guides** (Phase 1 Repository, releases, and distribution chapter): the user guide gains the Case Chat page; the admin guide the two settings.

#### What this chapter fixes for the other Phase 2 chapters

- **Cases**: the Case page gains the Chat tab; Case Chats are Case rows; the Case's Delete confirmation counts them among the chats it names.
- **Sharing**: Collaborators may start, continue, export, and delete Case Chats; the phrase "cross-Case Chat" reads "Case Chat".
- **Retention policy and the Recycle bin**: starting or continuing a Case Chat is Last activity; deleting one is not; a binned Case cannot be asked.
- **People and the Speakers tab**: the People line is sent, with Roles, never notes.
- **The Folder management toggle**: "Chat across cases" Off hides the tab only; Folder management Off hides everything as before, and a question in flight when Off is applied finishes and is hidden with its Case.
- **Backup and restore**: Case Chats are Postgres rows with the Case, in the dump; nothing new.
- **Admin panel additions in Phase 2**: two settings rows and one prompt template row.

### The Chat tab

The Case page gets a **Chat** tab beside the Recordings, Speakers, and Clips tabs. It works like the viewer's Chat overlay: the Case's Chats listed newest first, each named from its first question, with New chat and Delete; the conversation with Copy on every answer; Export to Word. The tab holds Case Chats only: a Recording's own Chats stay in its viewer and never appear here, and a Case Chat never appears in a viewer.

While a question runs the tab shows "Reading 5 transcripts..." and polls every two seconds, as the viewer's Chat does. When the Case is read in parts it shows "Reading 40 transcripts in 4 parts. This takes a few minutes." A question that fails shows its reason and "Try again", never a half answer.

### What a question reads

#### The Case as it stands

Every Recording in the Case whose Transcript exists at the moment the question is asked, in upload order. A Recording added or moved in later is read from the next question on. One that is Queued, Running, or Failed is skipped, and the answer opens with "2 recordings were not read: still transcribing" (or "failed"). One being processed again is read as it stands, the old Transcript until the new one lands. A Recording whose Transcript is in its own language (Translate unticked) is read as it is; the answer is English regardless.

#### The People line

Before the Transcripts, one line built from the Speakers tab:

```
People in this case: John Smith (Defendant), Maria Lopez (Interpreter), Officer Diaz
```

Roles in brackets when set, notes never, "none yet" when the Case has no People.

#### One header line per Transcript

Written by the app, carrying per Recording what the Phase 1 Transcript-nature line carries:

```
Recording 3 of 14: <title>, <Recording type>, uploaded <date>, <length>, machine transcription in English, speakers separated automatically
```

with "machine translation to English from Spanish" or "machine transcription in Spanish" in place of the transcription phrase as the Transcript's nature demands. Then the Transcript's lines exactly as the viewer's Chat renders them:

```
[n] [hh:mm:ss] Speaker: text
```

n from 1 for each Recording, current Speaker names, Corrections in the text, "(corrected)" after the label.

#### The history

The last turns of the same Case Chat up to 16k tokens, oldest dropped first, go with every Reading and with the combining call.

#### Grounding

Answers come only from those Transcripts. Legal advice, opinions on guilt or credibility, and anything outside them get "I can only answer from the transcripts in this case."

### Readings: the size rule

- **One Reading** is one engine call holding up to 100,000 tokens of rendered Transcript, the Phase 1 ceiling (about six hours of talk), estimated as Phase 1 does (four characters per token plus 10%). With the Ground rules, the Case chat template, the People line, 16k of history, and the answer cap, a Reading fits the Local engine's 131,072-token window as well as a Shared engine's larger window (262,144 tokens on the engine the app was designed against). The planning research on LLM handler capabilities warns that models use the middle of a long context badly, which is why a Reading stays at Phase 1's size instead of filling the Shared engine's window.
- **When the Case fits one Reading**, the question is one call, exactly as a Recording's Chat is, and the page shows "Reading 5 transcripts...". This is the common Case: a few calls and an interview.
- **When it does not**, the app packs whole Transcripts into as few Readings as they fit, in upload order, never cutting a Transcript; asks every Reading the same question with the same history, two Readings at a time so one Case never fills the AI assistant's four lanes; then one **combining call** writes the answer from the Readings' answers. The page shows "Reading 40 transcripts in 4 parts. This takes a few minutes." The Readings' own answers are never shown or kept; only the combined answer is stored.
- **A Transcript larger than a Reading** (very dense talk near the six-hour limit) gets a Reading of its own; if even alone it would not fit the engine's window with the rest of the prompt, the question fails with `llm_too_long` naming the Recording.
- **The ceiling.** One question reads at most the Limits setting "Case chat: most hours of talk per question" (default 120 hours, range 6 to 600), measured as the summed length of the Recordings it would read; the ceiling counts hours of talk, not Recordings. Beyond it the question refuses with `llm_case_too_large` and "This case is too large for one question (140 hours of recordings; the limit is 120)." At the default the worst question is about twenty Readings, two at a time, inside the time limit below.
- **Nothing between questions.** No index, no embeddings, no cached prompt; each question renders the Case afresh. Retrieval with an embedding model is ruled out (see the Deferred and ruled out chapter): no embedding service is a dependency of this app, and an office with the Local engine needs nothing more than it has.

### Citations

The AI assistant writes `[Recording 3, 00:12:45]`. The app matches the Recording number to the question's header lines and the time to a Segment start of that Recording (the Phase 1 match rule) and shows the Citation as the Recording's title and time, "Jail call 2026-03-04 at 00:12:45", a link that opens that Recording in the viewer at that moment. A Citation the app cannot match stays plain text, as in Phase 1. A Recording later deleted or moved to another Case leaves its Citations as plain text marked "(recording removed)". In the combining call the Readings' Citations are kept word for word and never invented; the app checks the combined answer's Citations again before display.

### Whose it is

- **Case content.** A Case Chat is a Postgres row keyed to the Case, not to a Recording, with its turns; it goes with the Case on Transfer and Reassign, into the Recycle bin and back, into the Snapshot with the Case's other text, and is deleted with the Case (the Case's Delete confirmation counts Case Chats among the chats it names, see the Cases chapter).
- **Who may.** The owner and every Collaborator see the same Case Chats and any of them may start one, continue one, export one, or delete one (a Chat is not a destructive action in the Sharing chapter's sense; Delete asks "Delete this chat?"). Starting, continuing, and exporting are Last activity; deleting a Case Chat is not. An Admin's use under ADR 0004 is audited and never Last activity.
- **The "Chat across cases" switch.** Off hides the Chat tab on every Case page and keeps the Chats; it is independent of the viewer's Chat toggle, so the viewer's Chat can stay on while the heavy feature is stopped. Both sit under the AI assistant master switch.
- **Folder management Off** hides the tab with the Case; a question in flight when Off is applied finishes and is hidden with its Case (see The Folder management toggle chapter). A binned Case cannot be asked (see the Retention policy and the Recycle bin chapter).
- **Process again** on one Recording: the Case Chat shows "Earlier answers used a previous transcript of <title>; new questions use the current one." Old Citations still open the Recording, since it is the same Recording.
- **Recordings that leave.** A Recording deleted or moved out is simply not read from the next question on; the Chat and its answers stay.

### Export

Export to Word follows the Phase 1 Chat export (Phase 1 Exports chapter): layout A typography; the cover facts are the Case's (Case name, owner, and the Recordings the Chat has read across its questions, each with its title, Recording type, upload date, and length); the header block (started when, by whom, how many questions, model); the AI notice above the Transcription notice and, when any Recording read was translated, the Translation notice too; then "Question n." and each answer in order, declines included, Citations printed as the Recording's title and [hh:mm:ss] in grey. File name:

```
<case name> - case chat <yyyy-mm-dd hhmm>.docx
```

One "export made" audit row of kind `case chat`. The Workspace's "Download everything" is untouched and a Case has no zip.

### The prompt inventory

Two additions to the Phase 1 inventory (Phase 1 AI assistant chapter).

#### Case chat (prompt template, editable, version 1)

Default wording:

```
Answer the user's questions using only the transcripts of the recordings in this case. If the answer is not in them, say so in one sentence and do not guess. Quote the transcripts when it helps. For every statement you rely on, give the recording and the time as [Recording 3, 00:12:45], copied from the line it appears on, and never make one up. When several recordings bear on the question, say which says what. Keep answers short unless the user asks for detail. If a question asks for legal advice, an opinion on guilt or credibility, or anything outside these transcripts, reply: I can only answer from the transcripts in this case.
```

Every Reading's request is, in order: the Ground rules, then this template, then the People line, the header lines and Transcripts of that Reading, the history, and the question. Admins edit it in the panel with Reset to default; a change applies to the next question.

#### Combining (app, fixed)

The system message is the Ground rules; the user message says:

```
The same question was answered separately over several parts of one case's recordings. Write one answer from these part answers. Keep every [Recording n, hh:mm:ss] reference exactly as written and add none. Where the parts disagree, say so. If no part found an answer, say the transcripts do not answer it.
```

followed by the history, the question, and the part answers labelled "Part 1 of 4" and so on. Plumbing, not a template: it has no version and Admins do not edit it.

The People line and the header lines are app plumbing like the Transcript-nature line.

### Limits and failure behaviour

| Matter | Rule |
|---|---|
| Delivery | One question is one Procrastinate task on the `llm` queue run by `llm-worker`; its Readings are engine calls made from that task, two at a time within the four in flight; the page polls every two seconds |
| Time limits | 15 minutes for the whole question; each engine call keeps the Chat rule of two minutes; both doubled when "Let the model think before answering" is On |
| Retries | One automatic retry per call on a connection error; none on a timeout |
| Half answers | Never: if any Reading or the combining call fails after its retry, the question fails with that reason class and "Try again" |
| Answer caps | A single Reading's answer 1,500 tokens (it is the answer); part answers 1,500 each; the combined answer 2,000; a cap hit shows "The answer was cut short." |
| Too large | `llm_case_too_large` (the ceiling) and `llm_too_long` (one Transcript that cannot fit) |
| Engine down | "The AI assistant is not available right now", `llm_unreachable`, as in Phase 1 |
| Everything else | Phase 1's `llm_timeout`, `llm_refused`, `llm_bad_output`, `llm_error` |
| Privacy | Questions, part answers, and answers are never logged; the engine keeps nothing |

### Reason classes

| Class | When |
|---|---|
| `llm_case_too_large` | new in Phase 2: the question would read more hours of talk than "Case chat: most hours of talk per question" allows |
| `llm_too_long` | Phase 1 class; in a Case Chat, one Transcript that cannot fit a Reading even alone, named in the failure |
| `llm_unreachable` | the engine is down, as in Phase 1 |
| `llm_timeout`, `llm_refused`, `llm_bad_output`, `llm_error` | as in Phase 1, from whichever call failed after its retry |

### Environment keys

None are added. The Case Chat reaches the engine with the Phase 1 settings: the engine's address and model from the panel and its token from `.env` (Phase 1 AI assistant chapter).

### Audit rows

| Row | When it is written | Details |
|---|---|---|
| `case_chat_turn` | once per question, when the question ends, whatever the outcome | the Case as the object (its name as the snapshot label) with the owner as the affected user; transcripts read; Readings used; model name; endpoint host; the Ground rules and Case chat template versions ("ground-rules v1; case-chat v1"); input and output token counts summed over the calls; duration; outcome (ok or the reason class) |
| export made, kind `case chat` | when a Case Chat is exported to Word | the Phase 1 export row |
| Chat delete | when a Case Chat is deleted | the Phase 1 Chat delete row |
| ADR 0004 opening | when an Admin opens a Case Chat in someone else's Case | as in the Phase 1 audit log, the owner as affected user |

Never the question, the prompt, or the answer.

### Settings

By their catalogue names; the admin settings catalogue defines each.

- **AI assistant** master switch (Phase 1): everything in this chapter sits under it.
- **Chat across cases** (AI assistant section, a Phase 2 row): the switch above; independent of the viewer's Chat toggle.
- **Case chat: most hours of talk per question** (Limits, a Phase 2 row): the ceiling in the size rule above.
- **Case chat** (AI assistant section, prompt templates, a Phase 2 row): the template above, version 1, with Reset to default; a change applies to the next question.
- **Ground rules** (Phase 1 prompt template): first in every Reading's request and the combining call's system message.
- **Let the model think before answering** (Phase 1): On doubles both time limits.
- **AI notice**, **Transcription notice**, and **Translation notice** (Phase 1): printed on the export as above.
- The engine's **address** and **model** (Phase 1).
- **Folder management** and **Sharing** (Cases section): whether Cases and Collaborators exist.

### Not in this phase

- Tags on Recordings in a Case, typed by users, so that a Case Chat can be asked about one tag only: in neither phase's list (see the Deferred and ruled out chapter); Recording type, an admin-kept list picked at upload, is not it.
- A picker to narrow a Chat to chosen Recordings: not built; a question about one Recording has the viewer's Chat, and a picker could be added later without changing anything here.
- A retrieval index (embeddings and rerankers) behind the Case Chat: ruled out.
- A Summary of the whole Case: not a feature; "Summarise this case" is a question to the Case Chat, and its answer exports like any other. The Readings machinery could carry a Case Summary if the office ever asks.

### Left to the build

- How a question remembers which Recordings it read and in which order: the tickets fix that a Citation names a Recording by its number in that question's header lines, that a stored Citation must still open the right Recording later, and that the export's cover lists the Recordings the Chat has read across its questions with title, Recording type, upload date, and length.
- How the app knows the configured engine's window for the "would not fit even alone" check: the tickets give the Local engine's 131,072 tokens and the 262,144 of the engine the app was designed against, the Phase 1 estimate of four characters per token plus 10%, and name no setting; whatever the Phase 1 build does for `llm_too_long` applies.
- How Transcripts are packed into Readings beyond the fixed rules: whole Transcripts, in upload order, as few Readings as they fit, a Transcript never cut, a Transcript larger than a Reading alone in its own.
- What the tab shows for a Case with no readable Transcript (every Recording still Queued, Running, or Failed, or no Recording at all): the tickets fix only that such Recordings are skipped and that the answer names them.
- What happens to a question in flight when "Chat across cases" is switched Off: the tickets fix only that Off hides the tab and keeps the Chats; for Folder management Off the question finishes and is hidden with its Case.

### Sources

Chat across a whole Case; Speaker management panel (the People the line is built from).

### Amendments applied

- From Chat across a whole Case to the Phase 1 LLM features rules: the inventory gains the Case chat template and the fixed combining instruction; reason class `llm_case_too_large`; the "Chat across a Case is Phase 2 fog" line is superseded.
- From Chat across a whole Case to the settings catalogue: the two Phase 2 rows and the template row.
- From Chat across a whole Case to the audit log rules: the `case_chat_turn` row and the reason class.
- From Chat across a whole Case to the Word export rules: the Case Chat export.
- From Chat across a whole Case to the Case folder rules: the Chat tab; Case Chats are Case rows; the Delete confirmation counts them.
- From Chat across a whole Case to the sharing rules: "cross-Case Chat" reads "Case Chat"; Collaborators may start, continue, export, and delete Case Chats.
- From Chat across a whole Case to the Retention policy rules: starting or continuing a Case Chat is Last activity; deleting one is not; a binned Case cannot be asked.
- From Chat across a whole Case to Speaker management panel: the People line is sent, with Roles, never notes.
- From Chat across a whole Case to the Folder management toggle rules: "Chat across cases" Off hides the tab only; Folder management Off hides everything as before.
- From Chat across a whole Case to the backup rules: Case Chats are Postgres rows with the Case, in the dump; nothing new.
- From Chat across a whole Case to the GitHub distribution rules: the user guide gains the Case Chat page; the admin guide the two settings.
- Within Chat across a whole Case: the Answer's forms win over round 1 where they differ ("(recording removed)" for a Recording deleted or moved out, Chats listed newest first and named from the first question, "Let the model think before answering" as the setting's name).
- From the v1.12.0 build, which shipped this chapter ahead of the Cases release, the decisions it left to the build:
  - **How a question remembers what it read.** Each turn stores its header lines' list (`readings`): per Recording read, in the question's order, the Recording's id, title, type, upload date, length, whether it was translated, and the Transcript's creation time. A Citation is stored as its text with the Recording's id and the Segment's start, so it opens the right Recording later whatever the Case now holds; the tab resolves it at display time to the title and time, or to "(recording removed)" when the Recording has left the Case. The export's cover lists the union of every turn's readings, in the order first read.
  - **The engine's window** for "would not fit even alone" is the Phase 1 build's constant (131,072 tokens, the Local engine's) with the Phase 1 estimate, as the Phase 1 `llm_too_long` check uses; the failure names the Recording in the turn's own words.
  - **Packing** is the fixed rules and nothing more: whole Transcripts in upload order, a new Reading when the next would take the current one past 100,000 estimated tokens, a Transcript larger than that alone in its own.
  - **A Case with no readable Transcript** shows the tab with the line "No recording in this case has a transcript to read yet." and refuses a question (409) rather than queueing one that would fail.
  - **A question in flight when "Chat across cases" is switched Off** finishes on the worker and is kept with its Chat, hidden until the switch is On again; nothing is cancelled.
  - **The Readings' own answers are never stored**, as the chapter says; the part answers live only in the worker's memory until the combining call returns.
  - **The tab polls without an ADR 0004 row.** Opening the Case page already wrote the Admin's row; the state answer the tab fetches every two seconds does not write another. Asking and exporting, which open a Chat, do.
  - **The reason class `llm_case_too_large`** carries the person's line "This case is too large for one question." in the engine's table, and the turn carries the figures ("140 hours of recordings; the limit is 120").
  - **The time limit** of fifteen minutes is kept by the task itself: before each engine call it checks the time spent and fails with `llm_timeout` when the limit has passed; each call keeps the Chat's two minutes.


## 8. Email notifications

Phase 2 gives the app one way out by mail. It sends plain-text messages over SMTP through the office's relay: four kinds of Notification to people (the Retention digest, a Case shared with them, a Case handed to them, a Batch finished) and Operator mail to one IT mailbox. Phase 1 sends no mail and carries no mail settings; every Phase 1 rule this chapter changes is listed under "Changes to Phase 1" below. The relay is the office's and swappable, every number here is a setting or an environment key, and nothing here is hard to reverse.

### Principles

1. **Mail announces, never acts.** Nothing waits for a message to be sent or read, deletion least of all. A person who never reads mail is exactly as safe as the app's pages make them.
2. **The pages are the record.** Every message repeats something a page already shows (the amber row, the New mark on a shared Case, the Batch page). A person without an Email address loses the message and nothing else.
3. **A message says what an audit row may.** Names of Cases and Recordings, counts, dates, display names, one link. Never content.
4. **One mail a night for the Retention policy**, per person, however many Cases. The other kinds are one per event.
5. **The directory is the only source of addresses.** The app never lets anyone type an address for a directory account, and it re-reads the directory so a value filled in later arrives by itself.
6. **All of it Phase 2.** Phase 1 sends no mail and carries no mail settings.

### Words

- **Notification**: an email the app sends to a person about their own Cases, Shares, or Batches: the Retention digest, a Case shared with them, a Case handed to them, or a Batch finished. It names things and quotes nothing, it never carries an attachment, and nothing in the app ever waits for it.
- **Email address**: the mailbox a person's Notifications go to: the directory's `mail` value, read at each sign-in and refreshed by the Directory check. Nobody types one for a directory account; a Local admin's is typed when the account is made. A person without one gets no mail and misses nothing the app's pages show.
- **Operator address**: the one IT mailbox, named in `.env` as `OPERATOR_EMAIL`, that receives the app's own mail: backup, drill, and restore reports, the nightly lines about Cases whose owner has left, and the test message. Replies to every message the app sends go there. Never a person's Notification.
- **Retention digest**: the one Notification a person can get in a night, sent after the nightly sweep and listing every Case, their own or shared with them, that the Retention policy will delete soon.
- **Retention warning**: the amber mark a Case carries on the Cases page during its last days, with the matching line in the nightly Retention digest.
- **Directory check**: the nightly comparison of app accounts against the directory, also run on demand, which also refreshes each account's Email address.

### The kinds of mail

| Kind | To | When | What it says |
|---|---|---|---|
| Retention digest | every owner and Collaborator with a Case inside the warning window | nightly, right after the 03:30 sweep, every night while there is something to say | "Deleting soon": each of the person's own Cases with days left, last used, and Recordings count; "Shared with you": the same for Cases shared with them, with the owner's name |
| Case shared with you | the new Collaborator | at once, when the owner shares | the Case's name, the owner's name, what a Collaborator may do |
| Case handed to you | the new owner | at once, on Transfer or Reassign | the Case's name, who handed it, the days left on its clock |
| Batch finished | the person who submitted the Batch, when they ticked "Email me when this batch finishes" | at once, when the last Recording in the Batch has ended | how many transcribed and how many failed, the failed Recordings' titles with their reason in plain words, where the Recordings are |
| Operator: Cases whose owner has left | the Operator address | nightly, with the digests | each Case whose owner is Deactivated or Blocked and inside the warning window: name, owner, days left |
| Operator: backup | the Operator address | as the Backup and restore chapter says | that chapter's four messages, fixed wording |
| Test message | the signed-in Admin (the Email page's button) or the Operator address (`./transcribe check`) | on demand | fixed wording |

Nothing else, ever: no welcome or sign-in mail; no mail when a Case is deleted, restored, or wiped, or when a Share is removed, or when Keep is pressed; no per-Recording mail; no mail for a refused upload or a single failed Job (the Batch mail covers it); no mail about the Directory check's result or a service being down; no mail about another person's material; and never a mail from the drill project.

Admins' own mailboxes are never used for the app's mail. Operator mail goes to the Operator address only.

### The Retention digest

**When.** The 03:30 sweep marks and deletes, then hands the `worker` one digest task per recipient. The digest is built from database state when the task runs, in office time (`TZ`).

**Who.** Every person with at least one Case inside the warning window that they own or that is shared with them. A person with three Cases in the window gets one mail, not three. Deactivated and Blocked people are never mailed; their own Cases go to the Operator address instead, and their Collaborators still see those Cases under "Shared with you", since a leaver's Case keeps ticking through its Collaborators (see the Retention policy and the Recycle bin chapter).

**Lines.** One per Case, the app's own format, not editable. Under "Deleting soon" (the `{cases}` block; "Deleting soon" is the block's name, not a printed heading, since the template's own line introduces it):

```
- <Case>: deletes in N days unless used (last used <date>, N recordings)
```

Under "Shared with you" (the `{shared}` block, which prints its own heading):

```
Shared with you:
- <Case> (owner: <owner's display name>): deletes in N days unless used
```

N is the number the Cases page shows. On the last night the line reads "deletes in 1 day unless used".

**Cadence.** Every night while anything is inside the window, so a Case in its last seven days puts a line in seven mails. Nothing goes out when there is nothing to say.

**The last mail.** The final warning on the night before deletion, "deletes in 1 day unless used". Nothing is sent when the sweep deletes the Case into the Recycle bin, when it is restored, or when the bin wipes it: the warnings that came before are the whole of the mail about a Case. The Recycle bin page is where a person learns that a Case was deleted.

**Keep.** Pressing Keep or opening the Case starts its clock over, so the Case leaves the next digest.

**Folder management Off.** The sweep does nothing, so no digest is built. The first sweep after On sends the digest as on any other night, with the days that were left, and nothing special is sent on the change.

**Sample.** The default wording with the "Deleting soon" and "Shared with you" blocks filled in (the Case names and dates are illustrations):

```
Subject: Gideon Transcribe: cases deleting soon

Hello <recipient's display name>,

These cases delete unless someone uses them:
- US v. Smith: deletes in 3 days unless used (last used 2026-06-08, 14 recordings)
- Jones interview 2026-08: deletes in 6 days unless used (last used 2026-06-11, 2 recordings)

Shared with you:
- People v. Doe (owner: <owner's display name>): deletes in 1 day unless used

Open a case, or press Keep on the Cases page, to start its clock over: https://<APP_HOSTNAME>:<HTTPS_PORT>/cases

Sent automatically by Gideon Transcribe (https://<APP_HOSTNAME>:<HTTPS_PORT>/). Replies go to <OPERATOR_EMAIL>.
```

### Case shared with you

Sent when the owner confirms the Share dialog, to the new Collaborator. It names the Case and the owner and repeats the dialog's words on what a Collaborator may do. Removing a Share sends nothing. A Share needs a colleague who has signed in at least once, so the recipient always has an account; whether they have an Email address is a separate question (see "The Email address" below). Share mails cannot happen while Folder management is Off, since Cases are hidden.

### Case handed to you

Sent on Transfer (by the owner) and on Reassign (by an Admin), to the new owner. It names the Case, who handed it (the old owner's display name on Transfer, the Admin's on Reassign), and the days left on its clock, since the new owner inherits the clock (see the Retention policy and the Recycle bin chapter). The old owner gets nothing. One message per Case: the template names one Case and its days left. Handover mails cannot happen while Folder management is Off.

### Batch finished, and the Upload page tick

Sent when the last Recording in a Batch has ended (Done or Failed; a Batch the person cancelled whole sends nothing), only when they ticked "Email me when this batch finishes" on the Upload page's settings step.

The tick:

- is remembered from the person's last Batch and unticked the first time;
- is greyed with "No email address on your account; ask IT" when they have none;
- is hidden while the Admin setting "Batch finished emails" is Off or mail is not configured (`SMTP_HOST` empty).

The message gives the counts, lists each failed Recording's title with its reason in plain words, and says where the Recordings are: "in your recordings until your session ends", or "in the case <name>" when they were added to a Case at upload. Sent once, never resent. Batch mails continue while Folder management is Off.

### Operator mail

Operator mail goes to the Operator address (`OPERATOR_EMAIL`) and obeys only `.env`: the "Email notifications" setting does not touch it, and an empty `OPERATOR_EMAIL` means no Operator mail. It has fixed wording in the app, not settings. Three sources:

- **Cases whose owner has left.** A nightly message, sent with the digests, listing each Case whose owner is Deactivated or Blocked and that is inside the warning window: its name, its owner, its days left. Never to the person's old address and never to Admins' own mailboxes. The Cases page's "Owner deactivated" and "Expiring" filters are the place an Admin then goes to Reassign or Keep. A night with no such Case sends nothing.
- **Backup.** The four messages the Backup and restore chapter defines (a Snapshot failed, no successful Snapshot in 26 hours, a Restore drill failed or overdue, a restore completed with its counts) go through the same mailer as every other message, handed to it by the `worker`'s hourly check and by the record commands the backup, the drill, and the restore run. Plain text, no content, no names.
- **The test message.** Sent by `./transcribe check` to the Operator address, and by the Email page's Test message button to the signed-in Admin (or to the Operator address when that Admin has no Email address).

### The Email address

| Question | Rule |
|---|---|
| Source | The directory's `mail` value, and nothing else, for every directory account. |
| When it is read | At every sign-in, and by the Directory check: nightly at 03:00 and on "Check directory now". A change writes an "Email address updated" audit row. So a `mail` value filled in after the account was made reaches the app by the next night, or at once when an Admin presses the button; a value removed in the directory is removed in the app. |
| Nobody types one | The Users page never offers an address field for a directory account. The one typed address is a Local admin's, optional, entered on Create Local admin and editable on that row, because a Local admin has no directory record. `transcribe-admin` has none by default. |
| Missing | No mail, no audit row, nothing else changes. The Users page shows "No email address" on the row and gets a filter for it; the Status page counts "People without an email address: N"; `./transcribe check` reports how many members of the Sign-in group have no `mail` in the directory, as a warning. |
| Deactivated and Blocked | Never mailed. Their Cases go to the Operator address. |
| Labels | The Users page calls the userPrincipalName the "Directory address" (the sign-in identity, which is not a mailbox) and adds an "Email" column beside it. |
| Fixing an omission | Before the Phase 2 install the office fills `mail` for every member of the Sign-in group. A later omission is caught by the "No email address" filter and the `check` count, and fixed in the directory, never in the app; the next sign-in or Directory check brings the value in. |

### What a message may say

- **May**: the names of Cases and the titles of Recordings; counts; dates and times in office time; the display name of the owner, of the owner who shared, or of the person who handed a Case over; the recipient's own display name in the greeting; one link into the app, which carries nothing but the page (signing in is still required).
- **Never**: a line of a Transcript, Summary, or Chat; a Speaker's or Person's name; a Clip's title or note; a Case's Description; a Vocabulary word; anything about another person's material. The Audit log chapter's never-logged list is the never-mailed list.
- **Form**: plain text only; no HTML, no images, no tracking, and no attachments ever. Nothing leaves the app by mail as a file; exports and Clips are downloaded from the app.
- **Footer**: every message ends with a fixed line the app adds, and is marked as automatic so out-of-office replies do not answer it:

```
Sent automatically by Gideon Transcribe (https://<APP_HOSTNAME>:<HTTPS_PORT>/). Replies go to <OPERATOR_EMAIL>.
```

The app's address in links and in the footer is built from `APP_HOSTNAME` and `HTTPS_PORT`, as everywhere else.

### Wording: the templates

The Email page holds the four Notifications as ordinary text settings, a Subject and a Body each, with a fixed set of placeholders per kind and Reset to default, saved through the tray like the Notices, so the "Setting changed" audit row keeps the old and new text. No version numbers: prompt templates carry a version only because every LLM audit row cites it, and nothing cites an email. Apply refuses a template that uses a placeholder its kind does not have. The Operator messages and the test message have fixed wording in the app and are not settings.

The blocks (`{cases}`, `{shared}`, `{failed_list}`) and the fixed footer are the app's own lines and are not editable, which is what keeps every message inside the rule above. When a block is empty, nothing is inserted for it.

The defaults below are stored exactly as shown; a change takes effect from the next message.

#### Retention digest

Placeholders: `{name}` (the recipient's display name), `{cases}` (the "Deleting soon" block, one line per Case the person owns that is inside the warning window, built by the app), `{shared}` (the "Shared with you" block, its heading and one line per Case shared with the person that is inside the window, or nothing, built by the app), `{link}` (the one link into the app: the Cases page).

Subject:

```
Gideon Transcribe: cases deleting soon
```

Body:

```
Hello {name},

These cases delete unless someone uses them:
{cases}

{shared}

Open a case, or press Keep on the Cases page, to start its clock over: {link}
```

#### Case shared with you

Placeholders: `{name}` (the recipient's display name), `{owner}` (the owner's display name), `{case}` (the Case's name), `{link}` (the one link into the app: the Case).

Subject:

```
Gideon Transcribe: {owner} shared the case "{case}" with you
```

Body:

```
Hello {name},

{owner} shared the case "{case}" with you. You can do everything in it except share, rename, transfer, or delete it; recordings you add count against {owner}'s space.

Open it: {link}
```

#### Case handed to you

Placeholders: `{name}` (the recipient's display name), `{by}` (the display name of who handed it: the old owner on Transfer, the Admin on Reassign), `{case}` (the Case's name), `{days}` (the days left on the Case's clock, the number the Cases page shows), `{link}` (the one link into the app: the Case).

Subject:

```
Gideon Transcribe: the case "{case}" is now yours
```

Body:

```
Hello {name},

{by} handed you the case "{case}". It deletes in {days} days unless used, so open it to start its clock over.

Open it: {link}
```

#### Batch finished

Placeholders: `{name}` (the recipient's display name), `{count}` (how many Recordings the Batch held), `{done}` (how many transcribed), `{failed}` (how many failed), `{failed_list}` (one line per failed Recording, its title and its reason in plain words, or nothing, built by the app), `{where}` (where the Recordings are, one of the two fixed phrases below), `{time}` (when the Batch finished, office time), `{link}` (the one link into the app: where the Recordings are).

Subject:

```
Gideon Transcribe: your batch has finished ({done} done, {failed} failed)
```

Body:

```
Hello {name},

Your batch of {count} recordings finished at {time}: {done} transcribed, {failed} failed.

{failed_list}

The recordings are {where}.

Open them: {link}
```

The two values of `{where}`:

```
in your recordings until your session ends
in the case <name>
```

### Sender and reply-to

- The sender is `MAIL_FROM`, shown as "Gideon Transcribe <address>". It is required when `SMTP_HOST` is set.
- The `Reply-To` on every message is the Operator address (`OPERATOR_EMAIL`), so a puzzled reply lands with IT instead of bouncing.
- Every message is marked automatic.

### Sending, and when mail fails

- Every message is one background task on the `worker`: Django's SMTP sending, a 20-second network timeout, `Reply-To` the Operator address, marked automatic. Operator mail uses the same task.
- Three tries within thirty minutes: at once, after 5 minutes, after 25 minutes. Then one "Email failed" audit row with the reason class and the number of tries, the Status page's Email line turns red, and the message is dropped. The digest simply comes again the next night; the other kinds are not resent, since the app's pages are the record. Not a whole day of retries, because those pile up messages that arrive stale.
- Reason classes:

| Reason class | Meaning |
|---|---|
| `smtp_unreachable` | no connection, or a timeout |
| `smtp_refused` | the relay refused the sender, a recipient, or the message |
| `smtp_auth_failed` | the password was refused, or the relay offered no TLS while a password is set |

- Nothing waits for mail. When "Email notifications" is Off, or the person has no Email address, no task is created and no row is written.
- The `worker` container reaches the relay over the LAN on `SMTP_PORT`; the Architecture and deployment chapter's egress list gains it. No new service.
- The drill project never sends mail: its override leaves `SMTP_HOST` empty. After a restore, the first sweep's digest goes out as on any night.

### The Status page

The Status page gains an Email line:

- "Email: not configured" while `SMTP_HOST` is empty; or
- "Email: last sent <time> (<kind>); last failure <time> (<reason>)", red while the most recent try failed.

Beside it: "People without an email address: N".

### The Email page

An **Email** page joins the Settings group of the Admin panel in Phase 2 (beside Features, Limits, Transcription defaults, AI assistant, Notices, Sign-in and directory, Audit log, and Cases). It holds:

| Setting | Type | Default | When changed |
|---|---|---|---|
| Email notifications | On or Off; greyed "SMTP not configured" while `SMTP_HOST` is empty | On | At once. Off stops every mail to people; Operator mail depends only on `.env`. |
| Batch finished emails | On or Off | On | At once. Off hides the tick on the Upload page. |
| The four templates | text, Subject and Body each, Reset to default | the wordings above | The next message. |

And a **Test message** button, outside the tray, that mails the signed-in Admin (or the Operator address when the Admin has no Email address) and shows the relay's reply on the page. Each press writes a "Test email sent" audit row.

The Installation page shows the seven mail keys read-only, with the password shown as set or missing.

### No opt-out

There is no per-person switch for the digest, the share mail, or the handover mail: they exist for safety and come one a night at most. The Batch tick is the one personal choice, and nobody needs a settings page of their own. Admins hold the "Email notifications" switch.

### Environment keys

All seven live in the app's `.env`, are asked by `./transcribe install` in Phase 2 after the backup target, and are shown read-only on the Installation page.

| Key | File | Meaning | Placeholder or example |
|---|---|---|---|
| `SMTP_HOST` | `.env` | The office relay. Empty means the app sends no mail at all. | `<relay host>`; default empty |
| `SMTP_PORT` | `.env` | The relay's port. | `25`; default 25 |
| `SMTP_STARTTLS` | `.env` | `auto`: upgrade to TLS when the relay offers it, and require it when a password is set; `always`; `never`. | `auto`; default `auto` |
| `SMTP_USER` | `.env` | The relay's sign-in name, only when the relay wants one. | empty; default empty |
| `SMTP_PASSWORD_FILE` | `.env` | The secrets file holding the relay's password, when the relay wants one; written by the install, never in the panel. | `secrets/smtp_password`; default empty |
| `MAIL_FROM` | `.env` | The sender, shown as "Gideon Transcribe <address>". Required when `SMTP_HOST` is set. | `<sender address>`; default empty |
| `OPERATOR_EMAIL` | `.env` | The Operator address; also the `Reply-To` on every message. Empty means no Operator mail. | `<Operator address>`; default empty |
| `secrets/smtp_password` | the secrets folder in the Install home | The relay's password, when the relay wants one; named by `SMTP_PASSWORD_FILE`. | optional |

Existing keys the messages use, unchanged: `APP_HOSTNAME` and `HTTPS_PORT` (the link and the footer), `TZ` (every time in a message is office time). The drill project's override leaves `SMTP_HOST` empty.

### Install and check

`./transcribe install` asks, in plain words, after the backup target:

1. the relay's host and port;
2. whether it needs a password (then the user, and the password typed hidden, written to `secrets/smtp_password`);
3. the sender address;
4. the Operator address.

Leaving the host blank is allowed, and the install says what that loses: the app sends no mail at all, so no Retention digest, no other Notification, and no Operator mail.

`./transcribe check` gains two lines:

1. it connects to the relay, sends one test message to the Operator address, and reports the relay's reply (which proves the two relay facts: that the relay takes mail from the server's address, and that it lets the sender through);
2. it counts the Sign-in group's members without `mail` in the directory, as a warning.

### What Admins see

- The Email page with the settings, the templates, and Test message; the Installation page's read-only mail keys with the password shown as set or missing.
- The Status page's Email line and the count of people without an Email address.
- The Users page's "Email" column, the "No email address" mark and filter, and the Email field for Local admins.
- The Operator address's nightly message about Cases whose owner has left, with the Cases page's "Owner deactivated" and "Expiring" filters as the place to Reassign or Keep.
- The audit log's Email category as a filter.

### Audit rows

| Row | Category | Actor | When it is written | Object and details |
|---|---|---|---|---|
| Email sent | Email | system (mailer) | when the relay accepts a message, one row per message | the kind; the recipient as a username, or `operator`; the object: the Case, the Batch, or "digest" with its counts (own, shared); never the subject or body |
| Email failed | Email | system (mailer) | when the third try has failed, one row per message | the same, plus the reason class and the number of tries |
| Test email sent | Email | the Admin (the button), or system (check) | when the Test message button or `./transcribe check` sends its message | the recipient address and the relay's reply |
| Email address updated | Accounts | system (Directory check), or the sign-in | when a sign-in or the Directory check finds the directory's `mail` value differs from the stored Email address, including its removal | the account, and the new address in the details block |

The Audit log chapter's fixed field set applies. A person without an Email address gets no row; the Status page counts them. A template edit is recorded by the existing "Setting changed" row, which keeps the old and new text.

### Settings

The behaviour in this chapter depends on these admin settings, by their catalogue names (their tables are in the admin settings catalogue):

- **Email notifications** (Email page): governs every mail to people; Operator mail ignores it.
- **Batch finished emails** (Email page): allows the Upload page's tick at all.
- **Retention digest**, **Case shared with you**, **Case handed to you**, **Batch finished** (Email page): the four templates, a Subject and a Body each, with Reset to default.
- **Warning-before-deletion** (the Retention policy's setting, default 7 days, range 1 to 30): the window; a Case inside it is in the digest, and its owner's or Collaborators' lines, or the Operator message's lines, stop when it leaves.
- **The Retention policy's days**: the clock whose days left every digest line and every handover mail reports.
- **Folder management**: Off pauses the sweep, so no digest is built, and hides Cases, so no share or handover mail can happen; Batch mails continue.

### Changes to Phase 1

1. **Sign-in and the Directory check.** Phase 1 stores the directory's `mail` value as the account's Email address from the first sign-in, refreshes it at each sign-in and by the Directory check, and nothing uses it. Phase 2 uses it for every Notification, and a change (including removal) now writes the "Email address updated" audit row.
2. **The users list.** Phase 1 shows each person's address, the userPrincipalName. Phase 2 labels that column "Directory address" and adds an "Email" column beside it; a row without one shows "No email address", and a filter selects those rows.
3. **Local admin.** Phase 2 adds an optional Email field on Create Local admin, editable on that row; `transcribe-admin` has none by default.
4. **The Upload page.** The settings step gains the tick "Email me when this batch finishes", with the rules under "Batch finished, and the Upload page tick" above.
5. **The end of a Batch.** When the last Recording in a Batch has ended, the Batch finished message may be sent.
6. **The Admin panel.** The Settings group gains the Email page; the Status page gains the Email line and the count of people without an Email address; the Installation page shows the seven mail keys read-only.
7. **The helper script.** `./transcribe install` asks the four mail questions after the backup target; `./transcribe check` gains the two lines above.
8. **The audit log.** A new Email category with three rows and its filter, and the Accounts row "Email address updated".
9. **Deployment topology.** Seven mail keys and the optional secrets file in `.env`; the `worker`'s egress list gains the relay on `SMTP_PORT`; the drill project's override leaves `SMTP_HOST` empty. No new service.
10. **The directory objects.** The Bind account must be able to read `mail`; the office fills `mail` for the Sign-in group before Phase 2.
11. **Backup.** The four operator messages the Backup and restore chapter defines now go through the mailer to `OPERATOR_EMAIL`, which that chapter left this chapter to name.

Phase 2 chapters this chapter amends: the Retention policy and the Recycle bin chapter (the warning email is the Retention digest, sent from the sweep's job, to owners and Collaborators alike; no deletion or wipe mail), the Sharing chapter (the share mail; Collaborators get the warning in their own digest, replacing "the owner alone gets the warning email"), the Cases chapter (the handover mail on Transfer and Reassign), and the Folder management toggle chapter (the digest resumes on the first sweep after On, with the days that were left, and nothing special is sent).

### Before you begin (Phase 2)

- Every member of the Sign-in group has a `mail` value in the office's directory, and the Bind account can read `mail`. `./transcribe check` counts who still lacks one.
- A relay that accepts mail from the server's address, without a password or with one over STARTTLS, and lets the sender address through. Both facts are proven by `./transcribe check` at the install; there is nothing to prove earlier.
- The sender address and the Operator address, chosen; `./transcribe install` asks for them.

### Not in this phase

Decided against, so a builder must not assume them:

- An Admin-typed address for a directory account on the Users page, and with it any allowed-domains key: the directory is the only source.
- A per-person opt-out or a personal email settings page.
- Versioned email templates.
- A mail when a Case is deleted into the Recycle bin, restored, or wiped: the last mail about a Case is the final warning on the night before its deletion.
- Alerting mail about a service being down: not in any phase yet.

### Left to the build

- **The fixed wording of the test message** (the Email page's button and `./transcribe check`): the ticket says "fixed wording" in the app, not a setting. Constraints: plain text; the content rule above; the fixed footer; the recipient is the signed-in Admin, or the Operator address; the "Test email sent" row records the recipient address and the relay's reply.
- **The fixed wording of the nightly Operator message about Cases whose owner has left**: fixed in the app, not a setting. Constraints: to the Operator address only; sent with the digests; one line per Case whose owner is Deactivated or Blocked and that is inside the warning window, giving its name, its owner, and its days left; plain text; the fixed footer; never the person's old address, never Admins' own mailboxes. (The backup's four messages have their fixed wording in the Backup and restore chapter.)
- **The line shape of `{failed_list}`** ("each failed Recording's title with its reason in plain words"), **the `{time}` format** (office time), and **how an empty block collapses its blank line**. Also how the digest reads when `{cases}` is empty and only `{shared}` has lines, since the editable line "These cases delete unless someone uses them:" precedes `{cases}`.
- **How a message is marked automatic** so that out-of-office replies do not answer it, and the exact `From` header for "Gideon Transcribe <address>".
- **Whether Apply also refuses a template that omits a placeholder its kind needs** (the ticket refuses only a placeholder the kind does not have).
- **Whether the Upload page's tick also hides while "Email notifications" is Off**: the ticket hides it while "Batch finished emails" is Off or mail is not configured, and separately says no task is created while "Email notifications" is Off.
- **Whether the Test message button sends within the request** (its reply is shown on the page) or through the background task with its three tries.
- **The exact wording of the two `./transcribe check` lines** (the relay's reply; the count of Sign-in group members without `mail`, as a warning) and of the install's plain-word questions and its blank-host warning.
- **The user guide's email section**: the ticket routes "the guides" to the install story without wording. The facts it would carry from this chapter: what the four Notifications are and when they come; that the digest is a safety message, one a night at most, and that Keep or opening the Case stops it; that the last mail about a Case is the final warning, and the Recycle bin page is where a deletion is learnt; the Batch tick and its "ask IT" state; that there is no opt-out; that a message names things and never quotes content.
- **The admin guide's email section**: the facts it would carry: the Email page, its two switches and four templates, and Test message; the Status page's Email line and the count; the Users page's "Email" column and "No email address" filter, and that an omission is fixed in the directory, never in the app; the Local admin Email field; the Operator address, what goes to it, and that replies land there; the seven keys and the secrets file; the `check` lines; what "Email failed" and a red Status line mean and that nothing waited for the mail.

### Sources

Email notifications over SMTP (the only ticket read), which carries as quoted facts the decisions of Case folder model on the mount, Audit log, Sharing model, Retention policy, Folder management toggle transitions, and Backup and restore.

### Amendments applied

- Within Email notifications over SMTP, the Answer over its round 1 drafts: the digest carries warnings only (no "Deleted last night" section, no wipe mail); no Admin-typed address on the Users page and no `MAIL_ALLOWED_DOMAINS` key; the reason class `smtp_auth_failed` replaces `no_address` (a missing address creates no task and no row); seven keys, not eight.
- From Email notifications over SMTP to LDAP sign-in, roles, and the local admin: `mail` is the Email address, refreshed at sign-in and by the Directory check; the Users page labels ("Directory address", "Email"); the Local admin Email field.
- From Email notifications over SMTP to Audit log: the Email category's three rows and the Accounts row "Email address updated".
- From Email notifications over SMTP to App-side transcription queue and job model: the Batch finished mail at the end of a Batch.
- From Email notifications over SMTP to Deployment topology on the rebuilt server: seven mail keys, the optional secrets file, the relay egress, the drill override.
- From Email notifications over SMTP to Admin settings catalogue and panel: the Email page, its settings and templates, Test message, the Status line, the Users page column and filter, the Installation page keys.
- From Email notifications over SMTP to Case folder model on the mount: the handover mail on Transfer and Reassign.
- From Email notifications over SMTP to Sharing model: the share mail; Collaborators in their own digest, replacing "the owner alone gets the warning email".
- From Email notifications over SMTP to Retention policy: the digest is the warning email, sent from the sweep's job; no deletion mail.
- From Email notifications over SMTP to Folder management toggle transitions: the cadence after On (the digest resumes on the first sweep, nothing special sent).
- From Email notifications over SMTP to Backup and restore: `OPERATOR_EMAIL` named; the four operator mails go through the mailer.
- From Email notifications over SMTP to GitHub distribution and install story: the install questions, the `check` lines, the guides, the before-you-begin list.
- From Email notifications over SMTP to Create the directory objects: `mail` readable by the Bind account; fill it for the Sign-in group before Phase 2.
- From Email notifications over SMTP to Upload page and Batch settings prototype: the Phase 2 tick on the settings step.


## 9. Backup and restore

Phase 2 gives the app its own nightly Backup. Every night at 02:00 a host timer runs `./transcribe backup`, which takes one consistent dump of the database, copies it with `cases/`, the configuration, the secrets, and a manifest into an encrypted, deduplicated restic repository over SFTP, in a folder of the app's own on the office's backup store, and prunes whatever is older than the keep rule. If the box dies, IT installs the app fresh, runs one restore command, and the app is back to the night of the last Snapshot. Once a month the app proves, by itself, that the newest Snapshot restores, into a throwaway copy beside the live one that is torn down afterwards.

### Principles

1. **The app carries its own copy to the backup store.** Gideon Transcribe is a separate stack, so its data is outside any other backup set on the server, and the store vendor's backup agent cannot run on this host's kernel. Nightly, one push to the store as a dedicated account, 30 nights off the box, 7 dumps on the box, and an automated drill; the mechanism is the app's own.
2. **Encrypted before it leaves the box.** Every Snapshot is ciphertext on the store. The repository password never rides in the Backup; it lives in the office's password manager.
3. **A backup is for the box dying.** The whole app comes back to one night. Nothing is ever picked out of a Backup for a person: Delete stays final and the Recycle bin is the only undo.
4. **The Retention policy reaches the Backups only through the keep rule.** A Case that is gone from the app stays in Snapshots for the keep period and no longer.
5. **A restore never resurrects a Workspace and never punishes anyone for the outage.** Login sessions end and the Discard runs; the days the app was dead are an Off spell.
6. **The drill runs itself.**
7. **Everything office-specific is `.env`.** The Backup set, the commands, and the calendar are the same at every office; only the target, the keys, and the times differ.

### Words

- **Backup set**: everything the app must copy to come back: the database dump, `cases/`, the configuration and secrets, and the manifest.
- **Snapshot**: one night's copy of the Backup set, as kept in the repository on the Backup target.
- **Backup target**: the encrypted store off the box where Snapshots live, named by `BACKUP_TARGET`: a folder of the app's own on the office's backup store, reached over SFTP as a dedicated ordinary account.
- **Restore**: putting one Snapshot back so the app is as it was that night.
- **Restore drill**: the monthly, automatic proof that the newest Snapshot restores, run into a throwaway copy of the app beside the live one.
- **Off spell**: a span of days the Retention policy leaves out of its counts, the Folder management toggle chapter's build term. It gains a cause: `toggle` or `restore`.

### What changes from Phase 1

Phase 1 ships `./transcribe backup-db` and nothing else from this chapter: the pre-upgrade dump, which IT can also run by hand and copy anywhere it likes. Nothing in the Phase 1 database needs more than that dump. Phase 2 changes these Phase 1 rules:

1. **The pre-upgrade dump keeps its name and format and gains a keep rule.** `backup/pre-<tag>.dump` is in Postgres custom format (never `.sql`), the same format as the nightly dump, so there is one dump format and one restore path. From Phase 2 the nightly job prunes it: a pre-upgrade dump and its `config-pre-<tag>.tar` stay until the next successful upgrade plus 7 days.
2. **`backup/` gains files.** The last 7 nightly dumps, `manifest.json`, and `last-run.json` join the pre-upgrade dump and `config-pre-<tag>.tar`.
3. **The Compose project gains a service and an override file.** The `backup` service (restic) makes ten services with `vllm`; `compose.drill.yaml` is the drill override.
4. **`./transcribe` gains four subcommands**: `backup`, `snapshots`, `restore <snapshot>`, and `restore-drill`. `backup-db` is unchanged.
5. **`./transcribe install` gains the backup steps**: two more questions, the three backup secrets files, the repository, the timer units, and a first `backup` and `restore-drill`.
6. **`./transcribe check` gains the target checks.**
7. **The host gains three timer units and their service units**, and the server preparation creates `<drill folder>`, a folder of its own beside the App data folder, owned by the app's system user.
8. **Pages, rows, and classes.** The Status page gains the Backup line; the Installation page gains read-only rows; the audit log gains four System rows; the Queue's Failed reason classes gain `restored`; the Off spell row gains a cause.
9. **Egress** gains the backup store on port 22 on the LAN, and nothing outside.

### The Backup set

| What | In or out | Why |
|---|---|---|
| The database dump: every table (settings, users and the Local admin, prompt templates and Summary templates, Office Vocabulary, Cases, Recordings' rows, Transcripts, Corrections, Speakers, People, Shares, Case Chats, Off spells, binned Cases, Batches and Jobs, the audit log with its hash chain, Procrastinate's own tables) | In | The record. One `pg_dump` in Postgres custom format through the running `postgres` container, consistent without stopping the stack. |
| `cases/` | In | The only retained Recordings' files: the uploaded bytes, the probe output, the ASR audio per Side, the Playback copy, the waveform, and `clips/`. |
| `<Install home>/.env`, `secrets/`, `tls/`, `ca/`, `whisperx-service/.env`, `whisperx-service/secrets/` | In | The configuration and secrets a restore onto a new box needs: the Bind account's password, the Consumer tokens file, the HuggingFace token, and the rest. The two backup secrets are the exception (see The keys, the password, and the host key). |
| `backup/manifest.json` | In | Release tag, migration number, WhisperX service version, timestamps, a row count per table, a sha256 per file under `cases/`, the dump's size. |
| `uploads/`, `scratch/` | Out | Nothing in them outlives a Login session. |
| `postgres/` as raw files | Out | The dump stands for them. |
| `models/whisperx/`, `models/vllm/` | Out | The `pull` commands recreate them. |
| `whisperx/` (the WhisperX service's own state, its job database included) | Out | Troubleshooting metadata the service keeps for 30 days. |
| `test-corpus/` | Out | The master copy is kept off the server. |
| Docker images, the code checkout | Out | Pulled by tag and digest at install; the manifest names the release tag. |
| `backup/` beyond the newest nightly dump and the manifest (older nightly dumps, pre-upgrade dumps, `config-pre-<tag>.tar`, `last-run.json`) | Out | The repository holds the earlier nights already. |

**Workspace text.** The dump holds whatever is in an open or Busy Workspace at 02:00: the Transcripts, Summaries, Chats, and Clip rows of a late Login session or a running Batch. This is accepted, and only as text: a Workspace's files under `uploads/` and `scratch/` are never copied, so a Snapshot never holds a Workspace as such. Most Workspaces are gone by 02:00, since the idle timeout is 8 hours. The text never reappears: the after-restore step discards every Workspace within a minute of the stack starting, and only IT can decrypt a Snapshot. Admins can already open any Workspace, audited; a copy only IT can decrypt, gone from the app the moment it is restored, is no wider a door.

**Case Chats** are Postgres rows keyed to the Case and ride in the dump with the Case's other text; nothing is indexed or embedded, so the Backup set gains nothing for them.

**Clips.** A Clip inside a Case rides in the Snapshot with its Recording, under `cases/`; a Workspace Clip is never backed up.

### The nightly job

`./transcribe backup`, in order, stopping and reporting at the first failure:

1. **Preflight**, by the app (`docker compose run --rm app backup-preflight`): free space on the App data folder above the "Minimum free disk space" floor; `BACKUP_TARGET` set; the two backup secrets present.
2. **The dump**: `pg_dump --format=custom` through `docker compose exec postgres`, into `backup/nightly-<YYYY-MM-DD>.dump`, mode 0600, owned by the app's system user. It is the same dump `backup-db` writes before an upgrade as `backup/pre-<tag>.dump`.
3. **The manifest**, `backup/manifest.json`, written by the app command `write-manifest`, so the counts and hashes the drill checks come from the same code that checks them.
4. **The Snapshot**: restic (BSD licence), from its official image pinned by digest, run as the Compose service `backup` with `<App data folder>/backup/` (the newest dump and the manifest), `<App data folder>/cases/`, and the configuration files mounted into it, into the repository named by `BACKUP_TARGET` over SFTP. Deduplicated, so an unchanged Recording costs nothing after its first night; encrypted by restic with the repository password, so the store holds only ciphertext.
5. **The keep rule**: `restic forget --keep-daily $BACKUP_KEEP_DAYS` every night. `restic prune` and `restic check --read-data-subset=10%` run on the weekly slot instead, so the nightly job stays short.
6. **Local dumps**: the last `BACKUP_LOCAL_DUMPS` (7) nightly dumps stay in `backup/`, older ones are removed; a pre-upgrade dump and its `config-pre-<tag>.tar` stay until the next successful upgrade plus 7 days.
7. **Report to the app**: the app command `record-backup <result>` writes the audit row ("Backup ran", or "Backup failed" with a reason class) and the Status page's Backup line, and sends the Operator mail when the run failed.

`BACKUP_TARGET` empty means backups are off: the Status page's Backup line says so in red and nothing runs.

The `backup/` folder:

```
<App data folder>/backup/
  nightly-<YYYY-MM-DD>.dump   the last BACKUP_LOCAL_DUMPS nightly dumps, Postgres custom format, 0600
  pre-<tag>.dump              the pre-upgrade dump written by ./transcribe backup-db, which ./transcribe upgrade runs first; same format
  config-pre-<tag>.tar        a copy of .env, both secrets folders, and tls/, taken by ./transcribe upgrade beside the pre-upgrade dump, 0600
  manifest.json               the newest Snapshot's manifest
  last-run.json               the last run's record
```

#### Calendar

Host timers, written by `./transcribe install` from `.env`:

| Timer | When | Runs |
|---|---|---|
| `transcribe-backup.timer` | nightly at `BACKUP_TIME`, 02:00: the hour before it is left to the server's other nightly work, and it comes before the app's own 03:00 Directory check and 03:30 sweep, so the Snapshot holds the day's Cases before anything is binned | `./transcribe backup` |
| `transcribe-backup-weekly.timer` | Sundays at `DRILL_TIME`, 04:00 | `restic prune` and `restic check --read-data-subset=10%` |
| `transcribe-backup-drill.timer` | the first Sunday of the month at `DRILL_TIME`, 04:00, after the weekly step; disk and CPU only, never the GPU | `./transcribe restore-drill` |

Timers live on the host because they fire when the stack is down or half-upgraded. The service units run `./transcribe <command>` as root (docker needs it); everything they start runs in containers as their own users. Nothing is installed on the host beyond the unit files; the tool is a container.

#### Reason classes

| Row | Reason class | Meaning |
|---|---|---|
| Backup failed | `disk_full` | preflight: free space on the App data folder under the floor |
| Backup failed | `dump_failed` | the dump did not complete |
| Backup failed | `manifest_failed` | the manifest was not written |
| Backup failed | `target_unreachable` | the Backup target could not be reached |
| Backup failed | `snapshot_failed` | restic did not complete the Snapshot; a full folder on the store ends here |
| Backup failed | `prune_failed` | the keep rule, or the weekly prune, failed |
| Backup failed | `check_failed` | the weekly check failed |
| Restore drill ran | `drill_failed` | the drill failed; the failing step is in the details block |
| Job Failed | `restored` | a Case-bound Job that was Queued or Running at the Snapshot, failed by the after-restore step |

The "Backup failed" row also names the step.

### The Backup target

#### The account on the store

The store needs one account for this app alone, with rights on one shared folder and nothing else:

- **An ordinary account, never an administrator.** restic speaks SFTP, and a Synology-class store gives SFTP to ordinary accounts: each sees only the shared folders it has rights to, as folders at the root of its own view, and never gets a shell. An administrator account would see the folder under a volume path, and a path of that form in `BACKUP_TARGET` betrays the mistake. Group: the store's ordinary users group only.
- **SFTP allowed, every other application denied** (the store's web interface, its file manager, and the rest), so the password opens nothing even if it ever leaked. No admin rights; no other shares; no per-user quota; no speed limit.
- **Key-only sign-in.** The key is the only credential in play. A Synology-class store accepts passwords at the service level and has no switch for that, so the account gets a long random password (32 characters or more) that nobody ever uses, locked against change and never expiring, saved in the office's password manager as the account's record. A suggested description for the account: "Gideon Transcribe nightly backup, restic over SFTP, key only".
- **An explicit No access on every other shared folder.** A shared folder readable by the account's group is otherwise visible at the account's root; an explicit No access on the account beats a group permission.
- **The account's home service on**, since the key lives in the account's home.
- **On the store itself**: the SFTP service on, on port 22 (the app assumes 22, and `BACKUP_TARGET` carries no port); FTP and FTPS off.

#### The folder on the store

A shared folder of the app's own, on a volume with room for `BACKUP_KEEP_DAYS` nightly Snapshots (the first is the size of `cases/`, later ones only what changed):

- **The folder's recycle bin off.** restic deletes pruned data files, and a recycle bin would hoard them for good. A `#recycle` entry in the folder means it is still on.
- **Encryption off.** restic encrypts everything before it leaves the box, and an encrypted share that is not mounted after a store reboot fails the push silently.
- **Data integrity on, compression off.** On a file system that offers a data-integrity option at creation, tick it; leave compression off, since restic's data is already compressed and encrypted.
- **A folder quota**, so a runaway fails the Backup and mails the Operator address instead of filling the volume.
- **Permissions**: the account Read/Write, everyone else No access.

#### Placing the public key

sshd on the store accepts `authorized_keys` only when the account itself owns the file and its folders and the modes are exact. A file uploaded through the store's file manager belongs to the administrator who uploaded it, which is the classic reason a key "does not work" on a Synology-class store. So the key is placed from the store's shell as root, into the account's home:

```bash
sudo -i
H=/var/services/homes/<backup account>
mkdir -p "$H/.ssh"
echo '<public key line>' > "$H/.ssh/authorized_keys"
chown <backup account>:users "$H"; chown -R <backup account>:users "$H/.ssh"
chmod 755 "$H"; chmod 700 "$H/.ssh"; chmod 600 "$H/.ssh/authorized_keys"
ls -la "$H" "$H/.ssh"; cat "$H/.ssh/authorized_keys"
```

The listing must show the account, not root, as the owner of `.ssh` and `authorized_keys`; a `chown -R` that did not take leaves them root's, and the key is refused, because sshd reads the file as the account. The modes: the home 755 (anything from 711 up), `.ssh` 700, `authorized_keys` 600.

#### The path and `BACKUP_TARGET`

The folder presents at the root of the account's view, as `/<backup folder>`; the account's root lists only that folder and `home` (its own home, where the key lives). So:

```
BACKUP_TARGET=sftp:<backup account>@<backup store hostname>:/<backup folder>
```

No port; 22 is assumed. An office without such a store can point `BACKUP_TARGET` at any SFTP host. Empty means backups are off.

#### The keys, the password, and the host key

Three secrets files in `<Install home>/secrets/`, each named by a `.env` key:

- **`secrets/backup_ssh_key`** (0400): the account's private key. The key is made once and is the account's key for good: the public half goes into the store's account, and the private half goes into the office's password manager, in the account's record, together with the public half and a note carrying the target line, the folder, the store's host key, and the key's fingerprint. A fresh box gets the key from there, placed before the install runs.
- **`secrets/backup_password`** (0400): the restic repository password. Generated by the install and copied into the same password-manager record before the first Snapshot. Without it every Snapshot is unreadable, and there is no recovery.
- **`secrets/backup_known_hosts`**: the store's host key, recorded by the install. The install guide tells the installer to compare it with the fingerprint the store's administrator knows. The connection is refused if the store ever presents a different key.

The circular part: `secrets/` rides in the Snapshot except `backup_password` and `backup_ssh_key`, which a fresh box gets from the password manager.

#### Sizing and a full folder

The repository is about the size of `cases/` plus a month of changes, since restic sends only what changed each night. The theoretical ceiling of the Cases is the per-user quota times the number of users (30 users at the 50 GB default is 1.5 TB), before deduplication and compression, and only Cases are copied; real use is expected far below it, and the office's folder quota may sit below that ceiling. A full folder fails that night's Snapshot with `snapshot_failed` and the Operator mail; nothing on the box is affected, and raising the quota on the store is the fix. The Status page's Snapshot size shows the trend.

#### Store-side snapshots

Whether the store keeps its own snapshots of the folder as a second line (a Synology-class device offers a scheduled snapshot of a shared folder; for example daily at 03:00, after the 02:00 push, keeping 14) is a store choice the admin guide mentions and nothing in the app depends on. It guards against the box itself: whoever holds the repository key can delete Snapshots, and a store-side snapshot survives that.

### Keeping

- `BACKUP_KEEP_DAYS` = 30 nightly Snapshots on the target, `BACKUP_LOCAL_DUMPS` = 7 dumps on the box, no weekly or monthly tier: nothing older than 30 days is recoverable anywhere. Another office may set a longer keep in `.env`.
- **What that means for the Retention policy**, recorded once here: a Case the clock deletes waits the Recycle bin's days (30) in the bin, is wiped by the 03:30 sweep, and stays in Snapshots for `BACKUP_KEEP_DAYS` after the wipe; with the defaults a Case is gone from everywhere at most 90 days after its Last activity. A Case or Recording a person deletes is gone from the app at once and lingers in Snapshots for 30 days, unreachable from the app.
- **Nothing is picked out of a Snapshot for a person**: no `restore-case` command and no per-Case packaging in the Snapshot.

### Restore

`./transcribe restore <snapshot>` takes `latest` or a snapshot id from `./transcribe snapshots`, on the same box or a fresh install. The admin guide carries this as the runbook, written for a non-programmer, and its first line is:

```
A restore takes the app back to 02:00 of the Snapshot's day, and everything done after that is gone.
```

1. **A fresh box**: follow the install guide to the point where `./transcribe install` has run (the prerequisites, the checkout at the release tag, `.env`, `tls/`, `ca/`, from the password manager or the old box), with the SSH private key from the password manager placed at `secrets/backup_ssh_key` before the install runs, so the install uses it and prints nothing to paste; then put the repository password from the password manager into `secrets/backup_password`. **The same box**: nothing to do first.
2. `./transcribe restore latest` reads the manifest from the Snapshot before anything else and refuses unless the checkout is at the release tag the manifest names (it says which tag to check out); refuses while a Job is running; stops the stack, the WhisperX service included.
3. Puts back the configuration files (over the fresh ones, keeping the two backup secrets), then `cases/` in full from the Snapshot.
4. Recreates the database empty, loads the dump with `pg_restore`, runs migrations (a no-op at the right tag), starts the stack.
5. **The after-restore step** (`docker compose run --rm app after-restore`):
   - ends every Login session and runs the Discard for every Workspace: Recordings, Transcripts, Summaries, Chats, Clips, Provenance, and Batches; their files were never copied, so nothing is on disk;
   - marks every Case-bound Job that was Queued or Running at the Snapshot as Failed with the reason class `restored`, keeping its files and a Retry button (the Queue's Failed rule); the stalled-job recovery would have found them, this makes it immediate and named;
   - records the outage as an Off spell with cause `restore`, from the Snapshot's timestamp to now, so those days count for no Case and no binned Case, unless Folder management was Off at the Snapshot, when the still-open toggle spell already covers the gap; Last activity and deleted-on dates are never moved;
   - runs the Integrity check and writes its result;
   - writes "Restore completed" (the Snapshot's id and time, the outage span, counts, the Integrity result), sends the Operator mail, and prints the report: Cases, Recordings, GB, rows per table against the manifest, the Integrity result, and what the next 03:30 sweep will do (Cases due tonight, binned Cases the sweep will wipe tonight).
6. `docker compose run --rm whisperx pull` (and the Local engine's pull when its profile is on), then the smoke test from the Architecture and deployment chapter.

A Recording half-added to a Case at the Snapshot comes back as Failed with `restored` and Retry when its rows are there and its files are not; files with no rows are removed by the next daily sweeper. The WhisperX service's own job database is not restored, so its old job ids mean nothing to the restored app, which is why in-flight Jobs are failed rather than resumed.

### The Restore drill

`./transcribe restore-drill`, monthly on the first Sunday at `DRILL_TIME` and once at install:

1. Refuses when free space on the data drive is under the Snapshot's size plus the "Minimum free disk space" floor, with `drill_failed` and the reason.
2. Pulls the newest Snapshot into `<drill folder>`, a folder of its own beside the App data folder, owned by the app's system user; the server preparation creates it.
3. Brings up a sibling Compose project `transcribe-drill` from the same compose file with the drill override `compose.drill.yaml`: Postgres and the app container only, ports on loopback, no Caddy, no GPU, no WhisperX service, no workers, `LDAP_ENABLED=0`, `SMTP_HOST` empty, the restored configuration in a temporary folder and never the Install home. It never starts a Login session and never sends mail.
4. Loads the dump, runs migrations, then checks: a row count per table against the manifest; a hash walk of every file under the drill's `cases/` against the manifest; every Recording row in a Case has its files; the Integrity check reports unbroken.
5. Reports to the live app: the app command `record-drill` writes "Restore drill ran" (pass with duration, or `drill_failed` with the step) into the live app's audit log and the Status page's drill line, and sends the Operator mail when the drill failed.
6. Tears down whatever the result: `docker compose -p transcribe-drill down -v`, and `<drill folder>` emptied.

At install the sequence is `backup` then `restore-drill`, on the just-installed state, so an installer sees both succeed before the app has anything to lose. The full "new box" runbook lives in the admin guide and nobody is made to rehearse it.

### Commands

| Command | Runs | Does |
|---|---|---|
| `./transcribe backup` | on the host, from the nightly timer or by hand | the nightly job |
| `./transcribe snapshots` | on the host | lists the Snapshots in the repository with their ids, for `restore` |
| `./transcribe restore <snapshot>` | on the host | the restore; `<snapshot>` is `latest` or a snapshot id |
| `./transcribe restore-drill` | on the host, from the drill timer, once at install, or by hand | the Restore drill |
| `./transcribe backup-db` | on the host | the pre-upgrade dump `backup/pre-<tag>.dump`, unchanged from Phase 1 |
| `./transcribe upgrade` | on the host | as before: `pre-<tag>.dump` and `config-pre-<tag>.tar` first |
| `./transcribe install` | on the host | gains the backup steps (see Install) |
| `./transcribe check` | on the host | gains the target checks (see `./transcribe check`) |
| `backup-preflight` | the `app` container (`docker compose run --rm app backup-preflight`) | step 1 of the nightly job |
| `write-manifest` | the `app` container | step 3 of the nightly job |
| `record-backup <result>` | the `app` container | step 7 of the nightly job |
| `after-restore` | the `app` container (`docker compose run --rm app after-restore`) | step 5 of the restore |
| `record-drill` | the live app's `app` container | step 5 of the drill |
| `docker compose run --rm whisperx pull` | the WhisperX service container | rebuilds the model cache after a restore |
| `docker compose -p transcribe-drill down -v` | on the host | tears the drill project down |

### Install

`./transcribe install` gains these steps:

1. **Two questions**, after the questions the Repository, releases, and distribution chapter fixes: the backup target (`BACKUP_TARGET`; empty means backups are off), then the Operator address (`OPERATOR_EMAIL`; empty means no Operator mail).
2. **The key.** The install uses the backup key it finds at `secrets/backup_ssh_key` (placed there from the password manager before the install runs) and generates a key pair only when there is none; it prints the public half, to paste into the store's account, only in that second case. A restore onto a fresh box needs this behaviour.
3. **The password.** The install generates the repository password into `secrets/backup_password`. Both files are mode 0400.
4. **The host key.** The install records the store's host key into `secrets/backup_known_hosts`; the guide tells the installer to compare it.
5. **The repository.** The install initialises the repository at `BACKUP_TARGET` and checks the target is reachable and writable.
6. **The timers.** The install writes the three timer units and their service units from `.env`.
7. **The first proof.** At install the sequence ends with `backup` then `restore-drill`, on the just-installed state, so an installer sees both succeed before the app has anything to lose. Whether the install command runs them itself or the guide's next step does is left to the build.

The guide's step between 4 and 7: paste the public key into the store's account when the install printed one, then copy the repository password and the private key into the office's password manager before the first Snapshot.

### `./transcribe check`

`./transcribe check` gains these items for the Backup target, modelled on a seven-check test of the account. Three of them are the failures seen at the first run of that test.

1. **The key and the host key**: `secrets/backup_ssh_key` and `secrets/backup_known_hosts` are present and unchanged.
2. **What the store offers**: the sign-in methods the store's SSH service announces (a Synology-class store announces publickey and password).
3. **Key-only sign-in** works, with the key alone and no password.
4. **The root listing warning**: what the account sees at its SFTP root. Only the app's own folder and `home` should be visible; anything else is reported, because a shared folder readable by the account's group is visible there until it gets an explicit No access.
5. **The folder's path** as the store presents it matches the path in `BACKUP_TARGET`; a path under a volume name means the account is an administrator.
6. **Write and remove**: a file written, listed, and removed, and the folder empty afterwards. A `#recycle` entry is a failure: the folder's recycle bin is still on and would hoard every pruned data file.
7. **No shell**: a shell request is refused after the key is accepted ("Permission denied" from a Synology-class store), while SFTP goes through.
8. **The host key comparison**: the key the store presents matches `secrets/backup_known_hosts`.

The check also sends one test message to the Operator address and reports the relay's reply (see the Email notifications chapter). The three first-run failures a builder should expect from a new store account: the key file owned by root after placement (sshd reads it as the account, so the account must own it; an upload through the store's file manager has the same problem); a shared folder readable by the ordinary users group visible at the account's root until it got an explicit No access; the recycle bin on, leaving a `#recycle` folder.

### What IT sees

#### Status page

A Backup line: the last Snapshot (time, result, size, Snapshots held, next run) and the last drill (time, result). Red when the last successful Snapshot is older than 26 hours, when the last Snapshot or the last drill failed, or when `BACKUP_TARGET` is empty (the line says backups are off); amber when a drill is more than 3 days overdue. The Snapshot size shows the repository's trend.

#### Installation page

Read-only rows: the target (account and host, never the key), the schedule, the keep rule, the local dump count, and whether the two backup secrets are set. No panel setting anywhere: a host timer cannot be changed from inside a container.

#### Operator mail

Four Operator mails, to `OPERATOR_EMAIL`, plain text, no content:

1. a Snapshot failed;
2. no successful Snapshot in 26 hours, once a day until one succeeds;
3. a drill failed, or is 3 days overdue;
4. a restore completed.

The `worker`'s hourly check does the two overdue tests; the three record commands (`record-backup`, `record-drill`, and the after-restore step's "Restore completed") send the rest. Every one goes through the app's mailer like every other message: a `worker` task, three tries over thirty minutes, an "Email sent" or "Email failed" audit row, and the Status page's Email line; fixed wording, no template. See the Email notifications chapter for the mailer, the wording, and the `OPERATOR_EMAIL` rules. The drill project never sends mail, because its override leaves `SMTP_HOST` empty. Empty `OPERATOR_EMAIL` means no Operator mail; the Status page still shows everything.

### Audit rows

All four are System rows, metadata only.

| Row | When it is written | What it carries |
|---|---|---|
| Backup ran | by `record-backup`, at the end of a successful nightly job | duration, dump size, Snapshot size, Snapshots held |
| Backup failed | by `record-backup`, when the nightly job stopped at a failure, and when the weekly prune or check failed | reason class, step |
| Restore drill ran | by `record-drill`, at the end of every drill, pass or fail, in the live app's audit log | result, duration; on failure `drill_failed` and the step |
| Restore completed | by the after-restore step | the Snapshot's id and time, the outage span, counts, the Integrity result |

The Integrity check the restore runs writes its own row as always (see the Audit log and logging chapter); the drill's Integrity check runs inside the throwaway project, and only its result reaches the live app, in the "Restore drill ran" row. Each Operator mail writes its "Email sent" or "Email failed" row (see the Email notifications chapter).

### Environment keys

Every key lives in the app's `.env` at `<Install home>/.env`; `whisperx-service/.env` holds none of them.

| Key | File | Meaning | Placeholder or example |
|---|---|---|---|
| `BACKUP_TARGET` | `<Install home>/.env` | the restic repository over SFTP: the account, the store, and the folder as the store presents it at the root of the account's view; no port, 22 is assumed; empty means backups are off | `sftp:<backup account>@<backup store hostname>:/<backup folder>`; default empty |
| `BACKUP_SSH_KEY_FILE` | `<Install home>/.env` | the account's private key file, used by the `backup` service | `secrets/backup_ssh_key` |
| `BACKUP_KNOWN_HOSTS_FILE` | `<Install home>/.env` | the store's host key file, used by the `backup` service | `secrets/backup_known_hosts` |
| `BACKUP_KEY_FILE` | `<Install home>/.env` | the repository password file, used by the `backup` service | `secrets/backup_password` |
| `BACKUP_KEEP_DAYS` | `<Install home>/.env` | nightly Snapshots kept on the target, the keep rule (`restic forget --keep-daily`) | `30` |
| `BACKUP_LOCAL_DUMPS` | `<Install home>/.env` | nightly dumps kept in `backup/` | `7` |
| `BACKUP_TIME` | `<Install home>/.env` | when the nightly timer fires; written into the unit at install | `02:00` |
| `DRILL_TIME` | `<Install home>/.env` | when the weekly and drill timers fire; written into the units at install | `04:00` |
| `OPERATOR_EMAIL` | `<Install home>/.env` | the Operator address; asked by the install after the backup target; empty means no Operator mail; also the Reply-To on every message the app sends (see the Email notifications chapter) | `<operator address>`; default empty |

Keys of other chapters the drill override sets: `LDAP_ENABLED=0` and `SMTP_HOST` empty.

The secrets files:

| File | Mode | Holds | Comes from | Rides in the Snapshot |
|---|---|---|---|---|
| `secrets/backup_ssh_key` | 0400 | the store account's private key | the password manager, placed before the install; generated by the install only when none is there | no |
| `secrets/backup_password` | 0400 | the restic repository password | generated by the install; copied into the password manager before the first Snapshot | no |
| `secrets/backup_known_hosts` | not fixed by the sources | the store's host key | recorded by the install; compared by the installer | yes, with the rest of `secrets/` |

### Settings

No admin setting controls the Backup itself: the schedule, the target, and the keep rule are `.env` facts. This chapter's behaviour depends on these settings from the admin settings catalogue, whose tables it does not restate:

| Setting | What this chapter uses it for |
|---|---|
| Minimum free disk space | the preflight floor of the nightly job; the drill refuses when free space is under the Snapshot's size plus this floor |
| Folder management | a Backup taken while Off holds every Case as it was; when Off at the Snapshot, the restore writes no Off spell of its own, because the still-open toggle spell covers the gap |
| The Retention policy's days without activity | with the Recycle bin's days and the keep rule, bounds how long a Case exists anywhere: at most 90 days after Last activity with the defaults |
| The Recycle bin's days (default 30) | the bin wait before the wipe, counted into the same bound |
| The per-user quota (default 50 GB) | bounds `cases/` per user, and so the repository's ceiling |
| The idle timeout (8 hours) | why most Workspaces are gone by 02:00 |

### Compose, folders, host, and egress

- **Compose**: one more service, `backup`: image `restic/restic` pinned by digest, on the `transcribe` network, reaching the store on port 22 over the LAN, `profiles: [backup]` so `up -d` never starts it; `cases/` and the configuration files mounted read-only, `backup/` read-write for restores. Ten services with `vllm`. The drill override file `compose.drill.yaml` in the repository.
- **Folders**: `<App data folder>/backup/` (dumps, `manifest.json`, `last-run.json`); `<drill folder>`, empty between drills.
- **Host**: the three timer units and their service units, written by `./transcribe install` and kept in the repository.
- **Egress**: the store on port 22 on the LAN; nothing outside. The distribution and install chapter's egress list gains nothing.

### Ruled out

- The store vendor's backup agent for this host: its Linux agent supports the server's OS only through an older release, and the community-patched agent for the server's kernel is an unsupported hobbyist module.
- Joining another stack's backup set, timer, or store account on the same server: the stacks share nothing.
- Dated hard-link snapshots pushed by rsync, or a plain mirror: no check that the copy is sound beyond an exit code, privileged files lying plain on the store, and a mirror copies last night's mistake over this morning.
- A weekly or monthly tier, or any Snapshot older than the keep period: a monthly tier keeps everything for a year through the back door, and the Retention policy exists so unused material goes away.
- Restoring one Case from a Backup on request, and per-Case packaging in the Snapshot: Delete stays final and the Recycle bin is the only undo (out of scope on the map).
- Keeping Workspace text out of the dump: more code, and a restore could no longer be a plain load.
- Judging a restored Case's dates as they stand, or resetting deleted-on dates: the outage is an Off spell instead, which needs no new mechanism.
- A manual drill, a drill that stays up, or a rehearsal anyone is made to run: a drill nobody runs is not a drill.
- Panel settings for the schedule or the keep rule, and a scheduler container: a host timer fires when the stack is down and cannot be changed from inside a container.
- Pulling the nightly job into Phase 1: offered, not taken.

### Left to the build

- **The admin guide's Backups chapter and the restore runbook.** Written for a non-programmer. The runbook's first line is fixed above ("a restore takes the app back to 02:00 of the Snapshot's day, and everything done after that is gone"). The chapter carries: the store account and folder steps for a Synology-class device as this chapter lists them, the ordinary-account rule and how a volume path in `BACKUP_TARGET` betrays a mistake, the authorized_keys recipe from the store's shell, the three first-run failures, paste the key (only when the install printed one), the password-manager step before the first Snapshot, the host key comparison, what a restore loses, `BACKUP_TARGET` empty means off, and the store-side snapshot option as something nothing depends on. The "new box" runbook lives there and nobody is made to rehearse it.
- **The `check` items.** Modelled on the planning task's seven-check test script, which the build does not have; the eight items above are what the tickets fix. Whether item 4 (an extra folder visible at the account's root) fails the check or only warns is not fixed by the tickets: the planning test script was tightened to fail on it.
- **The unit files.** The three timers and their service units, in the repository, written from `.env` by the install; how the drill is ordered after the weekly prune and check when both fire at `DRILL_TIME` on the first Sunday; the name of the weekly command the weekly timer runs (the tickets name the timer and the two restic steps, `restic prune` and `restic check --read-data-subset=10%`, and no subcommand).
- **`compose.drill.yaml`**: the override that gives Postgres and the app container only, loopback ports, no Caddy, no GPU, no WhisperX service, no workers, `LDAP_ENABLED=0`, `SMTP_HOST` empty, and the restored configuration in a temporary folder that is never the Install home.
- **The restic image digest** pinned in the compose file.
- **Write access for a restore.** The `backup` service's nightly mounts are read-only for `cases/` and the configuration files and read-write only for `backup/`, while a restore puts `cases/` and the configuration back; how `restore` gets that write access is the build's.
- **The install on a box being restored.** The install uses an existing `secrets/backup_ssh_key`; the tickets say the repository password is generated by the install and, on a fresh box, is put into `secrets/backup_password` from the password manager after the install has run. What the install does when it finds a password already in place, or a repository already initialised at `BACKUP_TARGET`, is the build's, under the rule that a fresh box restores from the existing repository with the existing password.
- **Whether the install itself runs the first `backup` and `restore-drill`** or the guide's next step does; the password-manager copy of the repository password must come before the first Snapshot either way.
- **The type of key generated when none is found**; the tickets fix only that one is generated and its public half printed.
- **The manifest's JSON shape** (the fields are fixed: release tag, migration number, WhisperX service version, timestamps, a row count per table, a sha256 per file under `cases/`, the dump's size) and the shape of `last-run.json`, which the tickets name and do not describe.
- **What `./transcribe snapshots` prints** beyond the snapshot ids `restore` accepts.
- **The Status page's "next run"** and the `worker`'s hourly overdue check, beyond the thresholds fixed above (26 hours, 3 days).
- **The four Operator mails' wording** (fixed wording, no template) belongs to the Email notifications chapter.
- **The smoke test** the restore ends with belongs to the Architecture and deployment chapter.

### Sources

Backup and restore; Create the backup account and folder on the NAS.

### Amendments applied

- From the GitHub distribution ticket, recorded on Backup and restore, to the `backup/` folder rule: `config-pre-<tag>.tar` (0600) beside the pre-upgrade dump, kept and pruned with it.
- From the email notifications ticket, recorded on Backup and restore, to the Operator mail rule: the key is `OPERATOR_EMAIL`, asked after the backup target, empty means none, and it is the Reply-To; the four mails go through the app's mailer with its tries, audit rows, and Status line; the drill override leaves `SMTP_HOST` empty; `./transcribe check` sends a test message.
- From the Case Chat ticket, recorded on Backup and restore, to the Backup set: Case Chats ride in the dump and add nothing.
- From Create the backup account and folder on the NAS, recorded on Backup and restore, to the Backup target: the ordinary account rule, the path form at the root of the account's view, the quota and the full-folder behaviour, the host key file and the comparison, the sizing note.
- From Create the backup account and folder on the NAS (Q1), to Backup and restore's install step: the install uses an existing key at `secrets/backup_ssh_key` and generates one only when none, printing the public half only then; the password is still generated by the install.
- From Create the backup account and folder on the NAS to `./transcribe check`: the three first-run failures become checks, with the seven-check test as the model.
- From Backup and restore to the deployment topology's pre-upgrade dump: `pre-<tag>.dump` in Postgres custom format, not `.sql`.
- From Backup and restore to the Folder management toggle's Off spell: the row gains a cause (`toggle` or `restore`).
- From Backup and restore to the Queue's Failed rule: the reason class `restored`.


## 10. Admin panel additions in Phase 2

The Phase 1 panel stands: the rail, the tray, the confirmations, the Off-hides-never-deletes rule, and every Phase 1 page. Phase 2 adds pages, rows, lines, and actions; each chapter above fixes the behaviour behind them, and the admin settings catalogue defines every row. This chapter lists what the panel gains so the build can lay it out in one pass.

### Settings pages

| Where | What arrives |
|---|---|
| A **Cases** page in the Settings group | Folder management (default Off); Sharing (default Off); Retention period (30 days); Warning before deletion (7 days); Recycle bin (30 days); Recording types (the six shipped); Speaker roles (the eight shipped). Sharing, Retention period, Warning before deletion, Recycle bin, and Speaker roles are greyed while Folder management is Off and keep their values. |
| An **Email** page in the Settings group | Email notifications (default On; greyed "SMTP not configured" while `SMTP_HOST` is empty); Batch finished emails (default On); the four Notification templates, a Subject and a Body each with Reset to default, saved through the tray so the Setting changed row keeps the old and new text and Apply refuses an unknown placeholder; the Test message button, outside the tray, which mails the signed-in Admin (or the Operator address when that Admin has no Email address) and shows the relay's reply. |
| The **AI assistant** page | Chat across cases (default On; under the master switch, independent of the viewer's Chat toggle); the Case chat prompt template beside Ground rules, Chat, and Speaker suggestions, editable with Reset to default and a version, applied at once like the other templates. |
| The **Limits** page | Case chat: most hours of talk per question (120 hours, 6 to 600). |

The tray works as in Phase 1. Two rows differ in what they show: the Folder management row carries the counts of Cases, GB, and owners it hides or shows again ("Folder management: On to Off. Hides 14 cases, 210 GB, for 6 users. Nothing is deleted."), and a Notification template's row carries its old and new text.

### Overview pages

| Page | What arrives |
|---|---|
| **Status** | A Cases line: "Cases: N, X GB; M expiring; K in the recycle bin, Y GB", followed by "Folder management has been off since <date>" while Off. A Backup line: the last Snapshot (time, result, size, Snapshots held, next run) and the last drill (time, result); red when the last successful Snapshot is older than 26 hours, when the last Snapshot or the last drill failed, or when `BACKUP_TARGET` is empty; amber when a drill is more than 3 days overdue. An Email line: "Email: not configured", or the last sent and the last failure with its reason class, red while the last try failed; beside it "People without an email address: N". |
| **The Admin's Cases page** | Every Case in the app, with an owner filter, an "Owner deactivated" filter, and an "Expiring" filter; Keep on any row, audited with the owner as affected user; Reassign (one Case, or every Case a user owns) and Delete. Opening a Case from it shows the banner and writes the Admin access row unless the Admin is a Collaborator on that Case. Hidden while Folder management is Off. |
| **The Recycle bin page** | Every user's deleted Cases, with an owner filter and the "Owner deactivated" mark: name, Recordings, size, deleted on, days left, Restore, Delete permanently (behind a confirmation naming the counts). Reached from the Cases page. Hidden while Folder management is Off. |
| **Users** | The Recordings and GB figures include Cases, shown as "3 in session, 41 in cases", and stay while Folder management is Off. The quota's description says it covers the Workspace and every Case the user owns together. "Reassign to a named user" and "Delete data" come alive (Delete data wipes the user's Cases, binned Cases included, behind a confirmation naming the counts), and grey out again while Folder management is Off. The userPrincipalName column is relabelled "Directory address" and an "Email" column arrives beside it, with "No email address" on blank rows and a filter for them; Create Local admin gains an optional Email field, editable on the Local admin's row. |
| **Audit log** | The category filter gains Email; the Cases category rows (Case created, renamed, deleted, reassigned; Recording moved to case, between cases; Share granted, revoked; the six Retention rows; the five Person rows; `case_chat_turn`) appear as they are written. |
| **Installation** | Read-only rows for the backup facts (the Backup target as account and host, never the key; the schedule; the keep rule; the local dump count; whether the two backup secrets are set) and the seven mail keys, the password shown as set or missing. The backup schedule and keep rule are `.env` facts and never settings, because a host timer cannot be changed from inside a container. |

### Help

The Help link opens the admin guide, which gains the Backups chapter with the restore runbook, the Email chapter, the Retention content, the Folder management toggle both ways, and the two Case Chat settings (the Repository, releases, and distribution chapter of the Phase 1 specification lists them).

### Audit rows

| Row | When it is written |
|---|---|
| Setting changed | one per changed setting at Apply, as in Phase 1; the Folder management row's details block carries the counts; a Notification template's carries the old and new text |
| Template saved, Template reset | Save or Reset to default on the Case chat prompt template, as for the Phase 1 templates |
| Test email sent | the Email page's Test message button, or `./transcribe check` |

### Settings

Every row above is defined in the admin settings catalogue with its type, default, range, and effect. Nothing in this chapter adds a setting the catalogue does not hold.

### Left to the build

- The layout of the Cases and Email pages within the Phase 1 form layout (name and help on the left, control on the right, "Default: x", "changed from default", "When changed").
- The Recycle bin page's and the Admin's Cases page's layouts beyond the columns, filters, and buttons the chapters fix.
- How the Status page's three new lines sit among the Phase 1 lines; the sources fix the lines and their colours, not their order.

### Sources

Admin settings catalogue and panel (its Phase 2 amendments); Case folder model on the mount; Sharing model; Retention policy; Folder management toggle transitions; Speaker management panel; Backup and restore; Email notifications over SMTP; Chat across a whole Case.

## 11. Upgrading from Phase 1

Phase 2 is a Release like any other: a tag, `v2.0.0`, with a GitHub Release whose notes are its changelog section, installed with the helper script. This chapter gathers what an office running Phase 1 does to reach it, and what the app does by itself.

### Before you begin (Phase 2)

The install guide's "Before you start" gains these items, each the office's own work outside the app:

1. **The backup store.** An ordinary account and a shared folder of the app's own on the office's backup store, SFTP only, key-only, with the account's public key placed from the store's shell (the Backup and restore chapter). Where the office already made the key pair, its private half is placed at `secrets/backup_ssh_key` before the install runs, so the install uses it and prints nothing to paste.
2. **The mail relay.** A relay that accepts mail from the server's address, without a password or with one over STARTTLS, and lets the sender address through; the sender address and the Operator address chosen (the Email notifications chapter).
3. **The directory.** Every member of the Sign-in group has a `mail` value, and the Bind account can read `mail`; `./transcribe check` counts who still lacks one.
4. **The drill folder.** `<App data folder>-drill/` exists beside the App data folder, empty, owned by the app's system user (the Architecture and deployment chapter's server preparation already creates it).

### The upgrade

1. `./transcribe upgrade v2.0.0`: refuses while a Job runs or tracked files have local edits; takes the pre-upgrade dump `backup/pre-v2.0.0.dump` and the configuration copy `backup/config-pre-v2.0.0.tar`; reads out the changelog's "Models" and "Database" lines; fetches and checks out the tag; pulls or builds the images; brings the stack up, which runs the migrations; pulls models when the notes say they changed; runs `./transcribe check`. Roll back is `./transcribe rollback v1.x` with the pre-upgrade dump restored when a migration cannot be reversed (the Architecture and deployment chapter).
2. **The new office facts.** Phase 2 adds keys to `.env` (the Backup target and its seven companions, the Operator address, and the seven mail keys) and up to four secrets files (`secrets/backup_ssh_key`, `secrets/backup_password`, `secrets/backup_known_hosts`, and `secrets/smtp_password` when the relay wants a password). `./transcribe install` asks the Phase 2 questions after the Phase 1 ones, in the order the Repository, releases, and distribution chapter of the Phase 1 specification fixes, and only `install --reconfigure` overwrites an existing `.env`, `secrets/`, or `tls/`.
3. **The backup steps of the install.** The key is used or generated, the repository password generated into `secrets/backup_password`, the store's host key recorded, the repository initialised, the three timer units written, and the sequence ends with `backup` then `restore-drill` on the just-upgraded state, so the operator sees both succeed before the app has anything to lose. The repository password and the private key are copied into the office's password manager before the first Snapshot.
4. **After the upgrade.** `./transcribe check` prints the Phase 2 lines: the Backup target proved eight ways, the relay's reply to a test message to the Operator address, and the count of Sign-in group members without `mail`.

### What users see

Nothing, until an Admin turns Folder management On: the setting arrives Off, so the app keeps landing on the Recordings page and behaving as Phase 1. When it goes On, the Cases pages appear at once with no announcement, and the empty Cases page says "No cases yet. A case keeps recordings after you sign out." Sharing arrives Off too. Email notifications arrives On but sends nothing until `SMTP_HOST` is set and a person has an Email address. Chat across cases arrives On under the AI assistant master switch.

### What Phase 1 carried and Phase 2 brings alive

Every hook the Phase 1 chapters listed under "Carried for Phase 2" comes alive here, without a data migration of its own:

- the Recording row's Case link, Recording type, and Description; the Case table with its deleted-on date, the Share table, and the Off spell table, all empty; `cases/` beside `scratch/`;
- the Discard and the sweepers skipping any Recording with a Case;
- the users list's greyed "Reassign to a named user" and "Delete data";
- the Speaker row's empty Person link, the viewer's pick-or-type rename box, the Known names list, and the Appearances table's hidden Role column;
- the prompt inventory's room for the Case chat template and the combining instruction;
- the sign-out dialog's place for "Move to case";
- `backup-db` and the `backup/` folder, the `pre-<tag>.dump` format, and the first-run order that places files after the clone;
- the Email address stored at sign-in and refreshed by the Directory check, unused in Phase 1;
- the Batch's end as the hook for the "batch finished" Notification;
- the reason class `restored` and the Off spell's cause on the audit row.

The changelog section for `v2.0.0` opens with its two fixed lines; the "Database" line says whether the Release migrates, and `./transcribe upgrade` reads both out before it starts.

### Left to the build

- **How the Phase 2 keys reach an existing install.** The decisions fix that `./transcribe install` asks the Phase 2 questions, that a re-run refuses to overwrite an existing `.env`, `secrets/`, or `tls/` without `--reconfigure`, and that `--reconfigure` asks everything again. Whether `upgrade` prompts for the keys a new Release needs, or the guide's upgrade chapter tells the operator to run `install --reconfigure` after `upgrade v2.0.0`, is not fixed; either way the Phase 1 values, secrets, and certificate are never touched by the upgrade itself.
- **The Phase 2 migrations.** Which tables and columns Phase 1 ships empty and which Phase 2's migration adds (the People table is the one the sources leave open); the sources fix that turning Folder management on adds pages, not tables.
- **The install guide's upgrade chapter and the admin guide's Phase 2 chapters** (the Repository, releases, and distribution chapter of the Phase 1 specification lists them).

### Sources

GitHub distribution and install story; Deployment topology on the rebuilt server; Backup and restore; Create the backup account and folder on the NAS; Email notifications over SMTP; Folder management toggle transitions; Case folder model on the mount; Speaker management panel; the Phase 1 chapters' "Carried for Phase 2" lists.

## 12. Build gates and deliverables

What the Phase 2 build must prove and deliver beside the running app. The Phase 1 gates stand and are not repeated; the benchmark gate runs again only if the pinned stack or the models change.

### Gates

| Gate | What is proven |
|---|---|
| The Backup target | `./transcribe check` proves the store eight ways (the Backup and restore chapter): key-only sign-in, the root listing, the folder's path, write and remove, no `#recycle`, no shell, the host key comparison, and the two secrets present. The first `backup` and the first `restore-drill` succeed at the install, on the just-upgraded state. |
| The restore | A restore onto a fresh box from the newest Snapshot, following the admin guide's runbook, brings the app back to the Snapshot's night: the manifest's counts and hashes match, the Integrity check reports unbroken, in-flight Case-bound Jobs are Failed with `restored`, every Workspace is discarded, and the outage is an Off spell. |
| The Retention policy | Under a short Retention period on a throwaway Case, one night's sweep warns, deletes into the Recycle bin, and wipes after the bin period, writing its six rows and sending the digest; the same Case survives a Folder management Off spell with its days intact. |
| Mail | The relay accepts the test message; the digest, the share mail, the handover mail, and the batch-finished mail each arrive with the fixed wording and nothing but names, counts, dates, and one link. |
| The Case Chat | A Case that fits one Reading and a Case that needs several parts both answer with checked Citations that open the right Recording; a Case over the hours ceiling refuses with `llm_case_too_large`; a question never returns a half answer. |
| People | Renaming on the Speakers tab changes every linked Speaker across the Case in one transaction; a viewer rename changes one Recording only; a merge relinks and renames without merging two Speakers inside one Transcript. |

### Deliverables of the Phase 2 build

1. **The Release** `v2.0.0`, its changelog section opening with the two fixed lines, its images on ghcr.io.
2. **The Compose additions**: the `backup` service under profile `backup`, `compose.drill.yaml`, and the three timer units with their service units in `systemd/`, written from `.env` by the install.
3. **The helper script's Phase 2 subcommands** `backup`, `snapshots`, `restore <snapshot>`, and `restore-drill`, the Phase 2 install questions, and the Phase 2 `check` lines.
4. **The app commands** `backup-preflight`, `write-manifest`, `record-backup`, `after-restore`, and `record-drill`.
5. **The guides' Phase 2 chapters**: the admin guide's Backups chapter with the restore runbook and the store steps for a Synology-class device, the Email chapter, the Retention content, the Folder management toggle both ways, and the two Case Chat settings; the user guide's pages on Cases and the clock, the Retention digest and the other mail, the Batch tick, and the Case Chat; the install guide's Phase 2 "Before you start" items and upgrade chapter.
6. **The pages**: the Cases page and Case page with its four tabs, the Recycle bin page, the Admin's Cases page, the Cases and Email settings pages, and the Status, Users, Installation, and Audit log additions.
7. **`THIRD_PARTY_LICENSES.md`** gains restic.

### Open points the build settles within the rules

- Whether a Collaborator's Move to case of their own Done Recording into a shared Case can be refused for room; the Sharing chapter carries the two readings as an unresolved point.
- The cause recorded on "Recording deleted" when a Collaborator deletes a Recording they added, and whether Transfer's automatic Share for the old owner writes "Share granted" (the Sharing chapter).
- Which cause "Case permanently deleted" carries when the users list's Delete data wipes a leaver's binned Cases (the Retention policy and the Recycle bin chapter).
- The tray row's wording on a change of Folder management to On (The Folder management toggle chapter).
- How the Phase 2 keys reach an existing install: `upgrade` prompting, or `install --reconfigure` (the Upgrading from Phase 1 chapter).
- Whether the Upload page's "Email me when this batch finishes" tick also hides while "Email notifications" is Off, and whether the Test message button sends within the request or through the background task (the Email notifications chapter).
- How `restore` gets write access to `cases/` and the configuration files, given the `backup` service's read-only nightly mounts, and what the install does when it finds a repository password already in place or a repository already initialised (the Backup and restore chapter).

## 13. Deferred and ruled out

A builder needs to know what not to build as much as what to build. The first list is work that may come later and is deliberately unspecified; nothing in it is designed, and nothing in the app should anticipate it beyond what a chapter says under "Carried for Phase 2". The second list is work ruled out of the app for good, with the reason; it returns only if the office that runs the app redraws the product's scope, and then as a fresh effort.

### Deferred: possible later, not specified

- Sample recordings in languages other than English, and interpreter-mediated recordings, for the benchmark's translation leg. The four checks of that leg are fixed (see the Transcription, translation, and diarization choices chapter); running them waits on the samples. A recording longer than two hours is optional in the sample set, since a recording of about one and three quarter hours is accepted as the long sample.
- Watched-folder ingest on a schedule: who owns files dropped into a folder, how they map to users and Cases, and how they share the serial Queue. In neither phase's list.
- Saved Chat questions: admin-kept preset questions shown as buttons in a Chat. The prompt-template machinery could serve it.
- Streaming Chat and Summary answers word by word. This needs a live channel from server to browser, which the queue design declined to build; every page polls instead.
- A second GPU worker or parallel transcription, if the serial Queue bottlenecks at the office's size. Under the serial-queue decision (ADR 0005) this is a change to the WhisperX service that every Consumer inherits, never a change to the app.
- Alerting when the WhisperX service, the engine, or disk health degrades. The Status page is in scope; alerting is not. Backup failure, overdue, and drill mail to the Operator address, and the mail plumbing, are settled in Phase 2, so an alerting design would need only its event list.
- Mobile and tablet use.
- Combining several Clips into one file (a highlight reel for a hearing). The Clip model was fixed without it.
- GPU video encoding (NVENC) for Playback copies, only if CPU transcodes of real body-camera files prove slow in the Phase 1 build.
- A "Phone" Preprocessing profile (a band filter and gentle noise reduction) for narrowband calls, shipped only if the Phase 1 benchmark gate shows it measurably lowers errors on jail-call and phone recordings.
- Forwarding audit rows to a log collector or SIEM as they are written, for tamper-proofing beyond the hash chain. No collector is assumed to exist.
- A public route for the WhisperX service (a hostname, a certificate, a route on the app's Caddy or its own) when a second Consumer appears. Today the service has no hostname and no published port.
- Tags on Recordings in a Case, typed by users, so that a Case Chat can be narrowed to the Recordings carrying one tag. Recording type is an admin-kept list picked at upload and is not this.

### Ruled out

- Restoring or reusing any earlier transcription app, engine wrapper, or saved container image (ADR 0002). Earlier apps may be read for facts only, never for code.
- Translation to any language other than English, and keeping the original-language text alongside the English.
- SSO middleware or OIDC for sign-in. Sign-in is the office directory over LDAPS plus Local admin accounts.
- Paid services, paid models, or anything cloud-hosted. Everything runs on the office's own server with free tools.
- Network shares (Samba or the like) onto the App data folder.
- Access for anyone outside the office.
- Downloading the uploaded original from the app. The file of record lives outside the app, so the app keeps the uploaded bytes only to hash, inspect, and derive from. Users take media out of the app as Clips or exports.
- A user-facing view of the audit log (own history, recent sign-ins) and any export of the log. The log is an Admin-only troubleshooting record. The rows exist, so a later effort could add either.
- A bulk "Summarise all" on the Batch page. Summaries are asked for one Recording at a time; the Phase 2 answer to "tell me about all of these" is the Case Chat.
- Sharing a Case with a directory group or a typed address. A Share names a person who has signed in to the app at least once, so the app never enumerates or watches group membership.
- Legal hold, per-Case retention exceptions, and any other way to exempt a Case from the Retention policy's clock. The way to keep a Case is to use it or press Keep.
- A Recycle bin for what a person deletes. The bin holds only what the clock deletes; a person's Delete of a Case or a Recording stays final behind its confirmation.
- An office-wide list of People, or any link between names across Cases. People live inside one Case, and nothing crosses a Case's edge.
- Voice matching of the same Speaker across Recordings, and storing speaker embeddings (voiceprints), in either phase. The WhisperX service keeps its `return_speaker_embeddings` door and the app never opens it; a later effort could decide about voiceprints for itself and Process old Recordings again to get them.
- Restoring one Case from a backup on request, and packaging each Case inside a Snapshot so that it could be. A backup is for the server dying, the whole app comes back to one night, and a person's Delete stays final against backups too. A later effort could add the packaging and a restore-one-Case command without changing the Snapshots taken before it.
- A retrieval index (embeddings and rerankers) behind the Case Chat. The assistant reads whole Transcripts, in one Reading or in parts, and nothing is embedded or indexed in either phase; no embedding service is a dependency of this app. A later effort could add retrieval for pinpoint questions on very large Cases without changing what exists.
- A Summary of the whole Case. "Summarise this case" is a question to the Case Chat, and its answer exports like any other; a Case Summary shaped by a Summary template could ride on the same Readings if an office ever asks.

## Appendix A. Environment keys added in Phase 2

All in the app's `.env`, asked by `./transcribe install` after the Phase 1 questions, shown read-only on the Installation page. The service's `whisperx-service/.env` is unchanged.

| Key | Meaning | Default or placeholder | Chapter |
|---|---|---|---|
| `BACKUP_TARGET` | the restic repository over SFTP: `sftp:<backup account>@<backup store hostname>:/<backup folder>`; no port, 22 assumed; empty means backups are off | empty | Backup and restore |
| `BACKUP_SSH_KEY_FILE` | the store account's private key file | `secrets/backup_ssh_key` | Backup and restore |
| `BACKUP_KNOWN_HOSTS_FILE` | the store's host key file | `secrets/backup_known_hosts` | Backup and restore |
| `BACKUP_KEY_FILE` | the repository password file | `secrets/backup_password` | Backup and restore |
| `BACKUP_KEEP_DAYS` | nightly Snapshots kept on the target | `30` | Backup and restore |
| `BACKUP_LOCAL_DUMPS` | nightly dumps kept in `backup/` | `7` | Backup and restore |
| `BACKUP_TIME` | when the nightly timer fires | `02:00` | Backup and restore |
| `DRILL_TIME` | when the weekly and drill timers fire | `04:00` | Backup and restore |
| `OPERATOR_EMAIL` | the Operator address; the Reply-To on every message; empty means no Operator mail | empty | Email notifications; Backup and restore |
| `SMTP_HOST` | the office relay; empty means the app sends no mail | empty | Email notifications |
| `SMTP_PORT` | the relay's port | `25` | Email notifications |
| `SMTP_STARTTLS` | `auto`, `always`, or `never` | `auto` | Email notifications |
| `SMTP_USER` | the relay's sign-in name, when it wants one | empty | Email notifications |
| `SMTP_PASSWORD_FILE` | the secrets file holding the relay's password, when it wants one | empty | Email notifications |
| `MAIL_FROM` | the sender, shown as "Gideon Transcribe <address>"; required when `SMTP_HOST` is set | empty | Email notifications |

Secret files added: `secrets/backup_ssh_key` (0400; from the password manager, or generated when none), `secrets/backup_password` (0400; generated by the install and copied into the password manager before the first Snapshot), `secrets/backup_known_hosts` (recorded by the install), and `secrets/smtp_password` (only when the relay wants a password). The first two never ride in a Snapshot. The drill override sets `LDAP_ENABLED=0` and `SMTP_HOST` empty for the throwaway project.

## Appendix B. Audit rows added in Phase 2

Every row uses the Phase 1 field set and holds metadata only; a Case's snapshot label is its name, a Person's is "Person <id> in <Case name>", and a Person's name and notes join the never-logged list. The affected user is the owner whenever someone else acts.

| Category | Row | Chapter |
|---|---|---|
| Cases | Case created; Case renamed; Case deleted (N recordings, X GB); Case reassigned (Reassign or Transfer); Recording moved to case; Recording moved between cases; Recording opened (also when a Collaborator opens one, with the owner as affected user) | Cases; Sharing |
| Cases | Share granted; Share revoked | Sharing |
| Cases | Retention warning; Case kept; Case deleted (cause: retention); Case restored; Case permanently deleted (cause: recycle bin period, owner, or admin) with one Recording deleted (cause: retention) row per Recording; Retention sweep ran | Retention policy and the Recycle bin |
| Cases | Person added; Person renamed; Person edited; Person merged; Person deleted | People and the Speakers tab |
| LLM | `case_chat_turn` (the Case as object; transcripts read, Readings used, model, endpoint host, template versions, token counts, duration, outcome) | Case Chat |
| Exports | export made, kind `case chat` | Case Chat |
| Admin | Setting changed for the Phase 2 rows (the Folder management row with its counts; a Notification template with its old and new text); Template saved and Template reset for the Case chat template; Test email sent | Admin panel additions in Phase 2; Email notifications |
| Accounts | Email address updated | Email notifications |
| Email | Email sent; Email failed (reason class, tries); Test email sent | Email notifications |
| System | Backup ran; Backup failed (reason class, step); Restore drill ran; Restore completed; Integrity check ran (after a restore, as always) | Backup and restore |

Never written: a row for a Rename of a Clip; a row while Folder management is Off from the retention sweep; a row for a person without an Email address; a row for a viewer's Playback.

## Appendix C. Reason classes added in Phase 2

| Where | Classes | Chapter |
|---|---|---|
| Job failed | `restored`: a Case-bound Job that was Queued or Running at the Snapshot, failed by the after-restore step with Retry | Backup and restore; Queue and Jobs (Phase 1) |
| Case Chat | `llm_case_too_large`: the question would read more hours of talk than the Limits setting allows; `llm_too_long` gains a second use, one Transcript that cannot fit a Reading even alone | Case Chat |
| Email failed | `smtp_unreachable`; `smtp_refused`; `smtp_auth_failed` | Email notifications |
| Backup failed | `disk_full`; `dump_failed`; `manifest_failed`; `target_unreachable`; `snapshot_failed`; `prune_failed`; `check_failed` | Backup and restore |
| Restore drill ran | `drill_failed`, with the failing step | Backup and restore |

## Appendix D. Sources

| Chapter | Tickets |
|---|---|
| Cases; Sharing | Case folder model on the mount; Sharing model |
| Retention policy and the Recycle bin; The Folder management toggle | Retention policy; Folder management toggle transitions |
| People and the Speakers tab; Case Chat | Speaker management panel; Chat across a whole Case |
| Clips in Cases | Clips: model, lifecycle, and management (its Phase 2 section) |
| Email notifications | Email notifications over SMTP |
| Backup and restore | Backup and restore; Create the backup account and folder on the NAS |
| Admin panel additions in Phase 2; Upgrading from Phase 1; Build gates and deliverables | the Phase 2 amendments on Admin settings catalogue and panel, GitHub distribution and install story, and Deployment topology on the rebuilt server, and every Phase 2 chapter's "Left to the build" |

The decision records (`docs/adr/`) and the research findings (`docs/research/`) ship with this document; the tickets stay in the planning repository of the office that wrote the app.
