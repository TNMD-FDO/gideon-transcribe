"""Units (Phase 5 chapter 2, the unit's voice book; v1.146.0, the four line
forms and the pin by hand in v1.147.0): the office's parts, each with a
voice book of its own, placed from the directory or by an Admin's hand.

The Admin lists the units on the Sign-in page, one per line: the unit's
name, a vertical bar, then how the directory tells its accounts apart. Four
forms, because offices lay their directories out differently:

- a folder chain, `OU=Trial,OU=Staff`: the account's own path, with its name
  (CN) and the domain parts (DC) set aside, holds those folders in that
  order and next to each other;
- a group, `group=Trial Attorneys` (a group's name, or its full path): the
  account is a member, directly or through nested groups, read the way the
  sign-in group already is;
- an attribute, `department=Trial Division`: the account's attribute of that
  name holds that value, letter case ignored;
- everyone: every directory account, for an office with one book.

The lines are tried in the Admin's order and the first that fits places the
account, so a nested unit is listed above its parent. The unit, what placed
it, and the folder chain are kept on the account as words, so the People
page shows them and a wrong placement is seen, not guessed. An Admin may
also pin any account's unit by hand on the People page; a pinned account
keeps its unit through every sign-in and nightly check until the Admin lets
the directory decide again. A Local admin is not in the directory and is
always placed by hand. An Admin is in one unit like anyone and reads every
unit's book; a Case belongs to its owner's unit.

No office value is in the app: the names, folders, groups and attributes
are the Admin's typed setting, and this module knows only how to read them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core import settings_store

# The parts of a directory path that are not folders: the account's own
# name and the domain.
NOT_A_FOLDER = ("cn", "dc")
NAME_LENGTH = 40
FOLDER, GROUP, ATTRIBUTE, EVERYONE = "folder", "group", "attribute", "everyone"
BY_HAND = "by hand"


@dataclass
class Line:
    """One Units line: the unit's name and how its accounts are told."""

    name: str
    kind: str
    text: str
    value: str = ""
    chain: list[str] = field(default_factory=list)

    def describe(self) -> str:
        return f"{self.name} | {self.text}"


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


def _read_line(raw: str) -> Line | None:
    """One line as a Line, or a ValueError saying what is wrong with it;
    None for a blank line."""
    line = raw.strip()
    if not line:
        return None
    if "|" not in line:
        raise ValueError(
            f"Units: each line is the unit's name, a vertical bar, then how the "
            f"directory tells its accounts, and {line!r} has no bar"
        )
    name, right = line.split("|", 1)
    name = name.strip()
    right = right.strip()
    if not name:
        raise ValueError(f"Units: the line {line!r} names no unit")
    if len(name) > NAME_LENGTH:
        raise ValueError(f"Units: a unit's name is at most {NAME_LENGTH} characters")
    if not right:
        raise ValueError(
            f"Units: the line {line!r} says nothing after the bar; write a folder "
            "(OU=Trial,OU=Staff), group=<name>, <attribute>=<value>, or everyone"
        )
    if right.casefold() == EVERYONE:
        return Line(name=name, kind=EVERYONE, text=EVERYONE)
    if right.lower().startswith("group="):
        value = right.split("=", 1)[1].strip()
        if not value:
            raise ValueError(f"Units: the line {line!r} names no group after group=")
        return Line(name=name, kind=GROUP, text=f"group={value}", value=value)
    parts = [one for one in _split(right) if one]
    if parts and all(
        "=" in one and one.split("=", 1)[0].strip().lower() == "ou" for one in parts
    ):
        return Line(
            name=name,
            kind=FOLDER,
            text=",".join(parts),
            chain=[one.lower() for one in parts],
        )
    if len(parts) == 1 and "=" in parts[0]:
        key, value = (one.strip() for one in parts[0].split("=", 1))
        if key and value and key.lower() not in NOT_A_FOLDER:
            return Line(name=name, kind=ATTRIBUTE, text=f"{key}={value}", value=value)
    raise ValueError(
        f"Units: after the bar, {right!r} is none of a folder such as "
        "OU=Trial,OU=Staff, group=<name>, <attribute>=<value>, or everyone"
    )


def parse(text: str) -> list[Line]:
    """The Units setting as lines, in the Admin's order; a line that does
    not read is left out here (the setting refused it when typed)."""
    out = []
    for raw in (text or "").splitlines():
        try:
            line = _read_line(raw)
        except ValueError:
            continue
        if line is not None:
            out.append(line)
    return out


def check_setting(text: str) -> str:
    """The Units setting as it would be kept, or a refusal saying why not."""
    kept = []
    for raw in (text or "").splitlines():
        line = _read_line(raw)
        if line is not None:
            kept.append(line.describe())
    return "\n".join(kept)


def lines() -> list[Line]:
    return parse(settings_store.get("units") or "")


def names() -> list[str]:
    """The units, in the Admin's order, each once."""
    out: list[str] = []
    for line in lines():
        if line.name not in out:
            out.append(line.name)
    return out


def groups_wanted() -> list[str]:
    """The groups the lines name, for the sign-in to read membership of."""
    return [line.value for line in lines() if line.kind == GROUP]


def attributes_wanted() -> list[str]:
    """The attributes the lines name, for the sign-in to read."""
    out: list[str] = []
    for line in lines():
        if line.kind == ATTRIBUTE:
            key = line.text.split("=", 1)[0]
            if key not in out:
                out.append(key)
    return out


def placement(
    folder: str, groups=(), attributes: dict | None = None
) -> tuple[str, str]:
    """(unit, the line that placed) for a directory account from its folder
    chain, the groups it is a member of (as the lines name them) and its
    attributes; ("", "") when no line fits."""
    chain = _chain(folder)
    in_groups = {str(one).casefold() for one in (groups or ())}
    held = {k.casefold(): str(v) for k, v in (attributes or {}).items()}
    for line in lines():
        if line.kind == EVERYONE:
            return line.name, line.describe()
        if line.kind == FOLDER:
            width = len(line.chain)
            if any(
                chain[start : start + width] == line.chain
                for start in range(len(chain) - width + 1)
            ):
                return line.name, line.describe()
        elif line.kind == GROUP:
            if line.value.casefold() in in_groups:
                return line.name, line.describe()
        elif line.kind == ATTRIBUTE:
            key, value = line.text.split("=", 1)
            if held.get(key.casefold(), "").casefold() == value.casefold():
                return line.name, line.describe()
    return "", ""


def place(folder: str, groups=(), attributes: dict | None = None) -> str:
    """The unit alone, for a reader who needs no more."""
    return placement(folder, groups, attributes)[0]


def placed(path: str) -> tuple[str, str]:
    """(folder chain, unit) for a directory path, from its folders alone."""
    folder = folder_of(path)
    return folder, place(folder)


def apply_directory(
    user, folder: str, groups=(), attributes: dict | None = None
) -> bool:
    """What the directory says at a sign-in or the nightly check: the folder
    chain is kept, and the unit follows the lines unless an Admin pinned it.
    True when something on the account changed."""
    fields = []
    if user.folder != (folder or ""):
        user.folder = folder or ""
        fields.append("folder")
    if not user.unit_pinned:
        unit, how = placement(folder, groups, attributes)
        if user.unit != unit or user.unit_how != how:
            user.unit = unit
            user.unit_how = how
            fields += ["unit", "unit_how"]
    if fields:
        user.save(update_fields=fields)
    return bool(fields)


def of(user) -> str:
    """The person's unit, as the directory or an Admin placed them, while
    that unit is still listed."""
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
    """An Admin pins the account's unit, or pins it to no unit; the
    directory leaves it alone until follow_directory."""
    from core import audit

    wanted = (unit or "").strip()
    if wanted and wanted not in names():
        raise ValueError(f"{wanted!r} is not a unit the Admin has listed.")
    user.unit = wanted
    user.unit_pinned = True
    user.unit_how = BY_HAND
    user.save(update_fields=["unit", "unit_pinned", "unit_how"])
    audit.write(
        audit.Category.ACCOUNTS,
        "Unit set by hand",
        actor=by,
        request=request,
        affected_user=user,
        unit=wanted,
    )


def follow_directory(user, *, by, request=None) -> None:
    """The pin comes off: the unit is read again from what the directory
    last said (the folder chain now; groups and attributes at the next
    sign-in or check)."""
    from core import audit

    if user.is_local:
        raise ValueError("A Local admin is not in the directory; pick a unit by hand.")
    user.unit_pinned = False
    user.unit, user.unit_how = placement(user.folder)
    user.save(update_fields=["unit", "unit_pinned", "unit_how"])
    audit.write(
        audit.Category.ACCOUNTS,
        "Unit follows the directory",
        actor=by,
        request=request,
        affected_user=user,
        unit=user.unit,
    )


def summary() -> dict:
    """For Check directory now and the nightly check: the count per unit,
    the accounts in no listed unit with their folder chains, and how many
    are pinned by hand."""
    from core.models import User

    counts = {name: 0 for name in names()}
    none = []
    pinned = 0
    for person in User.objects.filter(deactivated_at=None, blocked_at=None).order_by(
        "username"
    ):
        if person.unit_pinned:
            pinned += 1
        unit = of(person)
        if unit:
            counts[unit] = counts.get(unit, 0) + 1
        elif not person.is_local:
            none.append({"username": person.username, "folder": person.folder})
    return {"counts": counts, "none": none, "pinned": pinned, "listed": bool(names())}
