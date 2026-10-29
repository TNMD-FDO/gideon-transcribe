# The contracts (Phase 11, stage 0)

Two OpenAPI documents, written before any code moves, so that Gideon
Transcribe's own pages and the other front end (`gideon-frontend`) build
against the same thing. Nothing described here is served yet: stage 0 is the
contracts and the sandbox alone, and `docs/spec/SPEC-PHASE-11.md` chapter 4
says when each part is built. Until then the documents are the plan, and a
change to them is a change to the plan, agreed by both sides.

| Document | What it describes | Served from |
|---|---|---|
| `pipeline-v1.yaml` | The pipeline service's API and its Result, version 1 (Phase 11 chapter 1). | stage 2 |
| `product-v1.yaml` | The product's API under `/api/v1/`: sign-in and who I am, cases and recordings (Phase 11 chapter 2, sections 1 and 2). The later sections join this document as they are built. | stage 3 |

## Reading them

They are OpenAPI 3.1 and read in any OpenAPI viewer, or by eye: each path
says what it does, each schema what the fields mean, in the glossary's words
(`CONTEXT.md`). The app's test `tests/test_api_contracts.py` loads both and
checks their shape, so a document that no longer parses fails CI.

## The rules both documents keep

- **Nothing leaves the building.** Both APIs are on the office network behind
  Caddy. The pipeline service holds no titles, file names, cases or people;
  a Client sends a file and a reference of its own. Audio is deleted when a
  job ends; a Result waits at most 24 hours.
- **The same sign-in, the same rows.** The product API uses the office
  sign-in (the directory, the Login session) as a cookie on the app's origin,
  never a token in a browser. Every read of a record is the use of a Case the
  page's read is: the retention clock moves, the Admin's access row and the
  share's rows are written, with the client named.
- **The same words.** `reason_class` values are the app's own; states are the
  app's own; a recording's state words are the words its row shows.
- **Pagination** on every list, `Cache-Control: private, no-store` on every
  answer, and an error body of `{"error": "<reason words>", "reason_class": "<class>"}`
  with the status the pages would give (`400`, `403`, `404`, `409`).
- **Versions.** The path carries the major version (`/v1/`, `/api/v1/`); the
  Result carries `result_version`. A field is added, never changed or
  removed, within a version.

## What the front end team can do with them now

Build against the documents with stubs of their own, pick a framework with
the rules above in hand (no CDN, the app's origin, nothing leaving the
building), and run the sandbox (`docs/sandbox.md`) to see the pages the
API will mirror. Questions about a field or a path go to the Transcribe
maintainer, and the answer lands in these documents before anything is
built on it.
