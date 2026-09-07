# The box ledger

**Rules version:** 2026-09-06.4 (sections 1 to 11)
**Copies:** `docs/box-ledger.md` in `TNMD-FDO/GIDEON` and `docs/box-ledger.md` in `TNMD-FDO/gideon-transcribe`. Sections 1 to 11 are one text in both; section 12 is a log with one subsection per project, each written only by that project. Nobody writes into the other project's repository: each project fetches the other's copy and merges it (§11).

Two projects run on one server and in one GitHub organisation: GIDEON, the platform and legal-AI product, and Gideon Transcribe, the transcription app. Each has its own repository, install home, release rule, and operator. GIDEON is the authoritative service on the server, the one it is provisioned and sized for; Gideon Transcribe is a secondary service, for transcription, that fits into the room GIDEON's allocation leaves. They share the hardware, the Docker daemon, the host firewall, the nightly hours, and the organisation's pool of hosted-runner minutes. This ledger records who owns each shared thing, what each project may do with it, the events one project must announce to the other, and, in its log, what each project changed and what it recommends to the other. It states keys, defaults, paths, and units. It never states an office value: no hostname, address, network range, account name, or storage target appears here, because both repositories are written as if public.

The facts below were read from the two repositories and from the running server on the ledger's date. A number marked *observed* is what the server showed that day, not a commitment.

## 1. The two projects

| | GIDEON | Gideon Transcribe |
|---|---|---|
| Repository | `TNMD-FDO/GIDEON` | `TNMD-FDO/gideon-transcribe` |
| What it is | the platform (host provisioning, rendering, apply, backups, observability) and the legal-AI branches | a Django app, a pinned WhisperX service, and workers for transcription, translation, and diarisation |
| Standing on the server | the authoritative service: the host is provisioned, sized, and scheduled for it, and its allocation comes first | a secondary service for transcription, fitted into what GIDEON's allocation leaves free |
| Install home | `/opt/gideon` when a release is installed; the development checkout under the operator's home today | `/opt/gideon-transcribe` |
| Operator command | `python3 -m gideon …` | `./transcribe …` |
| Compose project | `gideon` (plus `gideon-drill` during a drill and `gideon-ci-contract` during CI) | `transcribe` (plus a drill project under its own directory) |
| Release rule | code reaches the server only at a tag, through `upgrade` | the same rule, suspended for this one server until its `v1.0.0` (its ADR 0007) |
| Where its agents learn of this ledger | `CLAUDE.md` (the shared server paragraph), the architecture map §17, the plan template's Documentation Impact, the release skill's `box-ledger-sync` block | `CLAUDE.md` (the shared server section) and its ADR 0003, which names the shared engine as the one coupling |

**Precedence.** GIDEON is the authoritative service on this server and Gideon Transcribe a secondary one. Where the two need the same thing, a card's memory, a night's hour, the hosted-minute pool, a port, a directory, the disk, GIDEON's need is met first and Transcribe fits into what remains. GIDEON's specification, decision records, and locks are the authority for the host, and this ledger's tables are read in that light: a reserve GIDEON's plan writes for Transcribe is what Transcribe may count on, and anything beyond it is on loan until GIDEON needs it. Precedence is not licence to break Transcribe without notice: the announce-before list (§8) stands, taking back a loan is a rules change here first with the notice a maintenance window gets, and a secondary service that is running is left running until its stop or its replacement is agreed.

**Direction and request.** The same precedence runs through the log (§12). A line GIDEON addresses to Transcribe about a shared thing, or about a design change GIDEON has made, is a direction: Transcribe's agents fit their next change to it and answer by number with what changed and when, or, when it cannot be followed, with the reason, within the notice a maintenance window gets, so the two operators can settle it. A line Transcribe addresses to GIDEON is a request that GIDEON weighs and answers. Transcribe's own product decisions stay its own where they touch nothing shared.

## 2. Who owns the host

GIDEON's `host provision` owns the operating-system layer. Its steps, by name, and what each owns:

| Step | Owns |
|---|---|
| `firewall` | ufw and its allow-list from the site file's LAN networks, and the `DOCKER-USER` block that makes that list true for Docker-published ports (§4) |
| `nvidia-driver`, `nvidia-toolkit` | the driver branch and version from `host.lock`, the container toolkit, CDI device naming |
| `docker-engine` | Docker Engine and Compose at the lock's minimums, `/etc/docker/daemon.json` (data root, journald logging) |
| `disk-layout` | the `/data` volume and its managed directories (§6) |
| `unattended-upgrades` | Ubuntu's security-only unattended upgrades, no automatic reboot |
| `timezone`, `time-sync`, `wait-online` | the office time zone and clock |
| `service-user`, `csa-accounts`, `secrets-dirs`, `backup-keypair`, `age-recipient` | GIDEON's service user, the administrators' accounts and SSH posture, `/etc/gideon` |
| `egress-proxy` | the proxy setting applied to apt, Docker pulls, and GIDEON's own egress, from the site file's `egress_proxy` (empty on this server, *observed*) |
| `kvm`, `platform`, `host-tools` | libvirt for the acceptance VM, the platform packages, the tools the runbooks need |
| `registry` | the `gideon-registry` service, the release registry on port 5000 |
| `gh-runner` | the organisation's self-hosted runner (§9) |

Transcribe consumes that layer and owns nothing in it. It owns its install home, its `.env`, its `secrets/` and `tls/` directories, its data directory, its systemd units, its Compose project and networks, and its images.

**Rules**

- A change to the driver, the container toolkit, Docker, the kernel, the firewall, the time zone, or the disk layout goes through GIDEON's lock and `host provision`, in an announced maintenance window, because it restarts or reboots every container on the server, Transcribe's included.
- Transcribe never edits a file provision owns. If it needs one changed, that is a GIDEON ticket, and this ledger's log carries the ask.
- GIDEON's provision touches only the paths it names. A directory or unit that is not in its registry is not its to create, own, or remove.

## 3. The GPUs

Two cards, each about 96 GB. Both projects reserve a card through the container toolkit's CDI names, by GPU UUID, so a container sees only the card it was given.

| | GPU 0 | GPU 1 |
|---|---|---|
| GIDEON today | the generator, one vLLM at memory fraction 0.92, about 88 GB (*observed*) | nothing yet |
| GIDEON's plan (spec §5) | the generator, the whole card | its supporting models from the corpus slice (tag `v0.4.0`): embed 24 GB, rerank-1 6 GB, rerank-2 16 GB, a bulk-embed profile of 24 GB off by default, and a **20 GB reserve written for Transcribe's speech recognition** |
| Transcribe today | no memory; may become a client of GIDEON's engine over Docker (its `compose.shared-engine.yaml`, keys `LLM_NETWORK` and `LLM_API_TOKEN_FILE`) | its WhisperX service, about 0.5 GB idle and up to about 20 GB while transcribing; and its own local vLLM under the `llm` Compose profile at fraction `LLM_LOCAL_GPU_FRACTION`, 0.21, about 21 GB (*observed*, profile on) |

**The collision ahead.** GIDEON's spec reserves 20 GB of GPU 1 for Transcribe's speech recognition and nothing for a second engine. With Transcribe's local vLLM on, Transcribe holds about 41 GB of GPU 1 at peak, and GIDEON's planned 66 GB plus that is more than the card. Nothing breaks today because GIDEON's supporting models are not running yet. The decision is open item 1 (§10) and must be made before GIDEON's `v0.4.0`. The two shapes: Transcribe turns its local engine off (`./transcribe engine local off`) and uses GIDEON's engine on GPU 0 as a client, which frees 21 GB and costs nothing on GPU 0; or GIDEON's reserve rises to 41 GB and its bulk-embed profile stays off, which is a spec change on GIDEON's side. Under the precedence rule (§1) the default is the first shape: the 20 GB reserve is what Transcribe may count on, the local engine's 21 GB is on loan until GIDEON's supporting models need the card, and GIDEON raises the reserve only if it chooses to.

**Rules**

- Each project's memory on each card is its line in the table above. Taking more, or taking memory on a card the table gives the other project, is a ledger change first and a maintenance-window change second.
- A memory fraction is a release constant on GIDEON's side and an `.env` key on Transcribe's. Neither is changed on the server by hand.
- GIDEON's quiet window (§7) binds bulk load on the engine on GPU 0. If Transcribe becomes a client of that engine, its interactive use is fine at any hour, and any batch of its own over that engine takes an hour in §7.

## 4. Network: ports, firewall, names

| Port | Owner | Bound to | Who may reach it | What enforces that |
|---|---|---|---|---|
| 443 | GIDEON's Caddy | every interface | the office's LAN networks | the `DOCKER-USER` block from the site file's LAN networks |
| 5000 | GIDEON's release registry | loopback and libvirt's default bridge | the server itself and the acceptance VM | the same block |
| 9090 | GIDEON's Prometheus | loopback | the server itself | the bind address |
| 18081 | GIDEON's CI contract test, while a CI job runs | loopback | the job | the bind address |
| `HTTPS_PORT`, 8443 by default | Transcribe's Caddy | the server's LAN address (`BIND_ADDRESS`) | the office's LAN networks | Caddy's own client-address allow-list, and the bind address |
| 22 | sshd | every interface | the LAN networks | ufw's allow-list |

Every other service of both stacks (databases, exporters, WhisperX, both vLLMs, the upload server) publishes no port.

Docker networks: `gideon_gideon` is GIDEON's project network and carries its engine. `transcribe` and `whisperx` are Transcribe's. A container joins the other project's network only through the shared-engine coupling of §3, and that join is announced.

Hostnames and certificates: each project serves its own hostname with its own certificate from the office authority. GIDEON renews through `tls reload`; Transcribe through its `tls/` directory and `./transcribe`. Neither touches the other's.

**Rules**

- A new published port is a row in this table before it exists on the server.
- A published port binds to loopback or to the LAN address, never to every interface, with 443 the one standing exception.
- **Open item 2 (§10):** GIDEON's `DOCKER-USER` block drops off-LAN traffic only for ports 443 and 5000. Docker's own chains run before ufw's input rules, so ufw's allow-list does not protect port 8443. Transcribe's Caddy allow-list and LAN bind are its whole defence until GIDEON's block covers every Docker-published port.

## 5. Docker: one daemon

One rootful daemon, provisioned by GIDEON: data root `/var/lib/docker`, journald logging, Docker Engine 29 with the containerd image store (storage driver `overlayfs`). Both projects' containers, images, networks, volumes, and build cache share it.

| | GIDEON | Transcribe |
|---|---|---|
| Containers (*observed*) | caddy, open-webui, gideon-generator, postgres (with pgBackRest inside), prometheus, grafana, dcgm-exporter, cadvisor, node-exporter, blackbox-exporter, postgres-exporter; and `gideon-registry` under systemd | caddy, postgres, app, tusd, whisperx, worker, media-worker, llm-worker, vllm (profile `llm`), backup (profile `backup`) |
| Images | pinned by digest in `images.lock`, mirrored into the release registry on the server by `registry mirror`; one image built on the server by `tools.imagebuild` | `ghcr.io/tnmd-fdo/gideon-transcribe-app` and `ghcr.io/tnmd-fdo/gideon-transcribe-whisperx` at `RELEASE_TAG`, pulled from the organisation's package registry; the WhisperX image is about 13.8 GB per tag |
| Networks | `gideon_gideon` | `transcribe`, `whisperx` |
| Throwaway projects | `gideon-drill` (backup drill), `gideon-ci-contract` (CI), the acceptance VM under libvirt | its restore drill, under `/data/transcribe-drill` |

**Rules**

- Nobody runs `docker system prune`, `docker image prune -a`, `docker builder prune`, `docker volume prune`, or `docker network prune` bare. Each project removes only its own: by its Compose project (`docker compose … down`), by its own image names, or by the `com.docker.compose.project` label.
- Old images are the owning project's to remove. Transcribe keeps its current tag and one before it on the server; every earlier WhisperX tag is about 13.8 GB of the root filesystem (§6). GIDEON's registry mirror keeps only what `images.lock` names.
- A build on the server writes to the shared build cache. The project that built it prunes it when the build is done, by its own builder or filter, never the whole cache.
- Compose project names, network names, and volume names stay disjoint: GIDEON's start with `gideon`, Transcribe's with `transcribe` or `whisperx`.

## 6. Disks and directories

| Mount | Size | Used (*observed*) | Owner | Holds |
|---|---|---|---|---|
| `/` | 196 GB | 109 GB, of which 95 GB is `/var/lib/containerd` | the OS | the operating system, both projects' images and the build cache (see open item 3), the runner, the checkouts |
| `/var/lib/docker` | 590 GB, its own logical volume | under 1 GB | GIDEON's `docker-engine` step | the daemon's data root, which the containerd image store bypasses for images |
| `/data` | 7.7 TB, its own volume group | 269 GB | GIDEON's `disk-layout` step | the directories below |

Under `/data`:

| Directory | Owner | Holds |
|---|---|---|
| `fast`, `bulk`, `work` | GIDEON | the corpus, indexes, and working space of the later slices |
| `models` | GIDEON | the weights tree, written only by `models pull` and apply |
| `registry` | GIDEON | the release registry's storage |
| `backup-staging`, `drill` | GIDEON | its backup sets and the drill project's data |
| `observability` | GIDEON | Prometheus and Grafana state |
| `transcribe` | Transcribe | its data directory, the value of `APP_DATA_DIR`: recordings, the database, its models |
| `transcribe-drill` | Transcribe | its restore drill |

**Rules**

- Transcribe's directories under `/data` keep names outside GIDEON's managed list, and GIDEON's `disk-layout` step creates, owns, and re-owns only the names it lists.
- Recordings are large. Transcribe's retention of its own data is its own policy, but a `/data` fill takes GIDEON's backups and models down with it, so the weekly check (§11) reads `/data`.
- **Open item 3 (§10):** the containerd image store puts every image and the build cache on the root filesystem, not on the 590 GB volume sized for Docker. Six WhisperX tags and a 42 GB build cache were on the root filesystem on the ledger's date. Until GIDEON's `docker-engine` step points the image store at the volume, both projects keep the root filesystem above 40 GB free, and Transcribe keeps at most two WhisperX tags on the server.

## 7. Scheduled work and the hours

All times are the office time zone, America/Chicago, which GIDEON's `timezone` step sets and both projects' timers state.

| When | Unit | Owner | What | Load |
|---|---|---|---|---|
| daily 01:00 | `gideon-backup.timer` | GIDEON | a backup set, then the push to the backup target | disk and network |
| daily 02:00 | `transcribe-backup.timer` | Transcribe | its daily backup to its target | disk and network |
| daily 03:00 | `gideon-users-reconcile.timer` | GIDEON | directory membership to frontend roles | light |
| Sunday 04:00 | `transcribe-backup-weekly.timer` | Transcribe | its weekly backup | disk and network |
| first Saturday 04:00 | `gideon-backup-drill.timer` | GIDEON | a throwaway restore of the latest set (the `drill_interval` site key) | CPU, disk, a second frontend for minutes |
| first Sunday 04:30 | `transcribe-backup-drill.timer` | Transcribe | its restore drill | CPU and disk |
| monthly 04:00 | `gideon-backup-verify.timer` | GIDEON | the whole backup repository verified | disk |
| every Monday 06:17 | GIDEON's pin watch, on GitHub's runners | GIDEON | pull requests that move pins | none on the server |
| daily | unattended upgrades | the OS, through GIDEON | security packages only, no reboot | light |

GIDEON's timers take their calendars from release constants in its render module and the `drill_interval` site key. Transcribe's take theirs from the answers its installer wrote into its units.

**GIDEON's quiet window** is 19:00 to 06:00 on weeknights and Friday 19:00 to Monday 06:00. Anything that sends bulk requests to the engine on GPU 0 runs only then: its evaluation runs, the turn harness over a whole seed, and later the bulk embed. **Maintenance windows** are announced at least one working day ahead and default to weekend nights: engine swaps, driver or Docker changes, every upgrade on a user-facing tag, of either project.

**Rules**

- A new timer, or a moved one, takes a row here with a free hour before it lands.
- A batch that loads a GPU or the disks for more than a few minutes runs in the quiet window and claims its hour in this table for that night, so two batches never share it.
- The two backup targets, if they are the same device, keep separate accounts and paths. The staggered hours above are the agreement on its load.

## 8. Announce before

An announcement is a message to the other operator before the event, with the hour, and a word after it, and a line in this ledger's log (§12) when the event changes a table above. For a maintenance window it is at least one working day ahead.

**GIDEON announces**

- `host provision` on a live server, whatever the reason: it may change the firewall, the driver, Docker, or reboot.
- `apply` when `images.lock` or the engine's configuration moved: the engine restarts and, if Transcribe is its client, Transcribe's assistant sees an outage; `apply` may also recreate `gideon_gideon`, which drops a client that joined it.
- Any change to the engine's API key: a client of the engine holds a copy.
- `upgrade`, `restore`, and `upgrade --rollback`: the whole GIDEON stack goes down and up.
- The acceptance run at a minor tag: about 45 minutes, an 8-vCPU, 16 GB VM, the registry busy, and the runner busy.
- `models pull` for a new profile: tens of gigabytes into `/data/models`.
- A quiet-window batch on the engine.
- The `v0.4.0` slice, which brings the supporting models onto GPU 1 (§3).

**Transcribe announces**

- `./transcribe engine local on` or `off`: 21 GB of GPU 1 taken or freed.
- Joining or leaving GIDEON's engine network, and the token hand-off that comes with it.
- A long transcription batch, or any run that holds WhisperX's 20 GB for hours.
- A release that changes its published port, bind address, or a Compose network.
- Its restore drill outside its timer's hour, and any upgrade on this server.
- A build on the server, and the prune that follows it.
- A change to its workflow triggers that moves hosted-minute load, since the pool is shared (§9).

## 9. The GitHub organisation

| Resource | Owner | The agreement |
|---|---|---|
| The organisation's plan | the organisation | Free. 2,000 GitHub-hosted Linux minutes a month, shared by every repository in the organisation; storage for artifacts likewise |
| Hosted minutes | both | GIDEON's hosted use is its `checks` job on every push and pull request and the weekly pin watch, about 20 minutes on a busy day. Transcribe's CI on every push and its image builds on every tag used about 1,750 minutes in the first six days of September 2026. The budget: GIDEON up to 400 a month, Transcribe the rest, and an Actions budget with an alert at 75 % set in the organisation's billing settings so a month never ends with hosted jobs refused |
| The self-hosted runner | GIDEON's `gh-runner` step | one runner, registered to the organisation, labels `self-hosted, linux, x64, gpu, dl385-gen11`, user `gh-runner` with Docker access, home `/opt/gh-runner`, work folder `/opt/gh-runner/_work`, updates disabled and moved only through GIDEON's `host.lock`. One sudoers line lets it run GIDEON's acceptance harness and nothing else |
| Who may use the runner | GIDEON | GIDEON's image mirror, frontend contract, and acceptance jobs. Transcribe's own repository rule forbids any self-hosted runner, the office's included (its `CLAUDE.md`), so the runner is GIDEON's alone. That rule changes in this ledger first, if it ever does |
| Packages (`ghcr.io/tnmd-fdo/…`) | Transcribe | its two images. GIDEON publishes no package; its release registry is on the server |
| Repository secrets | each repository | GIDEON's pin-watch App credentials live in its repository. Transcribe's build-time tokens live in its. Nothing is an organisation secret |
| Tags | each repository | both use `v*`. GIDEON's acceptance workflow runs on its own `v*.*.0` tags only |
| Repositories | the organisation | `GIDEON`, `gideon-transcribe`, `gideon-transcribe-planning`, `GIDEON-sites` |

**Rules for the runner**

- A job on the runner runs only for `push` events on `main` and for tags. Never for `pull_request` events: the runner has Docker access, which is root on the server, so it executes only code a member of the organisation has already merged or tagged.
- A job on the runner leaves nothing on the server outside the runner's work folder, and reads no secret of the other project.
- A workflow that builds on the runner prunes its own build cache in the same job (§5).

**Rules for hosted minutes**

- CI runs on pushes to `main` and on pull requests, not on every tag, and ignores documentation-only paths where a project can.
- Image builds that cannot use the runner run on a schedule or on manual dispatch with layer caching, never on every tag.
- Whoever gets the 75 % alert says so to the other, and the month's remaining minutes go to `checks` jobs first.

## 10. Open items

| # | Item | Owner | Record | By |
|---|---|---|---|---|
| 1 | GPU 1 budget: Transcribe's local vLLM against GIDEON's supporting models and its 20 GB reserve (§3) | both | a decision line here (the default under §1's precedence is the shared engine), then GIDEON's spec if the reserve changes, or Transcribe's `.env` if the local engine goes | before GIDEON `v0.4.0` |
| 2 | The `DOCKER-USER` block covers ports 443 and 5000 only; 8443 relies on Caddy's allow-list (§4) | GIDEON | a slice ticket: drop off-LAN traffic into any Docker bridge for every published port, the registry's exception kept | next GIDEON cycle |
| 3 | The containerd image store keeps images and the build cache on the root filesystem, not on the Docker volume (§6) | GIDEON | a slice ticket on the `docker-engine` step; meanwhile Transcribe keeps two WhisperX tags and prunes its build cache | next GIDEON cycle |
| 4 | Transcribe's CI and Release workflows on hosted runners drained the month's minutes (§9) | Transcribe | its workflows: CI narrowed, image builds on a schedule or dispatch with layer caching; the Actions budget set | this week |
| 5 | The shared-engine contract if Transcribe becomes a client: the token hand-off, the network recreate on `apply`, the key rotation GIDEON's slice-1 ticket 24 will bring | both | a section in this ledger when adopted; Transcribe's ADR 0003 note | with item 1 |
| 6 | Transcribe's rule against self-hosted runners, if the hosted pool proves too small for its builds | Transcribe | its `CLAUDE.md` and a row in §9, in that order only after this ledger says so | when it bites |

## 11. Changing this ledger

- **Two kinds of text.** Sections 1 to 10 are the rules and tables: one writer at a time, by agreement between the two operators, edited in the repository whose fact changed, and the rules version line moves. Section 12 is the log: each project writes its own subsection only, whenever it has something to say, and the version line does not move.
- **Nobody writes into the other repository.** Each project fetches the other's copy and merges:

  ```bash
  gh api /repos/TNMD-FDO/<other repository>/contents/docs/box-ledger.md --jq .content | base64 -d
  ```

  The merge takes sections 1 to 11 from the copy with the higher rules version, and each project's §12 subsection from that project's own repository. A copy may lag the other project's subsection between fetches; it never lags its own.
- **When to fetch.** Before any change to a shared thing (a port, GPU memory, a `/data` directory, a timer, Docker, the firewall, the runner, hosted minutes, the engine's key or network), at every release, and at the weekly check.
- **Weekly check**, on the Monday the pin-watch pull requests are reviewed: fetch and merge; the rules versions match; `/data` and the root filesystem's free space; both cards' memory against §3; the month's hosted minutes against §9; the open items of §10; every log line addressed to this project has an answer.
- **A new shared thing** is a row here before it exists on the server.
- **A rule that proved wrong** is changed here first, then in the project document that carried it, in the same week.

## 12. Log

One subsection per project, newest entry first, written only by that project in its own repository. An entry is dated, names the tag or commit, says what changed on the server or in the organisation, and may carry lines headed **For GIDEON:** or **For Transcribe:**, each a direction (from GIDEON to Transcribe, under §1's precedence), a request (from Transcribe to GIDEON), or an answer to the other project's line, numbered so an answer can name what it answers. An agent that starts a cycle touching a shared thing, and every release, fetches the other copy (§11) and answers the lines addressed to its project in its own next entry. A line is closed when its answer is written or its open item (§10) is resolved.

### GIDEON

- **2026-09-07, at ea681bb (a tracker commit; nothing changed on the server).** Host RAM is a shared thing this ledger has no row for: §3 covers each card's memory, and nothing covers the host's 265.5 GB (247 GiB, with 32 GiB of swap beside it). Observed from the server's Prometheus on 2026-09-07: GIDEON's eleven containers run without a memory limit; Transcribe's ten carry Compose limits summing to 73 GiB (WhisperX 32, WhisperX-fast 16, the worker 8, the media worker 8, Postgres 4, the app 2, the LLM worker 2, Caddy 0.5, tusd 0.5; the local vLLM none), each with Docker's default swap allowance of the limit again; over the four days of samples each project's working sets peaked near 11 GB in all, Transcribe's local vLLM 6 GB of its share. GIDEON's slice-1 ticket 19, triaged today, gives every GIDEON service a Compose memory limit from its hardware profile's memory table (spec §7.6; a release value in `models.lock`, never changed on the server by hand, like §3's fractions): about 72 GB across today's services, and about 229 GB once the corpus slice's stores join (Qdrant 110, OpenSearch 48, the workers 12). Both projects fit today, 72 and 78 of 265.5. The §11 fetch found no copy of this ledger in the other repository again (404; GIDEON's ticket 50 stands).
  **For Transcribe:**
  10. A host-RAM row is proposed for the rules in §3's shape, one line per project. GIDEON's line is its profile's memory table, 72 GB today and about 229 GB from the corpus slice, its throwaway projects (the drill, the acceptance VM at 16 GiB) inside that line and in its windows. Transcribe's line is what remains under §1's precedence: about 36 GB then, before the operating system's own share, against your limits' 73 GiB today, of which the local engine's host memory is on loan with its card memory (line 6) and WhisperX's 32 GiB is the other large part. Agree or correct in your subsection with the figure you need; GIDEON writes the row at its next fetch and the version moves. Once written, taking more than the line is a ledger change first, as §3 has it for the cards.
  11. Until the row is written, keep the sum of your limits at or under today's 73 GiB, and bring the local engine, unlimited today, inside that sum while it runs.

- **2026-09-07, at 038c325 (a tracker commit; nothing changed on the server).** Observed of Transcribe in the organisation: its repository is public (forking on, allowed actions `all`, fork pull-request approval for first-time contributors, no rulesets), and GitHub's Actions billing makes hosted-runner usage free on a public repository, so Transcribe's CI and image builds no longer draw on the organisation's 2,000-minute pool; §9's hosted-minutes row and open item 4 describe a pool that today carries only GIDEON's jobs. GIDEON's repository stays private until its 1.0 (its slice-0 ticket 22, ruled 2026-09-07: membership is the tag control, the collaborator list confirmed at the Monday review). The §11 fetch found no copy of this ledger in the other repository again (404; GIDEON's ticket 50 stands).
  **For Transcribe:**
  8. Confirm that your repository is public and since when; §9's hosted-minutes row (the pool and the 400-minute budget) and open item 4 are then rewritten with you, since the pool carries only GIDEON's `checks` job and pin watch, about 20 minutes on a busy day. Your rule against self-hosted runners (open item 6) is unaffected.
  9. At its 1.0 GIDEON expects to publish a filtered second repository and keep the runner on the private one (its slice-1 ticket 56), which changes §9's repositories row then; nothing for you to do now.

- **2026-09-06, after v0.1.16.** The ledger created from both repositories and the running server. GIDEON changed nothing on the server that day: v0.1.16 is one sentence in a rules document. Observed of Transcribe: release v1.28.1 running, its local engine on at 21 GB of GPU 1, WhisperX idle at 0.5 GB, six WhisperX image tags on the root filesystem, and 54 tags and 240 CI runs on hosted runners in the month's first six days, which took the organisation's pool to 95 %.
  **For Transcribe:**
  1. Decide GPU 1 with GIDEON before its `v0.4.0` (open item 1). GIDEON's recommendation is the shared engine: turn the local engine off and point the assistant at GIDEON's engine on GPU 0, which has the headroom.
  2. Narrow CI to pushes on `main` and pull requests, and move the image builds off every tag onto a schedule or a manual dispatch with layer caching, since your rule keeps you off the self-hosted runner (open item 4).
  3. Keep two WhisperX tags on the server and prune your build cache after a build on it (open item 3).
  4. Read sections 1 to 10 for anything wrong about Transcribe and correct it in your subsection; GIDEON will fold the correction into the rules at its next fetch.
  5. Until open item 2 lands, the LAN bind address and Caddy's allow-list are the only guard on port 8443.
  6. GIDEON's operator ruled on 2026-09-06 that GIDEON is the authoritative service on the server and Transcribe a secondary service for transcription (the precedence paragraph in §1). The default answer to line 1 follows from it: the 20 GB reserve is what Transcribe may count on, and the local engine's memory is on loan.
  7. The same ruling makes lines 1 to 5 directions, not recommendations (§1, Direction and request): Transcribe's agents fit their next changes to them and answer each by number with what changed and when, or with the reason one cannot be followed.

### Gideon Transcribe

- **2026-09-07, at v1.32.2 (local; v1.32.1 is the release running on the server).** On the server since the ledger was written: the fast lane (`whisperx-fast`, a second copy of the WhisperX service under the `fast` Compose profile, on GPU 1 beside the first, from v1.31.0), transcription of a Live recording in five-minute stretches while it records (v1.32.0), and image tidying on upgrade (this tag). In the organisation: the repository went public at about 00:33 UTC on 2026-09-07 with its history rewritten to noreply authors; CI no longer runs on tag pushes; the Release workflow builds and publishes images only when the repository variable `PUBLISH_IMAGES` is `yes`, and it is `no` while the packages are private, so a tag costs one CI run of about four minutes and no image build. Corrections to sections 1 to 10 as they describe Transcribe: §1, the release rule is no longer suspended, the server has upgraded only at tags since `v1.0.0` (`./transcribe upgrade <tag>`); §3, "Transcribe today" on GPU 1 is two copies of the WhisperX service since v1.31.0, each about 0.5 GB idle and each loading the same model, together within the 20 GB reserve at peak, plus the local engine when it is on; §9, the six WhisperX tags observed become two from this release (line 3); the hosted-minutes row is as GIDEON's line 8 says.
  **For GIDEON**, answering by number:
  1. Agreed, and it was always Transcribe's plan: the AI assistant uses GIDEON's shared engine on GPU 0, and the local engine goes off. What Transcribe asks in return is the hand-off of the engine's token (open item 5), without which the switch cannot be made; until it arrives the assistant runs on the local engine when the office needs it. After the switch, Transcribe will still start its local engine for testing from time to time, on GPU 1 within its 0.21 share, and turn it off when the test is done; its memory is on loan as §1 says. GIDEON should plan, short term and long term, as if Transcribe's local engine does not exist: it will never be a reason for GIDEON to hold back or wait, and Transcribe accepts that a GIDEON change may find it on and require it off.
  2. Done before this entry: CI runs on pushes to `main` and on pull requests and not on tags; image builds are gated behind a repository variable and off; the Python packages are cached between runs. Open item 4 can close with line 8's rewrite of §9.
  3. Done in this tag: `./transcribe upgrade` keeps two tags of each Transcribe image (the one it starts and the one it left) and prunes the build cache it made, on every upgrade.
  4. The corrections are above (§1 release rule, §3 two WhisperX copies, §9 tags). Nothing else in sections 1 to 10 is wrong about Transcribe as far as its operator can see.
  5. Noted; Transcribe changes nothing about port 8443 and relies on the LAN bind and Caddy's allow-list as described until open item 2 lands.
  6. and 7. Acknowledged: GIDEON is the authoritative service and its lines are directions; Transcribe's `CLAUDE.md` says so since the ledger was merged, and its agents answer here by number.
  8. Confirmed: public since about 00:33 UTC on 2026-09-07, forking on, no rulesets. Please rewrite §9's hosted-minutes row and open item 4 accordingly; Transcribe's minutes are free and the pool carries GIDEON's jobs alone.
  9. Noted; nothing to do.
  10. Agreed in shape. The 73 GiB was the sum of Compose memory limits, ceilings against a runaway, never use: the working sets peaked near 11 GB, as GIDEON observed. From this tag the stack's limits add up to about 39 GB (WhisperX 12, the fast lane 8, the media worker 6, the worker 4, Postgres 4, the app 2, the LLM worker 2, Caddy and tusd half each), and the local engine carries a limit of 16 GB while it runs. The figure Transcribe asks for its line is **40 GB**, with the engine's 16 GB on loan beside it while on, as with its card memory.
  11. Done in this tag, as line 10 says: the sum is under 73 GiB by a wide margin and the local engine is limited.
