from aiogram import Bot
from keyboards.inline import join_button

async def build_and_send(bot: Bot, chat_id: int, gid: int, title: str | None, caption: str | None, media_type: str | None, media_file_id: str | None, button_text: str):
    text = ""
    if title:
        text += f"<b>{title}</b>\n\n"
    if caption:
        text += caption
    kb = join_button(gid, button_text or "Участвую!")
    if media_type and media_file_id:
        if media_type == "photo":
            await bot.send_photo(chat_id, media_file_id, caption=text or None, reply_markup=kb)
            return
        if media_type == "video":
            await bot.send_video(chat_id, media_file_id, caption=text or None, reply_markup=kb)
            return
        if media_type == "animation":
            await bot.send_animation(chat_id, media_file_id, caption=text or None, reply_markup=kb)
            return
    await bot.send_message(chat_id, text or "Розыгрыш", reply_markup=kb)
