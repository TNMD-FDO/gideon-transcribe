# Gideon Transcribe, Phase 5 specification

The Speakers release, published as `v1.50.0`.

## About this document

This is the build specification for Phase 5 of Gideon Transcribe: managing Speakers as a job of its own. A Transcript arrives with its Speakers labelled by the engine, Speaker 1 and Speaker 2 and on, and someone has to listen and say who each one is. Phase 1 gave that job a strip at the head of the Transcript and Phase 4's releases a window beside the page; the maintainer asked on 2026-09-12 for "more of a suite": a page whose one job is turning the engine's Speakers into people, with the Transcript in view while it happens. It builds on Phase 1 (`docs/spec/SPEC-PHASE-1.md`, the Transcript viewer and player chapter and the AI assistant chapter), Phase 2 (`docs/spec/SPEC-PHASE-2.md`, People and the Speakers tab), and Phase 4 (`docs/spec/SPEC-PHASE-4.md`), and changes nothing in them beyond what "What changes from earlier phases" lists.

Read it with the same companions: `CONTEXT.md` (the glossary, with the Phase 5 terms Speakers page, Lane, Sample, and Voice print), `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` (unchanged by chapter 1), and `docs/whisperx-api.md` (unchanged by chapter 1; chapter 2 will open its door for embeddings).

Nothing in this document is office-specific. No new environment key is needed and no new service. The conventions of the Phase 1 document apply here unchanged.

## What Phase 5 adds

- **The Speakers page** (chapter 1, v1.50.0): a page of its own for one Recording, reached by Manage speakers on the Speakers strip and left by Done, that plays the Recording, lists its Speakers as cards with three Samples each, shows a Lane per Speaker across the whole Recording, and keeps the Transcript's Ledger under them filtered to the Speaker in hand. Naming offers the Case's People first. Rename, merge, giving one line to a Speaker, Suggest names, and Undo all live on it. The Speakers window of v1.47.0 to v1.49.0 becomes this page opened in a window.
- **Voice prints** (chapter 2, a later release): the app recognising a voice it has heard before in the same Case, by sound rather than words, and offering the name first. Written here as the reservation the page keeps for it and the rules it will have to meet; not built, and the earlier phases' rule against embeddings stands until the chapter is amended into force.

Chapter 1 adds no admin setting, no audit row, no table, and no environment key.

## Contents

1. The Speakers page
2. Voice prints (deferred; the reservation and the rules)
3. Deferred and ruled out

Appendices: A. Audit rows added in Phase 5. B. Settings added in Phase 5.

## 1. The Speakers page

Written 2026-09-12 from the maintainer's ask ("treat any in depth speaker management as more of a suite... a separate window/function/feature set... I imagine they wanna see the transcript as well") and the answers to the build's questions the same day: the page serves a deliberate pass after processing and a quick fix while reviewing about equally; naming the Speakers is the first job; it is a full page of its own; and the Case's People are offered first. The layout is the maintainer's pick from the mockups, "the line-up with lanes": Idea 1 (cards down the left, the recording and the Ledger on the right) with Idea 3's Lanes folded in as the page's timeline.

### Principles

1. **One page, one job.** The page exists to say who each Speaker is. Everything on it serves that: hearing a Speaker, seeing where in the Recording they talk, naming them, joining two the engine split, and fixing a line given to the wrong one. It does not correct text, mark Clips, summarise, or chat; those stay on the recording page, one press away.
2. **The Transcript stays in view.** The Ledger under the Lanes is the viewer's own Ledger, the same rows in the same colours, so nothing about a line has to be remembered from another page. Follow keeps the line being spoken in view while the Recording plays.
3. **Both tempos.** A deliberate pass reads the progress line, works down the cards, and presses Done. A quick fix opens the page, picks one card, names it, and presses Done; nothing on the page has to be finished first, and nothing is lost by leaving.
4. **The Case's People first.** Inside a Case, naming offers the Case's People with their Roles before a free name, so the same officer gets the same name across the Case's Recordings without typing. Outside a Case naming is free-form, as Phase 1 has it.
5. **Nothing new is stored for it.** Samples, Lanes, the progress line, and the fragment hint are computed from the Segments the Transcript already holds. The page adds no table and no setting. Every change it makes is a change the viewer already makes, through the viewer's own routes, with the viewer's own audit rows and the viewer's own Undo.
6. **The engine is not asked to listen.** Chapter 1 recognises nobody by sound. Suggest names on the page is the Phase 1 feature, from the words, on request, one call per press. Voice prints are chapter 2, not built.

### Words

**Speakers page**, **Lane**, and **Sample**, as `CONTEXT.md` defines them. The page says "speaker" for what the glossary calls a Speaker throughout; the mockups' word "voice" is not used on the page. **Voice print** is chapter 2's word and appears on the page only as the reservation below.

### In and out

- **Manage speakers** on the Speakers strip of the recording page opens the page at `recording/<id>/speakers`. It replaces Tag speakers (v1.47.0 to v1.49.0) on the strip. The strip's fold, the chips, and the Speakers toggle stay as Phase 1 has them.
- The page opens at the recording page's playhead when it was opened from there, paused. Its own player has the sound from then on; the recording page, if it is still open in another tab, is not kept in step (see Open in a window for the arrangement that is).
- **Done** in the page's head returns to the recording page at the page's playhead, the way a citation from a Case page opens the viewer at a time. The browser's Back does the same without the time.
- **Open in a window**, beside Done, opens the same page in a window of its own, which is what the Speakers window of v1.48.0 was: the window plays the Recording, the recording page follows it through the browser's channel, and a change made in the window redraws the page's rows, exactly as the Transcript viewer and player chapter's Speakers window paragraph has it. The route `recording/<id>/window/speakers` keeps working and shows this page. In a window the head has no Done; closing the window is Done.
- The page needs a Transcript with Speakers. A Recording without one (not diarized, one Side) has no Manage speakers on its strip, and the route shows the recording page's "This recording has no speaker labels to tag" line with a link back.
- Standing is the viewer's: whoever may open the Recording may open the page, and a Collaborator acts on it as the owner does (Phase 2 Sharing chapter).

### The head

One line across the top: **Speakers of <title>**, the progress line **N of M speakers named** with a small bar (a Speaker is named when its name is not its engine label; on a Two-channel call a Side labelled by its Side alone counts as unnamed), the last change with **Undo** when there is one ("Undo: merged Speaker 4 into Ofc. Reyes"), **Suggest names** under the AI assistant chapter's rules (present only while Speaker suggestions is On, two or more Speakers are unnamed, and the engine passes the minute check, greyed with the unavailable line otherwise), **Open in a window**, and **Done**.

### The cards

Down the left, one card per Speaker, in the order the Speakers first spoke, which is the order of their numbers.

- **The head of a card**: the Speaker's colour dot, the name in bold (or the engine label while unnamed), the Role pill inside a Case when the Person holds one, a **named** or **unnamed** pill, and the engine label in small type at the right so a Provenance reference can be matched (the Exports chapter's Appearances table prints both).
- **The line under it**: how many lines, how long talking (the sum of the Speaker's Segment lengths), and the time of the first line: "44 lines, 5 min 03 s talking, first at 0:07".
- **Samples**: up to three play buttons, each labelled with its time. The Samples are chosen from the Speaker's own lines: one from the first third of them, one from the middle third, one from the last third, preferring in each third the line nearest four seconds long among those between two and eight seconds, and taking the longest when none is; a Speaker with fewer than three lines shows what it has. Pressing a Sample plays the Recording from that line's start and pauses at its end, so a voice is heard on its own; Space carries on from there. While the card is picked, its Samples are marked on its Lane.
- **rename** and **same person as...**: the Speakers strip's rename and merge, with the same confirmation and the same audit rows. Inside a Case, rename is the pick-or-type box of the Phase 2 People chapter, which lists the Case's People as the user types and joins the Person whose name is picked or typed.
- **The name box** on an unnamed Speaker's card: the same pick-or-type box, open on the card rather than in a prompt, with **Name** as its button. Inside a Case, the list under it is headed **Known in this case** and offers the Case's People first, each with its Role and "in N other recordings" when the Person is named elsewhere in the Case, then **New name "<typed>"** with a Role picker beside it from the Admin's Speaker roles list, so that a new Person made here can be given its Role at once; Phase 2 had the Role set on the Speakers tab only, and this is the one change to that (see What changes). Outside a Case the box has no list. Naming a Speaker with a name another Speaker of the Transcript already holds is the merge, confirmed as the merge is.
- **The fragment hint**: a Speaker whose lines never overlap in time with another Speaker's lines, and who has fewer lines than that other Speaker, carries the line "Never speaks while <other> does; see the lanes." with **Merge into <other>**. When more than one Speaker qualifies as the other, the one with the most lines is named. The hint says what the timing shows and no more; whether the two are one person is the listener's call, which is why the Samples and the Lanes sit beside it. Overlap is measured on the Segments as they are; two lines that touch within half a second are not an overlap.
- **The suggestion line**: after Suggest names, each suggestion lands on its Speaker's card as "Probably <name> (<Role>), from <time>: '<quote>'" with **Accept** and **Reject**, which are the Phase 1 Accept and Reject with their audit rows; the dashed pill on the Transcript's first Segment appears as well, since the Ledger is the viewer's. Only high and medium suggestions arrive, as the AI assistant chapter has it.
- **The reservation for chapter 2**: an unnamed Speaker's card keeps one line, empty and not drawn until chapter 2 is built, for "Sounds like <Person>" (see chapter 2). Nothing about it shows in v1.50.0.
- A card is **picked** by a press on it or on its Lane's head, or by pressing one of its Samples; the picked card is outlined, its Lane is outlined, and the Ledger filters to it. A number key never picks: it gives the line being spoken, as below. The first unnamed Speaker is picked when the page opens, or the first Speaker when all are named.
- Under the cards, one line: "1 to 9 give the line being spoken to a speaker. Space plays, B goes back three seconds, Left and Right five."

### The Lanes

On the right, between the transport and the Ledger, the page's timeline: a ruler with times across the top, then one Lane per Speaker in card order, each with its head (colour dot and name) at the left and its track across the width, with a block for every stretch that Speaker talks. The playhead is a line through every Lane.

- **The blocks** are the Speaker's Segments; Segments of one Speaker with less than a second between them are drawn as one block, so a Lane stays light on a long Recording. A block's title on hover is its times.
- **Seeking**: a press anywhere on a track seeks the player there; pressing on a block seeks to the block's start. The Lanes are the page's scrub bar and there is no other.
- **Zoom**: **all**, **2 min**, and **30 s** at the right of the Lanes; the two narrower views keep the playhead in view and scroll with it. All is the default and is remembered in the browser.
- **The picked Speaker's Lane** is outlined in its colour, and its Samples are marked on it as small ticks.
- **Drag to merge**: dragging one Lane's head onto another's is the strip's merge, with the same confirmation. The keyboard's route to the same thing is same person as... on the card.
- **Many Speakers**: with more than six Speakers, those who talk for under a minute in all fold into one Lane headed "N small speakers", which a press expands into their Lanes and a second press folds again. Their cards are unaffected.
- **A Two-channel call** has one Lane per Speaker as any Recording has, the Side's name in the head where Phase 1 labels a Speaker by its Side.
- A sound-only Recording has the Lanes where a video has them; the picture above them is the waveform strip.

### The player and the Ledger

- **The player** is the viewer's: the picture (or the waveform strip on a sound Recording) at the top of the right column, the transport under it (Play and pause, back three seconds, five seconds either way, the clock, the speed), and the page's keys. On a window narrower than 1280 pixels the picture shrinks to a strip the way the stage does on the recording page, so the Lanes and the Ledger keep their room; the cards move above the Lanes in one column.
- **The Ledger** is the viewer's Transcript, the same rows at the same size in the same colours (the Transcript viewer and player chapter's Ledger of v1.46.0), without the marking, correcting, describing, and Clip controls, which belong to the recording page. Above it, a filter with two pills: **<picked speaker> only**, the default whenever a card is picked, which shows that Speaker's lines with the line before and after each dimmed for context, and **Everyone**. Follow is on and keeps the line being spoken in view under the viewer's own band rule; the pill to turn it off is the viewer's.
- **The line being spoken** carries its actions: play, and **not this speaker**, which opens the list of the other Speakers and gives the line to the one picked. That is the Speakers window's number key by mouse: one Segment changes hands, the row Speaker changed on a line is written (no name), and Undo puts that one line back. The number keys 1 to 9 do the same for the line being spoken, as the window's did; there is no key past 9, and the list covers the rest.
- A press on a row seeks to it, as on the recording page.

### Undo

The Transcript's twenty-deep record of renames, merges, and lines given (the Transcript viewer and player chapter, v1.36.0 and v1.47.0) is the page's Undo, shown in the head with the last change in words. Undo on the page is the strip's Undo.

### What changes from earlier phases

- **Phase 1, the Transcript viewer and player chapter, the Speakers window**: Tag speakers on the strip becomes Manage speakers and opens the Speakers page; the Speakers window is the Speakers page opened in a window, with the following and the channel as that paragraph has them. The window's own roster, nowbox, and number keys are the page's cards, line being spoken, and number keys. Its route stays.
- **Phase 1, the Transcript viewer and player chapter, Speaker suggestions**: Suggest names is offered on the Speakers page as well as on the strip, under the same rules; a suggestion shows on the card as well as in the pill.
- **Phase 2, the People chapter, In the viewer inside a Case**: the pick-or-type box on the Speakers page offers a Role picker beside New name, so a Person made from the page can take its Role at once. The Speakers tab's Edit stays the place to change a Role afterwards. Accepting a role suggestion still creates or joins a Person of that name without setting the Role, as Phase 2 has it.
- **Phase 2, the People chapter, Principles 4**, and **Phase 1's ruled-out item 12** (no embeddings requested or stored): unchanged by chapter 1. Chapter 2 is written as the amendment that will change them, and is not in force.
- Nothing changes for the Speakers tab on the Case page, the strip's chips, exports, Clips, Summary, Chat, or Moments.

### Audit rows

None new. The page writes the rows the strip and the window write: Speaker renamed, Speakers merged, Speaker changed on a line, Speaker suggestion accepted and rejected, and the AI assistant call for `speaker_suggestions`; and, inside a Case, the People chapter's rows when a Person is made, joined, or merged. None holds a name.

### Settings

None new. Speaker suggestions (Phase 1) governs Suggest names on the page; Speaker roles (Phase 2) fills the Role picker.

### Not in this phase

- **Voice prints** (chapter 2).
- **Splitting a line** between two Speakers at a word. A line that holds two voices is given to the one who says more of it; the maintainer did not ask for the cut.
- **Checking off** a Speaker or a stretch of lines as verified; nothing marks what a person has listened to.
- **Lanes on the recording page.** The Timeline there stays as it is.
- **A page across a Case.** The page is one Recording's; the Case page's Speakers tab remains the view across Recordings.

### Left to the build

- The Samples' choice within the rule above (which line in a third when several are between two and eight seconds), and the tick marks' shape on a Lane.
- How the block list reaches the page: from the Segments the page already renders, or a lighter list of spans in the state answer. Either way nothing is stored.
- The narrow-window arrangement below 1280 pixels, within the rule that the cards go above the Lanes and the picture gives way first.
- The exact wording of the fragment hint and the "not this speaker" list, within the words fixed here.

## 2. Voice prints (deferred; the reservation and the rules)

Not built. The maintainer chose on 2026-09-12 to build the page first and voice prints in a later release, and this chapter is the reservation the page keeps and the rules the release will have to meet, so that the page is not redesigned when it comes. Nothing here is in force, and Phase 1's ruled-out item 12 and Phase 2's Principle 4 stand until an amendment moves this chapter into force.

### What it is

Recognising a Speaker by sound: the app noticing that the voice of an unnamed Speaker in this Recording is the voice of a Person already named in another Recording of the same Case, and offering that name on the card before anyone listens, as "Sounds like <Person> (<Role>)" with Accept, the way Suggest names offers a name from the words.

### What the app already has

The WhisperX service returns, on request, one vector per Speaker from its diarization model (`docs/whisperx-api.md`, `return_speaker_embeddings`). The app asks for them today for the stretches of a Live recording and matches labels across stretches by a same-voice threshold (Phase 3, the Live recording chapter), then discards them. Nothing is kept.

### The rules it will have to meet

1. **A Voice print is a Person's, inside a Case, and nowhere else.** One vector per Person per Case, kept as a field of the Person, made when a Speaker is named inside the Case from that Speaker's vector, and deleted with the Person. Nothing links a voice across Cases, as Phase 2's Principle 2 has it for names.
2. **It is content.** A Voice print is biometric data about a client, a witness, or an officer. It is on the never-logged list, never exported, never in a Backup's on-disk files beyond the database dump, and never sent to the engine or anywhere else. The service that makes it is local.
3. **On request, or at most as a suggestion.** Matching runs when a Transcript lands inside a Case with unnamed Speakers, and produces suggestions only; nothing is named by itself. A suggestion carries how close the match was, in the AI chapter's three words, and only the two upper ones show.
4. **Off by default.** An admin setting turns it on, and turning it off deletes every Voice print the Case holds; the pages say so before the switch is thrown.
5. **Honest wording.** "Sounds like" and never "is"; the card keeps the Samples beside it so a person listens before accepting.

### What it will change

Phase 1's ruled-out item 12 and Phase 2's Principle 4 (an amendment to each, recorded here and there); `return_speaker_embeddings` requested on every diarized job inside a Case while the setting is On; a field on the Person and a migration; the reservation line on the card drawn; an audit row for a match accepted and rejected (no name); the catalogue's row for the setting; the decision record in `docs/adr/` that says what is kept and why.

## 3. Deferred and ruled out

- **Voice prints**: deferred to a later release; chapter 2.
- **An office-wide list of people or voices**: ruled out, as Phase 2 rules it out for names.
- **Sending sound to the engine to name a voice**: ruled out; the engine reads words and pictures, and nothing about a voice leaves the WhisperX service.
- **Splitting a line at a word**: deferred; not asked for.
- **Checking off lines as verified**: deferred; not asked for.

## Appendix A. Audit rows added in Phase 5

None in chapter 1.

## Appendix B. Settings added in Phase 5

None in chapter 1.

## Sources

The maintainer's ask and answers of 2026-09-12; the mockups the maintainer chose from ("the line-up with lanes"); the Phase 1 Transcript viewer and player chapter (the Speakers panel, the Speakers window, Speaker suggestions) and AI assistant chapter; the Phase 2 People chapter; the Phase 3 Live recording chapter's use of embeddings across stretches; `docs/whisperx-api.md`.

## Amendments applied

None yet.
