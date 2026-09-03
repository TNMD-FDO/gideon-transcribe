---
status: accepted
date: 2026-09-02
---
# Admins can open any user's content, and every such access is audited

Gideon Transcribe holds privileged, confidential material, so the obvious design keeps Admins to metadata (counts, sizes, Job states) and never lets them read another user's Recordings, Transcripts, Chats, or Summaries. It was ruled on 2026-09-02 that Admins (the office's IT staff through the Admin directory group named in configuration, plus manually flagged and local admins) can open all of it with the owner's powers, because IT must be able to troubleshoot a stuck Job, recover a leaver's work, and reassign material without asking the owner. The guard rails are the trade: each access writes an audit row naming the Admin, the item, and the time; the screen shows a banner that the Admin is viewing another user's Workspace; and users are told, on the upload screen and in the user guide, that office IT administrators can access everything in the system.

## Consequences

The audit log is not optional and must exist from the first release, with the Admin-access rows queryable by user. Admin status is therefore a significant grant: the users list shows its source for each person, and the group that confers it is chosen by the office in configuration. If a future office wants metadata-only Admins, that is a new setting, not a reinterpretation of this one.
