from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import LinkPreviewOptions, Message, MessageEntity

from keyboards.inline import join_button, preview_button


@dataclass(frozen=True)
class SendResult:
    message: Message


def validate_payload_length(
    text: str,
    media_type: str | None,
    media_file_id: str | None,
) -> None:
    if media_type and media_file_id and len(text) > 1024:
        raise ValueError("Підпис медіапоста перевищує ліміт Telegram у 1024 символи")
    if not (media_type and media_file_id) and len(text) > 4096:
        raise ValueError("Текст поста перевищує ліміт Telegram у 4096 символів")


async def _send_once(
    bot: Bot,
    chat_id: int | str,
    gid: int,
    text: str,
    entities: list[MessageEntity],
    media_type: str | None,
    media_file_id: str | None,
    show_caption_above_media: bool,
    has_media_spoiler: bool,
    link_preview_options: LinkPreviewOptions | None,
    button_text: str,
    button_style: str | None,
    preview: bool,
) -> Message:
    validate_payload_length(text, media_type, media_file_id)
    if not button_text or not button_text.strip():
        raise ValueError("Текст кнопки не заданий")
    keyboard_factory = preview_button if preview else join_button
    keyboard = keyboard_factory(gid, button_text, button_style)

    common = {
        "reply_markup": keyboard,
        "parse_mode": None,
    }
    if media_type and media_file_id:
        media_common = {
            **common,
            "caption": text or None,
            "caption_entities": entities or None,
            "show_caption_above_media": show_caption_above_media or None,
            "has_spoiler": has_media_spoiler or None,
        }
        if media_type == "photo":
            return await bot.send_photo(chat_id, media_file_id, **media_common)
        if media_type == "video":
            return await bot.send_video(chat_id, media_file_id, **media_common)
        if media_type == "animation":
            return await bot.send_animation(chat_id, media_file_id, **media_common)

    if not text:
        raise ValueError("Текст авторського поста порожній")
    return await bot.send_message(
        chat_id,
        text,
        entities=entities or None,
        link_preview_options=link_preview_options,
        **common,
    )


async def build_and_send(
    bot: Bot,
    chat_id: int | str,
    gid: int,
    text: str,
    entities: list[MessageEntity],
    media_type: str | None,
    media_file_id: str | None,
    button_text: str,
    button_style: str | None,
    *,
    show_caption_above_media: bool = False,
    has_media_spoiler: bool = False,
    link_preview_options: LinkPreviewOptions | None = None,
    preview: bool = False,
    before_send: Callable[[], Awaitable[None]] | None = None,
) -> SendResult:
    style = None if button_style in (None, "default") else button_style
    if before_send is not None:
        await before_send()
    message = await _send_once(
        bot,
        chat_id,
        gid,
        text,
        entities,
        media_type,
        media_file_id,
        show_caption_above_media,
        has_media_spoiler,
        link_preview_options,
        button_text,
        style,
        preview,
    )
    return SendResult(message=message)
