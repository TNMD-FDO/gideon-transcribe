# ADR 0009: the app is not given the Docker socket

Date: 2026-09-03
Status: accepted

## The question

The Phase 1 specification's Status page shows "a health row per container
from Docker's health state", naming `caddy`, `app`, `media-worker`, `worker`,
`llm-worker`, `tusd`, `postgres`, `whisperx`, and `vllm`. The obvious way to
read Docker's health state from inside a container is to mount the Docker
socket into it.

## The decision

The app is never given the Docker socket, read-only or otherwise. The Status
page asks each service instead:

- `caddy`, `tusd`, and `whisperx` are asked over the network and answer or do
  not;
- `postgres` is asked for `SELECT 1`, which is the same question the health
  check asks;
- `app` is answering the page;
- `worker` and `media-worker` listen on nothing, so they are read from the
  work they have done: the last job on their queue to succeed. The `default`
  queue runs something every minute, so silence there means the worker is
  gone. The `media` queue runs only when there is media, so silence there
  means a quiet afternoon and nothing more, and the page says so.

## Why

The Docker socket is root on the server. Anything that can reach it can start
a container with the host's filesystem mounted, which is every recording, the
database, and every secret. This app exists because an office that handles
privileged material wants that material on its own server and nowhere else;
handing an application root on that server so that a page can print the word
"healthy" is a bad trade.

A socket proxy limited to `GET /containers/json` would be a smaller trade,
but it is another container, another pinned image, and another thing to
explain in the admin guide, and it would tell an Admin very little that
asking each service does not.

## What is given up

The Status page cannot say why a container is unhealthy in Docker's own
words, cannot see a container that is restarting in a loop while still
answering, and cannot list a container that is not in this list. An Admin
with a shell on the server runs `docker compose ps`, which is what they
would do anyway.

## What would change it

If a later phase needs restart counts or a container's own health output on
the page, the smaller trade is a socket proxy pinned to the one read-only
endpoint, never the socket itself.
