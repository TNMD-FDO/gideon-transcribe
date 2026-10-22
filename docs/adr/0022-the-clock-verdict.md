# 22. The clock verdict: the transcript's clock is checked against the audio, marked, and never moved by the app

Date: 2026-10-22. Status: accepted. Release: v1.151.0.

## Context

On 2026-10-22 the maintainer, listening to one of the office's jail calls
on the guided Speakers page, found a line that read 2:05 on the page and
was spoken at about 2:21. Measured against the audio's own energy on the
server (ffmpeg's silence detection on the prepared audio the recogniser
had been sent), the transcript had a hole of twenty-one seconds where the
audio had speech, then a block of seventeen seconds of lines, then another
hole of sixteen seconds that was fourteen seconds of sound. Two lines
inside the block claimed words across pauses the audio showed. Slid
forward by the length of the hole after it, the block fitted exactly, up
to the next line. The words and the speaker proposals were right; the
block was sixteen seconds early. The same shape appeared nine times
across the call, and twenty-nine of its hundred and ninety-nine longer
lines spanned an audio pause.

The cause is the recogniser's chunking: WhisperX cuts the audio by voice
activity, Whisper writes the words of each chunk, and the aligner places
every word inside its chunk's window. When Whisper writes words for only
part of a chunk, which noisy phone audio and long holds invite, the
aligner spreads what it has from the start of the window. The recogniser
reports no doubt about this; only the audio does. The "timing is a guess"
mark of v1.141.0 catches thin and repeated lines, not a shifted block.

The clock reaches every place a moment is played: the transcript, the
Samples, the guided page's line screen, the "hear" buttons of a Sounds
like, the Preview from the picker, the chat and the search, and the voice
step, which measures a line's voice on the audio between its clock and
its end. A shifted block therefore mis-plays, mis-samples and teaches a
wrong voice.

## Decision

1. **The verdict is a fact of the Transcript.** As every Transcript lands,
   after the Call system's pass and before the Speaker check, the audio's
   pauses are measured once on the prepared audio and held against the
   lines by three rules: a hole (eight seconds or more with no line) that
   the audio fills with sound for over seven tenths of it; a line of two
   seconds or more whose words are said to run across over a second of
   quiet inside it; and a block of lines (the run between two long gaps)
   that has such a line and a sound-filled hole after it is marked "the
   clock here may be off by up to N seconds", N the hole's length. The
   mark is kept on each line of the block (`Segment.clock`); the counts go
   in the Transcript's provenance; no audit row is written. The thresholds
   are the build's constants from the shape measured on the office's call
   and move only if a judgement sheet, by ear, on a local page, says so.
2. **Nothing moves and no word changes.** The app never rewrites a line's
   clock. A marked line keeps its time; the mark says where to listen.
3. **Every player reads the mark.** A marked line plays a wider window,
   from half a second before its own clock to the end of the hole beside
   it, and says so; the transcript draws the block with a quiet rule and
   one pill at its head; the guided page's line screen shows the window,
   the line's clock and where the sound is; the Preview seeks to where the
   sound is and names the verdict; the "hear" buttons and the picker's
   plays choose a line whose clock is sure while any remains.
4. **The voice step gives a marked line no vector.** It is never a Sample,
   never teaches a print on the recording or in the unit's book, and
   rates no match. The words' reading stands.
5. **Older transcripts get the verdict once**, when a Speaker check runs
   on them, the way the Call system's pass was given later; a transcript
   whose prepared audio is no longer on disk is left as it is.
6. **Sliding a block to the sound is left for later.** Moving a marked
   block into the hole beside it, by its own length, with its words
   re-aligned there, would change the transcript's clock. It is decided
   on its own, with the measurement behind it, after the marks have been
   lived with on the office's recordings.

## Consequences

- One migration (0088): a nullable JSON field on the line.
- The landing takes one ffmpeg pass over the prepared audio per Side, a
  few seconds on a half-hour call, before the check is queued.
- The pages say "clock unsure" in plain words and never pretend to a
  precision the audio denies; a user who hears a saying later than the
  page says now reads why on the page itself.
- The Preview's redesign (the same release) carries the verdict as a
  pill, so the one place a person's voice is heard from another recording
  tells the truth about where that voice is.
- The recogniser's stack stays pinned; nothing here changes how words are
  recognised, and the research pin stands.
