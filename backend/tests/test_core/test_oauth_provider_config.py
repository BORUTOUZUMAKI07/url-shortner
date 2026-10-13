"""OAuth provider configuration guards.

`is_configured()` must require BOTH the client id and the client secret. A
provider with only an id set (the pre-fix state of google_oauth.py / github_oauth.py)
rendered a sign-in button whose consent round trip could only fail at token
exchange — dead UI whose error surfaced a full provider trip later.

The registry's `configured_providers()` (what `GET /auth/providers` serves) must
advertise only such providers, so the login page never renders that button in
the first place.
"""

from src.identity.services.sso import SSOProviderRegistry
from src.identity.services.sso.github_oauth import GitHubOAuthProvider
from src.identity.services.sso.google_oauth import GoogleOAuthProvider
from src.shared.core.config import settings


def test_google_configured_requires_id_and_secret(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", None)
    assert GoogleOAuthProvider().is_configured() is False

    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "client-secret")
    assert GoogleOAuthProvider().is_configured() is True

    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None)
    assert GoogleOAuthProvider().is_configured() is False


def test_github_configured_requires_id_and_secret(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", None)
    assert GitHubOAuthProvider().is_configured() is False

    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "client-secret")
    assert GitHubOAuthProvider().is_configured() is True

    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", None)
    assert GitHubOAuthProvider().is_configured() is False


def test_registry_advertises_only_configured_providers():
    class _Configured:
        def is_configured(self) -> bool:
            return True

    class _Unconfigured:
        def is_configured(self) -> bool:
            return False

    SSOProviderRegistry.register("_test_configured", _Configured)
    SSOProviderRegistry.register("_test_unconfigured", _Unconfigured)
    try:
        configured = SSOProviderRegistry.configured_providers()
        assert "_test_configured" in configured
        assert "_test_unconfigured" not in configured
    finally:
        # Never leak the fakes into the shared class-level registry — other
        # tests (and any /auth/providers route assertion) read this dict.
        SSOProviderRegistry.providers.pop("_test_configured", None)
        SSOProviderRegistry.providers.pop("_test_unconfigured", None)
