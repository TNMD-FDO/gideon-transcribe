# The app image: Django, its workers, and the media tools.
#
# One image runs as four services (app, media-worker, worker, llm-worker), so
# everything any of them needs is here. Media work is CPU only; no container
# built from this image ever sees a GPU.
#
# Debian 13 is the base because it carries ffmpeg 7.1, which identifies and
# decodes G.729 inside a WAV container without being told to, and that is what
# a phone system exports.
FROM debian:13-slim@sha256:d7e12182ce18b85b93007c1dedf31f2d29e01ccf3182cc4017c709b6259bc132

LABEL org.opencontainers.image.title="Gideon Transcribe app"
LABEL org.opencontainers.image.description="Local transcription, translation, and speaker diarization for an office that handles privileged material."
LABEL org.opencontainers.image.source="https://github.com/TNMD-FDO/gideon-transcribe"
LABEL org.opencontainers.image.licenses="CC0-1.0"

ENV DEBIAN_FRONTEND=noninteractive

# Python and ffmpeg from the distribution, and the libraries audiowaveform
# needs. The apt versions are not pinned, for the reason given in the WhisperX
# service's Dockerfile: Debian removes superseded versions within weeks, and
# the base image digest above is what fixes which Debian this is. The exact
# ffmpeg and codec versions of each Release are recorded in
# THIRD_PARTY_LICENSES.md.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-venv \
      ffmpeg \
      ca-certificates \
      curl \
      libmad0 \
      libid3tag0 \
      libsndfile1 \
      libgd3 \
      libboost-program-options1.83.0 \
      libboost-filesystem1.83.0 \
      libboost-regex1.83.0 \
      libldap2 \
      libsasl2-2 \
 && rm -rf /var/lib/apt/lists/*

# audiowaveform draws the waveform under the player. It is not in the Debian
# archive; the project publishes a .deb per Debian release, so it is fetched by
# version and checked against its hash before it is installed. Version 1.10.3
# ships no binaries and is functionally identical to this one.
ARG AUDIOWAVEFORM_VERSION=1.10.2
ARG AUDIOWAVEFORM_SHA256=4208706c6ae5ffb5761dddf8294eaf648c7ba9fb4d6fc6ec9f021d1bb109ea6e
RUN curl -fsSL -o /tmp/audiowaveform.deb \
      "https://github.com/bbc/audiowaveform/releases/download/${AUDIOWAVEFORM_VERSION}/audiowaveform_${AUDIOWAVEFORM_VERSION}-1-13_amd64.deb" \
 && echo "${AUDIOWAVEFORM_SHA256}  /tmp/audiowaveform.deb" | sha256sum -c - \
 && apt-get install -y --no-install-recommends /tmp/audiowaveform.deb \
 && rm -f /tmp/audiowaveform.deb \
 && rm -rf /var/lib/apt/lists/*

# The two media checks, made at build time so that a broken image never reaches
# a server: ffmpeg must decode G.729, and audiowaveform must run.
RUN ffmpeg -hide_banner -decoders | grep -qw g729 \
 && audiowaveform --version

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m venv "${VIRTUAL_ENV}"

# python-ldap is built from source against OpenLDAP's headers, so the
# compiler and those headers are installed for the one pip layer and taken out
# again in the same step; the shared libraries above are what stays.
COPY app/requirements.txt /tmp/requirements.txt
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      python3-dev \
      libldap-dev \
      libsasl2-dev \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 && apt-get purge -y --auto-remove build-essential python3-dev libldap-dev \
      libsasl2-dev \
 && rm -rf /var/lib/apt/lists/*

# The directory library must import in the finished image, so that a missing
# shared library is a build failure rather than a sign-in failure.
RUN python -c "import ldap; print(ldap.__version__)"

# The container runs as the office's own account, which has no home folder on
# the server, so HOME points somewhere writable.
ENV HOME=/tmp \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=transcribe.settings

# The build context is the repository root and not this folder (ADR 0012), so
# that the two guides the app serves can come from docs/ where the
# specification keeps them. The root .dockerignore keeps everything else out,
# the office's .env and secrets first among them.
COPY app/ /opt/app/
COPY docs/user-guide.md docs/admin-guide.md /opt/app/guides/
WORKDIR /opt/app

# The static files are gathered when the image is built rather than when a
# container starts, so every container serves the same bytes and none of them
# writes to its own filesystem to do it. The settings need a secret to import,
# and this one is thrown away with the layer.
#
# The guides are rendered here too, from Markdown to HTML, so that a guide
# that will not render fails the build and never reaches a server, and so
# that what the app serves is exactly the Release's own text.
RUN DJANGO_SECRET_KEY_FILE=/dev/null python manage.py collectstatic --no-input \
 && DJANGO_SECRET_KEY_FILE=/dev/null python manage.py render_guides \
 && rm -rf /opt/app/static

EXPOSE 8000
ENTRYPOINT ["/opt/app/entrypoint.sh"]
CMD ["web"]
