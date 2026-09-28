"""Concurrent signup: a unique-violation IntegrityError is a 409, not a 500.

register() pre-checks `email_exists` and then INSERTs. Two requests with the
same address can both pass the check before either INSERT commits; the unique
constraint then lets one succeed and the other hit IntegrityError. Uncaught,
that surfaced as a 500 for a condition the pre-check already deemed an error
— and the pre-check only exists to produce that exact response.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from src.identity.services.auth_service import AuthService
from src.shared.errors import EmailAlreadyExists


class RacingUserRepo:
    """Models the loser of a signup race: `email_exists` says free, the INSERT
    hits the unique constraint because the other caller committed first."""

    def __init__(self):
        self.rolled_back = False

    async def email_exists(self, email):
        return False

    async def create(self, **kwargs):
        raise IntegrityError(
            'duplicate key value violates unique constraint "uq_users_email"',
            None,
            RuntimeError("orig"),
        )

    async def rollback(self):
        self.rolled_back = True

    async def get_by_email(self, email):
        return None


class AssertNoDefaultWorkspace:
    async def create_default(self, user_id):
        raise AssertionError("create_default must not run when the INSERT failed")


async def test_concurrent_register_maps_integrity_error_to_409():
    repo = RacingUserRepo()
    svc = AuthService(user_repo=repo, workspace_repo=AssertNoDefaultWorkspace())

    with pytest.raises(EmailAlreadyExists):
        await svc.register("dup@example.com", "StrongPass1!")

    assert repo.rolled_back, "the failed transaction must be rolled back"
