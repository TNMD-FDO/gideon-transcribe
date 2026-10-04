"""Close matches (v1.97.0): the forms of a word that Find and Search also
look for.

A plain word typed into Find or Search is matched as a whole word, as it
always was. Beside it the app now looks for that word's close forms: the
same word in another form ("pill" and "pills", "search" and "searched"),
by PostgreSQL's own English stemmer, and a near spelling of it
("dredlocks" and "dreadlocks"), by the trigram similarity of pg_trgm. Only
forms that are written somewhere in what is being searched are looked for,
so every close match is a whole word a person can see lit on the line.

The rule lives here and nowhere else: the database says which forms are
close, and the search then matches them as it matches any whole word. A
phrase in quotes has no forms. Measured on the office's own lines before
the build (docs/research/close-matches.md): at 0.6 a near spelling added
nothing wrong, at 0.5 it brought "pillow" for "pill"; matching by sound
brought "polo" for "pill" and is left out.
"""

from __future__ import annotations

import logging
import re

from django.db import DatabaseError, connection, transaction

log = logging.getLogger(__name__)

# The least similarity a near spelling has, and the shortest word that is
# given one; the most forms looked for beside one word.
LEAST = 0.6
# A short word shares few trigrams with itself one letter off ("knive" and
# "knife" share three of nine), so the floor steps with the length (v1.123.0):
# up to 5 letters 0.3, up to 7 letters 0.4, up to 10 letters 0.5, then LEAST;
# a stepped floor holds only for a word of about the same length (one letter
# longer or shorter), so "pill" is not near "pillow".
FLOORS = ((5, 0.3), (7, 0.4), (10, 0.5))
SPELT_FROM = 4
FORM_FROM = 3
MOST_FORMS = 8

LETTERS = re.compile(r"[^\W\d_]+")
SPLIT = r"[^[:alpha:]]+"


def words_of(text: str) -> set[str]:
    return {one for one in LETTERS.findall((text or "").lower()) if len(one) >= 2}


def forms(words, sources=(), texts=()) -> dict[str, list[str]]:
    """The close forms of each plain word, from what is being searched:
    `sources` are (queryset, field) pairs read by the database, `texts` what
    the app reads itself (a memo's paragraphs, a summary's). A word with no
    close form has no entry. Nothing for a phrase in quotes."""
    from core.case_search import Phrase

    if isinstance(words, Phrase) or not words:
        return {}
    asked = sorted({word.lower() for word in words if len(word) >= FORM_FROM})
    if not asked:
        return {}
    parts: list[str] = []
    params: list = []
    for queryset, field in sources:
        inner, inner_params = (
            queryset.order_by().values_list(field).query.sql_with_params()
        )
        parts.append(
            f"SELECT lower(regexp_split_to_table(s.t, '{SPLIT}')) AS w "
            f"FROM ({inner}) AS s(t)"
        )
        params.extend(inner_params)
    written = sorted(set().union(*[words_of(text) for text in texts])) if texts else []
    if written:
        parts.append("SELECT unnest(%s::text[]) AS w")
        params.append(written)
    if not parts:
        return {}
    sql = (
        "WITH written AS (SELECT DISTINCT w FROM ("
        + " UNION ALL ".join(parts)
        + ") AS every WHERE length(w) >= %s) "
        "SELECT q.word, v.w, "
        "(cardinality(ts_lexize('english_stem', q.word)) > 0 "
        " AND ts_lexize('english_stem', v.w) = ts_lexize('english_stem', q.word)) "
        " AS same, "
        "similarity(v.w, q.word) AS near "
        "FROM written AS v, unnest(%s::text[]) AS q(word) "
        "WHERE v.w <> q.word AND ("
        " (cardinality(ts_lexize('english_stem', q.word)) > 0 "
        "  AND ts_lexize('english_stem', v.w) = ts_lexize('english_stem', q.word)) "
        " OR (length(q.word) >= %s AND length(v.w) >= %s "
        "  AND similarity(v.w, q.word) >= CASE"
        "   WHEN length(q.word) <= %s AND abs(length(v.w) - length(q.word)) <= 1"
        "    THEN %s"
        "   WHEN length(q.word) <= %s AND abs(length(v.w) - length(q.word)) <= 1"
        "    THEN %s"
        "   WHEN length(q.word) <= %s AND abs(length(v.w) - length(q.word)) <= 1"
        "    THEN %s"
        "   ELSE %s END)"
        ") ORDER BY same DESC, near DESC, v.w"
    )
    floors = [value for pair in FLOORS for value in pair]
    params = [*params, FORM_FROM, asked, SPELT_FROM, SPELT_FROM, *floors, LEAST]
    try:
        # A savepoint: a database without the extension fails here alone
        # and the exact search goes on.
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    except DatabaseError:
        log.warning("close matches could not be read; the exact search stands")
        return {}
    found: dict[str, list[str]] = {}
    for word, form, same, near in rows:
        if not same and near < LEAST and not _one_slip(word, form):
            # Under the stepped floor a form counts only when it is the word
            # a letter or two off; trigrams alone would call "pillow" near
            # "pills" (v1.123.0).
            continue
        kept = found.setdefault(word, [])
        if len(kept) < MOST_FORMS and form not in kept:
            kept.append(form)
    return found


def _one_slip(word: str, form: str) -> bool:
    """Whether `form` is `word` with one letter changed, added, dropped or
    swapped with its neighbour (two such slips for a word of eight letters or
    more): the slips a short word may have ("lettre" for "letter")."""
    allowed = 2 if len(word) >= 8 else 1
    if abs(len(word) - len(form)) > allowed:
        return False
    rows = [list(range(len(form) + 1))]
    for i, a in enumerate(word, 1):
        now = [i]
        for j, b in enumerate(form, 1):
            cost = min(
                rows[i - 1][j] + 1, now[j - 1] + 1, rows[i - 1][j - 1] + (a != b)
            )
            if i > 1 and j > 1 and a == form[j - 2] and word[i - 2] == b:
                cost = min(cost, rows[i - 2][j - 2] + 1)
            now.append(cost)
        rows.append(now)
    return rows[-1][-1] <= allowed


def every_form(found: dict[str, list[str]]) -> list[str]:
    """The forms as one list, for the line that says what else was looked for."""
    out: list[str] = []
    for kept in found.values():
        for form in kept:
            if form not in out:
                out.append(form)
    return out
