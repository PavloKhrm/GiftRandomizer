import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    bot_token: str
    admin_ids: list[int]
    database_url: str
    timezone_name: str
    auto_draw_interval_seconds: int
    auto_draw_batch_size: int

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.database_url:
            missing.append("DATABASE_URL")
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        try:
            ZoneInfo(self.timezone_name)
        except Exception as exc:
            raise RuntimeError(f"Unknown TIMEZONE: {self.timezone_name}") from exc


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    admin_ids=[
        int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
    ],
    database_url=os.getenv("DATABASE_URL", ""),
    timezone_name=os.getenv("TIMEZONE", "Europe/Amsterdam"),
    auto_draw_interval_seconds=max(
        5, int(os.getenv("AUTO_DRAW_INTERVAL_SECONDS", "20"))
    ),
    auto_draw_batch_size=max(1, min(100, int(os.getenv("AUTO_DRAW_BATCH_SIZE", "20")))),
)
