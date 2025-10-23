from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from states import CreateGiveaway
from utils.texts import text_saved, ask_button_text, ask_requirements_intro, req_added, req_invalid, ready_to_post, no_requirements, ask_end_datetime, ask_post_channel, ask_winners_count
from utils.formatting import normalize_channel
from keyboards.inline import button_text_presets, req_controls
from services.giveaways import create_giveaway, set_post, set_button_text, add_requirement, list_requirements, allow_no_subs, set_ends_at, set_post_target, set_winners_count
from services.subscription import bot_is_admin

router = Router()

@router.message(CreateGiveaway.waiting_post, F.content_type.in_({"text","photo","video","animation"}))
async def capture_post(m: Message, state: FSMContext):
    data = await state.get_data()
    gid = data.get("gid")
    if not gid:
        gid = await create_giveaway(m.from_user.id)
        await state.update_data(gid=gid)
    title = ""
    caption = (m.caption or m.text or "").strip() if hasattr(m, "caption") else (m.text or "").strip()
    media_type = None
    media_file_id = None
    if getattr(m, "photo", None):
        media_type = "photo"
        media_file_id = m.photo[-1].file_id
    elif getattr(m, "video", None):
        media_type = "video"
        media_file_id = m.video.file_id
    elif getattr(m, "animation", None):
        media_type = "animation"
        media_file_id = m.animation.file_id
    await set_post(gid, title, caption, media_type, media_file_id)
    await m.answer(text_saved())
    await m.answer(ask_button_text(), reply_markup=button_text_presets())
    await state.set_state(CreateGiveaway.waiting_button_text)

@router.callback_query(CreateGiveaway.waiting_button_text, F.data.startswith("btnpreset:"))
async def preset_btn(cq: CallbackQuery, state: FSMContext):
    text = cq.data.split(":",1)[1]
    data = await state.get_data()
    gid = data.get("gid")
    await set_button_text(gid, text)
    await cq.message.answer(ask_requirements_intro(), reply_markup=req_controls())
    await state.set_state(CreateGiveaway.waiting_requirements)
    await cq.answer()

@router.message(CreateGiveaway.waiting_button_text, F.text.len() > 0)
async def custom_btn(m: Message, state: FSMContext):
    data = await state.get_data()
    gid = data.get("gid")
    await set_button_text(gid, m.text.strip())
    await m.answer(ask_requirements_intro(), reply_markup=req_controls())
    await state.set_state(CreateGiveaway.waiting_requirements)

@router.callback_query(CreateGiveaway.waiting_requirements, F.data == "req:add")
async def req_add_prompt(cq: CallbackQuery):
    await cq.message.answer("Надішліть @юзернейм каналу або перешліть повідомлення з каналу")
    await cq.answer()

@router.message(CreateGiveaway.waiting_requirements, F.forward_from_chat | F.text)
async def req_add_handle(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    gid = data.get("gid")
    chat_id = str(m.forward_from_chat.id) if m.forward_from_chat else normalize_channel(m.text)
    ok = await bot_is_admin(bot, chat_id)
    if not ok:
        await m.answer(req_invalid())
        return
    added = await add_requirement(gid, chat_id)
    if added:
        await m.answer(req_added())
    reqs = await list_requirements(gid)
    if reqs:
        await m.answer(ready_to_post())

@router.callback_query(CreateGiveaway.waiting_requirements, F.data == "req:skip")
async def req_skip(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    gid = data.get("gid")
    await allow_no_subs(gid)
    await cq.message.answer(no_requirements())
    await cq.answer()

@router.callback_query(CreateGiveaway.waiting_requirements, F.data == "req:next")
async def req_next(cq: CallbackQuery, state: FSMContext):
    await cq.message.answer(ask_end_datetime())
    await state.set_state(CreateGiveaway.waiting_end_datetime)
    await cq.answer()

@router.message(CreateGiveaway.waiting_end_datetime, F.text.len() > 0)
async def set_end_datetime(m: Message, state: FSMContext):
    txt = m.text.strip()
    import datetime
    try:
        dt = datetime.datetime.strptime(txt, "%Y-%m-%d %H:%M")
        ends_at = int(dt.timestamp())
    except Exception:
        await m.answer("Невірний формат. Приклад: 2025-11-03 18:30")
        return
    data = await state.get_data()
    gid = data.get("gid")
    await set_ends_at(gid, ends_at)
    await m.answer(ask_winners_count())
    await state.set_state(CreateGiveaway.waiting_winners_count)

@router.message(CreateGiveaway.waiting_winners_count, F.text.len() > 0)
async def set_winners(m: Message, state: FSMContext):
    try:
        n = max(1, min(100, int(m.text.strip())))
    except Exception:
        await m.answer("Введіть ціле число від 1 до 100")
        return
    data = await state.get_data()
    gid = data.get("gid")
    await set_winners_count(gid, n)
    await m.answer(ask_post_channel())
    await state.set_state(CreateGiveaway.waiting_post_channel)

@router.message(CreateGiveaway.waiting_post_channel, F.forward_from_chat | F.text)
async def set_post_channel(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    gid = data.get("gid")
    chat_id = str(m.forward_from_chat.id) if m.forward_from_chat else normalize_channel(m.text)
    try:
        info = await bot.get_chat(chat_id)
    except Exception:
        await m.answer("Не вдалося отримати доступ до каналу. Переконайтеся, що бот — адміністратор.")
        return
    await set_post_target(gid, str(info.id), None)
    await state.clear()
    await m.answer("Чернетку створено та ціль публікації збережено. Відкрийте «📦 Мої розіграші», щоб отримати пост і опублікувати.")

def setup(dp):
    dp.include_router(router)
