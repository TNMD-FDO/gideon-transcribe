"""A task deferred once the surrounding transaction has committed (v1.131.0).

In a web process the queue's connector shares Django's connection, so a job
deferred inside a transaction is committed with it. In a worker the queue has
a connection of its own, and a job deferred inside a transaction is committed
at once, so another worker can take it up before the rows it needs are there:
the v1.54.0 case of a video prepared before the mark that queued it was
written. Every deferral that can happen inside a worker's transaction goes
through here, and runs when the transaction commits, or at once when none is
open. The test suite makes it run at once.
"""

from __future__ import annotations

from collections.abc import Callable

from django.db import transaction


def after_commit(deferral: Callable[[], None]) -> None:
    transaction.on_commit(deferral)
