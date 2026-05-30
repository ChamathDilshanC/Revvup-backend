import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration.

    Values are read from environment variables (or a local .env file).
    On Vercel, set these in the project dashboard.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Supabase ---------------------------------------------------------
    supabase_url: str = ""
    supabase_anon_key: str = ""
    # Service role key bypasses Row Level Security — keep it server-side only.
    supabase_service_key: str = ""
    # Public storage bucket used for bike images.
    supabase_bucket: str = "bike-images"

    # --- Approval / email -------------------------------------------------
    # Showroom-owner registrations require approval from this developer email.
    developer_email: str = "dilshancolonne123@gmail.com"
    # Public base URL of THIS backend — used to build approve/reject links.
    app_base_url: str = "http://localhost:8000"

    # SMTP credentials for sending the HTML approval email.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    @property
    def is_configured(self) -> bool:
        has_key = bool(
            self.supabase_service_key
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or self.supabase_anon_key
        )
        return bool(self.supabase_url and has_key)

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def from_address(self) -> str:
        return self.smtp_from or self.smtp_user

    @property
    def effective_app_base_url(self) -> str:
        """Public backend URL for approve/reject email links.

        Uses APP_BASE_URL when set to a real host. On Vercel, if APP_BASE_URL
        is still localhost (common copy-paste from .env.example), uses
        https://<VERCEL_URL> automatically.
        """
        base = self.app_base_url.strip().rstrip("/")
        is_local = not base or "localhost" in base or "127.0.0.1" in base
        vercel_host = os.environ.get("VERCEL_URL", "").strip()
        if vercel_host and is_local:
            return f"https://{vercel_host}"
        return base or "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
