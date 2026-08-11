import os
from functools import lru_cache
class Settings:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN", "").strip()
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.admin_ids = os.getenv("ADMIN_IDS", "").strip()
        self.admin_secret = os.getenv(
            "ADMIN_SECRET",
            "change-me",
        )
        self.app_host = os.getenv(
            "APP_HOST",
            "0.0.0.0",
        )
        self.app_port = int(
            os.getenv(
                "PORT",
                os.getenv("APP_PORT", "8080"),
            )
        )
        self.log_level = os.getenv(
            "LOG_LEVEL",
            "INFO",
        ).upper()
        self.support_username = os.getenv(
            "SUPPORT_USERNAME",
            "",
        ).strip()
        self.shop_name = os.getenv(
            "SHOP_NAME",
            "Telegram Shop",
        ).strip()
    @property
    def admin_id_set(self) -> set[int]:
        result = set()
        for value in self.admin_ids.split(","):
            value = value.strip()
            if not value:
                continue
            try:
                result.add(int(value))
            except ValueError:
                pass
        return result
@lru_cache
def get_settings() -> Settings:
    return Settings()
