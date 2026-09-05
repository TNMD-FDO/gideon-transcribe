# Speaker suggestions: what the evidence says, and what to do with the feature

Read on 2026-09-05, after the first trials of Suggest names against the Local
engine (Qwen3.5-4B) on a body-worn camera recording with five unnamed
speakers gave, in the maintainer's words, "a terrible job identifying".

## What the feature asks the model to do

From the transcript text alone, for each speaker still wearing the app's
label, propose a name if someone says it or is addressed by it, otherwise a
role (Officer, Caller, Interpreter), with the line it drew on and a
confidence; the app keeps only high or medium, drops labels, unknowns and
names already held, and a person accepts or rejects each one. No voice
biometrics: speaker embeddings are neither requested nor stored, by the
chapter's rule and for good reason in a defender office.

## What the literature covers, and does not

- **Roles, with fine-tuning, in one domain.** Speaker role identification in
  clinical conversations reached 82 percent accuracy from text alone and 95
  percent when the diarization identifiers were added, with fine-tuned models
  (BERT, decision trees) on 117 transcripts and 27,505 utterances of labelled
  data. All models were fine-tuned; the paper says so plainly and does no
  zero-shot work and no naming of individuals. The signals that carried the
  roles were pronoun patterns ("you") and role vocabulary.
- **Diarization correction, with fine-tuning.** Fine-tuned LLMs "can markedly
  improve diarization accuracy" as a post-processing step, and a model
  fine-tuned on one ASR's output did not carry to another's without an
  ensemble. The same line of work reports that zero-shot models did worse than
  the baseline for lack of adaptation to the task.
- **Naming individuals from text.** Not thoroughly studied: the survey
  material notes that LLMs show a capability to autofill speaker names and
  roles but that it "has not been thoroughly studied or evaluated due to lack
  of relevant training and testing datasets". The one recent system that names
  speakers (SpeakerLM) does it from audio embeddings of registered voices, not
  from what is said.

So: roles are tractable with a fine-tuned model and labelled data; names from
text are an open problem; nothing in the literature supports a small model,
zero-shot, over a 25,000-token transcript, which is what the Local engine is
being asked to do.

## Why the trials went as they did

- A 4B model's recall over a long context is weak; the AI assistant chapter
  itself notes long-context recall of 66.4 percent at 128K on a larger model.
  Asked to weigh a whole transcript, a small model reaches for the nearest
  shape: the labels it was given (the first trial), or a repeated entry until
  the cap (the second).
- Body-worn camera footage rarely names anybody; the only honest answers are
  roles, and a role needs a judgement about who is doing what, which is
  exactly the kind of reading a small model does least well.
- Self-reported confidence is poorly calibrated in any model; "high" from a
  4B model means little, so the high-or-medium filter keeps most of what it
  says.

## What would make it work better, if it is wanted

1. **Evidence first, then the mapping.** Have the model (or plain rules) list
   the name mentions and forms of address in the transcript with their line
   numbers: "This is X" (a self-introduction, which names the speaker of that
   line), and "X, ..." or "..., X" at the edge of a turn (a vocative, which
   names the other party in a two-way exchange). Then map labels to names from
   that evidence, with the type of evidence as the confidence, not the model's
   opinion of itself. This is a smaller, checkable task, and the reason shown
   to the person is the evidence itself.
2. **A larger model.** The office's shared 27B engine is the model the chapter
   was written against; the same prompt will do markedly better there, and
   `./transcribe engine` switches to it when the key arrives.
3. **Measure before trusting.** The Accept and Reject audit rows are a running
   hit rate; a handful of the office's own recordings with known speakers,
   read once by a person, would show whether the feature earns its place.
4. **Roles from a fixed list per recording type**, chosen by the Admin
   (Interview: Interviewer, Interpreter, Suspect; Jail call: Caller, Called
   party; Body-worn camera: Officer, Suspect, Witness, Passenger), would give
   the model a small choice rather than an open one.

## Recommendation

Keep the feature, but off by default: the Speaker suggestions toggle already
exists on the AI assistant settings page, and its default moves from On to
Off, so a new install does not offer a feature that a small engine does badly.
An office with a larger engine turns it on in one click. Revisit with the
evidence-first method and the shared engine, measured on the office's own
recordings, before making it default On again.

## Sources

- https://pmc.ncbi.nlm.nih.gov/articles/PMC12952674/ (Speaker Role Identification in Clinical Conversations: 82% text-only, 95% with diarization ids, fine-tuned, 117 transcripts)
- https://arxiv.org/abs/2406.04927 (LLM-based speaker diarization correction: a generalizable approach; fine-tuned LLMs "markedly improve"; ASR-specific models did not carry over)
- https://dl.acm.org/doi/10.1016/j.specom.2025.103224 (the same, as published in Speech Communication 170; the search summary reports zero-shot models did worse than baseline)
- https://arxiv.org/html/2508.06372v1 (SpeakerLM: speaker naming from registered audio embeddings, not from text)
- https://arxiv.org/pdf/2401.03506 (DiarizationLM: LLM post-processing of diarization output)
