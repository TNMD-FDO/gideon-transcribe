#!/bin/sh
# One image, four services. The word after the image name says which.
#
#   web            the Django application, behind Caddy
#   media-worker   ffmpeg and audiowaveform, CPU only
#   worker         the queue: hand-over to the WhisperX service, and the merge
#   llm-worker     the AI assistant
#
# Anything else is passed to Django's own command line, which is what
# `docker compose run --rm app create-local-admin` relies on.
set -eu

case "${1:-web}" in
  web)
    # The app's own database role, below the account that made the database.
    # It comes first, because from here on the migrations run as it.
    python manage.py ensure_roles
    # Migrations run as the web service starts, so that an upgrade is a
    # restart and nobody has to remember a separate step. The workers wait for
    # the app to be healthy, so they never race it.
    python manage.py migrate --no-input
    # No access log: Caddy keeps the request record, and gunicorn's would put a
    # line in the journal for every health check, four times a minute, for ever.
    # Threads under each worker (v1.132.0): one slow download no longer
    # takes a quarter of the app with it.
    exec gunicorn transcribe.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-4}" \
      --worker-class gthread \
      --threads "${GUNICORN_THREADS:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --error-logfile -
    ;;
  media-worker)
    exec python manage.py procrastinate worker \
      --queues media \
      --concurrency "${MEDIA_CONCURRENT_JOBS:-4}" \
      --delete-jobs=successful \
      --shutdown-graceful-timeout 540
    ;;
  worker)
    # A finished job's row carries its arguments, and a mail's arguments are
    # the message; a successful job is deleted as it ends (v1.130.0).
    # Two jobs at a time (v1.134.0): a hand-over sending a large file to the
    # WhisperX service, up to ten minutes, used to hold the poll, the mails
    # and the minute sweeps behind it. The poll itself stays single: its
    # lock in core/tasks.py keeps two from running at once.
    exec python manage.py procrastinate worker --queues default --concurrency 2 \
      --delete-jobs=successful \
      --shutdown-graceful-timeout 540
    ;;
  llm-worker)
    exec python manage.py procrastinate worker --queues llm --concurrency 4 \
      --delete-jobs=successful \
      --shutdown-graceful-timeout 540
    ;;
  *)
    # Anything else is a Django management command. The guides write these
    # names with hyphens, as `docker compose run --rm app create-local-admin`,
    # while Django takes them with underscores, because a Python module cannot
    # have a hyphen in its name. The first word is translated so that the
    # documented command is the one that works.
    command=$(printf '%s' "$1" | tr '-' '_')
    shift
    exec python manage.py "$command" "$@"
    ;;
esac
