from .github_oauth import GitHubOAuthProvider
from .google_oauth import GoogleOAuthProvider


class SSOProviderRegistry:
    providers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type):
        cls.providers[name] = provider_cls

    @classmethod
    def get(cls, name: str):
        provider_cls = cls.providers.get(name)
        if not provider_cls:
            return None
        return provider_cls()

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls.providers.keys())

    @classmethod
    def configured_providers(cls) -> list[str]:
        """Providers with a fully-specified config (id AND secret).

        The frontend renders a sign-in button per entry here. Advertising a
        provider whose secret is unset would send users on a whole consent round
        trip that can only fail at token exchange.
        """
        return [name for name, provider_cls in cls.providers.items() if provider_cls().is_configured()]


SSOProviderRegistry.register("google", GoogleOAuthProvider)
SSOProviderRegistry.register("github", GitHubOAuthProvider)
