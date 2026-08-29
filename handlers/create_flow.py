import datetime
import time
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from keyboards.inline import (
    button_style_choices,
    giveaway_actions,
    req_controls,
)
from keyboards.reply import MAIN_MENU_TEXTS
from services.giveaways import (
    add_requirement,
    allow_no_subs,
    clear_requirements,
    create_giveaway,
    get_owned_giveaway,
    list_requirements,
    set_button_design,
    set_button_text,
    set_ends_at,
    set_post,
    set_post_target,
    set_winners_count,
)
from services.posting import validate_payload_length
from services.subscription import bot_is_admin
from states import CreateGiveaway
from utils.entities import serialize_entities, serialize_link_preview_options
from utils.formatting import forwarded_chat_id, has_channel_reference, normalize_channel
from utils.texts import (
    ask_button_style,
    ask_button_text,
    ask_end_datetime,
    ask_post_channel,
    ask_requirements_intro,
    ask_winners_count,
    make_title,
    no_requirements,
    ready_to_post,
    req_added,
    req_invalid,
    text_saved,
)

router = Router()


def not_main_menu(message: Message) -> bool:
    return message.text not in MAIN_MENU_TEXTS


async def _show_requirements(message: Message, state: FSMContext) -> None:
    await message.answer(ask_requirements_intro(), reply_markup=req_controls())
    await state.set_state(CreateGiveaway.waiting_requirements)


@router.message(
    CreateGiveaway.waiting_post,
    F.content_type.in_({"text", "photo", "video", "animation"}),
    not_main_menu,
)
async def capture_post(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    gid = data.get("gid")
    if not gid:
        gid = await create_giveaway(message.from_user.id)
        await state.update_data(gid=gid)

    is_caption = message.caption is not None
    body = message.caption if is_caption else (message.text or "")
    source_entities = message.caption_entities if is_caption else message.entities
    media_type = None
    media_file_id = None
    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.animation:
        media_type = "animation"
        media_file_id = message.animation.file_id

    await set_post(
        gid,
        make_title(body),
        body,
        serialize_entities(source_entities),
        media_type,
        media_file_id,
        bool(message.show_caption_above_media),
        bool(message.has_media_spoiler),
        serialize_link_preview_options(message.link_preview_options),
    )
    await message.answer(text_saved())
    await message.answer(ask_button_text())
    await state.set_state(CreateGiveaway.waiting_button_text)


async def _save_button_text_and_ask_style(
    message: Message, state: FSMContext, text: str
) -> None:
    data = await state.get_data()
    await set_button_text(data["gid"], text)
    await message.answer(ask_button_style(), reply_markup=button_style_choices())
    await state.set_state(CreateGiveaway.waiting_button_style)


@router.message(
    CreateGiveaway.waiting_button_text,
    F.text.len() > 0,
    not_main_menu,
)
async def custom_btn(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if not text:
        await message.answer("Текст кнопки не може бути порожнім.")
        return
    await _save_button_text_and_ask_style(message, state, text)


@router.callback_query(
    CreateGiveaway.waiting_button_style, F.data.startswith("btnstyle:")
)
async def choose_button_style(callback: CallbackQuery, state: FSMContext) -> None:
    style = callback.data.split(":", 1)[1]
    if style not in {"default", "primary", "success", "danger"}:
        await callback.answer("Невідомий стиль", show_alert=True)
        return
    data = await state.get_data()
    await set_button_design(data["gid"], style)
    await _show_requirements(callback.message, state)
    await callback.answer()


@router.callback_query(CreateGiveaway.waiting_requirements, F.data == "req:add")
async def req_add_prompt(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "Надішліть @username каналу або перешліть повідомлення з каналу."
    )
    await callback.answer()


@router.message(
    CreateGiveaway.waiting_requirements,
    has_channel_reference,
    not_main_menu,
)
async def req_add_handle(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    raw = forwarded_chat_id(message) or normalize_channel(message.text)
    try:
        info = await bot.get_chat(raw)
    except Exception:
        await message.answer(req_invalid())
        return
    numeric_id = str(info.id)
    if not await bot_is_admin(bot, numeric_id):
        await message.answer(req_invalid())
        return
    added = await add_requirement(data["gid"], numeric_id)
    await message.answer(req_added() if added else "Цей канал уже є в умовах.")
    if await list_requirements(data["gid"]):
        await message.answer(ready_to_post(), reply_markup=req_controls())


@router.callback_query(CreateGiveaway.waiting_requirements, F.data == "req:skip")
async def req_skip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await clear_requirements(data["gid"])
    await allow_no_subs(data["gid"])
    await callback.message.answer(no_requirements(), reply_markup=req_controls())
    await callback.answer()


@router.callback_query(CreateGiveaway.waiting_requirements, F.data == "req:next")
async def req_next(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(ask_end_datetime(settings.timezone_name))
    await state.set_state(CreateGiveaway.waiting_end_datetime)
    await callback.answer()


@router.message(
    CreateGiveaway.waiting_end_datetime,
    F.text.len() > 0,
    not_main_menu,
)
async def set_end_datetime(message: Message, state: FSMContext) -> None:
    try:
        naive = datetime.datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
        aware = naive.replace(tzinfo=ZoneInfo(settings.timezone_name))
        ends_at = int(aware.timestamp())
        if ends_at <= int(time.time()) + 60:
            raise ValueError("deadline is in the past")
    except Exception:
        await message.answer(
            f"Невірна або вже минула дата. Приклад: 2026-09-03 18:30 ({settings.timezone_name})."
        )
        return
    data = await state.get_data()
    await set_ends_at(data["gid"], ends_at)
    await message.answer(ask_winners_count())
    await state.set_state(CreateGiveaway.waiting_winners_count)


@router.message(
    CreateGiveaway.waiting_winners_count,
    F.text.len() > 0,
    not_main_menu,
)
async def set_winners(message: Message, state: FSMContext) -> None:
    try:
        count = int(message.text.strip())
        if not 1 <= count <= 100:
            raise ValueError
    except Exception:
        await message.answer("Введіть ціле число від 1 до 100.")
        return
    data = await state.get_data()
    await set_winners_count(data["gid"], count)
    await message.answer(ask_post_channel())
    await state.set_state(CreateGiveaway.waiting_post_channel)


@router.message(
    CreateGiveaway.waiting_post_channel,
    has_channel_reference,
    not_main_menu,
)
async def set_post_channel(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    raw = forwarded_chat_id(message) or normalize_channel(message.text)
    try:
        info = await bot.get_chat(raw)
    except Exception:
        await message.answer(
            "Не вдалося знайти канал. Перевірте @username або переслане повідомлення."
        )
        return
    chat_id = str(info.id)
    if not await bot_is_admin(bot, chat_id, require_posting=True):
        await message.answer(
            "Додайте бота до цього каналу як адміністратора й спробуйте ще раз."
        )
        return
    row = await get_owned_giveaway(data["gid"], message.from_user.id)
    if not row:
        await state.clear()
        await message.answer(
            "Чернетку вже видалено або вона недоступна. Почніть новий розіграш."
        )
        return
    final_text = row["caption"] or ""
    try:
        validate_payload_length(final_text, row["media_type"], row["media_file_id"])
    except ValueError as exc:
        await message.answer(
            f"{exc}. У фінальному пості {len(final_text)} символів. "
            "Надішліть зараз коротший авторський текст/медіапост — умови розіграшу збережуться."
        )
        await state.set_state(CreateGiveaway.waiting_post)
        return
    await set_post_target(data["gid"], chat_id)
    await state.clear()
    await message.answer(
        "Чернетка готова ✨ Спочатку перегляньте її, потім натисніть «Опублікувати».",
        reply_markup=giveaway_actions(data["gid"], published=False, closed=False),
    )


def setup(dp) -> None:
    dp.include_router(router)
