# ADR 0011: Caddy is given two roots, not one over the app data folder

Date: 2026-09-04
Status: accepted

## The question

Playback copies, waveforms, and Clip files are served straight from disk by
Caddy, because a multi-gigabyte stream must never pass through Python. Until
Cases, every one of those files sat under `scratch/`, and Caddy was given
exactly that folder, read-only:

```
handle /media/* {
	route {
		forward_auth app:8000 { uri /media-auth }
		root * /srv/scratch
		uri strip_prefix /media
		file_server
	}
}
```

A Recording in a Case lives under `cases/<case id>/<recording id>/` instead,
which is outside that root, so nothing in a Case would play.

The obvious fix is to move the root up one level, to the App data folder
itself, and put the holder in the path: `/media/scratch/<user>/...` and
`/media/cases/<case>/...`. One route, one root, and the URL mirrors the disk.

## The decision

Two roots and two routes, not one:

- `/media/*` over `/srv/scratch` for a Recording in a Workspace
- `/case-media/*` over `/srv/cases` for a Recording in a Case

Both routes are `route` blocks, not bare `handle` blocks, for the reason ADR
nothing records but the Caddyfile does: inside a plain `handle`, Caddy sorts
the directives into its own canonical order, which puts the `strip_prefix`
before the `forward_auth`. That happened once already and refused every media
file in the office, silently, from the day the route was written.

The app builds the URL from where the Recording actually is
(`media_access.media_root`), and the auth endpoint checks the holder in the
path against the Recording's own (`media_access.holder_of`) rather than
trusting it, so a Recording moved into a Case cannot still be fetched by its
old URL.

## Why

The App data folder holds more than the two folders Caddy needs. It also
holds `postgres/`, the database's own files, and `uploads/`, the resumable
upload pieces that have not been checked yet. A single root over the whole
folder would put both inside a `file_server`'s reach, and the only thing
standing between a request and them would be the `forward_auth` and the app's
own list of servable names.

That is one layer, and it is a layer that has already failed once in this
project for a reason nobody would have predicted: the order of two lines in a
config file. Naming the two folders Caddy may serve means that the same
failure, next time it happens, exposes waveforms and playback copies rather
than the database.

The cost is a second route and a second mount. It is small, and it is paid
once.

## What follows

- `compose.yaml` mounts `${APP_DATA_DIR}/cases:/srv/cases:ro` beside the
  scratch mount. Read-only, as scratch is: Caddy never writes.
- `./transcribe install` and `./transcribe upgrade` create `scratch/`,
  `cases/` and `uploads/` with the app account as owner before anything
  starts, because Docker creates a missing bind-mount source as root and the
  app could then never write into it. `./transcribe check` says so if one is
  wrong.
- CI adapts the Caddyfile the way Caddy does and fails if either route serves
  a file before it asks the app. Both routes are required to exist, so a
  route that is deleted is noticed.
- A third holder, if one is ever added, needs a third route. That is the
  intended friction: each one is a deliberate decision about what Caddy may
  reach.
