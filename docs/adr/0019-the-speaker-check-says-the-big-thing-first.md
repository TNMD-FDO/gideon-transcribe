# 19. The Speaker check says the big thing first, and the second reading is retired

Date: 2026-10-07. Status: accepted. Release: v1.128.0.

## Context

Phase 5 chapter 3's Speaker check proposes, line by line, the lines whose
words show they belong to another Speaker, and a person accepts or
dismisses each. On 2026-10-02 (v1.105.0) every proposal gained a blind
second reading: read twice more without the first answer and with the
line's label hidden, backed when both readings agreed, otherwise set
aside under a fold, nothing dropped. The voice step's word labels were
given to the second reading as a note.

On 2026-10-07 a run on the office's server read a transcript of 522 lines
under six labels and proposed 179 moves. The second reading backed one and
set aside 178, 58 of them as too short to judge and 120 because it kept the
line where it was; 18 of the set-aside moves had the voice step hearing the
other Speaker in the line. The moves clustered: 58 lines of one label read
as a second label's, 24 of another as the same second label's, 20 as a
third's; grouped into runs of the same move close together they made 70
runs, the largest 25 lines. The maintainer found the page convoluted ("1
suggested correction and 178 optional") and asked for something simpler,
then asked whether simpler meant accepting too much inaccuracy.

## Decision

1. **The second reading is retired.** A gate that passes 1 in 179 and
   overrules the one evidence that is not fooled by words (the voice step)
   is not a gate; it is a fold with the whole check inside it. The fields
   that kept it (`second`, `aside_why`, `second_look`) stay, empty or
   repurposed, so nothing migrates; its prompt pieces are removed.
2. **The voice step is the one measure.** Each correction keeps what the
   voice step heard on its line: two voices (the other Speaker inside the
   line), one voice (every word of a long line given to the labelled
   Speaker), or silent (a short or untimed line). Said in those words on
   every card; never a score.
3. **The big thing first.** When a share of a label's lines read as one
   other Speaker's, the page shows one Speaker card, not the lines: the
   share as a bar, the voice's note, three moments to hear and one of the
   label's own, and Merge as the primary button only when a clear majority
   of the lines and the voice step agree. Below that bar the card
   describes, asks for a listen, keeps Merge quiet ("after listening"), and
   offers Not the same. A card the voice step argues against offers no
   merge: merging against the voice is how a real person vanishes.
4. **Then the stretches.** The remaining moves are grouped into runs
   between the same two Speakers close together, one card each, accepted
   or dismissed at once, the voice-backed first; Accept all becomes Accept
   every voice-backed stretch, so the one-press path never moves what the
   voice argued against. Nothing is dropped and nothing moves until a
   person says so; Undo reverses a merge or a stretch as it does a hand
   move; Check again reads the merged transcript afresh.

## Consequences

- A transcript the engine split into too many labels is mended in a few
  presses rather than a few hundred, and the person's judgement goes
  where it is worth most: on whether two labels are one voice.
- The thresholds are the build's starting figures, to be read against the
  office's recordings by ear, as the check itself was in September and the
  names in October; they move in code, not in the Panel, until the office
  has reason to want them there.
- The office's measure changes shape: no longer accepted among the
  backed against the set aside, but accepted against dismissed, card by
  card. The second reading's figures in the audit rows end with v1.127.1.
- Not built, and still the maintainer's to decide: per-line acoustic
  scores or voice prints from the service, and splitting a mixed line at
  the word.
