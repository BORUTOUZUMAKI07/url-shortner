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


SSOProviderRegistry.register("google", GoogleOAuthProvider)
SSOProviderRegistry.register("github", GitHubOAuthProvider)
