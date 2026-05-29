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
        return bool(self.supabase_url and (self.supabase_service_key or self.supabase_anon_key))

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password)

    @property
    def from_address(self) -> str:
        return self.smtp_from or self.smtp_user


@lru_cache
def get_settings() -> Settings:
    return Settings()
