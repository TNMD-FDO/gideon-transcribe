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
- **Cases**: the **Folder management** toggle that turns Cases on for the whole office, and the list of **Recording types** a person may label a recording with. Off hides every case from everyone, Admins included, and deletes nothing; on brings them all back as they were.

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

The log records what happened, who did it, and to whose material: sign-ins and sign-outs, uploads, downloads, corrections, deletions, every settings change with its note, every action on the Users page, every cancelled job, and every time an Admin opens somebody else's recordings.

It never records any of these, whatever the page and whoever is signed in: transcript text, either side of a correction, chat questions or answers, summaries, vocabulary, search terms, file contents, passwords, tokens, speaker names, clip titles, or clip notes. A recording's original file name is kept, because it is the only way to recognise a recording after it has been discarded.

The Audit log page shows the rows newest first and filters them by date, person, category, and outcome. Each row names the actor, what happened, whether it succeeded, the affected person where that is not the actor, the object, and the client it came from.

**Retention.** Rows older than the **Audit log retention** setting are removed by a nightly sweep. Three months is the default. The record of an Admin opening somebody's recordings is a row like any other, so the retention period is also how long that record lasts: an office that wants a longer memory of Admin access sets a longer retention.

**Integrity.** Every row carries a hash of itself and of the row before it, so a row that is changed or removed afterwards breaks the chain. **Integrity check** on the Status page walks the chain and says whether it holds. Rows are written through a database role that can only insert, and removed only by the sweep's own role; the app's ordinary role can do neither.

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
