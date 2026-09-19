# Search across a case: measured before v1.65.0

Written 2026-09-19 for Phase 7 chapter 3 (`docs/spec/SPEC-PHASE-7.md`),
which asked the build to measure the case-wide search on the office's
largest case before adding any index.

The Search tab and Find run plain `icontains` queries (PostgreSQL `ILIKE`)
over the segments of a case's transcripts, its events, its memos and its
summaries, with no index beyond the foreign keys. On the maintainer's
server, the largest case held 9 recordings and 2,664 segments of 8,526 in
the whole database.

| Query | Rows | Time |
|---|---|---|
| words, "gun" | 0 | 5 ms |
| words, "the" (the first 201) | 201 | 9 ms |
| words, "gun" and "backpack" | 0 | 4 ms |
| words, the phrase "I got gun" | 0 | 4 ms |
| events, "gun" | 0 | 1 ms |
| summaries, read in Python | 0 | 1 ms |

Milliseconds, so no index. The trigram extension (`pg_trgm`) is available
in the database image and not installed; the chapter's rule is to add a
trigram index on the segments' text only when a search takes more than a
second on the largest case, and to record the figures here when it does.
A case of a hundred hours would hold about a hundred thousand segments,
where an `ILIKE` scan is still well under a second on this server.
