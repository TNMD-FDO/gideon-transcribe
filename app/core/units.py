"""Units (Phase 5 chapter 2, the unit's voice book; v1.146.0): the office's
parts, each with a voice book of its own, placed from the directory.

The Admin lists the units on the Sign-in page, one per line: the unit's
name, a vertical bar, then the directory folder (OU) its accounts sit under.
Every sign-in already reads the account's own directory path to prove the
password; from it the account's folder chain is cut (the path at its commas,
with the account's own name, CN, and the domain parts, DC, set aside), and
the first Units line whose folders appear in the chain in the same order and
next to each other, letter case ignored, is the person's unit. The unit and
the chain are kept on the account as words, so the People page shows both
and a wrong placement is seen, not guessed. A Local admin is not in the
directory; their unit is set by hand there. An Admin is in one unit like
anyone and reads every unit's book; a Case belongs to its owner's unit.

No office value is in the app: the names and folders are the Admin's typed
setting, and this module knows only how to read a path.
"""

from __future__ import annotations

import re

from core import settings_store

# The parts of a directory path that are not folders: the account's own
# name and the domain.
NOT_A_FOLDER = ("cn", "dc")
NAME_LENGTH = 40


def _split(path: str) -> list[str]:
    """A path's components, cut at commas that are not escaped."""
    if not path:
        return []
    return [part.strip() for part in re.split(r"(?<!\\),", path)]


def folder_of(path: str) -> str:
    """The folder chain of a directory path: its components without the
    account's own name (CN) and the domain parts (DC), nearest folder first,
    joined with commas as the directory writes them."""
    kept = []
    for part in _split(path):
        if not part or "=" not in part:
            continue
        kind = part.split("=", 1)[0].strip().lower()
        if kind in NOT_A_FOLDER:
            continue
        kept.append(part)
    return ",".join(kept)


def _chain(folder: str) -> list[str]:
    return [part.lower() for part in _split(folder) if part]


def parse(text: str) -> list[tuple[str, list[str]]]:
    """The Units setting as (name, folders) pairs, in the Admin's order."""
    out = []
    for line in (text or "").splitlines():
        if "|" not in line:
            continue
        name, folders = line.split("|", 1)
        name = name.strip()[:NAME_LENGTH]
        chain = _chain(folders)
        if name and chain:
            out.append((name, chain))
    return out


def check_setting(text: str) -> str:
    """The Units setting as it would be kept, or a refusal saying why not:
    every line names a unit, then a bar, then at least one folder."""
    kept = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "|" not in line:
            raise ValueError(
                f"Units: each line is the unit's name, a vertical bar, then its "
                f"directory folder, and {line!r} has no bar"
            )
        name, folders = line.split("|", 1)
        if not name.strip():
            raise ValueError(f"Units: the line {line!r} names no unit")
        if len(name.strip()) > NAME_LENGTH:
            raise ValueError(
                f"Units: a unit's name is at most {NAME_LENGTH} characters"
            )
        chain = _chain(folders)
        if not chain or not all("=" in part for part in chain):
            raise ValueError(
                f"Units: the line {line!r} needs a folder such as OU=Appeals,OU=Staff "
                "after the bar"
            )
        kept.append(f"{name.strip()} | {','.join(_split(folders.strip()))}")
    return "\n".join(kept)


def names() -> list[str]:
    """The units, in the Admin's order."""
    return [name for name, _ in parse(settings_store.get("units") or "")]


def place(folder: str) -> str:
    """The unit an account's folder chain falls under: the first Units line
    whose folders appear in the chain in order and next to each other,
    letter case ignored; "" when none does."""
    chain = _chain(folder)
    if not chain:
        return ""
    for name, wanted in parse(settings_store.get("units") or ""):
        width = len(wanted)
        for start in range(len(chain) - width + 1):
            if chain[start : start + width] == wanted:
                return name
    return ""


def placed(path: str) -> tuple[str, str]:
    """(folder chain, unit) for a directory path, as the sign-in keeps them."""
    folder = folder_of(path)
    return folder, place(folder)


def of(user) -> str:
    """The person's unit, as the sign-in or the People page placed them,
    while that unit is still listed."""
    unit = getattr(user, "unit", "") or ""
    return unit if unit in names() else ""


def seen_by(user) -> list[str]:
    """The units whose books this person reads: every unit for an Admin,
    their own for anyone else, none for a person in no unit."""
    if getattr(user, "is_admin", False):
        return names()
    mine = of(user)
    return [mine] if mine else []


def set_by_hand(user, unit: str, *, by, request=None) -> None:
    """A Local admin's unit, picked on the People page; a directory
    account's is the directory's to decide and is refused here."""
    from core import audit

    if not user.is_local:
        raise ValueError("A directory account's unit is read from the directory.")
    wanted = (unit or "").strip()
    if wanted and wanted not in names():
        raise ValueError(f"{wanted!r} is not a unit the Admin has listed.")
    user.unit = wanted
    user.folder = ""
    user.save(update_fields=["unit", "folder"])
    audit.write(
        audit.Category.ACCOUNTS,
        "Unit set by hand",
        actor=by,
        request=request,
        affected_user=user,
        unit=wanted,
    )


def summary() -> dict:
    """For Check directory now and the nightly check: the count per unit and
    the accounts in no listed unit, each with its folder chain."""
    from core.models import User

    counts = {name: 0 for name in names()}
    none = []
    for person in User.objects.filter(deactivated_at=None, blocked_at=None).order_by(
        "username"
    ):
        unit = of(person)
        if unit:
            counts[unit] = counts.get(unit, 0) + 1
        elif not person.is_local:
            none.append({"username": person.username, "folder": person.folder})
    return {"counts": counts, "none": none, "listed": bool(names())}
