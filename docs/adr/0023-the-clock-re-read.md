# 23. The clock re-read: a squeezed block is placed again by the audio, and the Preview of a voice is a snippet

Date: 2026-10-22. Status: accepted. Release: v1.152.0; decision 2 amended
in v1.152.1 (the window is read in pieces). Amends ADR 0022 (its decisions
2 and 6 give way to this one; the rest stand).

## Context

ADR 0022 marked a block of lines the recogniser placed early and moved
nothing. On the day it reached the server the maintainer read the marked
stretch of the same jail call against the audio: the line the page put at
2:05 was spoken at about 2:21, and a short line the page also put at 2:05
was spoken at about 2:13. Measured read-only on the server, the block of
lines ran on the page from 2:05 to about 2:22, and the hole the audio
filled ran from about 2:22 to about 2:38. So the recogniser had squeezed
about thirty-three seconds of talk into the first seventeen: a line early
in the block was eight seconds early, a line late in it sixteen. Shifting
every line by the hole's length would put the first line sixteen seconds
late; stretching the block evenly would leave it where it is. Neither
simple move matches the audio. Only the audio can place the words.

The marking was also too broad. ADR 0022 marked the whole run of lines
back to the previous long gap: on that call 280 of 433 lines, in blocks up
to six minutes long, where the recogniser's own window is about thirty
seconds. Most of those lines were in their place.

The maintainer's words: what is said should be attributed to the time it
was said, across the whole app; how the transcript handles it just needs
to match what the audio says; and nothing should break.

On the same walk the maintainer found the Preview of a person's voice
(the "hear" buttons of the guided page, the Case tab, the Voices place)
too much: it took the page's column with a whole other transcript, lines
from forty-five seconds before to ninety after and reading on as it
played, over the recording being reviewed. They want the snippet that
relates to the speaker, a couple of lines around it, cleanly.

## Decision

1. **The mark is narrowed to the squeeze.** Of a block that qualifies
   under ADR 0022's rules, only the lines whose clock lies within the
   recogniser's window before the hole's end are marked: forty-five
   seconds, a window and a half, the constant `SQUEEZE_SECONDS`. The
   line over a pause must be among them. The head of the block is the
   first marked line. Fewer pills, and only where the squeeze is.
2. **A marked block is placed again by the audio.** When a landing or a
   late pass marks any block, the app cuts that window of the prepared
   audio (from a second before the first marked line to half a second
   after the hole's end), sends it to the WhisperX service as small jobs
   of its own (the recording's task, model and language, no speakers, the
   same vocabulary, priority with the speakers pass, behind a Live
   recording's stretches), **in pieces cut at the audio's own pauses**
   (v1.152.1: the first build sent the window whole, and on the office's
   call the second reading repeated the first reading's error, because
   Whisper writes its own rough stamps for each utterance and the word
   fitting is trapped inside them; a probe reading of the gap alone found
   the block's words there, the long saying starting at 2:21 as the
   maintainer heard it; a piece a few seconds long, none shorter than two
   seconds and none longer than twelve without a pause in it, cannot carry
   words across a pause), and when the pieces' readings come back, read
   together in time order, matches their words against the lines it
   already has (a sequence match on the
   words, punctuation and case set aside). A line at least half of whose
   words are found takes its clock from where those words were heard,
   the first found word's start to the last's end, the order of the lines
   kept and no line put before the one above it. The words, the speaker,
   the label, the corrections, the notes and the proposals on the line
   stay as they are; the words' own times move with the line. A line the
   reading cannot find keeps its clock and its "clock unsure" pill. The
   mark on a re-timed line keeps the old clock (`was`) and the shift, so
   the pill can say what happened and a later release can undo it.
3. **The re-read is not a Job of the Queue.** It is a background pass
   kept in the Transcript's provenance (`clock_check.reread`: waiting,
   done or failed, with the service's job ids while they are out), polled
   by a task of its own every ten seconds and given up after half an
   hour. A recording's state, its Queue row, the "being replaced" rule
   and the one-live-Job rule all read the Queue's Jobs, and none of them
   should see a clock re-read: nothing is being transcribed again. The
   service's own line orders the small jobs with everything else. A
   re-read that fails leaves the marks as they are; nothing on the page
   depends on it finishing.
4. **A re-timed line is a sure line.** The voice step measures it, it may
   be a Sample, the "hear" buttons and the Preview may seek to it; the
   dotted rule stays on the block and the pill at its head says "clock
   re-read · was 2:05". Every place that read "unsure" reads one helper
   that says whether a mark still means doubt.
5. **One audit row per re-read**, "Clock re-read", with the lines moved
   and the lines left; no word, no time, no name.
6. **The Preview of a voice is a snippet.** Opened with a person (the
   "hear" buttons, a tab, a sample), the Preview shows the person's head
   as before and under it the snippet alone: the line heard, one line
   before and one after, the player starting half a second before the
   line and stopping half a second after it (or at the end of the hole on
   a marked line), the samples as the row of plays; it reads no further
   lines and never scrolls on. On the guided page the context column
   stays beside it rather than giving way. Open the recording stays for
   the whole. Opened from a citation or a search hit, with no person, the
   Preview reads around the moment as before.

## Consequences

- No migration: the mark is the JSON field of 0088 with three more keys.
- Each marked block costs the service one small job, a few seconds of GPU
  on a window under a minute long; on the measured call, seven jobs.
- The transcript's clock can now change after it lands, by the audio's
  word only, by at most the hole's length, and visibly. Exports, Clips
  cut later, Samples, the Preview, Search hits and citations made after
  the re-read agree with the audio; a Clip cut before it keeps the times
  it was cut at.
- A later release may undo a re-read from `was`, or re-read a block
  whose first pass failed, by hand from the page; both are named here
  and not built.
- ADR 0022's measurement and rules stand; only its "nothing moves" gives
  way, to the audio.
