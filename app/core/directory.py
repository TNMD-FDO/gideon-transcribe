"""The office directory: signing people in, and the nightly check.

Everything office-specific is in `.env`: the domain, the CA root, the Bind
account and its password file, the base DN, and the two group DNs. Nothing
here names an office.

Three rules run through all of it. The app binds as the read-only Bind account
and never as anybody else, so no person's password is ever stored or cached.
Group membership is read from each group's own `member` list with Active
Directory's in-chain matching rule, never from a person's `memberOf`, because
`memberOf` is hidden from plain accounts in a hardened domain and a group's
own member list is not. And an empty password is refused before the directory
is asked, because the directory would take it as an anonymous bind, answer
"yes", and identify nobody.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

log = logging.getLogger("transcribe.directory")

# Active Directory's "member of, in chain" matching rule: a search that matches
# a group when the person is a member of it, or of a group inside it, however
# deep.
IN_CHAIN = "1.2.840.113556.1.4.1941"

# A slow or unreachable domain controller must fail over to the next rather
# than hang a sign-in. The domain name usually resolves to several, and one may
# sit at a continuity site over a slower link. There is no `.env` key for this.
NETWORK_TIMEOUT_SECONDS = 5

WHAT_IS_READ = ["sAMAccountName", "userPrincipalName", "givenName", "sn", "mail"]


class Unreachable(Exception):
    """The directory could not be reached, or would not answer."""


def is_on() -> bool:
    """Whether this office has a directory at all.

    `LDAP_ENABLED=false` gives a local-admins-only install for evaluation.
    """
    return os.environ.get("LDAP_ENABLED", "true").strip().lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


def facts() -> dict:
    """The eight keys, as the app reads them."""
    return {
        "enabled": is_on(),
        "server_uri": os.environ.get("LDAP_SERVER_URI", ""),
        "ca_file": os.environ.get("LDAP_CA_FILE", ""),
        "bind_user": os.environ.get("LDAP_BIND_USER", ""),
        "password_file": os.environ.get("LDAP_BIND_PASSWORD_FILE", ""),
        "search_base": os.environ.get("LDAP_SEARCH_BASE", ""),
        "signin_group": os.environ.get("LDAP_SIGNIN_GROUP", ""),
        "admin_group": os.environ.get("LDAP_ADMIN_GROUP", ""),
    }


def bind_password() -> str:
    """The Bind account's password, from the file `.env` names.

    It lives only in that file: never in `.env`, never in the panel, never in
    a log.
    """
    path = os.environ.get("LDAP_BIND_PASSWORD_FILE", "")
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        log.warning("the bind password file could not be read")
        return ""


def connect():
    """A connection, bound as the Bind account, or Unreachable.

    LDAPS on 636 against the office CA root. Not StartTLS: the specification
    fixes LDAPS, and a connection that is encrypted from the first byte cannot
    be downgraded by anything in between.
    """
    import ldap

    where = facts()
    if not where["server_uri"]:
        raise Unreachable("no directory address is configured")

    if _has_something(where["ca_file"]):
        ldap.set_option(ldap.OPT_X_TLS_CACERTFILE, where["ca_file"])
        # Without this, OpenLDAP keeps the TLS context it already built and
        # the CA file above is ignored on every connection after the first.
        ldap.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
    ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, NETWORK_TIMEOUT_SECONDS)
    ldap.set_option(ldap.OPT_TIMEOUT, NETWORK_TIMEOUT_SECONDS)

    password = bind_password()
    if not password:
        raise Unreachable("the bind account has no password")

    try:
        held = ldap.initialize(where["server_uri"])
        held.set_option(ldap.OPT_REFERRALS, 0)
        held.simple_bind_s(where["bind_user"], password)
    except ldap.LDAPError as problem:
        raise Unreachable(_said(problem)) from problem
    return held


def _has_something(path: str) -> bool:
    """An empty CA file means the system trust store, not a broken one.

    An office with a public certificate authority has nothing to put in the
    file, and the file has to exist either way because the stack refuses to
    start without it.
    """
    try:
        return bool(path) and Path(path).stat().st_size > 0
    except OSError:
        return False


def _said(problem) -> str:
    """What the directory said, in words, and never a password."""
    if problem.args and isinstance(problem.args[0], dict):
        told = problem.args[0]
        return str(told.get("desc") or told.get("info") or problem)[:200]
    return str(problem)[:200]


def find_person(held, username: str) -> dict | None:
    """One person by sign-in name, with the attributes the app keeps."""
    import ldap

    where = facts()
    try:
        found = held.search_s(
            where["search_base"],
            ldap.SCOPE_SUBTREE,
            f"(&(objectClass=user)(sAMAccountName={_escaped(username)}))",
            WHAT_IS_READ + ["userAccountControl"],
        )
    except ldap.LDAPError as problem:
        raise Unreachable(_said(problem)) from problem

    for dn, attributes in found:
        if dn is None:
            # A referral, not a person.
            continue
        return {"dn": dn, **{name: _one(value) for name, value in attributes.items()}}
    return None


def _one(value) -> str:
    if not value:
        return ""
    first = value[0]
    return first.decode("utf-8", "replace") if isinstance(first, bytes) else str(first)


def _escaped(value: str) -> str:
    """A search filter is not a place to put anything a person typed, raw."""
    for character, instead in (
        ("\\", "\\5c"),
        ("*", "\\2a"),
        ("(", "\\28"),
        (")", "\\29"),
        ("\0", "\\00"),
    ):
        value = value.replace(character, instead)
    return value


def groups_of(held, person_dn: str) -> set[str]:
    """Which of the two groups this person is in, directly or nested.

    One search, with the in-chain rule against each group's own member list.
    """
    import ldap

    where = facts()
    wanted = [one for one in (where["signin_group"], where["admin_group"]) if one]
    found = set()
    for group_dn in wanted:
        try:
            answer = held.search_s(
                group_dn,
                ldap.SCOPE_BASE,
                f"(member:{IN_CHAIN}:={_escaped(person_dn)})",
                ["cn"],
            )
        except ldap.NO_SUCH_OBJECT:
            log.warning("a configured group does not exist in the directory")
            continue
        except ldap.LDAPError as problem:
            raise Unreachable(_said(problem)) from problem
        if any(dn is not None for dn, _ in answer):
            found.add(group_dn)
    return found


def members_of(held, group_dn: str) -> list[str]:
    """A group's own member list, which is what the Bind account may read."""
    import ldap

    try:
        answer = held.search_s(group_dn, ldap.SCOPE_BASE, "(objectClass=*)", ["member"])
    except ldap.LDAPError as problem:
        raise Unreachable(_said(problem)) from problem

    for dn, attributes in answer:
        if dn is None:
            continue
        return [
            one.decode("utf-8", "replace") if isinstance(one, bytes) else str(one)
            for one in attributes.get("member", [])
        ]
    return []


# Signing in -------------------------------------------------------------------

# The bit of userAccountControl that says an account is switched off.
ACCOUNT_DISABLED = 0x0002


def sign_in(username: str, password: str) -> dict:
    """Prove who this is against the directory, and say what it found.

    Raises Unreachable when the directory cannot be reached, which is a
    different thing from a wrong password and is told to the person
    differently.
    """
    import ldap

    if not password:
        # Never sent: the directory would take it as an anonymous bind and
        # answer yes to nobody in particular.
        return {"ok": False, "why": "wrong_password"}

    held = connect()
    try:
        person = find_person(held, username)
        if person is None:
            return {"ok": False, "why": "no_such_account"}

        control = person.get("userAccountControl", "")
        if control.isdigit() and int(control) & ACCOUNT_DISABLED:
            return {"ok": False, "why": "disabled"}

        groups = groups_of(held, person["dn"])
        where = facts()
        if not groups:
            return {"ok": False, "why": "not_in_a_group"}

        # The person's own password, checked by the directory and never kept.
        try:
            theirs = ldap.initialize(where["server_uri"])
            theirs.set_option(ldap.OPT_REFERRALS, 0)
            theirs.simple_bind_s(person["dn"], password)
            theirs.unbind_s()
        except ldap.INVALID_CREDENTIALS:
            return {"ok": False, "why": "wrong_password"}
        except ldap.LDAPError as problem:
            raise Unreachable(_said(problem)) from problem

        return {
            "ok": True,
            "username": person.get("sAMAccountName", username).lower(),
            "directory_address": person.get("userPrincipalName", ""),
            "display_name": " ".join(
                part
                for part in (person.get("givenName", ""), person.get("sn", ""))
                if part
            ),
            "email": person.get("mail", ""),
            "in_admin_group": bool(
                where["admin_group"] and where["admin_group"] in groups
            ),
        }
    finally:
        with contextlib.suppress(Exception):
            held.unbind_s()


# The four checks --------------------------------------------------------------


def test_connection() -> list[dict]:
    """The four checks, in order, each pass or fail with what was said.

    The same checks the button on the Status page runs, the button on the
    Sign-in and directory page runs, and `./transcribe check` runs from a
    terminal, so an office is never told two different things about the same
    directory.
    """
    results = []

    def note(name, ok, says, warning=False):
        results.append({"name": name, "ok": ok, "says": says, "warning": warning})
        return ok

    where = facts()
    if not where["enabled"]:
        note("Directory", False, "LDAP_ENABLED is false: local admins only")
        return results

    # 1. Bind as the Bind account.
    try:
        held = connect()
    except Unreachable as problem:
        note("Bind as the bind account", False, str(problem))
        return results

    try:
        who = _whoami(held)
        if not who:
            note(
                "Bind as the bind account",
                False,
                "the bind succeeded but named nobody, which means an empty "
                "password reached the directory",
            )
            return results
        note("Bind as the bind account", True, f"the directory says {who}")

        # 2. Read both groups by DN and count their members.
        for label, group_dn in (
            ("Sign-in group", where["signin_group"]),
            ("Admin group", where["admin_group"]),
        ):
            if not group_dn:
                note(f"Read the {label}", True, "not configured", warning=True)
                continue
            try:
                members = members_of(held, group_dn)
            except Unreachable as problem:
                note(f"Read the {label}", False, str(problem))
                continue
            if not members:
                note(
                    f"Read the {label}",
                    label == "Sign-in group",
                    "no members are visible"
                    + (
                        " (fine until the first wave is added)"
                        if label == "Sign-in group"
                        else ": the member attribute is hidden from the bind account"
                    ),
                    warning=label == "Sign-in group",
                )
                continue
            note(f"Read the {label}", True, f"{len(members)} member(s)")

        # 3 and 4. Resolve one member of each, and prove the nested rule.
        for label, group_dn in (
            ("Sign-in group", where["signin_group"]),
            ("Admin group", where["admin_group"]),
        ):
            if not group_dn:
                continue
            try:
                members = members_of(held, group_dn)
            except Unreachable:
                continue
            if not members:
                continue
            person = _by_dn(held, members[0])
            if person is None:
                note(f"Resolve a member of the {label}", False, "could not be read")
                continue
            note(
                f"Resolve a member of the {label}",
                True,
                f"{person.get('sAMAccountName', '')} "
                f"({person.get('userPrincipalName', '')})",
            )

            # And find them the way a sign-in finds them: by sign-in name,
            # under the configured search base. A group can hold somebody who
            # sits outside that base, and then every one of their sign-ins is
            # refused with "no such account" while every check above passes.
            username = person.get("sAMAccountName", "")
            try:
                under_base = find_person(held, username) if username else None
            except Unreachable as problem:
                under_base = None
                log.warning("the search base could not be read: %s", problem)
            note(
                "Find that member under the search base",
                under_base is not None,
                f"found under {where['search_base']}"
                if under_base is not None
                else (
                    f"NOT under {where['search_base']}: this account is in the "
                    "group but outside the search base, so every sign-in of "
                    "theirs would be refused"
                ),
            )
            try:
                found = groups_of(held, members[0])
            except Unreachable as problem:
                note(f"The nested rule on the {label}", False, str(problem))
                continue
            note(
                f"The nested rule on the {label}",
                group_dn in found,
                "the in-chain search lists the group"
                if group_dn in found
                else "the in-chain search did not list the group",
            )
    finally:
        with contextlib.suppress(Exception):
            held.unbind_s()

    return results


def _whoami(held) -> str:
    try:
        told = held.whoami_s()
    except Exception:  # noqa: BLE001 - not every server answers this
        return ""
    return told.strip() if told else ""


def _by_dn(held, dn: str) -> dict | None:
    import ldap

    try:
        answer = held.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", WHAT_IS_READ)
    except ldap.LDAPError:
        return None
    for found_dn, attributes in answer:
        if found_dn is None:
            continue
        return {name: _one(value) for name, value in attributes.items()}
    return None


# The Directory check ----------------------------------------------------------


def check_accounts(actor=None) -> dict:
    """Compare every directory-backed account against the directory.

    Fail-safe: if the directory cannot be reached, or the Sign-in group
    resolves to no members at all, the check refuses, changes nothing, and
    says so. A directory that answers "nobody is in this group" because a
    replication has not finished must never deactivate an office.
    """
    from core import audit
    from core.models import LoginSession, User

    where = facts()
    if not where["enabled"]:
        return {"ran": False, "why": "the directory is switched off"}

    try:
        held = connect()
    except Unreachable as problem:
        _refused(str(problem), actor)
        return {"ran": False, "why": str(problem)}

    try:
        try:
            signin_members = set(members_of(held, where["signin_group"]))
            admin_members = (
                set(members_of(held, where["admin_group"]))
                if where["admin_group"]
                else set()
            )
        except Unreachable as problem:
            _refused(str(problem), actor)
            return {"ran": False, "why": str(problem)}

        if not signin_members and not admin_members:
            why = "the sign-in group resolved to no members"
            _refused(why, actor)
            return {"ran": False, "why": why}

        changes = []
        for person in User.objects.filter(is_local=False):
            found = find_person(held, person.username)
            allowed = False
            in_admin_group = False

            if found is not None:
                control = found.get("userAccountControl", "")
                disabled = control.isdigit() and int(control) & ACCOUNT_DISABLED
                groups = groups_of(held, found["dn"])
                allowed = bool(groups) and not disabled
                in_admin_group = bool(
                    where["admin_group"] and where["admin_group"] in groups
                )

            changes += _bring_into_line(person, found, allowed, in_admin_group, actor)

        audit.write(
            audit.Category.ACCOUNTS,
            "Directory check ran",
            actor=actor,
            system=None if actor is not None else "directory check",
            signin_group_members=len(signin_members),
            admin_group_members=len(admin_members),
            accounts_checked=User.objects.filter(is_local=False).count(),
            changes=len(changes),
        )
        log.info(
            "the directory check ran: %d in the sign-in group, %d changes",
            len(signin_members),
            len(changes),
        )
        return {
            "ran": True,
            "signin_group_members": len(signin_members),
            "admin_group_members": len(admin_members),
            "changes": changes,
        }
    finally:
        with contextlib.suppress(Exception):
            held.unbind_s()

        # A session belonging to somebody the check deactivated is ended here
        # rather than left to the person's next request.
        for person in User.objects.filter(is_local=False, deactivated_at__isnull=False):
            LoginSession.objects.filter(user=person, ended__isnull=True).update(
                ended=_now(), end_reason=LoginSession.DEACTIVATED
            )


def _now():
    from django.utils import timezone

    return timezone.now()


def _bring_into_line(person, found, allowed, in_admin_group, actor) -> list[str]:
    """One account, brought into line with what the directory says.

    One audit row per change, and never a row for something that did not
    change. A Block is the app's own and is never lifted here.
    """
    from core import audit

    changes = []

    if not allowed and person.deactivated_at is None:
        person.deactivated_at = _now()
        person.save(update_fields=["deactivated_at"])
        changes.append(f"{person.username} deactivated")
        audit.write(
            audit.Category.ACCOUNTS,
            "user deactivated",
            actor=actor,
            system=None if actor is not None else "directory check",
            affected_user=person,
            why="gone, disabled, or outside both groups",
        )
    elif allowed and person.deactivated_at is not None:
        person.deactivated_at = None
        person.save(update_fields=["deactivated_at"])
        changes.append(f"{person.username} reactivated")
        audit.write(
            audit.Category.ACCOUNTS,
            "user reactivated",
            actor=actor,
            system=None if actor is not None else "directory check",
            affected_user=person,
        )

    if allowed and in_admin_group != person.in_admin_group:
        person.in_admin_group = in_admin_group
        person.save(update_fields=["in_admin_group"])
        changes.append(
            f"{person.username} "
            + (
                "became an Admin"
                if in_admin_group
                else "is no longer an Admin by group"
            )
        )
        audit.write(
            audit.Category.ACCOUNTS,
            "admin group membership changed",
            actor=actor,
            system=None if actor is not None else "directory check",
            affected_user=person,
            now=in_admin_group,
        )

    if allowed and found is not None:
        # What the directory says about a person is written again at every
        # check, so a change of name or address reaches the app overnight.
        fresh = {
            "directory_address": found.get("userPrincipalName", ""),
            "display_name": " ".join(
                part
                for part in (found.get("givenName", ""), found.get("sn", ""))
                if part
            ),
            "email": found.get("mail", ""),
        }
        if any(getattr(person, name) != value for name, value in fresh.items()):
            for name, value in fresh.items():
                setattr(person, name, value)
            person.save(update_fields=list(fresh))

    return changes


def _refused(why: str, actor=None) -> None:
    from core import audit

    log.warning("the directory check refused: %s", why)
    audit.write(
        audit.Category.ACCOUNTS,
        "Directory check refused",
        actor=actor,
        system=None if actor is not None else "directory check",
        outcome=audit.Outcome.FAILURE,
        reason_class=audit.Reason.DIRECTORY_UNREACHABLE,
        why=why,
    )
