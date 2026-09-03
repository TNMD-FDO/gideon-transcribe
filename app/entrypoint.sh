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
    # Migrations run as the web service starts, so that an upgrade is a
    # restart and nobody has to remember a separate step. The workers wait for
    # the app to be healthy, so they never race it.
    python manage.py migrate --no-input
    # No access log: Caddy keeps the request record, and gunicorn's would put a
    # line in the journal for every health check, four times a minute, for ever.
    exec gunicorn transcribe.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-120}" \
      --error-logfile -
    ;;
  media-worker)
    exec python manage.py procrastinate worker \
      --queues media \
      --concurrency "${MEDIA_CONCURRENT_JOBS:-4}"
    ;;
  worker)
    exec python manage.py procrastinate worker --queues default --concurrency 1
    ;;
  llm-worker)
    exec python manage.py procrastinate worker --queues llm --concurrency 4
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
