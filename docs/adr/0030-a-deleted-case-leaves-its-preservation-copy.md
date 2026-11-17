# 30. A deleted case leaves its Preservation copy, for a number of days

Date: 2026-11-17. Status: accepted. Release: v1.245.0 (Phase 14 chapter 2, "The Preservation copy at deletion, and Archived").

## Context

From Phase 2 a person's own Delete of a Case was final at once: files and
rows gone, nothing kept, and the confirmation said so. Only what the
Retention policy deleted waited anywhere, whole, in the Recycle bin.

On 2026-11-17 the maintainer said that what is made in the app is part of the
client's record and must be easy to keep, "if anything at the time of case
deletion". v1.244.0 gave a Case its Preservation copy on request. This
decision is what happens to that copy when the Case goes.

It is recorded here because it changes what Delete means, and an office that
has told its people "Delete leaves nothing" would be wrong after an upgrade
unless it is told.

## Decision

1. **A Case that is deleted leaves its Preservation copy behind.** By its
   owner, by an Admin, or by the Retention policy, the copy is made first.
   The Case itself is deleted exactly as before: an owner's Delete is still
   final for the Case, and nothing of the Case can be brought back from the
   copy.
2. **The copy alone is kept, for a number of days an Admin sets** (30 by
   default), counted from the day the Case was gone for good: the day of an
   owner's or Admin's Delete, or the day the Recycle bin wiped it. It is kept
   in a place of its own, **Archived**, which the owner and Admins see.
3. **It can be switched off.** "Preservation copy at deletion" is a setting,
   On by default. Off, Delete leaves nothing, as it did before this decision.
4. **The owner is not held up.** When the copy cannot be made, the owner's
   Delete does not go through by itself, and the owner may then delete without
   a copy by saying so a second time. The nightly sweep never waits: a Case
   that is due goes to the Recycle bin with or without a copy, and one past
   its bin days is wiped with or without one.
5. **The copy may be removed early** by its owner or an Admin, behind a
   confirmation, and the sweep removes it when its days are up whether or
   not anyone downloaded it.

## Consequences

- "Delete" no longer means that nothing of the Case remains on the server.
  What remains is the written work as Word documents, never the uploaded
  recordings, for a bounded time, visible to the owner and Admins, and
  removable at once. The Delete confirmation says so in a sentence of its own.
- An office that needs Delete to leave nothing turns the setting Off, or its
  people press Remove now.
- An upgrade to this version turns the behaviour On for an office that has
  never chosen. The changelog and the admin guide say so first.
- The copies are small files under the app's own data directory, in every
  Backup, and count toward nobody's room. A Backup therefore holds a deleted
  Case's written work for the copy's days and then for the Backup's own.
- The mail that tells the owner the copy is there is the next release; until
  then the pages are the only notice.

## Considered and not chosen

- **Nothing kept; the copy downloaded to the browser as the Case is deleted.**
  A lost download is a lost record, and the Retention policy's deletion has
  nobody at a browser.
- **The Case never deleted without a copy.** The maintainer's rule is that
  saving the record is the owner's to do and the app does not hold a deletion
  back.
- **The copy's days counted from the day the Retention policy binned the
  Case.** With the two periods equal, a Case the clock deleted would never
  reach Archived: its copy would go the night the Case was wiped, and that is
  the Case whose owner was least likely to have been looking.
