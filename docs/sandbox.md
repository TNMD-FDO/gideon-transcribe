# The sandbox: the app on a workstation, for a front end to build against

Phase 11 stage 0. The app runs on a workstation against a database of its
own, filled with a fictional office, so that the front end team can see the
pages the product API mirrors and, from stage 3, call the API itself. Nothing
of the office's is in it, nothing plays (the recordings' files are stand-ins),
and nothing is transcribed (there is no engine). It is `docs/local-walk.md`'s
way of running the app, written out for a machine that has nothing of ours
on it.

## What you need

- Python 3.13 and PostgreSQL 16 or newer (the server's own, or a portable
  one; Docker's `postgres` image is fine).
- ffmpeg is not needed: nothing is prepared or played.
- On Windows, `python-ldap` in `app/requirements.txt` may refuse to build.
  The sandbox never signs in through the directory, so a stand-in is enough:
  install the rest, and put an empty file named `ldap.py` in a folder on
  `PYTHONPATH`. On Linux and macOS it installs with the rest.

## Once

```bash
git clone https://github.com/TNMD-FDO/gideon-transcribe.git
cd gideon-transcribe/app
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Make a database and a folder for the app's data, and a file holding the
sandbox's secret key and one holding the fictional office's password:

```bash
createdb -h 127.0.0.1 -U postgres sandbox
mkdir -p ../sandbox-data
python -c "import secrets; print(secrets.token_urlsafe(48))" > ../sandbox-data/secret-key
echo "a-password-of-your-own" > ../sandbox-data/seed-password
```

The password file stays outside the repository (`.gitignore` ignores nothing
of yours by name, so keep it out of the clone's tracked folders); the app's
own tests forbid a password in an environment key.

## Every time

With these in the environment (a `.env` of your own, or the shell):

```
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=sandbox
POSTGRES_USER=postgres
POSTGRES_APP_USER=postgres
POSTGRES_PASSWORD=<the database's password, if it has one>
APP_DATA_DIR=<the sandbox-data folder's full path>
APP_HOSTNAME=localhost
DJANGO_SECRET_KEY_FILE=<the secret-key file's full path>
TZ=<your time zone, for example America/Chicago>
```

then, from `app/`:

```bash
python manage.py migrate --no-input
python manage.py collectstatic --no-input --clear
python manage.py seed_demo --password-file ../sandbox-data/seed-password
python manage.py runserver 127.0.0.1:8000 --noreload
```

`seed_demo` runs once: it refuses where anybody already exists, so it cannot
touch a database in use. It makes two accounts, `test` (an Admin) and `pat`,
both with the password in the file; three cases ("Harbour Street stop",
"Marsh Lane interview", "Demo: audio samples (fictional)"); body-camera
videos with transcripts and speakers; an incident with three cameras on one
clock; a phone call; a dictation; clips; and names waiting to be accepted.
Every name and every word is made up.

Open `http://127.0.0.1:8000/` and sign in as `test`. The cookies keep their
secure flag; a browser treats `localhost` as secure, so sign-in holds.

## What the sandbox shows and what it cannot

- Every page, at every size, in light and dark: the cases, the recordings,
  the transcript with its words and speakers, the notes and the chronology,
  the incident with its cameras and events, the documents, the Panel.
- Nothing plays: the recordings' files are stand-ins. Nothing is
  transcribed, summarised or proposed: there is no engine, and the pages show
  their "not available" states, which are themselves worth seeing.
- From stage 3, the product API answers on the same origin under `/api/v1/`,
  so a front end on the workstation can call it with the sandbox's sign-in.

## Starting over

Drop the database and make it again (`dropdb sandbox && createdb sandbox`),
then the "every time" steps. The data folder can be deleted too.

## The rules, even here

The sandbox holds nothing real, so there is nothing to protect in it; but the
front end built against it will hold the office's material one day, so build
with the rules in hand: no font, script or image from outside the building;
the app's origin and its cookie, never a token in a browser; nothing of a
recording in a log, an error message or a URL.
