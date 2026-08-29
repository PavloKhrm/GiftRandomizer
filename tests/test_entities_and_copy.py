import json
from types import SimpleNamespace

import pytest
from aiogram.types import LinkPreviewOptions

from handlers.my_giveaways import _send_giveaway
from utils.entities import (
    deserialize_entities,
    deserialize_link_preview_options,
    serialize_entities,
    serialize_link_preview_options,
)


def test_all_author_entities_round_trip_without_degradation() -> None:
    serialized = [
        {"type": "mention", "offset": 0, "length": 1},
        {"type": "hashtag", "offset": 1, "length": 1},
        {"type": "cashtag", "offset": 2, "length": 1},
        {"type": "bot_command", "offset": 3, "length": 1},
        {"type": "url", "offset": 4, "length": 1},
        {"type": "email", "offset": 5, "length": 1},
        {"type": "phone_number", "offset": 6, "length": 1},
        {"type": "bold", "offset": 7, "length": 1},
        {"type": "italic", "offset": 8, "length": 1},
        {"type": "underline", "offset": 9, "length": 1},
        {"type": "strikethrough", "offset": 10, "length": 1},
        {"type": "spoiler", "offset": 11, "length": 1},
        {"type": "blockquote", "offset": 12, "length": 1},
        {"type": "expandable_blockquote", "offset": 13, "length": 1},
        {"type": "code", "offset": 14, "length": 1},
        {"type": "pre", "offset": 15, "length": 1, "language": "python"},
        {
            "type": "text_link",
            "offset": 16,
            "length": 1,
            "url": "https://example.com",
        },
        {
            "type": "text_mention",
            "offset": 17,
            "length": 1,
            "user": {"id": 123, "is_bot": False, "first_name": "Автор"},
        },
        {
            "type": "custom_emoji",
            "offset": 18,
            "length": 2,
            "custom_emoji_id": "premium-emoji-123",
        },
        {
            "type": "date_time",
            "offset": 20,
            "length": 10,
            "unix_time": 1788019200,
            "date_time_format": "dd.MM.yyyy",
        },
    ]

    restored = deserialize_entities(json.dumps(serialized))

    assert serialize_entities(restored) == serialized
    assert serialize_entities(None) == []


def test_link_preview_preferences_round_trip_without_aiogram_defaults() -> None:
    options = LinkPreviewOptions(
        url="https://example.com",
        prefer_large_media=True,
        show_above_text=True,
    )

    serialized = serialize_link_preview_options(options)
    restored = deserialize_link_preview_options(json.dumps(serialized))

    assert serialized == {
        "url": "https://example.com",
        "prefer_large_media": True,
        "show_above_text": True,
    }
    assert serialize_link_preview_options(restored) == serialized


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


class RecordingMediaBot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | str, str, dict]] = []
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=-100123),
            message_id=100,
        )

    async def _record(self, kind, chat_id, file_id, **kwargs):
        self.calls.append((kind, chat_id, file_id, kwargs))
        return self.message

    async def send_photo(self, chat_id, file_id, **kwargs):
        return await self._record("photo", chat_id, file_id, **kwargs)

    async def send_video(self, chat_id, file_id, **kwargs):
        return await self._record("video", chat_id, file_id, **kwargs)

    async def send_animation(self, chat_id, file_id, **kwargs):
        return await self._record("animation", chat_id, file_id, **kwargs)


@pytest.mark.asyncio
async def test_giveaway_post_is_exactly_the_authors_text_and_entities() -> None:
    author_text = "🎁 Авторський пост\nЦитата автора\nУмови автора"
    serialized = [
        {
            "type": "custom_emoji",
            "offset": 0,
            "length": 2,
            "custom_emoji_id": "premium-emoji-123",
        },
        {"type": "blockquote", "offset": 20, "length": 13},
    ]
    row = {
        "id": 17,
        "caption": author_text,
        "caption_entities": serialized,
        "media_type": None,
        "media_file_id": None,
        "show_caption_above_media": False,
        "has_media_spoiler": False,
        "link_preview_options": {
            "url": "https://example.com",
            "prefer_large_media": True,
            "show_above_text": True,
        },
        "button_text": "Будь-який текст кнопки",
        "button_style": "success",
        "button_icon_custom_emoji_id": "legacy-button-icon-must-be-ignored",
        "ends_at": 1788019200,
        "winners_count": 10,
    }
    bot = RecordingBot()

    result = await _send_giveaway(bot, -100123, row, preview=False)

    assert result.message is bot.message
    assert len(bot.calls) == 1
    _, sent_text, kwargs = bot.calls[0]
    assert sent_text == author_text
    assert "ЯК ВЗЯТИ УЧАСТЬ" not in sent_text
    assert "Переможців бот обере" not in sent_text
    assert serialize_entities(kwargs["entities"]) == serialized
    assert kwargs["link_preview_options"].model_dump(
        mode="json", exclude_none=True
    ) == {
        "url": "https://example.com",
        "prefer_large_media": True,
        "show_above_text": True,
    }
    button = kwargs["reply_markup"].inline_keyboard[0][0]
    assert button.text == "Будь-який текст кнопки"
    assert button.icon_custom_emoji_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("media_type", ["photo", "video", "animation"])
async def test_media_caption_is_exactly_the_authors_text_and_entities(
    media_type: str,
) -> None:
    author_text = "🔥 Авторський caption\n> без дописаного footer"
    serialized = [
        {
            "type": "custom_emoji",
            "offset": 0,
            "length": 2,
            "custom_emoji_id": "premium-emoji-456",
        },
        {"type": "expandable_blockquote", "offset": 22, "length": 20},
    ]
    row = {
        "id": 18,
        "caption": author_text,
        "caption_entities": serialized,
        "media_type": media_type,
        "media_file_id": "telegram-file-id",
        "show_caption_above_media": True,
        "has_media_spoiler": True,
        "link_preview_options": None,
        "button_text": "Взяти участь",
        "button_style": "primary",
    }
    bot = RecordingMediaBot()

    await _send_giveaway(bot, -100123, row, preview=False)

    assert len(bot.calls) == 1
    kind, _, file_id, kwargs = bot.calls[0]
    assert kind == media_type
    assert file_id == "telegram-file-id"
    assert kwargs["caption"] == author_text
    assert serialize_entities(kwargs["caption_entities"]) == serialized
    assert kwargs["parse_mode"] is None
    assert kwargs["show_caption_above_media"] is True
    assert kwargs["has_spoiler"] is True
    assert "entities" not in kwargs
