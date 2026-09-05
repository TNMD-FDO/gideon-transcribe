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

- **Features**: whether speaker separation, translation, and clips are offered at all. Off hides the feature everywhere; nothing already made is deleted.
- **Limits**: the largest file, the longest recording, the longest clip, the most files in one batch, the default quota per user, and how much free disk the server must keep. Uploading pauses when free disk falls under that last figure, and the Upload page says so.
- **Transcription defaults**: the model, whether speaker separation and translation are ticked by default, whether a mixed-language recording is translated without being asked, the office vocabulary that is added to every user's, and the preparation profile.
- **AI assistant**: the assistant and its parts, and the engine it talks to. An installation with no engine leaves the assistant off and everything else works.
- **Notices**: the four fixed texts. The **Transcription notice** goes on every export. The **Translation notice** goes on every export of a translated transcript. The **AI notice** goes with anything the assistant writes. The **Sign-in page notice** is the line under the sign-in form: an authorised-use statement, or where to ring for help. Empty hides it.
- **Sign-in and directory**: the idle timeout, eight hours by default, after which a login session ends and the person's recordings go; and the hour of the nightly directory check. The directory's own facts are shown read-only here, because they are set at install and not in the panel.
- **Audit log**: how many months of audit rows are kept, three by default. See the audit log below for what that means.
- **Appearance**: the **Office name**, shown under the logo on the sign-in page and on the cover of every Word export, and the **Logo on Word exports** toggle. The same page holds the **office logo** itself, uploaded and removed at once rather than through the tray: a PNG or JPEG up to 2 MB, a wide mark reads best. It appears large on the sign-in page as soon as it is uploaded, and at the head of every export's cover once the toggle is on. It is kept with the app's own data, so a backup carries it, and it never leaves the server.
- **Cases**: the **Folder management** toggle that turns Cases on for the whole office, the list of **Recording types** a person may label a recording with, and the list of **Speaker roles** a person in a case may be given (Defendant, Witness, Officer and the rest; one per line, a removed role stays on the people that hold it). Off hides every case from everyone, Admins included, and deletes nothing; on brings them all back as they were. Beside them, greyed while Folder management is off, the Retention policy's three numbers: the **Retention period**, thirty days by default; the **Warning before deletion**, seven days and always shorter than the period; and the **Recycle bin**, thirty days. See the Retention policy below.

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
- **Reassign** moves a person's recordings to somebody else, for when someone has left. **Delete data** removes them.

A person who has left the sign-in group is shown as **Deactivated** after the next directory check and cannot sign in. Putting them back in the group and running **Check directory now** reactivates them.

**Local admins** are created at the foot of the page. A Local admin has a password kept in the app, which **Change password** sets and which never goes anywhere near the directory. Keep one, for the day the directory is down, and give it a long password.

## The audit log

On a wide monitor the filters sit in a pane on the left and stay put while you scroll the rows; on a laptop they sit above the table.

The log records what happened, who did it, and to whose material: sign-ins and sign-outs, uploads, downloads, corrections, deletions, every settings change with its note, every action on the Users page, every cancelled job, and every time an Admin opens somebody else's recordings.

It never records any of these, whatever the page and whoever is signed in: transcript text, either side of a correction, chat questions or answers, summaries, vocabulary, search terms, file contents, passwords, tokens, speaker names, clip titles, or clip notes. A recording's original file name is kept, because it is the only way to recognise a recording after it has been discarded.

The Audit log page shows the rows newest first and filters them by date, person, category, and outcome. Each row names the actor, what happened, whether it succeeded, the affected person where that is not the actor, the object, and the client it came from.

**Retention.** Rows older than the **Audit log retention** setting are removed by a nightly sweep. Three months is the default. The record of an Admin opening somebody's recordings is a row like any other, so the retention period is also how long that record lasts: an office that wants a longer memory of Admin access sets a longer retention.

**Integrity.** Every row carries a hash of itself and of the row before it, so a row that is changed or removed afterwards breaks the chain. **Integrity check** on the Status page walks the chain and says whether it holds. Rows are written through a database role that can only insert, and removed only by the sweep's own role; the app's ordinary role can do neither.

## The Retention policy and the Recycle bin

Once Folder management is on, the app deletes cases by itself, on one rule for the whole office, with a Recycle bin behind it. Nothing in a Workspace is touched by this; a Workspace keeps nothing past its session anyway.

**The clock.** Every case has one: whole days since it was last used. Use is anything its owner does in it, opening it included; looking at the list of cases is not, and neither is your own audited opening of somebody else's case. Days while Folder management is off are left out of every count, so a case with ten days left when you turn it off still has ten days left when you turn it back on.

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

**Templates.** The Settings group of the rail has a **Templates** page: the Ground rules every call starts from, the Chat and Speaker suggestions instructions, and the Summary templates. Each is plain text you can edit, with **Reset to default** and a version that rises by one on every save; changes apply at once, outside the tray, and the audit log records the template and its new version, never the words. A Summary template has a name, a one-line description, and Enabled and Default flags; exactly one of the Enabled is the Default, users choose a template only when two or more are Enabled, and the built-in Standard summary cannot be deleted. **Add template** adds another shape of summary. The same page holds the **starter questions**: two lists, one for a recording's chat and one for a case's, one question per line, that an empty chat offers as one-click chips. They start empty, so nothing is offered until you add some; good ones are the questions your own staff actually ask, in their own words.

**When it fails**, the app says one of six things and records which: not available (the engine cannot be reached), took too long, refused the connection (the token is wrong or missing: "Ask IT" means you), too long a transcript, an answer the app could not read, or a problem. It never records what was asked or answered.

## The Installation page

What this server is, read from its environment and shown so that an Admin can check an installation without opening a terminal: the address and port, the bind address, the client networks allowed in, the time zone, the app data folder, the WhisperX service's address and the card it reserved, the engine network and profile, and the media worker's thread and job limits.

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
