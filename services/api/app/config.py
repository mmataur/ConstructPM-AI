import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://constructpm_app@127.0.0.1:55432/constructpm")
    environment: str = os.getenv("ENVIRONMENT", "production")
    dev_auth: bool = os.getenv("DEV_AUTH", "false").lower() == "true"
    dev_secret: str = os.getenv("DEV_AUTH_SECRET", "")
    dev_emails: tuple[str, ...] = tuple(os.getenv("DEV_EMAILS", "planner@example.test,supervisor@example.test").split(","))
    issuer: str = os.getenv("OIDC_ISSUER", "")
    audience: str = os.getenv("OIDC_AUDIENCE", "constructpm-api")
    jwks_url: str = os.getenv("OIDC_JWKS_URL", "")
    cors_origins: tuple[str, ...] = tuple(os.getenv("CORS_ORIGINS", "http://localhost:1420,http://127.0.0.1:1420,http://tauri.localhost,tauri://localhost").split(","))

    def validate(self):
        if self.dev_auth:
            if self.environment != "development" or len(self.dev_secret) < 32:
                raise RuntimeError("Development identity requires development environment and a 32+ character secret")
        elif not self.issuer.startswith("https://") or not self.jwks_url.startswith("https://"):
            raise RuntimeError("Configure HTTPS OIDC_ISSUER and OIDC_JWKS_URL; development identity is disabled by default")
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("Phase 1 requires PostgreSQL, not a SQLite substitute")

