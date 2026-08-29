from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.inline import channels_manage
from keyboards.reply import main_menu
from services.channels import add_owner_channel, del_owner_channel, list_owner_channels
from services.subscription import bot_is_admin, channel_preview
from utils.formatting import forwarded_chat_id, is_channel_add_message

router = Router()


@router.message(F.text == "📣 Мої канали")
async def my_channels(m: Message, state: FSMContext):
    await state.clear()
    ids = await list_owner_channels(m.from_user.id)
    prev = await channel_preview(m.bot, ids)
    kb = channels_manage([(n, u, c) for (n, u), c in zip(prev, ids)])
    await m.answer("📣 Мої канали", reply_markup=kb or main_menu())
    await m.answer(
        "Надішліть @юзернейм або перешліть повідомлення з каналу, щоб додати"
    )


@router.callback_query(F.data.startswith("mc:del:"))
async def mc_del(cq: CallbackQuery):
    chat_id = cq.data.split(":")[2]
    await del_owner_channel(cq.from_user.id, chat_id)
    try:
        ids = await list_owner_channels(cq.from_user.id)
        prev = await channel_preview(cq.bot, ids)
        kb = channels_manage([(n, u, c) for (n, u), c in zip(prev, ids)])
        await cq.bot.edit_message_reply_markup(
            chat_id=cq.message.chat.id,
            message_id=cq.message.message_id,
            reply_markup=kb,
        )
    except Exception:
        await cq.answer("Видалено, але список не вдалося оновити", show_alert=True)
    else:
        await cq.answer("Видалено")


@router.callback_query(F.data == "mc:add")
async def mc_add_hint(cq: CallbackQuery):
    await cq.message.answer(
        "Надішліть @юзернейм або перешліть повідомлення з каналу, щоб додати"
    )
    await cq.answer()


@router.message(is_channel_add_message)
async def mc_add(m: Message):
    chat_id = forwarded_chat_id(m) or m.text.strip()
    ok = await bot_is_admin(m.bot, chat_id)
    if not ok:
        await m.answer("Бот не адміністратор у каналі або ID некоректний")
        return
    added = await add_owner_channel(m.from_user.id, chat_id)
    if not added:
        await m.answer("Канал уже додано")
        return
    ids = await list_owner_channels(m.from_user.id)
    prev = await channel_preview(m.bot, ids)
    kb = channels_manage([(n, u, c) for (n, u), c in zip(prev, ids)])
    await m.answer("Додано", reply_markup=kb or None)


def setup(dp):
    dp.include_router(router)
