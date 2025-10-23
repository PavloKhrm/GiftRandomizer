import aiosqlite
from config import settings

CREATE_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS giveaways(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  title TEXT,
  caption TEXT,
  media_type TEXT,
  media_file_id TEXT,
  button_text TEXT,
  allow_no_sub INTEGER DEFAULT 0,
  ends_at INTEGER,
  post_chat_id TEXT,
  post_message_id INTEGER,
  closed INTEGER DEFAULT 0,
  winners_count INTEGER DEFAULT 1,
  created_at INTEGER
);
CREATE TABLE IF NOT EXISTS giveaway_requirements(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  giveaway_id INTEGER NOT NULL,
  chat_id TEXT NOT NULL,
  UNIQUE(giveaway_id, chat_id)
);
CREATE TABLE IF NOT EXISTS entries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  giveaway_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  joined_at INTEGER NOT NULL,
  UNIQUE(giveaway_id, user_id)
);
CREATE TABLE IF NOT EXISTS my_channels(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  chat_id TEXT NOT NULL,
  UNIQUE(owner_id, chat_id)
);
"""

async def init_db():
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(CREATE_SQL)
        await db.commit()

def db_conn():
    return aiosqlite.connect(settings.db_path)
