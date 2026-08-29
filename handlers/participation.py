import asyncio
import time

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from services.giveaways import add_entry, get_giveaway, list_requirements
from services.subscription import SubscriptionCheckUnavailable, is_member_everywhere
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
    if not row["post_message_id"]:
        await cq.answer("Розіграш ще не опубліковано.", show_alert=True)
        return

    now = int(time.time())
    closed = row["closed"]
    ends_at = row["ends_at"]
    if closed or row["draw_status"] != "pending" or (ends_at and ends_at <= now):
        await cq.answer(join_closed(), show_alert=True)
        return

    reqs = await list_requirements(giveaway_id)
    if reqs:
        try:
            async with asyncio.timeout(7):
                ok = await is_member_everywhere(
                    bot,
                    cq.from_user.id,
                    reqs,
                    retry=False,
                    concurrent=True,
                )
        except (SubscriptionCheckUnavailable, TimeoutError):
            await cq.answer(
                "Telegram тимчасово не відповідає. Спробуйте ще раз за хвилину.",
                show_alert=True,
            )
            return
        if not ok:
            await cq.answer(
                "Щоб взяти участь, підпишіться на канал(и) і натисніть кнопку ще раз.",
                show_alert=True,
            )
            return

    result = await add_entry(giveaway_id, cq.from_user.id, now)
    if result == "added":
        await cq.answer("Ви взяли участь🎉", show_alert=True)
    elif result == "exists":
        await cq.answer("Ви вже берете участь🤍", show_alert=True)
    else:
        await cq.answer(join_closed(), show_alert=True)


def setup(dp):
    dp.include_router(router)
