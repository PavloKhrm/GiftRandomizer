import time
from db import db_conn

async def create_giveaway(owner_id: int):
    async with db_conn() as db:
        cur = await db.execute("INSERT INTO giveaways(owner_id, created_at) VALUES(?,?)",(owner_id,int(time.time())))
        await db.commit()
        return cur.lastrowid

async def set_post(gid: int, title: str, caption: str, media_type: str|None, media_file_id: str|None):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET title=?, caption=?, media_type=?, media_file_id=? WHERE id=?", (title, caption, media_type, media_file_id, gid))
        await db.commit()

async def set_button_text(gid: int, text: str):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET button_text=? WHERE id=?", (text, gid))
        await db.commit()

async def add_requirement(gid: int, chat_id: str):
    async with db_conn() as db:
        try:
            await db.execute("INSERT INTO giveaway_requirements(giveaway_id, chat_id) VALUES(?,?)",(gid, chat_id))
            await db.commit()
            return True
        except Exception:
            return False

async def list_requirements(gid: int):
    async with db_conn() as db:
        cur = await db.execute("SELECT chat_id FROM giveaway_requirements WHERE giveaway_id=?", (gid,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]

async def clear_requirements(gid: int):
    async with db_conn() as db:
        await db.execute("DELETE FROM giveaway_requirements WHERE giveaway_id=?", (gid,))
        await db.commit()

async def allow_no_subs(gid: int):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET allow_no_sub=1 WHERE id=?", (gid,))
        await db.commit()

async def set_ends_at(gid: int, ends_at: int):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET ends_at=? WHERE id=?", (ends_at, gid))
        await db.commit()

async def set_winners_count(gid: int, n: int):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET winners_count=? WHERE id=?", (n, gid))
        await db.commit()

async def set_post_target(gid: int, chat_id: str, message_id: int|None):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET post_chat_id=?, post_message_id=? WHERE id=?", (chat_id, message_id, gid))
        await db.commit()

async def mark_closed(gid: int):
    async with db_conn() as db:
        await db.execute("UPDATE giveaways SET closed=1 WHERE id=?", (gid,))
        await db.commit()

async def get_giveaway(gid: int):
    async with db_conn() as db:
        cur = await db.execute(
            "SELECT id, owner_id, title, caption, media_type, media_file_id, button_text, allow_no_sub, ends_at, post_chat_id, post_message_id, closed, winners_count FROM giveaways WHERE id=?",
            (gid,)
        )
        return await cur.fetchone()

async def list_by_owner(owner_id: int):
    async with db_conn() as db:
        cur = await db.execute("SELECT id, title FROM giveaways WHERE owner_id=? ORDER BY id DESC", (owner_id,))
        return await cur.fetchall()

async def delete_giveaway(gid: int, owner_id: int):
    async with db_conn() as db:
        await db.execute("DELETE FROM giveaways WHERE id=? AND owner_id=?", (gid, owner_id))
        await db.execute("DELETE FROM giveaway_requirements WHERE giveaway_id=?", (gid,))
        await db.execute("DELETE FROM entries WHERE giveaway_id=?", (gid,))
        await db.commit()

async def add_entry(gid: int, user_id: int):
    async with db_conn() as db:
        try:
            await db.execute("INSERT INTO entries(giveaway_id,user_id,joined_at) VALUES(?,?,?)",(gid, user_id, int(time.time())))
            await db.commit()
            return True
        except Exception:
            return False

async def list_entries(gid: int):
    async with db_conn() as db:
        cur = await db.execute("SELECT user_id FROM entries WHERE giveaway_id=?", (gid,))
        return [r[0] for r in await cur.fetchall()]
