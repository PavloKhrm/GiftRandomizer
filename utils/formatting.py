from aiogram.types import Message, MessageOriginChannel, MessageOriginChat


def normalize_channel(s: str | None) -> str:
    s = str(s or "").strip()
    if s.startswith("@"):
        return s
    if s.startswith("-100"):
        return s
    return s


def forwarded_chat_id(message: Message) -> str | None:
    """Return the source chat for both current and legacy Telegram forwards."""
    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        return str(origin.chat.id)
    if isinstance(origin, MessageOriginChat):
        return str(origin.sender_chat.id)

    legacy_chat = getattr(message, "forward_from_chat", None)
    return str(legacy_chat.id) if legacy_chat else None


def has_channel_reference(message: Message) -> bool:
    return bool(forwarded_chat_id(message) or normalize_channel(message.text))


def is_channel_add_message(message: Message) -> bool:
    text = normalize_channel(message.text)
    return bool(forwarded_chat_id(message) or text.startswith(("@", "-100")))
