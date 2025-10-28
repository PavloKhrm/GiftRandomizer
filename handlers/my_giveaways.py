import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from keyboards.inline import giveaways_manage, giveaway_actions
from services.giveaways import list_by_owner, get_giveaway, list_requirements, list_entries, delete_giveaway, mark_closed
from services.subscription import is_member_everywhere, channel_preview
from services.posting import build_and_send
from keyboards.reply import main_menu
from utils.texts import composed_caption, finished_announce

router = Router()

async def winner_label(bot, user_id: int):
    try:
        chat = await bot.get_chat(user_id)
        if getattr(chat, "username", None):
            return f"@{chat.username}"
    except Exception:
        pass
    return f"<a href='tg://user?id={user_id}'>профіль</a>"

@router.message(F.text == "📦 Мої розіграші")
async def my_gw(m: Message):
    items = await list_by_owner(m.from_user.id)
    kb = giveaways_manage(items)
    await m.answer("Ваші розіграші", reply_markup=kb or main_menu())

@router.callback_query(F.data.startswith("gw:open:"))
async def gw_open(cq: CallbackQuery):
    gid = int(cq.data.split(":")[2])
    row = await get_giveaway(gid)
    if not row:
        await cq.answer("Не знайдено", show_alert=True); return
    _, owner_id, title, caption, media_type, media_file_id, button_text, allow_no_sub, ends_at, post_chat_id, post_message_id, closed, winners_count = row
    await cq.message.answer(f"#{gid} {title or ''}".strip() or f"#{gid}", reply_markup=giveaway_actions(gid))
    await cq.answer()

@router.callback_query(F.data.startswith("gw:post:"))
async def gw_post(cq: CallbackQuery):
    gid = int(cq.data.split(":")[2])
    row = await get_giveaway(gid)
    if not row:
        await cq.answer("Не знайдено", show_alert=True); return
    _, owner_id, title, caption, media_type, media_file_id, button_text, allow_no_sub, ends_at, post_chat_id, post_message_id, closed, winners_count = row
    if closed:
        await cq.answer("Розіграш уже завершено", show_alert=True); return
    reqs = await list_requirements(gid)
    ids = reqs or ([post_chat_id] if post_chat_id else [])
    prev = await channel_preview(cq.message.bot, ids[:3]) if ids else []
    final_caption = composed_caption(caption or "", prev, button_text or "Беру участь!")
    target_chat = int(post_chat_id) if post_chat_id else cq.from_user.id
    await build_and_send(cq.message.bot, target_chat, gid, title, final_caption, media_type, media_file_id, button_text or "Беру участь!")
    await cq.answer("Пост надіслано")

@router.callback_query(F.data.startswith("gw:draw:"))
async def gw_draw(cq: CallbackQuery):
    gid = int(cq.data.split(":")[2])
    row = await get_giveaway(gid)
    if not row:
        await cq.answer("Не знайдено", show_alert=True); return
    _, owner_id, title, caption, media_type, media_file_id, button_text, allow_no_sub, ends_at, post_chat_id, post_message_id, closed, winners_count = row
    if closed:
        await cq.answer("Розіграш уже завершено", show_alert=True); return
    reqs = await list_requirements(gid)
    users = await list_entries(gid)
    pool = []
    if allow_no_sub or not reqs:
        pool = users
    else:
        for u in users:
            if await is_member_everywhere(cq.message.bot, u, reqs):
                pool.append(u)
    if not pool:
        await cq.answer("Немає валідних учасників", show_alert=True); return
    k = min(max(1, winners_count or 1), min(100, len(pool)))
    chosen = random.sample(pool, k)
    names = [await winner_label(cq.message.bot, uid) for uid in chosen]
    text = finished_announce(title, names)
    target_chat = int(post_chat_id) if post_chat_id else cq.message.chat.id
    await mark_closed(gid)
    try:
        await cq.message.bot.send_message(target_chat, text)
    except Exception:
        await cq.message.answer(text)
    await cq.answer("Підсумки опубліковано")

@router.callback_query(F.data.startswith("gw:del:"))
async def gw_del(cq: CallbackQuery):
    gid = int(cq.data.split(":")[2])
    await delete_giveaway(gid, cq.from_user.id)
    await cq.message.answer("Видалено")
    await cq.answer()

def setup(dp):
    dp.include_router(router)
