from functools import lru_cache
from pathlib import Path
import json
from pydantic import BaseModel


class DatabaseSettings(BaseModel):
    supabase_url: str
    supabase_service_role_key: str


class SecuritySettings(BaseModel):
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expires_minutes: int = 60 * 24


class AdminSettings(BaseModel):
    software_owner_email: str = "admin@vamisurat.com"
    software_owner_password: str = "vami@surat"


class Settings(BaseModel):
    database: DatabaseSettings
    security: SecuritySettings
    admin: AdminSettings

    # Backwards-compatible properties so existing imports continue to work
    @property
    def supabase_url(self) -> str:
        return self.database.supabase_url

    @property
    def supabase_service_role_key(self) -> str:
        return self.database.supabase_service_role_key

    @property
    def jwt_secret(self) -> str:
        return self.security.jwt_secret

    @property
    def jwt_algorithm(self) -> str:
        return self.security.jwt_algorithm

    @property
    def access_token_expires_minutes(self) -> int:
        return self.security.access_token_expires_minutes

    @property
    def software_owner_email(self) -> str:
        return self.admin.software_owner_email

    @property
    def software_owner_password(self) -> str:
        return self.admin.software_owner_password


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"


@lru_cache()
def get_settings() -> Settings:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return Settings.model_validate(raw)

