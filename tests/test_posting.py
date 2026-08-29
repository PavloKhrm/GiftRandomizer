from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import MessageEntity

from services.posting import build_and_send, validate_payload_length


class FallbackBot:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls: list[tuple[int | str, str, dict]] = []
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123),
            message_id=99,
        )

    async def send_message(self, chat_id: int | str, text: str, **kwargs):
        self.calls.append((chat_id, text, kwargs))
        if len(self.calls) <= self.failures:
            raise TelegramBadRequest(
                method=SendMessage(chat_id=chat_id, text=text),
                message=f"unsupported design {len(self.calls)}",
            )
        return self.message


@pytest.mark.asyncio
async def test_posting_falls_back_icon_then_custom_emoji_then_style() -> None:
    bot = FallbackBot(failures=7)
    entities = [
        MessageEntity(type="bold", offset=0, length=4),
        MessageEntity(
            type="custom_emoji",
            offset=5,
            length=2,
            custom_emoji_id="caption-emoji",
        ),
    ]

    result = await build_and_send(
        bot,
        -100123,
        17,
        "Gift post",
        entities,
        None,
        None,
        "Join",
        "danger",
        "button-icon",
    )

    assert result.message is bot.message
    assert result.button_icon_fallback is True
    assert result.custom_emoji_fallback is True
    assert result.button_style_fallback is True
    assert len(bot.calls) == 8

    buttons = [call[2]["reply_markup"].inline_keyboard[0][0] for call in bot.calls]
    assert [(button.style, button.icon_custom_emoji_id) for button in buttons] == [
        ("danger", "button-icon"),
        ("danger", None),
        ("danger", "button-icon"),
        (None, "button-icon"),
        ("danger", None),
        (None, None),
        (None, "button-icon"),
        (None, None),
    ]
    assert [[entity.type for entity in call[2]["entities"]] for call in bot.calls] == [
        ["bold", "custom_emoji"],
        ["bold", "custom_emoji"],
        ["bold"],
        ["bold", "custom_emoji"],
        ["bold"],
        ["bold", "custom_emoji"],
        ["bold"],
        ["bold"],
    ]


@pytest.mark.asyncio
async def test_style_fallback_keeps_supported_custom_emoji() -> None:
    class StyleRejectingBot(FallbackBot):
        async def send_message(self, chat_id: int | str, text: str, **kwargs):
            self.calls.append((chat_id, text, kwargs))
            button = kwargs["reply_markup"].inline_keyboard[0][0]
            if button.style:
                raise TelegramBadRequest(
                    method=SendMessage(chat_id=chat_id, text=text),
                    message="style unsupported",
                )
            return self.message

    bot = StyleRejectingBot(failures=0)
    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id="caption-emoji",
        )
    ]

    result = await build_and_send(
        bot,
        -100123,
        17,
        "🎁 Gift post",
        entities,
        None,
        None,
        "Join",
        "danger",
        None,
    )

    assert result.button_style_fallback is True
    assert result.custom_emoji_fallback is False
    assert [entity.type for entity in bot.calls[-1][2]["entities"]] == ["custom_emoji"]


@pytest.mark.asyncio
async def test_invalid_caption_emoji_fallback_keeps_valid_button_icon() -> None:
    class CaptionEmojiRejectingBot(FallbackBot):
        async def send_message(self, chat_id: int | str, text: str, **kwargs):
            self.calls.append((chat_id, text, kwargs))
            if any(
                entity.type == "custom_emoji"
                for entity in (kwargs.get("entities") or [])
            ):
                raise TelegramBadRequest(
                    method=SendMessage(chat_id=chat_id, text=text),
                    message="caption custom emoji is not allowed",
                )
            return self.message

    bot = CaptionEmojiRejectingBot(failures=0)
    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id="caption-emoji",
        )
    ]

    result = await build_and_send(
        bot,
        -100123,
        17,
        "🎁 Gift post",
        entities,
        None,
        None,
        "Join",
        "success",
        "valid-button-icon",
    )

    button = bot.calls[-1][2]["reply_markup"].inline_keyboard[0][0]
    assert result.custom_emoji_fallback is True
    assert result.button_icon_fallback is False
    assert button.icon_custom_emoji_id == "valid-button-icon"


def test_payload_limits_count_unicode_characters_not_utf16_units() -> None:
    validate_payload_length("🎁" * 1024, "photo", "file-id")
    validate_payload_length("🎁" * 4096, None, None)

    with pytest.raises(ValueError, match="1024"):
        validate_payload_length("🎁" * 1025, "photo", "file-id")
    with pytest.raises(ValueError, match="4096"):
        validate_payload_length("🎁" * 4097, None, None)
