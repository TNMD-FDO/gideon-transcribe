# 17. Every recording gets its summary overnight

Date: 2026-10-04. Status: accepted. Release: the Phase 9 release that
builds its chapter 5.

## Context

Phase 1 chapter 17 ruled out "Summarise all", a bulk Summary per Done
Recording of a Batch: summaries were asked for one Recording at a time,
and the answer to "tell me about all of these" was the Case Chat. That
held while a case was a dozen recordings.

One of the office's departments reviews dumps of 800 or more jail calls,
about 200 hours of talk in one Case. The Case Chat cannot read 200 hours
in one question: it would be more than thirty Readings and a refusal at
the default ceiling. The way through (ADR 0018) is to read every
recording's Overview first and then the recordings the overviews point to,
whole. That needs an Overview for every recording, and the Overview is the
first part of a Summary. Eight hundred presses of New summary is not a
thing a person does.

## Decision

A tick on the Upload page, "Write each recording's summary tonight", and
an offer on the case page for the recordings already there without one.
Each marked recording's Summary is written in the overnight window the
Vision flow already keeps (Overnight from, Overnight until), oldest first,
one at a time by default and two when an Admin allows it, with the
recording type's template, Standard length and no Focus: the same Summary
a press of New summary gives. A summary the night does not reach is tried
the next night, as a video is. Nothing of this runs in the daytime.

## Consequences

- Phase 1 chapter 17's ruling is reversed for the overnight window alone.
  New summary in the daytime is unchanged.
- The engine's night carries the load: a 15-minute call is about 3,000 to
  4,000 tokens read and up to 1,600 written, about 90 seconds at the app's
  starting figure, so 800 calls are two nights one at a time or one night
  two at a time. The real figure comes from the office's expectation rows
  after the first night and goes in the box ledger's log, since GIDEON
  owns the engine.
- A reviewer opening any call finds its summary already written.
- The Overview becomes something the app reads (ADR 0018). It is still
  the Summary's first part, kept for its own sake, and not an index.
