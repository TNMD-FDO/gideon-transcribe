# Naming speakers and correcting them from the words: what is published

Read on 2026-10-02 for the Speaker check and Suggest names (Phase 5
chapters 1, 3 and 4; v1.105.0). Two of the papers were read in full (the
LIMSI study and the LREC workshop paper); the rest through their abstracts
and web versions, so their figures are as reported there. Each entry has
the URL it was read from.

One limit applies to almost all of it: the benchmarks are two people on a
telephone, in English. A body camera with seven voices talking over each
other is harder than anything measured here.

## Naming a speaker from what is said

**A name's direction is known, and has numbers.** Canseco-Rodriguez, Lamel
and Gauvain, "Towards Using STT for Broadcast News Speaker Diarization"
(LIMSI, 2004), https://www.cs.columbia.edu/~julia/papers/limsi04.pdf.
From 150 hours of transcribed broadcast news they sorted name patterns into
three classes: the name of who is speaking ("I am ...", "this is ..."), of
who will speak next, and of who just spoke ("thanks ..."). On about nine
hours they had not seen:

| The pattern names | Wrong |
|---|---|
| The speaker themselves | 0.8% |
| The next speaker | 16% |
| The previous speaker | 34% |

Only about a tenth of segments carry any pattern. In "thanks [name]" the
name "refers to the person who is not speaking". Their commonest errors
were a name that belonged to a third party and an ambiguous greeting.

**A model trained for the job gets one name in five wrong.** Nguyen and
others, "Identifying Speakers in Dialogue Transcripts: A Text-based
Approach Using Pretrained Language Models" (Interspeech 2024),
https://arxiv.org/abs/2407.12094. Precision 80.3%, recall 50.0%; many
speakers are never named in the talk, which caps what any method can find.

**Who is being spoken to is hard for a model.** Inoue and others, "An LLM
Benchmark for Addressee Recognition in Multi-modal Multi-party Dialogue"
(IWSDS 2025), https://arxiv.org/abs/2501.16643v2. An explicit addressee in
about a fifth of turns; GPT-4o "only marginally above chance" at naming the
addressee in three-party talk.

*What the app takes from it (v1.105.0):* a self-introduction is kept as the
engine rated it; a name a speaker calls someone by is never their own; a
name someone was called by is the other party's with two speakers and a
judgement with three or more, so the app keeps it at medium.

## Moving lines between speakers

**An untrained model correcting speakers makes them worse.** Wang and
others, "DiarizationLM: Speaker Diarization Post-Processing with Large
Language Models" (Google, Interspeech 2024),
https://arxiv.org/html/2401.03506v5: zero-shot, the word diarization error on
Fisher rose from 5.32% to 11.96%, one-shot to 16.58%; fine-tuned it fell to
2.37%. Untuned models "often delete big chunks" of the text. Efstathiadis
and others, "LLM-based speaker diarization correction: A generalizable
approach", https://arxiv.org/html/2406.04927v3: the same with open models,
and a fine-tuned model helped only on transcripts from the tool it was
tuned on. Both: two speakers, telephone, English.

**Words alone over-correct; the voice has to have a say.** Paturi, Li and
Srinivasan, "AG-LSEC: Audio Grounded Lexical Speaker Error Correction"
(Amazon, Interspeech 2024), https://arxiv.org/html/2406.17266v1: text-only
correction "over-corrects to a lexically more plausible yet incorrect"
speaker; errors gather around speaker turns and overlaps; grounding in the
diarizer's own speaker scores raised errors corrected from 29.2% to 44.5%
and cut errors introduced from 8.4% to 6.6%. "SEAL: Speaker Error
Correction using Acoustic-conditioned Large Language Models" (2025),
https://arxiv.org/html/2501.08421v1: the voice confidence is given to the
model as the labels low, medium and high, since models handle labels
better than numbers, and the output is constrained so no word can change;
24 to 43% relative improvement. Park and others, "Enhancing Speaker
Diarization with Large Language Models: A Contextual Beam Search Approach"
(NVIDIA, ICASSP 2024), https://arxiv.org/pdf/2309.05248 (its abstract only): acoustic and
lexical evidence decoded together, up to 39.8% relative improvement.

**This app's stack, with a role pass, on interviews.** Coats, "MD_NLP:
Reconstructing an Australian English Heritage Dialect Corpus from the
Mitchell-Delbridge Recordings through LLM-Assisted Speaker Attribution"
(LREC 2026 workshop),
https://cc.oulu.fi/~scoats/LREC_2026_workshop_MD_NLP_final.pdf. WhisperX
large-v3 and pyannote community-1, then an untrained model told only that
the interviewer asks and the pupil answers, roles kept consistent per
label: turn accuracy from 62.70% to 95.68%. Measured on ten recordings,
185 turns, one annotator, two speakers. Its example shows the diarizer
giving a short question to the speaker of the answers around it.

**A person's correction can teach the rest.** "Interactive Real-Time
Speaker Diarization Correction with Human Feedback" (2025),
https://arxiv.org/html/2509.18377v1: each human fix enrols that voice and
later lines follow (speaker confusion down 44.23% on AMI), and merged
segments must be split first or the voice learnt is a mixed one.

*What the app takes from it (v1.105.0):* the check proposes and never
rewrites, which the untrained-model results make a requirement; every
proposal gets a second, blind reading and is kept in front of the person
only where two readings agree; the voice step's own word labels, which the
app already stores, are given to that reading in words and set aside a move
off a long line the voice was firm on. Not taken: fine-tuning (no labelled
data, and the engine is shared), per-line acoustic scores and voice
enrolment (the pinned service and the rule on stored voice data; a decision
for the maintainer).

## The measure

Every one of these papers scored against speech labelled by ear; one made
do with 185 turns. The office has no such reference: the one made on
2026-09-24 was lost twice to reprocessing. From v1.105.0 the person's own
Accept and Dismiss, counted among the proposals the second reading backed
and those it set aside, are the measure. They say whether proposals are
right; they do not count the wrong lines the check never proposes, which
needs a by-ear pass over ordinary lines.
