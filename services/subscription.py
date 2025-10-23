from aiogram import Bot

async def is_member_everywhere(bot: Bot, user_id: int, channel_ids: list[str]):
    for ch in channel_ids:
        try:
            cm = await bot.get_chat_member(ch, user_id)
            if cm.status not in ("member","administrator","creator"):
                return False
        except Exception:
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

async def bot_is_admin(bot: Bot, chat_id: str):
    try:
        me = await bot.get_me()
        cm = await bot.get_chat_member(chat_id, me.id)
        return cm.status in ("administrator","creator")
    except Exception:
        return False
