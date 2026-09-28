"""Accepting a workspace invite must NOT verify an email address.

`accept_invite` used to finish with `update(user.id, is_verified=True)`. That is
not a proof of anything: an invite establishes that *somebody else* knows the
address, not that the person accepting owns the inbox. Worse, it was a free
bypass of email verification — accept any invite and the flag flips, which would
have quietly defeated `REQUIRE_EMAIL_VERIFICATION` the moment it was ever turned
on.

`is_verified` is only ever set by clicking the emailed link (`verify_email`) or
by an OAuth provider reporting a verified claim.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.shared.errors import AlreadyMember, BadRequestError, InviteEmailMismatch, InviteExpired
from src.workspaces.models.workspace_invite import InviteStatus
from src.workspaces.services.workspace_service import WorkspaceService


def _future():
    return datetime.now(timezone.utc) + timedelta(days=1)


class _User:
    def __init__(self, email, is_verified=False):
        self.id = 5
        self.email = email
        self.is_verified = is_verified


class _Invite:
    def __init__(self, email="member@example.com", status=InviteStatus.pending,
                 expires_at=None):
        self.id = 77
        self.workspace_id = 3
        self.email = email
        self.role = "editor"
        self.status = status
        self.expires_at = expires_at if expires_at is not None else _future()


class _UserRepo:
    def __init__(self, user):
        self._user = user
        self.updates: list[tuple[int, dict]] = []

    async def get(self, user_id):
        return self._user

    async def update(self, user_id, **values):
        self.updates.append((user_id, values))
        obj = self._user
        for k, v in values.items():
            setattr(obj, k, v)
        return obj


class _MemberRepo:
    def __init__(self, already_member=False):
        self._already = already_member
        self.added: list[tuple[int, int]] = []

    async def is_member(self, workspace_id, user_id):
        return self._already

    async def add_member(self, workspace_id, user_id, role):
        self.added.append((workspace_id, user_id))


class _InviteRepo:
    def __init__(self, invite):
        self._invite = invite
        self.accepted: list[int] = []
        # Tests that need the claim to be refused set this, to model an invite
        # that stopped being pending between the read and the claim.
        self.claim_succeeds = True

    async def get_by_token(self, token):
        return self._invite

    async def get(self, invite_id):
        return self._invite

    async def claim_pending(self, invite_id):
        """Models the conditional UPDATE: True for the one winner, False for
        everyone who lost the race (or whose invite was cancelled)."""
        if not self.claim_succeeds:
            return False
        self.accepted.append(invite_id)
        return True

    async def update(self, invite_id, **values):
        return self._invite


class _Audit:
    def __init__(self):
        self.logged: list[dict] = []

    async def log(self, **kwargs):
        self.logged.append(kwargs)


class _Unused:
    """Stands in for the workspace repository, which accept_invite never touches."""

    async def list_all(self, *a, **k):
        return []


class _WebhookSvc:
    def __init__(self):
        self.calls = []

    async def deliver_event(self, workspace_id, event_type, payload):
        self.calls.append((workspace_id, event_type, payload))


def _service(user, invite=None, already_member=False):
    users = _UserRepo(user)
    members = _MemberRepo(already_member)
    invites = _InviteRepo(invite if invite is not None else _Invite(email=user.email))
    audit = _Audit()
    svc = WorkspaceService(
        repo=_Unused(),
        member_repo=members,
        invite_repo=invites,
        user_repo=users,
        audit=audit,
        webhook_svc=_WebhookSvc(),
    )
    return svc, users, members, invites, audit


class TestAcceptInviteDoesNotVerifyEmail:
    async def test_does_not_set_is_verified(self):
        """The core bug: an invite must not be treated as proof of ownership."""
        svc, users, members, invites, audit = _service(_User("member@example.com"))
        await svc.accept_invite("tok", user_id=5)

        assert invites.accepted == [77]
        assert members.added == [(3, 5)]
        # Membership was granted...
        assert users.updates == []
        # ...but nothing about the email's verification status changed.
        assert all("is_verified" not in values for _, values in users.updates)

    async def test_leaves_flag_false_for_unverified_user(self):
        user = _User("member@example.com", is_verified=False)
        svc, *_ = _service(user)
        await svc.accept_invite("tok", user_id=5)
        assert user.is_verified is False

    async def test_preserves_existing_verified_flag(self):
        """A genuinely verified user stays verified — the change is not a reset."""
        user = _User("member@example.com", is_verified=True)
        svc, *_ = _service(user)
        await svc.accept_invite("tok", user_id=5)
        assert user.is_verified is True

    async def test_still_audits_acceptance(self):
        svc, _, _, _, audit = _service(_User("member@example.com"))
        await svc.accept_invite("tok", user_id=5)
        assert [e["action"] for e in audit.logged] == ["accept_invite"]


class TestAcceptInvitePreconditionsStillHold:
    async def test_email_mismatch_rejected(self):
        svc, users, members, *_ = _service(
            _User("someone-else@example.com"), invite=_Invite(email="member@example.com")
        )
        with pytest.raises(InviteEmailMismatch):
            await svc.accept_invite("tok", user_id=5)
        assert members.added == []
        assert users.updates == []

    async def test_expired_invite_rejected(self):
        invite = _Invite(email="member@example.com", expires_at=_future() - timedelta(days=1))
        svc, _, members, *_ = _service(_User("member@example.com"), invite=invite)
        with pytest.raises(InviteExpired):
            await svc.accept_invite("tok", user_id=5)
        assert members.added == []

    async def test_already_a_member_rejected(self):
        svc, *_ = _service(_User("member@example.com"), already_member=True)
        with pytest.raises(AlreadyMember):
            await svc.accept_invite("tok", user_id=5)


class TestAcceptInviteClaimIsTheGate:
    """A cancelled invite must not hand out membership.

    `accept_invite` used to insert the membership and commit, and only then call
    `invite_repo.accept(token)`, discarding its return value. That return value
    was the single signal that the invite was no longer pending, so an admin's
    cancel landing between the status read and that call still granted access —
    while the invite row stayed `cancelled`.

    The claim is now a conditional UPDATE and it happens first, so a lost race
    is refused before any membership row is written.
    """

    async def test_cancelled_invite_grants_nothing(self):
        svc, _, members, invites, _ = _service(_User("member@example.com"))
        # The invite was still `pending` when it was read, but the claim loses.
        invites.claim_succeeds = False

        with pytest.raises(BadRequestError, match="no longer valid"):
            await svc.accept_invite("tok", user_id=5)

        assert members.added == [], "membership was granted for a dead invite"

    async def test_claim_happens_before_the_member_insert(self):
        """Ordering is the fix — a commit-first order reintroduces the bug."""
        svc, _, members, invites, _ = _service(_User("member@example.com"))
        order: list[str] = []

        original_claim = invites.claim_pending
        original_add = members.add_member

        async def claim(invite_id):
            order.append("claim")
            return await original_claim(invite_id)

        async def add(*a, **kw):
            order.append("add_member")
            return await original_add(*a, **kw)

        invites.claim_pending = claim
        members.add_member = add

        await svc.accept_invite("tok", user_id=5)
        assert order == ["claim", "add_member"]
