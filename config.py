import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    bot_token: str
    admin_ids: list[int]
    database_url: str

settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    admin_ids=[int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x],
    database_url=os.getenv("DATABASE_URL", "")
)
