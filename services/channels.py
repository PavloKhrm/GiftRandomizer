from db import db_conn

async def add_owner_channel(owner_id: int, chat_id: str):
    async with db_conn() as db:
        try:
            await db.execute("INSERT INTO my_channels(owner_id, chat_id) VALUES(?,?)",(owner_id, chat_id))
            await db.commit()
            return True
        except Exception:
            return False

async def del_owner_channel(owner_id: int, chat_id: str):
    async with db_conn() as db:
        await db.execute("DELETE FROM my_channels WHERE owner_id=? AND chat_id=?",(owner_id, chat_id))
        await db.commit()

async def list_owner_channels(owner_id: int):
    async with db_conn() as db:
        cur = await db.execute("SELECT chat_id FROM my_channels WHERE owner_id=?",(owner_id,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]
