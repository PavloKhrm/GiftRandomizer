import time
from db import execute, fetch, fetchrow

async def create_giveaway(owner_id: int):
    row = await fetchrow("INSERT INTO giveaways(owner_id, created_at) VALUES($1,$2) RETURNING id", owner_id, int(time.time()))
    return row["id"]

async def set_post(gid: int, title: str, caption: str, media_type: str | None, media_file_id: str | None):
    await execute("UPDATE giveaways SET title=$1, caption=$2, media_type=$3, media_file_id=$4 WHERE id=$5",
                  title, caption, media_type, media_file_id, gid)

async def set_button_text(gid: int, text: str):
    await execute("UPDATE giveaways SET button_text=$1 WHERE id=$2", text, gid)

async def add_requirement(gid: int, chat_id: str):
    try:
        await execute("INSERT INTO giveaway_requirements(giveaway_id, chat_id) VALUES($1,$2)", gid, chat_id)
        return True
    except Exception:
        return False

async def list_requirements(gid: int):
    rows = await fetch("SELECT chat_id FROM giveaway_requirements WHERE giveaway_id=$1", gid)
    return [r["chat_id"] for r in rows]

async def clear_requirements(gid: int):
    await execute("DELETE FROM giveaway_requirements WHERE giveaway_id=$1", gid)

async def allow_no_subs(gid: int):
    await execute("UPDATE giveaways SET allow_no_sub=1 WHERE id=$1", gid)

async def set_ends_at(gid: int, ends_at: int):
    await execute("UPDATE giveaways SET ends_at=$1 WHERE id=$2", ends_at, gid)

async def set_winners_count(gid: int, n: int):
    await execute("UPDATE giveaways SET winners_count=$1 WHERE id=$2", n, gid)

async def set_post_target(gid: int, chat_id: str, message_id: int | None):
    await execute("UPDATE giveaways SET post_chat_id=$1, post_message_id=$2 WHERE id=$3", chat_id, message_id, gid)

async def mark_closed(gid: int):
    await execute("UPDATE giveaways SET closed=1 WHERE id=$1", gid)

async def get_giveaway(gid: int):
    return await fetchrow(
        "SELECT id, owner_id, title, caption, media_type, media_file_id, button_text, allow_no_sub, "
        "ends_at, post_chat_id, post_message_id, closed, winners_count FROM giveaways WHERE id=$1",
        gid
    )

async def list_by_owner(owner_id: int):
    rows = await fetch("SELECT id, title FROM giveaways WHERE owner_id=$1 ORDER BY id DESC", owner_id)
    return [(r["id"], r["title"]) for r in rows]

async def delete_giveaway(gid: int, owner_id: int):
    await execute("DELETE FROM giveaways WHERE id=$1 AND owner_id=$2", gid, owner_id)
    await execute("DELETE FROM giveaway_requirements WHERE giveaway_id=$1", gid)
    await execute("DELETE FROM entries WHERE giveaway_id=$1", gid)

async def add_entry(gid: int, user_id: int):
    try:
        await execute("INSERT INTO entries(giveaway_id,user_id,joined_at) VALUES($1,$2,$3)", gid, user_id, int(time.time()))
        return True
    except Exception:
        return False

async def list_entries(gid: int):
    rows = await fetch("SELECT user_id FROM entries WHERE giveaway_id=$1", gid)
    return [r["user_id"] for r in rows]
