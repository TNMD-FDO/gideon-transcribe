# Close matches: measured before v1.97.0

Written 2026-09-28, before Find and Search were given close matches and
what was seen (Phase 7 chapter 3 as amended in v1.97.0). The maintainer
asked for a search that finds something close to what was typed, named the
words to try, and asked for few, good hits over missing nothing.

## What was measured

On the maintainer's server, read and changed nothing: the two extensions
the measurement needed (`pg_trgm`, `fuzzystrmatch`) were made inside a
transaction that was rolled back. The database held 13,015 lines said and
3,341 descriptions of what a camera showed, 4,969 distinct words between
them. For each word tried, the distinct words of the database were asked
three ways:

- **Word forms**: the same stem by PostgreSQL's English stemmer
  (`ts_lexize('english_stem', ...)`).
- **Near spelling**: `similarity()` of `pg_trgm` at 0.7, 0.6 and 0.5, words
  of four letters or more.
- **Sounds alike**: the same `dmetaphone()` of `fuzzystrmatch`, within an
  edit distance of three.

| Word | Said | Seen | Word forms | Near spelling, 0.6 | Near spelling, 0.5 adds | Sounds alike |
|---|---|---|---|---|---|---|
| dreadlocks | 0 | 65 | none | none | none | none |
| bottle | 12 | 45 | bottles | bottles | nothing | none |
| pill | 1 | 0 | pills | none | pillar, pillow | ten wrong words, among them polo (59 lines), pull (38), play (14) |
| write | 12 | 8 | writes, writing | writes | nothing | six wrong words, among them ride and wrote |
| right | 772 | 1,552 | rights | rights | nothing | five wrong words |
| remain | 3 | 621 | remains, remaining | remains | remainder, remaining | none |
| silent | 4 | 0 | none | none | none | none |

Nothing matched at 0.7 that did not match at 0.6.

A search of every line said for one word, by similarity or by stem, with
no index, took 45 to 49 milliseconds.

## Amended on 2026-10-04 (v1.123.0)

The 0.6 floor cannot be reached by a short word one letter off: "knive" and
"knife" share three trigrams of nine (0.33), "licence" and "license" five of
eleven (0.45); only a word of eleven letters or more clears 0.6 with one
letter changed. The floor now steps with the typed word's length (0.3 up to
five letters, 0.4 up to seven, 0.5 up to ten, 0.6 beyond), and a form found
under 0.6 is kept only when it is the word one letter changed, added or
dropped (two letters from eight letters up), measured in Python after the
query, so that trigrams alone never call "pillow" near "pills". The forms
by stem are untouched.

## What was decided from it

- **What was seen is searched.** "dreadlocks" is never said and is
  described 65 times; "bottle" is described more often than it is said.
  This is the larger gain, and it is an exact match.
- **Word forms are looked for.** Everything they added was the same word.
- **A near spelling is looked for at 0.6**, for words of four letters or
  more. At 0.6 nothing wrong was added; at 0.5 "pill" brought "pillow" and
  "pillar".
- **Matching by sound is left out.** It is the only one of the three that
  would join "write" to "right", and it brought dozens of wrong lines for
  a short word. The three lines with "to remain silent" all had "right"
  spelt as it should be.
- **No index.** The chapter's rule is an index only when a search takes
  more than a second on the largest case; this is a twentieth of that.
- **Two words typed together must both be on the line**, as before, each
  as itself or as a close form. "pill bottle" finds nothing here, because
  no line carries both; that is what the Look for run (v1.96.0) is for,
  which judges by meaning.

## Sources

Read 2026-09-28.

- PostgreSQL 18, `pg_trgm`, which says the module is trusted, "that is, it
  can be installed by non-superusers who have CREATE privilege on the
  current database": https://www.postgresql.org/docs/18/pgtrgm.html
- PostgreSQL 18, `fuzzystrmatch`: https://www.postgresql.org/docs/18/fuzzystrmatch.html
- PostgreSQL 18, `ts_lexize`, which returns an empty array for a stop word
  and NULL for a word the dictionary does not know:
  https://www.postgresql.org/docs/18/textsearch-debugging.html
