import asyncio

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)


class SubscriptionCheckUnavailable(RuntimeError):
    pass


async def _get_chat_member(
    bot: Bot,
    chat_id: str,
    user_id: int,
    *,
    retry: bool = True,
):
    attempts = 3 if retry else 1
    for attempt in range(attempts):
        try:
            return await bot.get_chat_member(chat_id, user_id)
        except TelegramRetryAfter as exc:
            if attempt + 1 == attempts:
                raise SubscriptionCheckUnavailable("Telegram rate limit") from exc
            await asyncio.sleep(min(float(exc.retry_after), 10.0))
        except (TelegramNetworkError, TelegramServerError) as exc:
            if attempt + 1 == attempts:
                raise SubscriptionCheckUnavailable(
                    "Telegram is temporarily unavailable"
                ) from exc
            await asyncio.sleep(1 + attempt)
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            raise SubscriptionCheckUnavailable(
                f"Telegram cannot verify membership in {chat_id}"
            ) from exc


def _is_active_member(chat_member) -> bool:
    if chat_member.status in ("member", "administrator", "creator"):
        return True
    return chat_member.status == "restricted" and bool(
        getattr(chat_member, "is_member", False)
    )


async def is_member_everywhere(
    bot: Bot,
    user_id: int,
    channel_ids: list[str],
    *,
    retry: bool = True,
    concurrent: bool = False,
) -> bool:
    if concurrent:
        members = await asyncio.gather(
            *(
                _get_chat_member(bot, channel_id, user_id, retry=retry)
                for channel_id in channel_ids
            )
        )
        return all(_is_active_member(member) for member in members)

    for channel_id in channel_ids:
        member = await _get_chat_member(bot, channel_id, user_id, retry=retry)
        if not _is_active_member(member):
            return False
    return True


async def channel_preview(bot: Bot, channel_ids: list[str]):
    out = []
    for ch in channel_ids:
        try:
            info = await bot.get_chat(ch)
            uname = (info.username and f"@{info.username}") or str(info.id)
            name = info.title or uname
            out.append((name, uname))
        except Exception:
            out.append((ch, ch))
    return out


async def bot_is_admin(bot: Bot, chat_id: str, *, require_posting: bool = False):
    try:
        me = await bot.get_me()
        cm = await bot.get_chat_member(chat_id, me.id)
        if cm.status not in ("administrator", "creator"):
            return False
        if require_posting and cm.status == "administrator":
            return bool(getattr(cm, "can_post_messages", False))
        return True
    except Exception:
        return False
