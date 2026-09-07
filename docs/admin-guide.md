# The Admin guide

This guide is for the Admins of one installation: the people who run the Admin panel, look after the users, and keep the server going. It assumes you have read the user guide and can find your way around the app as a user. Installing and upgrading are in the install guide, which is in the repository and not in the app.

Everything an Admin does in the panel is written to the audit log, with the Admin's name against it. An Admin who opens another person's recordings is recorded doing so, every time.

## The Admin panel

The panel is reached from **Panel** at the top of every page, and only an Admin sees that link. Its rail, down the left, has four groups:

- **Overview**: Status, Queue, Users, and the Audit log.
- **Settings**: one page per group of settings. A number beside a page's name is how many of its changes are waiting in the tray.
- **Server**: the Installation page.
- **Help**: this guide, the user guide, and the way back to your recordings.

### Who is an Admin

There are three ways to be one, and the Users page shows which applies to each person:

1. **The Admin group** in the office directory. Anybody in it is an Admin the next time they sign in, and stops being one when they leave it. Nested membership counts.
2. **The manual flag**, set on the Users page. It only ever adds: it cannot demote a member of the Admin group.
3. **A Local admin**, an account kept inside the app with its own password, for reaching the panel when the directory is down. Every local account is an Admin, because that is the only reason to have one.

## The tray

No setting applies as you edit it. Each settings page collects your changes and **Put changes in the tray** moves them into a bar at the foot of the panel, which lists every waiting change as the setting's name, what it was, and what it will be. The bar follows you from page to page, and the rail counts the waiting changes beside each page's name.

The bar has a box for a **note for the audit log**: a ticket number, or the reason. It is optional, and it is the only free text an Admin can put in the log. **Apply** makes every waiting change at once and writes one audit row per setting, with the note against each. **Cancel all** drops them.

Leaving the panel with a tray that is not empty asks whether to apply or drop. Nothing is ever applied by accident.

## The settings

Every setting has a table in the settings catalogue in the repository (`docs/spec/ADMIN-SETTINGS-CATALOGUE.md`), with its default, its limits, and its consequences. A setting that has been changed from its default carries a mark, and the default is shown beside it. This is what each page is for:

- **Features**: whether speaker separation, translation, clips, and live recording are offered at all. Off hides the feature everywhere; nothing already made is deleted. **Live recording** is greyed while Folder management is off, since a recording made in the browser lands in a case; see Live recording below.
- **Limits**: the largest file, the longest recording, the longest live recording (three hours by default, which the Record page enforces so a page left recording overnight does not fill the disk), the longest clip, the most files in one batch, the default quota per user, and how much free disk the server must keep. Uploading pauses when free disk falls under that last figure, and the Upload page says so.
- **Transcription defaults**: the model, whether speaker separation and translation are ticked by default, whether a mixed-language recording is translated without being asked, the office vocabulary that is added to every user's, and the preparation profile.
- **AI assistant**: the assistant and its parts, and the engine it talks to. An installation with no engine leaves the assistant off and everything else works.
- **Notices**: the four fixed texts. The **Transcription notice** goes on every export. The **Translation notice** goes on every export of a translated transcript. The **AI notice** goes with anything the assistant writes. The **Sign-in page notice** is the line under the sign-in form: an authorised-use statement, or where to ring for help. Empty hides it.
- **Sign-in and directory**: the idle timeout, eight hours by default, after which a login session ends and the person's recordings go; and the hour of the nightly directory check. The directory's own facts are shown read-only here, because they are set at install and not in the panel.
- **Audit log**: how many months of audit rows are kept, three by default. See the audit log below for what that means.
- **Appearance**: the **Office name**, shown under the logo on the sign-in page and on the cover of every Word export, and the **Logo on Word exports** toggle. The same page holds the **office logo** itself, uploaded and removed at once rather than through the tray: a PNG or JPEG up to 2 MB, a wide mark reads best. It appears large on the sign-in page as soon as it is uploaded, and at the head of every export's cover once the toggle is on. It is kept with the app's own data, so a backup carries it, and it never leaves the server.
- **Cases**: the **Folder management** toggle that turns Cases on for the whole office, the **Sharing** toggle that lets owners share a case with named colleagues (greyed while Folder management is off; off hides the Share button, the Shared with panel and shared cases from collaborators' lists, and keeps every share, so on brings them back), the list of **Recording types** a person may label a recording with, and the list of **Speaker roles** a person in a case may be given (Defendant, Witness, Officer and the rest; one per line, a removed role stays on the people that hold it). Off hides every case from everyone, Admins included, and deletes nothing; on brings them all back as they were. Beside them, greyed while Folder management is off, the Retention policy's three numbers: the **Retention period**, thirty days by default; the **Warning before deletion**, seven days and always shorter than the period; and the **Recycle bin**, thirty days. See the Retention policy below.

## The Status page

Everything on it is read again every five seconds. It has six blocks.

**Services**: each container, whether it is listening, and whether its own health check passes. Amber is slow or waiting; red is down.

**WhisperX service**: whether the transcription service answers, which model it has loaded, and what it is doing.

**Storage and workspaces**: free disk against the minimum, how many people are signed in, and how much they are holding between them.

**Directory**: when the last nightly check ran and what it found. **Test directory connection** runs the same checks `./transcribe check` does, from inside the app, and says which step failed if one did. **Check directory now** runs the nightly check at once: it deactivates anybody who has left the sign-in group and reactivates anybody who has come back, and it is the way to pick up a change without waiting for three in the morning.

**Audit log**: the newest row, and **Integrity check**, which walks the whole log and reports whether any row has been changed or removed since it was written.

**Versions**: the Release this server is running, and the versions of the things underneath it. If it says "not tagged", the server was not installed by `./transcribe upgrade`; the install guide says how to put that right.

## The Queue page

Every transcription job in the office, whoever started it: the user, the recording, its batch, its length, its state and its step. One runs at a time, in arrival order, with no priority for anyone, and this page is where you see whose turn it is.

**Cancel** stops one job. The person's recording stays; only its transcription is stopped, and they can retry it. Cancelling is written to the audit log with your name.

## The Users page

Everybody who has ever signed in, with their role, where their admin status comes from if they have one, whether they are signed in now, how many recordings they are holding, their quota, and their last sign-in.

For each person:

- **End sessions** signs them out everywhere, now. Their recordings are then discarded as they would be at any sign-out.
- **Block** stops them signing in until an Admin lifts it. It is yours to lift; the directory check never does. **Unblock** lifts it.
- **Admin flag** makes them an Admin, or takes it back. It cannot take admin status from a member of the Admin group.
- **Set quota** gives them a quota of their own instead of the default.
- **Open workspace** shows you their recordings, as they see them. This is recorded in the audit log every time, with your name and theirs, and it is not use: it does not keep their session alive. Do it when there is a reason, because the log will show it.
- **Reassign** moves a person's recordings to somebody else, for when someone has left. The shares on the cases go with them as they are; Reassign adds nobody, and the new owner is mailed "a case handed to you" for each case when mail is on. **Delete data** removes them, and with their cases every share on those cases.

A person who has left the sign-in group is shown as **Deactivated** after the next directory check and cannot sign in. Putting them back in the group and running **Check directory now** reactivates them.

**Local admins** are created at the foot of the page. A Local admin has a password kept in the app, which **Change password** sets and which never goes anywhere near the directory. Keep one, for the day the directory is down, and give it a long password.

## The audit log

On a wide monitor the filters sit in a pane on the left and stay put while you scroll the rows; on a laptop they sit above the table.

The log records what happened, who did it, and to whose material: sign-ins and sign-outs, uploads, downloads, corrections, deletions, every settings change with its note, every action on the Users page, every cancelled job, and every time an Admin opens somebody else's recordings.

It never records any of these, whatever the page and whoever is signed in: transcript text, either side of a correction, chat questions or answers, summaries, vocabulary, search terms, file contents, passwords, tokens, speaker names, clip titles, or clip notes. A recording's original file name is kept, because it is the only way to recognise a recording after it has been discarded.

The Audit log page shows the rows newest first and filters them by date, person, category, and outcome. Each row names the actor, what happened, whether it succeeded, the affected person where that is not the actor, the object, and the client it came from.

**Retention.** Rows older than the **Audit log retention** setting are removed by a nightly sweep. Three months is the default. The record of an Admin opening somebody's recordings is a row like any other, so the retention period is also how long that record lasts: an office that wants a longer memory of Admin access sets a longer retention.

**Integrity.** Every row carries a hash of itself and of the row before it, so a row that is changed or removed afterwards breaks the chain. **Integrity check** on the Status page walks the chain and says whether it holds. Rows are written through a database role that can only insert, and removed only by the sweep's own role; the app's ordinary role can do neither.

## Live recording

With **Live recording** on (Features page, under Folder management), people make a recording in the browser on an office computer, from the microphone and, when they tick it, from what the computer plays (a Zoom or Teams call, a softphone, a jail call played there), into a case: **Record** appears beside Upload on the Cases page and beside Add recordings on a case's page. The browser encodes the sound and sends it to the upload sidecar in pieces as it goes, on the same path an upload takes; nothing leaves the building, and a browser that dies loses at most the last few seconds. When the recording ends, its transcription job goes to the service with a priority above every uploaded one, so a meeting that has just ended is transcribed before the batches waiting; the service runs one job at a time, so recordings that end together wait their turn, and the page and the case row say where each stands in words. Nothing rougher than the finished transcript is ever shown.

A recording made with the computer's sound is a two-channel call by the fact of how it was made, the microphone on one side ("This side") and the computer on the other ("The other side"), transcribed a side each; the browser offers the computer's sound only as part of sharing a screen, and the page drops the picture at once. A live recording is a recording: it joins its case as it starts, counts against the case owner's space, follows the retention clock, and is shared, exported, and deleted like any other. Its own batch never holds up the person's uploads. While recording, people tap the case's people as they start talking, and when the transcript lands each diarized speaker takes the name whose taps cover most of its speech (on a call, the microphone's side only), writing the ordinary speaker renames and a **Speakers named from taps** row with the count; a tapped person who is not yet a person of the case becomes one. Marks (a moment and an optional word) are shown in the viewer's Details as clickable times; a mark's word is content and never reaches a row or a message. The audit log writes **Live recording started** (the case, the sources, the language choice; never the title) and **Live recording finished** (how it ended, the length, the pauses, the counts of taps and marks). The Details panel and the Word export say it was recorded live, with what, and how it ended. It works in Edge and Chrome on the office's Windows computers; phones, tablets, and a desk phone's calls are outside it. What to record is the attorney's call: the app asks for no consent and refuses no source.

The service's contract gained a `priority` field for this (service 0.2.0); a job's position and the minutes of audio ahead of it count what runs before it under the rule.

**Transcription during the recording.** A recording made in the app is transcribed while it records: every five minutes of it (a stretch), and what came before a pause, is cut from the pieces already on the server, prepared as a whole recording is, and sent to the service at once, ahead of everything else in line; at Stop only the last stretch is left, so the transcript is ready about a minute later whatever the length. Each stretch is transcribed at the same quality as a whole recording, with the speakers told apart within it, and the stretches' speakers are matched across the recording by their voices when it is put together, so one person keeps one name. Nothing is shown before the transcript is whole; the person's page says "Recording" and then "Finishing: about a minute". A stretch that fails while the recording runs is tried once more at Stop, from the whole file. The Details panel says "Transcribed while recording, in N stretches". With the fast lane on, the stretches run there and never wait behind an upload; without it they go to the front of the one service's line. There is no setting: a stretch is five minutes, as the specification fixes.

## The fast lane

A second copy of the transcription service, beside the first on the same card, for what must not wait behind a long job: a recording made in the app (which already goes to the front of the line, but the front of the line is still behind whatever is running), and later the pieces of one transcribed while it records, and the Interpreter. It is a copy of the same image with the same model, so what it transcribes is of the same quality; it shares the model folder and has a state folder of its own. It needs about eight gigabytes of the card's memory for the default model.

The installer asks whether to turn it on, no by default. Later:

```bash
./transcribe fast-lane on
```

names the card (the service's own unless the service `.env` says otherwise), makes the state folder, writes the lane's address into `.env`, turns the `fast` Compose profile on, and starts it. `./transcribe fast-lane off` stops it and frees the memory. The Status page has a **Fast lane** card, off, up, or not answering, and `./transcribe check` asks it. A lane that is on but not answering is not waited for: a recording made in the app goes to the one service at the front of its line, and the worker's log says so.

An office with one modest card leaves it off and loses nothing but the waiting.

## The Interpreter

With **Interpreter** on (Features page, under Live recording; greyed until the AI assistant has an engine, since the engine does the translating), the New recording page offers a door to the Session page, where a staff member and a visitor who speaks another language talk turn by turn. Each turn's audio goes to the transcription service the moment the person stops talking, on the fast lane when there is one, and comes back as the words spoken and the language heard; the engine then translates into the other language with a fixed prompt that asks for the translation and nothing else. The page shows both. At Stop the session is a recording like any other made at the desk, with a transcript of one line per turn, each carrying its translation, in the viewer and the Word export.

The **Interpreter** settings page: **Languages offered** (one Whisper code per line, `es` at install; offer a language only once a bilingual reader has read a translated sample and called it usable, since the app cannot judge that itself; the research note `docs/research/interpreter-languages.md` says what each tool covers), **Turn-taking** (Tap, the default: one of the two buttons is always lit for whose turn it is, and a turn ends at a pause; or Hold, hold a button while speaking, for a loud room), **Readback** (each person sees their own words as heard), **Quick phrases** (the staff side's ready lines), and **The notice** (shown at the top, in English and in Spanish for Spanish). Every one takes effect at the next session. The rows: **Live recording started** and **finished** with the style `interpreter`, and **Language settled** (which language, at which turn) when the app heard the language rather than being told it. Never a word of a turn.

What is not yet built from the chapter: the voices (spoken output, the voice per language, speaking speed, when to speak), which come as their own service in a later release. The policy line the chapter names stands: decide before the first session whether the office hands the visitor the recording or the transcript.

## Record now

With **Record now** on (Features page, under Live recording), the Start page offers **Record now**, and the My recordings page opens with **Recorded here**, everything a person recorded from the New recording page, above **Uploaded this session**. The New recording page asks one question, what the person is recording, and offers three styles that preset everything: **Dictation** (one voice, no speaker separation, the recording type Dictation, the memo as the product), **Meeting or interview in the room** (the people to tap, the type Interview, an Interview summary), and **Call or meeting on this computer** (the computer's sound as the far side, the type Meeting, a Meeting summary). A type chosen under More options wins over the style's, so a jail call played on the computer can get the Jail call summary. A recording made there is kept on its own: past sign-out, in no case unless the person adds it to one afterwards, counted against their space. **Write the memo** or **Write the summary** makes one summary with the template the viewer would choose for the recording's type; the shipped **Dictation memo** writes the dictated words out as the document dictated and never summarises, and the shipped **Meeting summary** gives what was decided, who is to do what, questions left open, and what each person said; review their wording on the Templates page. **Send to** gives one colleague that one recording, under "Sent to you" on their page, with a mail saying it is there; a recipient reads, plays, and exports, and cannot send, add, or delete. **Take back** removes it. The rows: **Dictation sent** and **Dictation taken back** (the colleague's username, and whether a file went with the mail; never the content).

**Dictation by email** (Email page, off by default, greyed while mail is not configured) attaches the memo or summary as a Word file, and the recording itself (its playback copy) up to **Largest recording attached** (20 MB by default; most relays refuse mail above 10 to 25 MB), to the Send to mail; a recording over the limit is left out and the mail says so. The row and the share say a file was attached. It is the one message the app sends that carries content, made for the office's legal assistants and decided by the maintainer; the recipient is always a colleague the directory knows, never a typed address, and the row says a file was attached. The **Dictation sent** template sits beside the four Notifications on the Email page.

**Retention.** The office's Retention period applies to each recording made from the tab on its own: days since it was last used (opened by its owner or a recipient, its memo written, sent, taken back). The nightly sweep deletes a dictation that has run out, for good, with the recording's own **Recording deleted** row and the cause `retention`; there is no recycle bin. Inside the warning window the row is amber and the person's nightly digest carries a "Dictations deleting soon" block. This pass runs whatever Folder management says, since dictations do not depend on cases. A dictation added to a case follows the case's clock instead.

## Sharing

With **Sharing** on (Cases page of the settings, under Folder management), a case's owner shares it with named colleagues from the case page: people who have signed in at least once and are active, never local admins, never anyone outside the office. Everyone shared with can edit; a collaborator may not share, rename, transfer or delete the case, and may delete or reprocess only the recordings they added. The audit log writes **Share granted** and **Share revoked** in the Cases category, naming the collaborator's username, with the owner as affected user when you act on somebody else's case. A collaborator opening a recording writes the usual **Recording opened** row with the owner as affected user, so the log's "Access to their material" filter shows collaborators' openings beside Admins'.

You may share and remove shares on any case, under the audit banner as for any other act on somebody else's case. An Admin who is themselves a collaborator on a case is a colleague there: no banner, no Admin access row, and their use counts as the case's activity. Off never deletes a share.

## The Retention policy and the Recycle bin

Once Folder management is on, the app deletes cases by itself, on one rule for the whole office, with a Recycle bin behind it. Nothing in a Workspace is touched by this; a Workspace keeps nothing past its session anyway.

**The clock.** Every case has one: whole days since it was last used. Use is anything its owner or a collaborator does in it, opening it included; looking at the list of cases is not, and neither is your own audited opening of somebody else's case. Days while Folder management is off are left out of every count, so a case with ten days left when you turn it off still has ten days left when you turn it back on.

**The three settings**, on the Cases page and greyed while Folder management is off:

- **Retention period**, 30 days by default (7 to 3650): how long a case may go unused. Shortening it takes effect at the next sweep, and **every case already past the new number goes to the Recycle bin that night**. The bin is the safety net; there is no fresh warning first.
- **Warning before deletion**, 7 days by default (1 to 30, and always shorter than the period; the tray refuses a pair that is not): during a case's last days its row on the Cases page turns amber, reads "Deletes in N days unless used", and carries a **Keep** button. You see the same mark on every case in the office, and the **Expiring** filter shows only those. Your Keep on somebody else's case is audited with them as the affected user, and it does start their clock over: it is the one thing you can do to a case that counts as use.
- **Recycle bin**, 30 days by default (1 to 365): how long a deleted case waits before it is wiped.

**The nightly sweep** runs at half past three. While Folder management is off it does nothing at all and writes nothing. While on, in order: it marks the warning on every case newly inside its window, writing one "retention warning" row each; it moves every case that is due into the Recycle bin, whole, writing "case deleted (cause: retention)" with the counts; it wipes every binned case past the bin period, writing "case permanently deleted" and one "recording deleted" row per recording; and it writes one "retention sweep ran" row with the counts of what it did.

**The Recycle bin page**, reached from the Cases page, shows every deleted case in the office to you, with an owner filter and the "Owner deactivated" mark; an owner sees only their own. **Restore** puts a case back exactly as it was and starts its clock over, and never fails for a full quota, because the case never left the disk. **Delete permanently** wipes one case at once, behind a confirmation that names the counts. **Empty recycle bin** wipes your own binned cases; somebody else's you wipe one at a time, so that a leaver's cases never go in one unconsidered click. A binned case counts against its owner's quota until it is wiped.

**What the bin does not hold.** A person's own Delete of a case or a recording is final and does not come here. Only the clock's deletions do.

**Leavers.** A deactivated person's cases stay under the policy untouched until you act. Reassign hands them to a named colleague without starting the clock over; with no use, they run down and go to the bin like any other, showing under "Owner deactivated" and "Expiring" on your Cases page. Delete data on the Users page wipes a leaver's binned cases along with the rest.

**No exceptions.** Nothing in the app can exempt a case from the clock, and no owner or Admin can set a longer period for one case. The way to keep a case is to use it, or press Keep.

## The AI assistant's engine

The AI assistant, Summary, Chat and Speaker suggestions, talks to a language-model engine through the engine's own API. The app never runs a model itself. Which engine is yours to say, on the panel's **AI assistant** settings page:

- **Engine address**: the engine's base URL, for example `http://gideon-generator:8000/v1`. The defaults are the Local engine's.
- **Model name**: the served name the engine expects, exactly as it lists it.
- **Model display name**: optional; what the AI notice prints instead of the served name.
- **Token**: shown as set or missing and never editable here. It lives in a file on the server, `secrets/llm_api_token`, written by `./transcribe engine`.

**Two kinds of engine.** An office that already runs a vLLM, on this server or elsewhere on the LAN, uses it as a **shared engine**: `./transcribe engine` asks for the Docker network it listens on and its token, and the app's `llm-worker` joins that network. Nothing else in the app touches a network outside its own. An office with no engine can start the **Local engine** shipped with the app, a small model (Qwen3.5-4B by default) running on the transcription service's card within 20 GB of its memory: `./transcribe engine local on` on the server starts it and points these settings at it, and `./transcribe engine local off` stops it, frees the card, clears these two settings and turns the AI assistant off, so the app uses no engine until one is named again. `./transcribe engine` names a shared one: it asks for the address and model name and writes them here, and stops a running Local engine, since the two are never on together. Or leave the assistant off; everything else works without it.

**Test connection**, on the Status page, lists the engine's models with the token and asks it one tiny question. It runs on the worker that can reach the engine, so the answer appears a few seconds later on the same page. Turn the **AI assistant** toggle on only once it succeeds. The Status page's AI assistant line stays live afterwards: green with the model and the time of the last check, or red with "unreachable since". The check runs once a minute, and while it fails the Summary, Chat and Suggest names buttons are disabled everywhere and any call already queued fails at once.

**Turning the features on.** The AI assistant toggle is the master switch; Chat, Summary, Speaker suggestions and **Chat across cases** each have their own. Chat across cases is the Case Chat, the Chat tab on every case page that answers from every transcript in the case; it is the heaviest thing the assistant does, up to fifteen minutes and twenty engine calls for one question on a large case, so it has its own switch, independent of the viewer's Chat toggle, and its own ceiling on the Limits page, **Case chat: most hours of talk per question** (120 hours by default, 6 to 600). A question over the ceiling refuses and tells the person the figures. Its instructions are the **Case chat** template on the Templates page. Off hides a feature everywhere; what people wrote with it is kept, not deleted. Speaker suggestions starts Off: working out who is speaking from the words alone is hard for a small model, and the office that wrote the app found the Local engine did it badly. Turn it on, try it on a few of your own recordings with Accept and Reject, and leave it on only if it earns its place; the shared engine's larger model will do better than the Local one. Since v1.11.0 the app does the finding itself first: **Speaker suggestion method**, greyed while Speaker suggestions is Off, names how. Its one method today is "evidence": the app picks out the self-introductions and forms of address in the transcript, hands them to the engine with the case's people and your Speaker roles, and keeps a name only when the words back it, so the engine offers a role or nothing rather than a guess. Better methods, from more capable models or new pipeline tools, join that list as they are built, and you choose among them here; the Speaker suggestions toggle turns the whole feature off whichever method is chosen. **Let the model think before answering** is slower and sometimes better, doubles every time limit, and gives the thinking its own room on top of the answer's budget. Leave it Off for a small Local engine: a small model thinks at length, and when its thinking uses the whole budget the answer is empty and the page says so. The first request after the engine starts is slow, twenty seconds or so, while the engine warms up; the next ones take a fraction of a second.

**Templates.** The Settings group of the rail has a **Templates** page: the Ground rules every call starts from, the Chat and Speaker suggestions instructions, and the Summary templates. Each is plain text you can edit, with **Reset to default** and a version that rises by one on every save; changes apply at once, outside the tray, and the audit log records the template and its new version, never the words. A Summary template has a name, a one-line description, the **recording types it is for**, and Enabled and Default flags; exactly one of the Enabled is the Default, users choose a template only when two or more are Enabled, and the shipped templates cannot be deleted. The app ships six: Standard summary, and one each for Jail call, Body camera, Interview, Phone call and Hearing, each ticked for its type and Enabled from the first day; read their wording here and edit it in the office's own voice, or Reset to default to put the shipped words back. A recording in a case with a type gets that type's template preselected in the viewer, listed first, with the others still on offer; a recording without a type, or outside a case, gets the Default. **Add template** adds another shape of summary, ticked for whichever types it is for (none means any), and the viewer offers it from that moment. The ticks follow the Recording types list under Cases settings; a type you remove from the list stays on the templates that had it, marked "no longer listed", until you untick it. The same page holds the **starter questions**: two lists, one for a recording's chat and one for a case's, one question per line, that an empty chat offers as one-click chips. They start empty, so nothing is offered until you add some; good ones are the questions your own staff actually ask, in their own words.

**When it fails**, the app says one of six things and records which: not available (the engine cannot be reached), took too long, refused the connection (the token is wrong or missing: "Ask IT" means you), too long a transcript, an answer the app could not read, or a problem. It never records what was asked or answered.

## Backups

Every night at 02:00 the app carries a copy of itself to a folder of its own on the office's backup store: one consistent dump of the database, the recordings in cases with everything about them, the configuration and secrets, and a manifest that says what the copy holds. The copy is encrypted before it leaves the server, deduplicated so an unchanged recording costs nothing after its first night, and kept for thirty nights. Once a month, by itself, the app proves that the newest copy restores by restoring it into a throwaway copy beside the live one and tearing that down again. The Status page's **Backup** line says how the last night and the last drill went; the Installation page shows the target and the schedule.

A backup is for the server dying. Nothing is ever picked out of it for a person: Delete stays final, and the Recycle bin is the only undo. Recordings in a person's own workspace are never copied, since nothing there outlives their sign-in.

**Turning it on** is a line in the server's environment file, `BACKUP_TARGET`, which `./transcribe install` asks for. Empty means backups are off, and the Status page says so in red. It has the form `sftp:<account>@<store>:/<folder>`: an account and a folder on the store made for this app alone, reached over SFTP on port 22, and nothing else. An office without such a store can point it at any machine that speaks SFTP.

### The store's side

On a Synology-class store, in this order:

1. **The account.** An ordinary account, never an administrator: an administrator sees the folder under a volume path, and a path like `/volume1/...` in the target betrays the mistake. Give it SFTP and deny it every other application, so its password opens nothing. It signs in with a key only; since the store cannot turn passwords off, give it a long random password nobody uses, locked and never expiring, saved in the password manager as the account's record. Turn its home service on, since the key lives in its home. Description: "Gideon Transcribe nightly backup, restic over SFTP, key only".
2. **The folder.** A shared folder of the app's own, on a volume with room for thirty nights (the first is the size of the cases folder; later ones only what changed). Recycle bin off, or it hoards every pruned file for good. Encryption off, since the copy is already encrypted, and an encrypted share that is not mounted after a store reboot fails silently. Data integrity on, compression off. A quota, so a runaway fills the folder and fails the backup rather than the volume. Permissions: the account Read/Write, everyone else No access, and an explicit No access on every other shared folder, or the account sees them at its root.
3. **The service.** SFTP on, on port 22. FTP and FTPS off.
4. **The key.** Run `./transcribe install` (or `./transcribe install-backup`) on the server; when it finds no key it makes one and prints the public half. Place it from the store's shell as root, because a file uploaded through the store's file manager belongs to the administrator who uploaded it, and sshd reads the file as the account:

```bash
sudo -i
H=/var/services/homes/<backup account>
mkdir -p "$H/.ssh"
echo '<public key line>' > "$H/.ssh/authorized_keys"
chown <backup account>:users "$H"; chown -R <backup account>:users "$H/.ssh"
chmod 755 "$H"; chmod 700 "$H/.ssh"; chmod 600 "$H/.ssh/authorized_keys"
ls -la "$H" "$H/.ssh"
```

The listing must show the account, not root, as the owner of `.ssh` and `authorized_keys`.

5. **The password manager.** Before the first backup, put three things in the account's record: the private key from `secrets/backup_ssh_key`, the repository password from `secrets/backup_password`, and a note with the target line and the store's host key fingerprint the install printed. Without the password every copy is unreadable, and there is no recovery. Compare the fingerprint with the one the store's administrator knows.
6. **Check it.** `./transcribe check` runs eight tests against the store: the key and the recorded host key are present, the store presents the same host key, key-only sign-in works, the account sees only its folder and `home` at its root, the folder's path is not a volume path, a file can be written and removed, there is no recycle bin in the folder, and a shell is refused. The three failures every new account shows the first time: the key file owned by root after placement, another shared folder visible at the root until it gets an explicit No access, and the recycle bin still on.
7. **The first copy and the first proof**, once the stack is up:

```bash
./transcribe backup
```

```bash
./transcribe restore-drill
```

Both should pass before the app has anything to lose. The store may also keep its own scheduled snapshot of the folder, daily after 02:00, as a second line against the server itself; nothing in the app depends on it.

### What runs, and when

| When | What |
|---|---|
| Nightly at `BACKUP_TIME` (02:00) | `./transcribe backup`: the dump, the manifest, the copy to the store, the keep rule, and the record on the Status page |
| Sundays at `DRILL_TIME` (04:00) | the weekly prune and a check of a tenth of the data |
| The first Sunday of the month, thirty minutes later | `./transcribe restore-drill` |

They are host timers, so they fire when the stack is down. `systemctl list-timers 'transcribe-*'` shows them. Changing the times means editing `.env` and running `./transcribe install-timers`. `./transcribe snapshots` lists what the store holds.

**When a backup fails**, the Status line turns red and names the step and the reason: `disk_full` (the server's data folder is under its floor), `dump_failed`, `manifest_failed`, `target_unreachable` (the store, the key or the host key), `snapshot_failed` (a full folder on the store ends here; raise its quota), `prune_failed` or `check_failed` (the weekly slot). The audit log holds a **Backup failed** row with the same words, and a **Backup overdue** row once a day while there has been no successful copy for 26 hours. When the Email notifications chapter is built, the Operator address in `OPERATOR_EMAIL` is told as well.

### Restoring: the runbook

**A restore takes the app back to 02:00 of the Snapshot's day, and everything done after that is gone.** Every recording uploaded since, every correction, every case chat. Workspaces are discarded and everybody is signed out. Do it when the server has died or the data is beyond repair, not to undo a mistake.

**On the same server**, nothing to do first. **On a fresh server**, follow the install guide to the end of `./transcribe install`, with two things from the password manager placed first: the private key at `secrets/backup_ssh_key` before the install runs, so it uses that key and prints nothing to paste; and the repository password at `secrets/backup_password` after it. The install finds the existing repository on the store and uses it.

Then:

```bash
./transcribe snapshots
```

lists the nights. Pick one, or `latest`:

```bash
./transcribe restore latest
```

It reads the Snapshot's manifest first and refuses unless the checkout is at the release the Snapshot was taken with (it says which tag to check out), and refuses while a job is running. It says what it is about to do and waits for the word RESTORE. Then it stops the stack, puts back the configuration (keeping the two backup secrets already in place), the cases folder in full, and the dump; recreates the database and loads it; starts the stack; and runs the after-restore step, which signs everybody out, discards every workspace, fails any job that was in flight at the Snapshot with the reason `restored` and a Retry, records the outage as days that count against no case, checks the audit log's chain, and prints the report. The **Restore completed** row in the audit log carries the same figures.

Afterwards, two commands the restore names: `docker compose run --rm whisperx pull`, because the model cache is not backed up, and `./transcribe check`. Then upgrade to the current release if the Snapshot was older.

### The drill

The monthly drill restores the newest Snapshot into a folder beside the app data folder, brings up a throwaway copy of the database and the app on a network of their own (no web server, no GPU, no transcription, no sign-in, no mail), loads the dump, and checks it against the manifest: a row count per table, a checksum per file, every recording in a case has its files, the audit chain unbroken. It records **Restore drill ran**, pass or fail with the failing step, in the live app's audit log and on the Status page, and tears everything down whatever the result. It needs free space for the Snapshot plus the floor, and refuses when there is not. Nobody is made to rehearse a restore by hand: the drill is the rehearsal.

## Email

With a relay named in `.env` (`./transcribe install` or `./transcribe install-mail` asks for it), the app sends plain-text mail: four kinds of Notification to people, and Operator mail to one IT mailbox. Mail announces and never acts: nothing waits for a message, deletion least of all, and the pages are the record. A message says what an audit row may (names of cases and recordings, counts, dates, display names, one link) and never content.

**The Email page** of the settings has two switches and four wordings. **Email notifications** is the master switch for mail to people; Operator mail ignores it and obeys `.env` alone. **Batch finished emails** allows the tick on the Upload page. The four **templates** (the Retention digest, a case shared with you, a case handed to you, a batch finished) are a subject and a body each, with a fixed set of placeholders per kind, saved through the tray like any setting so the "Setting changed" row keeps the old and new text; Apply refuses a placeholder the kind does not have, and **Reset to default** puts the default back in the field for the tray. The blocks the app builds (the list of cases, the shared cases, the failed recordings) and the footer are not editable. All of it is greyed while mail is not configured; the values are kept. Under the settings, **Send a test message** mails you (or the Operator address when you have no email address) at once and shows the relay's reply on the page, writing a "Test email sent" row.

**Who gets what.** Every night after the retention sweep, one **retention digest** per person with a case in its last days, their own under "Deleting soon" and the ones shared with them under "Shared with you"; **a case shared with you** at once when a share is made (removing one sends nothing); **a case handed to you** at once on Transfer or Reassign, with the days left; **your batch has finished** when the last recording in a batch has ended, for a person who ticked the box, once. Deactivated and Blocked people are never mailed. Every message is one background job on the worker, tried three times within thirty minutes (at once, after five minutes, after twenty-five) and then dropped with an **Email failed** row naming the reason (`smtp_unreachable`, `smtp_refused`, `smtp_auth_failed`) and the tries. Nothing waited for it: the digest comes again the next night, and the other kinds are not resent because the pages already show what they said.

**The Operator address** (`OPERATOR_EMAIL`) gets the app's own mail and is the Reply-To on every message: each night, the cases whose owner has left (deactivated or blocked) that are deleting soon, so you can Reassign or Keep them from the Cases page's "Owner deactivated" and "Expiring" filters; the backup reports (a snapshot failed, no successful snapshot in 26 hours, a drill failed or overdue, a restore completed); and the test message from `./transcribe check`. Admins' own mailboxes are never used for the app's mail.

**The email address** is the directory's `mail` value, read at every sign-in and by the directory check, and never typed for a directory account: a missing or wrong address is fixed in the directory, and the next sign-in or "Check directory now" brings it in, writing an "Email address updated" row. The Users page shows an **Email** column, marks a row **No email address**, and has a filter for those; the Status page counts them. The one typed address is a Local admin's, optional, set when the account is made or on its row; `transcribe-admin` has none by default.

**The Status page's Email line** reads "not configured" while `SMTP_HOST` is empty, otherwise the last message sent and the last failure; it turns red while the most recent try failed. **The Installation page** shows the seven mail keys read-only, with the relay's password shown as set or missing. **`./transcribe check`** sends one test message to the Operator address and reports the relay's reply, which proves that the relay takes mail from the server and lets the sender through, and counts the Sign-in group's members without a `mail` value as a warning.

**The seven keys**, in `.env`: `SMTP_HOST` (empty means no mail at all), `SMTP_PORT` (25), `SMTP_STARTTLS` (`auto` upgrades to TLS when the relay offers it and requires it when a password is set; `always`; `never`), `SMTP_USER` and `SMTP_PASSWORD_FILE` (only when the relay wants a sign-in; the password lives in `secrets/smtp_password`, written by the install), `MAIL_FROM` (the sender, shown as "Gideon Transcribe <address>"), and `OPERATOR_EMAIL`. The worker reaches the relay over the LAN on `SMTP_PORT`; the drill project never sends mail.

## The Installation page

What this server is, read from its environment and shown so that an Admin can check an installation without opening a terminal: the address and port, the bind address, the client networks allowed in, the time zone, the app data folder, the WhisperX service's address and the card it reserved, the engine network and profile, the media worker's thread and job limits, and the backup target, schedule, keep rule and last run.

**Secrets** are shown as set or missing, never as values. **How this office gets releases** names the repository and says, in one sentence, that the app never checks for updates: a person subscribes to the repository's Releases on GitHub and runs the upgrade by hand.

## On the server

Everything an Admin does on the server itself is one script, `./transcribe`, run from the install folder. Run it with no arguments to see its subcommands. The ones for day to day:

```bash
./transcribe status
./transcribe check
./transcribe logs app
./transcribe backup-db
```

`status` says what is running. `check` runs every smoke check and prints a plain report. `logs` follows one service's log, or all of them with no name. `backup-db` takes a dump of the database into the backup folder under the app data folder.

### A background job that has stopped moving

Media work, polling, and the nightly sweeps run as background jobs on the app's own queue. A worker that dies holding a job leaves it marked as being done, and the app puts those back in line on its own every ten minutes. For the times that is not enough, when something is wedged and somebody is waiting:

```bash
docker compose run --rm app stuck_jobs
```

That lists what is being worked on and how long each has been at it. A job that has been running for over an hour is marked stuck, and

```bash
docker compose run --rm app stuck_jobs --release
```

puts the stuck ones back in the line for a worker to pick up. Add `--queue media`, `--queue default`, or `--queue llm` to look at one queue. Every release is written to the audit log.

This is for the app's own jobs. A transcription that has stopped is the WhisperX service's, and it appears on the Queue page with a reason and a Retry.

### The certificate

The app's certificate comes from the office's own certificate authority and lasts as long as that authority issues for; a Windows Web Server template issues for two years. `./transcribe check` prints the date it is good until, and the same line goes amber when that is within a month.

To renew it, make a new request exactly as the install guide describes, put the new `cert.pem` and `key.pem` in `tls/` in the install folder, and restart the web server:

```bash
docker compose restart caddy
```

Nothing else restarts and nobody is signed out.

**A note on DNS.** The directory's zone lives on the domain controllers, and a caching resolver in front of them keeps a "name does not exist" answer for the zone's negative TTL, usually an hour. So when the app's name is first created, create the record before anyone tries the name, or flush that resolver's cache; otherwise the name goes on failing for an hour after it exists.

### Upgrading and rolling back

Upgrades come as Releases on GitHub, and the app never checks for them. Subscribe to the repository's Releases (Watch, Custom, Releases) to hear about one. Each Release's notes open with two fixed lines, whether the models changed and whether the database migrates, and

```bash
./transcribe upgrade <tag>
```

reads them out before it does anything. When it pulls the images rather than building them, it checks that what arrived is what the Release was built as, and stops if not. The install guide has the whole procedure, and the roll-back. **Nothing is ever pushed from a workstation to the server or copied over the install folder**: code reaches the server only through that command.
