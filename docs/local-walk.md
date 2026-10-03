# Walking the pages on a workstation

How the pages are looked at before a push, at every screen size, without
an office's server: the app runs on the workstation against a database of
its own, filled with a fictional office.

## What runs

- Django's own development server, `python manage.py runserver`, with the
  same settings file the server uses. Nothing is turned on for it: debug is
  never on, and the cookies keep their secure flag (a browser treats
  `localhost` as secure, so sign-in holds).
- A PostgreSQL of the workstation's own (the test suite's portable one),
  with a database called `localdemo`, migrated like any install.
- `python manage.py collectstatic`, so the stylesheet and the scripts are
  served the way the image serves them. The folder it fills,
  `app/static-collected/`, is ignored by git.
- No media worker, no WhisperX, no engine, no mail and no directory: the
  pages that need them show their "not installed" or "not available"
  states, which are themselves worth looking at. Nothing plays.

## The fictional office

`python manage.py seed_demo --password-file <a file holding a password>`
fills an empty database: a Local admin and a colleague, three cases, body-camera videos
with transcripts and speakers, an incident with three cameras on one
clock, a phone call, a dictation, clips, and names waiting to be accepted.
Every name and every word is made up, and the recordings' files are
stand-ins. The command refuses to run where anybody already exists, so it
cannot touch a database in use; the password comes from a file the
workstation keeps outside the repository (or `--password` on the command
line), never from an environment key, which the app's own tests forbid.

## The walk

The browser's device emulation gives the shapes: 390 by 844 (a phone), 768
by 1024 (a tablet), 1024 by 768, 1366 by 768 (the laptop), 1366 by 768 at
125% zoom (1093 by 614), and 1912 by 1000 (a desk monitor), each in light
and dark. The look is judged against `the-look.md`. What the workstation
cannot show, the office's server shows after the upgrade: playback, the
assistant's results, and the office's own data at its own size.
