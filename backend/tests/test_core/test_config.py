from unittest.mock import patch

import pytest

from src.shared.core.config import Settings


def _settings(**overrides) -> Settings:
    """Build Settings for assertions about *defaults*.

    ENVIRONMENT is pinned to a non-production value because the class default
    is "production", and production mode now refuses to construct without a
    real SECRET_KEY (see TestProductionSecretKeyGuard). Every test in this file
    is asserting a default, not a production boot, so the helper makes that
    explicit rather than relying on the ambient environment.
    """
    overrides.pop("_env_file", None)
    overrides.setdefault("ENVIRONMENT", "development")
    return Settings(_env_file=None, **overrides)


class TestSettingsDefaults:
    def test_project_name_default(self):
        s = _settings()
        assert s.PROJECT_NAME == "LinkForge URL Shortener"

    def test_database_defaults(self):
        s = _settings()
        assert s.POSTGRES_USER == "linkforge_user"
        assert s.POSTGRES_PASSWORD == "linkforge_password"
        assert s.POSTGRES_DB == "linkforge_db"
        assert s.POSTGRES_HOST == "localhost"
        assert s.POSTGRES_PORT == 5432

    def test_redis_defaults(self, monkeypatch):
        monkeypatch.delenv("REDIS_URL", raising=False)
        s = _settings()
        assert s.REDIS_URL == "redis://localhost:6379"

    def test_jwt_defaults(self):
        s = _settings()
        assert s.ALGORITHM == "HS256"
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_rate_limit_defaults(self):
        s = _settings()
        assert s.RATE_LIMIT_IP_CAPACITY == 60
        assert s.RATE_LIMIT_IP_REFILL == 1.0

    def test_kafka_defaults(self):
        s = _settings()
        assert s.KAFKA_BOOTSTRAP_SERVERS == "localhost:29092"
        assert s.KAFKA_SECURITY_PROTOCOL == "PLAINTEXT"
        assert s.KAFKA_SASL_MECHANISM == "GSSAPI"

    def test_smtp_defaults(self):
        s = _settings()
        assert s.SMTP_HOST == ""
        assert s.SMTP_PORT == 587
        assert s.FROM_EMAIL == "noreply@linkforge.dev"

    def test_oauth_defaults(self):
        s = _settings()
        assert s.GOOGLE_OAUTH_CLIENT_ID is None
        assert s.GOOGLE_OAUTH_REDIRECT_URI == "http://localhost:8000/api/v1/auth/oauth/google/callback"

    def test_frontend_url_default(self):
        s = _settings()
        assert s.FRONTEND_URL == "http://localhost:3000"
        assert s.BACKEND_URL == "http://127.0.0.1:8000"


class TestSettingsOverrides:
    def test_project_name_override(self):
        s = _settings(PROJECT_NAME="Custom Project", _env_file=None)
        assert s.PROJECT_NAME == "Custom Project"

    def test_async_database_uri_from_full_url(self):
        s = _settings(DATABASE_URL="postgresql://user:pass@remote:5432/db", _env_file=None)
        assert "postgresql+asyncpg://user:pass@remote:5432/db" == s.ASYNC_DATABASE_URI

    def test_async_database_uri_handles_sslmode(self):
        s = _settings(DATABASE_URL="postgresql://user:pass@host/db?sslmode=require", _env_file=None)
        uri = s.ASYNC_DATABASE_URI
        assert "ssl=require" in uri
        assert "sslmode" not in uri

    def test_async_database_uri_strips_channel_binding(self):
        s = _settings(DATABASE_URL="postgresql://user:pass@host/db?channel_binding=require", _env_file=None)
        assert "channel_binding" not in s.ASYNC_DATABASE_URI

    def test_async_database_uri_fallback_construction(self):
        s = _settings(
            DATABASE_URL=None,
            POSTGRES_USER="usr",
            POSTGRES_PASSWORD="pwd",
            POSTGRES_HOST="pg.example.com",
            POSTGRES_PORT=15432,
            POSTGRES_DB="mydb",
            _env_file=None,
        )
        expected = "postgresql+asyncpg://usr:pwd@pg.example.com:15432/mydb"
        assert expected == s.ASYNC_DATABASE_URI

    def test_kafka_security_protocol_sasl_ssl(self):
        s = _settings(KAFKA_SASL_USERNAME="user", KAFKA_SASL_PASSWORD="pass", _env_file=None)
        assert s.KAFKA_SECURITY_PROTOCOL == "SASL_SSL"
        assert s.KAFKA_SASL_MECHANISM == "PLAIN"

    def test_kafka_security_protocol_plaintext(self):
        s = _settings(KAFKA_SASL_USERNAME=None, KAFKA_SASL_PASSWORD=None, _env_file=None)
        assert s.KAFKA_SECURITY_PROTOCOL == "PLAINTEXT"
        assert s.KAFKA_SASL_MECHANISM == "GSSAPI"

    def test_oauth_client_id_override(self):
        s = _settings(GOOGLE_OAUTH_CLIENT_ID="google-id.apps.googleusercontent.com", _env_file=None)
        assert s.GOOGLE_OAUTH_CLIENT_ID == "google-id.apps.googleusercontent.com"

    def test_mongodb_uri(self):
        s = _settings(MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net", _env_file=None)
        assert s.MONGODB_URI == "mongodb+srv://user:pass@cluster.mongodb.net"

    def test_type_coercion(self):
        s = _settings(RATE_LIMIT_IP_CAPACITY="120", _env_file=None)
        assert s.RATE_LIMIT_IP_CAPACITY == 120
        assert isinstance(s.RATE_LIMIT_IP_CAPACITY, int)

    def test_upstash_config(self):
        s = _settings(
            UPSTASH_REDIS_REST_URL="https://us1-wonder-123.upstash.io",
            UPSTASH_REDIS_REST_TOKEN="token123",
            _env_file=None,
        )
        assert s.UPSTASH_REDIS_REST_URL == "https://us1-wonder-123.upstash.io"
        assert s.UPSTASH_REDIS_REST_TOKEN == "token123"

    def test_otel_config(self):
        s = _settings(OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318", _env_file=None)
        assert s.OTEL_EXPORTER_OTLP_ENDPOINT == "http://otel-collector:4318"

    def test_otlp_enabled_by_default(self):
        s = _settings()
        assert s.OTLP_ENABLED is True

    def test_settings_model_config(self):
        s = _settings()
        assert s.model_config.get("case_sensitive") is True
        assert s.model_config.get("extra") == "ignore"


class TestSettingsEdgeCases:
    def test_database_url_with_ssl_and_other_params(self):
        s = _settings(DATABASE_URL="postgresql://u:p@host/db?sslmode=require&connect_timeout=10", _env_file=None)
        uri = s.ASYNC_DATABASE_URI
        assert "ssl=require" in uri
        assert "connect_timeout=10" in uri
        assert "sslmode" not in uri

    def test_database_url_no_params(self):
        s = _settings(DATABASE_URL="postgresql://u:p@host/db", _env_file=None)
        assert s.ASYNC_DATABASE_URI == "postgresql+asyncpg://u:p@host/db"

    def test_database_url_with_multiple_ssl_params(self):
        s = _settings(DATABASE_URL="postgresql://u:p@host/db?sslmode=require&sslmode=prefer", _env_file=None)
        uri = s.ASYNC_DATABASE_URI
        assert uri.count("ssl=require") == 1

    def test_rate_limit_user_defaults(self):
        s = _settings()
        assert s.RATE_LIMIT_USER_FREE_CAPACITY == 100
        assert s.RATE_LIMIT_USER_PREMIUM_CAPACITY == 1000

    def test_smtp_password_default_empty(self):
        s = _settings()
        assert s.SMTP_PASSWORD == ""

    def test_secret_key_default_empty(self):
        s = _settings()
        assert s.SECRET_KEY == ""

    def test_kafka_ssl_ca_path_default_none(self):
        s = _settings()
        assert s.KAFKA_SSL_CA_PATH is None

    def test_schema_registry_url_default_none(self):
        s = _settings()
        assert s.SCHEMA_REGISTRY_URL is None

    def test_environment_default_is_production(self):
        # Asserted through the raw class: production mode is the default, and
        # that is exactly why it also hard-fails without a SECRET_KEY.
        s = Settings(SECRET_KEY="x" * 64, _env_file=None)
        assert s.ENVIRONMENT == "production"


class TestProductionSecretKeyGuard:
    """SECRET_KEY defaulted to "" and webhook_secret_fallback copied it into
    WEBHOOK_SECRET_KEY, so a deploy that forgot the env var booted healthy and
    signed every JWT (and webhook HMAC) with a publicly known key."""

    def test_production_rejects_empty_secret_key(self):
        with pytest.raises(ValueError, match="SECRET_KEY is required"):
            Settings(ENVIRONMENT="production", _env_file=None)

    def test_production_rejects_short_secret_key(self):
        with pytest.raises(ValueError, match="at least 32 characters"):
            Settings(ENVIRONMENT="production", SECRET_KEY="too-short", _env_file=None)

    def test_production_accepts_strong_secret_key(self):
        s = Settings(ENVIRONMENT="production", SECRET_KEY="a" * 64, _env_file=None)
        assert len(s.SECRET_KEY) == 64

    def test_non_production_allows_empty_but_warns(self):
        with pytest.warns(UserWarning, match="SECRET_KEY is empty"):
            s = Settings(ENVIRONMENT="development", _env_file=None)
        assert s.SECRET_KEY == ""


class TestCookieTtlGuard:
    """The refresh cookie used to be hard-coded to 30 days while the refresh JWT
    lived 7, so browsers replayed a dead credential for 23 days."""

    def test_refresh_cookie_default_matches_token_lifetime(self):
        s = _settings()
        assert s.REFRESH_TOKEN_EXPIRE_DAYS == 7
        assert s.REFRESH_COOKIE_MAX_AGE == s.REFRESH_TOKEN_EXPIRE_DAYS * 86400

    def test_refresh_cookie_may_not_outlive_token(self):
        with pytest.raises(ValueError, match="must not exceed"):
            Settings(
                ENVIRONMENT="development",
                REFRESH_TOKEN_EXPIRE_DAYS=1,
                REFRESH_COOKIE_MAX_AGE=2592000,
                _env_file=None,
            )

    def test_access_cookie_may_exceed_access_token_ttl(self):
        # Intentionally allowed: that is how silent refresh works.
        s = _settings(ACCESS_TOKEN_EXPIRE_MINUTES=60, ACCESS_COOKIE_MAX_AGE=604800)
        assert s.ACCESS_COOKIE_MAX_AGE > s.ACCESS_TOKEN_EXPIRE_MINUTES * 60


class TestAdminBootstrapToken:
    def test_bootstrap_disabled_by_default(self):
        s = _settings()
        assert s.ADMIN_BOOTSTRAP_TOKEN == ""

    def test_bootstrap_token_is_configurable(self):
        s = _settings(ADMIN_BOOTSTRAP_TOKEN="s3cret-bootstrap")
        assert s.ADMIN_BOOTSTRAP_TOKEN == "s3cret-bootstrap"
