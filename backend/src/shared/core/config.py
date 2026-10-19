import tempfile
import warnings
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "LinkForge URL Shortener"

    # --- PostgreSQL (Neon / Supabase / local Docker) ---
    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: str = "linkforge_user"
    POSTGRES_PASSWORD: str = "linkforge_password"
    POSTGRES_DB: str = "linkforge_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    ASYNC_DATABASE_URI: str = ""

    @field_validator("ASYNC_DATABASE_URI", mode="before")
    @classmethod
    def build_async_uri(cls, v, info):
        if v:
            return v
        base_url = info.data.get("DATABASE_URL")
        user = info.data.get("POSTGRES_USER", "linkforge_user")
        password = info.data.get("POSTGRES_PASSWORD", "linkforge_password")
        host = info.data.get("POSTGRES_HOST", "localhost")
        port = info.data.get("POSTGRES_PORT", 5432)
        db = info.data.get("POSTGRES_DB", "linkforge_db")

        if base_url:
            base = base_url.replace("postgresql://", "postgresql+asyncpg://")
            q = ""
            if "?" in base:
                base, q = base.split("?", 1)
                params = q.split("&")
                ssl_params = [p for p in params if p.startswith("sslmode=")]
                other_params = [p for p in params if not p.startswith("sslmode=") and not p.startswith("channel_binding=")]
                if ssl_params and "require" in ssl_params[0]:
                    other_params.append("ssl=require")
                q = ("?" + "&".join(other_params)) if other_params else ""
            return f"{base}{q}"
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

    # --- MongoDB (Atlas / Aiven) ---
    MONGODB_URI: str = "mongodb://admin:adminpassword@localhost:27017"
    MONGODB_DB: str = "linkforge_analytics"

    # --- Redis (Upstash / Aiven / local Docker) ---
    REDIS_URL: str = "redis://localhost:6379"
    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None

    # --- Rate Limiting Tiers ---
    RATE_LIMIT_IP_CAPACITY: int = 60
    RATE_LIMIT_IP_REFILL: float = 1.0
    RATE_LIMIT_USER_CAPACITY: int = 100
    RATE_LIMIT_USER_REFILL: float = 1.67

    # --- Kafka (Aiven with SSL, or local Docker plain-text) ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:29092"
    KAFKA_SASL_USERNAME: Optional[str] = None
    KAFKA_SASL_PASSWORD: Optional[str] = None
    KAFKA_SSL_CA_PATH: Optional[str] = None
    KAFKA_SSL_CA: Optional[str] = None
    SCHEMA_REGISTRY_URL: Optional[str] = None

    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"

    @field_validator("KAFKA_SECURITY_PROTOCOL", mode="before")
    @classmethod
    def build_security_protocol(cls, v, info):
        if v and v != "PLAINTEXT":
            return v
        return "SASL_SSL" if info.data.get("KAFKA_SASL_USERNAME") else "PLAINTEXT"

    KAFKA_SASL_MECHANISM: str = "GSSAPI"

    @field_validator("KAFKA_SASL_MECHANISM", mode="before")
    @classmethod
    def build_sasl_mechanism(cls, v, info):
        if v and v != "GSSAPI":
            return v
        return "PLAIN" if info.data.get("KAFKA_SASL_USERNAME") else "GSSAPI"

    @model_validator(mode="after")
    def webhook_secret_fallback(self):
        if not self.WEBHOOK_SECRET_KEY:
            self.WEBHOOK_SECRET_KEY = self.SECRET_KEY
        return self

    @model_validator(mode="after")
    def validate_secret_key(self):
        """Refuse to boot a production instance that would sign tokens (and
        webhook HMACs) with an empty or trivially short key.

        ``SECRET_KEY`` defaults to ``""`` and ``webhook_secret_fallback`` copies
        it into ``WEBHOOK_SECRET_KEY``, so a deploy that forgot the env var used
        to come up healthy and sign every JWT with a publicly known key — a
        complete authentication bypass. Non-production keeps the blank default
        so local/test runs stay zero-config, but it logs loudly.
        """
        if not self.SECRET_KEY:
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "SECRET_KEY is required when ENVIRONMENT=production. "
                    "Generate one with: openssl rand -hex 32"
                )
            warnings.warn(
                "SECRET_KEY is empty - tokens are signed with a publicly known key. "
                "This is only acceptable for local development.",
                stacklevel=2,
            )
        elif len(self.SECRET_KEY) < 32 and self.ENVIRONMENT == "production":
            raise ValueError(
                "SECRET_KEY must be at least 32 characters in production "
                f"(got {len(self.SECRET_KEY)}). Generate one with: openssl rand -hex 32"
            )
        return self

    @model_validator(mode="after")
    def validate_cookie_ttls(self):
        """The refresh cookie must not outlive the refresh JWT it carries.

        The cookie is what a stale browser keeps replaying; if it lives longer
        than the token, every request after expiry presents a dead credential
        instead of simply being absent. The access cookie is deliberately longer
        than the access JWT - that is how silent refresh works (the expired
        access token triggers a 401, the client swaps it using the refresh
        cookie), so only the refresh pair is constrained here.
        """
        if self.REFRESH_COOKIE_MAX_AGE > self.REFRESH_TOKEN_EXPIRE_DAYS * 86400:
            raise ValueError(
                f"REFRESH_COOKIE_MAX_AGE ({self.REFRESH_COOKIE_MAX_AGE}s) must not exceed "
                f"REFRESH_TOKEN_EXPIRE_DAYS ({self.REFRESH_TOKEN_EXPIRE_DAYS}d) - a cookie that "
                "outlives its token replays a dead credential for the difference."
            )
        return self

    @model_validator(mode="after")
    def write_ca_cert(self):
        ca_content = self.KAFKA_SSL_CA
        if ca_content and not self.KAFKA_SSL_CA_PATH:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", prefix="kafka-ca-")
            tmp.write(ca_content.encode() if isinstance(ca_content, str) else ca_content)
            tmp.close()
            object.__setattr__(self, "KAFKA_SSL_CA_PATH", tmp.name)
        return self

    # --- SMTP (Email) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@linkforge.dev"
    FROM_NAME: str = "LinkForge"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://127.0.0.1:8000"

    # When True (Render), the rightmost X-Forwarded-For hop is appended by the
    # trusted reverse proxy and reflects the real client. Set to False when
    # deployed without a proxy so spoofed XFF values are ignored entirely.
    TRUST_PROXY: bool = True

    # --- IP geolocation (ipinfo.io) ---
    IPINFO_TOKEN: str = ""

    # --- JWT ---
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Refresh token lifetime. Also drives the refresh session record TTL in
    # Redis, the reuse-detection grace window budget, and the refresh cookie.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Auth cookie lifetimes (seconds). ACCESS_COOKIE_MAX_AGE intentionally
    # exceeds ACCESS_TOKEN_EXPIRE_MINUTES: the browser keeps presenting the
    # expired access token, the API answers 401, and the client refreshes.
    # REFRESH_COOKIE_MAX_AGE is validated against REFRESH_TOKEN_EXPIRE_DAYS.
    ACCESS_COOKIE_MAX_AGE: int = 604800  # 7 days
    REFRESH_COOKIE_MAX_AGE: int = 604800  # 7 days, matches REFRESH_TOKEN_EXPIRE_DAYS

    # --- Admin bootstrap ---
    # POST /admin/seed promotes the caller to superadmin. It must NOT be open to
    # any authenticated user: on a fresh database the first person to register
    # would otherwise own the platform. Requires this shared secret, which only
    # the operator has. Empty (the default) disables the endpoint entirely.
    ADMIN_BOOTSTRAP_TOKEN: str = ""

    # --- Email verification gate ---
    # OFF by default: is_verified is currently advisory only and turning the
    # gate on would lock out every account that registered before the check
    # existed. Flip to True once existing accounts have been verified.
    REQUIRE_EMAIL_VERIFICATION: bool = False

    # --- Webhook encryption (separate from JWT SECRET_KEY) ---
    WEBHOOK_SECRET_KEY: str = ""

    # --- Google OAuth 2.0 ---
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # --- GitHub OAuth 2.0 ---
    GITHUB_OAUTH_CLIENT_ID: Optional[str] = None
    GITHUB_OAUTH_CLIENT_SECRET: Optional[str] = None
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/github/callback"

    # --- Observability (3 layers: in-process → collector → New Relic) ---
    ENVIRONMENT: str = "production"
    # Layer-1 switch. When ON the app records metrics/traces/logs via the OTel
    # SDK and pushes OTLP at OTEL_EXPORTER_OTLP_ENDPOINT — normally the local
    # Layer-2 collector (http://localhost:4318 / otel-collector:4318), or New
    # Relic's own OTLP endpoint (https://otlp.nr-data.net:4318 + api-key
    # header) when running without the collector. Exporters are fail-open: the
    # app never blocks or crashes on telemetry.
    OTLP_ENABLED: bool = True
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    # Default header matches the collector's default basicauth (linkforge:linkforge).
    # This is a dev-only default: if you enable basicauth on the collector with a
    # different OTLP_HTTP_AUTH_HTPASSWD, you MUST change this to match, or
    # telemetry will return 401s (fail-open → silently dropped).
    _DEFAULT_OTLP_BASIC = "Authorization=Basic bGlua2ZvcmdlOmxpbmtmb3JnZQ=="
    OTEL_EXPORTER_OTLP_HEADERS: Optional[str] = _DEFAULT_OTLP_BASIC
    # Fraction of spans the app emits. 1.0 = send everything and let the
    # Layer-2 collector tail-sample (keeps 100% of errors, trims the rest).
    # Lower this only when pushing straight to a vendor with no collector.
    OTEL_TRACES_SAMPLE_RATIO: float = 1.0

    # --- Log PII/secret redaction ---
    # Every log record is shipped off-box (OTLP → New Relic), so scrubbing
    # happens at the handler boundary rather than at each call site. Turn off
    # only if the regexes mangle something you genuinely need in the log stream.
    PII_REDACTION_ENABLED: bool = True
    PII_REDACTION_REPLACEMENT: str = "***"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# base64("linkforge:linkforge") — the basicauth credential shipped as the
# collector's dev fallback (docker/otel-collector-config.yaml) and as this
# app's default OTEL_EXPORTER_OTLP_HEADERS. Matching by construction so that
# `docker compose up` works with zero config; the flip side is that a
# deployment overriding neither exposes a receiver guarded by a password
# published in this repo.
_DEV_OTLP_BASIC_CREDENTIAL = "bGlua2ZvcmdlOmxpbmtmb3JnZQ=="
_LOCAL_OTLP_HOSTS = frozenset(
    {"localhost", "127.0.0.1", "otel-collector", "host.docker.internal"}
)


def warn_if_default_otlp_credential(
    endpoint: Optional[str] = None,
    headers: Optional[str] = None,
) -> None:
    """Warn when a non-local OTLP endpoint is paired with unusable auth.

    Two cases, both silent by default and both fixed the same way (set a real
    ``OTLP_HTTP_AUTH_HTPASSWD`` on the collector and the matching
    ``Authorization=Basic`` header here):

    * the header carries the shipped dev credential ``linkforge:linkforge`` —
      render.yaml deploys the receiver publicly, so until overridden it is
      guarded by a password anyone reading the repo knows, and junk pushes burn
      the New Relic free quota;
    * the header is empty (a blueprint var left blank) — the receiver's
      basicauth then rejects every push with 401, which costs *all* telemetry
      while the app keeps serving normally.

    Warns once at startup, on stderr: a signal, never a refusal, because
    telemetry stays fail-open (it must not block boot).
    """
    ep = (settings.OTEL_EXPORTER_OTLP_ENDPOINT if endpoint is None else endpoint) or ""
    hdr = (settings.OTEL_EXPORTER_OTLP_HEADERS if headers is None else headers) or ""
    host = ep.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower()
    if not host or host in _LOCAL_OTLP_HOSTS:
        return
    if not hdr.strip():
        warnings.warn(
            f"OTEL_EXPORTER_OTLP_ENDPOINT points at non-local host '{host}' but "
            f"OTEL_EXPORTER_OTLP_HEADERS is empty: the collector's basicauth "
            f"will reject every push (401) and no telemetry will arrive. Set "
            f"Authorization=Basic <base64(user:pass)> here to match the "
            f"collector's OTLP_HTTP_AUTH_HTPASSWD.",
            UserWarning,
            stacklevel=2,
        )
        return
    if _DEV_OTLP_BASIC_CREDENTIAL not in hdr:
        return
    warnings.warn(
        f"OTEL_EXPORTER_OTLP_HEADERS carries the shipped dev credential "
        f"(linkforge:linkforge) while OTEL_EXPORTER_OTLP_ENDPOINT points at "
        f"non-local host '{host}': the OTLP receiver is protected by a "
        f"password published in this repo. Set a real "
        f"OTLP_HTTP_AUTH_HTPASSWD on the collector and the matching "
        f"Authorization=Basic header here.",
        UserWarning,
        stacklevel=2,
    )


settings = Settings()
warn_if_default_otlp_credential()
