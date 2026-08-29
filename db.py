import asyncio

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
      caption_entities JSONB NOT NULL DEFAULT '[]'::jsonb,
      media_type TEXT,
      media_file_id TEXT,
      button_text TEXT,
      button_style TEXT NOT NULL DEFAULT 'success',
      button_icon_custom_emoji_id TEXT,
      allow_no_sub INTEGER DEFAULT 0,
      ends_at BIGINT,
      post_chat_id TEXT,
      post_message_id BIGINT,
      published_at BIGINT,
      publish_status TEXT NOT NULL DEFAULT 'draft',
      publish_claimed_at BIGINT,
      publish_claim_token TEXT,
      closed INTEGER DEFAULT 0,
      winners_count INTEGER DEFAULT 1,
      draw_status TEXT NOT NULL DEFAULT 'pending',
      draw_claimed_at BIGINT,
      draw_claim_token TEXT,
      draw_attempts INTEGER NOT NULL DEFAULT 0,
      next_draw_attempt_at BIGINT,
      draw_error TEXT,
      drawn_at BIGINT,
      result_chat_id TEXT,
      result_message_id BIGINT,
      draw_selection_finalized BOOLEAN NOT NULL DEFAULT FALSE,
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
    CREATE TABLE IF NOT EXISTS giveaway_winners(
      giveaway_id BIGINT NOT NULL,
      place INTEGER NOT NULL,
      user_id BIGINT NOT NULL,
      selected_at BIGINT NOT NULL,
      PRIMARY KEY(giveaway_id, place),
      UNIQUE(giveaway_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS giveaway_result_messages(
      giveaway_id BIGINT NOT NULL,
      sequence INTEGER NOT NULL,
      chat_id TEXT NOT NULL,
      message_id BIGINT NOT NULL,
      created_at BIGINT NOT NULL,
      PRIMARY KEY(giveaway_id, sequence)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS giveaway_result_chunks(
      giveaway_id BIGINT NOT NULL,
      sequence INTEGER NOT NULL,
      body_html TEXT NOT NULL,
      PRIMARY KEY(giveaway_id, sequence)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS my_channels(
      id BIGSERIAL PRIMARY KEY,
      owner_id BIGINT NOT NULL,
      chat_id TEXT NOT NULL,
      UNIQUE(owner_id, chat_id)
    )
    """,
]


MIGRATION_STATEMENTS = [
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS caption_entities JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS button_style TEXT NOT NULL DEFAULT 'success'",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS button_icon_custom_emoji_id TEXT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS published_at BIGINT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS publish_status TEXT NOT NULL DEFAULT 'draft'",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS publish_claimed_at BIGINT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS publish_claim_token TEXT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS draw_status TEXT NOT NULL DEFAULT 'pending'",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS draw_claimed_at BIGINT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS draw_claim_token TEXT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS draw_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS next_draw_attempt_at BIGINT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS draw_error TEXT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS drawn_at BIGINT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS result_chat_id TEXT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS result_message_id BIGINT",
    "ALTER TABLE giveaways ADD COLUMN IF NOT EXISTS draw_selection_finalized BOOLEAN NOT NULL DEFAULT FALSE",
    "UPDATE giveaways SET draw_status='finished' WHERE closed=1 AND draw_status='pending'",
    "UPDATE giveaways SET publish_status='active' WHERE post_message_id IS NOT NULL AND publish_status='draft'",
    "CREATE INDEX IF NOT EXISTS giveaways_due_idx ON giveaways(ends_at) WHERE closed=0",
    "CREATE INDEX IF NOT EXISTS entries_giveaway_idx ON entries(giveaway_id)",
]


async def init_db(max_attempts: int = 8) -> None:
    global _pool
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is missing")

    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            _pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=1,
                max_size=5,
                command_timeout=30,
            )
            async with _pool.acquire() as con, con.transaction():
                giveaways_existed = await con.fetchval(
                    "SELECT to_regclass('public.giveaways') IS NOT NULL"
                )
                had_publish_status = False
                if giveaways_existed:
                    had_publish_status = await con.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name='giveaways' "
                        "AND column_name='publish_status')"
                    )
                for sql in CREATE_STATEMENTS:
                    await con.execute(sql)
                for sql in MIGRATION_STATEMENTS:
                    await con.execute(sql)
                if giveaways_existed and not had_publish_status:
                    await con.execute(
                        "UPDATE giveaways SET publish_status='legacy_unknown' "
                        "WHERE closed=0 AND post_chat_id IS NOT NULL "
                        "AND post_message_id IS NULL AND publish_status='draft'"
                    )
            return
        except Exception as exc:
            last_error = exc
            if _pool is not None:
                await _pool.close()
                _pool = None
            if attempt + 1 < max_attempts:
                await asyncio.sleep(min(2**attempt, 15))
    raise RuntimeError("Could not initialize PostgreSQL") from last_error


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


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
