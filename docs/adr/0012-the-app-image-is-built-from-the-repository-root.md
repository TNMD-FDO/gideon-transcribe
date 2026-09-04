# ADR 0012: The app image is built from the repository root, and the guides are rendered into it

Date: 2026-09-04
Status: accepted

## The question

The specification serves the user guide at `/help/` and the admin guide from
the Admin panel, "rendered at build time from the same Markdown files in
`docs/`", so that what the app shows is exactly the running Release's text
and nobody who uses the app needs GitHub to read it. It leaves how to the
build.

The app image's build context was `./app`. Docker can only copy what is
inside the context, and `docs/` is outside it, so the build could not see the
guides at all. Three ways out:

1. **Build from the repository root.** The context becomes `.` with the
   Dockerfile named explicitly, and the Dockerfile copies `app/` and the two
   guides.
2. **Copy the guides into `app/` before building.** A step in `./transcribe
   upgrade`, in the release workflow, and in anybody's local build, and a
   copy that can go stale in the repository.
3. **Keep the guides under `app/`.** The specification names their paths in
   `docs/`, and a guide beside the code is not where a reader looks for it.

## The decision

The first. The app image is built from the repository root:

```yaml
build:
  context: .
  dockerfile: app/Dockerfile
```

The Dockerfile copies `app/` to `/opt/app/` and the two guides to
`/opt/app/guides/`, then runs `manage.py render_guides` beside
`collectstatic`. That renders each guide from Markdown to HTML with
Python-Markdown and keeps the result beside the source as JSON. A guide that
is missing or will not render fails the build, which is the point: a Release
with a broken guide never reaches a server.

On a workstation there is no `guides/` folder, so the app reads the Markdown
from the repository's `docs/` and renders it on the way to the page. The text
is the same either way.

The WhisperX service's image is unchanged: its context is its own folder and
it has its own ignore file.

## What it costs, and what guards it

**The context now holds the office's own files.** On a server the repository
root is the Install home, where `.env`, `secrets/`, `tls/` and `ca/` live.
Nothing in the Dockerfile copies them, but everything in a context is sent to
the Docker daemon unless the ignore file names it, so the root
`.dockerignore` names those four first, and the service's folder with them.
A test fails if any of them leaves that file.

**Three files name the context**: `compose.yaml` (three services built from
the one image), the release workflow, and the Dockerfile's own `COPY` lines.
They have to agree, and a build from the wrong context fails loudly on the
first `COPY`, which is the right way for it to fail.

**The rendered HTML is marked safe in the template.** It is this
repository's own Markdown and nothing a user typed, and the renderer is never
run over anything else.
