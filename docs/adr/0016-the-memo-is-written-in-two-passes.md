# 16. The incident memo is written in two passes

Date: 2026-09-26. Status: accepted. Release: v1.91.0.

## Context

The Incident memo (Phase 6 chapter 3) was one call: the incident record
(every synced camera's Digest or words, merged on one clock, two to three
thousand lines on a twelve-camera incident) and the chronology in, the memo
out. The maintainer's walk of the outputs on the office's copy, on
2026-09-25 and 2026-09-26 at v1.90.0 and v1.90.1, found the engine's model
writing the memo by copying the record: phases that were lists of the
record's lines with their speaker labels, the memo's parts folded into one
another, the story trailing off before the end, a 4,000-token cap reached
at 2,100 words with five parts unwritten. Two rounds of re-shipped wording
(v1.90.0 and v1.90.1) improved the memo and did not cure this: a model of
this size, asked to read 230,000 tokens and write 1,800 words of prose in
one breath, falls back on the text in front of it.

## Decision

The memo is written in two passes.

1. **The facts sheet.** The model reads the record and the chronology once
   and answers as data, under a JSON schema: the people who matter and how
   the record identifies them; a timeline of the moments that tell the
   story in order from the first camera's start to the conclusion, each
   with its time, camera, one plain sentence, a quote copied word for word
   where the words matter, who said it and the chronology event it rests
   on; the rights advisements; the questions put before rights; the
   searches, seizures and force; the statements that matter; the gaps; the
   outcome. Its template, Memo facts sheet, is on the Templates page.
2. **The app checks the sheet.** Every time is looked for inside the
   incident's span and marked when it is not; every quote is looked for in
   the record word for word and marked verbatim or not; the timeline is
   put in time order and the sheet is marked when its last moment falls
   more than ten minutes before the last camera stops. Nothing is dropped;
   the figures are kept with the sheet.
3. **The memo.** The model writes the memo from the sheet alone, with the
   Incident memo template: the cameras line, the office's About and the
   sheet as text are all it is given. It cannot copy the record because
   the record is not there; a quote the sheet marks as not found word for
   word is given without quotation marks. A memo cut at its cap goes on
   from where it stopped (v1.90.1).
4. **The sheet is kept with the memo**, shown on the Memo tab under a fold
   with its times as citations, and printed in the Word export between the
   memo and the Chronology, so an attorney sees what the narrative rests
   on and can ask for more. **Rewrite from the sheet** runs the second pass
   alone, while the chronology and the cameras are as they were.

## Consequences

- Two engine calls where there was one; the first costs what the memo
  cost, the second is small (a few thousand tokens in, the memo out).
  Rewriting the memo's text becomes cheap.
- The memo can only say what the sheet holds. The sheet is therefore
  generous by instruction (forty to one hundred and twenty moments), the
  app says when it stops early, and it is visible and exportable.
- Quotes gain a check they never had: the app says which are in the record
  word for word.
- The Facts sheet answer cap (8,000 tokens) joins the Incidents page; the
  memo's own cap stays for the second pass. One migration (0063) adds the
  sheet and its cut mark to the memo's row; memos written before it carry
  an empty sheet and read as before.
- The record, the chronology, the Digest, the comparison and the chats are
  untouched.

## Alternatives considered

- **Keep one pass and tune the wording further**: two rounds showed the
  ceiling; the model copies whatever the wording says.
- **A larger answer cap**: it lets the copying run longer.
- **Strip the labels from the record before the call**: hides one symptom;
  the folded parts and the trailing story remain.
