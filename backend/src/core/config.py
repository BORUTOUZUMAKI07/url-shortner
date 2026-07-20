import os
import tempfile
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
    RATE_LIMIT_USER_FREE_CAPACITY: int = 100
    RATE_LIMIT_USER_FREE_REFILL: float = 1.67
    RATE_LIMIT_USER_PREMIUM_CAPACITY: int = 1000
    RATE_LIMIT_USER_PREMIUM_REFILL: float = 16.67

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

    # --- JWT ---
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Google OAuth 2.0 ---
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    # --- GitHub OAuth 2.0 ---
    GITHUB_OAUTH_CLIENT_ID: Optional[str] = None
    GITHUB_OAUTH_CLIENT_SECRET: Optional[str] = None
    GITHUB_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/github/callback"

    # --- Observability (OpenTelemetry OTLP) ---
    ENVIRONMENT: str = "production"
    OTLP_ENABLED: bool = True
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_EXPORTER_OTLP_HEADERS: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
