import json
from collections.abc import Iterable
from typing import Any

from aiogram.types import MessageEntity


def serialize_entities(
    entities: Iterable[MessageEntity] | None,
) -> list[dict[str, Any]]:
    return [
        entity.model_dump(mode="json", exclude_none=True) for entity in (entities or [])
    ]


def deserialize_entities(value: Any) -> list[MessageEntity]:
    if not value:
        return []
    raw = json.loads(value) if isinstance(value, str) else value
    return [MessageEntity.model_validate(item) for item in raw]


def without_custom_emoji(entities: Iterable[MessageEntity]) -> list[MessageEntity]:
    return [entity for entity in entities if entity.type != "custom_emoji"]


def first_custom_emoji_id(entities: Iterable[MessageEntity] | None) -> str | None:
    for entity in entities or []:
        if entity.type == "custom_emoji" and entity.custom_emoji_id:
            return entity.custom_emoji_id
    return None
