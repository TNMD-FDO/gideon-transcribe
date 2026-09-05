"""Accounts, Login sessions, and the sign-in throttle.

An account is made at a person's first successful sign-in, not before: nobody
pre-provisions users, and nothing here changes when the office adds somebody to
the Sign-in group. A Local admin is the exception, and exists so that IT can
sign in when the directory cannot be reached.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone

# How far back the two throttle counts look, and how long a wait they impose.
#
# The second count exists because two addresses could otherwise push one
# username past the domain's own lockout policy, which locks an account for
# thirty minutes after six wrong passwords in thirty minutes. Together they
# keep the rule that nobody can lock a directory account through this app.
THROTTLE_FAILURES = 5
THROTTLE_WINDOW = timedelta(minutes=30)
THROTTLE_WAIT = timedelta(minutes=15)


def normalise_username(typed: str) -> str:
    """`user`, `user@domain`, and `DOMAIN\\user` all become `user`.

    The specification leaves open how the app knows the suffix and the prefix
    to strip, and `.env` carries neither. It does not need to: whatever
    precedes a backslash is a domain and whatever follows an at-sign is a
    domain, in every form a person types. Nothing is stripped that could be
    part of a username, because neither character is allowed in one.
    """
    name = (typed or "").strip()
    if "\\" in name:
        name = name.rsplit("\\", 1)[1]
    if "@" in name:
        name = name.split("@", 1)[0]
    return name.lower()


class UserManager(BaseUserManager):
    def create_local_admin(self, username: str, password: str) -> User:
        """An Admin account kept inside the app, independent of the directory.

        Every local account is an Admin: the point of one is to be able to
        reach the Admin panel when the directory is down, and an account that
        could sign in but do nothing would not serve that.
        """
        username = normalise_username(username)
        if not username:
            raise ValueError("a Local admin needs a name")
        if not password:
            raise ValueError("a Local admin needs a password")

        user = self.model(username=username, is_local=True, display_name=username)
        user.set_password(password)
        user.save()
        return user

    def from_directory(self, username: str, **facts) -> User:
        """The account behind a directory sign-in, made if it is not there yet.

        Everything the directory says is written again at every sign-in, so a
        change of name or address in the directory reaches the app without
        anybody doing anything.
        """
        username = normalise_username(username)
        user, _ = self.get_or_create(username=username, defaults={"is_local": False})
        for field, value in facts.items():
            setattr(user, field, value)
        user.save()
        return user


class User(AbstractBaseUser):
    """One person who may sign in.

    Django's permission framework is deliberately absent. There are two roles,
    User and Admin, and admin status has exactly three sources; a second system
    of groups and permissions beside that would be a way for the two to
    disagree.
    """

    username = models.CharField(max_length=150, unique=True)

    # What the directory says. A Local admin has none of it.
    directory_address = models.CharField(max_length=320, blank=True, default="")
    display_name = models.CharField(max_length=200, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    is_local = models.BooleanField(default=False)

    # The three sources of admin status. The group only ever adds: a manual
    # flag cannot demote a member of the Admin group, so removing a group
    # member's admin status means removing them from the group in the
    # directory.
    in_admin_group = models.BooleanField(default=False)
    admin_flag = models.BooleanField(default=False)

    # Deactivated is the Directory check's doing and is lifted automatically
    # when the directory admits the person again. Blocked is an Admin's doing
    # and only an Admin lifts it.
    deactivated_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)

    # A per-person override on the Users page, which wins over the default
    # Workspace quota. Empty means the default, whatever it is at the time.
    quota_gb = models.IntegerField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    last_sign_in = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "username"

    class Meta:
        ordering = ["username"]

    def __str__(self) -> str:
        return self.username

    @property
    def is_active(self) -> bool:
        """Whether this account may sign in at all."""
        return self.deactivated_at is None and self.blocked_at is None

    @property
    def is_admin(self) -> bool:
        return self.is_local or self.in_admin_group or self.admin_flag

    @property
    def admin_source(self) -> str | None:
        """Which of the three sources gives this person admin status.

        In this order, because it is the order in which they cannot be
        overruled: a local account is always an Admin, a group member cannot be
        demoted by hand, and the manual flag is what is left.
        """
        if self.is_local:
            return "local"
        if self.in_admin_group:
            return "group"
        if self.admin_flag:
            return "manual"
        return None

    @property
    def status(self) -> str:
        if self.blocked_at is not None:
            return "blocked"
        if self.deactivated_at is not None:
            return "deactivated"
        return "active"

    @property
    def shown_name(self) -> str:
        return self.display_name or self.username


class LoginSession(models.Model):
    """One person's session, of which they have exactly one at a time.

    This is not Django's session. Django's session is how a browser is
    recognised; this is the thing the Workspace hangs off, the thing an idle
    timeout ends, and the thing an Admin can end from the users list.
    """

    LOGOUT = "logout"
    IDLE = "idle"
    ELSEWHERE = "elsewhere"
    DEACTIVATED = "deactivated"
    BLOCKED = "blocked"
    ADMIN_ENDED = "admin_ended"

    END_REASONS = [
        (LOGOUT, "signed out"),
        (IDLE, "idle for too long"),
        (ELSEWHERE, "signed in elsewhere"),
        (DEACTIVATED, "deactivated"),
        (BLOCKED, "blocked"),
        (ADMIN_ENDED, "ended by an Admin"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=40, db_index=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    started = models.DateTimeField(auto_now_add=True)
    # The idle clock. Every request the person makes moves it; an Admin looking
    # at their Workspace does not, because that is not their activity.
    last_request = models.DateTimeField(default=timezone.now)

    ended = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=20, choices=END_REASONS, blank=True)

    class Meta:
        ordering = ["-started"]
        indexes = [models.Index(fields=["user", "ended"])]

    def __str__(self) -> str:
        return f"{self.user.username} from {self.started:%Y-%m-%d %H:%M}"

    @property
    def is_open(self) -> bool:
        return self.ended is None

    def idle_for(self) -> timedelta:
        return timezone.now() - self.last_request

    def end(self, reason: str) -> None:
        if self.ended is not None:
            return
        self.ended = timezone.now()
        self.end_reason = reason
        self.save(update_fields=["ended", "end_reason"])


class SignInAttempt(models.Model):
    """A failed sign-in, kept only long enough to throttle on.

    Successful sign-ins are not kept here: the audit log is the record of who
    signed in, and this table exists for one arithmetic question.
    """

    username = models.CharField(max_length=150, db_index=True)
    address = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at"]

    @classmethod
    def record(cls, username: str, address: str | None) -> None:
        cls.objects.create(username=normalise_username(username), address=address)

    @classmethod
    def wait_for(cls, username: str, address: str | None) -> timedelta | None:
        """How long this username must wait, or None if it may try now.

        Two counts, both ending in the same wait: five failures for one
        username and address together, and five for the username from anywhere
        within half an hour.
        """
        username = normalise_username(username)
        since = timezone.now() - THROTTLE_WINDOW
        recent = cls.objects.filter(username=username, at__gte=since)

        for attempts in (recent.filter(address=address), recent):
            failures = list(attempts.order_by("-at")[:THROTTLE_FAILURES])
            if len(failures) < THROTTLE_FAILURES:
                continue
            waited = timezone.now() - failures[0].at
            if waited < THROTTLE_WAIT:
                return THROTTLE_WAIT - waited
        return None


# Django registers a model when the module defining it is imported, and it
# infers the app from the package the module sits in. These live in modules of
# their own because they are separate ideas, and they are imported here so that
# whether Django knows about them does not depend on which other module
# happened to be loaded first.
from core.assistant import (  # noqa: E402, F401
    Chat,
    ChatTurn,
    PromptTemplate,
    Suggestion,
    SuggestionRun,
    Summary,
    SummaryTemplate,
)
from core.audit import Row  # noqa: E402, F401
from core.branding import Branding  # noqa: E402, F401
from core.case_chat import CaseChat, CaseChatTurn  # noqa: E402, F401
from core.cases import Case, OffSpell  # noqa: E402, F401
from core.clips import Clip  # noqa: E402, F401
from core.engine import EngineStatus  # noqa: E402, F401
from core.jobs import Job, Run, Segment, Transcript  # noqa: E402, F401
from core.people import Person  # noqa: E402, F401
from core.recordings import Batch, Recording, Side  # noqa: E402, F401
from core.settings_store import Setting  # noqa: E402, F401
