from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from services.channels import add_owner_channel, del_owner_channel, list_owner_channels
from services.subscription import channel_preview, bot_is_admin
from keyboards.inline import channels_manage
from keyboards.reply import main_menu

router = Router()

@router.message(F.text == "📣 Мої канали")
async def my_channels(m: Message):
    ids = await list_owner_channels(m.from_user.id)
    prev = await channel_preview(m.bot, ids)
    kb = channels_manage([(n,u,c) for (n,u),c in zip(prev, ids)])
    await m.answer("📣 Мої канали", reply_markup=kb or main_menu())
    await m.answer("Надішліть @юзернейм або перешліть повідомлення з каналу, щоб додати")

@router.callback_query(F.data.startswith("mc:del:"))
async def mc_del(cq: CallbackQuery):
    chat_id = cq.data.split(":")[2]
    await del_owner_channel(cq.from_user.id, chat_id)
    ids = await list_owner_channels(cq.from_user.id)
    prev = await channel_preview(cq.message.bot, ids)
    from keyboards.inline import channels_manage
    kb = channels_manage([(n,u,c) for (n,u),c in zip(prev, ids)])
    await cq.message.edit_reply_markup(reply_markup=kb)
    await cq.answer("Видалено")

@router.callback_query(F.data == "mc:add")
async def mc_add_hint(cq: CallbackQuery):
    await cq.message.answer("Надішліть @юзернейм або перешліть повідомлення з каналу, щоб додати")
    await cq.answer()

@router.message(F.forward_from_chat | F.text.startswith("@"))
async def mc_add(m: Message):
    chat_id = str(m.forward_from_chat.id) if m.forward_from_chat else m.text.strip()
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
    from keyboards.inline import channels_manage
    kb = channels_manage([(n,u,c) for (n,u),c in zip(prev, ids)])
    await m.answer("Додано", reply_markup=kb or None)

def setup(dp):
    dp.include_router(router)
