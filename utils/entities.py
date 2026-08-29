import json
from typing import Any

from aiogram.client.default import Default
from aiogram.types import LinkPreviewOptions, MessageEntity


def serialize_entities(
    entities: list[MessageEntity] | None,
) -> list[dict[str, Any]]:
    return [
        entity.model_dump(mode="json", exclude_none=True) for entity in (entities or [])
    ]


def deserialize_entities(value: Any) -> list[MessageEntity]:
    if not value:
        return []
    raw = json.loads(value) if isinstance(value, str) else value
    return [MessageEntity.model_validate(item) for item in raw]


def deserialize_link_preview_options(value: Any) -> LinkPreviewOptions | None:
    if not value:
        return None
    raw = json.loads(value) if isinstance(value, str) else value
    return LinkPreviewOptions(
        is_disabled=raw.get("is_disabled"),
        url=raw.get("url"),
        prefer_small_media=raw.get("prefer_small_media"),
        prefer_large_media=raw.get("prefer_large_media"),
        show_above_text=raw.get("show_above_text"),
    )


def serialize_link_preview_options(
    value: LinkPreviewOptions | None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    serialized = {}
    for field in (
        "is_disabled",
        "url",
        "prefer_small_media",
        "prefer_large_media",
        "show_above_text",
    ):
        field_value = getattr(value, field, None)
        if field_value is not None and not isinstance(field_value, Default):
            serialized[field] = field_value
    return serialized or None
