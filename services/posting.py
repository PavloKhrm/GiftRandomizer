from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, MessageEntity

from keyboards.inline import join_button, preview_button
from utils.entities import without_custom_emoji


@dataclass(frozen=True)
class SendResult:
    message: Message
    custom_emoji_fallback: bool = False
    button_icon_fallback: bool = False
    button_style_fallback: bool = False


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
    button_text: str,
    button_style: str | None,
    button_icon_custom_emoji_id: str | None,
    preview: bool,
) -> Message:
    validate_payload_length(text, media_type, media_file_id)
    keyboard_factory = preview_button if preview else join_button
    keyboard = keyboard_factory(
        gid,
        button_text or "🎁 Беру участь",
        button_style,
        button_icon_custom_emoji_id,
    )

    common = {
        "reply_markup": keyboard,
        "parse_mode": None,
    }
    if media_type and media_file_id:
        media_common = {
            **common,
            "caption": text or None,
            "caption_entities": entities or None,
        }
        if media_type == "photo":
            return await bot.send_photo(chat_id, media_file_id, **media_common)
        if media_type == "video":
            return await bot.send_video(chat_id, media_file_id, **media_common)
        if media_type == "animation":
            return await bot.send_animation(chat_id, media_file_id, **media_common)

    return await bot.send_message(
        chat_id,
        text or "🎁 Розіграш",
        entities=entities or None,
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
    button_icon_custom_emoji_id: str | None,
    *,
    preview: bool = False,
    before_send: Callable[[], Awaitable[None]] | None = None,
) -> SendResult:
    style = None if button_style in (None, "default") else button_style
    clean_entities = without_custom_emoji(entities)
    has_custom_emoji = len(clean_entities) != len(entities)

    attempts: list[tuple[list[MessageEntity], str | None, str | None]] = []

    def add_attempt(
        attempt_entities: list[MessageEntity],
        attempt_style: str | None,
        attempt_icon: str | None,
    ) -> None:
        signature = (
            tuple(
                entity.model_dump_json(exclude_none=True) for entity in attempt_entities
            ),
            attempt_style,
            attempt_icon,
        )
        if signature not in {
            (
                tuple(
                    entity.model_dump_json(exclude_none=True) for entity in old_entities
                ),
                old_style,
                old_icon,
            )
            for old_entities, old_style, old_icon in attempts
        }:
            attempts.append((attempt_entities, attempt_style, attempt_icon))

    add_attempt(entities, style, button_icon_custom_emoji_id)
    if button_icon_custom_emoji_id:
        add_attempt(entities, style, None)
    if has_custom_emoji:
        add_attempt(clean_entities, style, button_icon_custom_emoji_id)
    if style:
        add_attempt(entities, None, button_icon_custom_emoji_id)
    if has_custom_emoji and button_icon_custom_emoji_id:
        add_attempt(clean_entities, style, None)
    if style and button_icon_custom_emoji_id:
        add_attempt(entities, None, None)
    if has_custom_emoji and style:
        add_attempt(clean_entities, None, button_icon_custom_emoji_id)
    add_attempt(clean_entities, None, None)

    last_error: TelegramBadRequest | None = None
    for attempt_entities, attempt_style, attempt_icon in attempts:
        try:
            if before_send is not None:
                await before_send()
            message = await _send_once(
                bot,
                chat_id,
                gid,
                text,
                attempt_entities,
                media_type,
                media_file_id,
                button_text,
                attempt_style,
                attempt_icon,
                preview,
            )
            return SendResult(
                message=message,
                custom_emoji_fallback=has_custom_emoji
                and not any(
                    entity.type == "custom_emoji" for entity in attempt_entities
                ),
                button_icon_fallback=bool(
                    button_icon_custom_emoji_id and not attempt_icon
                ),
                button_style_fallback=bool(style and not attempt_style),
            )
        except TelegramBadRequest as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise RuntimeError("No Telegram send attempts were created")
