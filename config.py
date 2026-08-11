from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_ids: str = ""
    admin_secret: str = "change-me"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    log_level: str = "INFO"
    support_username: str = ""
    shop_name: str = "Telegram Shop"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def admin_id_set(self) -> set[int]:
        return {int(x.strip()) for x in self.admin_ids.split(",") if x.strip()}

@lru_cache
def get_settings() -> Settings:
    return Settings()
