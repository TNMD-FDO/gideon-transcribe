# 24. Any voice may be kept for a unit: the Role no longer gates it

Date: 2026-10-26. Status: accepted. Release: v1.158.0. Amends Phase 5
chapter 2 ("The unit's voice book": the bullets "Keep for the unit", "The
switch and the roles" and "Who may") and retires the setting Roles kept
for the unit.

## Context

The unit's voice book (v1.146.0) kept a Person's voice print across cases
only in a Role the Admin listed: Officer, Interpreter and Interviewer as
shipped, and Defendant, Victim, Witness and Client refused if typed. The
rule was written for an office that handles privileged material: a book
works across cases, so a kept voice can be recognised on any later
recording of that unit, and a client's voice kept where it would be
matched on other clients' calls was the thing the chapter set out to
prevent.

On 2026-10-26, after v1.157.0 let an Admin keep a voice for any unit, the
maintainer found the Keep button missing on a card whose Role was
Defendant and asked that voices saved to a unit not carry the Role, so
that any voice the office chooses may be added. The concern above was put
to them in plain words, with two readings: lift the gate for Admins only,
or for everyone and retire the setting. The maintainer chose everyone.

## Decision

1. **The Role no longer gates the keeping.** Any Person with a voice print
   may be kept for a unit, by anyone who may keep (the case owner's unit
   for a person in that unit; any unit, or several, for an Admin as
   v1.157.0 made it). A Person with no Role may be kept too. The only
   rules left are the switch, the print, and (for everyone but an Admin)
   the case owner's unit.
2. **The Role rides with the voice as a label.** The book still records
   the Role, the Voices place still shows it, and Accept on a card still
   gives the Person the book's name and Role. A Role change on a kept
   Person changes the label in every book that holds them and stops
   nothing.
3. **The setting Roles kept for the unit is retired.** Its key
   `unit_voice_roles` leaves the settings definitions and the Admin
   settings catalogue; a row stored under it is left alone and never
   read. No migration.
4. **The pages say so.** The card's muted line "A <role>'s voice is never
   kept for the unit" goes, and so does "give them a role first"; the
   Voices place's note no longer lists allowed roles.

## Consequences

- The office decides what a unit's book is for. Keeping a client's or a
  witness's voice is now a choice a person makes on a card, not something
  the app refuses. The box that asks before keeping still says what
  keeping means and that the voice will be matched on any recording in
  the unit's cases; the audit row is written as before.
- An office that wants the old rule back can have it as a setting again;
  the hooks are small (`person_rule` and `follow_role` in
  `core/voice_book.py`). This decision does not close that door, it
  records that the shipped app no longer enforces it.
- Phase 5 chapter 2 is amended in place; the settings catalogue's row is
  struck with a note; CONTEXT.md's Keep for the unit and the user and
  admin guides follow.
