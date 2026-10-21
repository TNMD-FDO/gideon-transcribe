# 21. The voice step hears the recording, and the Case remembers a voice only when told

Date: 2026-10-19. Status: accepted. Release: the voice plan's V1 to V4;
V1 (decision 4, the Call system) landed in v1.138.0, V2 (decisions 1 to
3 and 5, the voice step) in v1.139.0, V3 (decision 6's one run and
decision 7's Also called) in v1.140.0 and V4 (Voice prints, decision 6)
in v1.144.0 behind the Admin's switch, Off as shipped.

## Context

The Speaker check (Phase 5 chapter 3) reads words. Its one voice measure
is the diarizer's word labels read back (`voice_of`): the voice step heard
the other Speaker inside the line, or gave every word of a long line to the
labelled Speaker. Nothing in the app can say how sure the voice step was of
a line, or whether two lines are the same voice. Phase 5 chapter 2 reserved
Voice prints with rules and no embedding step; chapter 3's Principle 3
forbids the check to add a Speaker; Phase 9 chapter 2's rule names one
Person on a Side of every call in a Case.

On 2026-10-19 the office measured a speaker verification model,
NVIDIA's TitaNet-large, on three of its recordings against the
maintainer's ear, on a local page that never left the building
(`docs/research/speaker-verification.md`). The diarizer's labels were wrong
on a quarter of the judged lines of two jail calls and a fifth of a body
camera's; the words-only check was right on 3 of 26 judged proposals; the
voice was right on 85 to 100 per cent of the lines it spoke on, and spoke
on a third to two thirds of lines depending on how a Speaker's voice print
was built; a print cannot split a label that holds two people, and
clustering within the label found the one real case, a phone passed from
hand to hand. The model loads through the NeMo commit the diarizer image
already pins, in 0.4 s, under 0.3 GB of card memory.

The maintainer read the counts and took the recommendation, then accepted
the words and the switches below on the same day.

## Decision

1. **The diarizer container gains a second duty**, `/v1/voices`: one
   vector per stretch of the prepared audio and one per label, from
   TitaNet-large loaded through the NeMo commit the container already pins.
   Its weights go in `models.yaml` by revision, fetched at install and
   offline afterwards; its licence (CC-BY-4.0) is attributed as pyannote's
   community-1 is. No new container, image or model server; nothing is
   stored in the container; the service version moves.
2. **The voice judges every proposal and makes its own.** For each line
   the voice step says agrees, against or cannot tell, calibrated on the
   recording's own lines. A Speaker's print on a recording is the mean of
   every line of its label of two seconds or more, outliers dropped and the
   mean re-taken until it settles. The floor under which the voice says
   cannot tell is a setting per Recording type, 1.5 seconds as shipped. A
   proposal the voice is against is shown as such and never in the
   one-press path. The voice may propose a move the words never made,
   under a cap per run.
3. **A Hand-over is a finding, and a person's Yes to it adds a Speaker.**
   Two or three voices within one label, apart by the recording's own
   measure and separated in time, not differing mainly in loudness, are
   proposed as a question with the moment to hear; Yes splits the label at
   that time into a new Speaker. This amends chapter 3's Principle 3: the
   check still never merges on its own and never touches a word, but it
   may propose a split that a person makes.
4. **The Call system is a Speaker, never a person.** On a jail call the
   prepaid-call system's recorded voice is a Speaker of its own, found by
   a shipped, editable list of phrases and, with the voice step, by
   sounding unlike every party. Its lines keep their own label; it has no
   Role, no name and no print anywhere; the check and the names never see
   it; the Side rule names the party and never the system; the memo says
   "the call system announced".
5. **Vectors live on the run, not the Transcript.** The voice step's
   vectors are deleted when the check is done. Nothing of a voice is kept
   past the run unless decision 6 is on.
6. **Voice prints come into force as chapter 2 wrote them**, with three
   additions: a print is learnt from acceptances only and refined by each
   recording a person accepts a match on; grouping and naming are two acts
   recorded apart ("this voice is the same as that Speaker"; "that Speaker
   is this Person"), so a wrong name is one rename and a wrong grouping is
   one unlearn; and **Unlearn** deletes the Person's print and returns every
   Speaker it matched to unnamed and marked. The Admin's switch, off by
   default; turning it off deletes every print and the page says so first;
   never across Cases; content, never logged or exported; "Sounds like",
   never "is"; a print taught by one recording rates no higher than medium.
7. **The label is the Person's name.** Also called (the names people use
   for a Person) and Also heard as (the engine's spellings) are ways to
   reach the Person and reasons on a card; neither labels a Speaker and
   neither rewrites a word. Also called goes to recognition as vocabulary,
   to the name rules, to Search and to Gideon; Also heard as never goes to
   recognition.
8. **Each release ships with its switches off and changes nothing for an
   office that leaves them off.** A switch off is the way back; a removal is
   a forward release, as ADR 0019 retired the second reading.

## Consequences

- Four releases in the plan's order: the Call system (V1), the voice step
  (V2), one run of the Speaker check with Suggest names as a part of it,
  automatic as the Transcript lands or overnight (V3), and the Case
  remembering (V4). Each is gated on the suite green both ways, a trial on
  the server before any wording ships, a browser walk, a server upgrade and
  a ledger line. V1 before V2 because a print taught from a call before the
  carve-out is half synthetic; V2 before V3 because names rest on
  separation; V3 before V4 because the Case's tab has nothing to show until
  names exist.
- The voice step ships switched on per Recording type for the kinds the
  measurement passed and off for the rest; an office turns a kind on after
  watching. Two measurements are still owed before the body camera's switch
  ships on: the curve by condition (quiet, noisy, distant, radio under it,
  shouting, overlapped), and a second call where both parties speak at
  length, for the cross-call print.
- The glossary gains Call system, Also called and Hand-over; the run keeps
  the name Speaker check. Phase 5 chapters 2 to 4, Phase 9 chapter 2,
  Phase 4's memo rules and Phase 1's two-channel call rule are amended;
  `docs/whisperx-api.md` gains the voices request; the settings catalogue
  gains the voice step's rows. The box ledger's Transcribe line grows by
  under a gigabyte of card memory in the diarizer container.
- A Voice print is biometric data about a client, a witness or an officer.
  Chapter 2's rules, this record and the Admin's switch make keeping one the
  office's choice, and Unlearn makes it reversible; the Call system's voice
  is kept nowhere, since phrases and "unlike every party" do its work.
- Not decided here, and never by default: accepting voice-backed moves by
  themselves (V5, an office switch after months of watching); Accept all
  for names or matches; prints across Cases; any print from the picture.

**Noted 2026-10-19, later the same day.** The pages were drawn and the
maintainer chose review as reading (`docs/spec/mockups/phase-5-review-as-reading.html`):
the run's output shown as a proposed version of the transcript with each
change in place and its three sounds, one primary button for the changes the
voice backs, names accepted one at a time on their cards. Decision 2's floor
and cap are the build's constants rather than Panel settings, and the Panel
gains three rows in all (Voices help the check, Remember voices across a
case, Call system phrases), at the maintainer's wish for no overlapping
settings.

**Noted 2026-10-21, at V4's build (v1.144.0).** The pages were drawn
(`docs/spec/mockups/phase-5-voice-prints.html`) and chosen: Sounds like,
the conflict and the Side rule's alarm are accepted on the recording's
Speakers page card, with the Person's voice to play beside the card's own
samples; the Case's Speakers tab is an overview (the Voice column with the
chain, what waits and where, Decided so far) and the home of Unlearn.
Decision 5 is amended by this: while the switch is on and the recording is
in a Case, the run keeps one vector per Speaker label (the label's print on
that recording) so a Speaker named later teaches its Person's print; the
per-line vectors still go when the check is done, and the switch going off
empties the label vectors with the prints. The rating's three links are
build constants (a cosine of 0.65 for high and 0.50 for medium, raised to
the run's own midpoint between same-voice and other-voice scores where
that is higher; 0.35 and under for the Side alarm; a print from one
recording and a voice heard for under ten seconds each cap at medium).
The same day the maintainer asked for prints beyond one case for the
people the office meets again and again (officers on body camera and in
interviews), switchable from the Panel, with a manual check against the
known voices inside a case, a place that shows the prints, and two units
(read from the directory's OUs) that never see each other's prints. That
is a change to "never across Cases" and is decided in its own record when
it is drawn and built (V4b, the unit's voice book); this release carries
only the hook: a scope on the print, always "case", and a reserved mark
on the Person, always off.

**Noted 2026-10-21, later (v1.145.0, voices first).** Reading the test_2
call back (202 proposals from the words on 573 lines, six checks and four
reprocesses, the call fixed by naming voices: one Sounds like settled 167
proposals) showed the run upside down: the words ran first and loudest on
labels, the voice only commented, and naming came last though it did the
work. The run is turned over where the voice listens (decision 2's per-type
switch): the voice's work and the names at arrival with no engine call for
moves; the lines in doubt from the voice alone (near another print, cannot
tell, two voices in one line); three stages on the page; the engine asked
twice and only after the names, narrowly about the lines in doubt at stage
2 and once over the whole call at stage 3. The name suggestions become
hints on the cards (the maintainer: usually wrong, but they tell you who is
who), never an Accept of their own. A mixed line is split at the word, with
Undo. Where the voice is off for the type the words-first run stands as
written above. Drawn in `docs/spec/mockups/phase-5-voices-first.html`.

