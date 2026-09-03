---
status: accepted
date: 2026-09-03
---
# The audit log's two roles are reached with SET ROLE, and the chain covers the whole row

The specification fixes that the audit log lives in the app's own database, that the app writes through an insert-only role which cannot change or delete rows, that only the retention sweep's separate role removes rows, and that each row carries a hash chained to the previous one. It leaves the shape of both to the build.

## The roles

Two ways to reach a second database role: give it a password of its own and open a second connection, or make the app's role a member of it and switch with `SET ROLE`.

The second is chosen. Both give the same thing where it counts, which is that no ordinary code path can change or delete an audit row: the role that inserts holds `INSERT` and nothing else, and the role that sweeps holds `DELETE` and nothing else. The first would add two secrets to the install, two more things for an office to lose, and two more connections to a database that already has a connection, and it would buy strength only against an attacker who can already run arbitrary SQL as the app. The specification's own words settle how much strength is being bought: "This is tamper-evident, not tamper-proof: root on the box can rewrite the chain."

So the app's role is a member of both, `NOINHERIT`, which means it does not hold their privileges until it asks for them by name. Writing a row is `SET ROLE` to the writer, insert, `RESET ROLE`. The sweep is the same with the sweeper. The app's own role keeps `SELECT`, because the Admin viewer reads the log, and is revoked `UPDATE` and `DELETE`.

The app's role owns the table, because Django's migrations create it, and an owner can grant itself back what it was revoked. That is a real limit and it is the reason the hash chain exists rather than a reason to abandon the roles: the roles stop a bug, a careless migration, and a mistaken `DELETE`, and the chain is what stands against somebody who means it.

## The chain

Each row carries the SHA-256 of the previous row's hash followed by every field of its own that a reader can see, in a fixed order, as canonical JSON. The first row's previous hash is sixty-four zeros.

Hashing the whole row rather than a few fields means the check catches an edited actor, an edited outcome, or an edited details block, not only a deleted row. Fixing the order and the JSON form means the hash of a row is the same tomorrow as it was today, whatever changes about the code that reads it.

## Consequences

- Adding a field to an audit row changes every hash after it, so the field set is versioned with the row: a row records which version of the field list it was hashed under, and the check hashes each row the way that row was written.
- The check reports "unbroken since the first row" or the first row where the chain breaks, and writes its own result as a row, which is itself chained.
- The retention sweep removes the oldest rows, which breaks the chain at the point it cuts. The check therefore starts from the oldest row that remains rather than from the first row ever written, and says so.
- An office that wants more than tamper-evidence needs rows forwarded off the box as they are written, which Phase 1 does not do and does not plan.
