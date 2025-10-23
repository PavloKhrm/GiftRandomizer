import asyncpg
from config import settings

_pool: asyncpg.Pool | None = None

CREATE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS giveaways(
      id BIGSERIAL PRIMARY KEY,
      owner_id BIGINT NOT NULL,
      title TEXT,
      caption TEXT,
      media_type TEXT,
      media_file_id TEXT,
      button_text TEXT,
      allow_no_sub INTEGER DEFAULT 0,
      ends_at BIGINT,
      post_chat_id TEXT,
      post_message_id BIGINT,
      closed INTEGER DEFAULT 0,
      winners_count INTEGER DEFAULT 1,
      created_at BIGINT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS giveaway_requirements(
      id BIGSERIAL PRIMARY KEY,
      giveaway_id BIGINT NOT NULL,
      chat_id TEXT NOT NULL,
      UNIQUE(giveaway_id, chat_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS entries(
      id BIGSERIAL PRIMARY KEY,
      giveaway_id BIGINT NOT NULL,
      user_id BIGINT NOT NULL,
      joined_at BIGINT NOT NULL,
      UNIQUE(giveaway_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS my_channels(
      id BIGSERIAL PRIMARY KEY,
      owner_id BIGINT NOT NULL,
      chat_id TEXT NOT NULL,
      UNIQUE(owner_id, chat_id)
    )
    """
]

async def init_db():
    global _pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is missing")
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    async with _pool.acquire() as con:
        async with con.transaction():
            for sql in CREATE_STATEMENTS:
                await con.execute(sql)

def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialized")
    return _pool

async def execute(sql: str, *args):
    async with pool().acquire() as con:
        return await con.execute(sql, *args)

async def fetch(sql: str, *args):
    async with pool().acquire() as con:
        return await con.fetch(sql, *args)

async def fetchrow(sql: str, *args):
    async with pool().acquire() as con:
        return await con.fetchrow(sql, *args)
