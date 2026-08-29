from asyncpg import UniqueViolationError

from db import execute, fetch


async def add_owner_channel(owner_id: int, chat_id: str):
    try:
        await execute(
            "INSERT INTO my_channels(owner_id, chat_id) VALUES($1,$2)",
            owner_id,
            chat_id,
        )
        return True
    except UniqueViolationError:
        return False


async def del_owner_channel(owner_id: int, chat_id: str):
    await execute(
        "DELETE FROM my_channels WHERE owner_id=$1 AND chat_id=$2", owner_id, chat_id
    )


async def list_owner_channels(owner_id: int):
    rows = await fetch("SELECT chat_id FROM my_channels WHERE owner_id=$1", owner_id)
    return [r["chat_id"] for r in rows]
