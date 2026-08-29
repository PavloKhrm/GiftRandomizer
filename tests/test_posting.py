from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from aiogram.types import MessageEntity

from services.posting import build_and_send, validate_payload_length
from utils.entities import serialize_entities


class RecordingBot:
    def __init__(self) -> None:
        self.calls: list[tuple[int | str, str, dict]] = []
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123),
            message_id=99,
        )

    async def send_message(self, chat_id: int | str, text: str, **kwargs):
        self.calls.append((chat_id, text, kwargs))
        return self.message


@pytest.mark.asyncio
async def test_rejected_style_is_not_silently_removed() -> None:
    class StyleRejectingBot(RecordingBot):
        async def send_message(self, chat_id: int | str, text: str, **kwargs):
            self.calls.append((chat_id, text, kwargs))
            button = kwargs["reply_markup"].inline_keyboard[0][0]
            raise TelegramBadRequest(
                method=SendMessage(chat_id=chat_id, text=text),
                message=f"style unsupported: {button.style}",
            )

    text = "🎁 Gift post\nQuoted text\nExpandable text"
    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id="caption-emoji",
        ),
        MessageEntity(type="blockquote", offset=13, length=11),
        MessageEntity(type="expandable_blockquote", offset=25, length=15),
    ]
    expected_entities = serialize_entities(entities)
    bot = StyleRejectingBot()

    with pytest.raises(TelegramBadRequest, match="style unsupported"):
        await build_and_send(
            bot,
            -100123,
            17,
            text,
            entities,
            None,
            None,
            "Будь-яка кнопка",
            "danger",
        )

    assert len(bot.calls) == 1
    _, sent_text, kwargs = bot.calls[0]
    assert sent_text == text
    assert serialize_entities(kwargs["entities"]) == expected_entities
    button = kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.style == "danger"
    assert button.icon_custom_emoji_id is None


@pytest.mark.asyncio
async def test_rejected_premium_emoji_is_never_silently_removed() -> None:
    class EntityRejectingBot(RecordingBot):
        async def send_message(self, chat_id: int | str, text: str, **kwargs):
            self.calls.append((chat_id, text, kwargs))
            raise TelegramBadRequest(
                method=SendMessage(chat_id=chat_id, text=text),
                message="custom emoji rejected",
            )

    entities = [
        MessageEntity(
            type="custom_emoji",
            offset=0,
            length=2,
            custom_emoji_id="caption-emoji",
        )
    ]
    bot = EntityRejectingBot()

    with pytest.raises(TelegramBadRequest, match="custom emoji rejected"):
        await build_and_send(
            bot,
            -100123,
            17,
            "🎁 Gift post",
            entities,
            None,
            None,
            "Join",
            "primary",
        )

    assert len(bot.calls) == 1
    assert all(
        [entity.type for entity in call[2]["entities"]] == ["custom_emoji"]
        for call in bot.calls
    )


@pytest.mark.asyncio
async def test_button_text_is_author_supplied_without_a_bot_defined_limit() -> None:
    bot = RecordingBot()
    label = "🔥" * 80

    await build_and_send(
        bot,
        -100123,
        17,
        "Author text",
        [],
        None,
        None,
        label,
        "success",
    )

    assert bot.calls[0][2]["reply_markup"].inline_keyboard[0][0].text == label


def test_payload_limits_count_unicode_characters_not_utf16_units() -> None:
    validate_payload_length("🎁" * 1024, "photo", "file-id")
    validate_payload_length("🎁" * 4096, None, None)

    with pytest.raises(ValueError, match="1024"):
        validate_payload_length("🎁" * 1025, "photo", "file-id")
    with pytest.raises(ValueError, match="4096"):
        validate_payload_length("🎁" * 4097, None, None)
