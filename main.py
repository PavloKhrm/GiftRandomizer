import asyncio
import time
import random
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from config import settings
from db import init_db, db_conn
from handlers import register_handlers
from services.giveaways import list_requirements, list_entries, get_giveaway, mark_closed
from services.subscription import is_member_everywhere

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
            async with db_conn() as db:
                cur = await db.execute(
                    "SELECT id FROM giveaways WHERE ends_at IS NOT NULL AND ends_at <= ? AND closed=0",
                    (now,)
                )
                ids = [r[0] for r in await cur.fetchall()]
            for gid in ids:
                row = await get_giveaway(gid)
                if not row:
                    continue
                _, owner_id, title, caption, media_type, media_file_id, button_text, allow_no_sub, ends_at, post_chat_id, post_message_id, closed, winners_count = row
                reqs = await list_requirements(gid)
                users = await list_entries(gid)
                pool = []
                if allow_no_sub or not reqs:
                    pool = users
                else:
                    for u in users:
                        if await is_member_everywhere(bot, u, reqs):
                            pool.append(u)
                if not pool:
                    await bot.send_message(owner_id, f"⚠️ У розіграші «{title or 'Розіграш'}» немає валідних учасників.")
                    await mark_closed(gid)
                    continue
                k = min(max(1, winners_count or 1), min(100, len(pool)))
                chosen = random.sample(pool, k)
                labels = [f"• {await winner_label(bot, uid)}" for uid in chosen]
                text = "🎉 Підсумки: <b>{}</b>\n{}".format(title or "Розіграш", "\n".join(labels))
                target_chat = int(post_chat_id) if post_chat_id else owner_id
                try:
                    await bot.send_message(target_chat, text)
                except Exception:
                    await bot.send_message(owner_id, text)
                await mark_closed(gid)
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
