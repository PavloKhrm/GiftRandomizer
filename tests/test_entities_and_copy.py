import json

from aiogram.types import MessageEntity

from utils.entities import (
    deserialize_entities,
    serialize_entities,
    without_custom_emoji,
)
from utils.texts import composed_caption


def test_entities_round_trip_and_custom_emoji_removal() -> None:
    entities = [
        MessageEntity(type="bold", offset=0, length=4),
        MessageEntity(
            type="custom_emoji",
            offset=5,
            length=2,
            custom_emoji_id="premium-emoji-123",
        ),
    ]

    serialized = serialize_entities(entities)

    assert serialized == [
        {"type": "bold", "offset": 0, "length": 4},
        {
            "type": "custom_emoji",
            "offset": 5,
            "length": 2,
            "custom_emoji_id": "premium-emoji-123",
        },
    ]
    restored = deserialize_entities(json.dumps(serialized))
    assert serialize_entities(restored) == serialized
    assert serialize_entities(without_custom_emoji(restored)) == [serialized[0]]
    assert serialize_entities(None) == []


def test_composed_caption_preserves_original_text_as_an_exact_prefix() -> None:
    original = "🎁 Оригінальний пост\nТекст із   пробілами та <символами>"

    composed = composed_caption(
        original,
        [("Канал", "@channel")],
        "✨ Спробувати удачу",
        winners_count=2,
    )

    assert composed[: len(original)] == original
    assert composed.startswith(original + "\n\n━━━━━━━━━━━━━━")
    assert "2️⃣ Натисніть «✨ Спробувати удачу»" in composed
