from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from services.giveaways import add_entry, list_requirements
from services.subscription import is_member_everywhere

router = Router()

@router.callback_query(F.data.startswith("join:"))
async def on_join(cq: CallbackQuery, bot: Bot):
    try:
        giveaway_id = int(cq.data.split(":")[1])
    except Exception:
        await cq.answer("Ошибка.", show_alert=True)
        return
    reqs = await list_requirements(giveaway_id)
    if reqs:
        ok = await is_member_everywhere(bot, cq.from_user.id, reqs)
        if not ok:
            await cq.answer("Чтобы принять участие, подпишитесь на канал(ы) и снова нажмите кнопку.", show_alert=True)
            return
    added = await add_entry(giveaway_id, cq.from_user.id)
    if added:
        await cq.answer("Участие засчитано ✅", show_alert=True)
    else:
        await cq.answer("Вы уже участвуете", show_alert=True)

def setup(dp):
    dp.include_router(router)
