# Event spotting: the proposer measured before v1.64.0

Written 2026-09-19 for Phase 7 chapter 2 (`docs/spec/SPEC-PHASE-7.md`),
from three runs of the proposer over the one camera on the maintainer's
server whose record carries "I got, I got gun, I got gun" at 4:30 and
which the v1.61.0 run had left unproposed. The camera is 47 minutes long;
its record (the Digest, a condensation of its words and its picture) is
428 lines. Every run used the office's engine (GIDEON's vLLM service, the
`gideon-generator` model), thinking off, the suggestions' deterministic
sampling, a 2,000-token answer cap. The scripts are in the session's
scratch folder, not in the repository; the numbers are what matter.

## A. The v1.61.0 ask, one call over the whole record

| Proposals | Cut short | Mentions the gun | Narrates the picture | Time |
|---|---|---|---|---|
| 22 | yes | 0 | 4 | 48 s |

The engine quoted the record line by line ("Speaker 8 said, ...") and
narrated the picture ("The camera view shifts to the interior of a moving
vehicle") from the start until the cap cut the answer at 2:50 into the
recording. The gun line at 4:30 was never reached. This is the failure the
maintainer saw: judgement and verbosity, not reading.

## B. The chapter's first draft: an investigator's ask, ten-minute windows, a second look

| Proposals (first look) | Second look added | Cut short | Mentions the gun | Narrates | Time |
|---|---|---|---|---|---|
| 55 | 30 | 4 of 5 windows | yes, at 4:30 with a reason | 0 | 244 s |

The windows and the ask found the line ("Indicates the discovery or
presence of a firearm") and stopped the narration, but the engine still
copied the record's lines as the event text and proposed nearly every
line, so four answers of five were cut and 85 proposals is far too many.

## C. The ask tightened: own words, the first words of the line, at most twelve a stretch

| Proposals (first look) | Second look added | Cut short | Mentions the gun | Narrates | Copies the record | Rests on verified | Time |
|---|---|---|---|---|---|---|---|
| 31 | 0 | 0 | yes, at 4:30 | 0 | 0 | 31 of 31 | 70 s (10 calls, 2,856 output tokens) |

Sample, at 4:30: "An officer shouted, 'I got, I got gun, I got gun.'" with
the reason "Indicates a weapon was found or perceived, which is critical
for justifying the stop and search." Others: "A person on the ground
stated, 'I'm not resisting.'" ("Directly contradicts any later claim of
resistance"), "An officer stated, 'You got shot.'" ("Indicates a gunshot
wound"). The second look answered an empty list in every window at about
one second a call; it costs little and stays as a switch for the cases
where the first look skims.

This is the shipped wording (`app/core/prompts.py`, `INCIDENT_EVENTS`,
`INCIDENT_EVENTS_FORMAT`, `INCIDENT_EVENTS_SECOND_LOOK`). The last two
windows of this camera answered with nothing on both looks where B had
found biographical questions and transport talk; that is the judgement
the ask now asks for, and the office's context and the Look for box are
the way to shift it.

## What the watch phrases add

The search is the app's own and needs no engine: on this camera it finds
the gun line by the word alone, and would have in v1.61.0. It is the floor
under the judgement, not the finder; the chapter's principle 5 says why.
