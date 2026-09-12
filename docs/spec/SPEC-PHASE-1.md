# Gideon Transcribe, Phase 1 specification

The Workspace release, published as `v1.0.0`.

## About this document

This is the build specification for Phase 1 of Gideon Transcribe: a local transcription, translation-to-English, and speaker diarization web app for an office that handles privileged material, with an AI assistant, running entirely on the office's own server. It was assembled from the resolved planning tickets of the office that wrote the app, so that a build session can start with nothing left to decide. Every rule in it is a decision already made. Where something was deliberately left to the build, the chapter says so under "Left to the build", with the constraints the decision put on it.

Read it with its companions:

- `CONTEXT.md`, the glossary. The capitalised words in this document (Recording, Transcript, Segment, Side, Batch, Job, Run, Queue, Workspace, Clip, Summary, Chat, Admin, and the rest) are defined there, and the build uses them in code, on pages, and in documents. Each entry also names the words to avoid.
- `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`, every admin setting of both phases with its type, default, range, phase, effect, and when a change takes effect. Chapters name settings; the catalogue defines them.
- `docs/whisperx-api.md`, the WhisperX service's API and operating contract. The service is an independent container that this app consumes; its contract is written for any Consumer.
- `docs/spec/SPEC-PHASE-2.md`, the Case folders release. Phase 1 carries a few hooks for it, listed in each chapter under "Carried for Phase 2".
- `docs/adr/`, the decision records for the hard-to-reverse choices, and `docs/research/`, the facts behind the pins and the designs.

Nothing in this document is office-specific. Every office fact (hostnames, networks, directory names, tokens, paths, mail addresses) is a value in `.env`, a secrets file, or an admin setting, and the install script asks for it. The office that wrote the app keeps its own values outside the product repository.

### Conventions

- "The app" is the Django application and its workers; "the service" is the WhisperX service; "the engine" is the language model the AI assistant talks to; "the panel" is the admin panel.
- A word in `code` is a literal the build must use exactly: a key, a file or folder name, a command, a reason class, a value.
- A number beside a setting is its default; the catalogue gives the range. Times of day are the server's local time.
- "Phase 1" and "Phase 2" name the two releases, `v1.0.0` and `v2.0.0`; "the build" is the effort that turns this document into the Phase 1 release.
- No em dashes anywhere in the app, its pages, or its documents; hyphens.
- British spelling in documents and pages (organise, licence as the noun), as the glossary uses it.

## What Phase 1 delivers

**The setting.** A federal defender office, or any office with the same needs: attorneys, investigators, paralegals, and interpreters, at least thirty users, internal only, never anyone outside the office. The material is privileged and confidential. The app runs entirely on the office's own server, uses free tools only, runs in Docker, and is installed by an IT generalist from the product repository: clone, run the install script, start with Compose.

**The features.**

- Sign-in with the office directory (LDAPS), gated by a Sign-in group, with Admins from an Admin group, a manual flag, or a Local admin account; one Login session per user; an idle timeout.
- Upload of one file or many as a Batch, browser only; every Recording inspected, prepared per Side, and given a Playback copy; per-user storage quotas.
- Transcription by the WhisperX service, one Run at a time across the whole office, in arrival order, with no priority for anyone; a queue the user can see, with position, the person ahead, and an Estimated wait.
- Translation to English as a per-Recording choice, with automatic language detection and a rule for recordings holding more than one language.
- Diarization as a per-Recording choice with a speaker-count hint; Two-channel calls transcribed per Side.
- A viewer with the Transcript at reading width, a synced player for audio and video, a waveform Timeline, Correction of Segments, merging, Speaker naming, Follow mode, frame stepping, speeds, and Boost.
- Clips: a span of a Recording saved as a playable file for use outside the app, with an excerpt, captions, and optional burned captions.
- The AI assistant, on request only: a Summary shaped by a Summary template, a Chat grounded in one Transcript with checked Citations, and Speaker suggestions; prompt templates Admins can edit.
- Exports: a Word Transcript as a Record, a combined document with Summaries and Chats, plain text, SRT captions, a Batch download, and "Download everything" at sign-out.
- The Workspace: everything a user uploads lives only while their Login session does and is discarded when it ends; nothing is kept past the session in Phase 1. What a user wants to keep, they export.
- An Admin-only audit log, metadata only, with a hash chain and an Integrity check.
- An admin panel with a Status page, the Queue, the users list, the audit log viewer, the Installation page, and about thirty settings applied together through a tray.
- The WhisperX service itself, pinned and independent, shipped in the same repository and consumable by other apps.
- The product repository, its licence, its Releases, its images, its helper script, and its guides.

**Not in Phase 1.** Cases (kept Recordings), sharing, the Retention policy and Recycle bin, People and the Speakers tab, Clips in Cases, the Case Chat, email notifications, and backup and restore are Phase 2 (see `SPEC-PHASE-2.md`). The Deferred and ruled out chapter lists what is neither.

## Contents

1. Architecture and deployment
2. Repository, releases, and distribution
3. Sign-in, accounts, and roles
4. Media handling
5. Upload page and Batch page
6. Queue and Jobs
7. Transcription, translation, and diarization choices
8. Transcript viewer and player
9. Clips
10. AI assistant
11. Exports
12. Workspace lifecycle
13. Audit log and logging
14. Admin panel
15. Rules that hold everywhere
16. Build gates and deliverables
17. Deferred and ruled out

Appendices: A. Environment keys. B. Audit rows. C. Reason classes. D. Sources.

Chapters 1 and 2 are the shape of the system. Chapters 3 to 14 follow a Recording from sign-in to export and then the pieces around it. Chapters 15 to 17 are the cross-cutting rules, what the build must prove and deliver, and what not to build. The appendices consolidate what the chapters name in passing.

## 1. Architecture and deployment

This chapter fixes the runtime as it stands once installed: the Compose project and every service in it, the networks, the GPU reservation, the ports and the address, the app's own Caddy, the two folders on the server, the app's system user, the secrets, the environment keys, the policies (restart, health, limits, logs, time zone), the Shared engine and the optional Local engine, the first run, the server preparation, the DNS record and the certificate, and the Upgrade and Roll back mechanics. The repository side (the licence, the community files, the images on ghcr.io and the pull-then-build rule, CI, versions and the changelog lines, the install guide's outline, the questions `./transcribe install` asks, and the lines `./transcribe check` prints) is in the chapter "Repository, releases, and distribution".

### A separate stack beside whatever else the server runs

Gideon Transcribe is a fully separate stack. It has its own repository, release cadence, install script, Compose project, App data folder, reverse proxy, certificate, directory configuration, and Backup job. Nothing of it is rendered or operated by any other project on the same server, and no other project's release rules bind it. If the office later wants transcription inside another platform, that is a new effort, not a change to this one.

It shares three things with the server, each consumed as configuration and never as code:

- **The box.** A data folder on the data drive, created once by an admin and owned by the app's own system user; Docker-published ports; the host's Docker daemon, NVIDIA driver, and journal.
- **One GPU.** Everything this app runs on a GPU runs on the one card the office assigns to it, reserved by UUID through CDI. Where a Shared engine occupies another card, that card is never touched.
- **A Shared engine's address.** Where the office runs a language-model engine outside the app, the AI assistant reaches it over a Docker network the office names in `.env`, with that engine's bearer token copied into the app's own secret file. The engine address and model name are admin settings, so switching engines is a panel change plus a copied token. Until a Shared engine exists, the AI assistant is either Off or pointed at the Local engine.

Two shapes were rejected, for a builder who might otherwise assume them: not a branch of another platform's release (that couples this app's schedule to that platform's and forbids the `.env` install story), and not a sibling that borrows another platform's reverse proxy (that needs a change there for every route and ties the hostname to that platform's certificate).

### The address and who may reach it

1. **Address.** `https://<hostname>:<port>/`, with the hostname from `APP_HOSTNAME` and the port from `HTTPS_PORT`. Another reverse proxy on the server may own port 443, so the app's own Caddy answers on its own port and the address carries that port; the default is 8443. The hostname is the app's own name in the office's DNS zone, not a name under any other product's hostname, because the app is a separate product. One A record, one certificate with that single name. Not a second IP address on the server (it would need a bind change in the other stack), and not a route through another stack's reverse proxy (it would couple the app to that stack's releases).
2. **Who may reach it.** The app's Caddy answers only clients inside the CIDRs listed in `ALLOWED_CLIENT_CIDRS` and returns 403 to everyone else. A host firewall's default-deny protects the host, not Docker's forwarded traffic, so a port this stack publishes is not held to the office network by the host. The restriction lives in the app's own Caddy and touches nothing on the host.
3. **Bind address.** Caddy publishes `${BIND_ADDRESS}:${HTTPS_PORT}` (port 443 inside the container). `BIND_ADDRESS` defaults to `0.0.0.0`; set to the server's LAN address, it keeps the port off every other interface the server has (a virtual-machine bridge, for example). Caddy binds to the address, not the name, so nothing on the box waits for DNS.
4. **Nothing else listens.** No port 80 and no ACME. The WhisperX service publishes no host port and has no hostname; no second Consumer exists, and a public route, hostname, and certificate name for it are added only when one appears. Postgres publishes no port.

### The picture

```
 office network (ALLOWED_CLIENT_CIDRS)           the server (BIND_ADDRESS)
 -------------------------------------           ------------------------------------------------------------------
 browser --HTTPS on HTTPS_PORT--> caddy -+- /files/*  --> tusd --writes--> <App data folder>/uploads/
                                         +- /media/*  --forward auth--> app, then files from <App data folder>/scratch/ (read-only)
                                         +- /*        --> app (Django, gunicorn)
                                                           |
                                            postgres <-----+-----> media-worker  (ffmpeg, audiowaveform; CPU only)
                                 <App data folder>/postgres      worker        (hand-over, 3 s poll, merge, schedules)
                                                           |     llm-worker    (Summary, Chat, Speaker suggestions)
                                                           |          |
                                       network "whisperx"  |          |  network LLM_NETWORK (external, the Shared engine)
                                                           v          v  or the Local engine on the project network
                                       whisperx (FastAPI + model process)    Shared engine   |  vllm (profile llm)
                                       the app's GPU by UUID, no port        its own GPU     |  the app's GPU by UUID
                                       <App data folder>/models/whisperx/, <App data folder>/whisperx/

 Any other stack on the server (a reverse proxy on 443, its own database and services) runs beside all of this and is never touched.
```

### The Compose project and its services

One Compose project, `transcribe`, from `<Install home>/compose.yaml`, which `include`s `whisperx-service/compose.yaml`: one `docker compose up -d` brings everything up, and the service folder still runs on its own for a second Consumer or a test bench. Service names are fixed because documented commands use them (`docker compose run --rm app create-local-admin`, `docker compose run --rm whisperx pull`). Container names follow Compose's rule, `transcribe-<service>-1`.

Nine services with the Local engine profile on, eight without. Two images are built from the repository (the app image and the WhisperX service image); every other image is upstream and pinned.

| Service | Image | Source | Runs as | Networks | What it does |
|---|---|---|---|---|---|
| `caddy` | caddy 2.11, pinned | upstream | the app user | `transcribe` | the front door; see The app's Caddy below |
| `app` | the app image: Django, gunicorn sync workers, psycopg 3 | built from the repository | the app user | `transcribe`, `whisperx` | the web app; runs migrations, then starts; `/healthz` (database reachable); the tus pre-create and post-finish hooks; the forward-auth endpoint for media |
| `media-worker` | the app image (it carries ffmpeg 7.1 and audiowaveform from Debian 13) | built | the app user | `transcribe` | Procrastinate queue `media`, concurrency 4, one ffmpeg per job with `MEDIA_THREADS_PER_JOB` threads: hash, probe, Sides, ASR audio, Playback copy, waveform, Clip renders; CPU only |
| `worker` | the app image | built | the app user | `transcribe`, `whisperx` | queue `default`: hand-over of Runs to the WhisperX service, the three-second poll of the service's job list, result fetch and merge, and the schedules (03:00 Directory check, 03:30 sweeper, the audit sweep, every minute Login sessions and Discards, every ten minutes stalled-Job recovery) |
| `llm-worker` | the app image | built | the app user | `transcribe`, plus the Shared engine's network when configured | queue `llm`, concurrency 4: Summary, Chat, Speaker suggestions; the once-a-minute engine check; the only container that touches a network outside the project |
| `tusd` | tusproject/tusd (MIT), pinned | upstream | the app user | `transcribe` | receives upload pieces into `/srv/data/uploads`; `-behind-proxy`; hooks to `app` for pre-create and post-finish; never logs request headers |
| `postgres` | postgres 18, pinned | upstream | its own user | `transcribe` | the database on `<App data folder>/postgres`; holds the app role, the audit insert-only role, and the sweep role |
| `whisperx` | built from `whisperx-service/` on `nvidia/cuda:12.8.2-base-ubuntu24.04` with the pinned stack | built | the app user | `whisperx` | the WhisperX service: FastAPI, uvicorn, SQLite, a supervised model child process; the app's GPU by UUID through CDI; no published port; `/healthz` |
| `vllm` | vllm/vllm-openai 0.27.1, pinned; profile `llm`, off by default | upstream | the app user | `transcribe` | the Local engine; see The Shared engine file and the Local engine profile below |

Notes on the services:

- The app image is one image run as four services (`app`, `media-worker`, `worker`, `llm-worker`). It carries Django, gunicorn with sync workers, psycopg 3, ffmpeg 7.1, and the audiowaveform package from Debian 13; the build verifies that `ffmpeg -decoders` lists g729. Browser pages poll the app every five seconds and there are no server-sent events, so a plain WSGI server is enough.
- Background work runs on Procrastinate 3.9.0 (MIT) over the app's own Postgres through `procrastinate.contrib.django`: there is no Redis, no Valkey, and no scheduler container. The three workers are one image on three queues (`media`, `default`, `llm`).
- Media work is CPU only. No app container sees a GPU.
- The WhisperX service ships as its own folder, `whisperx-service/`, with its own Dockerfile, Compose file, environment example, and README, so it can run without the app. Its API and its operating contract are in the WhisperX service API document. The web container reaches the service's `/healthz` and `/v1/` on the `whisperx` network; the Upload page calls the liveness check on open and on Submit.
- `restart: unless-stopped` on every service.

### Networks

| Network | Declared by | Members | Purpose |
|---|---|---|---|
| `transcribe` | `compose.yaml`, the project's own | `caddy`, `app`, `media-worker`, `worker`, `llm-worker`, `tusd`, `postgres`, and `vllm` when the profile is on | everything inside the app |
| `whisperx` | `whisperx-service/compose.yaml`, under that fixed name | `whisperx`, `app`, `worker` | the WhisperX service's line; open to a second Consumer's project as an external network |
| the engine's network, named by `LLM_NETWORK` | outside the app when it is a Shared engine's, joined as an external network by `compose.shared-engine.yaml`; otherwise a plain network the install creates (`transcribe-llm`) for the Local engine | `llm-worker` only, and `vllm` when the Local engine profile is on | reaching the engine |

The Shared engine's network name is a `.env` fact, never code. `compose.shared-engine.yaml` adds that external network to `llm-worker` and nothing else.

### GPU

Only `whisperx` and the optional `vllm` reserve a GPU, by UUID through CDI (`driver: cdi`, `nvidia.com/gpu=<GPU UUID>`), never by index. The UUID lives in `.env` as `WHISPERX_GPU_UUID` in the service's file and `LLM_LOCAL_GPU_UUID` in the app's file, written by `./transcribe install` from `nvidia-smi -L`. No app container sees a GPU.

The service uses whatever VRAM it needs on that card. The Phase 1 benchmark gate records its measured VRAM peak at the chosen batch size in the service README under "GPU budget", the figure IT checks before another model is placed on the card. When the Local engine shares the card, its memory fraction (`LLM_LOCAL_GPU_FRACTION`, 0.55) is the ceiling that keeps the two apart.

### The app's Caddy

- Image caddy 2.11, pinned; automatic HTTPS off; no port 80; no ACME. Publishes `${BIND_ADDRESS}:${HTTPS_PORT}` and nothing else.
- **TLS files.** `<Install home>/tls/cert.pem` and `<Install home>/tls/key.pem`, the office CA's certificate and key for `<hostname>`, mounted read-only. Caddy reads them at start, so a renewed certificate needs `docker compose restart caddy`.
- **CA root.** `<Install home>/ca/office-root.pem`, the office CA's root certificate, is for LDAPS (`LDAP_CA_FILE`); office clients already trust the CA that issued the certificate, so Caddy needs nothing beyond the pair above.
- **Client allow-list.** A `remote_ip` matcher from `ALLOWED_CLIENT_CIDRS`; 403 to everyone else; empty means everyone.
- **Routes.**
  - `/files/*` to `tusd`, with no request buffering and no body cap; the app's tus pre-create hook enforces the size limit (see the Media handling chapter).
  - `/media/*`: a forward-auth check against `app` first, then the file served from `/srv/scratch` (the App data folder's `scratch/`, mounted read-only) with range requests. This is how Playback copies, waveform data, and Clip files reach the browser; the uploaded bytes are never served.
  - everything else to `app:8000`, with a 64 MB body cap.
- **Logging.** A JSON access log to stdout; paths carry ids only, never file names.
- **Order.** Starts after `app` is healthy.

### Folders on the server

Two folders. Images live in Docker's data-root, never under either.

#### The Install home

The Install home, on the OS drive, is the clone of the Release tag: code, compose files, docs. Mode 0755, owned by the admin who runs compose (an account in the docker group). It is created empty by the server preparation, because git clones only into an empty folder; the clone is the first thing into it, and `tls/`, `secrets/`, and `ca/` (outside version control) follow the clone.

```
<Install home>/                      the clone of the Release tag: code, compose files, docs (OS drive)
  compose.yaml                       the project; include-s whisperx-service/compose.yaml
  compose.shared-engine.yaml         adds the Shared engine's external network to llm-worker, nothing else
  transcribe                         the helper script
  .env                               settings and the paths to secret files, mode 0600
  .env.example                       every key with a comment
  secrets/                           mode 0700: django_secret_key, postgres_password, ldap_bind_password,
                                     llm_api_token, whisperx_consumer_token (each mode 0400)
  tls/cert.pem  tls/key.pem          the office CA certificate and key for <hostname>; key.pem mode 0600
  ca/office-root.pem                 the office CA root, for LDAPS
  whisperx-service/                  the service: Dockerfile, compose.yaml, models.yaml, README
    .env                             its settings: GPU UUID, limits, VAD, alignment languages
    .env.example                     every key with a comment
    secrets/hf_token                 the HuggingFace token, mode 0400
    secrets/tokens                   one Consumer per line; the app's line written by the install
```

Every file under `tls/`, `secrets/`, `ca/`, and `whisperx-service/secrets/` is owned by the admin who installs. `.env` is mode 0600.

#### The App data folder

The App data folder holds everything the app stores. It is on the data drive (the largest drive, never the OS drive), named by `APP_DATA_DIR` (asked by the install; no default), and owned by the `transcribe` system user.

```
<App data folder>/                             transcribe:transcribe, 0750; the data drive
  uploads/                     0750            tus pieces (swept after 24 h)
  scratch/                     0750            scratch/<user id>/<recording id>/: uploaded bytes, probe, ASR audio,
                                               Playback copy, waveform, clips/
  postgres/                    0700            the database files; handed to the Postgres container's own user by the install
  models/                      0750
    whisperx/                                  HF cache, torch hub, CUDA compile cache; re-pullable, not backed up
    vllm/                                      the Local engine's weights
  whisperx/                    0750            the service's state: job database, in-flight audio, results awaiting collection
  test-corpus/                 0700            the office's test corpus with its SHA256SUMS.txt; every file 0600
  cases/                       0750            Phase 2
  backup/                      0700            database dumps taken before Upgrades; Phase 2 staging
<App data folder>-drill/                       transcribe:transcribe, 0750, empty; Phase 2
```

Every subfolder is `transcribe:transcribe`. Every app container mounts the App data folder at `/srv/data`; Caddy mounts `scratch/` read-only at `/srv/scratch`. The "Minimum free disk space" check reads the filesystem behind `/srv/data`, so the app and worker containers see the free space of the filesystem that holds the App data folder. Nothing survives a Login session, so `scratch/` and `uploads/` hold only working files, and Postgres holds text only for the session. The database files sit inside the App data folder, not on the OS drive, so one tree holds the whole app and one job backs it up.

### The app's system user

`transcribe` is a system account: shell `/usr/sbin/nologin`, no home folder created (its home field points at the App data folder), its own group `transcribe` and no other, never in the docker group. Its uid and gid go into `.env` as `APP_UID` and `APP_GID`, and every app service runs with `user:` set to them. Postgres runs as its own user; `postgres/` keeps the `transcribe` owner until `./transcribe install` hands it to the database container.

### Secrets as files

Nothing office-specific or secret is in the images, the repository, or the compose files. `.env` holds settings and the paths to secret files; the secret files reach containers as Compose file secrets, mode 0400 inside. `./transcribe install` generates the random ones (the Django key, the Postgres password, and the WhisperX Consumer token together with its line in the service's tokens file) and asks for the two human-held ones (the Bind account's password and the HuggingFace token) on the terminal, never as command arguments and never echoed. `install --reconfigure` is the only way to overwrite an existing `.env`, `secrets/`, or `tls/`. The `secrets/` folder is mode 0700; each file in it is 0400.

| File | Holds | Written by | Read by |
|---|---|---|---|
| `secrets/django_secret_key` | Django's secret key | the install, random | app, workers |
| `secrets/postgres_password` | the database password | the install, random | app, workers, postgres |
| `secrets/ldap_bind_password` | the Bind account's password | the install, asked on the terminal | app, workers |
| `secrets/whisperx_consumer_token` | the app's Consumer token for the WhisperX service | the install, random, with the matching line in `whisperx-service/secrets/tokens` | app, worker |
| `secrets/llm_api_token` | the engine's bearer token: a copy of the Shared engine's token, or the token the Local engine serves with | copied from the Shared engine's operator; for the Local engine see Left to the build | llm-worker, vllm |
| `whisperx-service/secrets/hf_token` | the HuggingFace token, for the model pull; mode 0400, owned by the admin who installs | the install, asked on the terminal | whisperx |
| `whisperx-service/secrets/tokens` | one named bearer token per Consumer, one per line, an `admin` mark allowed | the install writes the app's line | whisperx |

The HuggingFace token file is the whole of what the service needs beside the accepted model licence. The Bind account's password stays in the office's password store until the install asks for it; nothing else about it is placed on the box.

### Environment keys

Two files: the app's `<Install home>/.env` and the service's `<Install home>/whisperx-service/.env`. `.env.example` ships beside each with every key and a comment. `./transcribe install` asks the office facts on the terminal and writes both files itself; the admin never copies the example by hand.

| Key | File | Meaning | Placeholder or example value |
|---|---|---|---|
| `APP_HOSTNAME` | `.env` | the app's hostname: Caddy's site name; the app's allowed hosts and the links in exports | `<hostname>`; no default |
| `HTTPS_PORT` | `.env` | the published HTTPS port; read by the caddy publish | `8443` (default) |
| `BIND_ADDRESS` | `.env` | the address Caddy publishes on; the server's LAN address keeps the port off other interfaces | `<server LAN address>`; default `0.0.0.0` |
| `ALLOWED_CLIENT_CIDRS` | `.env` | the client networks Caddy answers; everyone else gets 403 | `<office CIDRs>`; empty means everyone |
| `APP_DATA_DIR` | `.env` | the App data folder; the source of every bind mount | `<App data folder>`; no default, the install asks |
| `APP_UID`, `APP_GID` | `.env` | the `transcribe` user's ids; `user:` on every app service | `<uid>`, `<gid>`; no default |
| `TZ` | `.env` | every container's time zone, so schedules are office-local; the host stays UTC | `<office time zone>`; default `UTC` |
| `LDAP_ENABLED` | `.env` | whether directory sign-in is on; read by app and workers | see the Sign-in, accounts, and roles chapter |
| the seven `LDAP_*` keys | `.env` | the directory settings; read by app and workers. Two are fixed here: `LDAP_CA_FILE` is `ca/office-root.pem` and `LDAP_BIND_PASSWORD_FILE` is `secrets/ldap_bind_password` | see the Sign-in, accounts, and roles chapter |
| `MEDIA_THREADS_PER_JOB` | `.env` | ffmpeg threads per media job; media-worker | `8` |
| `MEDIA_CONCURRENT_JOBS` | `.env` | media jobs at once; media-worker | `4` |
| `WHISPERX_URL` | `.env` | the service's address on the `whisperx` network; app, worker | `http://whisperx:8000` |
| `WHISPERX_TOKEN_FILE` | `.env` | the app's Consumer token file; app, worker | `secrets/whisperx_consumer_token` |
| `LLM_API_TOKEN_FILE` | `.env` | the engine token file; llm-worker, vllm | `secrets/llm_api_token` |
| `DJANGO_SECRET_KEY_FILE` | `.env` | Django's secret key file; app, workers | `secrets/django_secret_key` |
| `POSTGRES_PASSWORD_FILE` | `.env` | the database password file; app, workers, postgres | `secrets/postgres_password` |
| `COMPOSE_FILE` | `.env` | which compose files Compose reads; set only to add the shared-engine file | unset, meaning `compose.yaml` alone; with a Shared engine `compose.yaml:compose.shared-engine.yaml` |
| `LLM_NETWORK` | `.env` | the Docker network the AI assistant's engine is reached on: the Shared engine's network, joined as an external network by llm-worker, or a plain network the install creates for an office without a Shared engine | `<engine network>`; default `transcribe-llm`, created by the install |
| `COMPOSE_PROFILES` | `.env` | Compose profiles; `llm` turns the Local engine on | unset |
| `LLM_LOCAL_MODEL` | `.env` | the Local engine's model | `Qwen/Qwen3.8-27B-FP8` |
| `LLM_LOCAL_GPU_UUID` | `.env` | the Local engine's GPU, by UUID | `<GPU UUID>`; no default |
| `LLM_LOCAL_GPU_FRACTION` | `.env` | the Local engine's share of the card's memory | `0.55` |
| `WHISPERX_GPU_UUID` | `whisperx-service/.env` | the service's GPU, by UUID | `<GPU UUID>`; no default |
| `WHISPERX_ALIGN_LANGUAGES` | `whisperx-service/.env` | the alignment languages | see the WhisperX service API document |
| the limits, timeouts, VAD thresholds, and batch size | `whisperx-service/.env` | the service's operating settings | see the WhisperX service API document |
| `HF_TOKEN_FILE` | `whisperx-service/.env` | the HuggingFace token file | `secrets/hf_token` |

The Phase 2 keys (Backup and mail) are listed under Carried for Phase 2. Two things are panel settings and not `.env` keys: the engine address and the model name, and the AI assistant toggle (see Settings).

### Policies

#### Restart and start order

`restart: unless-stopped` on every service. Start order: `postgres` healthy before `app`; `app` healthy before `caddy`, `tusd`, and the three workers.

#### Health checks

| Service | Check |
|---|---|
| `app` | `/healthz` (the database is reachable) |
| `postgres` | `pg_isready` |
| `media-worker`, `worker`, `llm-worker` | `manage.py procrastinate healthchecks` |
| `whisperx` | `/healthz`, the service's unauthenticated liveness endpoint |
| `vllm` | `/health` |

`docker compose ps` shows every service healthy; `./transcribe status` prints the compose state plus the health lines.

#### Resource limits

Memory limits in the compose file, with starting values that the build gate tunes: postgres 4 GB, app 2 GB, each of the three workers 8 GB, caddy and tusd 512 MB each, whisperx 32 GB, vllm 64 GB. `cpus: 40` on `media-worker` (four jobs of eight ffmpeg threads plus headroom); no other CPU caps.

#### Container logs

Every container uses the Docker daemon's journald log driver. Retention is the host's journal retention: journal retention is one setting for the whole host, and the app sets none of its own. No content ever: those logs are never the record, the Caddy access log sees paths that carry ids and never file names, and the tus sidecar never logs request headers. `journalctl CONTAINER_NAME=transcribe-app-1` is the admin guide's example.

#### Time zone

`TZ` from `.env` in every container, so schedules are office-local; the host stays UTC.

#### Postgres

`shared_buffers` 1 GB and a nightly `VACUUM` are enough for a database that holds settings, users, the audit log, prompt templates, and session text. Three roles: the app role, the audit insert-only role (it cannot update or delete), and the sweep role that removes audit rows past Audit retention (see the Audit log and logging chapter).

### Systemd units

Phase 1 has none. The app's services come back after a reboot through `restart: unless-stopped` under the Docker daemon. The timer and service units that `./transcribe install` writes for the Backup are Phase 2 (see Carried for Phase 2).

### The Shared engine file and the Local engine profile

An office gives the AI assistant an engine in one of two ways. The AI assistant behaves the same against either, and the app sends no `priority` to either.

**A Shared engine.** Two `.env` lines: `COMPOSE_FILE=compose.yaml:compose.shared-engine.yaml` and `LLM_NETWORK=<engine network>`. The second file adds that external network to `llm-worker` and nothing else. The engine's bearer token is copied into `secrets/llm_api_token`. The engine address and model name are then changed once in the panel. The Shared engine listens only on its own Docker network behind that token, which is why `llm-worker` joins the network rather than the engine publishing a port.

**The Local engine.** An office without a Shared engine leaves both lines out and turns the Compose profile `llm` on (`COMPOSE_PROFILES=llm`). The profile runs vllm/vllm-openai 0.27.1, pinned, serving `LLM_LOCAL_MODEL` (default `Qwen/Qwen3.5-4B`, the small model of `docs/research/local-engine-model.md`) on the GPU named by `LLM_LOCAL_GPU_UUID`, with:

- `--served-model-name local-engine`
- `--max-model-len 131072`
- `--reasoning-parser qwen3`
- `--api-key` from `secrets/llm_api_token`
- `--gpu-memory-utilization ${LLM_LOCAL_GPU_FRACTION}` (0.21, twenty gigabytes of a 96 GB card, to share it with the WhisperX service)
- `VLLM_USE_DEEP_GEMM=0` (mandatory for FP8 on this GPU generation, harmless for the bf16 default)
- `HF_HUB_OFFLINE=1` after its own pull; weights under `<App data folder>/models/vllm/`
- memory limit 64 GB; on the `transcribe` network only; health check `/health`

Off by default. The panel's defaults are what the profile serves: engine address `http://vllm:8000/v1`, model name `local-engine`. An office whose Shared engine does not exist yet turns the profile on until the Shared engine is reachable, then switches the two panel settings, copies the token, and turns the profile off again.

### The helper script

`./transcribe` is a small bash script in the repository; each subcommand is a short bash function that a non-programmer runs by name. The questions `install` asks and the lines `check` prints are in the chapter "Repository, releases, and distribution".

| Subcommand | What it does |
|---|---|
| `install` | checks the prerequisites; asks the office facts on the terminal and writes both `.env` files; writes the GPU UUID into both from `nvidia-smi -L`; generates the random secrets; asks for the Bind account's password and the HuggingFace token; hands `postgres/` to the database container's own user; reports what is missing. `--reconfigure` is the only way to overwrite an existing `.env`, `secrets/`, or `tls/`. `--build` builds the two images on the server instead of pulling them |
| `status` | the compose state plus the health lines |
| `check` | the smoke checks as a plain report; nothing in it reaches GitHub, since nothing on the box phones home |
| `backup-db` | a `pg_dump` in Postgres custom format into `<App data folder>/backup/` |
| `upgrade <tag>` | the Upgrade sequence below; `--build` as on `install` |
| `rollback <tag>` | the Roll back below |

Phase 2 adds `backup`, `snapshots`, `restore <snapshot>`, and `restore-drill`.

### First run

1. **Host prerequisites.** The NVIDIA driver and the NVIDIA container toolkit with CDI enabled in the Docker daemon, Docker with the Compose plugin, the daemon's default log driver set to journald, and a data drive. An office whose server provisioning already provides these starts at step 2; another office follows the install guide's checklist.
2. **One `sudo` session, then the clone.** Create the `transcribe` system user (no login, not in the docker group), the App data folder tree with its ownership and modes, and the Install home, empty and owned by the admin who runs compose. Then, as that admin, clone the Release tag into the empty Install home. While the repository is private the clone goes over SSH with a read-only deploy key through an SSH nickname; once it is public, HTTPS with no key works too. The clone must be at a Release tag, never at `main`; `./transcribe upgrade` and, in Phase 2, `restore` both check that. The commands are under Server preparation.
3. **Place the certificate, key, and CA root.** Move `cert.pem`, `key.pem`, and `office-root.pem` from the staging folder on the box into `<Install home>/tls/` and `<Install home>/ca/` (`key.pem` mode 0600; all three owned by the admin who runs compose). This happens after the clone and never before, because the Install home must be empty at clone time. Then delete the staging folder with everything else in it. The certificate is requested before this step (see DNS and certificate); the private key was generated on the box and never leaves it.
4. **`./transcribe install`.** It checks the prerequisites, asks the office facts and writes both `.env` files, writes the GPU UUID into both, generates the secrets, asks for the Bind account's password and the HuggingFace token, and reports what is missing.
5. **The models.** `docker compose run --rm whisperx pull` (needs the HuggingFace token and the accepted model licence). With the Local engine: `docker compose run --rm vllm pull` as well.
6. **Start.** `docker compose up -d`; migrations run as `app` starts; `docker compose ps` shows every service healthy.
7. **The Local admin.** `docker compose run --rm app create-local-admin`.
8. **Smoke test.** Open the address, sign in as the Local admin, see the status page green on directory, service, disk, and (when an engine exists) AI assistant; upload one corpus file and watch it through to a Transcript. `./transcribe check` prints the same checks as a plain report.

### Server preparation

Human work on the server, as an admin with sudo who is in the docker group. It touches nothing belonging to any other stack on the box. Each command checks nothing and creates one thing, so run only the ones whose target does not exist yet. The data folder goes on the largest drive, not the OS drive.

```bash
# 1. the system user; the uid and gid become APP_UID and APP_GID
sudo useradd --system --no-create-home --home-dir <App data folder> --shell /usr/sbin/nologin --user-group transcribe
id transcribe

# 2. the App data folder tree (0750 for the folder and most children; 0700 for the database files, dumps, and real recordings)
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/uploads
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/scratch
sudo install -d -o transcribe -g transcribe -m 0700 <App data folder>/postgres
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/models
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/models/whisperx
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/models/vllm
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/whisperx
sudo install -d -o transcribe -g transcribe -m 0700 <App data folder>/test-corpus
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/cases
sudo install -d -o transcribe -g transcribe -m 0700 <App data folder>/backup
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>-drill

# 3. the Install home: empty, owned by the admin who runs compose
sudo install -d -o <compose admin> -g <compose admin> -m 0755 <Install home>

# 4. verify
id transcribe
sudo ls -la <App data folder>
```

**The test corpus.** The office's own recordings for the smoke test and the benchmark gate, with their `SHA256SUMS.txt`. Copy them into `<App data folder>/test-corpus/` with `cp -a`, set the owner to `transcribe:transcribe`, the folder to 0700 and every file to 0600, then verify in the new home with `sha256sum -c SHA256SUMS.txt`. Remove the old copy on the box only after every file checks; the master copy stays off the box. The corpus is never committed anywhere.

**The deploy key** (only while the repository is private; a public repository is cloned over HTTPS with no key). As the admin who runs compose, generate a key on the box that never leaves it, give GitHub a nickname (`<nickname>`) that uses that key and no other, and put GitHub's host keys in `known_hosts` so the clone never stops at a host-key prompt:

```bash
ssh-keygen -t ed25519 -N '' -C 'transcribe deploy key' -f ~/.ssh/<deploy key file>
```

```
# ~/.ssh/config
Host <nickname>
    HostName github.com
    User git
    IdentityFile ~/.ssh/<deploy key file>
    IdentitiesOnly yes
```

GitHub's host keys come from `api.github.com/meta` over HTTPS and must match the fingerprints GitHub publishes. The public half of the key goes into the product repository's Deploy keys page as read-only (see the chapter "Repository, releases, and distribution"). Before it is registered, `ssh -T git@<nickname>` answers "Permission denied (publickey)", which shows the route works; once registered it answers "Hi TNMD-FDO/gideon-transcribe! You've successfully authenticated, but GitHub does not provide shell access." Port 443 to `ssh.github.com` is the fallback if port 22 is ever closed. Nothing else on the box that talks to GitHub is affected by the nickname, and once the repository is public the nickname can stay or go.

**The clone**, as the admin who runs compose, into the empty Install home:

```bash
git clone --branch <tag> git@<nickname>:TNMD-FDO/gideon-transcribe.git <Install home>
```

`./transcribe upgrade` fetches through the same nickname.

**What `./transcribe check` verifies about this preparation**, offline: the `transcribe` user exists and is not in the docker group; the App data folder is owned by it with mode 0750; the checkout at the Install home is at a Release tag, not `main`.

### DNS and certificate

Human work outside the server, done once the hostname and port are fixed and before first-run step 3. The private key never leaves the box. The WhisperX service gets no record and no certificate.

#### DNS

One A record in the office's DNS zone: `<hostname>` pointing at the server's LAN address (the value of `BIND_ADDRESS`). Either in DNS Manager on a domain controller (the forward zone, New Host (A or AAAA), the host label as the name, the server's address; leave "Allow any authenticated user to update" unticked; the PTR box is optional), or from a PowerShell window running as an account allowed to edit the zone:

```powershell
Add-DnsServerResourceRecordA -ComputerName <DNS server> -ZoneName <zone> -Name <host label> -IPv4Address <server LAN address>
```

A name looked up before its record exists plants a "name does not exist" answer in every cache on the way, which lingers for the zone's negative TTL. After adding the record, run `ipconfig /flushdns` on the workstation and flush the cache on each caching resolver the office runs (the server's first resolver above all), or wait the TTL out. Nothing on the box waits for this: Caddy binds to the address from `.env`, not the name. Verify that the name resolves from a workstation and from the box.

#### The certificate request

The certificate is from the office CA, which office clients already trust; the commands below assume a Windows certificate authority (Active Directory Certificate Services) with a Web Server template. Requirements: subject and only SAN `<hostname>`; Extended Key Usage TLS Web Server Authentication; one certificate in the file with LF line endings; the key RSA 3072, generated on the box and never copied off it.

1. On the box, as the admin who runs compose, in a staging folder of mode 700 in that admin's home, generate the key and the request:

   ```bash
   openssl req -new -newkey rsa:3072 -nodes -keyout key.pem -out transcribe.csr -subj "/CN=<hostname>" -addext "subjectAltName=DNS:<hostname>"
   chmod 600 key.pem
   ```

2. Copy `transcribe.csr` (it carries no secret) to a Windows machine. In a PowerShell window running as an account with Enroll on the Web Server template:

   ```powershell
   certreq -submit -attrib "CertificateTemplate:WebServer" -config "<CA config string>" transcribe.csr transcribe.cer
   ```

   If certreq answers "Taken Under Submission" instead of issuing, the template wants a manager's approval: open the Certification Authority console on the CA, Pending Requests, right-click the request, All Tasks, Issue, then `certreq -retrieve <RequestId> transcribe.cer`.

3. The `.cer` that comes back is already PEM. Copy it to the box as `cert.pem`, as is; there is no `certutil -encode` step (that would wrap the PEM in base64 a second time, and Caddy could not read it).
4. Put a copy of the office CA's root certificate in the staging folder as `office-root.pem`, and verify: subject and SAN match `<hostname>`; `openssl verify -CAfile office-root.pem cert.pem` reports OK; the public key in `cert.pem` matches the one in `key.pem`; note the expiry date.
5. The three files wait in the staging folder until first-run step 3 moves them into `tls/` and `ca/`. `transcribe.csr` can be deleted after the move or kept for the next renewal.

#### Renewal

The admin guide records the certificate's expiry date and these steps. Begin in the month before expiry. Repeat steps 1 to 4 above in a scratch folder on the box (the same `openssl` line, a new key and request), then put the new pair in `<Install home>/tls/` and run `docker compose restart caddy`. The CA root in `ca/office-root.pem` changes only when the office CA is replaced. The office facts the guide's fill-in fields need: the CA config string, and where the DNS zone lives and which resolvers cache it.

### Upgrade and Roll back

Releases are git tags. `./transcribe upgrade <tag>` does, in this order:

1. Refuses while a Job is running (the status page's line says so).
2. Refuses when tracked files have local edits.
3. Takes the dump: `backup-db` into `<App data folder>/backup/pre-<tag>.dump`, Postgres custom format.
4. Copies the configuration: `.env`, both secrets folders (`secrets/` and `whisperx-service/secrets/`), and `tls/` into `<App data folder>/backup/config-pre-<tag>.tar`, before the checkout.
5. `git fetch --tags && git checkout <tag>` (through the SSH nickname while the repository is private).
6. `docker compose pull`, or `docker compose build` with `--build`. The compose file carries `image:` with a pinned tag and digest either way; the pull-then-build rule is in the chapter "Repository, releases, and distribution".
7. `docker compose up -d`, which restarts only the changed services and runs the migrations as `app` starts.
8. `docker compose run --rm whisperx pull` when the Release's notes say the models changed. The script reads out the changelog's "Models" and "Database" lines (their format is in the Repository, releases, and distribution chapter).
9. The smoke test (`./transcribe check`).

An Upgrade never touches the office's settings, secrets, or certificate. There is no fixed monthly cadence: base-image and dependency updates arrive as Releases; how often they are cut and how an installer hears about them is the Repository, releases, and distribution chapter's.

`./transcribe rollback <tag>` checks out the previous tag and runs `docker compose up -d`. If a migration cannot be reversed, it restores the dump taken before the Upgrade, `backup/pre-<tag>.dump`, with `pg_restore`. One dump format serves both this Roll back and a Phase 2 restore, so the two share one mechanism. The configuration copy `config-pre-<tag>.tar` is kept beside the dump; these tickets give `rollback` no automatic use of it.

### Egress

At install and Upgrade only: `huggingface.co` and its download hosts, which an office that filters egress must allow as `*.hf.co` rather than by name (HuggingFace routes large-file downloads through regional hosts under `hf.co` and changes them without notice; `cdn-lfs.hf.co`, `cdn-lfs-us-1.hf.co`, and `cas-bridge.xethub.hf.co` all resolve, yet a gated model's weight was served from `us.aws.cdn.hf.co`); the image registry `ghcr.io`, or, for builds on the server, `pypi.org` and `deb.debian.org`; and GitHub for the clone and the fetch (port 22, or port 443 to `ssh.github.com`).

At run time: LDAPS to the office's domain controllers on the LAN, and the engine's network inside Docker. Nothing else; nothing on the box phones home. The app edits no host-level egress list; the install guide states the hosts for an office that filters egress.

### What this stack never touches

Any other stack's Compose project, reverse proxy, certificate, secrets, firewall rules, journal policy, and egress list, and every folder on the data drive except the App data folder and its `-drill` sibling. The only links to another stack are the Shared engine's network name and its copied token, both `.env` facts.

### Audit rows

These tickets name no audit row. They fix how the audit log is held and fed:

- the audit log is an insert-only table in the app's Postgres database with a hash chain; the app writes through a role that cannot update or delete it, and a separate sweep role removes rows past Audit retention;
- the client address on an audit row is taken from the app's own Caddy only;
- the Integrity check is a management command as well as a status-page button;
- container logs are never the record and hold no content.

The rows themselves are in the Audit log and logging chapter.

### Settings

- **Minimum free disk space** (default 200 GB): measured on the filesystem that holds the App data folder, which every app and worker container sees through its `/srv/data` mount.
- **The engine address and the model name** (the AI assistant's provider settings): defaults `http://vllm:8000/v1` and `local-engine`, what the Local engine profile serves; an office with a Shared engine changes both once.
- **The AI assistant toggle**: Off until an engine answers.
- **Audit retention**: the sweep role removes audit rows past it.
- **The upload size limit** the tus pre-create hook enforces, since Caddy puts no body cap on `/files/*`.
- **The status page**: a row for every service's health, the app GPU's use from the service status, free space on the App data folder, the engine line, and the "a Job is running" line that `upgrade` refuses on. **The Installation page** shows the `.env` facts read-only: address, port, allowed CIDRs, data folder, network.

### Left to the build

- "The Phase 1 benchmark gate records its measured VRAM peak at the chosen batch size in the service README under 'GPU budget'": the figure, and the batch size, come from the gate.
- Memory limits and the `media-worker` CPU cap are "starting values tuned at the build gate": postgres 4 GB, app 2 GB, each worker 8 GB, caddy and tusd 512 MB, whisperx 32 GB, vllm 64 GB, `cpus: 40`.
- The mechanism behind `docker compose run --rm vllm pull`: the tickets fix the command, `HF_HUB_OFFLINE=1` afterwards, and the folder `<App data folder>/models/vllm/`, not how the upstream image fetches the weights.
- Who writes `secrets/llm_api_token` when the Local engine is on: the tickets have the install generate three random secrets and ask for two, and name this file in neither list; with a Shared engine it is a copy of that engine's token. If the Repository, releases, and distribution chapter's list of install questions covers it, that list governs.
- How `./transcribe install` hands `postgres/` to the Postgres container's own user.
- Health check intervals, timeouts, and retries; the exact Compose YAML for the CDI reservation, the file secrets, the `user:` lines, and the memory limits; the Caddyfile that carries the routes, the allow-list, and the forward-auth check.
- Who runs the nightly `VACUUM` and when.
- The `ffmpeg -decoders` check for g729 as a build step of the app image.
- The file name `backup-db` gives a dump taken outside an Upgrade (inside one it is `pre-<tag>.dump`).
- Which schedule carries the 24-hour sweep of `uploads/`.
- What, if anything, `rollback` does with `config-pre-<tag>.tar`; the tickets fix that the copy is made, not that it is unpacked.
- The certificate checks assumed a one-certificate file verified against a self-signed root; the tickets say nothing about an office whose CA issues through an intermediate.

### Carried for Phase 2

- `cases/` (0750) exists in the App data folder tree from the server preparation and is unused in Phase 1.
- `backup/` is Phase 2's staging: the last 7 nightly dumps as `nightly-<date>.dump` (Postgres custom format), `manifest.json`, `last-run.json`, beside the pre-upgrade dumps `pre-<tag>.dump`. One dump format, restored with `pg_restore`.
- `<App data folder>-drill/` (0750, `transcribe:transcribe`, empty) is created at server preparation for the monthly Restore drill, which restores into it and empties it afterwards.
- One more Compose service, `backup`: image `restic/restic` pinned by digest, `profiles: [backup]` so `up -d` never starts it; mounts the newest dump and manifest, `cases/`, and the configuration files read-only and `backup/` read-write for restores; reaches the Backup target on port 22 over the LAN. Ten services with `vllm`.
- A drill override, `compose.drill.yaml`, brings up a sibling project `transcribe-drill` (Postgres and app only, loopback ports, no Caddy, no GPU, no WhisperX service, no workers, `LDAP_ENABLED=0`, `SMTP_HOST` empty so the drill never sends mail) under `<App data folder>-drill/`.
- Systemd timer and service units written by `./transcribe install`: nightly backup at `BACKUP_TIME` (02:00), prune and check on Sundays at 04:00, the drill on the first Sunday of the month at `DRILL_TIME` (04:00). The units run `./transcribe <command>` as root, and everything they start runs in containers.
- `./transcribe` gains `backup`, `snapshots`, `restore <snapshot>`, and `restore-drill`; `restore` refuses unless the checkout is at the Release tag the Snapshot's manifest names.
- `.env` gains `BACKUP_TARGET`, `BACKUP_SSH_KEY_FILE`, `BACKUP_KNOWN_HOSTS_FILE`, `BACKUP_KEY_FILE`, `BACKUP_KEEP_DAYS` (30), `BACKUP_LOCAL_DUMPS` (7), `BACKUP_TIME` (02:00), `DRILL_TIME` (04:00); `secrets/` gains `backup_ssh_key`, `backup_password`, `backup_known_hosts`, the first two also in the office's password store and never inside a Snapshot.
- `.env` gains seven mail keys, `SMTP_HOST`, `SMTP_PORT`, `SMTP_STARTTLS`, `SMTP_USER`, `SMTP_PASSWORD_FILE`, `MAIL_FROM`, `OPERATOR_EMAIL`, and one optional secret file, `secrets/smtp_password`, written by the install only when the relay wants a password. The Installation page shows the seven keys read-only, the password as set or missing. No new service.
- Run-time egress gains the Backup target on port 22 on the LAN, and `worker` reaching the office mail relay on `SMTP_PORT` over the LAN.
- Phase 1 carries none of the above except `backup-db`, the folders, and the first-run order that already places the files after the clone.

### Sources

Deployment topology on the rebuilt server; Relationship to the platform project on the server; Verify the server's mount and drive layout; Create DNS records and request the certificate; Prepare the server for the app: user, data folder, test corpus; ADR 0003, a fully separate stack beside the platform project on the server.

### Amendments applied

- From the platform-relationship ticket's amendment, to the ingress rule: the app runs its own Caddy on another port and the address carries the port; the second-address and borrowed-route options are gone.
- From the topology ticket, to the platform-relationship and DNS tickets: the hostname is the app's own name, not a name under another product's hostname; the port is 8443; the WhisperX service gets no hostname.
- From the topology ticket, to the audit ticket's container-log rule: retention is the host's journal retention, not 30 days.
- From the topology ticket, to the LLM features ticket: the Local engine profile answers the temporary-engine question; the panel's defaults are the Local engine's address and served name; the AI assistant toggle starts Off; the Shared engine's network is joined by `llm-worker` only.
- From the backup ticket, to the topology's `backup/` and helper-script rules: the pre-upgrade dump is `pre-<tag>.dump` in custom format (not `.sql`), restored with `pg_restore`; the `backup` service, the drill override, the systemd units, the four subcommands, the eight Backup keys, and the three Backup secrets, all Phase 2 except `backup-db`.
- From the GitHub distribution ticket, to the topology's helper-script and first-run rules: `check`, `install --reconfigure`, and `--build`; `install` asks the office facts and writes both `.env` files, so first-run step 3 is "place the certificate, key, and CA root"; `image:` plus `build:` with no pull policy on the two built services; `upgrade` refuses local edits and copies `.env`, both secrets folders, and `tls/` into `backup/config-pre-<tag>.tar`; the changelog's "Models" and "Database" lines.
- From the HuggingFace token task, to the topology's Egress rule: the download hosts are allowed as `*.hf.co`; `whisperx-service/secrets/hf_token` (0400) is all the service needs beside the licence acceptance.
- From the server-preparation task, to the topology's first-run step 2 and the DNS ticket's "Final home" table: the Install home is created empty because git clones only into an empty folder; the clone at the Release tag is the first thing into it; the certificate, key, and CA root are placed after the clone at first-run step 3, which also deletes the staging folder; the clone goes through the SSH nickname with a read-only deploy key while the repository is private. The directory-objects task's "delete the bind test with the folder" moves with it.
- From the DNS ticket's second round, to its renewal steps: the `.cer` that certreq returns is already PEM and is copied to the box as is; there is no `certutil -encode` step.
- From the email notifications ticket, to the topology's `.env` list and egress: the seven mail keys, `secrets/smtp_password`, the relay egress, and the drill override's empty `SMTP_HOST`, all Phase 2.
- From the maintainer, on the v1.10.0 build, to The Local engine: the default model `Qwen/Qwen3.5-4B` and the memory fraction 0.21, for the reasons the AI assistant chapter's amendment gives; the switch that turns the profile on and off.


## 2. Repository, releases, and distribution

This chapter fixes how Gideon Transcribe lives on GitHub, how a Release is cut and published, and how an IT generalist at another office gets from the repository to a running app. The product repository is `https://github.com/TNMD-FDO/gideon-transcribe`, in the organisation `TNMD-FDO`. It is private while Phase 1 is built and used by the office, and it goes public at `v1.0.0`. Its history starts clean from the first commit: every file in it is office-neutral, and the secret scan below runs on the seed before that commit. The organisation is on GitHub's Free plan, which decides several rules below. The install story is fixed: clone a Release tag, fill in `.env`, start with Compose; nothing office-specific is in the code. The audience of the public repository is other federal defender offices, and every guide is written for an IT generalist who is not a programmer: one command where possible, a verification checklist, and plain-language error recovery.

The runtime layout, the services, the networks, the folders, the systemd units, the mechanics of the eight install steps, and the mechanics of Upgrade and Roll back are in the Architecture and deployment chapter. This chapter names them only where the repository, the helper script's command line, or a guide depends on them.

### Licence

1. The app's own work carries the US-government-work notice plus the CC0 1.0 Universal dedication (ADR 0006). Under 17 U.S.C. section 105 a work prepared by federal employees as part of their duties carries no US copyright, so a licence such as MIT or Apache-2.0 would grant rights the office does not hold, and AGPL-3.0 would oblige any office that changes the app to publish its changes, a barrier for the IT generalists the app is meant for. CC0 is not OSI-approved, and that does not matter here: GitHub's licence detection reads the file as CC0-1.0.
2. The dedication covers the code, the built-in prompt wordings, the guides, and the spec pack. The built-in prompt wordings are the Ground rules, the Chat instructions, the Speaker-suggestion instructions, the Standard summary template, and the AI notice; they ship in the code as defaults and are edited in the admin panel, never in files. Nothing in the repository needs a copyright header. Any office can clone, change, and run the app without asking anyone.
3. `LICENSE` keeps the short 18F form of the notice ahead of the CC0 text, so that GitHub's licence detection still reads the file as CC0-1.0 (a LICENSE file with extra text may not be detected). The longer explanation goes in the README. The notice, in the 18F/GSA form:

```
As a work of the United States government, this project is in the public domain within the United States of America.

Additionally, we waive copyright and related rights in the work worldwide through the CC0 1.0 Universal public domain dedication.
```

The full text of the CC0 1.0 Universal legal code follows the notice in the same file.

4. `CONTRIBUTING.md` accepts contributions only under the same dedication, because Community Defender Organization staff are nonprofit employees who do hold copyright in what they write. If the office's pending question to the Community Defender Organizations about that term is ever answered differently, `CONTRIBUTING.md` follows the answer; the dedication itself does not change.
5. A licence on released code cannot be taken back. The decision holds for every Release once the repository is public; a later effort could only add terms to new versions.
6. Everything shipped beside the code keeps its own licence and is listed in `THIRD_PARTY_LICENSES.md` (below).

### Community files

The six community files live at the repository root.

| File | What it holds |
|---|---|
| `README.md` | what the app is, who it is for, the one-page install summary, the longer licence explanation that `LICENSE` leaves out, and the as-is line: the app is provided as is, with no support promised and reports welcome |
| `LICENSE` | the government-work notice and the CC0 1.0 dedication, in that order (ADR 0006) |
| `CONTRIBUTING.md` | the contribution term (contributions are accepted only under the same dedication), and how the work is organised: commits go straight to `main`, tags mark Releases, and the repository's Issues are for other offices' reports |
| `THIRD_PARTY_LICENSES.md` | everything shipped beside the code, with its licence (the list below) |
| `SECURITY.md` | how to report a problem privately: it points at the repository's private vulnerability reporting (switched on at the public flip) |
| `CHANGELOG.md` | one section per Release in the Keep a Changelog form, the two fixed lines first (see Versions, tags, and Releases) |

GitHub shows `CONTRIBUTING.md` as a Contributing tab and links it from new issues and pull requests; `SECURITY.md` is picked up on the repository's Security tab. Dependabot alerts and `SECURITY.md` work on every plan and visibility.

#### THIRD_PARTY_LICENSES.md

The file lists, with its licence, everything the two built images and the compose file ship beside the app's own code. Its sources are the third-party section of the GitHub distribution research file and the WhisperX pinned-stack research file (both ship under `docs/research/`). The entries:

| Component | Licence | Note |
|---|---|---|
| whisperx | BSD-2-Clause | |
| faster-whisper | MIT | |
| CTranslate2 | MIT | |
| pyannote.audio (code) | MIT | |
| pyannote/speaker-diarization-community-1 (weights) | CC-BY-4.0 | behind a Hugging Face gate that each office accepts itself; attribution required; never redistributed with the app |
| OpenAI Whisper (code and model weights) | MIT | the Hugging Face mirror `openai/whisper-large-v3` is tagged Apache-2.0 and is not gated |
| PyTorch | BSD-3-Clause | |
| every other component pinned on the WhisperX stack | as pinned | the WhisperX pinned-stack research file is the list |
| Django | BSD-3-Clause | |
| Procrastinate | MIT | the app's background worker, on Postgres; the stack ships no Redis or Valkey, so there is no licence note for either |
| python-docx | MIT | |
| Caddy | Apache-2.0 | upstream image |
| PostgreSQL | the PostgreSQL License | upstream image |
| tusd | MIT | upstream image |
| vLLM | Apache-2.0 | upstream image, the Local engine (profile `llm`) |
| Qwen3 weights | Apache-2.0 | the Local engine's model; not gated |
| restic | BSD-2-Clause | upstream image, Phase 2 (profile `backup`) |
| `nvidia/cuda` base image | NVIDIA Deep Learning Container Licence (proprietary) | the WhisperX service's base |
| ffmpeg as Debian builds it, with its codec packages | GPL v2 or later | the exact package versions per Release, see below |

Three consequences follow from that section of the research file:

1. **ffmpeg.** Debian's ffmpeg is a GPL build because it links libx264 (with libx265 and libxvid), which the app needs for H.264 Playback copies and Clips. Calling ffmpeg as a separate program leaves the app's own terms untouched. But publishing the app image means distributing GPL binaries, and whoever distributes GPL binaries must make the complete corresponding source available for as long as the binaries are distributed. So each Release records the exact ffmpeg and codec package versions in `THIRD_PARTY_LICENSES.md` with a pointer to Debian's source packages for them. Not an ffmpeg built without `--enable-gpl`, because the app needs the H.264 encoder.
2. **The WhisperX image.** It is a derived container under the NVIDIA Deep Learning Container Licence: that licence permits distributing a derived container that adds material functionality, forbids distributing the base container as a stand-alone product, and licenses its proprietary parts to run only on systems with NVIDIA GPUs. The image is proprietary in that respect and is listed as such.
3. **The notice form.** `LICENSE` keeps the short 18F form of the notice ahead of the CC0 text so that GitHub's licence detection still reads it as CC0-1.0, with the longer explanation in the README (rule 3 under Licence).

### The product repository

```
gideon-transcribe/
  README.md                 what it is, who it is for, the one-page install summary, the as-is line
  LICENSE                   the government-work notice and the CC0 1.0 dedication (ADR 0006)
  CONTRIBUTING.md           the contribution term, and how the work is organised
  THIRD_PARTY_LICENSES.md   everything shipped beside the code, with its licence
  SECURITY.md               how to report a problem privately
  CHANGELOG.md              one section per Release, the two fixed lines first
  CONTEXT.md                the glossary
  transcribe                the helper script: install, check, status, backup-db, upgrade, rollback,
                            and in Phase 2 backup, snapshots, restore, restore-drill
  compose.yaml              the app stack; includes whisperx-service/compose.yaml
  compose.shared-engine.yaml
  compose.drill.yaml        Phase 2
  .env.example              every key with a comment; the only environment file tracked
  .gitignore  .gitattributes
  app/                      the Django project, its Dockerfile, its tests
  whisperx-service/         Dockerfile, compose.yaml, models.yaml, .env.example, README.md, the service
  systemd/                  the unit files ./transcribe install writes (Phase 2 timers included)
  docs/
    install.md              the install guide
    admin-guide.md          the admin guide
    user-guide.md           the user guide
    whisperx-api.md         the WhisperX service API spec
    spec/                   SPEC-PHASE-1.md, SPEC-PHASE-2.md
    adr/                    the decision records
    research/               the findings behind the pins and the choices
  .github/workflows/
    ci.yml                  lint, tests, compose config, secret scan
    release.yml             images and the GitHub Release, on tags
```

Ignored and never committed: `.env`, `secrets/`, `tls/`, `ca/`, `whisperx-service/.env`, `whisperx-service/secrets/`.

Notes on the tree:

- The Django project lives under `app/` with its Dockerfile so the root stays readable for an installer.
- The WhisperX service lives under `whisperx-service/` with its own `compose.yaml`, `Dockerfile`, `models.yaml`, `.env.example`, and a `README.md` written for a non-programmer: accept the diarization model's licence on Hugging Face, create the read token, run `pull`, generate the tokens file. The service's API is documented under `/v1/`, with its version reported in every result; `docs/whisperx-api.md` is the WhisperX service API document.
- `compose.yaml` is the app stack and `include`s the service's file. `compose.shared-engine.yaml` adds the external engine network to `llm-worker` and nothing else. Profile `llm` ships the Local engine for an office without a Shared engine. `compose.drill.yaml` is Phase 2.
- The app's `.env.example` carries every key with a comment; it and `whisperx-service/.env.example` are the only environment files tracked.
- The spec pack (`docs/spec/`), the decision records, and the research findings ship, scrubbed of anything office-specific, so that another office's IT and the Claude helping them can see why things are as they are.
- `systemd/` holds the unit files `./transcribe install` writes, Phase 2 timers included. Their content is the Architecture and deployment chapter's.

### Images

1. Two images are built from the repository: `ghcr.io/tnmd-fdo/gideon-transcribe-app` (from `app/`) and `ghcr.io/tnmd-fdo/gideon-transcribe-whisperx` (from `whisperx-service/`). The GHCR namespace is lowercase. Each is tagged with the Release tag and, once published, pinned by digest in the compose file: the `image:` line carries the Release tag and the `@sha256:` digest.
2. The upstream images (caddy, postgres, tusd, restic, vllm, and `nvidia/cuda` as the service's base) are pinned by tag and digest from their own registries and never mirrored.
3. The compose file carries both `image:` and `build:` for the two built services and no pull policy. With both present and no pull policy, Compose itself pulls first and builds from source only when the pull finds nothing in the registry or the platform cache; the built image is tagged with the `image:` name, so a build on the server produces the same name the compose file expects. `./transcribe install` and `./transcribe upgrade` lean on that, and `--build` on either forces a build, so an office that cannot reach ghcr.io still installs. Never a `latest` tag: Compose always pulls `latest` even under the missing policy.
4. A release workflow (`release.yml`) on GitHub's hosted runners builds and pushes both images on every tag from `v1.0.0`, with these constraints: the disk clean-up step comes first, because standard runners guarantee only 14 GB of free disk (about 10 to 30 GB is recoverable by deleting preinstalled tools: `/usr/share/dotnet`, `/opt/ghc`, `/usr/local/share/boost`, and the tool cache); the CUDA and PyTorch layer is kept apart from the WhisperX layer, because no single layer may exceed 10 GB (there is no documented whole-image limit); and each upload has a 10-minute timeout. Larger hosted runners need the Team plan and are always billed, so they are not available to the organisation.
5. Container images on ghcr.io are currently free for storage and bandwidth even while the package is private, with at least a month's notice promised before that changes (the half-gigabyte quota is for GitHub's other registries). So the office may start publishing at any tag it chooses before `v1.0.0`; nothing in the layout changes, and the build path stays as the fallback either way. Until it publishes, the office builds the images on the server itself, where the app runs anyway.
6. A package's visibility does not follow its repository: a package is private when first published, and making it public cannot be undone. Going public at `v1.0.0` is therefore a visibility switch on the repository plus one on each of the two packages. A package linked to the repository through the `org.opencontainers.image.source` label, set before the first push, inherits the repository's access permissions, not its visibility.

### Versions, tags, and Releases

1. Semantic version numbers on git tags, with a `v` prefix (`v1.2.3` for version 1.2.3): `v0.x` during the Phase 1 build and the office's own use, `v1.0.0` as the public release of Phase 1, `v2.0.0` for Phase 2, and patch numbers for fixes.
2. Every tag is also a GitHub Release whose notes are that version's section of `CHANGELOG.md`; `release.yml` creates it. A Release is the only thing an installer ever installs or upgrades to, and its notes always say whether the models or the database change.
3. `CHANGELOG.md` is in the Keep a Changelog form: one section per version, newest first, each dated, changes grouped by type (Added, Changed, Deprecated, Removed, Fixed, Security), an Unreleased section at the top for what is coming, and a line saying the project follows Semantic Versioning. Every version's section opens with two fixed lines, before anything else:

```
Models: unchanged
Database: unchanged
```

where the first line reads `Models: changed` when the models change and the second reads `Database: migrates` when the database changes. `./transcribe upgrade` reads the two lines of the target Release out before it starts.

4. No schedule: a Release when there is something to release, a monthly look at the pins, and Dependabot alerts on from the start (they work on every plan and visibility).
5. The app never checks GitHub for a newer Release; nothing on the server phones home. The Status page shows the running tag. The Installation page states the repository address and that nothing phones home. The install guide tells installers to subscribe on the repository page with Watch, Custom, Releases.
6. Upgrade means moving an installed app from one Release to a newer one with the helper script: a database dump and a copy of the configuration first, then the new Release's code and images, then the database changes; it never touches the office's settings, secrets, or certificate. Roll back means returning to the Release that ran before, restoring the pre-upgrade dump when the database changes cannot be reversed. The mechanics are in the Architecture and deployment chapter.

### The helper script `./transcribe`

A bash script at the repository root. Its subcommands:

| Subcommand | Phase | What it does |
|---|---|---|
| `install` | 1 | asks the office facts on the terminal, writes both `.env` files, generates the secrets, writes the systemd units, prints the next step; flags `--reconfigure` and `--build` |
| `check` | 1 | runs the smoke checks and prints a plain report, one line per check |
| `status` | 1 | reports the state of the running project |
| `backup-db` | 1 | dumps the database |
| `upgrade <tag>` | 1 | moves the install to a newer Release; flag `--build` |
| `rollback <tag>` | 1 | returns the install to the Release it ran before |
| `backup` | 2 | takes a Backup now |
| `snapshots` | 2 | lists the Snapshots in the Backup target |
| `restore <snapshot>` | 2 | restores a Snapshot |
| `restore-drill` | 2 | runs the Restore drill |

#### `./transcribe install`

1. It asks the office facts in plain words on the terminal and writes both `.env` files itself (the app's and `whisperx-service/.env`). The questions, in this order:
   1. the address: hostname and port;
   2. the server's LAN address to bind;
   3. who may connect: the networks;
   4. the App data folder;
   5. the time zone;
   6. directory sign-in on or off, and if on the eight directory facts (the `LDAP_*` keys), with the bind password typed hidden;
   7. the AI assistant's engine: a Shared engine's network name, or the Local engine and its GPU;
   8. the GPU for the WhisperX service, picked from the list `nvidia-smi -L` prints;
   9. the Hugging Face token, typed hidden;
   10. (Phase 2) the Backup target. The script uses the backup key it finds at `secrets/backup_ssh_key` and generates one only when there is none; it prints the public half for the backup store only in that case;
   11. (Phase 2) the mail facts, after the Backup target: the relay's host and port; whether the relay needs a password, and if so the user and the password typed hidden into `secrets/smtp_password`; the sender address; and the Operator address. A blank host means no mail, and the install says what that loses.
2. It then generates the secrets, writes the systemd units, and prints the next step.
3. It can be run again. It refuses to overwrite an existing `.env`, `secrets/`, or `tls/` unless given `--reconfigure`.
4. `--build` forces a build of the two images instead of the pull.
5. The install guide describes the engine settings and `LLM_API_TOKEN_FILE` together: the engine address and model name are admin settings, `LLM_API_TOKEN_FILE` is an `.env` line naming the file that holds the engine's token. An installer without an engine leaves the AI assistant toggle Off, and everything else works.

#### `./transcribe check`

It runs the smoke checks and prints a plain report; the install guide's chapter 4 says what each line means. Nothing in it reaches GitHub. The lines:

1. the hostname resolves to this server;
2. the certificate matches the hostname and is not expiring;
3. CDI sees the chosen GPU by its UUID;
4. the directory checks: the bind works, the groups can be read, members resolve, and nested membership resolves (the same list the panel's "Test directory connection" runs; see the admin settings catalogue);
5. `huggingface.co` answers;
6. the Hugging Face token works, tested by fetching and never by reading the token's permissions back (a permission read-back through `/api/whoami-v2` can report a working token's fine-grained permissions as empty while a gated file returns HTTP 200, so it proves nothing). The check makes a HEAD request on `pyannote/speaker-diarization-community-1/resolve/main/config.yaml` with the token, handing the token to curl on stdin so it never appears in the process list, and reports plainly: HTTP 200 is good; 401 means the token is wrong, missing, or revoked; 403, or 401 with the header `x-error-code: GatedRepo` while the account itself reads back fine, means that account has not accepted the model's conditions;
7. the disk has room;
8. Docker and Compose are recent enough;
9. the `transcribe` user exists and is not in the docker group (offline);
10. the App data folder is owned by the `transcribe` user with mode 0750 (offline);
11. the checkout is at a Release tag, not `main` (offline);
12. once the project is up, every container is healthy;
13. (Phase 2) the Backup target is proven: the check signs in with the key alone and no password fallback; lists the SFTP root and warns when anything but the backup folder and `home` is visible; writes and removes a file in the folder; fails when a `#recycle` folder is present; confirms the account gets no shell; and compares the store's host key against `secrets/backup_known_hosts`;
14. (Phase 2) the mail relay accepted a test message to the Operator address;
15. (Phase 2) how many members of the Sign-in group have no `mail` value in the directory: a warning, not a failure.

#### `./transcribe upgrade <tag>`

What this chapter fixes about it (the rest is in the Architecture and deployment chapter):

1. Code reaches the server only by `git fetch` and `git checkout <tag>` inside the script, which by nature never touches ignored files. While the repository is private the fetch goes through the SSH nickname described under Access, branches, and CI.
2. It refuses to run when tracked files have local edits.
3. It reads out the target Release's two fixed changelog lines before it starts.
4. Before the checkout it copies `.env`, both secrets folders (`secrets/` and `whisperx-service/secrets/`), and `tls/` into `backup/config-pre-<tag>.tar` (mode 0600), beside the pre-upgrade database dump.
5. `--build` forces a build of the two images instead of the pull.

### Secrets hygiene

1. `.gitignore` covers `.env`, every `.env.*` except `.env.example`, `secrets/`, `tls/`, `ca/`, `whisperx-service/.env`, and `whisperx-service/secrets/`. The example files are the only environment files tracked.
2. Code reaches a server only by fetch and checkout inside `./transcribe upgrade`. The install guide says in bold that nothing is ever pushed from a workstation or copied over the install folder. This is the rule that prevents a production `.env` from being overwritten during an upgrade.
3. Before every upgrade the script copies the configuration (`.env`, both secrets folders, `tls/`) into `backup/config-pre-<tag>.tar`, mode 0600, beside the pre-upgrade dump.
4. A secret scan runs in CI on every push, and on the seed before its first commit. It is the gitleaks command-line tool (MIT, no licence key) run directly in a workflow step, not the gitleaks GitHub Action, whose licence since its version 2 needs a key for organisation accounts (one repository free, more than one paid).
5. Repository push protection is not available to a private repository on the Free plan (it needs GitHub Secret Protection, which the Free plan cannot buy). Once the repository is public, GitHub's push protection for users is on by default and stops secrets being pushed to it.
6. No per-machine git hooks.
7. Flipping a private repository public publishes its whole history; forks and cached views keep anything ever committed, and a secret that ever reaches the history must be revoked or rotated, since rewriting the history is not enough. That is why the product repository's history starts clean and is scanned before its first commit.

### Access, branches, and CI

1. **The server's clone while the repository is private.** The server clones over SSH with a read-only deploy key, GitHub's name for a repository-scoped SSH key. The key is made on the server and its public half is installed on the repository. On the server the key file sits under `~/.ssh/` with a nickname in `~/.ssh/config`:

```
Host <nickname>
  HostName github.com
  User git
  IdentityFile <deploy key file>
  IdentitiesOnly yes
```

   The clone is then `git clone --branch <tag> git@<nickname>:TNMD-FDO/gideon-transcribe.git <Install home>`, always at a Release tag and never at `main`, and `./transcribe upgrade` fetches through the same nickname. GitHub's host keys are added to `known_hosts` from `api.github.com/meta` over HTTPS so nothing prompts. Once the repository is public the guide's clone is plain HTTPS with no key (`git clone --branch <tag> https://github.com/TNMD-FDO/gideon-transcribe.git <Install home>`), and an installing office never needs the nickname; it is a detail of the office's own pre-release period.
2. **Write access.** One person, the maintainer, has write access; a maintainers team is created when a second person appears. Commits go straight to `main`, and tags mark Releases. A rule on `main` forbidding force-push and deletion cannot be applied to a private repository on the Free plan (neither classic branch protection nor rulesets), so it is set as a ruleset at the public flip; until then the protection is the single writer and the workflow.
3. **`ci.yml`**, on every push and pull request, on GitHub's hosted runners: ruff, the unit tests, `docker compose config` against the example files, and gitleaks. A private repository on the Free plan has 2,000 hosted-runner minutes a month; a public repository's use of standard hosted runners is free.
4. **`release.yml`**, on tags from `v1.0.0`: builds and pushes the two images (with the disk clean-up step and the layer split under Images) and creates the GitHub Release from the tag's changelog section.
5. **No self-hosted runner.** Nothing uses a runner on the server, including the one the office already runs there for its other work (ADR 0003, the separate-stack decision). The GPU benchmark gate is a by-hand step on the server, not a workflow.
6. **At the public flip:** Issues on, Discussions off, Wiki off, private vulnerability reporting on (Settings, Advanced Security, Private vulnerability reporting; it exists for public repositories only) with `SECURITY.md` pointing at it, the ruleset on `main`, and the README's as-is line in place. The repository's Issues are for other offices' reports.

### The guides inside the app

The app serves the user guide at `/help/` and the admin guide from a Help link in the Admin panel's rail. Both are rendered at build time from the same Markdown files in `docs/` (`docs/user-guide.md`, `docs/admin-guide.md`), so the guides always match the running Release and nobody needs GitHub to read them. Only those two are served inside the app; the install guide (`docs/install.md`) is read from the repository.

### The install guide

`docs/install.md`, written for an IT generalist who is not a programmer, one command per step and nothing to choose from. Its chapters:

1. **What you need.** The hardware: one NVIDIA GPU with enough memory for the WhisperX service (the Phase 1 benchmark gate fills in the number). Ubuntu Server 24.04 or newer. The NVIDIA driver. The container toolkit with CDI. Docker with the Compose plugin. A data drive. A hostname and a certificate from the office's own CA. The hosts the server must reach (the appendix).
2. **Before you start.** The directory checklist; the certificate request; accepting the diarization model's terms on Hugging Face and creating the read token; and in Phase 2 the backup account on the office's store and the mail facts (see Carried for Phase 2). Each is written out below.
3. **Install.** The eight steps of the Architecture and deployment chapter, with `./transcribe install` doing the middle ones. The server-preparation step and the placing of the certificate are written out below.
4. **Check.** `./transcribe check` and what each line means.
5. **First sign-in.** The Local admin, the status page, and the first Recording taken from upload to Transcript. The first sign-in test needs at least one member of the Sign-in group who is not in the Admin group, so that the ordinary User role is exercised.
6. **When it fails.** A table of message, meaning, and fix.
7. **Upgrade.** Subscribe to Releases (Watch, Custom, Releases); read the two lines; `./transcribe upgrade <tag>`. In bold: nothing is ever pushed from a workstation or copied over the install folder.
8. **Roll back.** `./transcribe rollback <tag>`, and when the pre-upgrade dump is restored.
9. **Uninstall.** Stop the project, remove the folders, remove the units, remove the user.
10. **Appendix.** Every `.env` key with its meaning, and the egress hosts.

#### Egress hosts (the appendix)

At install and upgrade:

| Host | For |
|---|---|
| `github.com` | the clone and the fetch |
| `ghcr.io` and `pkg-containers.githubusercontent.com` | the prebuilt images |
| `registry-1.docker.io` and `production.cloudflare.docker.com` | the upstream images |
| `huggingface.co` and `*.hf.co` | the models; `*.hf.co` covers the download hosts, which Hugging Face changes without notice, so naming them individually is wrong |
| `pypi.org`, `files.pythonhosted.org`, `download.pytorch.org`, `deb.debian.org` | only for a build on the server |

At run time: only the directory servers on the LAN, the engine's network inside Docker, and in Phase 2 the backup store on the LAN (no new egress host, since the store is on the LAN). Nothing phones home.

#### Before you start: the directory checklist

Written for a non-programmer, with two paths that both work: clicking through Active Directory Users and Computers, or four PowerShell lines on any workstation with the directory tools (`New-ADGroup`, `Read-Host -AsSecureString` for the password, `New-ADUser` with `-PasswordNeverExpires $true -CannotChangePassword $true -ChangePasswordAtLogon $false`, `Add-ADGroupMember`), run with `-Credential` for the admin account and `-Server` naming one domain controller. The guide carries both. The items:

1. Create the Sign-in group, and optionally an Admin group.
2. Create the Bind account, a read-only directory account: the default Domain Users read is enough, it needs no delegation of `memberOf` and no group beyond Domain Users. A domain that hides `memberOf` from plain accounts is fine, because the app reads the groups' member lists.
3. Export the office CA root as PEM: copy it from any PEM the office already trusts, or export it with `Export-Certificate` plus `certutil -encode`. It can be taken from any domain-joined machine.
4. Fill in the eight `LDAP_*` keys in `.env`, with the bind password in a file (`./transcribe install` asks them and writes them).
5. Run `docker compose run --rm app create-local-admin`.
6. Test with "Test directory connection" in the Admin panel.

Three warnings the guide carries:

- Give the other domain controllers a minute after creating the objects.
- Never test the bind with a wrong password against the real account: a domain lockout policy can lock the account after a few wrong tries for a period.
- The domain may accept an empty password as an anonymous bind, so a blank test "passing" proves nothing.

#### Before you start: the certificate request

1. Generate the key and the request on the server:

```
openssl req -new -newkey rsa:3072 -nodes -keyout key.pem -out <hostname>.csr -subj "/CN=<hostname>" -addext "subjectAltName=DNS:<hostname>"
```

2. Submit the `.csr` on a Windows machine, as an account with Enroll on the Web Server template:

```
certreq -submit -attrib "CertificateTemplate:WebServer" -config "<CA config string>" <hostname>.csr <hostname>.cer
```

3. Copy the `.cer` to the server as `tls/cert.pem` exactly as it is. certreq answers a PEM request with a PEM certificate, and a `certutil -encode` step double-encodes it (this has happened).
4. Verify with `openssl verify -CAfile ca/office-root.pem tls/cert.pem`, and by comparing the public-key hashes of `tls/cert.pem` and `tls/key.pem`.
5. The CA root comes from any domain-joined machine (the export in the directory checklist) or from a PEM the office already trusts.

#### Before you start: the Hugging Face account and token

1. The Hugging Face account must be a user account, since acceptance of the model's conditions is granted to individual users and never to an organisation. An office is better served by a shared account that outlives one person.
2. The gate's form asks Company/university and a Use case whose options are all commercial; Other is the honest answer.
3. The token may be a plain Read token, or a fine-grained one with "Read access to contents of all public gated repos you can access" ticked.
4. The acceptance and the token are both needed, and neither alone is enough.
5. Each office accepts the CC-BY-4.0 licence itself; the model is never redistributed with the app.

The service's README carries the same facts.

#### The server-preparation step, written out

The guide gives these as commands to copy, run as an account with sudo:

```
sudo useradd --system --no-create-home --home-dir <App data folder> --shell /usr/sbin/nologin --user-group transcribe
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/uploads
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/scratch
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/models
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/models/whisperx
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/models/vllm
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/whisperx
sudo install -d -o transcribe -g transcribe -m 0750 <App data folder>/cases
sudo install -d -o transcribe -g transcribe -m 0700 <App data folder>/postgres
sudo install -d -o transcribe -g transcribe -m 0700 <App data folder>/backup
sudo install -d -o transcribe -g transcribe -m 0700 <App data folder>/test-corpus
sudo install -d -o transcribe -g transcribe -m 0750 <drill folder>
sudo install -d -o <compose admin> -g <compose admin> -m 0755 <Install home>
```

- `transcribe` is a system account with no login. It is never added to the docker group.
- The App data folder goes on the largest drive, not the OS drive. The empty drill folder sits beside it.
- The Install home is created empty and owned by the account that runs Compose, so it holds nothing before the clone.
- Verify with `id transcribe` and `sudo ls -la <App data folder>`.
- The keys `APP_UID` and `APP_GID` in `.env` carry the numeric ids of the `transcribe` account and its group.

#### Placing the certificate, after the clone

Git refuses to clone into a folder that already holds files, so the Install home must be empty at clone time, and the step that places the certificate comes strictly after the clone. It reads: move `cert.pem` and `key.pem` into `tls/` (the key mode 0600) and the CA root into `ca/` as `ca/office-root.pem`, then delete the staging folder they waited in.

### The admin guide

`docs/admin-guide.md`, served from the Help link in the Admin panel's rail. In Phase 1 it documents:

1. The audit log: what it records, the never-log line, and the Admin viewer; the "Audit log retention" setting and its consequence for the audited Admin accesses (ADR 0004); and the Integrity check. The content is the Audit log and logging chapter's.
2. The certificate: its expiry date (`<certificate expiry date>`; a Web Server template issues for two years), the renewal steps (the same request flow into `tls/`, then `docker compose restart caddy`), and the DNS note: the directory's zone lives on the domain controllers, and a caching resolver in front of them keeps a "name does not exist" answer for the zone's negative TTL, an hour, so create the record before anyone looks the name up, or flush that cache.
3. The Status page's running tag, and the Installation page's repository line.
4. The Phase 2 chapters (Backups, Email, Retention, the Folder management toggle, and the Case Chat settings) are listed under Carried for Phase 2.

### The user guide

`docs/user-guide.md`, served at `/help/`. Its Phase 1 content is left to the build (see Left to the build); the Phase 2 pages the amendments fixed are listed under Carried for Phase 2.

### Environment keys

The keys this chapter names. The full key list, with every key's meaning, is the install guide's appendix and the Architecture and deployment chapter.

| Key | File | Meaning | Placeholder or example |
|---|---|---|---|
| `LDAP_*` (eight keys) | `.env` | the directory facts, asked by `./transcribe install`; the bind password is in a file named by one of them, never in the key | see the directory sign-in chapter |
| `LLM_API_TOKEN_FILE` | `.env` | the file that holds the token for the AI assistant's engine | a path under `secrets/` |
| `APP_UID` | `.env` | the numeric id of the `transcribe` system account | `<uid>` |
| `APP_GID` | `.env` | the numeric id of the `transcribe` account's group | `<gid>` |
| `BACKUP_TARGET` | `.env` | Phase 2; the Backup target, an SFTP address whose path part is `/<share name>`; empty means backups are off | `/<share name>` as the path |
| the App data folder key | `.env` | the one folder that holds everything the app stores; named in the Architecture and deployment chapter | `<App data folder>` |

Files beside the keys, all ignored by git:

| File | Meaning |
|---|---|
| `whisperx-service/.env` | the service's own environment file, written by `./transcribe install` |
| `whisperx-service/secrets/` | the service's tokens file |
| `secrets/` | the app's secrets, generated by `./transcribe install`; holds the bind password file and the engine token file |
| `tls/cert.pem`, `tls/key.pem` | the certificate and its key (the key mode 0600) |
| `ca/office-root.pem` | the office CA root as PEM |
| `backup/config-pre-<tag>.tar` | the configuration copy `./transcribe upgrade` makes before the checkout, mode 0600 |
| `secrets/backup_ssh_key` | Phase 2; the backup key, used if present and generated only when absent |
| `secrets/backup_known_hosts` | Phase 2; the backup store's host key, compared by `./transcribe check` |
| `secrets/smtp_password` | Phase 2; the mail relay's password, typed hidden at install |

### Audit rows

This chapter adds no audit rows. The rows the admin guide must document (the audit log's own, and in Phase 2 the six Retention rows) belong to the chapters that define them.

### Settings

The admin settings this chapter's behaviour depends on, by their catalogue names; their tables are in the admin settings catalogue.

- The AI assistant toggle: an installer without an engine leaves it Off, and everything else works.
- The engine address and the model name: admin settings, described in the install guide together with `LLM_API_TOKEN_FILE`.
- "Test directory connection": the panel action whose check list `./transcribe check` runs.
- "Audit log retention": documented in the admin guide with its consequence for the audited Admin accesses.
- "Check directory now": the on-demand Directory check, which the Email notifications chapter names as the way to pick up a fixed `mail` value at once.
- Phase 2: "Retention period", "Warning before deletion", "Recycle bin", the Folder management toggle, "Chat across cases", "Case chat: most hours of talk per question", and the Email page's Test message.

### Left to the build

- **The install guide** (`docs/install.md`): written from the outline above. Constraints: for an IT generalist who is not a programmer; one command per step and nothing to choose from; a verification checklist; plain-language error recovery; the "When it fails" table of message, meaning, and fix; the bold line about never pushing or copying over the install folder; the directory checklist with both paths and the three warnings; the certificate steps; the Hugging Face facts; the server-preparation commands; the GPU memory figure in "What you need" filled in by the Phase 1 benchmark gate, which is a by-hand step on the server.
- **The admin guide** (`docs/admin-guide.md`) and **the user guide** (`docs/user-guide.md`): written for a non-programmer, rendered into the app at build time so they match the running Release; the admin guide's Phase 1 content is listed above; the user guide's Phase 1 pages use the glossary's page names.
- **The helper script `./transcribe`**: generated by the wizard skill at build time as a bash script. Constraints: the subcommands and flags in the table above; the install questions in the order given; both `.env` files written by the script; the refusal to overwrite without `--reconfigure`; every `check` line above, with the token handed to curl on stdin and never read back; the `upgrade` rules above; the two changelog lines read out before an upgrade. The planning repository holds working test scripts for the token test and the backup-target test that are the shape to follow; they do not ship.
- **The exact texts** of `README.md` (including the one-page install summary and the longer licence explanation), `CONTRIBUTING.md` (the contribution term and how the work is organised), `SECURITY.md`, and `.env.example` (every key with a comment).
- **`THIRD_PARTY_LICENSES.md`**: the entries above, plus the exact ffmpeg and codec package versions in each Release with the pointer to Debian's source packages, and the attribution the diarization weights require.
- **`ci.yml` and `release.yml`**: the steps named above. For the release workflow, the disk clean-up (the deletion of preinstalled tools, by hand or with an action that does the same) comes before the build, the CUDA and PyTorch layer is kept apart from the WhisperX layer, and the GitHub Release is created from the tag's changelog section. The `org.opencontainers.image.source` label is set before the first push.
- **How the server pulls a private package** before the packages go public (a registry login, or the build path): not fixed by the sources; the build path is the fallback either way.
- **`.gitattributes`**: listed in the tree; its content is not fixed.
- **The public-key hash comparison** in the certificate check: the guide names it; the exact commands are not fixed.
- **The wording of the `check` report** and of the install's next-step line.
- **The exact uninstall commands** for chapter 9: the sources fix only the four acts (stop the project, remove the folders, remove the units, remove the user).

### Carried for Phase 2

- The script's Phase 2 subcommands (`backup`, `snapshots`, `restore <snapshot>`, `restore-drill`) are named in the tree and absent in Phase 1; `backup-db` ships in Phase 1.
- `compose.drill.yaml`, the `backup` service (image `restic/restic` pinned by digest, profile `backup`), and the Phase 2 timers in `systemd/` are named in the tree and inert in Phase 1. The restic entry in `THIRD_PARTY_LICENSES.md` arrives with them.
- `BACKUP_TARGET` in `.env`: empty means backups are off. `backup/` exists from Phase 1 (the server preparation creates it) and holds `config-pre-<tag>.tar` from the first upgrade.
- `./transcribe install` gains the Backup target question and the mail questions, in the order given above, and `./transcribe check` gains the backup-target proof and the two mail lines.
- The install guide's Phase 2 "Before you start" list gains: the backup account and folder exist on the office's store and the key is in the account; every user's `mail` value is filled in the directory; and a relay that accepts mail from the server.
- The admin guide gains a **Backups** chapter written for a non-programmer: the account and folder on the office's store (a task for the office); pasting the public key the install prints; copying the repository password and the private key into the office password manager before the first Snapshot (without the password every Snapshot is unreadable); the Status page's Backup line and the operator mails; the restore runbook, whose first line is that a restore takes the app back to 02:00 of the Snapshot's day and everything after is gone, and that the checkout must be at the Release tag the manifest names; the Restore drill; and that `BACKUP_TARGET` empty means backups are off. It carries the steps for a Synology store running DSM 7 as a worked example:
  - The account is an ordinary account, never an administrator. restic speaks SFTP, and DSM 7 gives SFTP to ordinary accounts: each sees only the shared folders it has rights to, at the root of its own view, and never a shell. The path in `BACKUP_TARGET` is therefore `/<share name>`; an administrator account would see `/volumeN/<share name>` instead, and a reader who sees a `/volume` path has made the account an administrator by mistake.
  - Control Panel steps: File Services, FTP tab, "Enable SFTP service" on port 22, FTP itself off. The account with a long random password saved in the office password manager, "Disallow the user to change account password", group `users` only, Applications: SFTP allowed and everything else denied, and No access on every other shared folder, including the ones the `users` group can read (a share the `users` group could read appears in the account's view until it gets an explicit No access, which in DSM beats any group permission). The shared folder with Recycle Bin off (a `#recycle` folder would hoard every data file restic prunes; if the bin was ever on, delete the leftover `#recycle` folder as an administrator), encryption off (restic already encrypts, and an unmounted encrypted share fails the push silently), data checksum on for btrfs, compression off, a quota as a hard cap if wanted, Read/Write for the account and No access for everyone else. The user home service must be on, since the key lives in the account's home.
  - The public key goes into the account from the store's own shell as an administrator, not through File Station: `/var/services/homes/<account>/.ssh/authorized_keys`, owned by the account, the home not writable by others, `.ssh` mode 700, the file 600. A File Station upload belongs to the administrator and sshd refuses it.
  - The three things the `check` proof catches (a visible share, the Recycle Bin, a key file owned by the wrong account) each went wrong once at a first run.
- The admin guide gains an **Email** chapter written for a non-programmer: the relay and the sender; the Operator address; filling the `mail` attribute in the directory (the only source of addresses; the Directory check picks up later fixes by the next night, "Check directory now" at once); the Email page and its Test message; the nightly digest; the batch tick; what a message may and may never say; and what to do when the Status page's Email line is red.
- The admin guide gains the **Retention** content: the three settings ("Retention period", "Warning before deletion", "Recycle bin"), the 03:30 sweep, the Recycle bin page with the owner filter, the six audit rows, and the consequence that shortening the period deletes that night.
- The admin guide explains the **Folder management** toggle both ways: On adds the Cases pages at once with no announcement and resumes the paused Retention clocks; Off hides every Case from everyone, Admins included, deletes nothing, pauses every Retention clock and the Recycle bin's wait, shows the counts in the tray row, and greys Reassign and Delete data, so an Admin turns On to act on a leaver's Cases.
- The admin guide gains the two settings "Chat across cases" and "Case chat: most hours of talk per question".
- The user guide gains: the Case clock in plain words ("opening a case starts the clock over"; a Case nobody opens for 30 days goes to the Recycle bin for 30 days and is then wiped; the amber Retention warning, Keep, and the email from 7 days ahead; Restore from the Recycle bin page; a person's own Delete is final at once); the line that if the Cases pages disappear, IT has turned them off and nothing is lost; the nightly Retention digest ("one email a night listing the cases that delete soon, yours and those shared with you; the last one comes the night before"), the share and handover mails, and the batch tick; and a Case Chat page (the Chat tab, what a question reads, parts on a big Case, Citations that name the Recording, export).
- The Status page gains a Backup line and an Email line.
- At run time the server reaches the backup store on the LAN; no new egress host.

### Sources

GitHub distribution and install story (ticket 23, with the facts it gathered from the server-layout, LDAP, audit, WhisperX contract, queue, LLM features, deployment-topology, Retention policy, toggle transitions, backup, DNS-and-certificate, and directory objects tickets and tasks); ADR 0006, Gideon Transcribe's own code is a US government work dedicated under CC0 1.0; the GitHub distribution research file (`docs/research/github-distribution-facts.md`); the glossary (`CONTEXT.md`).

### Amendments applied

- Correction after the round (from the GitHub distribution research file) to Images rule 5: container images on ghcr.io are free even while private, so publishing may start at any tag before `v1.0.0`; the build path stays the fallback.
- Correction after the round (from the GitHub distribution research file) to Access rule 2: a rule on `main` cannot be set on a private Free-plan repository, so the ruleset is set at the public flip.
- From the DNS-and-certificate ticket (recorded in the ticket's Comments) to the install guide: the certificate request steps; to the admin guide: the expiry date, the renewal steps, and the DNS note.
- From the directory objects task (recorded in the ticket's Comments) to the directory checklist: the two paths, the Bind account's needs, the CA root export, the three warnings; to `./transcribe check`: the bind, group-read, member-resolve, and nested-membership checks; to First sign-in: the non-Admin member.
- From the HuggingFace token task to the egress appendix: the download hosts documented as `*.hf.co`; to `./transcribe check`: the token tested by a HEAD fetch with the HTTP codes and the stdin hand-off; to "Before you start" and the service README: the account and token facts.
- From the server-preparation task to the install guide: the server-preparation commands written out; to the install steps: the Install home empty at clone time and the certificate placed after the clone; to Access: the private-period clone through the SSH nickname with the deploy key at a Release tag; to `./transcribe check`: the three offline items and that no check reaches GitHub; the office's `.env` values kept out of the product, in the planning repository.
- From the email notifications ticket to `./transcribe install`: the Phase 2 mail questions after the Backup target; to `./transcribe check`: the two mail lines; to the guides: the Email notifications chapter, the user guide's digest and mail lines, and the Phase 2 before-you-begin additions.
- From the Case Chat ticket to the guides: the Case Chat page and the two settings (Phase 2).
- From the NAS task to the Backup and restore chapter: the ordinary account, the `/<share name>` path, the DSM steps, and the key placement; to `./transcribe install`: the existing key at `secrets/backup_ssh_key` used and a new one generated only when absent; to `./transcribe check`: the backup-target proof; to the Phase 2 before-you-begin list: the account, folder, and key.


## 3. Sign-in, accounts, and roles

This chapter fixes how a person gets into Gideon Transcribe and what they may do once in: the connection to the office's directory, who the directory must admit, the accounts the app makes for them, the two roles, the sources of admin status, the Local admin accounts that work without the directory, Login sessions, the nightly Directory check, the Deactivated and Blocked states, the users list, the directory objects an office creates before the first sign-in, and the `.env` keys that carry every office-specific value. Nothing office-specific is in code: every directory value is configuration.

### The directory connection

- The app signs users in against the office's Active Directory over LDAPS on port 636, not StartTLS. `LDAP_SERVER_URI` names the domain name, never one domain controller, so any domain controller answers: `ldaps://<domain>:636`.
- The domain controllers' certificates are validated against the office CA root, a PEM file the office exports from its certificate authority and mounts read-only into the app at the path `LDAP_CA_FILE` names. Every domain controller must present a certificate issued under that root that names the domain name in `LDAP_SERVER_URI`. The controllers' own certificates renew through the office CA; the app holds only the root. With a private office CA, which is the normal case, the app cannot connect at all without the root file. When `LDAP_CA_FILE` is unset the system trust store is used instead.
- The domain name usually resolves to several domain controllers, and one of them may sit at a continuity site over a slower link. The client library tries them in resolver order. The app sets a network timeout of 5 seconds on the directory connection (`OPT_NETWORK_TIMEOUT`, set beside the CA file option), so a slow or unreachable controller fails over to the next instead of hanging a sign-in. `.env` has no key for this timeout.
- The app binds as the Bind account, a read-only directory account named in `LDAP_BIND_USER` in the form `<bind account>@<domain>`, with the password read from the file `LDAP_BIND_PASSWORD_FILE` names. Only the app ever binds with it, always with the stored password, so the Bind account is never at risk from the sign-in throttle or the domain's lockout policy. Its password is never shown in the Admin panel.
- The Bind account needs nothing beyond an ordinary domain account's default read (Domain Users): no group memberships and no delegation. The app reads each group's own `member` list (the forward link) and never a person's `memberOf`. In a domain where `memberOf` is hidden from plain accounts (Authenticated Users removed from Pre-Windows 2000 Compatible Access), nothing changes, because group member lists stay readable and that is all the app asks for.
- People are found under `LDAP_SEARCH_BASE`, the domain's base DN. The sign-in name is `sAMAccountName`, what people type. The identity the app keeps is `userPrincipalName`. `mail` is read as well and may be missing on some accounts.
- Group membership is checked with Active Directory's "member of, in chain" matching rule against the group's member list: a search with the filter `(member:1.2.840.113556.1.4.1941:=<user DN>)` lists the group when the user is a direct or a nested member. Nested groups therefore count for both the Sign-in group and the Admin group.
- The directory treats a bind with a username and an empty password as an anonymous bind: it "succeeds" and identifies nobody. The app never sends an empty password. The sign-in form rejects an empty password before the directory is asked, and django-auth-ldap refuses one as well (`AUTH_LDAP_PERMIT_EMPTY_PASSWORD` stays `False`).
- Directory passwords are never stored or cached. The app holds no copy of any user's password, only the Bind account's, in its secrets file.
- `LDAP_ENABLED=false` gives a local-admins-only install for evaluation: no directory sign-in, Local admins only. The default is `true`.

### Who may sign in

- A directory account that is a direct or nested member of the Sign-in group or the Admin group. Either group grants sign-in, so a member of the Admin group needs no place in the Sign-in group; an Admin who cannot sign in is a state nobody wants.
- A Local admin, always, including when the directory is down.
- Nobody else: no self-signup, no local regular users, no one outside the office.

### The sign-in page

- One sign-in form, username and password, used by directory users and Local admins alike. There is no "remember me".
- The typed username is normalised first: `<user>`, `<user>@<domain>`, and `<NETBIOS>\<user>` all normalise to `<user>`, and the app account's username is the lowercased `sAMAccountName`.
- A username matching a Local admin is checked locally. Anything else goes to the directory.
- An empty password is refused by the form before the directory is asked.
- Throttle, two counts, both ending in the same wait:
  - five failures for one username-and-address pair, then a fifteen-minute wait for that pair;
  - five failures for one username in any 30 minutes, whatever the address, then the fifteen-minute wait.
  The second count exists because two addresses could otherwise push one username past the domain's own lockout policy, which locks an account for 30 minutes after 6 wrong passwords within 30 minutes (Windows' default domain policy). Together the two counts keep the rule true that nobody can lock a directory account through the app.
- When the directory cannot be reached, a directory user is refused with this notice and nothing else:

```
Sign-in is unavailable because the office directory cannot be reached. Contact IT.
```

### Accounts

- The app account is created at the first successful directory sign-in. Nobody pre-provisions users, and nothing in the app has to change when the office adds a person to the Sign-in group: the group is read live at every sign-in and again at the nightly Directory check.
- What the account holds: the username, the lowercased `sAMAccountName`; the Directory address, the `userPrincipalName`, stored and shown; the display name, from `givenName` and `sn`; and the Email address, the directory's `mail` value, read and stored at every sign-in. `mail` is optional, and Phase 1 stores it and does nothing with it.
- A Local admin account has no directory record. It is made by the command or from the Admin panel (see Local admin accounts).

### Roles

Two roles, User and Admin. There is no interpreter role: Translation is a per-Recording choice open to every User.

| Ability | User | Admin |
|---|---|---|
| Upload, Batch, Diarization and Translation choices, Correction, Chat, Summary, Word export, own Workspace | yes | yes |
| Open any user's Recordings, Transcripts, Chats, and Summaries with the owner's powers: correct, chat, export, delete (reassign to a named user is greyed out in Phase 1, see Carried for Phase 2) | no | yes; every access writes an audit row, and the screen shows the banner `Viewing <user>'s Workspace as an Admin` |
| Admin panel: settings, users list, status page, audit log viewer, "Check directory now" | no | yes |
| Set or clear the manual admin flag, block and unblock, deactivate, delete a user's data, create Local admins | no | yes, never on themselves |

Admins also see every Job in the Queue; what regular Users see of each other's Jobs is the Queue and Jobs chapter's question.

### Admin status and its sources

Admin status has three sources, and the users list shows which applies to each person:

1. **Admin group.** Membership makes a person an Admin at sign-in and at each Directory check; leaving the group removes it at the next check or sign-in. The group only ever adds: a manual toggle cannot demote a group member, so removing a group member's admin status means removing them from the group in the directory.
2. **Manual flag.** Set by an Admin on any directory account; adds admin status to someone outside the group and stays until an Admin clears it. The Directory check never touches it.
3. **Local admin.** Every local account is an Admin.

Nobody can remove their own admin status.

Admin status is a significant grant. The users list shows its source for each person, and the group that confers it is the office's choice, made in configuration (`LDAP_ADMIN_GROUP`). If a future office wants metadata-only Admins, that is a new setting, not a reinterpretation of this one.

### What Admins may open

Gideon Transcribe holds privileged, confidential material, and the obvious design would keep Admins to metadata (counts, sizes, Job states). The decision is the opposite: Admins may open any user's Recordings, Transcripts, Chats, and Summaries with the owner's powers, because IT must be able to troubleshoot a stuck Job, recover a leaver's work, and reassign material without asking the owner. The guard rails are the trade:

- Every such access writes an audit row naming the Admin, the item, and the time, with the owner as the Affected user. The audit log is not optional: it exists from the first release, and the Admin-access rows are queryable by user (see the Audit log and logging chapter).
- While an Admin is inside another user's material the screen shows the banner `Viewing <user>'s Workspace as an Admin`.
- An Admin opening a user's Workspace does not extend its life; the Workspace's idle clock belongs to its owner's Login session (see the Workspace lifecycle chapter).
- No page and no guide carries a line telling users that office IT administrators can access everything in the system. That line was withdrawn from every page and guide; the audit row and the banner are the guard rails, and ADR 0004 itself stands.

### Local admin accounts

- A Local admin is an Admin account kept inside the app, independent of the directory, so IT can sign in when the directory is down.
- The first one is created after first start by one documented command:

```
docker compose run --rm app create-local-admin
```

  It asks for the password on the terminal, so the password never sits in `.env` or in logs. The default name is `transcribe-admin`; the name is chosen at creation, and the command refuses a name that exists in the directory when the directory is reachable.
- The password goes into the office's password manager.
- Further Local admins are created from the Admin panel with "Create Local admin". Local accounts change their own password in the app.
- The app refuses to deactivate, block, or delete the last active Local admin.

### Login sessions

- A user has one Login session at a time. A new sign-in wins: the older session ends and shows this on its next request:

```
You signed in from another place; this session has ended
```

  The Workspace belongs to the user, so nothing in it is lost by the switch, and a running Batch is unaffected. The sign-out audit row records the cause "signed in elsewhere".
- Idle timeout only, admin-settable, default 8 hours. There is no absolute cap, because a session end discards the Workspace's Recordings and a cap would force a re-upload in the middle of a day.
- A running Batch counts as activity: it keeps the Workspace alive, plus the grace period the Workspace lifecycle chapter fixes.
- A warning is shown 15 minutes before the idle timeout. No "remember me".
- A session ends by logout, idle timeout, a newer sign-in, deactivation, block, or an Admin ending it. The Workspace rules then apply: deactivation, a Block, or an Admin ending a session ends the Workspace like a logout.
- Sessions already open when the directory goes down keep working until their own idle timeout.

### When the directory is down

- Local admins sign in.
- Directory users are refused with the notice under The sign-in page.
- Login sessions already open keep working until their own idle timeout, and running Jobs finish.
- The status page shows "directory unreachable since HH:MM".
- The Directory check refuses to run (see below).

### The Directory check

- Runs nightly at 03:00 office time, and on demand from the "Check directory now" button in the Admin panel.
- For each directory-backed account it confirms that the directory account exists, is enabled, and is a direct or nested member of the Sign-in group or the Admin group. Otherwise the account is Deactivated and its live sessions end.
- Admin status is re-derived from the Admin group. Manual flags and Blocks are untouched.
- Reactivation is automatic when the directory admits the person again, at the next check or the next sign-in.
- Fail-safe: if the directory cannot be reached, or the Sign-in group resolves to no members, the check refuses, changes nothing, and reports the refusal on the status page.
- Each run writes a membership snapshot and one audit row per change.
- The Admin panel shows the check's schedule, the "Check directory now" button, and the last run's result.

### Deactivated, Blocked, and leavers

- **Deactivated**: an account the Directory check found gone, disabled, or outside both groups. It cannot sign in. It is reactivated automatically when the directory admits it again.
- **Blocked**: an Admin can Block a directory account ahead of the directory. A Blocked user cannot sign in, their sessions end, and the Directory check never lifts a Block; only an Admin unblocks. The account record stays.
- Nothing in a Workspace survives the Login session, so a leaver's Workspace is discarded when deactivation or a Block ends their session, once any running Job has finished, plus the grace period. There is nothing to reassign in Phase 1.
- An Admin who Blocks or deactivates cannot do so to themselves, and the last active Local admin can be neither.

### The users list

Part of the Admin panel's Authentication section. One row per account with these columns:

| Column | Values |
|---|---|
| Username | the lowercased `sAMAccountName`, or the Local admin's name |
| Display name | from `givenName` and `sn` |
| Directory address | the `userPrincipalName`; blank for a Local admin |
| Role | User or Admin |
| Admin source | group, manual, or local |
| Status | active, deactivated, or blocked |
| Last sign-in | |
| Storage used | |

Per-user actions, all Admin-only and never on the Admin's own row: set or clear the manual admin flag (clearing does nothing for a member of the Admin group), block and unblock, deactivate, end the user's Login session, delete the user's data, and reassign to a named user, which is greyed out in Phase 1. The list also carries "Create Local admin".

### Directory objects the office creates

An office creates these in its Active Directory before the build's first sign-in test. The checklist and the ways to create the objects are the install guide's; they are recorded here so the guide and the app agree.

1. **A Sign-in group.** A global security group, in the office's groups OU. Members may sign in; members of the Admin group sign in without it. Suggested description: `Gideon Transcribe: may sign in (<Admin group> signs in without it)`. It may start empty; the office adds people in the console at any time, and the app picks them up at their next sign-in and at the nightly Directory check. The build's first sign-in test needs at least one member of the Sign-in group who is not in the Admin group, so that it covers the ordinary User role and not only Admins.
2. **An Admin group, optional.** An existing or new global security group whose members are Admins. Its DN goes in `LDAP_ADMIN_GROUP`; leave the key blank for an install with no group-derived admins.
3. **A Bind account.** A read-only service account in the office's service accounts OU, with User logon name `<bind account>@<domain>`. Before creating it, make a password manager entry and generate a long random password there, 32 characters or more; the password lives only in the password manager until the build, when `./transcribe install` asks for it and writes it to the file `.env` names in `LDAP_BIND_PASSWORD_FILE`. The account is enabled, with "Password never expires" and "User cannot change password" ticked and "User must change password at next logon" unticked; no group memberships beyond Domain Users; no delegation of any kind. Suggested description: `Gideon Transcribe LDAP bind, read-only`. Check the two tick-boxes as a directory admin: a plain account cannot read "Password never expires" or "Enabled" and may show "User cannot change password" as unticked.
4. **The office CA root as PEM.** The self-signed root of the certificate authority that issued the domain controllers' certificates, exported as a PEM file and placed at `ca/office-root.pem` under the Install home, which `.env` names in `LDAP_CA_FILE`. Nothing else from the CA is needed: the domain controllers' own certificates renew themselves.

Give the other domain controllers a minute to catch up before testing anything, whichever way the objects were created.

#### Creating the objects in the console

In Active Directory Users and Computers, as a directory admin:

- Group: in the groups OU, New, Group. Name `<Sign-in group>`, scope Global, type Security, the description above. Members tab: the first wave, or nobody.
- Account: in the service accounts OU, New, User. Full name and User logon name `<bind account>`, suffix `@<domain>`. Paste the password from the password manager. Untick "User must change password at next logon"; tick "User cannot change password" and "Password never expires". No groups beyond Domain Users. The description above. The full name is the office's choice; the app binds by the User logon name.

#### Creating the objects from PowerShell

From an ordinary PowerShell window on a workstation with the Active Directory module installed. It asks once for the directory admin's password (a small dialog) and once for the Bind account's password from the password manager (nothing echoed). One line at a time:

```powershell
Import-Module ActiveDirectory
$cred = Get-Credential <NETBIOS>\<directory admin account>
$dc = '<a domain controller, fully qualified>'
New-ADGroup -Server $dc -Credential $cred -Name '<Sign-in group>' -SamAccountName '<Sign-in group>' -GroupScope Global -GroupCategory Security -Path '<groups OU DN>' -Description 'Gideon Transcribe: may sign in (<Admin group> signs in without it)'
$pw = Read-Host -AsSecureString 'Paste the password from the password manager'
New-ADUser -Server $dc -Credential $cred -Name '<bind account>' -SamAccountName '<bind account>' -UserPrincipalName '<bind account>@<domain>' -Path '<service accounts OU DN>' -AccountPassword $pw -Enabled $true -PasswordNeverExpires $true -CannotChangePassword $true -ChangePasswordAtLogon $false -Description 'Gideon Transcribe LDAP bind, read-only'
Add-ADGroupMember -Server $dc -Credential $cred -Identity '<Sign-in group>' -Members <username>
```

Put the first wave's usernames in the last line, separated by commas, or skip that line if the group starts empty.

#### The bind test

Before the first sign-in, and again whenever the directory side changes, the office proves the objects with the same bind-and-read test that `./transcribe check` runs (next section): bind over LDAPS to `<domain>:636` against the CA root as the Bind account, read both groups by DN, resolve one member of each, and confirm the nested-membership rule. The password is typed by a person at a hidden prompt and never stored; the test refuses an empty password, because the directory would accept it as an anonymous bind and report nothing.

Two lessons recorded while the objects were first made:

- Never test a bind with a wrong password against a real account. The domain's lockout policy counts those attempts, and a handful of dry runs locked the new Bind account once. Dry-run with a name that does not exist. A locked account is unlocked by a directory admin (the console's Account tab, "Unlock account", or `Unlock-ADAccount`), or clears by itself after the policy's 30 minutes.
- "Invalid credentials" right after the account was created usually means replication has not reached the controller that answered; wait a minute and run the test again.

### The directory checks `./transcribe check` runs

`./transcribe check` runs the bind-and-read test with the values in `.env`, and reports `PASS` or `FAIL` with the failing lines:

1. The CA root file named by `LDAP_CA_FILE` is readable.
2. Bind over `LDAP_SERVER_URI` as `LDAP_BIND_USER`, with the password from `LDAP_BIND_PASSWORD_FILE`, validated against the CA root. The directory's answer to "who am I" must name the Bind account (`u:<NETBIOS>\<bind account>`). A bind that returns success with an empty identity was anonymous, which means an empty password reached the directory: fail and stop. Any other failure stops the test, because the rest needs a working bind.
3. Read `LDAP_SIGNIN_GROUP` and, when set, `LDAP_ADMIN_GROUP` by DN and count their `member` entries. A Sign-in group with no members is a note, not a failure (fine until the first wave is added). An Admin group whose members are not visible is a failure: the `member` attribute is hidden from the Bind account.
4. Resolve one member of each group: read its `sAMAccountName` and `userPrincipalName`. Note whether `memberOf` is visible to the Bind account; it is not needed either way.
5. The nested rule: a search with the filter `(member:1.2.840.113556.1.4.1941:=<that member's DN>)` must list the group.

### Libraries

A fresh implementation on django-auth-ldap with python-ldap, versions pinned at build time, with `libldap2-dev` and `libsasl2-dev` in the image build. No code is copied from any other application. What the tickets fix of the configuration: LDAPS to `LDAP_SERVER_URI` with the CA file option pointing at `LDAP_CA_FILE`; `OPT_NETWORK_TIMEOUT` of 5 seconds; `AUTH_LDAP_PERMIT_EMPTY_PASSWORD` left `False`; the Bind account and its password file; `LDAP_SEARCH_BASE` as the search base; `sAMAccountName` as the sign-in name; group membership by the in-chain `member` filter, never `memberOf`.

### Environment keys

All of these live in `.env`, the single source of truth for the directory connection. The Admin panel shows them read-only with a "Test directory connection" button; none is edited in the panel.

| Key | File | Meaning | Placeholder or example | Default |
|---|---|---|---|---|
| `LDAP_ENABLED` | `.env` | whether directory sign-in is on; `false` gives a local-admins-only install for evaluation | `true` | `true` |
| `LDAP_SERVER_URI` | `.env` | the directory, by domain name so any domain controller answers, LDAPS on 636 | `ldaps://<domain>:636` | none |
| `LDAP_CA_FILE` | `.env` | path to the office CA root PEM, mounted read-only | `ca/office-root.pem` under the Install home | none (system trust store) |
| `LDAP_BIND_USER` | `.env` | the Bind account's User logon name | `<bind account>@<domain>` | none |
| `LDAP_BIND_PASSWORD_FILE` | `.env` | path to a file holding the Bind account's password, mode 0400; written by `./transcribe install`, which asks for the password | `<path to the secrets file>` | none |
| `LDAP_SEARCH_BASE` | `.env` | the domain's base DN, under which people are found | `DC=<domain part>,DC=<domain part>` | none |
| `LDAP_SIGNIN_GROUP` | `.env` | the Sign-in group's DN | `CN=<Sign-in group>,<groups OU DN>` | none |
| `LDAP_ADMIN_GROUP` | `.env` | the Admin group's DN | `CN=<Admin group>,<groups OU DN>` | blank (no group-derived admins) |

The 5-second network timeout has no key. The Bind account's password lives only in the file `LDAP_BIND_PASSWORD_FILE` names, never in `.env`, the panel, or logs.

### Audit rows

The Audit log chapter fixes the row names, fields, and Reason classes; this chapter's behaviour writes these rows:

| Row | Written when |
|---|---|
| Sign-in success | a sign-in succeeds, local or directory |
| Sign-in failure | a sign-in fails, with the Reason class |
| Sign-out | a Login session ends by logout; carries the cause, including "signed in elsewhere" when a newer sign-in ended it |
| Idle timeout | a Login session ends by the idle timeout |
| Admin access | an Admin opens another user's Recording, Transcript, Chat, Summary, or Workspace; names the Admin, the item, and the time, with the owner as the Affected user |
| Admin flag set, Admin flag cleared | an Admin sets or clears the manual admin flag |
| Block, Unblock | an Admin blocks or unblocks a user |
| Directory check snapshot | each Directory check run, with the membership snapshot |
| Directory check change | each change a Directory check makes: a deactivation, a reactivation, admin status gained or lost through the Admin group; one row per change |
| Local admin created | a Local admin is created by the command or from the Admin panel |
| Local admin password changed | a local account changes its own password |

### Settings

The Admin panel's Authentication section, whose rows the admin settings catalogue holds:

- The directory facts from `.env` (every key in the Environment keys table), shown read-only, with the "Test directory connection" button.
- Idle timeout: the Login session idle timeout, admin-settable, default 8 hours.
- Directory check schedule: nightly at 03:00 office time, shown with the "Check directory now" button and the last run's result, including a refusal.
- The users list, above.

The grace period that follows a session's end is the Workspace lifecycle chapter's setting; this chapter only relies on it.

### Left to the build

- The idle timeout's range. Fixed: admin-settable, default 8 hours, no absolute cap. Not fixed: the lowest and highest values an Admin may set.
- The form of the warning 15 minutes before the idle timeout. Fixed: that it exists and when it comes.
- The exact username normalisation. Fixed: `<user>`, `<user>@<domain>`, and `<NETBIOS>\<user>` all become `<user>`. Not fixed: how the app knows the suffix and the prefix to strip; `.env` carries no key for the domain's NetBIOS name.
- What "Test directory connection" checks and reports. Fixed: the button's name and that the facts beside it are read-only. The tickets do not say whether it runs the same bind-and-read test as `./transcribe check`.
- How `./transcribe check` performs its directory checks. The recorded test used OpenLDAP's `ldapwhoami` and `ldapsearch`; the checks it must make are fixed above.
- The rest of the django-auth-ldap configuration beyond what Libraries fixes: the user search filter, attribute mapping, and connection options.
- The content of the Directory check's membership snapshot and where it is kept. Fixed: one per run, and one audit row per change (see the Audit log and logging chapter).
- The Reason classes a failed sign-in records (the Audit log and logging chapter).
- The exact labels of the users list's actions and status values beyond the words used above.
- Whether an Admin's manual deactivation is lifted like one the Directory check made. Fixed: reactivation is automatic when the directory admits the person again, and Block is the state only an Admin lifts.
- The `create-local-admin` command's prompts beyond the password. Fixed: it asks for the password on the terminal, the default name is `transcribe-admin`, the name is chosen at creation, and a name that exists in the directory is refused when the directory is reachable.
- Whether the delete action on a Local admin removes the account. Fixed: the roles table lists the deletion of user data, and the last active Local admin can be neither deactivated, blocked, nor deleted.

### Carried for Phase 2

- **Reassign to a named user.** Greyed out in the users list until Phase 2, when it acts on Cases: a leaver's Cases are reassigned by an Admin (see the Cases chapter). In Phase 1 there is nothing for it to act on.
- **The Email address.** Phase 1 stores the directory's `mail` value at every sign-in and does nothing with it. From Phase 2: the Directory check refreshes it, nightly and on "Check directory now", and writes an "Email address updated" audit row when it changes, so a value filled in after the account was made reaches the app by the next night or at once, and a value removed in the directory is removed in the app. Nobody types an address for a directory account. The users list shows an "Email" column beside "Directory address", with "No email address" on blank rows and a filter for them. A Local admin gets an optional Email typed on "Create Local admin" and editable on its row; `transcribe-admin` has none by default. Deactivated and Blocked accounts are never mailed. `./transcribe check` counts the members of the Sign-in group without a `mail` value. Before the Phase 2 install the office fills `mail` for every member of the Sign-in group; the fix is always made in the directory. The Bind account's ordinary read covers `mail`.

### Sources

"LDAP sign-in, roles, and the local admin"; "Create the directory objects: sign-in group and bind account"; ADR 0004 "Admins can open any user's content, and every such access is audited".

### Amendments applied

- From the queue ticket, to the Login session rules of "LDAP sign-in, roles, and the local admin": one Login session per user, a newer sign-in wins, the older session's message, and the sign-out row's cause "signed in elsewhere"; replaces "several concurrent sessions per person are fine".
- From the Workspace lifecycle ticket, to the leavers' data rule of "LDAP sign-in, roles, and the local admin": a leaver's Workspace is discarded when deactivation or a Block ends the session, and "reassign to a named user" is greyed out until Phase 2; replaces "Chats and Summaries are kept until an Admin deletes them or reassigns them".
- From the directory objects task, to the directory connection and throttle of "LDAP sign-in, roles, and the local admin": several domain controllers and the 5-second network timeout; the empty-password anonymous bind and its refusal; the added per-username five-in-30-minutes throttle count; `memberOf` hidden changes nothing.
- From the Upload page ticket, to the roles of "LDAP sign-in, roles, and the local admin": the line "office IT administrators can access all material in this system" withdrawn from the upload screen and the user guide; ADR 0004 unchanged.
- From the email notifications ticket, to the accounts, Directory check, users list, and Local admins of "LDAP sign-in, roles, and the local admin": `mail` is the Email address, read at every sign-in; Phase 1 stores it and does nothing with it; the Directory check refresh, the audit row, the Email column and filter, and the Local admin's Email carried for Phase 2.
- From the server-preparation task, to the bind test of "Create the directory objects: sign-in group and bind account": `./transcribe check` takes over the bind test's job; the interim test script and its folder go at the build's first run.
- From the email notifications ticket, to "Create the directory objects: sign-in group and bind account": the Bind account's ordinary read covers `mail`; the office fills `mail` for every member of the Sign-in group before the Phase 2 install.


## 4. Media handling

This chapter follows a Recording from the browser to the WhisperX service and back to the player: how the bytes arrive, how they are checked, what is made from them, where everything lives on disk, and how the browser is served. The Clip model is in the chapter "Clips"; Job states and every reason class beyond upload refusals are in the chapter "Queue and Jobs"; the translation rules are in the chapter "Transcription, translation, and diarization choices"; the Workspace discard rules are in the chapter "Workspace lifecycle". The facts behind this chapter's tooling choices (upload libraries, the WhisperX loader, browser playback limits, ffmpeg, loudness normalisation, channel tests, waveform tooling) are in the media pipeline research file.

### Principles

1. The uploaded bytes are never changed, never served to the browser, and never downloadable. The file of record lives outside the app. The uploaded bytes exist to be hashed, inspected, and turned into the ASR audio and the Playback copy.
2. Nothing is discarded before the WhisperX service hears it: no trimming, no silence removal, no track dropping. Every channel and every audio track that carries distinct sound is transcribed.
3. The app owns all media work. The WhisperX service receives one prepared file per Side and does recognition only.
4. All media work runs in a media worker container, never in the web process, on CPU only.

### Upload transport

- Uploads are resumable and travel in pieces over the tus protocol. The official tus server (`tusproject/tusd`, MIT licence, pinned) runs as a sidecar container in the app stack. It receives the pieces into `<App data folder>/uploads/` and calls the app's hook endpoint twice for every upload:
  - **pre-create**: is there a valid Login session; is the declared size within the Largest file setting and the user's quota; is the Batch under the Files per Batch setting.
  - **post-finish**: register the file and start the pipeline.
- The browser uses Uppy with its tus plugin (`@uppy/core` and `@uppy/tus`, MIT), or plain tus-js-client (MIT).
- The app's Caddy passes `/files/*` to the sidecar without buffering. Large bodies never pass through Python. Caddy streams request bodies by default (its `request_buffers` option is opt-in, so it must not be turned on for this route); its `request_body max_size` directive is available as a cap on the route. The sidecar runs with `-behind-proxy` so it honours `X-Forwarded-Host` and `X-Forwarded-Proto`. The chapter "Architecture and deployment" places the route and names the containers; the shape the media pipeline research file gives is:

```
tusd -behind-proxy -base-path /files/ -upload-dir <App data folder>/uploads \
     -max-size <Largest file, in bytes> \
     -hooks-http http://<app container>:<port>/upload-hook/ \
     -hooks-enabled-events pre-create,post-finish
```

  with Caddy routing `handle_path /files/*` to the sidecar. tusd's hook events are pre-create, post-create, post-receive, pre-finish, post-finish, pre-terminate, and post-terminate; post-finish fires after all upload data is received. The app implements only the two hook endpoints.

- Up to three files upload at once per browser. Uploads start only when the user presses "Upload and transcribe" on the Upload page (see the chapter "Upload page and Batch page"); nothing is sent before, and there is no draft Batch.
- The size cap is checked three times: in the browser before the first byte, by the sidecar (`-max-size`), and by the pre-create hook. Duration is known only after the probe, so the Longest Recording cap is applied then, and an over-length file is refused after upload with a plain message.

#### Abandoned and stale uploads

- Leaving the Upload page abandons its unfinished uploads. The browser shows its own leave-page dialog, which the app cannot word; the page itself carries the warning (its wording is in the chapter "Upload page and Batch page"). The user starts over on return.
- A momentary network drop inside the page retries by itself, invisibly.
- **The ten-minute rule.** An upload that receives nothing for ten minutes is dropped and its Recording removed, so an unfinished upload can never hold a user's one Batch open.
- The sidecar's pieces are swept as a backstop: the daily sweeper (below) removes upload pieces older than 24 hours.

### Acceptance

- Every finished upload is opened with ffprobe (`-v error -show_format -show_streams`, JSON output). The JSON is kept as part of the Provenance. Extension and declared type are ignored.
- A file is **accepted** when at least one audio stream exists and a short test decode of it succeeds: the first ten seconds, with the forced-decoder fallback described under "The ASR audio".
- Video without sound is refused. Archives are not unpacked in Phase 1; bulk means selecting many files.
- The Upload page lists formats that usually work (mp4, mov, m4a, mp3, wav, wma, ogg, webm, mkv, avi, flac, amr, 3gp), but the probe decides.
- A Recording's title defaults to the original file name without its extension. The title is editable at upload and can be renamed later; the original name stays in the Provenance.
- A refused file never becomes a Recording; its pieces are removed at once.

#### Upload refusals

Every refusal has one plain message for users and one reason class for Admins; the classes sit in the same catalogue as the Job reason classes (chapter "Queue and Jobs") and never make a Job. The figures in the messages come from the settings named.

| Message shown to the user | When it is decided | Reason class |
|---|---|---|
| `Zip files are not accepted. Choose the recordings inside it instead.` | Before upload, in the browser (an archive is never sent) | a format class; identifier left to the build |
| `The file is empty` | Before upload | a format or size class; identifier left to the build |
| `Over the size limit (10 GB)` (the Largest file setting) | Before upload in the browser; again by the sidecar's `-max-size` and the pre-create hook | `too_large` |
| `This file has no audio track` | After checking (the probe finds no audio stream) | a format class; identifier left to the build |
| `The audio in this file could not be decoded` | After checking (the ten-second test decode fails, fallback included) | a format class; identifier left to the build |
| `This file is incomplete: its index was never written, usually because the export or the copy was cut short. Play it on your own computer; if it will not play there either, export it again from the system it came from.` | After checking: the probe reports an MP4 whose index (the moov box) is missing, which a camera or an export writes last (v1.44.0) | `incomplete_file` |
| `Over the length limit (6 hours)` (the Longest Recording setting) | After checking (duration is known only from the probe) | `too_long` |
| `You already have this file in your recordings as <title>` | After checking: same SHA-256 and same user. Other users' files are never checked, so no user learns what another has uploaded. On the Batch page the title is a link to the recording it already is (v1.44.0) | a duplicate class; identifier left to the build |
| `This batch would go over your storage space (52 of 50 GB). Remove some files, or delete recordings you no longer need. IT can raise your space.` (the figures are the user's own after this Batch and their quota) | Before upload: on the Upload page, and by the pre-create hook | `quota_exceeded` |
| `A batch can hold up to 25 files. Remove N to continue.` (the Files per Batch setting) | Before upload: on the Upload page, and by the pre-create hook | `limit_exceeded` |
| `You have a batch in progress; wait for it to finish.` | When the Upload page opens or Submit is pressed while the user's one unfinished Batch exists | `batch_in_progress` |
| `Transcription is not available right now. Try again later.` | When the Upload page opens and when Submit is pressed, if the WhisperX service liveness check fails; no Batch is created | `service_unreachable` |
| `Uploading is paused because the server is low on space. Ask IT.` | Before upload, while free space on the App data folder is below the Minimum free disk space setting | `disk_full` |

### Sides

**A Side is one distinct sound source of a Recording that is transcribed on its own.** Most Recordings have one Side. A Side's Segments are merged into the one Transcript by time, and Speakers are labelled by Side. A Job holds one Run per Side; the merge is the Queue's work (chapter "Queue and Jobs").

#### Audio tracks

If the container carries more than one audio track, the tracks are compared with the tests below. Identical tracks: use one. Distinct tracks: each becomes a Side, named "Track 1", "Track 2", so nothing on any track is missed. The Provenance says "N audio tracks found, M distinct, transcribed separately". No file in the sample corpus has more than one track; this is a rule for the build to follow without a sample to test on.

#### Two-channel calls

A two-channel track is tested for genuinely different channels with three ffmpeg measurements, each a `-f null -` pass:

```
# phase and mono-sequence detection: dual-mono logs "mono" for essentially the whole file; one party per channel does not
ffmpeg -i <track> -af "aphasemeter=video=0:phasing=1:duration=1:tolerance=0.001" -f null -

# per-channel RMS and peak levels (lavfi.astats.<n>.RMS_level and so on); also catches a silent channel
ffmpeg -i <track> -af "astats" -f null -

# the left-minus-right difference signal: an overall RMS tens of dB below each channel's own RMS means identical channels
ffmpeg -i <track> -af "pan=1c|c0=c0-c1,astats" -f null -
```

- Channels that differ materially on narrowband audio (8 kHz, or a phone-system container) mark the Recording as a **Two-channel call**, and each channel becomes a Side, named "Side 1" and "Side 2". `channelsplit` writes each channel to its own stream when separate files are wanted.
- The thresholds are build constants, tuned on the sample corpus's Two-channel call files (the phone-system exports with G.729 in WAV and the two-channel inmate-call MP3) and documented in code. They are not admin settings.
- An ordinary stereo track (interview recorder, body-worn camera) whose channels differ only slightly is not a Two-channel call; it is mixed to one Side.

#### Diarization on a multi-Side Recording

- Diarization is always the user's choice, made at upload with a speaker-count hint. The app cannot know a Recording is a Two-channel call until it is checked, after the user's choices are in, so the user's Diarize choice is honoured and nothing is switched off.
- With Diarize ticked, Diarization runs on each Side separately, using "Let the app decide" for each Side whatever the hint says (an "Exactly 2" meant for the whole call would be wrong for one Side). A Side that comes out with one Speaker is labelled by its Side alone ("Side 1"); a Side with more is labelled "Side 1 Speaker 1", "Side 1 Speaker 2", "Side 2 Speaker 1". So a two-party call reads as it would without Diarization and a three-way call (a phone passed around on one side) comes out right the first time, with nothing run twice.
- With Diarize unticked, the Sides are the Speakers.
- The Provenance records the hint as applied per Side. The Runs of a Two-channel call carry an empty hint (chapter "Queue and Jobs").
- Under Translation a Two-channel call still has Sides as Speakers but no word timing (chapter "Transcription, translation, and diarization choices").

#### The speaker-count hint

Three shapes: "Let the app decide" (the default), "Exactly N", and "Between N and M". Set per Recording at upload with a Batch-wide default; the WhisperX service contract carries all three (the WhisperX service API document).

### The ASR audio

- One file per Side: WAV, 16 kHz, mono, 16-bit PCM. This is the format WhisperX's own loader produces, so it passes through the service untouched. The loader runs, verbatim:

```
ffmpeg -nostdin -threads 0 -i <file> -f s16le -ac 1 -acodec pcm_s16le -ar 16000 -
```

  and reads raw signed 16-bit little-endian PCM from stdout (divided by 32768 to float32). It accepts anything ffmpeg can demux and decode and, given several audio streams, takes the one with the most channels; that is why the app, not the service, chooses what is heard.

- The ASR audio is made with the app's pinned ffmpeg (see "The ffmpeg pin"). When the probe reports an unknown codec inside a WAV container, the decode is forced with `-c:a g729`; this is the forced-decoder fallback, used by the acceptance test decode as well.

#### Preprocessing profiles

The Preprocessing profile is automatic: the Preprocessing profile setting fixes the default, there is no per-upload choice in Phase 1, and the Upload page shows it read-only.

| Profile | What it does | Status |
|---|---|---|
| **Standard** (the default) | Decode the Side; remove DC offset (high-pass at 20 Hz); resample to 16 kHz mono; loudness normalisation with ffmpeg `loudnorm` in two-pass linear mode (pass one measures, pass two applies): target -16 LUFS integrated, true peak -1.5 dBTP, loudness-range target set high (20 LU) so the transparent linear mode holds and the change is a pure volume scale. No band filtering, no noise reduction. | Ships |
| **Off** | Decode, DC removal, resample only. | Ships |
| **Phone** | Band filter and gentle noise reduction for narrowband calls. | Candidate, not shipped: added as a third profile only if the Phase 1 benchmark gate shows it measurably lowers errors on the jail-call and phone files |

`loudnorm` facts the build works from: its defaults are I = -24 LUFS, LRA = 7, TP = -2 dBTP (the app overrides all three as above); pass one is `loudnorm=...:print_format=json` to a null output; pass two carries the four `measured_*` values from pass one and `linear=true`, otherwise the filter reverts to dynamic mode; in dynamic mode the stream is upsampled to 192 kHz for true-peak detection, so the output sample rate is always set explicitly with `-ar`. If the normaliser still reverts to dynamic mode, the Provenance records "dynamic".

The pipeline never trims, never removes silence, never drops a track. Voice-activity decisions happen inside the WhisperX service, and any voice-activity setting that could lose quiet speech is a recorded setting there; the Phase 1 benchmark gate includes a "dropped speech" check on the jail calls (the WhisperX service API document).

### The Playback copy

Every Recording gets exactly one Playback copy; the player never touches the uploaded bytes. Chrome and Edge cannot play PCM inside mp4 (the interview-room video), G.729, or HEVC without hardware support, and they seek imprecisely in variable-bitrate mp3; one predictable copy removes all of that.

| Recording | Playback copy |
|---|---|
| Audio-only | AAC in an m4a container, 96 kbps for one channel, 128 kbps for two, `-movflags +faststart` |
| Video | mp4 with H.264 video and AAC audio, `-movflags +faststart`. The video stream is copied unchanged when it is already H.264 at or below 720p (a body-worn camera mp4 is a fast remux, well under a minute); otherwise it is re-encoded with libx264, preset veryfast, CRF 23, scaled to at most 720p, frame rate unchanged |

- **Sound**: the same loudness normalisation as the ASR audio, applied with the values measured in pass one, so what the listener hears is what the model heard. The Provenance states "loudness normalised (linear, -16 LUFS)". The file of record outside the app stays the faithful one.
- **Channels**: kept as recorded for a Two-channel call (one side per ear); distinct audio tracks are mixed into the Playback copy so the listener hears everything; a single stereo track stays stereo.
- Always `+faststart`: a movie plays as it downloads only when its index (the moov atom) is at the front, and ffmpeg writes it at the end unless told otherwise. Never serve variable-bitrate MP3 for playback.
- Recognition never waits for the Playback copy. The viewer and the Batch page show "Preparing video" or "Preparing audio" until it is ready.
- CPU only, with a thread cap per transcode (`MEDIA_THREADS_PER_JOB`, default 8) and at most `MEDIA_CONCURRENT_JOBS` (default 4) media jobs at once, both in `.env`. GPU encoding (NVENC) is revisited only if real body-worn camera files prove slow; the app stack has no GPU, and the GPUs stay with the WhisperX service.

### Waveform peaks

- BBC `audiowaveform` (GPL-3, run as a separate command-line process, never linked into the app) produces JSON peaks from the Playback copy's audio: 8-bit, about 8,192 pairs for the whole Recording whatever its length (the zoom is the Recording's samples divided by 8,192, never finer than 256 samples per pair), split channels for a Two-channel call. The Timeline draws the whole Recording at the width of the page and never zooms, so a fixed count, a few pairs per pixel on the widest screen, is all it can use, and the file stays under 100 KB for a six-hour Recording. The file is stored beside the Playback copy as `waveform.json`.

```
audiowaveform -i <audio> -o waveform.json -z 256 -b 8
```

- audiowaveform is not in the Debian archive; the project publishes `.deb` files on its GitHub Releases for Debian 10 to 13 (`audiowaveform_1.10.2-1-13_amd64.deb` for Debian 13; the 1.10.3 tag ships no binaries and is functionally identical). Its inputs are MP3, WAV, FLAC, Ogg Vorbis, and Opus. Its JSON carries `version, channels, sample_rate, samples_per_pixel, bits, length, data` (interleaved min and max integer pairs).
- The viewer decides how the peaks are drawn (chapter "Transcript viewer and player"); wavesurfer.js (BSD-3) accepts pre-computed peaks through `load(url, channelData, duration)`, with the integer pairs converted to floats (divide by 128 for 8-bit data) first.

### Clips on the media worker

The Clip model, its options, page, limits, and lifecycle are in the chapter "Clips". The media facts fixed here: a Clip is rendered from the Playback copy, never from the uploaded bytes; renders run on the media worker within its concurrency; a render fails after the length of the Clip plus five minutes, or on an ffmpeg error, with the reason class `clip_render_failed`, and is stopped when the Recording goes; a Clip can be made as soon as playback readiness is Ready (steps 6 and 7 below), before the Transcript exists, and carries every Side as the Playback copy does. On disk a Clip lives under its Recording's folder as `clips/<clip id>.mp4` or `.mp3` and nothing else is stored beside it; the transcript excerpt and the caption file are built from the live Transcript at download time. The Longest Clip setting is 30 minutes.

### The Provenance record

Kept for every Recording, shown in the Details panel, and printed on every export (chapter "Exports"). Its fields are fixed:

- original file name
- size
- SHA-256 of the uploaded bytes
- uploader and upload time
- container, codecs, streams, channels, sample rate, duration
- audio tracks found and used
- whether it is a Two-channel call and the measurements behind that call
- the Sides
- the Preprocessing profile and whether the normaliser ran linear or dynamic
- loudness values measured and applied
- ASR model and version
- the Diarization choice and the speaker-count hint, as applied per Side
- the Translation choice
- Vocabulary used
- WhisperX service version
- processing start and finish per step
- pipeline version
- the raw ffprobe output
- for each Clip, its span, options, and render time (a deleted Clip drops out of these lines)

Never the content of the Transcript.

### Storage layout

`<App data folder>` is this app's own folder on the server's data drive; the chapter "Architecture and deployment" fixes its path and owner. Nothing this app stores goes anywhere else on the server.

```
<App data folder>/
  uploads/                                unfinished uploads, owned by the tus sidecar
  scratch/<user id>/<recording id>/
    original.<ext>                        the uploaded bytes, read-only after hashing
    probe.json                            the raw ffprobe output
    asr-side1.wav                         the ASR audio, one file per Side (asr-side2.wav, ...)
    playback.m4a  or  playback.mp4        the Playback copy
    waveform.json                         the peaks
    clips/<clip id>.mp4  or  .mp3         rendered Clips, nothing else beside them
  test-corpus/                            the office's sample recordings (see "Kinds of recordings")
```

- Ids only: no original file name, user name, or title ever appears in a path.
- **Failure**: nothing is deleted because a step failed. The Recording shows "Failed: <plain reason>" with Retry; a Retry reuses the steps that already succeeded. A refused upload's pieces are removed at once.
- A Recording's whole folder goes together when the Recording is deleted or its Workspace ends (chapter "Workspace lifecycle").

#### The daily sweeper

The sweeper runs daily at 03:30, after the Directory check. It removes upload pieces older than 24 hours and any folder on disk with no matching database row, and it logs what it removed. Its run is an audit row (below).

#### Quotas and the storage warning

- Everything on disk for a user's Recordings (uploaded bytes, ASR audio, Playback copy, waveform, Clips) counts toward that user's quota, shown on the users list of the admin panel. The Default Workspace quota per user setting (50 GB) fixes the default, and the users list allows a per-person override.
- The pre-create hook refuses an upload that would exceed the quota (`quota_exceeded`, the message in the refusals table).
- Users see no storage meter and no figure while there is room. A warning appears only near the limit: on the Upload page when the Batch would take the user past 80% of their space (`You are close to your storage space: 42 of 50 GB after this batch`), turning into the refusal when it would pass it; on the Recordings page the same warning once past 80%. The 80% is a build constant, not a setting.

#### Limits

All admin-settable in the Limits section of the admin settings catalogue; their ranges are there and are not repeated here.

| Setting | Default | Where it bites |
|---|---|---|
| Largest file | 10 GB | the browser before the first byte, the sidecar's `-max-size`, the pre-create hook; `too_large` |
| Longest Recording | 6 hours | after the probe; `too_long` |
| Files per Batch | 25 | the Upload page and the pre-create hook; `limit_exceeded` |
| Default Workspace quota per user | 50 GB, with a per-user override on the users list | the pre-create hook; `quota_exceeded`; the 80% warning |
| Minimum free disk space | 200 GB | before upload; `disk_full` |
| Longest Clip | 30 minutes | saving a Clip (chapter "Clips") |

A 6-hour body-worn camera export at a typical bitrate is about 13 GB, so an office with such files raises Largest file.

### The media worker and the processing order

All media work runs in the media worker container, on CPU only, never in the web process. Its concurrency (`MEDIA_CONCURRENT_JOBS`, `MEDIA_THREADS_PER_JOB`) is separate from the serial Queue. For each accepted upload it runs, in order:

1. hash (SHA-256 of the uploaded bytes);
2. probe and acceptance (the refusals table, the duplicate check included);
3. track and channel analysis (Sides);
4. ASR audio per Side;
5. hand the Job to the app's Queue; the WhisperX service may start now. A Recording is Ready after step 4, and a Job for a multi-Side Recording is one Run per Side, merged by time;
6. the Playback copy, in parallel with recognition;
7. the waveform, in parallel with recognition.

Media states of a Recording, with playback readiness as a separate flag:

| Media state | Meaning |
|---|---|
| Uploading | pieces arriving |
| Checking | steps 1 to 3 |
| Preparing | step 4 |
| Ready | ready for transcription (handed to the Queue) |
| Rejected | refused; never a Recording in the user's list beyond the Batch page's refused row |
| Failed | a media step failed; "Failed: <plain reason>" with Retry (reason class `media_failed`, chapter "Queue and Jobs") |
| Playback readiness | Preparing, then Ready (steps 6 and 7) |

Job states belong to the chapter "Queue and Jobs". The admin status page shows media jobs running and upload pieces pending (chapter "Admin panel").

### Serving media to the browser

The app's own Caddy serves Playback copies, waveform data, and Clip files straight from disk with HTTP range support, after asking the app (forward auth) whether the current Login session may see that file: the owner, or an Admin, audited. Multi-gigabyte streams never pass through Python. The chapter "Architecture and deployment" places the route.

Browsers: current Microsoft Edge and Google Chrome are required; Firefox is best-effort; no Safari or mobile commitment in Phase 1.

### The ffmpeg pin

- The worker image carries ffmpeg from the Debian 13 package (7.1.x; Debian 13 ships `7:7.1.5-0+deb13u1`, and the `python:3.12` and `python:3.12-slim` images are Debian 13 based). The image build verifies that `ffmpeg -decoders` lists `g729`; ffmpeg's G.729 decoder is decode-only and native, and Debian's build disables no decoders.
- Why the version matters: an ffmpeg 7 build identifies G.729 inside a WAV container on its own; ffmpeg 5.1.9 (Debian 12's package) reports the codec as unknown and decodes it only when forced with `-c:a g729`. The pin removes the first failure and the forced-decoder fallback stays for the second.
- Licences in the images (chapter "Repository, releases, and distribution"): ffmpeg from Debian; audiowaveform GPL-3 as a separate command; tusd MIT.

### Kinds of recordings an office will meet

The sample corpus is an office asset: real, privileged recordings that never enter the repository and are listed nowhere in the product. What a build's corpus must contain is fixed by kind, so that every decision below is judged against evidence and not clean studio audio.

| Kind | Container, video, audio (as met) | Typical length and size | What it teaches |
|---|---|---|---|
| Body-worn camera export | mp4; H.264 1280x720 at about 30 fps; AAC 48 kHz stereo at about 47 kbps | about 50 minutes, 1.8 GB (about 5 Mbps) | the largest files; a fast remux for playback; real exports run longer than the samples |
| Clean recorded interview | mp3; MP3 44.1 kHz stereo, 192 kbps | about 20 minutes, 27 MB | the easy case; ordinary stereo, not a Two-channel call |
| Interview-room camera | mp4; H.264 1280x720 at about 15 fps; PCM s16le 8 kHz mono | about 1 hour 44 minutes, 260 MB | PCM in mp4 does not play in Chrome or Edge; the longest sample; 8 kHz audio in a video |
| Phone-system (jail) exports | wav; G.729 8 kHz, 2 channels, 16 kbps | 17 to 32 minutes, 2 to 4 MB | G.729 inside WAV; no browser plays it; Two-channel calls with one party per channel |
| Inmate phone call export | mp3; MP3 8 kHz, 2 channels, 16 kbps | about 22 minutes, 2.6 MB | a Two-channel call in an ordinary container |
| Old phone or logger recordings | plain MP3 under `.v08` and `.v09` extensions; MP3 8 kHz mono, 16 kbps | 15 to 21 minutes, about 2 MB | extension and content disagree; accept by sniffing, never by extension |
| Office phone-system calls | mp3; MP3 8 kHz mono, 64 kbps | 4 to 7 minutes, 2 to 3 MB | narrowband office calls |
| Handheld recorder | mp3; MP3 44.1 kHz stereo, 128 kbps | about 7 minutes, 6 MB | ordinary stereo |
| Camera video, source unknown | mp4; H.264 1280x720 at about 30 fps; AAC 48 kHz mono at about 67 kbps | about 25 minutes, 900 MB | a video whose provenance is unknown |

What the samples taught, and what the corpus must therefore keep exercising:

- **G.729 inside WAV.** The phone-system exports are G.729 audio in a WAV container. A recent ffmpeg identifies and decodes it; an old one reports the codec as unknown and decodes only when forced. Hence the ffmpeg pin, the forced-decoder fallback, and the unavoidable transcode for playback.
- **Extension and content disagree.** Recordings arrive under extensions that mean nothing (`.v08`, `.v09`); acceptance sniffs with ffprobe and never trusts the extension.
- **Two-channel calls with one party per channel.** The G.729 exports and the inmate-call MP3 are two-channel with a party per channel: a cheap exact speaker split before Diarization, and the files the detection thresholds are tuned on.
- **Narrowband dominates.** Ten of the fourteen sample files are 8 kHz, and the interview-room video carries 8 kHz PCM. Normalising to 16 kHz mono for ASR is a resample up, not down, so quality decisions are judged on these files.
- **Size and length.** The largest sample is 1.8 GB and the longest 1 hour 44 minutes, both far inside the Largest file and Longest Recording defaults; real body-worn camera exports run longer, which is why both are settings.
- **Slots still owed.** A Spanish-language call and a mixed-language interpreter-mediated interview are not yet in the sample corpus; every sample is in English. A true over-two-hours recording is optional. No file has more than one audio track.

Corpus handling rules: the files live at `<App data folder>/test-corpus/` on the server, never in any repository and never tracked by git; they are copied under neutral slot names (the originals' names carry personal names and phone numbers, which appear nowhere but in an `ORIGINAL-NAMES.txt` kept beside the files); a `SHA256SUMS.txt` beside them is verified after every copy; the folder is owner-only (mode 700, files 600).

```
cd <App data folder>/test-corpus && sha256sum -c SHA256SUMS.txt
ffprobe -v error -show_format -show_streams <file>
```

### The benchmark gate's media legs

The Phase 1 benchmark gate runs against the corpus folder. Its media legs are:

- **The Phone profile decision.** Phone ships as a third Preprocessing profile only if the gate shows it measurably lowers errors on the jail-call and phone files against Standard.
- **The ffmpeg identification.** The image build's check that `ffmpeg -decoders` lists `g729`, and the gate's confirmation that the pinned ffmpeg identifies and decodes G.729 inside WAV on its own while the `-c:a g729` fallback still works when forced.
- **The "dropped speech" check** on the jail calls belongs to the WhisperX service contract (the WhisperX service API document): nothing the service's voice-activity settings do may lose quiet speech.

### Environment keys

| Key | File | Meaning | Placeholder or example |
|---|---|---|---|
| `MEDIA_THREADS_PER_JOB` | `.env` | thread cap per ffmpeg transcode on the media worker | `8` |
| `MEDIA_CONCURRENT_JOBS` | `.env` | media jobs the worker runs at once | `4` |
| `<App data folder>` | fixed by the chapter "Architecture and deployment", which names its `.env` key | the app's own folder on the data drive, holding `uploads/`, `scratch/`, and `test-corpus/` | `<App data folder>` |

Both `MEDIA_` values are shown read-only on the admin panel's Installation page.

### Audit rows

| Row | When it is written |
|---|---|
| upload accepted | after step 2: original file name, size, duration, hash, detected format, Sides found |
| upload rejected | at a refusal, with its reason class |
| Recording deleted | by the owner, by an Admin, or by the Discard at the last sign-out |
| Playback copy served to an Admin for another user's Recording | when forward auth admits an Admin to a file that is not theirs; the affected user is filled |
| daily sweeper ran | at 03:30, with counts and sizes |
| quota refused an upload | when the pre-create hook refuses for quota |

The Clip rows (created, re-rendered, downloaded, deleted) are in the chapter "Clips".

### Settings

By their names in the admin settings catalogue: Largest file, Longest Recording, Files per Batch, Default Workspace quota per user (with the per-user override on the users list), Minimum free disk space, Longest Clip (Limits); Preprocessing profile (Transcription defaults; recorded in every Provenance); Model, Diarization ticked by default, and Speaker-count hint default (Transcription defaults; recorded in the Provenance as applied). Fixed rules, not settings: three uploads at once per browser; the ten-minute rule; the 24-hour sweep; the 80% warning; the Two-channel call detection thresholds; the sweeper at 03:30.

### Not in this phase

- No pause banner and no resuming of an upload across leaving the page; leaving abandons the uploads. (A builder could assume tus resumability across page loads; only the in-page retry after a momentary drop exists.)
- No archive unpacking, and no per-upload choice of Preprocessing profile.
- No downloading of the uploaded original, ever.
- No matching of a file uploaded again to an earlier Recording; it is a new Recording, processed from scratch.
- No GPU encoding, and no Phone profile, unless the gate admits it.

### Left to the build

- The Two-channel call detection thresholds: build constants tuned on the corpus's Two-channel call files, documented in code, never admin settings.
- The reason-class identifiers for the refusals whose names the tickets did not fix (no audio track, undecodable audio, empty file, duplicate file, archive). Constraints: one class per refusal; the user's message is fixed in the table above; the class name is what Admins see; the classes live in the one catalogue with the Job classes; the audit row "upload rejected" records the class.
- Whether a refusal decided in the browser before any byte is sent (archive, empty, over the size limit) is reported to the app so that "upload rejected" is written; the tickets fix the row and its classes (format, size, duration, quota, Batch limit) but not the reporting path.
- How the sidecar's `-max-size` follows the Largest file setting, which an Admin can change in the panel while the sidecar's flag is fixed at start. Constraint: the pre-create hook enforces the live value; the flag is the backstop and must never be lower than the setting.
- The exact ffmpeg command lines. The tickets fix every parameter (20 Hz high-pass, 16 kHz mono 16-bit PCM, `loudnorm` two-pass linear at -16 LUFS, -1.5 dBTP, LRA 20, explicit `-ar`; AAC 96 or 128 kbps; libx264 veryfast CRF 23 at most 720p; `+faststart`), not the assembled commands.
- The waveform input: audiowaveform reads MP3, WAV, FLAC, Ogg Vorbis, and Opus, not AAC, so the Playback copy's audio is decoded (ffmpeg) for it. Constraint: the peaks reflect the Playback copy's loudness-normalised sound, not the ASR audio.
- The multi-track rule (identical tracks use one, distinct tracks become Sides) has no corpus file to test on; the build follows the rule as written.
- Who watches the ten-minute rule (the sidecar's hook events or the app). Constraints: the upload is dropped, its Recording removed, and the user's one Batch never held open by it.
- The Phone profile, only through the benchmark gate; NVENC, only if real body-worn camera files prove slow on CPU.
- The image build check `ffmpeg -decoders | grep g729` (one `docker run` at build time).

### Carried for Phase 2

- The per-Recording file set fixed here (`original`, `probe.json`, `asr-side*.wav`, `playback.*`, `waveform.json`, `clips/`) is what a Case keeps in Phase 2; Clips saved into a Case keep their files under the Retention policy (the "Cases" and "Retention policy and the Recycle bin" chapters of the Phase 2 specification).
- Cases live under the App data folder in Phase 2; the layout above leaves room for them beside `scratch/`.

### Sources

Media handling from browser to ASR to player; Assemble a test corpus of real recordings; Upload page and Batch settings prototype (its amendment to the media ticket); the media pipeline research file. Names of reason classes, audit rows, and settings checked against App-side transcription queue and job model, Audit log, and Admin settings catalogue and panel.

### Amendments applied

- From App-side transcription queue and job model, to Upload: the pause banner and the 24-hour resume withdrawn; leaving the page abandons uploads; the ten-minute rule; the 24-hour sweep kept as the backstop.
- From Workspace lifecycle rules, to Clips and duplicates: a Clip's definition does not survive the Recording; a file uploaded again is a new Recording never matched to an earlier one; the duplicate rejection against a live Recording stands.
- From Clips: model, lifecycle, and management, to Clips and the storage layout: no `.txt` or `.srt` stored beside a Clip; a Clip possible once playback is Ready; renders on the media worker with the timeout and `clip_render_failed`; the Longest Clip limit; a deleted Clip leaves the Provenance.
- From Upload page and Batch settings prototype, to Diarization on a multi-Side Recording: "defaults to off for a Two-channel call" withdrawn; the user's Diarize choice honoured per Side with "Let the app decide"; the Side-alone label for a one-Speaker Side; the title editable at upload.
- From the maintainer, on the v1.3.0 build, to Waveform peaks: 256 samples per pixel replaced by about 8,192 pairs for the whole Recording, never finer than 256, because the Timeline never zooms and was drawing one pair in four hundred of a 4 MB file that every opening of the viewer fetched again.
- From the maintainer, on the v1.43.0 build (two surveillance exports refused as undecodable when their index had never been written), to the refusals: the incomplete-file refusal, `incomplete_file`, told apart from undecodable by ffprobe's own words, with a message that says what to do; and the duplicate refusal's title linked to the recording it already is (v1.44.0).

## 5. Upload page and Batch page

The Upload page is the entry point for the office's users and carries every per-Batch choice. After Submit it becomes the Batch page and stays so until the Batch ends. A prototype of this page exists in the planning repository at `prototypes/upload-page/` (its Steps layout, with the changes recorded here); where the prototype and this specification differ, the specification wins.

Where the rules behind what the page shows belong to the Queue (positions, the person ahead, Estimated wait, Cancel and Retry semantics, the one-Batch rule), this chapter states only what the page shows; the rules are in the chapter "Queue and Jobs".

### The three steps

The page is a stepper with three steps: 1 Choose files, 2 Settings, 3 Check and start. On a window narrower than 1280 pixels one step shows at a time, with Next and Back. From 1280 pixels all three are on the page at once: Choose files on the left, Settings above Check and start on the right, with Upload and transcribe always in view and greyed until there is a file to send; Next and Back are not shown. The steps are the same three in the same order either way, and the Check and start table follows every change as it is made.

#### Step 1: Choose files

- The drop zone: a file picker and drag-and-drop; no archives. It carries the format list and the limits line, with the figures from the Largest file, Longest Recording, and Files per Batch settings:

```
Files that usually work: mp4, mov, m4a, mp3, wav, wma, ogg, webm, mkv, avi, flac, amr, 3gp. No zip files.
Up to 25 files in a batch, 10 GB and 6 hours each.
```

- One card per chosen file: an editable title (defaulting to the file name without its extension), the original name, the size, the length once known, and Remove.
- Files refused before upload (archives, empty files, files over the size limit) are shown in red with their reason. Over the Files per Batch cap the page shows `A batch can hold up to 25 files. Remove N to continue.` and Submit is not possible.
- Next.

#### Step 2: Settings

Two panes. Each chosen file's card in step 1 also carries the `Same as batch` or `Custom settings` chip that the table below carries, which opens that file's own settings in the rail; on a wide window, where the whole page is in view, the table is not repeated and the chips on the cards are the way to a file's own settings.

- Left, the "Exceptions for single files" table: one row per file with its title, speakers, translate, language, and a chip reading "Same as batch" or "Custom".
- Right, a sticky rail holding the Batch settings (below).
- Clicking a file's chip turns the rail into that file's own settings, headed by "Use the batch settings for this file" (ticked by default; unticking copies the Batch settings into the file's own, which then edit independently), with a Title field, and "Back to batch settings" returns the rail to the Batch settings.

#### Step 3: Check and start

- The review table: title, original name, size, and the effective settings with a "custom" mark where a file has its own.
- The button "Upload and transcribe N files".
- The note `Uploads start when you press the button, three at a time. Keep this page open until they finish.`
- The storage warning, when it applies (below).

### The Batch settings and one file's own settings

The Batch settings apply to every file; the rail gives any file its own. The page starts from the Transcription defaults in the admin settings catalogue.

| Control | Default | Behaviour and help |
|---|---|---|
| **Diarize** (checkbox) | ticked when the Diarization ticked by default setting is On | Labelled "Diarize", nothing else. Hidden when the Diarization available setting is Off. Its help line carries the warning below, in substance |
| Speaker-count hint | the Speaker-count hint default setting: Let the app decide, Exactly N, or Between N and M | Beneath Diarize; greyed while Diarize is unticked; set per Recording with the Batch-wide default |
| **Translate to English** (checkbox) | ticked when the "Translate to English" ticked by default setting is On (Off by default) | Hidden when the Translation available setting is Off. Beside it (or in the help) the note that a recording holding more than one language is translated to English whether or not this is ticked, and that translation loses word timing. The rules are in the chapter "Transcription, translation, and diarization choices" |
| **More options** (collapsed unless something in it is set) | | |
| Spoken language | Automatic | A search box over Whisper's list: Automatic first, then English and Spanish, then the rest. Help: choosing a language switches detection off for that recording |
| Vocabulary | empty | One name or term per line. Help: office names are added automatically (the Office Vocabulary setting), and the engine's prompt is short, so a long list is cut from the end |
| Context (one line) | empty | One sentence of context for the engine (who is speaking and what about). Help: write it in the spoken language, or in English when translating |
| Audio clean-up | the Preprocessing profile setting | Read-only, shown as `Standard (set by IT)` |

The Diarize warning, in substance (the build may polish the words, not the substance):

```
Labels who is talking. Automatic speaker separation is sometimes wrong: one person can be split into two speakers, or two merged into one. Check the names against the audio.
```

Not on the page: no model field (the model is the Model setting, chosen by an Admin, and appears in the Provenance); no "Recorded on" date (the export cover date is the upload date); no "Add to case"; no Recording type.

### Two-channel calls and the user's Diarize choice

The app learns that a Recording is a Two-channel call only when the file is checked, after the user's choices are in, and every Run is handed over the moment its Recording is Ready, so there is no window to ask. The user's Diarize choice is therefore honoured on a Two-channel call and nothing is switched off:

- With Diarize ticked, Diarization runs on each Side with "Let the app decide" for each Side whatever the hint says. A Side with one Speaker is labelled by its Side alone ("Side 1"); a Side with more is labelled "Side 1 Speaker 1", "Side 1 Speaker 2". A two-party call reads as it would without Diarization; a three-way call comes out right the first time, with nothing run twice.
- With Diarize unticked, the Sides are the Speakers.
- The Batch page's note under the row reads `Two-channel call: 2 sides, each transcribed on its own.` The two-track note reads `N audio tracks found, M distinct, transcribed separately.`
- The Provenance records the hint as applied per Side.

### Submit: the liveness check, the Batch, and the uploads

- The page checks the WhisperX service's liveness when it opens and again when "Upload and transcribe" is pressed. If the check fails, no Batch is created and the page says `Transcription is not available right now. Try again later.`
- On Submit the app creates the Batch, and the files then upload three at a time. Nothing is sent before Submit, and there is no draft Batch.
- While uploads run the browser shows its own leave-page dialog, which the app cannot word. The page itself says:

```
Keep this page open while files are uploading; once every file shows 'in line' or later you can leave and come back.
```

- Leaving the page abandons its unfinished uploads; a momentary network drop retries by itself; an upload that receives nothing for ten minutes is dropped and its Recording removed (chapter "Media handling").
- While free space is below the Minimum free disk space setting the page shows `Uploading is paused because the server is low on space. Ask IT.` and refuses to start.

### The Batch page

The Upload page and the Batch page are one page. After Submit the Upload page shows the Batch and keeps showing it, accepting no files, until every Recording in it has ended (Done, Failed, Refused, Cancelled); then "Upload more" clears it. Opening Upload while a Batch is unfinished shows that Batch under `You have a batch in progress; wait for it to finish.` (the prototype adds: `New files can be added once every recording in it has ended.`). A user has one unfinished Batch at a time.

- **Heading**: "Batch of N, started 1:52 pm" (or "Processing again" for a Process again Batch); the standing line; the Batch download button, `Download 5 transcripts (1 not ready)`, which downloads the plain-text zip, one plain-text Transcript per Done Recording, each with its notice (Word, captions, and the combined document live in the viewer's Export group, chapter "Exports"); Cancel batch.
- **Two panes from 1280 pixels**: the count strip and the rows on the left; on the right `Ready now`, every Done Recording with Open, then the Batch download, then `Still to come` with the count and the overall line, then Cancel. On a narrower window the same blocks follow the rows. The finished state takes the whole width.
- **The count strip**: Uploading (waiting, uploading, checking, preparing), In line, Transcribing, Done, Failed, Refused or cancelled.
- **The overall line**: `Everything done by about 3:40 pm`, from the last Recording's Estimated wait plus its own audio at the measured speed, refreshed with every poll, shown while anything is unfinished.
- **One row per Recording**:
  - title, the "to English" mark, size, length, and the effective settings in one line;
  - its media state (Waiting to upload; Uploading 62% with a bar; Checking the file; Preparing the audio) or its Job state and Step with a bar (`Side 1 of 2: Transcribing 42%`);
  - its place in line and Estimated wait: `3rd in line, behind mlee. About 2 minutes.` or `behind 1 of your own recordings` (`4th in line, behind jsmith. About 35 minutes.`; `behind 2 of your own recordings`), shown as a clock time when over ten minutes; the figure comes from the service's measured speed multiplied by the audio minutes ahead (chapter "Queue and Jobs");
  - Done; Failed with its plain message and Retry; Refused with its reason; Cancelled;
  - "Preparing video" (or "Preparing audio") until playback is Ready, then Open; the viewer opens from this page as soon as playback is Ready, before the Transcript exists;
  - Cancel while unfinished; Process again and Details once Done;
  - the two-channel-call and two-track notes under the row.
- **Refused rows** stay in the list with their reason until the Batch ends. Zip files, empty files, and files over the size limit are refused before uploading; no audio, undecodable audio, an incomplete file, over the length limit, and duplicates after checking (the messages are in the chapter "Media handling"). A duplicate's reason names the recording it already is as a link (v1.44.0).
- **A Batch added from a Case** (v1.44.0): while it runs, `Ready now` ends with a line saying the batch carries on without you and a **Back to <case>** button; when it finishes, the finished state says "Back to <case> in 8 seconds..." and returns there, with **Stay here** to stop it, because what the batch made is on the Case page, refused rows with their reasons included. A Batch whose files went to several places, or to the person's own recordings, has no one place to go back to and behaves as before.
- **Cancel** for a Recording and for the Batch each confirm first; the confirmation says the recording is removed from your recordings and must be uploaded again.
- **Retry** on a Failed Recording, with its plain message beside it (a new one-Recording Batch with the same settings, reusing the media steps that succeeded; chapter "Queue and Jobs").
- There is no list of past Batches. Each Recording on the Recordings page shows the time of its batch, and the Batch download and the sign-out dialog's zips cover downloads.

### The storage warning

No storage meter and no figure while there is room. On the Upload page, when the Batch would take the user past 80% of their space: `You are close to your storage space: 42 of 50 GB after this batch`. When it would pass their space, the refusal: `This batch would go over your storage space (52 of 50 GB). Remove some files, or delete recordings you no longer need. IT can raise your space.` On the Recordings page the same warning once past 80%. The figures are the user's own; the 80% is a build constant, not a setting.

### The Process again form

Process again opens from a Done Recording (the Batch page row, the Recordings page, the Details panel) as a one-Recording Batch: the same settings pre-filled for that Recording (Spoken language, Translate to English, Diarize and its hint, Vocabulary, Context), with the warning of what is lost and what is kept (the rules are in the chapter "Queue and Jobs"). It is refused while a Batch is in progress (`batch_in_progress`) or the service is down (`service_unreachable`). Its Batch page is headed "Processing again".

### Landing and the Recordings page

Sign-in lands on the Recordings page, empty or not. It holds the user's Recordings as one table (title, state, length, Clips, the time of its batch) with Open on each Ready row, and the chosen Recording's details (the file, the state in full, the Sides, the Clips, and Process again, Move to case, Retry and Delete) in a pane beside the table from 1280 pixels or under its row on a narrower window; Up and Down move along the rows, Enter opens, and on a wide window the first Recording's details show until another is chosen; the standing line at the top; an "Upload recordings" button; and the storage warning once past 80%. Delete confirms with the counts of what goes with the Recording (chapter "Workspace lifecycle"). The pages say "your recordings", never Workspace.

### Shared page furniture

Present as prototyped; the rules behind each live in the chapters named.

- The standing line at the top of the Upload, Recordings, and Clips pages (chapter "Workspace lifecycle" owns it and its hours figure, which is the Idle timeout setting's): `Your recordings and transcripts are removed when you sign out or after 8 hours without activity. Download or export anything you want to keep.`
- The top navigation: Recordings, Upload, Clips (chapter "Clips"; hidden when the Clips available setting is Off).
- The Details drawer with the Provenance (the fields are in the chapter "Media handling").
- The sign-out dialog (chapter "Workspace lifecycle"): the counts of recordings, summaries, chats, and undownloaded clips; `N clips have not been downloaded` with a Download clips link; the buttons Download all transcripts, Download everything, Cancel, Sign out; an extra line when a transcription is still running.
- The 15-minute idle warning with Stay signed in.
- Cancel's confirmations for a Recording and for a Batch; Delete with its counts.
- Light and dark themes both ship; the page's styling is the app's own, reused from no other app.

### Wording

| Where | Wording |
|---|---|
| the Diarization checkbox | Diarize (never "Separate speakers") |
| the viewer's pill for a Recording processed without Diarization | Not diarized |
| the Preprocessing profile | Audio clean-up |
| the context field | Context (one line) |
| the submit button | Upload and transcribe N files |
| everywhere the tickets say Workspace | your recordings |
| the duplicate-file refusal | You already have this file in your recordings as <title> |
| Cancel's confirmation | removes the recording from your recordings |

### Environment keys

None are named for this page; the upload transport's keys are in the chapter "Media handling".

### Audit rows

None are named for this page by its sources. The upload rows are in the chapter "Media handling"; Batch submitted, Job completed, Job failed, and Job cancelled are in the chapter "Queue and Jobs".

### Settings

By their names in the admin settings catalogue: Diarization available, Translation available, Clips available (Features); Diarization ticked by default, Speaker-count hint default, "Translate to English" ticked by default, Translate mixed-language Recordings to English automatically (behind the Translate note), Office Vocabulary (behind the Vocabulary help), Model (not shown, recorded), Preprocessing profile (shown read-only) (Transcription defaults); Largest file, Longest Recording, Files per Batch (the limits line), Default Workspace quota per user (the storage warning), Minimum free disk space (the `disk_full` line) (Limits); Idle timeout (the standing line's hours). Fixed rules, not settings: one unfinished Batch per user; three uploads at once; the 80% warning; Spoken language starts Automatic.

### Not in this phase

- No line saying that office IT administrators can access all material in this system, on this page or in the user guide. Admins may open any user's content and every such access is audited; the app simply does not announce it on a page.
- No storage meter and no "Using X of Y GB" figure while there is room.
- No model field, no "Recorded on" date, no "Add to case", no Recording type.
- No list of past Batches, no draft Batch, and no upload before Submit.
- The app never switches Diarize off on a Two-channel call, and Process again is never the way to diarize one.

### Left to the build

- The final words of the Diarize warning (its substance is fixed above).
- The exact wording of the Cancel confirmations for a Recording and for a Batch, the Delete confirmation, and the Process again lost-and-kept warning; their substance is fixed here and in the chapters "Queue and Jobs" and "Workspace lifecycle".
- The reason-class identifier for the archive refusal (constraints in the chapter "Media handling").
- The poll interval behind "refreshed with every poll" (chapter "Queue and Jobs").

### Carried for Phase 2

- **Add to case**: when the Folder management toggle is On, the settings step gains a per-Batch "Add to case" dropdown beside the other Batch settings, with a per-Recording override like the rest: the user's own Cases and every Case shared with them, default "This session only", never a Case in the Recycle bin, showing the owner's remaining room when the target is someone else's Case. Adding a Recording to a Case is activity and starts its Retention policy clock over. A Recording added this way is never in the Workspace.
- **Recording type**: in the same place, a per-Batch dropdown over the Admin-kept list (the Recording types setting), with a per-Recording override.
- Both appear only while Folder management is On and go on the next page load when it is turned Off; an upload in flight with a Case chosen finishes into that Case, hidden.
- **Email me when this batch finishes**: one tick on the settings step beside the Batch settings, remembered from the person's last Batch and unticked the first time; greyed with "No email address on your account; ask IT" when they have none; hidden while the Admin setting "Batch finished emails" is Off or mail is not configured (chapter "Email notifications").
- A typed "Recorded on" date waits for Cases.
- Nothing of these is rendered in Phase 1; the prototype's README records where they go.

### Sources

Upload page and Batch settings prototype; Media handling from browser to ASR to player (the refusal messages and the Two-channel call rule). Names of reason classes and settings checked against App-side transcription queue and job model and Admin settings catalogue and panel.

### Amendments applied

- From Email notifications, to the settings step: the Phase 2 "Email me when this batch finishes" tick (carried, nothing in the Phase 1 build).
- Within Upload page and Batch settings prototype, the Answer over the prototype: the prototype's Diarize-off rule for a Two-channel call, its storage meter, and its IT-administrators line withdrawn; "Diarize" for "Separate speakers".
- From the maintainer, on the v1.5.0 build, to the three steps, the Batch page, and the Recordings page: the Workbench Layout's second page. From 1280 pixels the Upload page shows all three steps at once with Start always in view and the exceptions chip on each file's card; the Batch page is two panes, the rows and `Ready now`; the Recordings page is a table with the chosen Recording's details in a pane. Below 1280 pixels the stepper, the single column, and details under the row.
- From the maintainer, on the v1.43.0 build ("when I'm in a case and select add recording and go through the flow, when it's done for whatever reason, I want to land back on the same case"), to the Batch page: a Batch added from a Case offers the way back while it runs and returns there when it finishes, after a short countdown with Stay here (v1.44.0).


## 6. Queue and Jobs

This chapter fixes the app's Queue and Job model: how Batches, Jobs, and Runs sit on top of the WhisperX service's serial line, what users and Admins see and can do, what happens when a Job fails or something is down, and how the app's background work is run. The rule that one transcription runs at a time office-wide is enforced inside the service, not in the app (ADR 0005). The service's endpoints, request and result fields, ceilings, and its own reason classes are in the WhisperX service API document and are not restated here.

### Principles

1. **The service's line is the only line.** The app hands every Run to the WhisperX service the moment its Recording is Ready and never holds one back. Position and audio ahead come straight from the service. Nobody has priority: no "move to front" and no pause, for users or Admins.
2. **Keep it simple.** One Batch per user at a time. When something is down it does not work and the user tries again later; there is no waiting state anywhere.
3. **Cancel throws everything away; failure keeps everything.** A cancelled Recording is removed as if it had never been uploaded. A Failed one keeps its files and a Retry button.
4. **The app's work queue lives in Postgres.** No Redis, no Valkey, no scheduler container.

### Batch, Job, Run, and the service's line

| Object | What it is |
|---|---|
| Batch | The set of Recordings a user submits together, with shared settings and per-Recording overrides. A Batch is a real object with its own page (the Batch page), and every Job belongs to exactly one Batch. Retry and Process again each create a Batch of one Recording; a Process again Batch is marked as a re-processing. |
| Job | One Recording's pass through the Queue, created the moment the Recording is Ready. A Job holds one Run per Side and is Queued, Running, Done, Failed, or Cancelled. |
| Run | One Side's pass through the WhisperX service; the service's own API calls it a job. The app submits each Run with `client_reference` set to the Run's own id, which is the service's duplicate protection. |
| Queue | The office-wide line of Jobs: the WhisperX service's line seen through the app. |

How the two lines relate:

- Two lines exist by design and their units differ: the app's Job is one Recording; the service's job is one Side, which the app calls a Run.
- The service runs one job at a time across every Consumer, first in first out, and keeps its line across its own restarts. The app is one Consumer, holds a regular token, and sees only its own jobs; each job's position and audio minutes ahead count everyone's.
- The app keeps its own Queue only for what the service cannot know: Batches, the one-Batch rule, the order of a Recording's Sides, the keep-alive rule, and what users see. Nothing is held back in the app and nothing is reordered.
- The service's own ceilings (2 GB per request, 8 hours of audio, a run time of 30 minutes plus the audio length) sit above the app's limits, so the limits users meet are the app's own (see the Media handling chapter).
- A future move to parallel transcription is a change to the service that the app inherits without code changes of its own.

### Batches and the one-Batch rule

- Settings are recorded per Recording at submission (the Batch defaults plus any per-file override) and copied onto the Job when it is created, so the Provenance names exactly what the Job used. The settings themselves are in the Transcription, translation, and diarization choices chapter.
- A user may have **one unfinished Batch at a time**, Admins included. A Batch is unfinished while any Recording in it is Uploading, Checking, Preparing, Queued, or Running. It is finished when every Recording in it is Done, Failed, Cancelled, Rejected, or removed. A second Batch, or a Process again, is refused with:

```
You have a batch in progress; wait for it to finish.
```

- The Upload page shows the unfinished Batch and its progress and accepts no new files until it is finished.
- The only size rule is the admin setting "files per Batch", default 25. There is no separate cap on waiting Recordings, because the one-Batch rule bounds it, and there is no "queued Jobs per user" setting.
- The Submit button carries a one-time token, so a double click makes one Batch. Uploads start on Submit, never before. A Recording has at most one unfinished Job at a time, and the Run id is the service's `client_reference`, which is the service's own duplicate guard.
- **Leaving the Upload page abandons its unfinished uploads.** The browser warns:

```
Uploads in progress will be lost
```

  and the user starts over on return. A momentary network drop inside the page retries by itself, invisibly. An upload that receives nothing for ten minutes is dropped by the app and its Recording removed, so a closed laptop can never leave a Batch unfinished. There is no pause banner and no 24-hour resume of an upload.

#### The Batch page

The page's shape belongs to the Upload page and Batch page chapter; the rules it must obey are these.

- The Upload page and the Batch page are one page. After Submit the Upload page shows the Batch until every Recording in it has ended, then "Upload more" clears it. There is no list of past Batches.
- It shows every Recording with its state and Step; the count strip (waiting, running, done, failed); the position and Estimated wait of each Recording; one overall line, "Everything done by about 3:40 pm", computed from the last Recording's Estimated wait plus its own audio at the measured speed and refreshed with every poll; a link to each Recording as it becomes Ready; Cancel per Recording and for the whole Batch; Retry on each Failed Recording; and the Batch download.
- Refused Recordings stay listed with their reason until the Batch ends.
- Media states (Uploading, Checking, Preparing, Ready, Rejected, Failed) belong to the media worker and show on the Batch page until the Job exists.

### Joining the line

- Each Recording joins the line the moment it is Ready, in Ready order, not upload order: a small mp3 uploaded after a large video overtakes it while the video is still being prepared.
- A multi-Side Recording's Runs are handed over together, back to back, so a Job never interleaves with another user's Job. The Job's position is its first Run's, and the Job finishes as a whole.
- Nothing is held back and nothing is reordered. Nobody has priority. The Admin's only control is Cancel.

### Job states and Steps

| State | Meaning |
|---|---|
| Queued | Every Run is at the service and none has started. |
| Running | A Run has started; the page shows a Step. |
| Done | The merged Transcript is stored and the audit row "Job completed" (duration) is written. |
| Failed | Ended with a reason class; files kept; Retry offered. |
| Cancelled | Ended by its user or an Admin; the Recording is removed (see Cancel). |

Queued and started are Job states only, never audit rows.

A Step is the plain wording shown while a Job runs, mapped from the service's `stage` values:

| The service reports | The Step shown |
|---|---|
| `loading model` | Loading the model |
| `transcribing`, with its percent | Transcribing 42% |
| `aligning` | Aligning words |
| `diarizing` | Separating speakers |
| `finishing` | Finishing |
| (the app's own step, after the last Run is done) | Merging sides |

A multi-Side Recording prefixes the Step with its Side: "Side 1 of 2: Transcribing 42%". A Recording being processed again shows "Processing again" in lists.

### Merging a Job's Runs into one Transcript

1. The merge starts when the last Run of the Job is Done. While it runs, the Step is "Merging sides".
2. The app fetches each Run's result from the service. A result must be collected within 24 hours of the Run finishing; after that the service has deleted it and the Job fails with `result_expired`.
3. The Runs' Segments are merged by start time into one Transcript.
4. Speaker labels arrive from the service as `SPEAKER_NN`, numbered per Run, and are renamed before anyone sees them: "Speaker 1", "Speaker 2" on a single-Side Recording; "Side 1 Speaker 1" on a multi-Side Recording. A Side with one Speaker is labelled by its Side alone. With Diarize off, the Sides of a Two-channel call are the Speakers.
5. Word timing is per Run. A translated Run, or a Run in a language the service could not align, comes back with segment timing only; the flag and its reason are stored for the viewer and the Provenance (see the Transcription, translation, and diarization choices chapter). A Two-channel call under translate still has its Sides as Speakers, with segment timing only.
6. The app stores the Segments and words, keeps every setting the service echoes in its result (`settings_used`, the service's version and pins, timings, the detected-language figures) for the Provenance, writes the audit row "Job completed" with the duration, marks the Job Done, and deletes the service jobs.
7. If the app cannot merge or store the Transcript, the Job is Failed with `merge_failed`, files kept, Retry offered.
8. No LLM step follows a Job. Summary, Chat, and Speaker suggestions run only when a user asks from the viewer (see the AI assistant chapter), so nothing after the merge ever holds a Job in Running.

### What users see

- A user sees their own Jobs, the position of each, and the sign-in name of the person directly ahead, never a title or file name of anyone else's. Admins see every Job (see The Admin's Queue tab).
- The queued wording, in three shapes:

```
4th in line, behind jsmith. About 35 minutes.
4th in line, behind 2 of your own recordings.
4th in line, behind another system.
```

  The first names the sign-in name of the user whose Job is directly ahead. The second is used when the Jobs directly ahead are the user's own. The third is used when the job ahead belongs to another Consumer of the service.

- The queued page says the user can leave the page, offers Cancel, and becomes the viewer by itself as soon as the Recording's playback readiness is Ready, not only when the Transcript is: the user can mark and save Clips while the Job waits, and the Transcript appears in the viewer when the Job finishes. The processing view shows the current Step and a progress bar.

**Estimated wait** is the app's figure for how long until a Job starts. The service never states a wait; it publishes its measured speed, and the app computes:

1. Take the Run's `audio_minutes_ahead` from the service's status.
2. Divide by the service's measured speed (audio minutes processed per wall-clock minute) for the matching model and Diarization setting. The app's own Jobs ahead use their own settings' speed; anything else ahead uses the slower figure (Diarization on).
3. Add fifteen seconds per Run ahead.
4. Round up to the next minute. Under a minute shows "less than a minute". Over ten minutes adds a clock time: "about 35 minutes, around 3:40 pm".
5. Until the service has ten completed Jobs for a setting, use the research reference figures instead (about seventy times real time for transcription; Diarization adds about half a minute per hour of audio) and say "roughly" instead of "about".
6. Refresh the figure with every page poll.

### Live status by polling

| Who polls | What | How often |
|---|---|---|
| The `worker` service | The service's job list (`GET /v1/jobs`, which returns every Run of the app's in one call); the statuses are written into Postgres. A queueing lock keeps one poll waiting at a time. | Every three seconds |
| Every open page | The app, for the Jobs the page shows, read from the database, so thirty open pages never touch the service. | Every five seconds; a page showing nothing unfinished stops polling |
| The viewer while an AI assistant call is running | The app | Every two seconds, then back to five |

No server-sent events in Phase 1. The queue and worker research file records how to add them later without changing the queue: the web container moves to an ASGI server (gunicorn with the uvicorn worker, or uvicorn), the reverse proxy already flushes `text/event-stream` responses (`flush_interval -1` is the explicit line), and django-eventstream 5.3.4 (MIT) runs on plain ASGI with no Channels. With gunicorn's sync workers every open event stream would occupy one worker for its whole life, which is why polling is the Phase 1 design.

### Cancel

- A user cancels their own Job while Queued (instant) or Running (after a confirmation):

```
This stops the transcription and removes the recording from your Workspace. You will need to upload it again.
```

  The confirmation also names the Recording's Clips and how many of them were not downloaded.

- Cancelling a running Run kills the service's model process and costs the next job a short reload; accepted.
- **Cancel removes the Recording**: its files, its folder, its Clips, and its row, as if it had never been uploaded. Cancelling a Batch does that to every Recording in it that is not Done, including ones still uploading or preparing; Done Recordings stay. A Clip render in flight is stopped by Cancel.
- Exception: cancelling a Process again Job discards only the new Job; the Recording and its old Transcript stay and the old Transcript unlocks.
- Admins cancel any Job from the Queue tab, audited with the affected user. There is no Pause and no reordering.
- Audit rows: "Job cancelled" (by whom) and "Recording deleted" (cause: cancel).

### Failure, Retry, and the reason classes

A Job ends Failed with exactly one reason class. The service's nine classes pass through unchanged: `bad_input`, `too_large`, `too_long`, `model_unavailable`, `gpu_error`, `timeout`, `cancelled`, `service_restarted`, `internal`; their meanings are in the WhisperX service API document. The app adds its own:

| Class | When |
|---|---|
| `media_failed` | A media step failed (hash, probe, Sides, ASR audio). |
| `service_unreachable` | The service could not be reached when the Run was handed over, or two status polls in a row failed to connect. |
| `service_refused` | The service rejected the app itself: an unknown token, a Run it should know, an API mismatch. |
| `result_expired` | The result was gone before the app collected it (the app was down for over 24 hours). |
| `merge_failed` | The app could not merge or store the Transcript. |

Upload refusals use their own classes in the same catalogue and never make a Job: the Media handling chapter's rejections (no audio, undecodable, empty, duplicate file, over size, over length), `quota_exceeded`, `limit_exceeded` (files per Batch), `batch_in_progress`, and `service_unreachable` when the Upload page's liveness check fails. An AI assistant call made while the engine is down fails at once with `llm_unreachable` (see the AI assistant chapter); it is never a Job class.

Every class has one plain message for users and the class name for Admins.

**Retry.** Every Failed Job has Retry: a new Job with the same settings, in a new one-Recording Batch, reusing the media steps that already succeeded. The app retries nothing by itself beyond what the service already does (one retry on `gpu_error`, and one survival of a service restart, after which a second interruption is `service_restarted`).

### When something is down

**The WhisperX service.**

- The Upload page checks the service's liveness (`GET /healthz`) when it opens and when Submit is pressed. If the check fails, no Batch is created and the page says:

```
Transcription is not available right now. Try again later.
```

- A Run that cannot be handed over fails its Job at once with `service_unreachable`; each Recording fails on its own as it becomes Ready.
- A Job already at the service fails with the same class the moment two status polls in a row fail to connect (six seconds, so one dropped packet does not fail a two-hour transcription).
- There is no waiting state. When IT restarts the service, every Job at it fails and users press Retry. The service would still finish those abandoned jobs, so the app cancels them on its next successful contact to free the GPU.

**The app itself.** Jobs and Runs live in Postgres. After a restart the worker resumes polling and nothing is lost. A result that expired meanwhile fails with `result_expired` and Retry.

**The engine.** Transcription is unaffected. Summary, Chat, and Speaker suggestions say:

```
The AI assistant is not available right now
```

  Nothing is deferred and nothing waits: no LLM step follows a Job, and a click while the engine is down fails at once with `llm_unreachable`. The user tries again later from the viewer.

### Keep-alive and one sign-in at a time

- A user's Workspace is busy from the moment any upload of theirs finishes until their last Job ends (Done, Failed, or Cancelled). Media preparation therefore counts; a half-finished upload does not. A Clip render is not a Job and never keeps a Workspace busy.
- When the Login session ends while the Workspace is busy, the Workspace lives until the last Job ends plus a grace period equal to the idle timeout (default 8 hours). There is no separate setting. The Workspace lifecycle chapter owns the rest.
- A user has one Login session at a time. A new sign-in wins: the older session ends and shows, on its next request:

```
You signed in from another place; this session has ended
```

  The Workspace belongs to the user, so nothing in it is lost by the switch and a running Batch is unaffected. The idle timeout is unchanged. The logout audit row carries the cause "signed in elsewhere". The Sign-in, accounts, and roles chapter carries the rule as its own.

### Process again

- Process again is a Details-panel action. It pre-fills the Recording's settings (Spoken language, Translate to English, Diarization and its hint, Vocabulary, context line), warns what will be lost (the list is in the Transcription, translation, and diarization choices chapter), and submits a one-Recording Batch, marked as a re-processing, through the normal line, obeying the one-Batch rule.
- While the new Job is unfinished the Recording shows "Processing again" in lists, and the old Transcript stays readable but locked: no Corrections, merges, Speaker naming, or new Clips, under a banner:

```
A new transcription is in progress; this transcript will be replaced.
```

- Cancelling the new Job unlocks the old Transcript untouched.
- When the new Transcript lands it replaces the old. Only then do Summaries and Chats get their "based on an earlier transcript" mark and Clip excerpts refresh. The Provenance keeps both processings.
- The re-run is recorded in the audit log as "Batch submitted" for the one-Recording Batch, with its settings.

### Batch download

- One zip per Batch with one plain-text file per Done Recording: the viewer's plain-text export (Speakers, timestamps, Transcript) with the Transcription notice or the Translation notice at the top. Recordings not yet Done are left out, and the button says:

```
Download 22 transcripts (3 not ready)
```

- The zip is named `Transcripts <yyyy-mm-dd> <hhmm>.zip`. Inside it each file is `<title> - transcript.txt`, under the file-name rules and the four-line text head fixed in the Exports chapter, with duplicates suffixed " (2)".
- The Batch download is the only download on the Batch page. There is no bulk Word button; "Download everything" lives on the sign-out dialog instead (see the Exports chapter).
- Audit: one row "export made, plain text" per Recording included, with the affected user when an Admin downloads.

### The Admin's Queue tab

- The status page of the panel has a Queue tab listing every Job with user, title, Batch, duration, state, Step, position, and a Cancel button, nothing else. No Pause, no reordering.
- Viewing the tab is a metadata list and writes no audit row. Opening a Recording from it is an Admin opening another user's material and writes that audit row (see the Audit log and logging chapter).
- An Admin's Cancel is audited with the affected user.
- IT cancels Jobs from this tab. A wedged Procrastinate job (any queue, `llm` included) is cleared from the terminal with a `./transcribe` subcommand named in the Repository, releases, and distribution chapter. Django's own admin is not mounted at all, in any environment: it would show raw tables, Transcript text included, without the audit row.

### Background work: Procrastinate and the worker services

- The app's task queue is **Procrastinate** 3.9.0 (MIT) on the app's own Postgres through `procrastinate.contrib.django`. No Redis, no Valkey, no scheduler container. The worker needs psycopg 3.
- Chosen over Huey's Postgres backend for its built-in recovery of jobs lost to a crashed worker and its once-per-period schedules across several workers, and over Django's own Tasks framework, which has no retries, schedules, or crash recovery (see the queue and worker research file).
- One worker image, three Compose services; same code, different queues, so a slow transcode never delays a status poll and an AI assistant call never delays it either.

| Service | Queue | Work |
|---|---|---|
| `media-worker` | `media`, concurrency 4 | Hash, probe, Sides, ASR audio, Playback copy, waveform, Clip renders. Each job waits on one ffmpeg with `MEDIA_THREADS_PER_JOB` threads. |
| `worker` | `default` | Handing Runs to the service; the three-second status poll (a queueing lock keeps one poll waiting at a time); result fetch and merge; the schedules: Directory check at 03:00, sweeper at 03:30, the audit sweep, session expiry and Workspace discards every minute, stalled-job recovery every ten minutes. |
| `llm-worker` | `llm`, concurrency 4 | The AI assistant's calls (Summary, Chat, Speaker suggestions), so the status poll on `worker` is never delayed. |

- Stalled-job recovery uses Procrastinate's own mechanism, as the research file records it: workers write a heartbeat every 10 seconds; a worker whose heartbeat is older than 30 seconds is considered stalled; a periodic task with a queueing lock re-queues that worker's jobs. The ticket sets the period at ten minutes.
- Procrastinate's schedules are once-per-period across workers, so a schedule never runs twice because two workers are up.
- On SIGTERM a worker finishes its running jobs before exiting.
- Procrastinate's job table is visible only through the terminal subcommand above, because the Django admin is not mounted.

### Fixed intervals and limits

| What | Value |
|---|---|
| `worker` status poll of the service | every 3 seconds |
| Page poll of the app | every 5 seconds; 2 seconds in the viewer while an AI assistant call runs |
| Polls that must fail to connect before a Job fails `service_unreachable` | 2 in a row (6 seconds) |
| Upload that receives nothing | dropped after 10 minutes; its Recording removed |
| Result collection window at the service | 24 hours, then `result_expired` |
| Per-Run allowance in the Estimated wait | 15 seconds |
| Completed Jobs per setting before the measured speed replaces the reference figures | 10 |
| Grace period after the last Job when the Login session has ended | equal to the idle timeout (default 8 hours) |
| Stalled-job recovery | every 10 minutes |
| Session expiry and Workspace discards | every minute |
| Directory check, sweeper | 03:00, 03:30 |
| Files per Batch | admin setting, default 25 |
| Media concurrency | 4 jobs, `MEDIA_THREADS_PER_JOB` threads each |
| AI assistant concurrency | 4 |

### Environment keys

| Key | Default | Meaning |
|---|---|---|
| `MEDIA_CONCURRENT_JOBS` | 4 | How many media jobs run at once; the `media-worker` concurrency. Owned by the Media handling chapter. |
| `MEDIA_THREADS_PER_JOB` | 8 | ffmpeg threads per media job. Owned by the Media handling chapter. |

The app's own bearer token for the service is written into the app's `.env` by the service's `make-token` command; its key is named in the Architecture and deployment chapter. The app reaches the service's `/healthz` and `/v1/` on the shared Docker network only.

### Audit rows

| Row | When it is written |
|---|---|
| Batch submitted | At Submit, with each Recording's settings: Diarization choice and hint, Translation, whether Vocabulary was given, preprocessing profile, model. Also for the one-Recording Batch of a Retry and of a Process again. |
| Job completed (duration) | When the merged Transcript is stored. |
| Job failed (reason class) | When a Job ends Failed. |
| Job cancelled (by whom) | When a user or an Admin cancels; with the affected user when an Admin cancels. |
| Recording deleted (cause: cancel) | When Cancel removes the Recording. |
| export made, plain text | Once per Recording included in a Batch download; with the affected user when an Admin downloads. |
| logout (cause: signed in elsewhere) | When a newer sign-in ends the older Login session. |

Viewing the Queue tab writes no row. Queued and started are never rows.

### Settings

- **files per Batch** (default 25): the only size rule on a Batch.
- **idle timeout** (default 8 hours): also the keep-alive grace period; no separate setting exists.
- **Model**: the model the app names in every Run; the Estimated wait uses the speed figure for that model.
- There is no "queued Jobs per user" setting, no Pause, and no priority setting; the Queue tab carries Cancel only.

### Left to the build

- The plain message shown to users for each reason class. Fixed: every class has one plain message for users and the class name for Admins; upload-refusal classes included.
- The `./transcribe` subcommand that clears a wedged Procrastinate job from the terminal. Fixed: it must reach any queue, `llm` included; the Repository, releases, and distribution chapter names it.
- The Phase 1 benchmark gate replaces the research reference speed figures with measured numbers on the service's GPU; the app itself keeps using the service's published speed and the "roughly" rule above until ten Jobs per setting have completed.
- Not fixed by the tickets, so the build decides or asks: whether Retry on a Failed Recording of a Batch that is still unfinished is allowed at once (Retry makes a new one-Recording Batch, and a user may have one unfinished Batch at a time; the tickets do not say which rule wins); what the app does with a Job's other Runs, still at the service, when one Run fails (the Job "finishes as a whole" and ends with one reason class).

### Carried for Phase 2

- **Batch finished mail.** When the last Recording in a Batch has ended (Done or Failed; a Batch the person cancelled whole sends nothing), the app hands `worker` one "batch finished" Notification for the person who submitted it, if they ticked "Email me when this batch finishes" on the Upload page: how many transcribed and how many failed, each failed Recording's title with its reason in plain words, and where the Recordings are. Sent once, never resent. Nothing about the Queue, the Job states, or the Batch page changes.
- **The `restored` reason class.** After a restore, the app marks every Case-bound Job that was Queued or Running at the Snapshot as Failed with `restored`, keeping its files and a Retry button, because the service's job database is not restored and its old job ids mean nothing. A Recording in a Case whose rows came back without its files is Failed with `restored` too. Workspace Jobs go with the Discard, since a restore never brings a Workspace back. The stalled-job recovery is unchanged.

### Sources

"App-side transcription queue and job model"; "Translation-to-English behaviour" (Process again); "WhisperX service API and operating contract" (context only); ADR 0005, "The office-wide one-transcription-at-a-time rule is enforced inside the WhisperX service"; the queue and worker research file.

### Amendments applied

- From the LLM features ticket to the queue ticket: no LLM step follows a Job; a call while the engine is down fails at once with `llm_unreachable`; the `llm-worker` service and its `llm` queue; the viewer polls every two seconds while an AI assistant call runs.
- From the Word export ticket to the queue ticket: the Batch download is the only download on the Batch page; the zip and file naming; no bulk Word button.
- From the settings catalogue ticket to the queue ticket: Django's own admin is not mounted; a wedged Procrastinate job is cleared with a `./transcribe` subcommand.
- From the backup ticket to the queue ticket: the `restored` reason class (carried for Phase 2).
- From the Clips ticket to the queue ticket: the queued page becomes the viewer as soon as playback is Ready; Cancel names the Clips and how many were not downloaded; a Clip render is not a Job.
- From the Upload page ticket to the queue ticket: the Upload page and the Batch page are one page; uploads start on Submit; the "Everything done by about" line; refused Recordings stay listed; a Two-channel call with Diarize ticked sends each Side's Run with an empty speaker hint.
- From the email notifications ticket to the queue ticket: the Phase 2 "batch finished" Notification (carried for Phase 2).
- The queue ticket's own amendments to the LDAP ticket (one Login session at a time, a new sign-in wins) and to the media handling ticket (no upload pause or resume; the ten-minute stale rule) are written here in their final form.

## 7. Transcription, translation, and diarization choices

This chapter fixes what a user chooses for each Recording, what the app sends to the WhisperX service for each choice, how the language of the speech is detected and what happens when a Recording holds more than one, how translated and non-English Transcripts are marked, and the notice every export carries. The service's request and result fields are named here only where the app's behaviour depends on them; the WhisperX service API document defines them.

### Principles

1. **English is the goal; the Spoken language is the means.** The one visible language choice is "Translate to English". The Spoken language is an advanced control that exists for the day detection guesses wrong.
2. **One language per Run.** The service picks one language for a whole Run, and the app never splits a Recording, merges a transcribe Run with a translate Run, or re-runs a Recording on its own. A Recording that holds more than one language is translated wholesale to one English output.
3. **What Whisper produced is the Transcript**, plus human Corrections. No LLM ever touches the translation path.
4. **Machine text is always labelled as such**: markers in the viewer, a notice on every export, the facts in the Provenance.

### What the user chooses per Recording

Every choice is a Batch default with a per-file override, recorded per Recording at submission and copied onto the Job (see the Queue and Jobs chapter). The page shape is in the Upload page and Batch page chapter.

- **Diarize.** The pages call the choice "Diarize" and carry a short warning that automatic speaker separation is sometimes wrong. With it comes the **speaker-count hint** in one of three shapes:

| Hint | Sent to the service as |
|---|---|
| Let the app decide | `speakers` empty |
| Exactly N | `speakers: {"exactly": N}` |
| Between N and M | `speakers: {"between": [N, M]}` |

  The hint is ignored unless `diarize` is true, and the service refuses `between` with N greater than M. On a Two-channel call with Diarize ticked, each Side's Run is sent with an empty hint, so the service decides the count for each Side; a Side with one Speaker is labelled by its Side alone. With Diarize off, the Sides of a Two-channel call are the Speakers. Diarization still runs under translate, at segment level.

- **Translate to English.** A visible checkbox.

- **Spoken language**, under **More options**, beside Vocabulary and the context line. Default **Automatic**. English and Spanish are listed first and the rest of Whisper's language list is searchable below. The list is Whisper's list and nothing else; a language Whisper does not cover (Kurdish, for example) cannot be offered. An explicit Spoken language switches detection off for that Recording, so the mixed-language rule cannot fire and the user gets exactly what they asked for.

- **Vocabulary** and the optional one-line **context** sentence, under More options. The context-line hint says to write it in the Spoken language, or in English when translating.

### What the app asks the service for

Each Side of the Recording is one Run, and every Run of a Job carries the same settings. The task and language fields follow the user's two choices:

| User's choice | Request to the WhisperX service |
|---|---|
| Translate ticked, Spoken language Automatic | `task=translate_if_needed`, `language` empty: the service detects, then transcribes if the speech is English and translates otherwise. |
| Translate ticked, Spoken language chosen | `task=translate_if_needed` with the code: `en` means transcribe, any other code means translate. No detection. |
| Translate unticked, Spoken language Automatic | `task=transcribe`, `language` empty, and `translate_if_mixed=true` while the admin setting "Translate mixed-language Recordings to English automatically" is On (`false` when it is Off). |
| Translate unticked, Spoken language chosen | `task=transcribe` with the code. No detection, so no mixed rule. |

The rest of the request:

- `model`: the admin setting **Model** (`large-v3-turbo`, the default since the Phase 1 benchmark gate, or `large-v3`). The model used is recorded on the Recording at submission, in the "Batch submitted" audit row, and in the Provenance.
- `diarize` and `speakers`: as in the table above.
- `vocabulary`: the Office Vocabulary first, then the Batch's own Vocabulary, as one list of strings. The service builds Whisper's prompt itself from the `context` line and the list, keeps it under 200 tokens by dropping terms from the end of the list, and reports `vocabulary_terms_used` and `prompt_tokens` in the result, which the Provenance keeps. Because the Office Vocabulary comes first, the Batch's own terms are the ones dropped when the prompt is too long. The service refuses more than 200 terms or a context line over 500 characters; the caps are in the WhisperX service API document.
- `context`: the one-line context sentence, empty when none was given.
- `return_speaker_embeddings`: `false`. Embeddings are not requested or stored in Phase 1.
- `client_reference`: the Run's id.

The ASR audio sent is the same prepared file whether the task is transcribe or translate (see the Media handling chapter). No title, file name, or user name travels to the service.

### Language detection and the "language uncertain" warning

- With `language` empty, the service samples three 30-second windows: the start, one third in, and two thirds in. A Run under 90 seconds gets as many non-overlapping windows as fit, at least one. Each window reports a language and a probability.
- **Mixed**: at least two windows report different languages, each with a probability of 0.5 or more.
- **Otherwise** the language with the highest combined probability wins and is the detected Spoken language.
- When the winner's combined probability is under **0.6**, the Recording carries a **"language uncertain"** warning in the viewer header and in the Provenance, pointing at Process again with the language chosen.
- Detection is best effort. An interpreted interview where every window holds both languages may still come out as one language; the warning and Process again cover it.

### The mixed-language rule and its toggle

- When the service finds a mixed Run, it translates the whole file to English, whether or not "Translate to English" was ticked, as long as the admin setting **"Translate mixed-language Recordings to English automatically"** is On (the default). Off means the Recording is transcribed in its winning language and carries only the warning.
- Under translate the service tells Whisper the non-English language with the highest combined probability; English speech passes through untranslated under the translate task anyway.
- An interpreter-mediated interview therefore comes out as one English Transcript holding the interpreter's rendering and the machine's rendering of the witness side by side; Diarization keeps them apart. The user guide explains this, and that word timing is lost under translation.
- No splitting by Speaker, no automatic second Run, no merging of a transcribe Run and a translate Run.

### Transcripts in the Spoken language

- Translate unticked and a single non-English language: the Transcript is in that language (an interpreter checking a jail call wants the Spanish).
- Word timing exists when the service can align the language. The alignment models for English and Spanish are fetched when the service is installed; any other language's model is fetched on first use when the network allows. When no alignment model is available the result is segment-timed with the reason `no_alignment_model`, and the viewer says:

```
Word timing unavailable for <language>
```

- One Recording holds one Transcript. A user who wants both the Spanish text and the English uploads the Recording twice in Phase 1.
- Summary and Chat are written in English whatever the Transcript's language, and their prompts are told the Transcript is a machine translation or a machine transcription (see the AI assistant chapter).

### What the app stores per Recording

For the Provenance and the viewer markers, the app keeps on the Recording: the task it asked for; the task the service actually ran (`task_run`: `transcribe` or `translate`) and why (`task_reason`: `requested`, `english_detected`, `mixed_detected`); the Spoken language as chosen or detected, with its probability; each detection window's language and probability, the combined total per language, and whether the Run was mixed; and the `word_timestamps` flag with its reason (`translation` whenever the service ran translate, including when it chose to; `no_alignment_model` for a language it could not align). Nothing is stored per Segment: the language is one per Run, so there is no per-Segment language marking.

### Process again

- The Details panel offers Process again with the Recording's settings pre-filled: Spoken language, Translate to English, Diarization and its hint, Vocabulary, context line. The user edits them and submits; the app makes a new one-Recording Batch and Job through the normal line, and the new Transcript replaces the old one when it lands. The mechanics (the one-Batch rule, the locked old Transcript, the banner, Cancel) are in the Queue and Jobs chapter.
- **Lost**, and the user is warned before submitting: Corrections, Speaker names and merges, and Speaker suggestions.
- **Kept**: Summaries and Chats, marked as based on an earlier Transcript once the new one lands; Clips keep their time spans and rendered files, and their transcript excerpts are refreshed from the new Transcript.
- The Provenance keeps both processings. The audit log records the re-run as "Batch submitted" with its settings.

### No LLM in the translation path

No polishing, no rewriting, no post-editing by a model, because the original-language text is not kept and nothing could check the result. Chat and Summary prompts are told the Transcript is a machine translation (or a machine transcription) so they can say so when it matters.

### Marking in the viewer and the Provenance

| Case | Viewer header | Details and Provenance |
|---|---|---|
| Translated, language chosen | "Translated to English from Spanish" | Spoken language: Spanish (chosen); task: translate (requested) |
| Translated, language detected | "Translated to English from Spanish" | Spoken language: Spanish (detected, 97%); task: translate (requested) |
| Mixed, translated by the rule | "Translated to English (Spanish and English detected)" | the windows and their probabilities; task: translate (mixed detected); a Process again link |
| Translate ticked, English detected | none (an ordinary English Transcript) | task: transcribe (English detected) |
| Not translated, non-English | a "Spanish transcript" pill | Spoken language: Spanish (chosen or detected) |
| Winner under 0.6 | a "Language uncertain" warning | the probability and a Process again link |

Spanish stands for whichever language applies. Every translated Recording's Details panel states that word timing is unavailable because the Recording was translated.

### Notices on exports

Two admin-editable texts in the panel, **"Translation notice"** and **"Transcription notice"**. The placeholders `{language}` and `{model}` are filled from the Provenance, so the wording stays true when the model or the language changes. For a mixed Recording `{language}` reads "Spanish and English" (the two languages detected).

Default Translation notice:

```
Machine translation to English from {language} by Whisper {model}. The original-language text was not kept. This is not a certified translation.
```

Default Transcription notice:

```
Automatic transcription by Whisper {model}. Corrections made by staff are marked. This is not a certified transcript.
```

- **One notice per export**: the Translation notice on a translated Transcript, the Transcription notice on every other one. Never both.
- Where a notice is printed: the Word export of a Transcript, the plain-text export (and so each file in a Batch download and in Download everything), the Clip transcript excerpt, and the Word export of a Summary written from that Transcript, because the Summary inherits the translation's limits.
- Never on Captions: an SRT file carries no notice, and a notice is never burned into a Clip's picture.
- The Exports chapter fixes the notice line's placement and the "Translated to English from ..." header on the Word export; the Clips chapter fixes the excerpt.

### The benchmark gate's translation checks

The translation leg of the Phase 1 benchmark gate has four checks, scored by the office with a bilingual reader. A word-error rate needs a reference transcript nobody has, so the reader's judgement on names and numbers is the bar.

1. **Spanish call or interview.** A two-minute excerpt read against the audio: pass when every name, number, date, and amount is right and the reader rates the English as understandable without the audio. Any wrong name or number fails.
2. **Interpreted interview**, under both paths (Translate ticked; Translate unticked with Automatic, so the mixed rule fires): pass when nothing the witness said is missing from the English, and the doubled text is legible with Diarization on.
3. **English Recording with Translate ticked**: the text must equal the plain transcription and keep word timing (proves `translate_if_needed`).
4. **Spanish jail call with the English announcement**, Automatic: must be detected as Spanish (proves the three-window detection).

### Environment keys

None of the app's own. The languages whose alignment models the service fetches at install are the service's own setting `WHISPERX_ALIGN_LANGUAGES` (default `en,es`), in the WhisperX service API document; the "Word timing unavailable" rule above follows from it.

### Audit rows

| Row | When it is written |
|---|---|
| Batch submitted | At Submit, and for a Process again, with each Recording's settings: Diarization choice and hint, Translation, whether Vocabulary was given (never the terms), preprocessing profile, model. |

Vocabulary terms, the context line, and Transcript text never appear in the audit log or in the service's logs.

### Settings

- **Translate mixed-language Recordings to English automatically** (default On): whether a mixed Run is translated by the rule; sets `translate_if_mixed` on Automatic transcribe requests.
- **Translation notice** and **Transcription notice**: the two export texts, with the defaults above.
- **Model**: the model named in every Run and printed by `{model}`.
- **Office Vocabulary**: sent ahead of the Batch's own Vocabulary in every Run.

### Left to the build

- The four translation checks of the Phase 1 benchmark gate run when the office supplies the Spanish and mixed-language samples, which the test corpus does not yet hold; the checks are defined above and wait only for the samples. Fixed: scored by the office with a bilingual reader; names, numbers, dates, and amounts are the bar; no word-error rate.
- The user guide must explain the two paths for an interpreted interview and the loss of word timing under translation; the admin guide must explain the notices and their placeholders (see the Repository, releases, and distribution chapter).
- Not fixed by the tickets, so the build decides or asks: the viewer header and Provenance line for a mixed Run when the toggle is Off ("carries only the warning"), and for a mixed Run when Translate was ticked (the table gives the header for the rule's case only); how a multi-Side Recording whose Runs detected different languages is marked, since detection is per Run and the markers are per Recording.

### Carried for Phase 2

- Nothing is fixed. The rule that a user who wants both the original-language text and the English uploads the Recording twice is stated for Phase 1; no Phase 2 replacement is decided.

### Sources

"Translation-to-English behaviour"; "App-side transcription queue and job model" (Process again mechanics, the Two-channel call hint, the audit row); "WhisperX service API and operating contract" (context only: request fields, the Model allow-list, the prompt rule, the alignment languages).

### Amendments applied

- From the translation ticket to the WhisperX service contract: `task=translate_if_needed`, the `translate_if_mixed` request field, three-window detection with the `windows`, `combined`, and `mixed` result parts, `task_run` and `task_reason` in `settings_used`, and `word_timestamps.reason` of `translation` whenever the service ran translate; all written here as the request and storage rules.
- From the Upload page ticket to the queue ticket: a Two-channel call with Diarize ticked sends each Side's Run with an empty speaker hint.
- From the queue ticket to the translation ticket's open mechanics: Process again is a one-Recording Batch through the normal line, its audit row is "Batch submitted", and the old Transcript stays readable but locked until the new one lands.


## 8. Transcript viewer and player

The viewer is the page where a user plays one Recording and reads, searches, corrects, and exports its Transcript. It plays the Playback copy only; the uploaded bytes are never served to the player. A user reaches it by Open on the Recordings page, by itself from the queued page once playback is Ready (see "Before the Transcript exists" below), from a Citation in a Summary or a Chat answer, and from Open in viewer on the Clips page (see the Clips chapter).

Nothing in this chapter is deferred from Phase 1. Light and dark themes both ship. The browsers are current Edge and Chrome, as the Media handling chapter says. The CSS is fresh, written for this app, with a light and a dark theme; no code or styles are reused from any other app.

A prototype exists in the planning repository at `prototypes/transcript-viewer/` (`viewer-prototype.html`, `peaks.js`, `make-samples.sh`; `media.js` and the synthetic media are regenerated by the script and kept out of git). Its Desk layout is the picture behind this chapter; its Studio and Bench layouts stay in the file as rejected alternatives. This chapter wins wherever the prototype differs from it.

### The Desk layout

The Transcript comes first, in the **work area**, a tabbed area that takes the full width of the page under the head and the Timeline: **Transcript**, **Clips**, **Summary**, **Chat**, **Moments** (on a video with Moments on), **Details**, one at a time, each at the area's full width and height (v1.46.0). Beside it on a window 1280 pixels or wider stands the **stage**: the picture, the transport under it, the line being spoken, and Describe this moment, a column resizable by its right edge from 360 pixels to half the window. On a narrower window the stage is not a column: the picture sits beside the title at 160 pixels and the transport under it, and the work area takes the rest, so a laptop shows the same page smaller. A sound recording has no picture and no stage at any width; its transport sits under the title. The head above holds the search box, the one primary (New Clip), and two menus, **Export** and **More**; the Speakers are a strip at the head of the Transcript tab, stuck under the tab bar so they never scroll away. The layout is built for correctors and interpreters who live on the keyboard, and for the wide monitors an office actually has, without taking anything from a laptop.

Before v1.46.0 the page was the Desk of the prototype (a left sidebar, the Transcript at reading width, the picture and the panels in a right-hand column, the Bench, from v1.4.0, or a bottom sheet on a laptop); the maintainer's review of 2026-09-12 found the tools squeezed beside the picture and the speakers out of view while tagging, and chose the stage and the work area from four mockups.

```
+------------------------------------------------------------------+
| Header: back, title, markers | search | New Clip | Export | More |
| Timeline: waveform; the marking strip under it                   |
+----------------------+-------------------------------------------+
| STAGE                | WORK AREA                                 |
|  picture (Pop out)   |  Transcript | Clips | Summary | Chat |    |
|  transport, clock    |  Moments | Details                        |
|  Now: 0:42 Ruiz ...  |  Speakers: chip chip chip           hide  |
|  Describe this moment|  0:04   Officer Ruiz   Licence and ...    |
|  <- drag ->          |  0:09   Speaker 2      Yeah, hold on ...  |
|                      |  one row per Segment: time, name, words   |
+----------------------+-------------------------------------------+
```

- **The work area**: the tabs along its top, one panel at a time at full width and height, each scrolling inside itself. The tab chosen is remembered; a link that names a panel (`?panel=`) wins; D opens Details. The **Transcript** tab holds the Speakers strip and the Transcript (see "The Transcript" below); it is the only thing that scrolls in Follow mode. The others hold what the chapters give them: Clips (the Clip tool and the Recording's Clips list), Summary, Chat, Moments (the Phase 4 chapters), Details (the Provenance).
- **A tab in its own window** (v1.47.0): **Open in a window** at the end of the tab bar opens the tab shown (never the Transcript) in a window of its own, drawn from the same markup with that one panel, and the page goes back to the Transcript; the tab is marked as away and pressing it brings the window to the front. The window follows the page through the browser's own channel between them: the page sends the time and the line being spoken; the window sends a seek (a Citation, Play on a Clip), a Clip range, and word that something changed, on which the page reads its state again. A window opens nothing the page does not offer, and nothing to somebody who may not open the Recording. On a second monitor the words stay on one screen and the tool sits on the other.
- **The stage**, on a wide window: the picture at the column's width, which pops out to a floating window (the `Pop out video` and `Dock video` control on the picture itself; while popped out the picture's slot reads `Video popped out`); the transport under it; the line being spoken (its time, Speaker and words) and, on a video with Moments on, **Describe this moment**; the grip on its right edge, dragged, double-clicked to reset, or moved by the arrow keys. On a laptop the same picture sits beside the title, the transport under it, and the line being spoken with Describe this moment on a row under the marking strip.
- **The Timeline**, under the head at the width of the window: the waveform; click to seek, drag to mark a Clip. For a Two-channel call the waveform is split into one lane per Side. Under it the **marking strip**: at rest one sentence; while a range is marked, the range, its length and its Segments, **Preview**, **Save clip** and **clear**. Marking a Clip by any route fills the strip and never changes the tab under the reader; Save clip, New Clip and Adjust open the Clips tab.
- **The header's menus** (v1.45.0, in place of the left sidebar): the search box with its match count; **Export**, a menu of Word, plain text and Captions; **More**, a menu of the keyboard shortcuts, Process again and, last and red inside the menu only, Delete this recording. Nothing is red at reading height.
- **Overlays**: the shortcuts list opens as an overlay from the More menu or `?`. Esc closes an open menu, an overlay, a marking in progress, or a marked range.
- **Header**: a control back to the Recordings page, the Recording's title, the markers (see "Markers" below), the search box, New Clip, the Export and More menus, and the light and dark theme toggle.

### Player and transport

- The player plays the Playback copy only.
- **Speed**: 0.5x to 2.5x in 0.25 steps (0.5x, 0.75x, 1x, 1.25x, 1.5x, 1.75x, 2x, 2.5x), from a Speed control on the transport and from the `[`, `]`, and `0` keys.
- **Boost**: volume above 100%, up to 400%, through a Web Audio gain node, from a Boost slider on the transport that shows the percentage. It exists because browsers cap volume at 100% and quiet Recordings are common.
- **Balance**: on a Two-channel call, a slider on the transport between the two Sides, labelled with the two Sides' Speaker names, that shifts the sound towards one Side.
- The speed range, the Boost ceiling, and follow-by-default are build constants, not admin settings.
- **Transport buttons**: Play or Pause; back three seconds and keep playing (the foot-pedal substitute); back and forward 5 s; one frame back or forward; the Speed control; the Follow button; Boost; and Balance on a Two-channel call. The keys for each are in the table below.
- **Frame stepping**: one frame back or forward, with the frame rate taken from the Provenance; an audio-only Recording steps 0.1 s.
- The transport is disabled while the Playback copy is still being made (see "Transcript ready before the Playback copy" below).

### Keyboard

Shortcuts work whenever the user is not typing in a box. The list opens from the More menu or `?`.

| Key | Does |
|---|---|
| Space | Play or pause |
| B | Back three seconds and keep playing (foot-pedal style) |
| Left, Right | Back or forward 5 s |
| Shift + Left, Right | Back or forward 1 s |
| Ctrl + Left, Right | Back or forward 30 s |
| , and . | One frame back or forward (0.1 s on an audio-only Recording) |
| Up, Down | Previous or next Segment |
| [ and ] | Slower or faster, one 0.25 step |
| 0 | Normal speed |
| F | Follow mode on or off; resumes it while it is paused |
| E | Correct the current Segment |
| Ctrl + Enter | Save the Correction |
| Esc | Cancel the Correction; close an overlay or panel |
| / | Put the cursor in the search box |
| Enter, Shift + Enter (in the search box) | Next or previous match |
| I, O | Clip start or end at the playhead |
| S | Snap the Clip to the current Segment |
| P | Preview the Clip |
| D | Open the Details panel |
| ? | The shortcuts list |

The decision fixes every row except `/`, `D`, `?`, and Esc as "close", which come from the prototype's list unchanged. The transport keys do nothing until playback is Ready; the keys that need a Segment (Up, Down, E, S) have nothing to act on until the Transcript exists.

### Follow mode

- Follow mode is on by default. While the Recording plays it keeps the current Segment in the middle of the Transcript column, scrolling it to the centre only once it has left the middle band (about a fifth of the way down to three quarters; v1.49.0, because centring every new line made a column of short lines creep), and underlines the current word when word timing exists (word timing exists whenever the Transcript is not a Translation). The "Following paused" pill sits in a holder of no height, so its coming and going moves no line.
- When the user scrolls the Transcript by hand, following pauses and a pill appears at the top of the Transcript column:

```
Following paused while you read. Resume (F)
```

- F, the pill, or the Follow button resume following. While it is paused the Follow button reads `Follow (paused)`.
- F and the Follow button also turn Follow mode off and on altogether.
- While a Correction is open, Follow mode does not scroll the Transcript.

### The Transcript

#### Rows and seeking

- One row per Segment: the time, the Speaker's name in the Speaker's colour with a colour bar, and the text. Each Speaker has one colour, used for the name and the colour bar.
- Clicking a row seeks the player to the Segment's start.
- The current Segment is highlighted; the current word is underlined when word timing exists.
- A corrected Segment carries a ✎ mark. Segments inside a Clip's marked range are tinted.
- Every row carries a `+ Clip` control for the Clip tool (see "Clips in the viewer").

#### Search

- The search box sits in the header (v1.45.0; the sidebar before); `/` puts the cursor in it. Typing filters the rows to the matches, highlights the match in each row, and shows the match count. Enter jumps to the next match and Shift + Enter to the previous one.

#### Correction

- A Correction changes a Segment's text. It starts by double-clicking the Segment, by the `✎ Edit` button that every Segment carries (visible on hover and on the current Segment), or by E for the current Segment. The row becomes a text box holding the Segment's text.
- Ctrl + Enter saves; Esc cancels.
- A corrected Segment carries a ✎ mark in the viewer, and exports print `(corrected)` after its Speaker name (see the Exports chapter).
- Every Correction writes an audit row (the row never holds the text; see the Audit log and logging chapter).
- A Correction inside a Clip's span marks a Clip with burned captions "Captions out of date" (see the Clips chapter). Clips without burned captions are unaffected, because their excerpt and captions are built from the live Transcript at download time.

#### Markers for Diarization, Sides, and Translation

- The **Speakers toggle**, at the end of the Speakers strip, hides and shows the Speaker labels.
- A Recording processed without Diarization shows the plain flow of Segments and a `Not diarized` pill in place of the toggle (the pages say Diarize).
- A Two-channel call shows its Sides as Speakers, a `Two-channel call: 2 Sides` pill, and the waveform split into one lane per Side. On a Two-channel call diarized per Side, a Side with one Speaker is labelled by its Side alone (`Side 1`) and a Side with more as `Side 1 Speaker 1`, `Side 1 Speaker 2`; the Speakers panel follows the same labels.
- A Translation shows the marker `Translated to English from <language>` in the header (its tooltip says the speech was recognised in that language and translated to English, that the original-language text is not kept, and that word timing is not available for translations) and no word underline, since a translated Transcript has Segment timing only.

### Speakers panel

The Speakers panel is the strip at the head of the Transcript tab, stuck under the tab bar so it never scrolls away (v1.46.0; from v1.45.0 it scrolled with the Transcript, and the sidebar held it before); **fold** at its end folds it to one line with the count of Speakers, remembered in the browser (v1.49.0). It lists the Recording's Speakers as chips in their colours, with the line "Click a name to rename it. Drag one Speaker onto another to merge them (when two labels are the same person)." It names one Recording's Speakers only.

#### Rename and merge

- **Rename**: click the name; a prompt takes the new name. The new name applies to every Segment of that Speaker.
- **Merge**: drag one Speaker onto another, or use the Merge control (choose the Speaker to merge and the Speaker to merge it into, then Merge). Both routes ask for confirmation first; the prototype's wording is `Merge <A> into <B>? Every Segment of <A> becomes <B>.` A merge relabels every Segment of the merged Speaker.
- A rename and a merge each write an audit row (the row never holds the names).
- A rename or merge marks a Clip with burned captions in the affected span "Captions out of date" (see the Clips chapter).

#### The Speakers window

**Tag speakers** on the strip opens the Speakers window (v1.47.0), a window of its own for matching voices to names while the Recording plays. It plays the Recording itself (v1.48.0): the picture, or the sound alone, with a scrub bar under the picture (v1.49.0), Play, back three seconds, five seconds either way, the clock and the speed, and the page's keys; whichever of the page and the window played last has the sound, and the other follows along, so the page's rows light as the window plays. Under the player, the line being spoken at the top with its time, Speaker and words, and the Recording's Speakers under it, one row each with a number key, the count of its lines and a sample line. A number key, or a press on the row, gives the line being spoken to that Speaker: one Segment changes hands, the row `Speaker changed on a line` is written (no name), and the change is remembered beside the renames and merges so Undo puts that one line back. **play a line** seeks the page to a line of that Speaker; **rename** and **same person as** are the panel's rename and merge, with the same confirmation; **Undo** is the panel's. Space plays and pauses and B goes back three seconds, in the window's own player. The page redraws its rows as lines change hands and reloads after a rename or a merge. From v1.50.0 the strip's button reads **Manage speakers** and opens the Speakers page, and the Speakers window is that page opened in a window, with the following and the channel as above; the page is Phase 5's first chapter (`docs/spec/SPEC-PHASE-5.md`).

#### Speaker suggestions

- Whenever two or more Speakers have no name, the panel shows the line `Want name suggestions from what people say?` with a `Suggest names` button. Suggestions appear only after that click; nothing runs by itself. The prompt and the result are the AI assistant chapter's.
- Each suggestion carries its reason, the Segment it came from.
- Suggestions appear in the Speakers panel, with Accept and Reject, and inline in the Transcript next to the Speaker name on the first Segment of that Speaker only, as a dashed pill:

```
Suggested: <name> ✓ ✗
```

  Its tooltip names the AI assistant, gives the reason Segment, and says nothing changes until the user accepts. The pill reads unmistakably as a suggestion and does not repeat on every row.
- Nothing changes until a suggestion is accepted. Accepting applies the name to every Segment of that Speaker; rejecting removes the suggestion. Each acceptance and each rejection writes an audit row.
- From v1.50.0 the Speakers page offers Suggest names as well, under these rules, and each suggestion shows on its Speaker's card there with Accept and Reject (Phase 5, chapter 1).

### Clips in the viewer

The Clips chapter owns the Clip: its fields, rendering, downloads, limits, and lifecycle. The viewer owns the marking and previewing tool and the Recording's Clips list, both on the Clips tab of the work area (v1.46.0), and the marking strip under the Timeline.

- **Marking a start and an end**: I and O at the playhead while playing; typing the times; Snap to the current Segment (S), which sets the start and end to that Segment's (when a start has been marked and no end yet, Snap extends the range to the Segment's end, as the prototype does); `+ Clip` on any Segment in the Transcript, which extends the range to include that Segment; or dragging on the Timeline. Any of these fills the marking strip under the Timeline and leaves the tab under the reader alone; Save clip in the strip, New Clip in the header, and Adjust on a Clip's card open the Clips tab (v1.46.0; until then any route opened the sheet at Clips).
- The tool shows the range's length and the number of Segments in it (or `No range yet`), a Clear control, and Preview.
- **Preview** (P) plays the range and stops at its end.
- **Title** (required, prefilled `Clip 1`, `Clip 2` per Recording), an optional **note**, and the two options: `Burn captions into the video` (off by default; shown for a video Recording only) and `Include the transcript excerpt` (on by default). The limits on each are the Clips chapter's.
- **Save** renders the Clip on the media worker (see the Clips chapter). The tool for a saved Clip reads `Adjust Clip` instead of `New Clip`.
- **The Clips list** in the sheet shows each Clip's status, span, length, and options, and offers **Download all**, one zip of the Recording's Ready Clips with their excerpts and captions, once there is one (v1.49.0; in a Case every collaborator's Clips of the Recording, elsewhere the person's own), with Download, Play (seeks the player to the Clip's start), Adjust (start, end, options; re-renders and clears the downloaded mark), Rename (title and note; renders nothing), and Delete (confirmed: `Delete this Clip?`). The statuses are `Rendering`, `Ready`, `Failed` (with Retry beside Delete), and `Captions out of date` (with a Re-render button, on a Clip with burned captions whose Transcript changed since it was rendered).
- The Clips panel, New Clip, and `+ Clip` are hidden while the "Clips available" setting is Off.

### Export, Summary, and Chat

- **Export**, a menu in the header (v1.45.0; the sidebar before), offers the Transcript's exports: **Word**, **plain text (.txt)**, and **Captions (.srt)**. Each is written at the moment of export from the live Transcript, carries what the Exports chapter fixes (the Word layout and its Processing record; the plain-text shape with its head, the one notice, and `[hh:mm:ss] Speaker: text` lines with `(corrected)` after the name; the Captions cues with no notice), and writes an audit row. No VTT is produced in Phase 1.
- **Summary** is a tab of the work area (v1.46.0) that lists the Transcript's Summaries, each with Export to Word, Regenerate, and Delete, and a `New summary` dialog with a Summary template choice (shown only when two or more templates are Enabled), an optional Focus box, and a Length choice of Short, Standard, or Detailed. Every time in a Summary is a Citation, a link that seeks the player. The AI notice sits at the top.
- **Chat** is a tab of the work area (v1.46.0) with a thread list (New chat, Delete per Chat), the conversation, Copy per answer, and Export to Word. Answers cite Segments; each Citation seeks the player. The AI notice sits at the top.
- Both panels show `Reading the transcript...` while the AI assistant works and deliver whole answers; there is no streaming.
- The content of Summaries, Chats, and Speaker suggestions, their prompts, and their exports are the AI assistant chapter's and the Exports chapter's decisions.

### Details panel and the Provenance

The Details tab of the work area (also D) shows the Provenance: where the Recording came from and how it was processed, as name and value pairs. It is the same Provenance that is printed on every export, and it never holds Transcript content. The Media handling chapter fixes the entries: the original name, size, hash, uploader and time, the technical facts (container and duration; streams, with the frame rate the viewer uses for frame stepping; the sound sources found and used, from which the Sides are made; Two-channel detection; Sides), and every setting and model used (Preprocessing profile and the loudness measured and applied, the ASR model, Diarization and its Speaker-count hint, Translation, Vocabulary, the WhisperX service version, the Playback copy, the processing times and pipeline version). The Provenance also carries one Clip line per Clip that exists at the time (span, options, render time); a deleted Clip drops out.

### Before the Transcript exists

Live status reaches the open page (server-sent events or polling; the Queue and Jobs chapter decides), so every change below happens by itself, without a reload. The pages say "your recordings", never Workspace.

#### The queued page

Opening a Recording whose Job is Queued or Running, before its playback is Ready, shows the queued page in the viewer's place:

- **Queued**: the Job's position and the Queue length (`Position 3 of 5`), the Estimated wait, worked out from the Recordings ahead, the line "you can leave this page", and Cancel.
- **Running**: the current Step and a progress bar, with the line `Diarization follows` beside "you can leave this page".
- Cancel's confirmation names the Recording's Clips when any exist (the wording is in the Clips chapter); a Cancel removes the Recording as if never uploaded, Clips included.

#### The viewer before the Transcript

As soon as the Recording's playback readiness is Ready (the Playback copy and the waveform, media steps 6 and 7, which run beside recognition), even while the Job is still Queued or Running, the queued page becomes the viewer:

- The media dock, the transport, and New Clip are live, and the Timeline is the waveform.
- Where the Transcript will go, the page shows the Job's position and Estimated wait, or its Steps while Running, and Cancel.
- Marking a Clip by I and O, typed times, and dragging on the Timeline works, as do Preview and Save. Snap to Segment, `+ Clip`, and both Clip options are greyed with the text `available once the transcript is ready`.
- When the Job finishes, the Transcript appears in place and the greyed controls come alive. Nothing about the Clips saved meanwhile is announced and nothing re-renders by itself (see the Clips chapter).

#### Transcript ready before the Playback copy

Recognition can finish before the Playback copy is ready. Then an overlay reading `Preparing video` (or `Preparing audio`) covers the thumbnail, the transport is disabled, and the Transcript is fully usable: reading, search, and Correction all work. The prototype's sub-line under the heading reads: "The Transcript is ready; you can read, search, and correct it now. Playback starts when the Playback copy is done (a few minutes for long video)." The overlay lifts by itself when the Playback copy is done.

### An Admin in another user's Recording

Through "Open their Workspace" on the Admin panel's users list, an Admin opens another user's Recordings page and this viewer for any of that user's Recordings, under the audit banner (its wording is the Audit log and logging chapter's). Every media file served to the Admin there, the Playback copy or a Clip's file, writes an audit row carrying the affected user. The Admin sees the Recording's Clips sheet and may play and download its Clips, each download an audit row with the affected user that never sets the owner's downloaded mark; the Admin does not adjust, rename, or delete another user's Workspace Clip. What else an Admin may do in another user's viewer, and what each row carries, is the Admin panel and Audit log chapters' rule; every such row carries the affected user.

### Build notes

- The app draws the waveform itself from the audiowaveform peaks JSON with a small canvas routine, as the prototype does; there is no wavesurfer.js dependency.
- Boost is a Web Audio gain node; the prototype's balance splits the Playback copy of a Two-channel call into its two Sides, applies a gain to each, and merges them again.
- The frame rate for frame stepping comes from the Provenance, so the Media handling chapter keeps it there.
- Word timestamps come from the WhisperX service whenever it is not translating (see the WhisperX service API document); the word underline depends on them.
- The Queue chapter supplies the position, the Queue length, the Estimated wait, live status to the open page, and Cancel.

### Audit rows

The Audit log chapter fixes each row's name and contents. The viewer writes a row for each event below; no row ever holds Transcript text, search terms, Speaker names, or Clip titles and notes.

| Event | Written when |
|---|---|
| Correction | A Correction is saved (Ctrl + Enter) |
| Speaker renamed | A rename is confirmed in the Speakers panel |
| Speakers merged | A merge is confirmed, by drag or by the Merge control |
| Speaker change undone | Undo in the Speakers panel puts the last rename or merge back (v1.36.0), or the last line given to a Speaker (v1.47.0) |
| Speaker changed on a line | A number key in the Speakers window gives the line being spoken to a Speaker (v1.47.0) |
| Recording renamed | A new title is confirmed, in the viewer or on My recordings (v1.36.0) |
| Suggestion accepted | ✓ on a Speaker suggestion, in the panel or on the inline pill |
| Suggestion rejected | ✗ on a Speaker suggestion, in the panel or on the inline pill |
| Export (Word, plain text, or Captions) | An export file is produced from the Export entries |
| Media served to an Admin for another user | The Playback copy or a Clip's file is served under the audit banner; carries the affected user |
| Clip events | See the Clips chapter |

### Settings

The viewer adds no setting: the speed range, the Boost ceiling, and follow-by-default are build constants. It depends on these rows of the admin settings catalogue:

- **Clips available**: Off hides New Clip, the Clips panel of the sheet, and `+ Clip`.
- **Longest Clip**: the ceiling the Clip tool enforces on a range.
- The Summary templates and their Enabled state: the `New summary` dialog offers a template choice only when two or more are Enabled.

No environment key belongs to this chapter.

### Left to the build

- The reading width (900 pixels to v1.44.0, 1,040 from v1.45.0, when the sidebar's width went to the words), the Speaker colour palette, and the rest of the CSS: fresh, with light and dark themes, nothing reused from other apps; the prototype is the reference.
- The exact wording of the queued page and the Running page beyond the fixed elements (position and Queue length, Estimated wait, "you can leave this page", `Diarization follows`, Cancel); the prototype's sentences may be kept, except that pages never say Workspace.
- The live status route to the open page: server-sent events or polling, as the Queue and Jobs chapter decides.
- Whether playback pauses by itself when a Correction starts: not fixed. The prototype keeps playing and only stops Follow mode from scrolling while the Correction is open.
- The rename prompt's form: "a prompt" is all that is fixed.
- The wording of the audit banner: the Audit log and logging chapter's.
- The list of Provenance entries the Details panel shows: the Media handling chapter's, in the order it gives them.

### Carried for Phase 2

- The viewer opens at a given Recording and time from a link (Open in viewer on the Clips page, a Citation). In Phase 2 a Citation in a Case Chat names the Recording as well and opens it in the viewer at that moment through the same route.
- The Speakers panel names one Recording's Speakers only. In Phase 2 the Case's Speakers tab is the place a Person is renamed for the whole Case, merged, or deleted (see the Cases chapter); the panel does not gain that.
- The audit banner and the affected user apply unchanged when an Admin who is not a Collaborator opens a Recording in a Case.
- "Clips available" Off will also hide the Case's Clips tab (see the Clips in Cases chapter).

### Sources

Transcript viewer and synced player; Clips: model, lifecycle, and management (its amendment to the viewer and the facts it records from the Word export ticket).

### Amendments applied
- From the maintainer, after a day on the stage (v1.49.0): Follow mode scrolls only once the line has left the middle band, and the "Following paused" pill takes no height, so the column neither creeps nor jumps; the Speakers strip folds to one line; Download all on the Clips tab; a scrub bar in the Speakers window; the chat's list redrawn only when it changed. The shortcuts overlay and the pop-out, lost in the v1.46.0 rewrite, put back.
- From the maintainer, on the v1.47.0 build ("it feels a bit off having that pop out and also trying to move it around to see or hear the audio/video"), the Speakers window plays the Recording itself (v1.48.0): its own picture or sound and transport; the sound to whichever of the page and the window played last; the page following the window's clock.
- From the maintainer, on the v1.46.0 build, the windows (v1.47.0): any tab of the work area in a window of its own, kept in step with the page through the browser's channel; the Speakers window with a number key per Speaker, and with it the one-line change `Speaker changed on a line`, remembered beside the renames for Undo.
- From the maintainer, on the v1.45.1 build ("the features are gonna squish too much"), the stage and the work area (v1.46.0), chosen from four mockups: the work area a tabbed area at full width, Transcript first, one tab at a time; the stage a column on the left with the picture, the transport, the line being spoken and Describe this moment, resizable by its right edge; on a laptop the picture beside the title and the same tabs below; a sound recording without a stage; the sheet, its grip, Expand and Close withdrawn, so the two shapes of the page are one page; the Transcript as a Ledger (time, the name in a column of its own, the words, the row's buttons; a speaker's second line in a row leaves the name blank; 16 px); the Speakers strip stuck under the tab bar; the marking strip under the Timeline, so no route of marking changes the tab; a Citation opening the Transcript tab. The Desk diagram redrawn again.
- From the maintainer, on the v1.43.0 build ("do another review of the recording page ... giving the main things more space to move"), the first layout slice (v1.45.0): the left sidebar withdrawn; the search box, New Clip, and the Export and More menus in the header, the housekeeping (shortcuts, Process again, Delete) inside More and nothing red at reading height; the Speakers a strip at the head of the Transcript column that scrolls with it; the pop-out control on the picture; the reading width 1,040 pixels; each row's buttons in a column of their own rather than over the words; the sheet's tabs drawn as the case page's underline tabs; the Bench column 400 to 620 pixels with the window; the `No word timing` pill dropped from the header (the Details panel says it and the missing word underline shows it); the Timeline's caption one sentence. The Desk diagram redrawn.
- From the maintainer, on the first Teams call (v1.35.1), to the Speakers panel, built in v1.36.0: a rename or a merge is remembered on the Transcript (`speaker_changes`, the moved Segment ids, kept to the last twenty) and **Undo** under the chips puts exactly those Segments back under their old name, newest change first, touching only Segments that still carry the given name; a **Rename** control beside the title lets the people who work in a Recording (standing "own", not an Admin looking in) give it a new title, the file name kept, writing "Recording renamed" without the title.

- From the LLM features ticket, recorded on the viewer ticket, to the queued page: the Running line reads `Diarization follows`.
- From the LLM features ticket to the Speakers panel: the `Want name suggestions from what people say?` line and the `Suggest names` button; suggestions appear only after the click.
- From the LLM features ticket to the Summary overlay: the `New summary` dialog (template choice when two or more are Enabled, Focus, Length: Short, Standard, Detailed) and the list of Summaries with Export to Word, Regenerate, and Delete.
- From the LLM features ticket to the Chat overlay: the thread list (New chat, Delete per Chat), Copy per answer, Export to Word.
- From the LLM features ticket to both overlays: times are Citations that seek the player; `Reading the transcript...`; whole answers, no streaming.
- From the Clips ticket to the viewer: the viewer opens once playback is Ready before the Transcript (bare Timeline, position and Estimated wait or Steps in the Transcript area, New Clip live, Snap and `+ Clip` and both options greyed with `available once the transcript is ready`).
- From the Clips ticket to the Clips sheet: the statuses Rendering, Ready, Failed, and Captions out of date with Re-render; Rename beside Adjust; Adjust clears the downloaded mark.
- From the Upload page ticket to the markers: the pill reads `Not diarized`; a Side with one Speaker is labelled `Side 1`, with more `Side 1 Speaker 1`, `Side 1 Speaker 2`, in the Transcript, the Speakers panel, and the Timeline lanes.
- From the Word export ticket, as recorded on the Clips ticket, to the Export entries: Captions (.srt) joins Word and plain text; the plain-text export's shape (head, one notice, `[hh:mm:ss] Speaker: text`, `(corrected)`) replaces "Speakers, timestamps, and the Transcript, nothing else"; no VTT in Phase 1.
- From the maintainer, on the v1.3.0 build, to the Timeline: the Speaker lanes withdrawn. The Timeline is the waveform, split into one lane per Side on a Two-channel call, and a Speaker's colour is used for the name and the colour bar. The lanes were one translucent band per Segment on every redraw, and told a corrector nothing the rows beside them did not.
- From the maintainer, on the v1.4.0 build, to the layout: the Bench. From 1280 pixels the video and the Clips, Details, Summary and Chat panels are a third column on the right, always open, with the sheet and the overlays kept for narrower windows; the dock then carries the title, transport and Timeline only. The first page of the Workbench Layout, which every page follows in turn: use the width, put the action beside its consequence, cover nothing, and stack as before below 1280 pixels.

## 9. Clips

A Clip is a user-chosen span of a Recording, marked by a start and an end, with its own title and note, rendered as a playable file for use outside the app, at hearings and the like. The viewer chapter fixes the marking and previewing tool and the Recording's Clips sheet; this chapter fixes the Clip itself, its rendering, its downloads, the Clips page, its limits, and its lifecycle.

### Principles

1. **A Clip is a span of time of the whole Recording**: a start and an end to the millisecond, carrying every Side exactly as the Playback copy does. It is linked to the Transcript by time only; the Segments in a Clip are whichever overlap its span at that moment, never a stored list of Segment ids, so Corrections, merges, renames, and Process again need no bookkeeping.
2. **A Clip can be made as soon as the Recording plays**: the Playback copy and the waveform are enough, and the Transcript joins when it arrives.
3. **Nothing about a Clip goes stale except burned captions**: the transcript excerpt and the caption file are built from the live Transcript at download time and never stored; only a video with captions burned in can fall behind the Transcript, and it is marked, never re-rendered by itself.
4. **A Clip is listed in one place**: the Clips page for the Workspace's Clips (and in Phase 2 the Case's Clips tab for a Case's; see the Clips in Cases chapter).

### Words

| Term | Meaning |
|---|---|
| Clips page | The Workspace's list of every Clip the user has made this Login session. |
| Adjust | Changing a saved Clip's start, end, or either option, which renders its file again. |
| Rename | Changing a Clip's title or note, which renders nothing. |
| Captions out of date | The mark on a Clip with burned captions whose Transcript has changed since it was rendered. |

### The Clip

| Field | Rule |
|---|---|
| Id | The database id; the only thing that appears in a path or an audit row. |
| Recording | A Clip belongs to one Recording and follows it everywhere: Workspace, Case, Discard, Delete. |
| Saved by, saved on | Recorded always; the owner in the Workspace. Shown only in a Case, where Collaborators exist (Phase 2). |
| Title | Required, up to 120 characters, prefilled `Clip 1`, `Clip 2` per Recording. Two Clips may share a title. |
| Note | Optional, up to 1,000 characters, kept inside the app and never printed anywhere. |
| Start, end | Milliseconds from the Recording's start. The shortest Clip is one second; the longest is the "Longest Clip" setting. Clips may overlap. |
| Options | `Burn captions into the video` (off by default; video only) and `Include the transcript excerpt` (on by default). Both can be changed later through Adjust. |
| Render state | Rendering, Ready, Failed (with a reason class). |
| Rendered on, file size | Of the current file. |
| First downloaded on, download count | The downloaded mark (see "Downloads"). |

- A Clip of a Two-channel call carries both Sides, and its excerpt holds both Sides' Segments; there is no single-Side Clip.
- The Provenance's Clip lines (span, options, render time) list the Clips that exist at export time, so a deleted Clip drops out.
- No limit on Clips per Recording; the quota bounds the disk.

### Making a Clip

- **When**: as soon as the Recording's playback readiness is Ready (media steps 6 and 7, the Playback copy and the waveform, which run beside recognition), even while the Job is still Queued or Running. The viewer opens then with the media dock, the Timeline, and New Clip; where the Transcript will go, the page shows the Job's position and Estimated wait, or its Steps while Running. Marking by I and O, typed times, and dragging on the Timeline works; Snap to Segment, `+ Clip`, and both options are greyed with `available once the transcript is ready`. Preview and Save work.
- **When the Transcript arrives**: a Clip saved before it keeps `Include the transcript excerpt` on (the default), so its download gains the excerpt at once; until then there is no excerpt to build and the download is the bare media file. `Burn captions` was unavailable, so the user turns it on through Adjust, which re-renders. Nothing is announced and nothing re-renders by itself.
- **Marking**: the routes and the tool are the Transcript viewer and player chapter's (I and O while playing, typed times, Snap to the current Segment, `+ Clip` on a Segment, drag on the Timeline; Preview; title, note, the two options; Save). Segments inside the range are tinted in the Transcript.

### Rendering

- A Clip is cut from the Playback copy, frame-accurate: mp4 for video, mp3 for audio.
- Rendering runs on the media worker beside Playback copies (CPU, ffmpeg), within that worker's own concurrency, never in the serial Queue. Ten Clips saved at once wait their turn showing `Rendering`, with no positions shown.
- A render fails on an ffmpeg error or after the Clip's length plus five minutes, with the reason class `clip_render_failed`; the Clip stays Failed with Retry and Delete.
- A Clip render is not a Job. It never keeps a Workspace alive; the Busy rule stays "until the last Job ends".
- **Burned captions**: white with a dark outline at the bottom of the picture, one cue per Segment in the span, `Speaker: text` (the text alone when there are no Speakers), timed by Segment on a translated Transcript. Fixed style, no setting. Burned captions never carry a notice.

### Excerpt and captions

- The transcript excerpt (`.txt`) and the caption file (`.srt`) are built from the live Transcript at the moment of download and never stored, as every other export is.
- The excerpt uses the plain-text export's shape (see the Exports chapter): the four-line head with the Recording's title, the kind line, the Speakers, and the one notice (the Translation notice for a translated Transcript, the Transcription notice otherwise), then `[hh:mm:ss] Speaker: text` lines with `(corrected)` after the name. The excerpt keeps the Recording's own times, so a line can be found in the full Transcript.
- The caption file uses the Captions export's cue shape: one cue per Segment inside the Clip's span, `Speaker: text`, or the text alone without Speakers, no notice. Its cue times start at zero, shifted by the Clip's start, so a player shows them on the rendered file. On a translated Transcript the cues are timed by Segment, since a Translation has Segment timing only.
- Speaker names appear on the excerpt and the captions as they stand in the Transcript at download time.
- When the Transcript changes after a Clip with burned captions was rendered (a Correction inside its span, a Speaker renamed or merged, Process again), the Clip shows `Captions out of date` with a Re-render button. Clips without burned captions never go stale.

### Adjust and Rename

- **Adjust** (start, end, either option) re-renders: the Clip returns to Rendering, the old file is replaced when the new one is ready, and the downloaded mark is cleared, because the copy the user holds is now the wrong one. Adjust happens in the viewer; the Clips page's Adjust opens the viewer at the Clip.
- **Rename** (title, note) renders nothing; the download name is built at download time from the current title.

### Downloads

#### One Clip

- With `Include the transcript excerpt` on: one zip named after the Clip, holding the media file, the `.txt`, and the `.srt`. With it off: the bare `.mp4` or `.mp3`.
- File names follow the Media handling chapter's rule (the Recording's title, the Clip's title, the start and end, reduced to safe characters), and the zip carries the same name.

#### Download all

- On the Clips page: one zip named `clips <date> <time>.zip`, flat, holding every Ready Clip's media file with its `.txt` and `.srt` beside it where the excerpt option is on; no zip inside a zip.
- One "Clip downloaded" audit row per Clip in the zip.

#### The downloaded mark

- Set when the owner downloads the Clip, alone or inside any zip (Download all, the sign-out zips); cleared by a re-render; never set by an Admin's audited download.
- The Clips page shows it as `Downloaded <time>` or `Not yet`, and the sign-out count uses it.

#### The sign-out dialog

- The dialog counts undownloaded Clips, in the sentence `2 clips have not been downloaded`, and that sentence carries a `Download clips` link giving the Download all zip.
- `Download everything` includes every Ready Clip with its excerpt beside that Recording's Word and text files (see the Exports chapter and the Workspace lifecycle chapter).
- While "Clips available" is Off, the dialog and Download everything omit Clips.

### The Clips page

- A **Clips** item in the top navigation, beside Recordings and Upload, lists every Clip in the Workspace.
- Columns: Title, Recording, Span, Length, Options (captions burned, excerpt), Status (Rendering, Ready, Failed, Captions out of date), Size, Saved, Downloaded (`Downloaded <time>` or `Not yet`).
- One table in upload order of the Recordings and start-time order of the Clips inside each, with the Recording as a column and a filter by Recording above; a sort control for Title, Saved, Length, and Size. The chosen Clip's details, with its player, sit in a pane beside the table from 1280 pixels or open under its row on a narrower window; Up and Down move along the rows and Enter opens the viewer.
- Per Clip: Play (an inline player of the rendered file, served by Caddy with forward auth like every media file), Download, Open in viewer (opens the Recording at the Clip's start with the Clips sheet open), Rename, Adjust (goes to the viewer), Delete (confirmed).
- At the top: Download all, a total-size line, and the standing Workspace line about removal at sign-out (see the Workspace lifecycle chapter).
- The page is hidden while "Clips available" is Off.

### Limits and room

- **Longest Clip**: one admin setting in Limits, in minutes, default 30, range 1 to the "Longest Recording" value, applied to the next Clip saved. The shortest Clip is one second.
- No limit on Clips per Recording; the quota bounds the disk.
- Clip files count toward the user's quota. The Clips page shows each file's size and the total. Storage is shown to the user only as a warning near the limit; the users list in the Admin panel stays "Recordings with GB", with no split for Clips.

### Lifecycle

- **Discard and Delete**: a Clip and its file go with the Recording. Delete on a single Clip removes only that Clip.
- **Cancel** of a Queued or Running Job: the Recording goes as if never uploaded, Clips included, and the confirmation names them:

```
This removes the recording and its 2 clips, 1 not downloaded
```

- **A render in flight**: if the Discard, a Delete of the Recording, or a Cancel arrives while a Clip is rendering, the render is stopped and its half-made file goes with the folder; no audit row beyond the deletion.
- **Process again**: Clips keep their spans and files; the excerpt follows the new Transcript at download; burned captions show `Captions out of date`.
- A Clip's definition never outlives its Recording. Uploading the same file again is a new Recording with no Clips.

### The AI assistant, Admins, the toggle

- There is no link between a Clip and a Chat or Summary. A Citation already seeks the player; a Clip is a file for outside the app.
- Through "Open their Workspace" an Admin sees the user's Clips page and every Recording's Clips sheet under the audit banner, and may play and download, each download an audit row with the affected user; an Admin does not adjust, rename, or delete another user's Workspace Clip.
- **"Clips available" Off** hides New Clip, the Clips sheet, and the Clips page; Clip files already made stay until their Recording goes; the sign-out dialog and Download everything omit them meanwhile.

### Files on disk

- A Clip on disk is `clips/<clip id>.mp4` or `clips/<clip id>.mp3` under the Recording's folder, and nothing else; the excerpt and the caption file are never written to disk.

```
<Recording's folder>/
  clips/
    <clip id>.mp4        (video Recording)
    <clip id>.mp3        (audio Recording)
```

- The file appears when the render succeeds, is replaced by an Adjust or Re-render, and goes with the Recording's folder at the Discard, at Delete, and at Cancel; a half-made file goes with it.
- Workspace Clips live under `scratch/` and are never backed up.

### Not in this phase

- No `.txt` or `.srt` is stored beside the rendered file; both are built at download time.
- No single-Side Clip of a Two-channel call.
- No VTT is produced anywhere in Phase 1.
- Combining several Clips into one file is out of scope unless added to a later phase.

### Audit rows

Every row carries the Clip id, the span, and the two options, never the title or note. Rename writes no row.

| Row | Written when |
|---|---|
| Clip created | A Clip is saved |
| Clip re-rendered | A render completes after Adjust or Re-render |
| Clip downloaded | A Clip is downloaded, alone or inside any zip (one row per Clip); an Admin's carries the affected user |
| Clip deleted | A Clip is deleted on its own |
| Clip render failed | A render fails; carries the reason class `clip_render_failed` |

A deletion of the Recording, the Discard, or a Cancel writes its own row and no Clip row.

### Settings

By their names in the admin settings catalogue:

- **Longest Clip** (Limits): the longest span a Clip may have.
- **Longest Recording** (Limits): the ceiling of Longest Clip's range.
- **Clips available**: Off hides New Clip, the Clips sheet, and the Clips page.
- The per-user quota (Limits; the Workspace lifecycle chapter names it): Clip files count against it.
- **Translation notice** and **Transcription notice**: the one notice printed on the excerpt.

No environment key belongs to this chapter.

### Left to the build

- The date and time format in the Download all zip's name; the name is `clips <date> <time>.zip`.
- The font and size of burned captions; fixed as white with a dark outline at the bottom of the picture, one cue per Segment, no setting.
- Which row a Retry of a Failed Clip writes: the sources fix "Clip re-rendered" for a render after Adjust or Re-render and "Clip render failed" for a failure, and do not name a successful Retry.
- Whether the Clips page offers Retry (on Failed) and Re-render (on Captions out of date) directly or through Open in viewer; the Clips sheet offers both.
- Whether the sort control sorts within the Recording groups or flattens the list.
- The media worker's concurrency, within which renders queue: the Media handling chapter's.

### Carried for Phase 2

- Saved by and saved on are recorded on every Clip from Phase 1; they are shown only in a Case.
- The Recording is a Clip's only parent, and `clips/` sits under the Recording's folder wherever that folder is; in Phase 2 that is `cases/<case id>/<recording id>/clips/`.
- Principle 4 will read: the Clips page for the Workspace's Clips, the Case's Clips tab for a Case's.
- "Clips available" Off will also hide the Case's Clips tab.
- Downloading a Clip in a Case will count as Last activity.

### Sources

Clips: model, lifecycle, and management; Transcript viewer and synced player.

### Amendments applied

- From the Clips ticket to the media handling rules: the stored `.txt` and `.srt` beside the rendered file are withdrawn; a Clip may be made before the Transcript exists.
- From the Workspace lifecycle ticket, as recorded on the Clips ticket: "the definition is kept and re-rendered when the same file is uploaded again" is withdrawn; a re-upload is a new Recording.
- From the Clips ticket to the queue rules: the queued page opens the viewer as soon as playback is Ready; Cancel's confirmation names the Clips.
- From the Clips ticket to the Word export rules: Download everything includes every Ready Clip with its excerpt; the Clip SRT starts at zero while the excerpt keeps the Recording's times.
- From the Upload page ticket to the Clips page and quota: the Workspace's "Using X of Y GB" line no longer exists; storage is shown only as a warning near the limit; the Clips page keeps its own total-size line.
- From the viewer chapter's Timeline amendment on the v1.3.0 build: the "bare waveform with no Speaker lanes" the viewer opened with before the Transcript is now simply the Timeline; nothing about Clips changes.
- From the maintainer, on the v1.6.0 build, to the Clips page: the Workbench Layout's third page. One table with the Recording as a column and a filter by Recording, in place of a table per Recording; the chosen Clip's details and its inline player in a pane from 1280 pixels, under its row below that.


## 10. AI assistant

The AI assistant is the user-facing name for the app's three language-model features together: Summary, Chat, and Speaker suggestions. Each runs only when a user asks for it from the viewer, works from one Transcript and nothing else, and arrives whole. This chapter fixes what each feature does and shows, what the model is told, how calls are delivered, what happens when the engine is down or a feature is Off, and what is recorded. The engine the app talks to is a Shared engine run outside the app, or the optional Local engine shipped with it; the containers, networks, and GPU placement are in the Architecture and deployment chapter, and every admin setting named here is described in the admin settings catalogue.

### Principles

1. **Nothing runs by itself.** Summary, Chat, and Speaker suggestions happen only when a user asks, from the viewer. A Job is Done the moment the Transcript is stored, and no LLM step follows it. The Queue chapter's rule for skipped automatic steps has nothing left to apply to; its "skipped, not deferred" rule now applies to a click while the engine is down: the call fails at once and the user tries again later by hand.
2. **The Transcript is the whole world.** Every call gets the whole Transcript and nothing else. Chat answers only from it and declines the rest in one sentence. Every claim carries a time the app has checked against a real Segment.
3. **Whole answers, not streaming.** Calls run on a worker, the page polls, and the answer arrives complete.
4. **Instructions are editable, plumbing is not.** Admins edit prompt templates as plain text; the app itself adds the Transcript, what it is, the user's choices, and the answer format.
5. **Nothing is kept beyond the Login session, and nothing is logged but metadata.** Summaries and Chats live only for the Login session (the Workspace lifecycle chapter); there is no kept or read-only Chat and no retention setting for text. Export is the only way to keep a Summary or a Chat, so an Export sits beside every one. The audit row is metadata only (the Audit log and logging chapter).

No LLM ever touches the translation path: no polishing and no post-editing (the Transcription, translation, and diarization choices chapter). Every prompt is told what the Transcript is, a machine transcription or a machine translation to English, so the model can say so when it matters. Summary and Chat are written in English whatever the Transcript's language.

### Words

- **AI assistant**: the three features together; the messages say "The AI assistant is not available right now".
- **Summary template**: an admin-kept instruction text that fixes a Summary's shape. "Standard summary" is built in.
- **Focus**: the user's optional steer for one Summary.
- **Citation**: a time in a Summary or Chat answer that the app has matched to a Segment; shown as a link that seeks the player.
- **Prompt template**: any admin-editable instruction the AI assistant works from, each with a version: Ground rules, Chat, Speaker suggestions, and every Summary template.
- **AI notice**: the admin-set wording shown at the top of every Summary and Chat and printed on their exports.

### The engine

The app talks to one engine at a time through the engine's OpenAI-compatible API, chat completions only, using the `openai` Python library. Which engine is a panel matter: the Engine address and Model name settings.

**The Shared engine.** The app was designed against the office's Shared engine: vLLM 0.27.1 serving `Qwen/Qwen3.8-27B-FP8` under the served name `<shared engine model name>`, with the full 262,144-token window, `--reasoning-parser qwen3`, thinking on by default at the engine, prefix caching off, token-gated, and reachable only on the engine network `<engine network>`, a Docker network outside the app's own Compose project that the app's containers join as an external network (the Architecture and deployment chapter). Structured output on it is `extra_body.structured_outputs.json`, which engages after the thinking block when thinking is on. The Shared engine's scheduler treats every client alike, and the app sends no `priority`. Its token is copied into the file that `LLM_API_TOKEN_FILE` names (see Environment keys). Switching the app from the Local engine to the Shared engine is a panel change (Engine address and Model name) plus the copied token in `secrets/llm_api_token`.

**The Local engine.** The repository ships an optional Compose profile `llm`, the Local engine: vLLM 0.27.1 serving a small model, `Qwen/Qwen3.5-4B` by default (`docs/research/local-engine-model.md`: the largest of its family that fits in 20 GB with its cache for the whole window, with the 262,144-token native context and Apache-2.0), as `local-engine` with a 131,072-token window, `--reasoning-parser qwen3`, `VLLM_USE_DEEP_GEMM=0`, the GPU chosen by UUID with a memory fraction, 0.21 by default, so it can share the WhisperX service's GPU. It is off by default; `./transcribe engine local on` starts it, writing a token when none is stored and pointing Engine address and Model name at it, and `./transcribe engine local off` stops it. An office turns it on when it has no Shared engine that answers, or wants the assistant without leaning on one, and off again when it does not. Any engine that stands in for the Shared engine must offer a window of at least 131,072 tokens.

**Defaults and the first switch-on.** The panel's provider defaults are the Local engine's: Engine address `http://vllm:8000/v1`, Model name `local-engine`. The AI assistant toggle starts Off, and an Admin turns it On once Test connection succeeds against whichever engine is in use. An installation without any engine leaves the AI assistant Off, and everything else in the app works. The AI assistant behaves the same against either engine.

**Sizes.** The app's longest Recording is 6 hours. Rendered as lines with times and Speaker labels, that is about 100,000 tokens at the outside, so the whole Transcript goes into every call, and Phase 1 has no chunking and no map-reduce. Chat history adds at most 16,000 tokens and the largest answer cap is 2,500 tokens, so every call fits the Local engine's window and the Shared engine's with room to spare. The research's map-reduce stays on file for Case-wide work (see Carried for Phase 2).

#### What the calls rely on

These are the facts the LLM handler research file fixed for vLLM. The research was done against Gemma 4; its model-specific rows (that model's context and its `gemma4` parsers) are replaced by the engine facts above, and its vLLM capability rows carry over.

- **Endpoint.** `/v1/chat/completions` on vLLM's OpenAI-compatible server. The app uses no other endpoint: no completions, responses, batch, embeddings, or audio endpoints.
- **Client.** The `openai` Python library (v3.6.0 at research time; Apache-2.0; Python 3.10 or newer) with `base_url` and `api_key`. vLLM-only fields go through `extra_body`: `structured_outputs` and `chat_template_kwargs`. `chat.completions.parse` with a pydantic model is available for the suggestions schema; vLLM accepts the `json_schema` response format it sends.
- **Answer cap.** `max_completion_tokens`, not the deprecated `max_tokens`. When it is omitted vLLM allows `max_model_len - prompt_tokens`, so the app always sends its cap.
- **Sampling.** Explicit on every call. Without it the server applies the model's own `generation_config.json`, whatever that holds.
- **Structured output.** `extra_body={"structured_outputs": {"json": <schema>}}` (`response_format` with `json_schema` does the same); vLLM's backends are xgrammar or guidance, chosen automatically; the older `guided_*` names are deprecated. With a reasoning parser the schema is enforced only after the reasoning section: when thinking is On, the JSON follows the thinking block, and the thinking spends part of the answer budget. Thinking is therefore Off by default, and Off is right for extraction.
- **Thinking per request.** `chat_template_kwargs: {"enable_thinking": ...}` through `extra_body`.
- **Over-long prompts.** The engine fails them with "Input length (N) exceeds model's maximum context length (M)". The app's own estimate refuses first (`llm_too_long`).
- **Concurrency.** vLLM batches all active requests each step (continuous batching), so the app needs no batching of its own. Prefix caching would let repeated calls over one Transcript pay prefill once; the Shared engine has it off, so the app never relies on it.
- **Recall.** Long-context recall is imperfect (the research measured 66.4 percent at 128K on one benchmark), so Citations are validated against real Segments, never trusted.
- **Not used.** Streaming (`stream`) exists and is not used. Tool calling exists and is not used. Embeddings need a second pooling process and are not used: nothing in Phase 1 stores embeddings or retrieves.

### What the user sees

The viewer offers Summary and Chat as panels of the Bench on a wide window and as overlays on a narrow one (the Transcript viewer and player chapter's v1.4.0 amendment), and the Speakers panel offers Suggest names. Nothing appears without a click. The queued page's line reads "Diarization follows"; no LLM step is announced there.

#### Summary

The Summary overlay lists the Transcript's Summaries, newest first, each with its template name, Focus, Length, and time, and the buttons Export to Word, Regenerate, and Delete. A Transcript can hold any number of Summaries.

"New summary" opens a small dialog:

- a template choice, shown only when two or more Summary templates are Enabled, with the Default preselected;
- the Focus box, "What should the summary concentrate on?", optional, 200 characters;
- Length: Short, Standard, or Detailed; default Standard.

"Write summary" queues the call; the overlay shows "Reading the transcript..." and the finished Summary appears whole. Regenerate repeats the same settings and replaces that Summary after "Replace this summary?". Every Summary opens with the AI notice, and its times are Citations. Summary text is always English. Export to Word is the Summary export of the Exports chapter.

#### Chat

The Chat overlay has a thread list (each Chat named from its first question, "New chat", Delete per Chat) and the conversation. The user types a question; the page shows "Reading the transcript..." and polls every two seconds until the whole answer lands. Times in answers are Citations. Each answer has Copy; the Chat has Export to Word (the Chat export of the Exports chapter). Every Chat opens with the AI notice. Chat answers are English whatever the Transcript's language.

Chat answers only from the Transcript: find, list, compare, count, quote, explain what was said, summarise a stretch. Legal advice, opinions on guilt or credibility, and anything outside the Transcript get "I can only answer from this transcript." A Chat covers one Transcript; a Transcript can hold any number of Chats.

#### Citations

Every claim in a Summary or a Chat answer carries a time as [hh:mm:ss], which the Ground rules tell the model to copy from the line it appears on. The app checks each time in an answer against the Transcript's Segments. A time it matches to a real Segment is a Citation: a link that seeks the player to that moment. A time the app cannot match to any Segment is not a Citation and is not linked. Citations print as [hh:mm:ss] on exports.

#### Speaker suggestions

Whenever a Transcript has two or more Speakers without a name, the Speakers panel shows the line "Want name suggestions from what people say?" with a **Suggest names** button. Speakers come from Diarization or from the Sides of a Two-channel call; a Recording with one Speaker has no button. One click runs one call for the whole Transcript, never one call per Speaker.

A suggestion is a person's name said in the Recording ("This is Detective Ruiz", "Thanks, Maria"), or a role when no name is spoken (Interviewer, Interpreter, Officer, Caller, Dispatcher). The Vocabulary supplied for the Recording or Batch is offered to the model as known names, and the model may still propose a name it finds in the text. Suggestions work from the Transcript text alone: Speaker embeddings are neither requested nor stored, and word confidence scores are not sent. They work on translated Transcripts like any other.

Results appear in the Speakers panel with Accept and Reject, and inline as the dashed "Suggested: <name>" pill on the Speaker's first Segment. Every suggestion carries its reason, the Segment it came from: the quote and its time, on hover and in the panel. Nothing changes until accepted. Accept renames every Segment of that Speaker; Reject dismisses the suggestion. Running again replaces every pending suggestion and never touches a Speaker that already has a name.

Confidence: the model rates each suggestion high, medium, or low, or says unknown. Only high or medium is shown; low and unknown are dropped silently. One suggestion per Speaker; the same name is never suggested for two Speakers (the higher confidence wins), and never a name a Speaker already holds. The app-side checks that enforce this are under The prompt inventory.

#### Process again

Process again replaces the Transcript. The marks below apply only when the new Transcript lands, and only within a Login session, since nothing survives it.

- Suggestions are lost with the old Transcript; the user runs Suggest names again.
- A Summary shows "Based on an earlier transcript of this recording (processed 09:14)", the time being when the earlier Transcript was processed.
- A Chat shows "Earlier answers are based on a previous transcript of this recording; new questions use the current one" and continues against the new Transcript. Its Citations still seek correctly because the Recording is the same.

#### Admins and other users' material

An Admin opening another user's Summaries or Chats does so as the Workspace lifecycle chapter fixes: audited, with the owner's powers.

#### When a feature is Off or the engine is down

- AI assistant Off hides Summary, Chat, and Suggest names everywhere. Chat, Summary, or Speaker suggestions Off hides that one feature. Existing Summaries and Chats are hidden, not deleted.
- While the engine is unreachable, the Summary, Chat, and Suggest names buttons are disabled with "The AI assistant is not available right now". Nothing waits: a call already queued fails at once with `llm_unreachable`, and the user runs the feature again later by hand from the viewer. The rest is under Limits and failure behaviour.

### Delivery

- Every call is a Procrastinate task on its own queue `llm`, run by a third worker service `llm-worker` built from the same image as the app, beside `media-worker` and `worker`, with concurrency 4, so LLM calls never delay the three-second status poll on `worker`. Four calls are in flight from the app at once; the rest wait in the `llm` queue in order. The engine batches whatever arrives. No `priority` is sent.
- A Summary, Chat turn, or suggestion run never holds a Job in Running.
- The viewer polls every two seconds while a Summary, Chat turn, or suggestion run is in progress, then returns to the five-second rule of the Queue and Jobs chapter or stops.
- Client: the `openai` Python library against the engine's OpenAI-compatible API, chat completions only.
- Per call: `chat_template_kwargs: {"enable_thinking": false}` unless "Let the model think before answering" is On; explicit sampling (Summary and Chat temperature 0.3, top_p 0.9; suggestions temperature 0); a `max_completion_tokens` cap per feature (see Answer caps under Limits and failure behaviour). These are starting values for the Phase 1 build gate, held in code, not settings.
- Token budget: the app estimates size at four characters per token with a 10 percent margin. If the rendered Transcript plus the templates plus the answer cap would exceed the engine's window (impossible at 6 hours against the Shared engine; possible against a stand-in engine with a smaller window), the feature refuses with `llm_too_long` before calling.
- Chat history: the last turns of the same Chat, up to 16,000 tokens, go back to the model with each question, oldest dropped first. The Transcript is never dropped.

### The prompt inventory

Every request is built the same way. The system message is the Ground rules, then the feature's prompt template, then what the app adds (the answer format). The user message is the Transcript-nature line, the rendered Transcript, then the feature's input: Focus and Length for a Summary; the prior turns and the question for a Chat; the unnamed Speakers and the known names for suggestions.

#### Rendering the Transcript (app, fixed)

One line per Segment:

```
[n] [hh:mm:ss] Speaker: text
```

`n` counts from 1. The time is the Segment's start. The Speaker is the Speaker's current name, or Speaker 1, or Side 1 Speaker 1 for a multi-Side Recording; there is no label when there is no Diarization and one Side. `(corrected)` follows the label on a Segment a user has corrected. Corrections are the text. Word timings and word confidence scores are not sent. Speaker labels reach the prompt only in the app's form (Speaker 1, Side 1 Speaker 1), never in the engine's own form (SPEAKER_00).

#### The Transcript-nature line (app, fixed, from the Provenance)

One of:

```
This is an automatic machine transcription of a {duration} recording in {language}. It may contain recognition errors.
```

followed by one of

```
Speakers were separated automatically and may be mislabelled.
Speakers were not separated.
The two sides of a phone call are labelled Side 1 and Side 2.
```

or, for a translated Transcript,

```
This is an automatic machine translation to English of a {duration} recording in {language}. The original-language text is not available. Translation errors are possible.
```

where, for a mixed Recording, "in {language}" becomes "in which {languages} were detected".

Appended when the Provenance says so:

```
The language was detected with low confidence.
Lines marked (corrected) were corrected by staff.
```

#### Ground rules (prompt template, editable, version 1)

Default wording:

```
You are the AI assistant inside Gideon Transcribe, a transcription tool used by a public defender office. You work only from the transcript you are given. Never invent facts, names, or quotes. Whenever you refer to something said, give the time it was said as [hh:mm:ss], copied from the line it appears on, and never make up a time. When the transcript is unclear or a name is uncertain, say so. Report what was said, not what it proves: no legal advice, no opinions on guilt, credibility, or strategy. Write in plain English.
```

#### Standard summary (Summary template, built in, editable, version 1)

Default wording:

```
Write a summary of this transcript with these parts, in this order, using these headings.
Overview: one short paragraph. What kind of recording this is, who takes part, and what it is about.
Key points: a bulleted list in the order things happen. Each point ends with the time it happens.
Notable statements: short quotes that matter, each with the speaker and the time. Quote exactly; never paraphrase inside quotation marks.
Names, places, and dates: every person, place, organisation, date, and time of day mentioned, each with the time of its first mention.
Unclear parts: stretches where the transcript is garbled, cut off, overlapping, or hard to follow, with their times. Write "None noticed" if there are none.
```

The app adds the Length line, one of:

```
Keep the whole summary under about 250 words.
Keep the whole summary to about 600 words.
Write up to about 1,500 words; be thorough.
```

for Short, Standard, and Detailed, and, when the user gave one, the Focus line:

```
Concentrate on: {focus}. Keep every part, but weight the content toward this.
```

#### Chat (prompt template, editable, version 1)

Default wording:

```
Answer the user's questions using only this transcript. If the answer is not in the transcript, say so in one sentence and do not guess. Quote the transcript when it helps. Give the time for every statement you rely on as [hh:mm:ss]. Keep answers short unless the user asks for detail. If a question asks for legal advice, an opinion on guilt or credibility, or anything outside the transcript, reply: I can only answer from this transcript.
```

The app adds the prior turns of the Chat (within the 16,000-token history budget) and the new question.

#### Speaker suggestions (prompt template, editable, version 1)

Default wording:

```
Some speakers in this transcript have no name yet. For each of them, work out from what is said who they are: a name, if someone says it or is addressed by it, or otherwise a role such as Interviewer, Interpreter, Officer, or Caller. Use the known names below when the talk points to one of them. Give the one line that best shows how you know, and say how sure you are. Never suggest the same name for two speakers. If nothing shows who a speaker is, say unknown.
```

The app adds two lines, for example:

```
Unnamed speakers: Speaker 1, Speaker 3
Known names: Maria Lopez, Detective Ruiz
```

The known names come from the Vocabulary supplied for the Recording or Batch; the line reads "Known names: none" when there are none. The app also adds the answer format as a JSON schema through vLLM's structured output:

```
{"suggestions": [{"speaker": <one of the unnamed Speakers>, "name": <text or "unknown">, "kind": "name" | "role" | "unknown", "confidence": "high" | "medium" | "low", "line": <line number>, "quote": <text>}]}
```

The app keeps a suggestion only when all of these hold:

- the line exists in the rendered Transcript; that line becomes the reason Segment;
- the confidence is high or medium;
- the name is not "unknown";
- the name is not already held by a Speaker;
- the name is not proposed for a second Speaker; when it is, the higher confidence wins and the other is dropped.

Invalid JSON after one retry fails the run with `llm_bad_output`.

#### Templates in the panel

The AI assistant section of the admin panel lists Ground rules, Chat, Speaker suggestions, and the Summary templates. Each prompt template is plain text with Reset to default and a version number that rises by one on every save. A Summary template has a name, a one-line description, the instruction text, Enabled, and Default; exactly one Default exists among the Enabled. The built-in "Standard summary" is editable and resettable but cannot be deleted; Admins add more with Add template. Users choose a template only when two or more are Enabled.

Templates are office configuration in the database: backed up with it (the Backup and restore chapter), never in files. The repository ships only the built-in wordings, in the code as defaults, and they are edited in the panel. No import or export of templates in Phase 1. Prompt templates and Summary templates apply at once, outside the panel's tray, with their versions.

#### The AI notice

The AI notice is a text setting beside the Transcription notice and the Translation notice. Default:

```
AI-generated and unverified. Check against the recording before relying on it. Written by {model} on {date}.
```

The placeholders are filled from the call: `{model}` is the Model display name when that setting is set, otherwise the served name (the Model name setting); `{date}` is the call's date. The notice is shown at the top of every Summary and Chat on screen and printed on their exports together with the Transcript's own notice (the Exports chapter).

### The engine settings

**Provider.** Engine address (the engine's base URL) and Model name (the served name the engine expects), editable in the panel, with a Test connection button that lists the engine's models and then runs one tiny completion. Model display name, an optional text, empty by default: when set, `{model}` in the AI notice prints it instead of the served name, on screen and on exports. The token lives in `.env` as `LLM_API_TOKEN_FILE` and never in the panel or the database; the panel shows it as "set in .env", set or missing, never editable.

**Toggles.** AI assistant (On or Off; starts Off; Off hides Summary, Chat, and Suggest names everywhere). Chat and Summary (each On or Off, On by default) and Speaker suggestions (On or Off, Off by default). "Let the model think before answering" (default Off; On sends `enable_thinking: true` on every call and doubles every time limit: Chat 4 minutes, Summary 10 minutes, suggestions 6 minutes). Sampling, answer caps, and time limits are code, not settings.

**Applying.** Provider settings and the toggles apply through the panel's tray like every other setting (old and new value, an optional note, one audit row each) and take effect on the next call. Prompt templates and Summary templates apply at once with their versions.

**Status page.** An "AI assistant" line: green, "reachable, model <model name>, checked 10:42", or red, "AI assistant: unreachable since 10:31", with Test connection beside it.

### Limits and failure behaviour

| Matter | Rule |
|---|---|
| Reachability | `llm-worker` checks the engine once a minute (list models with the token). While the check fails, the Summary, Chat, and Suggest names buttons are disabled with "The AI assistant is not available right now", the status page shows the red line "AI assistant: unreachable since 10:31", and queued calls fail at once with `llm_unreachable`. Nothing waits. |
| Time limits | Chat 2 minutes, Summary 5 minutes, suggestions 3 minutes, doubled when "Let the model think before answering" is On. On timeout: `llm_timeout`, "The AI assistant took too long. Try again." |
| Retries | One automatic retry on a connection error; none on a timeout; one on invalid suggestion JSON. |
| Answer caps | Chat 1,500 tokens (about 1,000 words); Summary 600, 1,200, or 2,500 tokens for Short, Standard, and Detailed; suggestions 1,000 tokens. A cap hit is shown as it is, with the line "The answer was cut short." |
| Too long | The token budget check fails before calling: `llm_too_long`, "This transcript is too long for the AI assistant." |
| Refused | 401 or 403 from the engine: `llm_refused`, "The AI assistant refused the connection. Ask IT."; the status line turns red. |
| Bad output | Invalid suggestion JSON after one retry: `llm_bad_output`. |
| Anything else | `llm_error`, "The AI assistant hit a problem. Try again." |
| Concurrency | Four calls in flight from the app; the rest wait in the `llm` queue in order. |
| Privacy | Prompts, questions, answers, and Summaries are never logged; the audit row is metadata only. The engine keeps nothing. |

### Environment keys

| Key | Holds | Notes |
|---|---|---|
| `LLM_API_TOKEN_FILE` | the path of the file holding the engine's bearer token, `secrets/llm_api_token` | Never in the panel or the database; the same pattern as the Bind account's password file. The panel shows it as set or missing. Changing it means changing the file on the server and restarting. |

The engine network the app's containers join, the Local engine's Compose profile `llm`, and its GPU (by UUID) and memory fraction are `.env` and Compose facts of the Architecture and deployment chapter. `VLLM_USE_DEEP_GEMM=0` belongs to the Local engine's own service environment, not the app's.

### Settings

This chapter depends on these rows of the admin settings catalogue, by their catalogue names: AI assistant; Chat; Summary; Speaker suggestions; Let the model think before answering; Engine address (with Test connection); Model name; Model display name; Token (read-only, from `LLM_API_TOKEN_FILE`); the prompt templates Ground rules, Chat, and Speaker suggestions; Summary templates; AI notice. The Transcription notice and Translation notice reach this chapter only through the exports of a Summary or Chat (the Exports chapter). The status page's AI assistant line and the fixed rules listed on the settings pages (sampling, answer caps, time limits) are not settings.

### Audit rows

| Row | When it is written | What it carries |
|---|---|---|
| AI assistant call, feature `chat_turn` | once per Chat question, whether it succeeded, failed, or was refused | model name; endpoint host; the Ground rules version and the feature template's name and version (for example "ground-rules v3; Chat v1"); input and output token counts from the engine's usage figures; duration; outcome (ok or the reason class). Never the question, the prompt, or the answer. |
| AI assistant call, feature `summary` | once per Summary written or regenerated, whether it succeeded, failed, or was refused | as above (for example "ground-rules v3; Standard summary v2") |
| AI assistant call, feature `speaker_suggestions` | once per Suggest names run | as above |
| AI assistant call, feature `moment` (Phase 4) | once per Moment described, whether it succeeded, failed, or was refused | as above ("ground-rules v3; Moment v1"), and whether the Moment was asked for or accepted from a Cue; never the description, the phrase, or the clip |
| Viewer-edit rows of the Audit log and logging chapter | Accept or Reject of a suggestion; Delete of a Summary or Chat | as that chapter fixes; never a name or any text |
| Export rows of the Exports chapter | Export to Word of a Summary or Chat | as that chapter fixes |
| Setting changed rows of the admin settings catalogue | each provider setting or toggle applied through the tray | old and new value, the optional note |

No full-text prompt logging exists anywhere in the app; the Chat and Summary themselves are the record, and they live only for the Login session.

Reason classes added to the catalogue (the Audit log and logging chapter):

| Reason class | When |
|---|---|
| `llm_unreachable` | the engine is failing the minute check, or the connection failed and its one retry failed |
| `llm_timeout` | the call ran past its time limit |
| `llm_refused` | 401 or 403 from the engine |
| `llm_too_long` | the app's token estimate exceeds the engine's window |
| `llm_bad_output` | invalid suggestion JSON after one retry |
| `llm_error` | anything else |
| `llm_no_vision` | a Moment asked of an engine that takes text only (Phase 4) |

### Not in this phase

- No LLM step runs after a transcription; nothing is automatic.
- No streaming answers.
- No chunking, windowing, or map-reduce; the whole Transcript goes in every call.
- No "Summarise all" (a bulk Summary per Done Recording of a Batch).
- No Chat across a Case (Phase 2: see Carried for Phase 2).
- No saved or preset Chat questions.
- No import or export of prompt templates.
- No Speaker embeddings, no retrieval, no embeddings service.
- No AI controls on the Upload page.
- No LLM on the translation path.
- No tool calling.

### Left to the build

- Sampling (Summary and Chat temperature 0.3, top_p 0.9; suggestions temperature 0), the answer caps, and the time limits are "starting values for the Phase 1 build gate, held in code, not settings"; the gate may adjust them, and they never become settings. **Overturned in part by the maintainer, v1.37.0:** the answer caps, the time limits, the thinking allowance, the chat history budget, and the engine window are settings on the AI assistant page, each with its code value as the default and Reset to default beside it, so an office tunes them to its engine and puts them back; sampling stays in code. The amendment at the chapter's foot records it.
- How a time in an answer is matched to a Segment. The prompts ask the model to copy the start time of the line it cites, so an exact match to a Segment's start is the expected case; the tickets fix only that a Citation is a time the app has matched to a real Segment, that an unmatched time is not a Citation, and that a suggestion whose line does not exist is dropped.
- How the app learns the engine's window for the too-long check; the tickets fix the estimate (four characters per token, a 10 percent margin) and the refusal, not the source of the window size.
- The exact answer-format text the app adds for Summary and Chat (prose with times as [hh:mm:ss]); the tickets fix a JSON schema only for suggestions.
- The message shown for `llm_bad_output`; the tickets fix the reason class and the one retry, not a wording.
- Which call's date fills `{date}` in the AI notice at the top of a Chat with several turns.
- The wording of the Test connection's "one tiny completion", and the Delete confirmations for a Summary and a Chat ("Replace this summary?" is fixed for Regenerate).
- How a Chat's name is taken "from its first question" (length, truncation).

### Carried for Phase 2

- **Case Chat.** Phase 2 adds a Chat grounded in every Transcript in a Case, read whole in Readings of up to 100,000 rendered tokens (about six hours of talk, this chapter's ceiling), with several Readings and one combining call when the Case does not fit one, two Readings at a time within the four in flight; a question is one task on `llm-worker` with a 15-minute limit, and each call keeps the two-minute Chat rule. Phase 1 carries the shape for it: the prompt inventory gains a **Case chat** template (editable, version 1) and a fixed combining instruction; a People line and one header line per Transcript are plumbing like the Transcript-nature line; the reason class `llm_case_too_large` joins the six above; the "Chat across cases" setting joins the AI assistant section. Keep a Case's Transcripts retrievable together so several can be rendered into one prompt. Nothing in Phase 1 stores anything for it, and the research's map-reduce stays on file for it.
- **Speaker suggestions inside a Case.** The "Known names:" line becomes the Case's People first, each as "Name (Role)" when a Role is set, then the Batch's Vocabulary, then the Office Vocabulary, duplicates removed, "none" when empty; the template wording (version 1) is unchanged. A suggestion matching a Person shows its Role, and Accept joins that Person; a new name creates one; a role word accepted ("Officer") becomes a Person of that name with no Role set by itself. A name held by a Speaker elsewhere in the Case is allowed; the one-Transcript rules stand. There is no Case-level Suggest names. The suggestion's `kind` field already separates a name from a role for the Role field.
- **Speaker embeddings** stay unrequested and unstored in Phase 2 as well.
- **Summaries and Chats of a Recording** are kept beyond the Login session only inside a Case (the Cases chapter); the "based on an earlier transcript" marks are the same there.

### Sources

Phase 1 LLM features: Chat, Summary, Speaker suggestions; LLM handler capabilities and long-transcript strategy (and the LLM handler research file behind it); Word export contents and layout (for what the Summary and Chat exports carry); Admin settings catalogue and panel (for the catalogue names of the settings and the "hidden, not deleted" effect of the toggles only).

### Amendments applied

- From the Workspace lifecycle ticket to the LLM features question's "Chats survive the session": Summaries and Chats live only for the Login session (Principle 5).
- From the deployment-topology ticket to "The engine" and "The engine settings": the Local engine as Compose profile `llm`, the provider defaults `http://vllm:8000/v1` and `local-engine`, the AI assistant toggle starting Off until Test connection succeeds, the switch to the Shared engine as a panel change plus the copied token.
- From the settings catalogue ticket to "The AI notice" and "The engine settings": the Model display name; provider settings and toggles applied through the tray, templates applied at once.
- From the Speaker management panel ticket to "Speaker suggestions": the known-names line inside a Case, Accept joining a Person, no Case-level Suggest names, no embeddings in Phase 2 (all under Carried for Phase 2).
- From the Case Chat ticket to "Chat": the Case Chat, the Case chat template, and `llm_case_too_large` (under Carried for Phase 2); the line "Chat across a Case is Phase 2 fog" superseded.
- From the LLM features ticket to the viewer and queue tickets, carried here as rules: "Diarization follows" on the queued page; no LLM step after a Job; `llm-worker` on queue `llm` beside `media-worker` and `worker`.
- From the build (v1.9.0), the second half of this chapter: Summary, Chat and Speaker suggestions built as fixed, with these decisions on what was left to the build. A time in an answer is a Citation when some Segment starts within the same whole second. The engine's window for the too-long check is the floor any stand-in engine must offer, 131,072 tokens, held in code. The answer format the app adds is one sentence for Summary (each part's heading on its own line followed by a colon, times as [hh:mm:ss]) and one for Chat. `llm_bad_output` reads "The AI assistant gave an answer the app could not read. Try again." The date in a Chat's AI notice is its first answer's. Test connection asks "Reply with the single word: ready". Delete asks "Delete this summary? Export it first if you want to keep it." and the same for a Chat. A Chat's name is its first question's first sixty characters, cut on a word. Templates are edited on the Panel's Templates page, in the Settings group of the rail.
- From the maintainer, on the v1.10.0 build, to The Local engine: the model is the small Qwen3.5-4B in place of the Shared engine's 27B, chosen against the maintainer's rule that the engine with its cache uses no more than 20 GB of the card it shares with the WhisperX service (`docs/research/local-engine-model.md`); the memory fraction 0.21; the `./transcribe engine local on|off` switch. The 131,072-token window stands, met natively.
- From the maintainer, on the v1.10.6 build, to the toggles: Speaker suggestions starts Off. The first trials against a small Local engine named labels and repeated itself, and the literature (`docs/research/speaker-suggestions.md`) supports roles with fine-tuned models on labelled data and says naming from text is unstudied; an office turns the feature on once it has seen it do well on its own recordings. What would make it better is written down there: evidence first, a larger engine, a measured trial, roles from a fixed list per recording type.
- From the maintainer, on the v1.22.0 build, to "Summary" and "The templates": **Summary templates by Recording type.** A Summary template may be for one or more Recording types (ticks on the Templates page over the Recording types setting's list; none means any; a type removed from the setting stays on the template, greyed "no longer listed"). The `New summary` dialog preselects the Enabled template for the Recording's type in place of the office Default, lists the type's templates first, hides nothing, and says in one line why ("This is a jail call, so the Jail call summary is chosen."); when two templates claim one type the Default wins, else the first by name. The app ships one template per shipped Recording type (Jail call, Body camera, Interview, Phone call, Hearing) beside the Standard summary, each built in: Enabled from the first day, editable and resettable to its own wording, never deleted, and made once the first time templates are wanted so an office that upgrades gets them too; the office reviews their wording on the Templates page. The "two or more Enabled" rule for the dropdown stands and so, with the shipped six, the dropdown shows from the first day. Add template takes the ticks, and a template appears in the viewer for its types from the moment it is added. Recording types exist only inside Cases, so a Workspace Recording keeps the office Default. The `key` column names the shipped templates; the "Summary template added" and "saved" rows carry the types.
- From the maintainer, on the v1.13.0 build, to "Chat" and to the Case Chat chapter of Phase 2: the Chat is one component drawn the same in the viewer's Chat panel and on the Case page's Chat tab (`chat-ui.js`), with these forms, chosen so that a person who is not technical can use it without being told how. An empty Chat opens with the office's starter questions as chips, when an Admin has listed some on the Templates page (Chat starter questions; Case chat starter questions; empty by default since v1.13.1, the maintainer having found built-in ones unwelcome), one click asks one, under a line saying what the assistant reads ("Answers come from this transcript only"; "Answers come from the 5 transcripts in this case"). The conversation is the person's questions on the right and the answers as cards on the left, each with its time, the answer's simple lists, bold and short colon-ended headings rendered, Copy under every answer. A Citation is a play pill (▶ 12:45; on a Case, ▶ Jail call 2, 12:45) whose hover shows the transcript line it points to, and which plays from there and lights that line in the transcript for a moment. A question in flight shows a pulse, the reading line, an honest expectation ("usually 5 to 20 seconds"; on a Case in parts, "Part 2 of 4 read", counted as parts return) and the seconds elapsed. A failed question offers Try again; a cut-short answer says "Ask for the rest, or ask a narrower question". Earlier Chats are a list under "Chats (n)", each with its name, when it started and how many questions; New chat stands apart. The conversation follows new answers only while the reader is at the bottom. The viewer's Chat inside a Case carries the link "Ask about the whole case instead" to the Case's Chat tab. The AI notice is one quiet line with an information mark. On a laptop the sheet gains Expand, which gives the panel the height the window allows and back. The viewer's own state answer carries when a Chat started and when each turn was asked and answered; the Case Chat's carries the cited line and the parts read so far (migration 0021), counted on the task's own thread as each Reading returns.
- From the maintainer, on the v1.37.0 build, to the sizes table and "Starting values": **the budgets become settings.** The answer caps (Chat 1,500; Summary 600, 1,200, 2,500; suggestions 1,500, the build's figure rather than the table's 1,000), the time limits (Chat 120 s, Summary 300 s, suggestions 180 s, doubled while the model may think), the thinking allowance (8,000 tokens, greyed while thinking is Off), the chat history budget (16,000 tokens), and the engine window (131,072 tokens) are rows on the AI assistant page, each with its code value as the default shown beside it and Reset to default, so an office tunes them to its engine (the maintainer's shared 27B engine spent the whole allowance thinking) and puts them back. Sampling stays in code. The chapter's "never become settings" line is overturned to that extent; the four-characters-a-token estimate is unchanged.

## 11. Exports

An Export is a file a user takes out of the app from a Transcript, a Summary, or a Chat: a Word document, a plain-text file, or Captions. Exports and Clip downloads are the only ways anything leaves a Workspace (the Workspace lifecycle chapter). The viewer offers Export as a group in its sidebar (Word, text, Captions); every Summary and every Chat has Export to Word; the Batch page has the Batch download; the sign-out dialog has "Download all transcripts" and "Download everything". Layouts, file names, and formats are code, not settings. Sample exports built during planning exist in the planning repository at `prototypes/word-export/` (the `A-record/` folder is the reference); this chapter wins where they differ.

### The Word Transcript

Layout "Record": a separate cover page, the talk on line-numbered pages, and the Processing record as the last pages. Built for printing and for citing by page and line.

1. **Cover page.** The title: the Recording title, falling back to the original file name without its extension. The kind line: "Transcript" (an English Transcript), "Translated to English from <language>" (for example "Translated to English from Spanish"), "Translated to English (<languages> detected)" for a mixed Recording (for example "Translated to English (Spanish and English detected)"), or "Transcript in <language>" for a Transcript that was not translated and is not English (for example "Transcript in Spanish"). The facts: Recording file and length, uploaded when and by whom, Speakers, Language, Processed when and with which Whisper model, SHA-256 of the recording. The one notice (Transcription notice or Translation notice, the admin text with its placeholders filled from the Provenance) followed by the legend "Segments marked * were corrected by staff." whenever any Segment was corrected. Whenever Speakers exist, the Appearances table: name, label from processing, Side, segments, speaking time, first heard; the Phase 1 build carries a Role column in it, hidden while empty. The cover date is the upload date, because the app cannot know when a recording was made; there is no typed "Recorded on" date, in a Case or anywhere.
2. **The talk.** Line-numbered pages in a fixed-width face, Speaker names in capitals, every Segment starting with its time as [hh:mm:ss] (hours always shown, matching Citations) and an asterisk after the time of a corrected Segment. Segment timing only: no per-word feature exists in any export, so a translated Transcript looks like any other apart from its kind line and notice. A Transcript without Speakers (no Diarization, one Side) prints the lines without names, and its cover has no Appearances table.
3. **The Processing record**, as the last pages: the Provenance record in full (original name, size, SHA-256, uploader, technical facts, Sides, Preprocessing profile with "loudness normalised (linear, -16 LUFS)", models, settings, service version, dates), then the Segment count, the Correction count, and who exported it when. The raw ffprobe output stays in the Details panel and is not printed.
4. **Header and footer.** Header: the title and the kind. Footer: the first twelve characters of the SHA-256, "Page X of Y", and "Gideon Transcribe, exported <date>". The exporter's name appears in the Processing record only, not on every page.
5. **Page.** US Letter, one-inch margins, built with python-docx (MIT, free).

### Corrections

An asterisk after the time of every corrected Segment plus the legend on the cover, and nothing on the words themselves. The app therefore keeps no original text per corrected Segment for export; the audit log records that a Correction happened, never the text.

### The combined document

Export to Word in the viewer shows two checkboxes when there is anything to include, "Include summaries (n)" and "Include chats (n)", unticked by default. Order: the cover page, the Summaries (each with its header block and the AI notice), the Transcript, the Chats, the Processing record. The file name gains " with summaries and chats" (or " with summaries", or " with chats"). With neither box ticked the document is the Word Transcript above.

### Summary and Chat exports (Word)

Each Summary and each Chat exports on its own, in layout Record's typography:

- the cover facts, with no Appearances table and no Processing record (the full record lives on the Transcript export);
- the header block: for a Summary, the template name and version, Focus, Length, written by which model and when; for a Chat, started when, how many questions, model;
- the AI notice above the Transcript's Transcription notice or Translation notice (the same notice as the Transcript it came from);
- the body: for a Summary, the Summary template's parts as Word headings (Heading 2) with Citations printed as [hh:mm:ss] in grey; for a Chat, "Question n." and the answer, in order, declines included ("I can only answer from this transcript.").

Summaries and Chat answers are English whatever the Transcript's language. `{model}` in the AI notice prints the Model display name when that setting is set, otherwise the served name (the AI assistant chapter).

### Plain text

A four-line head, a blank line, then one line per Segment:

```
<title>
<kind line>. <file>, <length>, uploaded <date> by <user>. Processed <date> with Whisper <model>.
Speakers: <name> (<label>); <name> (<label>)
<the one notice> <legend "Lines marked (corrected) were corrected by staff." when any>

[hh:mm:ss] Speaker: text
[hh:mm:ss] Speaker (corrected): text
```

The Speakers line is omitted when there are no Speakers, and the lines then read `[hh:mm:ss] text`. No SHA-256 line and no "exported by" line: the Word file carries the full record. UTF-8 with Windows line endings. This is the same line shape the AI assistant reads (its rendering adds only the `[n]` line number in front) and the shape a Clip's transcript excerpt uses (the Clips chapter).

### Captions

Export offers "Captions (SRT)": one cue per Segment with the Segment's start and end, its text as `Speaker: text` (the text alone when there are no Speakers), and no notice, because SRT has no place for one that would not show on screen. There is no VTT: the viewer already shows the text in the browser, and SRT is what VLC and the Windows players read. A Clip's Captions use the same cue shape (the Clips chapter).

### Batch download and Download everything

- **Batch page**: one button, "Download N transcripts (M not ready)" (for example "Download 22 transcripts (3 not ready)"): a zip of one plain-text file per Done Recording, each as under Plain text with its notice at the head; Recordings not yet Done are left out. There is no bulk Word button.
- **Sign-out dialog** (the Workspace lifecycle chapter): "Download all transcripts", the same zip across every Done Recording in the Workspace rather than one Batch; and "Download everything", a zip holding, for every Done Recording, its combined Word document (the Transcript with its Summaries and Chats inside; the Word Transcript alone when it has neither) plus its plain-text file, and every Ready Clip as the Clips chapter fixes: the Clip's media file with the `.txt` and `.srt` beside it where "Include the transcript excerpt" is on, placed beside that Recording's combined Word and text files. A Clip's SRT cue times start at zero, shifted by the Clip's start, while its plain-text excerpt keeps the Recording's times; both are built from the live Transcript at download time and never stored. "Download everything" is not on the Batch page.
- **Zip names**: `Transcripts <yyyy-mm-dd> <hhmm>.zip` for the Batch download and for "Download all transcripts"; `Everything <yyyy-mm-dd> <hhmm>.zip` for "Download everything".

### File names

```
<title> - transcript.docx
<title> - transcript with summaries and chats.docx
<title> - transcript with summaries.docx
<title> - transcript with chats.docx
<title> - transcript.txt
<title> - summary (<template>) <yyyy-mm-dd hhmm>.docx
<title> - chat <yyyy-mm-dd hhmm>.docx
<title> - captions.srt
Transcripts <yyyy-mm-dd> <hhmm>.zip
Everything <yyyy-mm-dd> <hhmm>.zip
```

`<title>` is the Recording title, falling back to the original file name without its extension, made safe: letters, digits, spaces, and `- _ . , ( ) '` survive; everything else becomes a hyphen (a colon in a title, for example); capped at 80 characters; the Windows reserved names (CON, PRN, AUX, NUL, COM1 to COM9, LPT1 to LPT9) get a suffix. Duplicate names inside a zip get " (2)", " (3)", and so on. Clip file names are the Clips chapter's.

### Notices on exports

Every export except Captions carries exactly one notice: the Translation notice on a translated Transcript, the Transcription notice on every other one, an admin text with `{language}` and `{model}` filled from the Provenance. Which notice applies, the wording, and how a mixed Recording reads are the Transcription, translation, and diarization choices chapter's rules. This chapter fixes where the notice sits: on the cover page of the Word Transcript below the facts, followed by the corrections legend when any Segment was corrected; on the fourth line of the plain-text head; and on a Summary or Chat export below the AI notice. The AI notice itself (default "AI-generated and unverified. Check against the recording before relying on it. Written by {model} on {date}.") is the AI assistant chapter's and prints only on Summary and Chat exports and inside the combined document.

### Environment keys

None. No export depends on a `.env` key.

### Settings

No new settings. This chapter depends on these rows of the admin settings catalogue, by their catalogue names: Transcription notice; Translation notice; AI notice; Model display name. They are the only admin-editable text on any export; layouts, file names, and formats are fixed in code and listed among the fixed rules on the settings pages.

### Audit rows

| Row | When it is written |
|---|---|
| "export made", kind transcript Word | each Word Transcript exported from the viewer |
| "export made", kind combined | each combined document (Transcript with Summaries or Chats inside), from the viewer or inside "Download everything" |
| "export made", kind transcript text | each plain-text file, from the viewer or inside a zip; the Batch download and "Download all transcripts" write one "export made, plain text" row per Recording included |
| "export made", kind captions | each SRT exported |
| "export made", kind summary | each Summary export |
| "export made", kind chat | each Chat export |

A zip writes one row per file inside it. Rows carry the Recording's snapshot label and never any text. The Clip files inside "Download everything" are recorded as the Clips chapter fixes.

### Not in this phase

- No VTT file.
- No bulk Word button on the Batch page.
- No "Recorded on" date, typed or otherwise; the cover prints the upload date.
- No marking of corrected words themselves (underline or colour); the asterisk and legend are the only marks.
- No exporter's name in the header or footer.
- No Processing record on a Summary or Chat export; cover facts only.
- No per-word feature in any export.
- No Case line on the cover and no Case Chat export (Phase 2: see Carried for Phase 2).
- No admin setting for layouts, file names, or formats.

### Left to the build

- The fixed-width face, type sizes, and the cover's typography. The samples under `prototypes/word-export/A-record/` show one choice; the build follows this chapter where the samples differ from it (Summaries before the Transcript in the combined document, the four-line plain-text head, cover facts only on Summary and Chat exports, no VTT).
- Whether line numbers restart on every page or run through the document; the layout is "built for printing and citing by page and line".
- The suffix given to a Windows reserved name; the tickets fix only that it gets one.
- The date and time formats printed on the cover, in the footer's "exported <date>", and in the Processing record; the file and zip names fix `<yyyy-mm-dd hhmm>` and `<yyyy-mm-dd> <hhmm>`.
- The folder shape inside "Download everything" (flat, or one folder per Recording); a Recording's Clip files sit beside its combined Word and text files, and duplicate names get " (2)".
- The Word styles beyond Heading 2 for a Summary's parts, and the styling of the header block and the AI notice.
- How "speaking time" and "first heard" in the Appearances table are computed from the Segments.

### Carried for Phase 2

- **Case name on the cover.** The export of a Recording in a Case adds the Case name to the cover facts and is otherwise the same document.
- **Role column.** The Appearances table's Role column, hidden while empty in Phase 1, is filled from the Person when the Recording is in a Case and the Person holds a Role, and left blank otherwise. Nothing else changes: the "Speakers" fact line, plain text, SRT, Clip excerpts, and the Summary and Chat exports read as fixed here.
- **Case Chat export.** The Chat export with the Case's facts: the cover carries the Case name, the owner, and the Recordings the Chat has read across its questions (title, Recording type, upload date, length); the header block reads started when, by whom, how many questions, model; the AI notice sits above the Transcription notice and, when any Recording read was translated, the Translation notice too (the one exception to one notice per export); the body is "Question n." and each answer in order, with Citations printed as the Recording's title and [hh:mm:ss] in grey. File name `<case name> - case chat <yyyy-mm-dd hhmm>.docx`. "Download everything" is unchanged, and a Case has no zip.

### Sources

Word export contents and layout (and the prototype notes at `prototypes/word-export/README.md`, which defer to that ticket where they differ); Phase 1 LLM features: Chat, Summary, Speaker suggestions (the AI notice and what a Summary and a Chat export carry); Admin settings catalogue and panel (for the catalogue names of the notices and the Model display name only).

### Amendments applied

- From the settings catalogue ticket to "Summary and Chat exports": the Model display name fills `{model}` in the AI notice on every Summary and Chat export.
- From the Case folder ticket to "The Word Transcript", cover page: no typed "Recorded on" date anywhere; the Case name added to the cover facts (Carried for Phase 2).
- From the Speaker management panel ticket to the Appearances table: the Role column, carried hidden while empty in Phase 1 (Carried for Phase 2).
- From the Clips ticket to "Batch download and Download everything": every Ready Clip in "Download everything", the cue-time shift, both files built live at download time.
- From the Case Chat ticket to "Summary and Chat exports": the Case Chat export and its file name (Carried for Phase 2).
- From the Word export ticket to the queue and Workspace lifecycle tickets, carried here as rules: no bulk Word button on the Batch page; "Download everything" on the sign-out dialog only; the zip and file names.


## 12. Workspace lifecycle

The Workspace is the Phase 1 mode of the app, where Folder management is off. It is a user's holding area. It belongs to the user, not to a browser tab, and it exists for every user at all times; what changes is whether it holds anything. Nothing in a Workspace outlives the user's Login session. What a user wants to keep, they export or download before signing out. Keeping anything for longer is what Cases are for in Phase 2; persistence, when it comes, is additive work owned by the Cases chapters and changes nothing written here.

### Principles

1. **The Workspace is not persistent.** When the user's Login session ends, everything in the Workspace goes: Recordings, Transcripts with their Corrections and Speaker names, Summaries, Chats, Clips and their definitions, Provenance, Batches. Not "the Recording goes and the text stays": nothing stays.
2. **A file uploaded again is a new Recording**, processed from scratch. The app never matches a new upload to anything that went before.
3. **Nothing is discarded early to make room.** When the disk is low, uploads are refused and IT is told.
4. **Everything runs from database state**, so a restart of the app loses nothing and changes no rule.

### Words

- **Workspace**: the user's holding area while Folder management is off. Nothing in it outlives the Login session.
- **Discard**: the removal of everything in a user's Workspace once their Login session has ended and no Job of theirs is running.
- No page says "Workspace" to users. The pages say "your recordings".

### What is where, and what survives

| Item | During the Login session | After the Discard |
|---|---|---|
| Recording: uploaded bytes, probe output, ASR audio, Playback copy, waveform | one folder on disk, `scratch/<user id>/<recording id>/` | gone |
| Transcript: Segments, word timings, Corrections, Speaker names, Speaker suggestions | Postgres | gone |
| Summaries and Chats | Postgres | gone |
| Clips: definitions in Postgres, rendered files under `clips/` | both | gone |
| Provenance | Postgres | gone; the audit rows keep their Snapshot label (the original file name and the start of the hash) |
| Batches and Jobs | Postgres | gone; the audit log's Job rows (completed with duration, failed with reason class, cancelled) are the record |
| Unfinished upload pieces | `uploads/` | gone (dropped after ten minutes of silence in any case) |
| The user's account, quota override, admin flag, Block | Postgres | kept; these are not Workspace content |
| Audit rows about all of the above | Postgres, metadata only | kept under Audit retention |
| The WhisperX service's copy of a result | deleted by the app at merge (see the Queue and Jobs chapter) | nothing to remove |

- Text lives in Postgres and bytes live on disk, both only for the working Login session.
- Exports (Word, plain text, the Batch download, Download everything) are rendered on demand and never stored.
- The per-user quota (default 50 GB, with a per-user override on the users list; see the Media handling chapter) is the Workspace's size cap. Everything on disk for the user's Recordings counts toward it; text does not.
- The uploaded original is never downloadable. Keeping the media means downloading Clips; keeping the text means exporting.

The disk layout under the App data folder, fixed by the Media handling chapter and relied on here:

```
<App data folder>/
  uploads/                    unfinished upload pieces
  scratch/
    <user id>/
      <recording id>/         uploaded bytes, probe output, ASR audio per Side,
                              Playback copy, waveform
        clips/                rendered Clip files
```

A Recording's folder goes as a whole. A user's Recordings are the only things under `scratch/<user id>/`.

### Conditions of a Workspace

A Workspace's condition is derived from database state, never stored.

| Condition | Meaning |
|---|---|
| Open | The user has a Login session. |
| Busy | Any upload has finished and the user's last Job has not ended. Independent of Open. |
| Ending | The Login session ended while the Workspace was Busy. It lives until the last Job ends, then for a grace period equal to the idle timeout (default 8 hours). A sign-in during that time reopens it untouched. |
| Empty | Nothing in it, after a Discard or before the first upload. |

The Busy rule and the grace period:

- The Workspace is Busy from the moment any upload finishes until the user's last Job ends. A Job has ended when it is Done, Failed, or Cancelled.
- A Clip render never keeps a Workspace alive. The Busy rule stays "until the last Job ends".
- The grace period equals the idle timeout. There is no separate setting for it.

### How a Login session ends

- A Login session ends by logout, by idle timeout (default 8 hours, with a warning 15 minutes before), by deactivation by the Directory check, by a Block, or by an Admin's End sessions. The idle timeout is the only session limit; there is no absolute cap.
- A user has one Login session at a time and a new sign-in wins. The older session ends with a "signed in elsewhere" message on its next request. The new session is Open, so nothing is discarded, and a running Batch is unaffected. Multi-device use therefore needs no rule of its own: the Workspace belongs to the user and continues under the new session.
- The idle clock is the last-request time stored on the Login session.
- An Admin opening the Workspace (ADR 0004) is not the user's activity. It neither reopens nor extends the Workspace.
- Whatever ends the Login session, the Workspace rules then apply exactly as for a logout: the conditions above decide when the Discard runs.

### When the Discard runs

- **The Discard runs within one minute** of the moment a Workspace is neither Open, nor Busy, nor inside its grace period. There is no undo window.
- A completed Job's outputs (the merged Transcript in Postgres, the Playback copy and waveform on disk) survive a restart of the app or of the WhisperX service within the same Workspace. A restart neither extends nor shortens a Workspace, because the idle clock lives on the Login session.
- The viewer needs no "media gone" state: a Recording's media and its Transcript are present together or gone together.
- A leaver's Workspace is discarded when deactivation ends their Login session, under the same conditions (a Busy Workspace lives until its last Job ends plus the grace period).

### Re-upload and Process again

- **Re-upload**: the same file uploaded again, in the same Login session or a later one, is a new Recording with a new Job, processed from scratch. Nothing is re-rendered or matched from an earlier upload. Uploading a file that matches a live Recording of the same user is still refused as "duplicate file" (see the Media handling chapter).
- **Process again** within a Login session is a one-Recording Batch, under the one-unfinished-Batch rule of the Queue and Jobs chapter. While it runs the old Transcript is locked, and cancelling it unlocks the old Transcript. When it completes, the new Transcript replaces the old one: the old Transcript with its Corrections, Speaker names, and suggestions goes; Summaries and Chats stay and are marked as based on an earlier Transcript; Clip definitions and rendered files stay and their transcript excerpts are refreshed; the Provenance keeps both processings. None of it outlives the Login session, so the "based on an earlier Transcript" mark exists only within a session.

### States a Recording passes through in the Workspace

As far as these chapters fix them. The Queue chapter and the Media handling chapter own the Job and upload rules the table leans on.

| State | What holds it | How it leaves |
|---|---|---|
| Uploading | Pieces in `uploads/`. The Workspace is not Busy on its account until the upload finishes. | The upload finishes: the Recording's folder exists and the Workspace is Busy. Refused by the tus pre-create hook (`disk_full`, "duplicate file", or a Media handling reason class): nothing is kept and the Recording is Rejected. No data for ten minutes: the upload is dropped and the Recording removed. |
| Queued, then Running | The folder on disk (uploaded bytes, probe output, ASR audio per Side); a Job in the Queue with a Step. The Workspace is Busy. | Done, Failed, or Cancelled. |
| Done | The Transcript in Postgres; the Playback copy and waveform on disk. Survives a restart. | Delete by the owner or an Admin; Process again (a new Job, the old Transcript locked meanwhile); the Discard. |
| Failed | The files kept, Retry offered, the reason class in the audit log (`media_failed` when the media step failed because the disk filled). | Retry (the Job runs again; media work that already succeeded is not repeated); Delete; the Discard. |
| Cancelled | Cancelling a Job or a Batch removes the Recording, its files, and its row, as if never uploaded. Done Recordings in a cancelled Batch stay. Delete on a Recording with an unfinished Job is this Cancel. | Gone at once, with a "Recording deleted (cause: cancel)" row. |
| Rejected | Refused at upload; nothing on disk. Counts as ended for the Batch. | Nothing to remove. |
| Discarding | Marked by the Discard. The folder is deleted, then the rows. A crash mid-way leaves the mark and the next minute finishes it; the 03:30 sweeper finishes any Recording marked Discarding for more than an hour. | Gone, with a "Recording deleted (cause: discard)" row. |
| Deleted | Removed by Delete (the owner or an Admin), by Cancel, or by the Discard. | The audit row keeps the Snapshot label; nothing else remains. |

### What the user is told

- Sign-in lands on the Recordings page, the list of the user's Recordings, whether or not it is empty. The Recordings page is the landing list of the user's Recordings, with the way to the Upload page.
- No storage figure is shown while there is room. The Upload and Recordings pages warn only when the user is past 80% of their space or a Batch would take them over it.
- The standing line on the Recordings and Upload pages. The hours follow the idle-timeout setting:

```
Your recordings and transcripts are removed when you sign out or after 8 hours without activity. Download or export anything you want to keep.
```

- The sign-out dialog. The counts are the Workspace's own; the hours follow the idle-timeout setting. "Download clips" is a link on the Clips sentence. The buttons are Download all transcripts, Download everything, Cancel, and Sign out:

```
Signing out removes 3 recordings and their transcripts, 2 summaries, and 1 chat.
2 clips have not been downloaded. [Download clips]

[Download all transcripts]  [Download everything]  [Cancel]  [Sign out]
```

- When a Batch is unfinished the dialog adds:

```
1 transcription is still running. It will finish, and everything will be removed 8 hours after that unless you sign in again.
```

- The idle warning, 15 minutes before the idle timeout, with the button Stay signed in:

```
You will be signed out in 15 minutes and your recordings and transcripts removed.
```

The three downloads in the sign-out dialog:

- **Download all transcripts** is the Batch download zip across every Done Recording in the Workspace, not one Batch: one plain-text file per Done Recording, each carrying its notice. The Word export chapter owns the zip's naming and layout.
- **Download everything** is a zip holding, for every Done Recording, its Word Transcript with its Summaries and Chats inside plus its plain-text file, and every Ready Clip with its excerpt.
- **Download clips** gives a zip of every Ready Clip.
- Neither Download all transcripts nor Download everything is offered on the Batch page.
- Every file inside any of these zips writes its own "export made" audit row, and a "Clip downloaded" row is written per Clip inside any zip.

Exports and Clip downloads are the only ways anything leaves a Workspace. An Export sits beside every Summary (see the AI assistant chapter).

### The user's controls

- **Delete** on a Recording removes it and everything about it: Transcript, Summaries, Chats, Clips, files. It sits behind a confirmation that names the counts of Summaries, Chats, and Clips as well as the Transcript. On a Recording with an unfinished Job, Delete is the Queue and Jobs chapter's Cancel. Audit: "Recording deleted (cause: owner)".
- **Delete** on a single Summary, Chat, or Clip removes only that item.
- There is one Delete per Recording, not a "remove files, keep text" pair: with nothing kept past the session, the two are one. Download and Export (in the viewer, on the Batch page, and in the sign-out dialog) are the way to keep anything.

### When the disk is low

- Admin setting **"Minimum free disk space"**, in the Limits section: default 200 GB, range 10 to 10,000 GB, measured on the filesystem that holds `<App data folder>`.
- Below it, the Upload page says:

```
Uploading is paused because the server is low on space. Ask IT.
```

  and the tus pre-create hook refuses new uploads with the reason class `disk_full`.
- Recordings already accepted continue through media work and the Queue. If the disk truly fills, the media step fails with the reason class `media_failed` and Retry is offered.
- The status page shows free space with an amber line under twice the floor and a red line under the floor.
- Nothing is discarded early to make room. The Admin frees space with End sessions (which ends that user's Login session, after which the Discard follows the conditions above) or Delete data on the users list.

### Admins

Admins (through the Admin group, the manual admin flag, or a Local admin account) can open any user's material with the owner's powers, because IT must be able to troubleshoot a stuck Job, recover a leaver's work, and reassign material without asking the owner. The guard rails are the trade: every such access writes an audit row naming the Admin, the item, and the time, and the screen shows a banner that the Admin is viewing another user's Workspace (ADR 0004). No page or guide carries a line telling users that IT administrators can access everything in the system; that line was withdrawn, and the ADR's audit and banner rules stand.

- Users list, per person: the Workspace condition (Open, Busy, Ending, Empty), the count of Recordings and the GB on disk, and the last sign-in. Users see nothing of the audit log, so no per-Workspace history is shown to them.
- Status page: "Workspaces: N open, M busy, X GB in scratch" and the free-space line.
- Opening a Workspace shows everything, with the banner "Viewing <user>'s Workspace as an Admin" and an audit row. The Admin acts with the owner's powers: Delete, Cancel, export, download. An Admin's opening is not the user's activity and does not extend the Workspace.
- End sessions confirms:

```
This signs <user> out and removes N recordings and their transcripts.
```

- Reassign to a named user has nothing to act on in Phase 1 and is greyed out; it becomes a Phase 2 action on Cases.
- A leaver's Workspace is discarded when deactivation ends their Login session (the Busy rule applies). Nothing of a leaver's is kept for an Admin to reassign in Phase 1.

### The sweeper

All schedules run on the `worker` service. Everything reads database state, so a restart changes nothing.

| Schedule | Work |
|---|---|
| Every minute (`worker` service, one run at a time) | 1. End Login sessions whose last request is older than the idle timeout; write the sign-out audit row with cause "idle". 2. For every user without a Login session whose Workspace is not Busy and whose grace period, if any, has elapsed: run the Discard. |
| The Discard itself | Per Recording: mark it Discarding, stop any Clip render in flight (its half-made file goes with the folder), delete its folder, delete its rows (Clips, Summaries, Chats, Transcript, Jobs, then the Recording and its Batch when the Batch is empty), write "Recording deleted (cause: discard)". Then one row "Workspace discarded (N recordings, X GB)". Idempotent: a crash mid-way leaves rows marked Discarding, and the next minute finishes them. |
| Daily at 03:30 (the Media handling chapter's sweeper) | Remove upload pieces older than 24 hours; any folder under `scratch/` with no Recording row; any Recording marked Discarding for more than an hour. Counts are logged in the "daily sweeper ran" row. |
| Every ten minutes (the Queue and Jobs chapter) | Stalled-job recovery, unchanged. |

### Nothing outlives the Discard anywhere

- The WhisperX service's copy of a result is deleted at merge, and its 30-day job metadata holds no text.
- The audit log is metadata only (see the Audit log and logging chapter).
- Container logs hold no content.
- The language-model engine (Shared or Local) keeps nothing.
- The nightly database dump at 02:00 holds whatever is in an Open or Busy Workspace at that moment. The Snapshot is encrypted and only IT holds the key. `scratch/` and `uploads/` are never copied, so nothing of a Workspace is on disk after a restore. The after-restore step ends every Login session and runs the Discard for every Workspace within a minute of the stack starting, so no Workspace is resurrected from a backup (see the Backup and restore chapter).
- Turning the Folder management toggle either way never touches Workspaces.
- The Retention policy applies to Cases only. Workspaces never retain, so there is nothing for the Retention policy to absorb from Phase 1.

### Not in this phase

- No Chat or Summary is kept past the Login session; there is no kept or read-only Chat.
- No Workspace text or retention setting exists in the admin panel.
- No per-Workspace history is shown to users.
- Reassign has nothing to act on.

### Audit rows

| Row | When it is written |
|---|---|
| Recording deleted (cause: owner) | The owner presses Delete on a Recording. |
| Recording deleted (cause: admin) | An Admin presses Delete on another user's Recording. Delete data on the users list also writes its own "user data deleted by an Admin" row with counts. |
| Recording deleted (cause: cancel) | Cancel of a Job or a Batch removes the Recording, including Delete on a Recording with an unfinished Job. |
| Recording deleted (cause: discard) | The Discard removes a Recording, one row each. |
| Workspace discarded (N recordings, X GB) | Once per Discard, after the per-Recording rows. |
| sign-out, cause "idle" | The minute sweeper ends a Login session whose last request is older than the idle timeout. |
| session ended by an Admin | End sessions on the users list. |
| upload rejected, reason class `disk_full` | The tus pre-create hook refuses an upload because free space is below "Minimum free disk space". |
| Job failed, reason class `media_failed` | The media step fails because the disk filled. |
| another user's Workspace opened | An Admin opens a user's Workspace (ADR 0004); the affected user is filled. |
| export made | One per file inside the "Download all transcripts" and "Download everything" zips, as for any export. |
| Clip downloaded | One per Clip inside the "Download clips" and "Download everything" zips. |
| daily sweeper ran | The 03:30 sweeper, with its counts. |

### Settings

The behaviour above depends on these admin settings, by their names in the admin settings catalogue:

- The idle timeout (default 8 hours). Its description must say it is also the Workspace's lifetime: the standing line, the sign-out dialog, and the grace period all follow it.
- "Minimum free disk space" (Limits section, default 200 GB, range 10 to 10,000 GB).
- The per-user quota (default 50 GB) and its per-user override on the users list.
- The users list columns (condition, Recordings, GB), the End sessions confirmation, the greyed-out Reassign, and the status page's Workspaces and free-space lines are catalogue items this chapter fixes the content of.

### Left to the build

- The exact wording of the Delete confirmation on a Recording. The tickets fix only that it names the counts of Summaries, Chats, and Clips and the Transcript.
- How the sign-out dialog's counts read at zero, and whether the Clips sentence with its "Download clips" link shows when no Clip is undownloaded. The tickets give the wording with example counts only.
- The naming and layout of the "Download all transcripts", "Download everything", and "Download clips" zips. The Word export chapter owns them.
- How the free-space check reads the filesystem that holds `<App data folder>`. The tickets fix only what is measured and where it runs (the `worker` service and the Upload page's pre-create refusal).
- The exact users list and status page layouts. The tickets fix their content.

### Carried for Phase 2

- When Folder management is on, the sign-out dialog lists the Done Recordings not yet moved to a Case with a "Move to case" button beside "Download all transcripts" and "Download everything". A Recording moved to a Case leaves the Workspace at once and is not counted in the dialog. Unmoved Recordings are discarded exactly as written here.
- The Discard and the sweepers skip any Recording with a Case. A Recording added to a Case at upload is never in the Workspace.
- Reassign to a named user is a Phase 2 action on Cases; in Phase 1 it is greyed out on the users list.
- The Retention policy applies to Cases only, and turning the Folder management toggle either way never touches Workspaces.

### Sources

Workspace lifecycle rules; Audit log (the rows and causes it fixes for the Workspace); ADR 0004, Admins can open any user's content and every such access is audited.

### Amendments applied

- From the Word export ticket to the sign-out dialog: two downloads, "Download all transcripts" and "Download everything", neither offered on the Batch page; every file inside a zip writes its own "export made" row.
- From the Case folder ticket to the sign-out dialog and the Discard: "Move to case" in the dialog when Folder management is on; the Discard and the sweepers skip any Recording with a Case (recorded under Carried for Phase 2).
- From the backup ticket to "Nothing outlives the Discard": the 02:00 dump holds Workspace text; the after-restore step ends every Login session and runs the Discard within a minute; `scratch/` and `uploads/` are never copied.
- From the Clips ticket to the sign-out dialog, the Busy rule, and the Discard: the "Download clips" link; Download everything includes every Ready Clip with its excerpt; a Clip render never keeps a Workspace alive; the Discard stops a render in flight; Delete names the Clips in its confirmation.
- From the Upload page ticket to "What the user is told": sign-in lands on the Recordings page whether or not it is empty; no storage figure while there is room, warnings only past 80% or when a Batch would go over.
- From the Workspace lifecycle rules to the earlier "Chats and Summaries are kept" rule: overturned; nothing survives the Login session, and a leaver's Workspace is discarded at deactivation.
- From the Workspace lifecycle rules to the media handling rule that a Clip definition is kept and re-rendered on re-upload: withdrawn; Clip definitions go with the Recording and a re-upload is a new Recording.
- From the Queue ticket to the Login session rule: one Login session per user, the new sign-in wins.

## 13. Audit log and logging

The app keeps one audit log, and it does two jobs. It is the troubleshooting record of what happened to each Recording, Batch, and account, and it is the accountability record of Admins opening other users' material, which ADR 0004 makes mandatory from the first release. Every row carries a category, so the accountability rows come out in one filter. Workspace activity is logged exactly like Case activity. The log holds metadata only, never content. It is Admin-only: users see nothing of it, and there is no export. Both could be added later because the rows exist; neither is planned.

### Purpose and scope

1. The log exists to troubleshoot issues. The Admin-access rows ADR 0004 requires ride along in the same log, under the Admin category, and are queryable by user through the Affected user field.
2. Every row is metadata. The never-logged list below applies to this log and to every other log the app writes.
3. Admins read it in the Admin viewer. No one else sees any part of it, and nothing leaves it.
4. Admins can read all content, so the question of who else might see the log is closed: no one.

### The never-logged list

Never logged anywhere, in the audit log or in any other log:

- Transcript text
- the before-and-after text of a Correction
- Chat questions and answers
- Summary text
- Vocabulary terms
- search terms
- file contents
- passwords
- tokens
- Speaker names
- Clip titles
- Clip notes
- a Moment's description, the phrase that cued it, and the clip shown to the engine (Phase 4)

The Recording's original file name is kept. It is the Snapshot label, a Provenance fact the app already shows Admins, and the only way to recognise a Recording after it is discarded. Settings are never content, so a setting's old and new values are logged, with one exception: Office Vocabulary is content, so its row says only that it changed.

### Fields on every row

| Field | Content |
|---|---|
| time | Stored in UTC, shown in office time. |
| actor | The user id plus a username snapshot and the directory sign-in identity, or `system` with the name of the job (sweeper, Directory check, retention sweep, Integrity check; other chapters add backup, drill, and restore). |
| category and event | From the catalogue below. |
| outcome | Success or failure, plus the reason class on failure. |
| affected user | The owner of the item when not the actor, so "who opened this person's material" is one filter. |
| object | Type, id, and a Snapshot label that outlives the item: for a Recording the original file name and the first eight characters of its hash; for a person the username and directory sign-in identity at the time; for a Clip its time range; for a setting its name. |
| login session | The Login session the event happened in; blank for system rows. |
| client | The address as seen by the app's own Caddy (the client address is taken from the app's own Caddy only), and the browser family (Edge, Chrome, other). |
| details | A small structured block with the extras named in the catalogue. |
| chain | The hash link to the previous row. |

Nothing else. A row never depends on the item, the user, or the Login session still existing.

- **Snapshot label**: the short human-readable description a row keeps of the item it is about, so the row stays readable after the item is gone.
- **Affected user**: the owner of the item a row is about, recorded whenever that person is not the one who acted. It is always filled on the Admin category's access rows. It is the field that answers whose material was opened, and by whom.

### Where it lives and integrity

- A table in the app's own Postgres database.
- Two database roles: the app writes through an insert-only role that cannot change or delete rows; only the retention sweep's separate role removes rows.
- Each row carries a hash chained to the previous row.
- The **Integrity check** is a button on the admin status page, which also shows the last result, and a command for IT. It reports "unbroken since the first row" or names the first break, and writes its result as a row.
- This is tamper-evident, not tamper-proof: root on the box can rewrite the chain.
- No file mirror and no off-box forwarding in Phase 1. Forwarding rows to an office log collector or SIEM as they are written is not planned.
- The table rides in the database backup, and every restore ends by running the Integrity check, which writes its usual row (see the Backup and restore chapter).

### Retention

- Admin setting **"Audit log retention"**, in whole months: default 3, range 1 to 120.
- Rows older than the setting are removed by a daily sweep at 03:30, the same quiet hour as the media sweeper. The sweep runs under the sweep role and writes its own row, "audit retention sweep ran".
- Three months is enough because the log exists to troubleshoot issues; an office wanting a longer record raises the setting.
- The admin guide states the consequence plainly: an Admin access under ADR 0004 is forgotten after the retention period, and in Phase 2 the log will not cover the life of a Case unless the office raises the setting.

### The Admin viewer

- A page in the admin panel: a table, newest first, 100 rows a page.
- Filters: date range, actor, affected user, category, event, outcome, object (an id or part of a file name), and client address.
- A row expands to show its details block.
- Three entry points besides the menu: from the users list, "Activity" (rows where the person acted) and "Access to their material" (rows where they are the affected user); from a Recording's Details panel when an Admin views it, "History" for that Recording.
- Opening or filtering the page is not itself logged.

### Not built

- No user-facing History tab, no "recent sign-ins" on a profile, no per-Workspace history for users.
- No CSV export and no export command.
- The users' transparency is the "Viewing <user>'s Workspace as an Admin" banner and the audit row behind it. No page or guide carries a line that office IT administrators can access everything in the system; that line was withdrawn.

### Catalogue of the rows these chapters fix

Rows other chapters add (settings and templates, Cases, Shares, the Retention policy, People, Backup, Email, Case Chat, and the rest) are defined in those chapters. The full catalogue is in the appendix "Audit rows" of the spec.

| Category | Row | Who acts | What it records |
|---|---|---|---|
| Sign-in | sign-in succeeded | the user | source: directory or local |
| Sign-in | sign-in failed | the account that tried | reason class: wrong password, not in a group, deactivated, blocked, directory unreachable, throttled |
| Sign-in | sign-out; idle timeout; session ended by an Admin | the user; `system` (sweeper) for idle; the Admin for End sessions | the cause (the minute sweeper writes idle as cause "idle"); which Admin, when one ended it |
| Accounts | admin flag set or cleared; blocked or unblocked; deactivated or reactivated | an Admin or the Directory check | who acted |
| Accounts | Directory check ran; Directory check refused | `system` (Directory check) | counts per group and the member identifiers (usernames and directory sign-in identities); one further row per change made; the refusal's reason class |
| Accounts | Local admin created; Local admin password changed | the person who did it | the account |
| Accounts | user data deleted by an Admin; material reassigned to a named user (reassignment is Phase 2) | an Admin | counts; from whom to whom |
| Recordings | upload accepted | the user | original file name, size, duration, hash, detected format, Sides found |
| Recordings | upload rejected | the user | reason class: format, size, duration, quota, Batch limit, `disk_full` |
| Recordings | Recording opened | the user, or an Admin | one row per opening of the viewer. Playing, pausing, seeking, and scrolling are never logged, for anyone, Admins included |
| Recordings | Recording deleted | the owner; an Admin; `system` for the Discard; whoever cancelled | cause: owner, admin, discard, or cancel |
| Batch and Jobs | Batch submitted | the user | per Recording: Diarization choice and speaker-count hint, Translation, whether Vocabulary was given, preprocessing profile, model |
| Batch and Jobs | Job completed; Job failed; Job cancelled | `system` for completed and failed; who cancelled | duration; the failure's reason class (from the fixed list the Queue and Jobs chapter holds; `media_failed` when the media step failed); who cancelled. Queued and started are Job states, not audit rows |
| Viewer edits | Segment corrected; Speaker renamed; Speakers merged; Speaker changed on a line (v1.47.0); Speaker change undone; Speaker suggestion accepted or rejected; Recording renamed | the user, or an Admin acting with the owner's powers (Recording renamed: the people who work in it only) | Segment or Speaker ids and time ranges only; never the text, the names, or the title |
| Exports | export made | the user, or an Admin | kind: Word or plain text; one row per file inside any zip |
| Clips | Clip created; re-rendered; downloaded; deleted | the user, or an Admin | Clip id, time range, the two options; never the title or note. One "Clip downloaded" row per Clip inside any zip. An Admin downloading another user's Clip writes the usual row with the affected user and never sets the owner's downloaded mark. A Rename (title, note) writes no row |
| LLM | Chat turn; Summary generated; Speaker suggestions generated; Moment described (Phase 4) | the user | feature, model name, endpoint host, prompt template version, input and output token counts, duration, outcome; never the question, the prompt, the answer, or a Moment's description |
| Admin | setting changed | an Admin | setting name, old value, new value, and the optional note typed in the panel's tray; one row per setting in an Apply; Office Vocabulary says only that it changed. The settings chapter holds the template and test rows |
| Admin | another user's Workspace opened; another user's item opened (Recording, Transcript, Chat, Summary, Clip); Playback copy served to an Admin for another user's Recording | an Admin | the ADR 0004 rows; the affected user is always filled |
| Admin | Integrity check run | an Admin, from the status page button | the outcome, with the reason class on failure |
| System | Workspace discarded (N recordings, X GB) | `system` (sweeper) | counts and sizes |
| System | daily sweeper ran | `system` (sweeper) | counts |
| System | quota refused an upload | `system` | counts and sizes |
| System | audit retention sweep ran | `system` (retention sweep) | counts |
| System | Integrity check ran | `system` (Integrity check) | the check's result |

Struck from the earlier list: "audit log exported" (no export exists) and any user-facing History.

### Reason classes

- A **reason class** is the fixed short category a row records when something is refused or fails (a sign-in, an upload, a Job, a Clip render, a backup step), in place of free text. It goes in the outcome field beside "failure".
- Where a ticket fixed the identifier, it is a lower-case name with underscores, quoted in code: `disk_full`, `media_failed`. Where a ticket named classes in words (the sign-in and upload classes above), the identifier is the build's, one per class, never free text.
- Every chapter names the classes its refusals and failures use. `disk_full` is fixed here; the Queue and Jobs chapter holds the fixed list for Job failures, and the WhisperX service returns a Job's failure as a reason class the app can log.

### Every other log

- The app's Caddy, the tus sidecar, the media worker, the Django app, and the WhisperX service write ordinary logs for troubleshooting only. They are never the record.
- They go to the host's system journal through Docker's journald driver, on every container, and keep for as long as the host's journal keeps them. Journal retention is a host setting outside this app, one setting for the whole host (`<host journal retention>`). The admin guide states that journal retention is the host's, not the app's, and gives the way to read a service's log:

```
journalctl CONTAINER_NAME=<service>
```

- They hold no content: the Caddy access log sees paths that carry ids, never file names; the tus sidecar never logs request headers, which is where the file name travels; the WhisperX service never prints Transcript text or Vocabulary at its normal log level. The WhisperX service's 30-day job metadata holds no text.
- There is no log store of the app's own and no file mirror: the host's journal is the only place these logs go.

### Audit rows

The rows the log writes about itself:

| Row | When it is written |
|---|---|
| audit retention sweep ran | The daily 03:30 sweep removes rows older than "Audit log retention", with its counts. |
| Integrity check ran | The Integrity check finishes, from the command or after a restore, with its result. |
| Integrity check run | An Admin runs the check from the status page button, with the outcome and the reason class on failure. |

Every other row is in the catalogue above.

### Settings

- "Audit log retention" (months, default 3, range 1 to 120).
- The audit log page and its filters, the Integrity check button and its last result on the status page, and the "Activity" and "Access to their material" links on the users list are catalogue items this chapter fixes the content of.

### Left to the build

- The hash chain: which fields are hashed and how. The tickets fix only that each row carries a hash chained to the previous row and that the check reports "unbroken since the first row" or the first break.
- The name and form of the Integrity check command for IT. The tickets fix only that it exists and reports as the button does.
- The shape of the details block. The tickets fix its content per row and that it is "a small structured block".
- What the actor field holds for a failed sign-in when no account exists for the name typed.
- The job name the actor field carries on Job completed and Job failed rows; the tickets name the sweeper, Directory check, retention sweep, Integrity check, backup, drill, and restore, but not the worker.
- Identifiers for the reason classes the tickets named in words (wrong password, not in a group, deactivated, blocked, directory unreachable, throttled; format, size, duration, quota, Batch limit).
- How the browser family is detected.
- The admin guide's text: it documents the audit log, the retention setting and its consequence, the never-logged list, the Integrity check, journal retention being the host's, and the `journalctl` command (see the Repository, releases, and distribution chapter).

### Carried for Phase 2

- Phase 2 rows use the fixed field set above: Case created, deleted, reassigned; Share granted and Share revoked; the Retention policy's rows; the People rows; the Email category and "Email address updated"; Case chat turn. Their definitions are in their chapters and in the appendix "Audit rows". The Folder management toggle writes the ordinary "setting changed" row.
- A Person's name and notes join the never-logged list beside Speaker names.
- The never-logged list is also the never-mailed list: a Notification carries only what a row may.
- A Collaborator opening a Recording in a shared Case is the "Recording opened" row with the owner as affected user, so "Access to their material" shows Collaborators' openings beside Admins'; an Admin who is a Collaborator opens as a colleague, without the Admin category row.
- The export row gains the kind "case chat", and the reason classes `llm_case_too_large`, `clip_render_failed`, and the Backup and Email classes join the catalogue through their chapters.
- The retention consequence: the log will not cover the life of a Case unless the office raises "Audit log retention".

### Sources

Audit log; Workspace lifecycle rules (the rows and causes it fixes); ADR 0004, Admins can open any user's content and every such access is audited.

### Amendments applied

- From the deployment-topology ticket to "Every other log": container logs keep for as long as the host's journal does, not 30 days; the admin guide gives `journalctl CONTAINER_NAME=<service>`.
- From the settings catalogue ticket to the Admin category: "setting changed" carries the tray's optional note, one row per setting in an Apply, Office Vocabulary says only that it changed; the "Integrity check run" row for the status page button. The template and test rows are left to the settings chapter.
- From the Workspace lifecycle rules to the Recordings and System categories: "Recording deleted" names its cause (owner, admin, discard, cancel); "Workspace discarded (N recordings, X GB)"; the sign-out row's cause "idle"; `disk_full` joins the reason-class catalogue.
- From the backup ticket to "Where it lives and integrity": every restore ends by running the Integrity check, which writes its usual row.
- From the Clips ticket to the Clips row: one "Clip downloaded" row per Clip inside any zip; an Admin's download of another user's Clip carries the affected user and never sets the owner's mark; Rename writes no row. "Clip render failed" is left to the Clips chapter.
- From the Word export ticket, through the Workspace lifecycle rules, to the Exports row: one "export made" row per file inside a zip.
- From the Speaker management panel ticket to the never-logged list: a Person's name and notes (Phase 2).
- From the email notifications ticket to the never-logged list: it is also the never-mailed list (Phase 2).
- From the sharing, Retention policy, toggle transitions, and Case Chat tickets to the Phase 2 placeholders: recorded under Carried for Phase 2 and left to their chapters.


## 14. Admin panel

The panel is the Admin-only part of the app: the settings pages, the Status page, the Queue page, the Users page, the Audit log page, and the Installation page, reached from a left rail. Admins see it, Local admins included; users never see any of it. It uses the light and dark themes like the rest of the app. A setting never applies as it is edited: changes collect in a tray and are applied together, and each applied change is recorded in the audit log. This chapter gives the panel's shape, its saving model, and its pages. Every setting the panel exposes, with its type, range, default, phase, what it does, and when a change takes effect, is defined in the admin settings catalogue; this chapter names settings and does not repeat their rows.

A throwaway prototype of the panel exists in the planning repository at `prototypes/admin-panel/`. Where it and this specification differ (its Save bar, which the tray replaces; its greyed Phase 2 rows, which the build leaves out), this specification wins.

### The panel's rules

#### 1. Shape

The panel is one layout: a left rail of pages in three groups, and the chosen page on the right. A settings page lists its settings in a pane beside the form from 1280 pixels, each a jump to its row and marked when changed from default or waiting in the tray.

| Rail group | Pages, in order |
|---|---|
| Overview | Status, Queue, Users, Audit log |
| Settings | Features, Limits, Transcription defaults, AI assistant, Notices, Sign-in and directory, Audit log |
| Server | Installation |

The rail also carries a Help link to the admin guide (see Help and the guides). "Audit log" appears twice: under Overview it is the audit log viewer; under Settings it is the page holding the one setting Audit log retention. The rail shows how many edits are waiting in the tray for each group.

Each settings page is a form. On the left, the setting's name and a one-line help. On the right, the control, with "Default: x" beneath it, a "changed from default" mark whenever the value differs from the default, and a "When changed" line saying what a change does and when it takes effect. The names, help, defaults, and "When changed" wordings are the admin settings catalogue's.

Three placements the build must keep:

- The idle timeout lives on the Sign-in and directory page, not on Limits, with the Workspace wording in its description ("recordings and transcripts are removed when a session ends"); the Limits page carries a cross-reference to it.
- Local admins are an action, Create Local admin, on the Users page, not a setting.
- The Directory connection (the eight `LDAP_` keys) is shown read-only on the Sign-in and directory page, the bind password shown as set or missing, with a Test directory connection button (see Test directory connection below).

At the foot of the Settings pages sits the list of fixed rules that are not settings (see Fixed rules, not settings).

#### 2. Saving: the tray

A setting never applies as it is edited. Edits collect in a tray fixed at the bottom of the panel and kept across pages. The tray lists each change as the setting's name with its old and new value. It carries one optional note for the audit log (a ticket number or the reason). **Apply** writes every change in one step. **Cancel all** drops them. Leaving the panel with a tray that is not empty asks whether to apply or drop. Each Apply writes one audit row per changed setting, and each row carries the note (the Setting changed row under Audit rows).

Two things sit outside the tray and apply at once, with their own confirmation where one is needed:

- Templates. On a prompt template, Save raises the version and Reset to default restores the wording. On the Summary templates list: Add template, Enabled, Default, and Delete.
- Every action on the Users page.

The buttons on the Status and settings pages (Test directory connection, Check directory now, Test connection, Integrity check) and Cancel on the Queue page are actions, not settings: they run at once and write the audit rows given under Audit rows.

#### 3. Confirmations

No setting asks "are you sure"; the tray is the confirmation. The destructive actions confirm one by one:

- End sessions, with the count of recordings that go with it: "This signs <user> out and removes N recordings and their transcripts".
- Block.
- Cancel a Job.
- Delete a template.
- Delete a Local admin.

#### 4. Phase 2 rows are absent

Phase 2's settings are absent from the Phase 1 build: no rows, no greyed placeholders, no pages. They arrive with Phase 2 as a Cases page in the rail (Folder management, Sharing, Retention period, Warning before deletion, Recycle bin, Recording types, Speaker roles) and an Email page in the Settings group (Email notifications, Batch finished emails, the Notification templates, Test message), together with the Phase 2 rows on existing pages (Chat across cases and the Case chat prompt template under AI assistant; Case chat: most hours of talk per question under Limits). The admin settings catalogue lists them with Phase 2 in the Phase column so the build knows they are coming; see Carried for Phase 2.

#### 5. Django's own admin is not mounted

Django's own admin is not mounted: no URL, no link, in any environment. It would show raw tables, Transcript text included, without the audit row every Admin access to a user's material must carry (ADR 0004; see the Audit log and logging chapter). The Queue page and the user's own Retry cover the daily need. A wedged background job, on any queue, the `llm` queue included, is cleared from the terminal with a `./transcribe` subcommand (Procrastinate's own commands underneath) named in the Repository, releases, and distribution chapter.

#### 6. Refresh

The Status and Queue pages refresh every five seconds, like every other page. Viewing them writes no audit row.

#### 7. Feature Off means hidden, not deleted

Turning a feature off hides its controls and its existing items; turning it on again brings them back as they were. Queued Jobs run as submitted. In particular:

- AI assistant Off hides Summary, Chat, and Suggest names everywhere; existing Summaries and Chats are hidden, not deleted.
- Chat, Summary, or Speaker suggestions Off hides that one feature and its existing items.
- Clips available Off hides New Clip and the Clips sheet, hides the Clips page in the navigation, and drops Clips from the sign-out dialog and "Download everything"; Clip files already made stay until their Recording goes.
- Diarization available Off hides the Diarization choice on the Upload page; Recordings already processed keep their Speakers.
- Translation available Off hides "Translate to English"; a Recording holding more than one language is then transcribed in its winning language with a warning.

Nothing is deleted by any of them.

### The Status page

One page of lines, refreshed every five seconds. Every line the sources name, with the phase it arrives in:

| Line | Shows | Phase |
|---|---|---|
| Services | A health row per container from Docker's health state: `caddy`, `app`, `media-worker`, `worker`, `llm-worker`, `tusd`, `postgres`, `whisperx`, and `vllm` when the Local engine profile is on. | 1 |
| WhisperX service | The service's status endpoint rendered for Admins: the model loaded; the service's GPU and its VRAM used and free; line length and audio minutes queued; the current job's Consumer and stage; measured speed per model; versions; uptime; the last failure class and time; each Consumer token's last-used time. | 1 |
| Storage | Free space on the App data folder. Amber under twice the Minimum free disk space; red under it. | 1 |
| Workspaces | "Workspaces: N open, M busy, X GB in scratch". | 1 |
| Media | Media jobs running and upload pieces pending. | 1 |
| Directory | Reachable, or unreachable since a time; the last Directory check's result; the buttons Test directory connection and Check directory now. | 1 |
| AI assistant | Reachable, with the model and the last check time, or unreachable since a time; the Test connection button. | 1 |
| Audit log | The Integrity check button and its last result. | 1 |
| Versions | The running Release tag, the database migration, the service version. | 1 |
| Cases | "Cases: N, X GB; M expiring; K in the recycle bin, Y GB". While Folder management is Off the line stays, followed by "Folder management has been off since <date>". | 2 |
| Backup | The last Snapshot (time, result, size, Snapshots held, next run) and the last drill (time, result). Red when the last successful Snapshot is older than 26 hours, when the last Snapshot or the last drill failed, or when `BACKUP_TARGET` is empty; amber when a drill is more than 3 days overdue. | 2 |
| Email | "Email: not configured", or the last sent and the last failure with its reason class, red while the last try failed; and "People without an email address: N". | 2 |

#### Test directory connection

The button on the Status page's directory line and the one on the Sign-in and directory page run the same four checks, in this order, and show each as pass or fail with the directory's message:

1. Bind with the Bind account over LDAPS against the CA file.
2. Read the Sign-in group and the Admin group by DN and count their members. An empty Sign-in group is a warning, not a failure.
3. Resolve one member of each to a sign-in name.
4. Run the nested-membership search for that member.

These are the checks of the planning repository's bind test (`assets/26-bind-test.sh`). `./transcribe check` runs the identical checks from the command line.

### The Queue page

Every Job in the Queue, with user, title, Batch, duration, state, Step, position, and a Cancel button; nothing else. No Pause, no reordering, no priority. Cancel a Job confirms. The page refreshes every five seconds and writes no audit row when viewed.

### The Users page

One row per account. From 1280 pixels the form that creates a Local admin sits in a pane beside the table; below that width it follows the table.

| Column | Shows |
|---|---|
| Username | The sign-in name. |
| Display name | The directory's display name. |
| Address | The directory's userPrincipalName. |
| Role | Whether the account is an Admin. |
| Admin source | Where admin status comes from: Admin group, Manual, or Local. |
| Status | Active, Deactivated, or Blocked. |
| Workspace condition | Open, Busy, Ending, or Empty. |
| Recordings | The count, with GB on disk. |
| Quota | Default, or the override. |
| Last sign-in | When the account last signed in. |

Admin status is held through the Admin group, the manual admin flag, or a Local admin account, and the Admin source column names which. The Directory check re-derives group-held status and never removes a manual flag or lifts a block (see the Sign-in, accounts, and roles chapter).

Per person, from the row:

- **Open their Workspace**: audited, with the banner shown while the Admin is inside (see the Audit log and logging chapter).
- **Activity** and **Access to their material**: the two audit log views for that person, defined in the Audit log and logging chapter.
- **Set quota override**: a per-user figure that wins over Default Workspace quota per user.
- **End sessions**: confirms "This signs <user> out and removes N recordings and their transcripts". This is the Phase 1 way to free a user's space.
- **Block** and **Unblock**: Block confirms.
- **The manual admin flag**: greyed for group-held Admins and for Local admins.
- **Change password** and **Delete**, on Local admins only: Delete confirms; the last Local admin cannot be deleted.
- **Reassign to a named user** and **Delete data**: present but greyed until Phase 2 (nothing to reassign or delete in Phase 1; End sessions frees space).

At page level: **Create Local admin** (username, display name, password). The install creates the first Local admin, `transcribe-admin`. Every Users page action applies at once, outside the tray.

### The Audit log page

The audit log viewer, defined in the Audit log and logging chapter: newest first, 100 rows a page; filters for date range, actor, affected user, category, event, outcome, object (an id or part of a file name), and client address, in a pane on the left that stays put while the rows scroll from 1280 pixels and above the table on a narrower window; a row expands to its details block. No export button. There is no user-facing view of the audit log anywhere.

### The Installation page

The read-only `.env` facts, for checking; never a secret's value:

- The address and port (hostname and port), the bind address, the allowed client networks, the time zone.
- The App data folder.
- The WhisperX service's address and its GPU UUID.
- The engine network and the Local engine profile.
- Media threads per job (`MEDIA_THREADS_PER_JOB`) and media jobs at once (`MEDIA_CONCURRENT_JOBS`).
- The eight directory keys: `LDAP_ENABLED`, `LDAP_SERVER_URI`, `LDAP_CA_FILE`, `LDAP_BIND_USER`, `LDAP_BIND_PASSWORD_FILE`, `LDAP_SEARCH_BASE`, `LDAP_SIGNIN_GROUP`, `LDAP_ADMIN_GROUP`.
- The five secret files, each shown as set or missing: the Django key, the database password, the WhisperX Consumer token, the engine token, the HuggingFace token.
- "How this office gets releases": the repository address (`TNMD-FDO/gideon-transcribe` on GitHub) and the sentence that the app never checks for updates.

The service's own settings (batch size, VAD thresholds, limits, timeouts, alignment languages, the model cache path) live in the service's environment file and are IT settings, never panel settings; see the WhisperX service API document.

### Help and the guides

The rail carries a Help link that opens the admin guide, rendered inside the app from the repository's `docs/admin-guide.md`. Every user-facing page carries a Help link to the user guide at `/help/`, rendered the same way, opening at the guide's section about that page, and on a window 1500 pixels or wider a `?` beside it that opens the same guide (the admin guide, from the Panel) in a pane on the right of the page, at that section, the page making room for it rather than being covered; the pane stays open from page to page, each time at the new page's section, until it is closed. On a window 1280 pixels or wider the guide's contents list is a rail beside the text, which keeps its reading width, with the section being read marked. The guides therefore always match the running Release, and nobody needs GitHub to read them. The admin guide explains the panel, the tray and its note, the catalogue, the Installation page, the Sign-in page notice, and the `./transcribe` subcommand that clears a wedged background job.

### Fixed rules, not settings

Listed at the foot of the Settings pages so nobody looks for them:

- one unfinished Batch per user, Admins included (so there is no queued-Jobs-per-user setting);
- one sign-in per user at a time;
- the keep-alive grace period equals the idle timeout;
- no Queue priority and no Pause;
- the Discard within a minute and the sweeper at 03:30;
- Spoken language starts Automatic, with Whisper's own list (there is no Spoken language default);
- the AI assistant's sampling (its answer caps, time limits, and budgets are settings since v1.37.0);
- pages poll every five seconds and the worker every three;
- three uploads at once per browser, and leaving the Upload page abandons them;
- Two-channel call detection thresholds;
- export layouts, file names, and formats, and the Clip caption style;
- the WhisperX service's own settings (batch size, VAD, limits, timeouts, alignment languages, model cache) in its environment file;
- the audit log's field set and the list of what is never logged;
- five sign-in failures then a fifteen-minute wait;
- the storage warning on the Upload and Recordings pages past 80% of the user's space (a build constant);
- no Workspace retention setting, because nothing in a Workspace survives the Login session; no bulk-upload switch, because Files per Batch set to 1 does it.

### Audit rows

All in the Admin category, metadata only. The Audit log and logging chapter holds the field set.

| Row | Written when | Carries |
|---|---|---|
| Setting changed | Once per changed setting, at each Apply of the tray. | The setting's name, its old value, its new value, and the tray's note. For Office Vocabulary the row says only that it changed (Vocabulary is content). |
| Template saved | Save on a prompt template or a Summary template. | The template's name and its new version; never the text. |
| Template reset | Reset to default on a template. | The template's name and its new version. |
| Summary template added | Add template. | The template's name and its version. |
| Summary template deleted | Delete on a Summary template, after its confirmation. | The template's name. |
| Summary template flag changed | Enabled or Default changes on a Summary template. | The template's name and the flag. |
| Directory tested | Test directory connection, on either page. | The outcome and, on failure, the reason class. |
| Directory check run now | Check directory now. | The outcome and, on failure, the reason class. |
| Engine tested | Test connection, on the AI assistant page or the Status page. | The outcome and, on failure, the reason class. |
| Integrity check run | Integrity check. | The outcome and, on failure, the reason class. |

Viewing the Status or Queue page writes nothing. The rows for the Users page's actions (opening a Workspace, Block and Unblock, End sessions, the manual flag, the quota override, Local admin changes), for Cancel a Job, and for the nightly Directory check are given in the chapters that own those actions and consolidated in the Audit log and logging chapter.

### Left to the build

- The name of the `./transcribe` subcommand that clears a wedged background job. The Repository, releases, and distribution chapter names it; it runs Procrastinate's own commands underneath and must reach every queue, the `llm` queue included.
- The "Phone" Preprocessing profile choice appears in Transcription defaults only if the benchmark gate in the Media handling chapter admits it; otherwise the choices are Standard and Off.
- The admin guide (`docs/admin-guide.md`): its text is the build's, within the constraint that it explains the panel, the tray and its note, the catalogue, the Installation page, the Sign-in page notice, and the wedged-job subcommand.
- The wording of every confirmation other than End sessions, and of the question asked on leaving the panel with a tray that is not empty (its two choices are fixed: apply or drop).
- The arrangement of the Status page's lines. The sources fix the lines and their amber and red conditions, not their layout.
- The look of the "changed from default" mark, the "Default: x" line, and the rail's waiting-edit counts.
- How the guides are rendered from Markdown inside the app.

### Carried for Phase 2

Nothing below is in the Phase 1 build; it is listed so the build leaves room for it, and the Admin panel additions in Phase 2 chapter specifies it.

- A **Cases page** joins the rail with the settings Folder management, Sharing, Retention period, Warning before deletion, Recycle bin, Recording types, and Speaker roles (rows in the admin settings catalogue). Sharing, Retention period, Warning before deletion, Recycle bin, and Speaker roles are greyed while Folder management is Off.
- Folder management goes through the tray like every other setting, the note optional; its tray row shows the counts ("Hides 14 cases, 210 GB, for 6 users. Nothing is deleted."). Off hides every Case from everyone, Admins included, and keeps them with their Retention clocks paused; On brings the Cases pages back and resumes the clocks.
- The panel's Cases area also gains the **Admin's Cases page** (with an "Owner deactivated" filter and an "Expiring" filter) and the **Recycle bin page** (every user's deleted Cases, with an owner filter, Restore, and Delete permanently). Both are hidden while Folder management is Off.
- An **Email page** joins the Settings group: Email notifications, Batch finished emails, the four Notification templates (a Subject and a Body each, saved through the tray, so their Setting changed row holds the old and new text; Apply refuses an unknown placeholder), and a **Test message** button outside the tray that mails the signed-in Admin and shows the relay's reply.
- AI assistant gains **Chat across cases** and the **Case chat** prompt template; Limits gains **Case chat: most hours of talk per question**.
- The Status page gains the Cases, Backup, and Email lines in the table above.
- The Users page: Recordings and GB include Cases ("3 in session, 41 in cases"), and the figure stays while Folder management is Off; the quota's description says it covers the Workspace and every Case the user owns together (there is no separate Case quota); Reassign to a named user (one Case, or all of the user's Cases) and Delete data (the user's Cases, their binned Cases included, behind a confirmation naming the counts) come alive, and grey out again while Folder management is Off; the userPrincipalName column is relabelled "Directory address"; an "Email" column arrives, with "No email address" on blank rows and a filter for them, and an Email field on Create Local admin and on a Local admin's row.
- The Audit log page's category filter gains Email.
- The Installation page adds the backup facts, all read-only: the Backup target (account and host, never the key), the schedule, the keep rule, the local dump count, and whether the two backup secrets are set; and the seven mail keys. The backup schedule and keep rule are `.env` facts and never settings, because a host timer cannot be changed from inside a container.
- Clips available Off also hides the Case page's Clips tab.
- The Speakers tab is a user page inside the Case, not a panel page; the rail does not gain one.
- Every setting, prompt template, and Summary template is office configuration in the database and belongs in the backup set.

### Sources

Admin settings catalogue and panel (its Answer; the facts it carries from the LDAP, media handling, audit log, WhisperX contract, translation, queue, Workspace lifecycle, Phase 1 LLM features, Word export, deployment topology, Case folder, GitHub distribution, and directory objects tickets; and every amendment recorded on it); the prototype notes at `prototypes/admin-panel/README.md`; the glossary.

### Amendments applied

- From the Case folder ticket, to the Users page and the Status page: Recordings and GB include Cases, the quota's Phase 2 description, Reassign and Delete data's Phase 2 meanings, the Owner deactivated filter, the Cases line (all carried for Phase 2).
- From the sharing ticket, to the Cases rows: Sharing fixed as On or Off, default Off, greyed while Folder management is Off, Off hiding and never deleting (carried).
- From the Retention policy ticket, to the Cases rows and pages: Retention period, Warning before deletion, and Recycle bin defined; the Recycle bin page; the Expiring filter; the fuller Cases line; Delete data wiping binned Cases (carried).
- From the Speaker management panel ticket, to the Cases rows and the rail: Speaker roles added; the rail unchanged (carried).
- From the toggle transitions ticket, to the Cases rows, the tray, the Users page, and the Status page: Folder management fixed, its tray counts, what greys and hides while Off, the "off since" line (carried).
- From the backup ticket, to the Status page and the Installation page: the Backup line and its colours; the backup facts shown read-only; no backup settings (carried).
- From the GitHub distribution ticket, to the rail, every user-facing page, and the Installation page: the Help links and the in-app guides; "how this office gets releases".
- From the directory objects task, to Test directory connection: the four checks and `./transcribe check`.
- From the Clips ticket, to rule 7 and the Limits rows: what Clips available Off hides, the Clips page and the sign-out dialog included; Longest Clip; no caption style setting.
- From the Upload page ticket, to the Transcription defaults rows and the fixed rules: "Two-channel calls start unticked regardless" withdrawn; the "Diarize" label; the 80% storage warning as a build constant.
- From the email notifications ticket, to the rail, the Status page, the Users page, the Audit log page, and the Installation page: the Email page and its rows, the Email line, the Users page's email changes, the Email category, the seven mail keys (carried).
- From the Case Chat ticket, to the AI assistant and Limits rows: Chat across cases, the Case chat prompt template, Case chat: most hours of talk per question (carried).
- From the maintainer, on the v1.7.0 build, to the Audit log, Users and settings pages and to Help and the guides: the Workbench Layout's fourth page. The audit filters as a pane, the Local admin form beside the users table, a jump list beside every settings page, the guides' contents as a rail with the section being read marked, and Help landing on the section about the page it was pressed on. The "?" pane the layout proposal sketched, the guide opening beside any page, is not built: a pane on every page would make every page's layout yield to it, and the section link gives most of its worth.
- From the maintainer, on the v1.8.0 build, to Help and the guides: the `?` that opens the guide beside the page, which the v1.7.0 amendment had set aside, is built after all at the maintainer's ask, on windows 1500 pixels or wider, where a 360-pixel pane leaves the page its own shape.


## 15. Rules that hold everywhere

These rules cut across every chapter. Each one is stated once in the chapter that owns it; this list exists so that a builder working on one feature does not break a rule that belongs to another. Where this list and a chapter differ, the chapter wins.

### Where things run and what leaves the server

1. **Everything runs on the office's own server.** Free tools only, pinned versions, in Docker. No paid service, no paid model, nothing cloud-hosted. (Architecture and deployment; Repository, releases, and distribution)
2. **Nothing phones home.** The app never checks GitHub or anywhere else for updates. The server reaches the internet only at install and upgrade, for the hosts the install guide's appendix lists; at run time it reaches only the directory servers, the engine's Docker network, and in Phase 2 the backup store, all on the LAN. (Repository, releases, and distribution)
3. **Nothing office-specific lives in code.** Every office fact is a value in `.env`, a secrets file, or an admin setting, asked by `./transcribe install`. The product repository, its images, and its documents hold no office name, hostname, address, group name, account name, key, or path. (Architecture and deployment; Repository, releases, and distribution)
4. **Secrets are files, never values.** Passwords and tokens live in files under `secrets/` and `whisperx-service/secrets/`, named by `.env` keys that end in `_FILE`. They are never in `.env` itself, never in the database, never editable in the panel (which shows only "set" or "missing"), and never in a log. (Architecture and deployment; Admin panel)
5. **Only fetch and checkout of a Release tag ever reaches a server.** Nothing is pushed from a workstation or copied over the Install home; `./transcribe upgrade` refuses when tracked files have local edits and copies the configuration first. (Repository, releases, and distribution)
6. **The app is a separate stack.** It shares the server with whatever else runs there, one GPU by UUID, and a Shared engine's address as configuration, and nothing else: its own Compose project, data folder, reverse proxy, certificate, directory connection, and backup. (Architecture and deployment; ADR 0003)

### What the app keeps and what it never does with it

7. **The uploaded bytes are never changed, served, or downloadable.** The app keeps them only to hash, inspect, and derive from. Users take media out of the app as Clips or exports. (Media handling)
8. **Nothing survives a Login session in Phase 1.** Recordings, Transcripts, Summaries, Chats, Clips, Provenance, and Batches are discarded within a minute of the session ending, or after the last Job plus a grace period. Only the account, its flags, and the audit rows remain. A file uploaded again is a new Recording. (Workspace lifecycle)
9. **Nothing is discarded early to make room.** Below the free-space floor, uploads are refused and IT is told; nothing already accepted is touched. (Workspace lifecycle)
10. **Exports and Clip downloads are the only ways anything leaves a Workspace**, and every export carries exactly one notice, the Translation notice or the Transcription notice, never both and never on Captions. (Exports; Transcription, translation, and diarization choices)
11. **Content is never in a log, an audit row, or a message.** Transcript text, Corrections, Chat questions and answers, Summary text, Vocabulary, search terms, file contents, passwords, tokens, Speaker names, Clip titles, and Clip notes are never written anywhere but the database rows that hold them. The audit log is metadata; container logs go to the host's journal and hold no content. (Audit log and logging)
12. **Speaker embeddings are never requested or stored.** The WhisperX service keeps its door for them; the app never opens it in either phase. (Deferred and ruled out; the WhisperX service API document)

### Who may do what

13. **Sign-in is the office directory or a Local admin.** No SSO, no OIDC, no self-signup, nobody outside the office. Membership of the Sign-in group or the Admin group, nested groups counted, is read live at every sign-in and again by the nightly Directory check. (Sign-in, accounts, and roles)
14. **One Login session per user.** A newer sign-in wins and the older session ends with a message. The idle timeout is the only session limit; there is no absolute cap. (Sign-in, accounts, and roles)
15. **Admins may open anything, and every such access is audited.** The screen shows a banner while an Admin is inside another user's material; the audit row names the Admin, the item, the time, and the owner. No page or guide tells users so in a standing line; that line was withdrawn. Admins see and take; they never change another user's Clips, and their opening never extends a Workspace. (Sign-in, accounts, and roles; Audit log and logging; ADR 0004)
16. **Nobody has priority.** The WhisperX service's line is the only line; every Run is handed over the moment its Recording is Ready, in Ready order, nothing held back or reordered, users and Admins alike. The Admin's only control is Cancel. (Queue and Jobs; ADR 0005)

### How features behave

17. **Nothing runs by itself after a transcription.** Summary, Chat, and Speaker suggestions happen only when a user asks from the viewer, one Transcript at a time; Chat answers from the Transcript alone and declines everything else, and every claim is a Citation the app checks against a real Segment. (AI assistant)
18. **No LLM ever touches the translation path.** What Whisper produced is the Transcript, plus human Corrections. Translation is to English only, and the original-language text is not kept. (Transcription, translation, and diarization choices)
19. **Diarization is always a user's choice per Recording**, with a speaker-count hint, and the pages warn that automatic speaker separation is sometimes wrong. Nothing is ever run twice for one Recording. (Transcription, translation, and diarization choices; Upload page and Batch page)
20. **When the WhisperX service or the engine is down, the feature does not work.** There is no waiting state and nothing is deferred: the Upload page refuses a Batch, a Job fails with its reason class and offers Retry, an AI assistant click fails at once. (Queue and Jobs)
21. **Cancel throws everything away; failure keeps everything.** A cancelled Recording is removed as if never uploaded; a Failed Job keeps its files and a Retry button. (Queue and Jobs)
22. **Every page polls; nothing streams.** Pages poll the app every five seconds, the worker polls the service every three, and whole answers arrive when they are ready. No server-sent events in Phase 1. (Queue and Jobs; AI assistant)
23. **A setting never applies as it is edited.** Edits collect in the panel's tray and apply together, one audit row per changed setting with the optional note. No setting asks "are you sure"; destructive actions confirm one by one. (Admin panel)
24. **Feature Off means hidden, never deleted.** Turning a feature off hides its controls and its existing items; turning it on again brings them back. Queued Jobs run as submitted. (Admin panel)
25. **Django's own admin is never mounted**, in any environment. (Admin panel; Queue and Jobs)
26. **Every refusal and failure records a reason class**, a fixed short identifier in place of free text, with one plain message for users and the class name for Admins. (Audit log and logging; Appendix C)

### Words, times, and text

27. **The glossary's words are the app's words.** Pages, code, documents, and audit rows use the terms in `CONTEXT.md` with their capitalisation, and never the words each entry lists under "Avoid". Users never read "Workspace"; the pages say "your recordings". (`CONTEXT.md`)
28. **Times.** Timestamps are stored in UTC and shown in the office's time zone (`TZ` in `.env`). Scheduled work runs at fixed local times: the Directory check at 03:00, the sweepers at 03:30, and in Phase 2 the backup at 02:00 and the drill at 04:00. (Audit log and logging; Architecture and deployment)
29. **No em dashes or en dashes anywhere** in pages, exports, guides, or documents; hyphens, commas, or full stops. British spelling in documents and pages, as the glossary uses it. (This document's conventions)
30. **Guides are part of the Release.** The user guide and the admin guide are rendered into the app at build time from `docs/`, so they always match the running Release. (Repository, releases, and distribution)

### The look

31. **One visual language, applied everywhere.** From v1.14.0 (the finish the maintainer approved on 5 September 2026, `docs/research/` has no paper for it because it is a decision, not a fact): every colour on a page is a token from the stylesheet's palettes, light and dark being two palettes for the same roles; the typeface is IBM Plex Sans with IBM Plex Mono for times and counts, shipped with the app under the SIL Open Font License and fetched from nowhere; type is one of four sizes (display 28, title 22, heading 17, body 15, small 13); there are four buttons (primary, the one thing to do on a page; secondary; quiet, for tools inside a panel; danger, red and last in any row) in three fixed heights; one shape of pill whose colour is the state, with a dot for anyone who does not see the colour; one set of line icons in a sprite included on every page (`templates/icons.html`, `{% icon %}`), drawn at the stroke of the type, in place of typewriter glyphs; a visible focus ring on every control; motion of 120 ms and none for anyone who asked for none. The mark beside the wordmark is the favicon's waveform on a rounded square. A test keeps the stylesheet free of colours outside the palettes and the pages free of the old glyphs. (Every page; the Repository chapter for the licence.)

32. **The app asks in its own words, and says what it did.** From v1.15.0: no page uses the browser's own confirm, prompt or alert. A question before an act is the app's dialog (`ui.js`): a plain title, one or two sentences of consequence, the safe choice first and the action last, red when it destroys; a form or button that asks first carries the question in `data-confirm` attributes and submits only on yes. A quiet confirmation (Copied, Renamed, Saved) is a toast for two seconds; a refusal that needs no decision is a toast marked as a problem. A page with nothing in it shows one empty state (`empty.html`): what the place is for and the one thing to do. Instructions live in first-time hints a person dismisses once, remembered in their browser, and in the guides, not in paragraphs on working pages. The first sentence of any message is for a colleague, and the technical detail sits behind "Details". (Every page.)

33. **The office's face is the office's own.** From v1.16.0: the sign-in page is the front door, showing the office's logo large when an Admin has uploaded one on the Panel's Appearance page, the office's name under it (the Office name setting), and the app's name under that; without a logo, the app's mark and name. The logo is a PNG or JPEG up to 2 MB, recognised by its bytes, kept as one database row and served by the app at `/branding/logo` to the page nobody has signed in to yet, with a cache of five minutes and an ETag. With Logo on Word exports On it heads every export's cover, 1.5 inches wide above the title, followed by the office name in grey; Off leaves the exports as before. Uploading and removing write audit rows and never the image. Every browser tab reads "<where you are> · Gideon Transcribe". (Sign-in; Admin panel; Exports.)

## 16. Build gates and deliverables

This chapter gathers what the build must prove before the Phase 1 release and what it must deliver beside the running app. Every item was fixed by a decision; the build settles only the values the decisions left to measurement. The chapters own the details; this is the list.

### The benchmark gate

A by-hand step on the office's server, on the app's GPU, against the office's sample recordings at `<App data folder>/test-corpus/` (the kinds a corpus must cover are in the Media handling chapter). It runs before `v1.0.0` and again whenever the pinned stack or the models change. Nothing about it is a workflow, and its numbers never reach the repository as office facts: they land in the service README, the install guide, and the code as product figures.

| Leg | What is measured | What it fixes |
|---|---|---|
| Model and speed | `large-v3` against `large-v3-turbo` on the corpus: accuracy by a reader's judgement, and the measured speed per model with and without Diarization | The default Model stays `large-v3` unless the gate changes it; the measured speed figures the WhisperX service publishes, which the app uses for the Estimated wait once ten Jobs per setting have completed (the research reference figures serve until then) |
| Batch size and VRAM | The service's VRAM peak at the chosen batch size | The "GPU budget" line in the service README, the figure IT checks before another model is placed on the card; the GPU memory figure in the install guide's "What you need" |
| Dropped speech | The jail-call files: nothing the service's voice-activity settings do may lose quiet speech (onset and offset defaults in the WhisperX service API document) | The service's VAD settings as shipped |
| Preprocessing | Standard against Off on the jail-call and phone files; the Phone candidate (band filter and gentle noise reduction) against Standard | Phone ships as a third Preprocessing profile only if it measurably lowers errors; otherwise the choices stay Standard and Off |
| Translation | The four checks of the translation leg (the Transcription, translation, and diarization choices chapter), scored by the office with a bilingual reader, once the office supplies non-English and mixed-language samples | Pass or fail on names, numbers, dates, and amounts; no word-error rate |
| Media | The pinned ffmpeg identifies and decodes G.729 inside WAV on its own while the forced decoder still works; CPU transcode time for the body-worn camera file; the Two-channel call detection thresholds tuned on the corpus's call files | The ffmpeg pin and the image build check; NVENC stays out unless CPU transcodes prove slow; the thresholds as build constants documented in code |
| Resource limits | Memory limits per container and the media worker's CPU cap under load | The compose file's limits (starting values in the Architecture and deployment chapter) |
| AI assistant | Sampling, answer caps, and time limits under the Shared or Local engine | Starting values held in code (the AI assistant chapter); from v1.37.0 the caps, limits, and budgets are settings with those values as defaults, and sampling stays in code |

The corpus's hashes are verified before the gate runs. The gate's results are recorded in the planning material of the office that runs it, not in the product repository.

### Smoke checks

- `./transcribe check` prints every line the Repository, releases, and distribution chapter fixes. The first smoke check after an install is the real `pull` of the diarization model with the stored token, which proves the licence acceptance and the token together.
- First run ends with one corpus file taken from upload to Transcript on the address, signed in as the Local admin, with the Status page green on directory, service, disk, and, when an engine exists, the AI assistant (the Architecture and deployment chapter).
- The first sign-in test needs at least one member of the Sign-in group who is not in the Admin group, so that the ordinary User role is exercised (the Sign-in, accounts, and roles chapter).

### Deliverables of the Phase 1 build

The product repository at `v1.0.0` holds, beside the app and the service as this document specifies them:

1. **The two images** built from `app/` and `whisperx-service/`, published to ghcr.io on the tag, pinned by digest in the compose file (the Repository, releases, and distribution chapter).
2. **The helper script** `./transcribe`, generated at build time as a bash script, with the subcommands, the install questions in order, the `check` lines, the refusal rules, and the upgrade sequence the chapters fix.
3. **Both example environment files**, `.env.example` and `whisperx-service/.env.example`, every key with a comment (Appendix A).
4. **The compose files** `compose.yaml`, `compose.shared-engine.yaml`, and the Phase 2 `compose.drill.yaml` as an inert file, and `systemd/` with the Phase 2 units inert.
5. **The three guides** in `docs/`: the install guide from its fixed outline, the user guide, and the admin guide with the chapters the decisions name, the last two rendered into the app at build time.
6. **The community files**: `README.md`, `LICENSE`, `CONTRIBUTING.md`, `THIRD_PARTY_LICENSES.md` with each Release's exact ffmpeg and codec package versions, `SECURITY.md`, and `CHANGELOG.md` with its two fixed lines per section.
7. **The workflows** `ci.yml` and `release.yml`.
8. **The service README** with the "GPU budget" line from the gate and the pull instructions for a non-programmer.
9. **The spec pack, the glossary, the decision records, and the research findings**, as seeded.
10. **The public flip** at `v1.0.0`: the repository and both packages public, the ruleset on `main`, Issues on, Discussions off, Wiki off, private vulnerability reporting on, and the README's as-is line in place.

### Open points the build settles within the rules

The chapters list under "Left to the build" everything the decisions deliberately left open, with the constraints on each. A few points were not fixed by any decision and were found while assembling this document; the build settles them within the rules around them, or asks the office where a rule would be new:

- Retry on a Failed Recording while its Batch is still unfinished: Retry makes a new one-Recording Batch, and a user may have one unfinished Batch at a time (the Queue and Jobs chapter).
- What the app does with a Job's other Runs, still at the service, when one Run fails; the Job finishes as a whole with one reason class (the Queue and Jobs chapter).
- The viewer header and the Provenance line for a mixed Run when the mixed-language setting is Off, and when "Translate to English" was ticked; and how a multi-Side Recording whose Runs detected different languages is marked (the Transcription, translation, and diarization choices chapter).
- Whether the Office Vocabulary joins the "Known names" line for Speaker suggestions outside a Case; the decision names the Batch's own Vocabulary only (the AI assistant chapter).
- How the tus sidecar's fixed size flag follows the "Largest file" setting an Admin can change while the sidecar runs; the pre-create hook enforces the live value (the Media handling chapter).
- How the server pulls a private package from ghcr.io before the public flip: a registry sign-in, or the build path, which is the fallback either way (the Repository, releases, and distribution chapter).
- Whether a refusal decided in the browser before any byte is sent is reported to the app so that the "upload rejected" row is written (the Media handling chapter).
- Whether "Test directory connection" in the panel runs the same bind-and-read test as `./transcribe check`; the panel chapter says the two run the same four checks (the Sign-in, accounts, and roles chapter and the Admin panel chapter).
- The `speakers` hint sent without `diarize`: ignored, or refused; the WhisperX service API document carries the two readings as an unresolved point.

## 17. Deferred and ruled out

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

## Appendix A. Environment keys

Two files, both written by `./transcribe install` and shown read-only on the Installation page: the app's `<Install home>/.env` and the service's `<Install home>/whisperx-service/.env`. `.env.example` ships beside each with every key and a comment. Secrets are never values in these files, only the paths of secret files. The Phase 2 keys are in the Phase 2 document's appendix.

### The app's `.env`

| Key | Meaning | Default or placeholder | Chapter |
|---|---|---|---|
| `APP_HOSTNAME` | the app's hostname: Caddy's site name, the allowed hosts, the links in exports | `<hostname>`, no default | Architecture and deployment |
| `HTTPS_PORT` | the published HTTPS port | `8443` | Architecture and deployment |
| `BIND_ADDRESS` | the address Caddy publishes on | `0.0.0.0`; the server's LAN address keeps the port off other interfaces | Architecture and deployment |
| `ALLOWED_CLIENT_CIDRS` | the client networks Caddy answers; 403 to everyone else; empty means everyone | `<office CIDRs>` | Architecture and deployment |
| `APP_DATA_DIR` | the App data folder | `<App data folder>`, no default | Architecture and deployment |
| `APP_UID`, `APP_GID` | the `transcribe` system user's ids; `user:` on every app service | `<uid>`, `<gid>` | Architecture and deployment |
| `TZ` | every container's time zone; the host stays UTC | `UTC` | Architecture and deployment |
| `LDAP_ENABLED` | directory sign-in on or off; `false` gives a local-admins-only install | `true` | Sign-in, accounts, and roles |
| `LDAP_SERVER_URI` | the directory, by domain name, LDAPS on 636 | `ldaps://<domain>:636` | Sign-in, accounts, and roles |
| `LDAP_CA_FILE` | the office CA root as PEM | `ca/office-root.pem` | Sign-in, accounts, and roles |
| `LDAP_BIND_USER` | the Bind account's logon name | `<bind account>@<domain>` | Sign-in, accounts, and roles |
| `LDAP_BIND_PASSWORD_FILE` | the file holding the Bind account's password | `secrets/ldap_bind_password` | Sign-in, accounts, and roles |
| `LDAP_SEARCH_BASE` | the domain's base DN | `DC=<domain part>,DC=<domain part>` | Sign-in, accounts, and roles |
| `LDAP_SIGNIN_GROUP` | the Sign-in group's DN | `CN=<Sign-in group>,<groups OU DN>` | Sign-in, accounts, and roles |
| `LDAP_ADMIN_GROUP` | the Admin group's DN; blank means no group-derived admins | `CN=<Admin group>,<groups OU DN>` | Sign-in, accounts, and roles |
| `MEDIA_THREADS_PER_JOB` | ffmpeg threads per media job | `8` | Media handling |
| `MEDIA_CONCURRENT_JOBS` | media jobs the worker runs at once | `4` | Media handling |
| `WHISPERX_URL` | the service's address on the `whisperx` network | `http://whisperx:8000` | Architecture and deployment |
| `WHISPERX_TOKEN_FILE` | the app's Consumer token file for the service | `secrets/whisperx_consumer_token` | Architecture and deployment |
| `LLM_API_TOKEN_FILE` | the engine's bearer token file | `secrets/llm_api_token` | AI assistant |
| `DJANGO_SECRET_KEY_FILE` | Django's secret key file | `secrets/django_secret_key` | Architecture and deployment |
| `POSTGRES_PASSWORD_FILE` | the database password file | `secrets/postgres_password` | Architecture and deployment |
| `COMPOSE_FILE` | which compose files Compose reads; set only to add the shared-engine file | unset; with a Shared engine `compose.yaml:compose.shared-engine.yaml` | Architecture and deployment |
| `LLM_NETWORK` | the Docker network the engine is reached on: the Shared engine's, joined by `llm-worker` as external, or a plain network the install creates | `<engine network>`; default `transcribe-llm` | Architecture and deployment |
| `COMPOSE_PROFILES` | Compose profiles; `llm` turns the Local engine on | unset | Architecture and deployment |
| `LLM_LOCAL_MODEL` | the Local engine's model | `Qwen/Qwen3.8-27B-FP8` | Architecture and deployment |
| `LLM_LOCAL_GPU_UUID` | the Local engine's GPU, by UUID | `<GPU UUID>` | Architecture and deployment |
| `LLM_LOCAL_GPU_FRACTION` | the Local engine's share of the card's memory | `0.55` | Architecture and deployment |

### The service's `whisperx-service/.env`

| Key | Meaning | Default or placeholder | Where defined |
|---|---|---|---|
| `WHISPERX_GPU_UUID` | the service's GPU, by UUID, through CDI | `<GPU UUID>`, no default | Architecture and deployment |
| `HF_TOKEN_FILE` | the HuggingFace token file for the model pull | `secrets/hf_token` | the WhisperX service API document |
| `WHISPERX_ALIGN_LANGUAGES` | the alignment languages fetched at install | `en,es` | the WhisperX service API document |
| the limits, timeouts, VAD thresholds, and batch size (`WHISPERX_MAX_UPLOAD_GB`, `WHISPERX_MAX_AUDIO_HOURS`, `WHISPERX_JOB_TIMEOUT_BASE_MINUTES`, `WHISPERX_JOB_TIMEOUT_PER_AUDIO_HOUR_MINUTES`, `WHISPERX_RESULT_HOURS`, `WHISPERX_JOB_HISTORY_DAYS`, `WHISPERX_VAD_ONSET`, `WHISPERX_VAD_OFFSET`, `WHISPERX_BATCH_SIZE`) | the service's operating settings | as the service document fixes them | the WhisperX service API document |

### Secret files

| File | Holds | Written by |
|---|---|---|
| `secrets/django_secret_key` | Django's secret key | the install, random |
| `secrets/postgres_password` | the database password | the install, random |
| `secrets/ldap_bind_password` | the Bind account's password | the install, asked on the terminal |
| `secrets/whisperx_consumer_token` | the app's Consumer token, with its line in the service's tokens file | the install, random |
| `secrets/llm_api_token` | the engine's bearer token | copied from the Shared engine's operator; for the Local engine see the Architecture and deployment chapter's Left to the build |
| `whisperx-service/secrets/hf_token` | the HuggingFace token | the install, asked on the terminal |
| `whisperx-service/secrets/tokens` | one named Consumer token per line | the install writes the app's line |

Files that are not secrets but never committed: `tls/cert.pem`, `tls/key.pem`, `ca/office-root.pem`, and `backup/config-pre-<tag>.tar`.

## Appendix B. Audit rows

Every row uses the fixed field set of the Audit log and logging chapter and holds metadata only. The chapter named owns the row's contents. Phase 2 rows are in the Phase 2 document's appendix.

| Category | Row | Chapter |
|---|---|---|
| Sign-in | sign-in succeeded; sign-in failed (reason class); sign-out (cause: logout, idle, signed in elsewhere); session ended by an Admin | Sign-in, accounts, and roles; Workspace lifecycle |
| Accounts | admin flag set, admin flag cleared; blocked, unblocked; deactivated, reactivated; Directory check ran (snapshot), Directory check refused, one row per change made; Local admin created; Local admin password changed; user data deleted by an Admin | Sign-in, accounts, and roles; Audit log and logging |
| Recordings | upload accepted; upload rejected (reason class); Recording opened; Recording deleted (cause: owner, admin, discard, cancel) | Media handling; Workspace lifecycle; Audit log and logging |
| Batch and Jobs | Batch submitted (settings per Recording); Job completed (duration); Job failed (reason class); Job cancelled (by whom) | Queue and Jobs |
| Viewer edits | Segment corrected; Speaker renamed; Speakers merged; Speaker changed on a line; Speaker change undone; Speaker suggestion accepted; Speaker suggestion rejected; Recording renamed | Transcript viewer and player |
| Exports | export made (kind: transcript Word, combined, transcript text, captions, summary, chat; one row per file inside any zip) | Exports |
| Clips | Clip created; Clip re-rendered; Clip downloaded (one per Clip inside any zip; an Admin's carries the affected user); Clip deleted; Clip render failed (`clip_render_failed`) | Clips |
| LLM | AI assistant call (feature `chat_turn`, `summary`, `speaker_suggestions`, or `moment`; model, endpoint host, template versions, token counts, duration, outcome) | AI assistant; Moments (Phase 4) |
| Admin | setting changed (one per setting per Apply, with the tray's note); Template saved; Template reset; Summary template added; Summary template deleted; Summary template flag changed; Directory tested; Directory check run now; Engine tested; Integrity check run; another user's Workspace opened; another user's item opened (Recording, Transcript, Chat, Summary, Clip); Playback copy served to an Admin for another user's Recording | Admin panel; Audit log and logging; Media handling |
| System | Workspace discarded (N recordings, X GB); daily sweeper ran; quota refused an upload; audit retention sweep ran; Integrity check ran | Workspace lifecycle; Audit log and logging |

Never written: a row for viewing the Status, Queue, or Audit log pages; a row for playing, pausing, seeking, or scrolling; a row for a Rename of a Clip; "Queued" and "started" as Job rows.

## Appendix C. Reason classes

A reason class is the fixed short identifier a row records when something is refused or fails, with one plain message for users and the class name for Admins. Identifiers the decisions fixed are shown in code; where a decision named a class in words only, the identifier is the build's (one per class, never free text).

| Where | Classes | Chapter |
|---|---|---|
| Sign-in failed | wrong password; not in a group; deactivated; blocked; directory unreachable; throttled (identifiers left to the build) | Sign-in, accounts, and roles |
| Upload refused | `too_large`; `too_long`; `quota_exceeded`; `limit_exceeded`; `batch_in_progress`; `service_unreachable`; `disk_full`; `incomplete_file` (v1.44.0); and one class each for no audio track, undecodable audio, empty file, duplicate file, and archive (identifiers left to the build) | Media handling; Queue and Jobs; Workspace lifecycle |
| Job failed, from the service | `bad_input`; `too_large`; `too_long`; `model_unavailable`; `gpu_error` (retried once by the service); `timeout`; `cancelled`; `service_restarted`; `internal` | the WhisperX service API document |
| Job failed, the app's own | `media_failed`; `service_unreachable`; `service_refused`; `result_expired`; `merge_failed` | Queue and Jobs |
| AI assistant | `llm_unreachable`; `llm_timeout`; `llm_refused`; `llm_too_long`; `llm_bad_output`; `llm_error`; `llm_no_vision` (Phase 4) | AI assistant |
| Clip render failed | `clip_render_failed` | Clips |
| Directory check refused; Directory tested; Engine tested; Integrity check run | a reason class on failure (identifiers left to the build) | Sign-in, accounts, and roles; Admin panel |

## Appendix D. Sources

Each chapter was assembled from the resolved planning tickets named here, with every amendment recorded on them folded in. The tickets stay in the planning repository of the office that wrote the app; the decision records (`docs/adr/`) and the research findings (`docs/research/`) ship with this document.

| Chapter | Tickets |
|---|---|
| Architecture and deployment | Deployment topology on the rebuilt server; Relationship to the platform project on the server; Verify the server's mount and drive layout; Create DNS records and request the certificate; Prepare the server for the app: user, data folder, test corpus; ADR 0003 |
| Repository, releases, and distribution | GitHub distribution and install story; ADR 0006; the GitHub distribution research file |
| Sign-in, accounts, and roles | LDAP sign-in, roles, and the local admin; Create the directory objects: sign-in group and bind account; ADR 0004 |
| Media handling; Upload page and Batch page | Media handling from browser to ASR to player; Upload page and Batch settings prototype; Assemble a test corpus of real recordings; the media pipeline research file |
| Queue and Jobs; Transcription, translation, and diarization choices | App-side transcription queue and job model; Translation-to-English behaviour; WhisperX service API and operating contract; ADR 0005; the queue and worker research file |
| Transcript viewer and player; Clips | Transcript viewer and synced player; Clips: model, lifecycle, and management |
| AI assistant; Exports | Phase 1 LLM features: Chat, Summary, Speaker suggestions; Word export contents and layout; LLM handler capabilities and long-transcript strategy; the LLM handler research file |
| Workspace lifecycle; Audit log and logging | Workspace lifecycle rules; Audit log; ADR 0004 |
| Admin panel; the admin settings catalogue | Admin settings catalogue and panel, with the amendments from every later ticket |
| The WhisperX service API document | WhisperX service API and operating contract; Pinned WhisperX stack for the office's GPU generation; Accept the diarization model licence and create the HuggingFace token; Translation-to-English behaviour (the contract amendments); ADR 0002; ADR 0005; the WhisperX service research file; the pinned stack research file |
| Rules that hold everywhere; Build gates and deliverables; Deferred and ruled out | the map's notes, deliverables, fog, and out-of-scope lists, and every chapter's "Left to the build" |
