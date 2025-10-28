import time
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from services.giveaways import add_entry, list_requirements, get_giveaway
from services.subscription import is_member_everywhere
from utils.texts import join_closed

router = Router()

@router.callback_query(F.data.startswith("join:"))
async def on_join(cq: CallbackQuery, bot: Bot):
    try:
        giveaway_id = int(cq.data.split(":")[1])
    except Exception:
        await cq.answer("Помилка.", show_alert=True)
        return

    row = await get_giveaway(giveaway_id)
    if not row:
        await cq.answer("Не знайдено.", show_alert=True)
        return

    now = int(time.time())
    closed = row["closed"]
    ends_at = row["ends_at"]
    if closed or (ends_at and ends_at <= now):
        await cq.answer(join_closed(), show_alert=True)
        return

    reqs = await list_requirements(giveaway_id)
    if reqs:
        ok = await is_member_everywhere(bot, cq.from_user.id, reqs)
        if not ok:
            await cq.answer("Щоб взяти участь, підпишіться на канал(и) і натисніть кнопку ще раз.", show_alert=True)
            return

    added = await add_entry(giveaway_id, cq.from_user.id)
    if added:
        await cq.answer("Ви взяли участь🎉", show_alert=True)
    else:
        await cq.answer("Ви вже берете участь🤍", show_alert=True)

def setup(dp):
    dp.include_router(router)
