import asyncio
import time
import random
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import settings
from db import init_db, fetch
from handlers import register_handlers
from services.giveaways import list_requirements, list_entries, get_giveaway, mark_closed
from services.subscription import is_member_everywhere
from utils.texts import finished_announce

async def winner_label(bot, user_id: int):
    try:
        chat = await bot.get_chat(user_id)
        if getattr(chat, "username", None):
            return f"@{chat.username}"
    except Exception:
        pass
    return f"<a href='tg://user?id={user_id}'>профіль</a>"

async def auto_draw_loop(bot: Bot):
    while True:
        now = int(time.time())
        try:
            rows = await fetch(
                "SELECT id FROM giveaways WHERE ends_at IS NOT NULL AND ends_at <= $1 AND closed=0",
                now
            )
            ids = [r["id"] for r in rows]
            for gid in ids:
                row = await get_giveaway(gid)
                if not row:
                    continue
                owner_id = row["owner_id"]
                title = row["title"]
                allow_no_sub = row["allow_no_sub"]
                post_chat_id = row["post_chat_id"]
                winners_count = row["winners_count"]

                reqs = await list_requirements(gid)
                users = await list_entries(gid)

                if allow_no_sub or not reqs:
                    pool = users
                else:
                    pool = []
                    for u in users:
                        if await is_member_everywhere(bot, u, reqs):
                            pool.append(u)

                if not pool:
                    await mark_closed(gid)
                    try:
                        await bot.send_message(owner_id, f"⚠️ У розіграші «{title or 'Розіграш'}» немає валідних учасників.")
                    except Exception:
                        pass
                    continue

                k = min(max(1, winners_count or 1), min(100, len(pool)))
                chosen = random.sample(pool, k)
                names = [await winner_label(bot, uid) for uid in chosen]
                text = finished_announce(title, names)
                target_chat = int(post_chat_id) if post_chat_id else owner_id

                await mark_closed(gid)
                try:
                    await bot.send_message(target_chat, text)
                except Exception:
                    try:
                        await bot.send_message(owner_id, text)
                    except Exception:
                        pass
        except Exception as e:
            print("[auto_draw_loop]", e)
        await asyncio.sleep(30)

async def main():
    await init_db()
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    register_handlers(dp)
    asyncio.create_task(auto_draw_loop(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
