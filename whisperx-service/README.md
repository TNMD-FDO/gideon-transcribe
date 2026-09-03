# The WhisperX service

Transcription, translation to English, word timing, and speaker separation, on
one GPU, one job at a time, with nothing leaving the building.

This folder is a product of its own. It has its own image, its own settings,
its own version number, and this README, and it runs without the app that
normally consumes it. Any application holding a token for it is a Consumer and
uses the same contract, which is written out in `docs/whisperx-api.md` at the
top of this repository.

It runs exactly one job at a time across every Consumer, in the order they
arrived. That rule lives here rather than in any application, so no Consumer
can transcribe beside another on the same card.

## What you need before you start

- A server with an NVIDIA card, the NVIDIA container toolkit with CDI turned
  on, and Docker with the Compose plugin.
- A HuggingFace account that has accepted the conditions of the diarization
  model, and a token belonging to that account. Both are needed together, and
  neither is enough on its own. See "The HuggingFace gate" in
  `docs/whisperx-api.md`.
- Somewhere for the models (about 6 GB) and somewhere for the service's own
  state.
- Video memory: see "GPU budget" below.

## Installing it

On a full installation of Gideon Transcribe, `./transcribe install` does all of
this and you never edit a file by hand. Running the service on its own:

**1. Settings.** Copy `.env.example` to `.env` and fill in the values written
in angle brackets. Every key has a comment above it saying what it does. The
ones with no sensible default are the card's UUID (`nvidia-smi -L` lists them),
the account the container runs as (`id transcribe`), and the two folders.

**2. The two secret files.** They are read by the service, which runs as the
office's own account, so they belong to that account:

```bash
mkdir -p secrets && chmod 700 secrets
read -rsp 'HuggingFace token: ' t && echo && printf '%s' "$t" | sudo tee secrets/hf_token >/dev/null && unset t
sudo chown transcribe:transcribe secrets/hf_token && sudo chmod 400 secrets/hf_token
```

Then a token for each application that will use the service:

```bash
docker compose run --rm whisperx make-token transcribe
```

It prints a line. Put that line in `secrets/tokens`, and give the file the same
owner and mode as the one above. The service picks up a change to that file on
its own, so adding an application later restarts nothing.

**3. Build the image.**

```bash
docker compose build
```

Everything installed into it is pinned to an exact version, and the reasons are
in `docs/research/whisperx-pinned-stack.md`. Do not raise a version without
reading that file: the stack was chosen for one generation of card, and several
of the pins hold each other in place. The first build takes a while, because
the torch and CUDA wheels are several gigabytes.

**4. Check the container.**

```bash
docker compose run --rm whisperx selftest
```

It prints what the container can see: the pinned versions, the card and its
compute capability, the ffmpeg version and whether it can decode G.729, and
whether the mounted folders can be written to. It downloads nothing and loads
no model, so it is safe to run at any time. It ends either with "Everything
this container needs is in place" or with a list of what is wrong and what to
look at.

**5. Fetch the models.**

```bash
docker compose run --rm whisperx pull
```

This is the only time the service reaches the network on purpose. It fetches
the two transcription models, the diarization model, and the alignment models
for the languages in `WHISPERX_ALIGN_LANGUAGES`, checks each against the
revision it is pinned to in `models.yaml`, and finishes by loading the default
model on the card once so that the driver's compiled kernels are cached and the
first person to use the service does not wait for them.

If it fails at the diarization model, the cause is almost always one of two
things: the token is wrong, or the account that token belongs to has not
accepted the model's conditions on its HuggingFace page.

**6. Start it.**

```bash
docker compose up -d
```

`docker compose ps` shows it healthy once the API is up. After this the service
makes no network call at all, with one exception the contract describes: a job
in a language whose alignment model was never fetched makes one attempt to
fetch it, and finishes with sentence timing rather than word timing if that
fails.

## Using it

The API is under `/v1/`, reached at `http://whisperx:8000` from inside the
`whisperx` Docker network. There is no published port and no hostname. Submit a
job, poll it, fetch the result, delete it. Everything about it, including what
every field means and what every refusal means, is in `docs/whisperx-api.md`.

## What it keeps, and for how long

- The audio you send is deleted the moment the job ends, whether it worked,
  failed, or was cancelled.
- The result, which holds the transcript, is deleted when you delete the job
  after fetching it, or after a day, whichever comes first.
- The job's own row (its id, which Consumer sent it, how long it took, how it
  ended) stays a month for troubleshooting and holds no text at all.
- The journal holds job ids, Consumer names, stages, timings, and reason
  classes. It never holds transcript text, vocabulary, the context line, or a
  token. `WHISPERX_LOG_LEVEL=debug` adds detail for IT: which model was loaded,
  how long each stage of a job took, what the card was holding, and why a
  language was chosen. It still holds none of the four things above.

## GPU budget

To be filled in by the Phase 1 benchmark gate: the measured peak video memory
at the batch size the gate chooses. That figure is what to check before
anything else is placed on the same card.

## Measuring it on your own recordings

```bash
docker compose run --rm -v /path/to/recordings:/corpus:ro whisperx bench /corpus
```

It prepares each recording the way the app does, runs it through the service
with each model and with speaker separation on and off, watches the card while
each job runs, and writes a report into the service's state folder. Nothing it
writes goes into this repository: it is made of your own recordings.

`--only=name` runs one recording, `--models=` and `--diarize=` narrow what is
tried, and `--label=` names the report. The batch size and the voice-activity
thresholds are settings rather than per-job choices, so comparing them means
running this again with a different `.env`; every report records the settings
the service actually used.

## When something is wrong

`docker compose logs whisperx` and `journalctl CONTAINER_NAME=whisperx-1` say
what the service has been doing. The status endpoint reports what is loaded,
what the card holds, how long the line is, and the last failure. An admin token
can list and cancel every Consumer's jobs, which is how a wedged line is
cleared from a terminal without touching containers.
