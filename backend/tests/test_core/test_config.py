from unittest.mock import patch

import pytest

from src.core.config import Settings


class TestSettingsDefaults:
    def test_project_name_default(self):
        s = Settings(_env_file=None)
        assert s.PROJECT_NAME == "LinkForge URL Shortener"

    def test_database_defaults(self):
        s = Settings(_env_file=None)
        assert s.POSTGRES_USER == "linkforge_user"
        assert s.POSTGRES_PASSWORD == "linkforge_password"
        assert s.POSTGRES_DB == "linkforge_db"
        assert s.POSTGRES_HOST == "localhost"
        assert s.POSTGRES_PORT == 5432

    def test_redis_defaults(self):
        s = Settings(_env_file=None)
        assert s.REDIS_URL == "redis://localhost:6379"

    def test_jwt_defaults(self):
        s = Settings(_env_file=None)
        assert s.ALGORITHM == "HS256"
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 60

    def test_rate_limit_defaults(self):
        s = Settings(_env_file=None)
        assert s.RATE_LIMIT_IP_CAPACITY == 60
        assert s.RATE_LIMIT_IP_REFILL == 1.0

    def test_kafka_defaults(self):
        s = Settings(_env_file=None)
        assert s.KAFKA_BOOTSTRAP_SERVERS == "localhost:29092"
        assert s.KAFKA_SECURITY_PROTOCOL == "PLAINTEXT"
        assert s.KAFKA_SASL_MECHANISM == "GSSAPI"

    def test_smtp_defaults(self):
        s = Settings(_env_file=None)
        assert s.SMTP_HOST == ""
        assert s.SMTP_PORT == 587
        assert s.FROM_EMAIL == "noreply@linkforge.dev"

    def test_oauth_defaults(self):
        s = Settings(_env_file=None)
        assert s.GOOGLE_OAUTH_CLIENT_ID is None
        assert s.GOOGLE_OAUTH_REDIRECT_URI == "http://localhost:8000/api/v1/auth/oauth/google/callback"

    def test_frontend_url_default(self):
        s = Settings(_env_file=None)
        assert s.FRONTEND_URL == "http://localhost:3000"
        assert s.BACKEND_URL == "http://127.0.0.1:8000"


class TestSettingsOverrides:
    def test_project_name_override(self):
        s = Settings(PROJECT_NAME="Custom Project", _env_file=None)
        assert s.PROJECT_NAME == "Custom Project"

    def test_async_database_uri_from_full_url(self):
        s = Settings(DATABASE_URL="postgresql://user:pass@remote:5432/db", _env_file=None)
        assert "postgresql+asyncpg://user:pass@remote:5432/db" == s.ASYNC_DATABASE_URI

    def test_async_database_uri_handles_sslmode(self):
        s = Settings(DATABASE_URL="postgresql://user:pass@host/db?sslmode=require", _env_file=None)
        uri = s.ASYNC_DATABASE_URI
        assert "ssl=require" in uri
        assert "sslmode" not in uri

    def test_async_database_uri_strips_channel_binding(self):
        s = Settings(DATABASE_URL="postgresql://user:pass@host/db?channel_binding=require", _env_file=None)
        assert "channel_binding" not in s.ASYNC_DATABASE_URI

    def test_async_database_uri_fallback_construction(self):
        s = Settings(
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
        s = Settings(KAFKA_SASL_USERNAME="user", KAFKA_SASL_PASSWORD="pass", _env_file=None)
        assert s.KAFKA_SECURITY_PROTOCOL == "SASL_SSL"
        assert s.KAFKA_SASL_MECHANISM == "PLAIN"

    def test_kafka_security_protocol_plaintext(self):
        s = Settings(KAFKA_SASL_USERNAME=None, KAFKA_SASL_PASSWORD=None, _env_file=None)
        assert s.KAFKA_SECURITY_PROTOCOL == "PLAINTEXT"
        assert s.KAFKA_SASL_MECHANISM == "GSSAPI"

    def test_oauth_client_id_override(self):
        s = Settings(GOOGLE_OAUTH_CLIENT_ID="google-id.apps.googleusercontent.com", _env_file=None)
        assert s.GOOGLE_OAUTH_CLIENT_ID == "google-id.apps.googleusercontent.com"

    def test_mongodb_uri(self):
        s = Settings(MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net", _env_file=None)
        assert s.MONGODB_URI == "mongodb+srv://user:pass@cluster.mongodb.net"

    def test_type_coercion(self):
        s = Settings(RATE_LIMIT_IP_CAPACITY="120", _env_file=None)
        assert s.RATE_LIMIT_IP_CAPACITY == 120
        assert isinstance(s.RATE_LIMIT_IP_CAPACITY, int)

    def test_upstash_config(self):
        s = Settings(
            UPSTASH_REDIS_REST_URL="https://us1-wonder-123.upstash.io",
            UPSTASH_REDIS_REST_TOKEN="token123",
            _env_file=None,
        )
        assert s.UPSTASH_REDIS_REST_URL == "https://us1-wonder-123.upstash.io"
        assert s.UPSTASH_REDIS_REST_TOKEN == "token123"

    def test_loki_config(self):
        s = Settings(LOKI_URL="https://custom-loki.example.com", _env_file=None)
        assert s.LOKI_URL == "https://custom-loki.example.com"

    def test_otel_config(self):
        s = Settings(OTEL_EXPORTER_OTLP_ENDPOINT="http://otel-collector:4318", _env_file=None)
        assert s.OTEL_EXPORTER_OTLP_ENDPOINT == "http://otel-collector:4318"

    def test_jaeger_disabled_by_default(self):
        s = Settings(_env_file=None)
        assert s.JAEGER_ENABLED is False

    def test_prometheus_enabled_by_default(self):
        s = Settings(_env_file=None)
        assert s.PROMETHEUS_ENABLED is True

    def test_settings_model_config(self):
        s = Settings(_env_file=None)
        assert s.model_config.get("case_sensitive") is True
        assert s.model_config.get("extra") == "ignore"


class TestSettingsEdgeCases:
    def test_database_url_with_ssl_and_other_params(self):
        s = Settings(DATABASE_URL="postgresql://u:p@host/db?sslmode=require&connect_timeout=10", _env_file=None)
        uri = s.ASYNC_DATABASE_URI
        assert "ssl=require" in uri
        assert "connect_timeout=10" in uri
        assert "sslmode" not in uri

    def test_database_url_no_params(self):
        s = Settings(DATABASE_URL="postgresql://u:p@host/db", _env_file=None)
        assert s.ASYNC_DATABASE_URI == "postgresql+asyncpg://u:p@host/db"

    def test_database_url_with_multiple_ssl_params(self):
        s = Settings(DATABASE_URL="postgresql://u:p@host/db?sslmode=require&sslmode=prefer", _env_file=None)
        uri = s.ASYNC_DATABASE_URI
        assert uri.count("ssl=require") == 1

    def test_rate_limit_user_defaults(self):
        s = Settings(_env_file=None)
        assert s.RATE_LIMIT_USER_FREE_CAPACITY == 100
        assert s.RATE_LIMIT_USER_PREMIUM_CAPACITY == 1000

    def test_smtp_password_default_empty(self):
        s = Settings(_env_file=None)
        assert s.SMTP_PASSWORD == ""

    def test_secret_key_default_empty(self):
        s = Settings(_env_file=None)
        assert s.SECRET_KEY == ""

    def test_kafka_ssl_ca_path_default_none(self):
        s = Settings(_env_file=None)
        assert s.KAFKA_SSL_CA_PATH is None

    def test_schema_registry_url_default_none(self):
        s = Settings(_env_file=None)
        assert s.SCHEMA_REGISTRY_URL is None

    def test_loki_password_default_none(self):
        s = Settings(_env_file=None)
        assert s.LOKI_PASSWORD is None

    def test_environment_default(self):
        s = Settings(_env_file=None)
        assert s.ENVIRONMENT == "production"
