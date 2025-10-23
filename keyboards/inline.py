from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def button_text_presets():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Участвую!", callback_data="btnpreset:Участвую!")],
        [InlineKeyboardButton(text="Принять участие", callback_data="btnpreset:Принять участие")],
        [InlineKeyboardButton(text="Участвовать", callback_data="btnpreset:Участвовать")]
    ])

def join_button(gid: int, text: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text or "Участвую!", callback_data=f"join:{gid}")]
    ])

def channels_links(items):
    row = [InlineKeyboardButton(text=n, url=f"https://t.me/{u.lstrip('@')}") for n,u in items]
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None

def req_controls():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал", callback_data="req:add")],
        [InlineKeyboardButton(text="✅ Без подписок", callback_data="req:skip")],
        [InlineKeyboardButton(text="➡️ Далее", callback_data="req:next")]
    ])

def channels_manage(owner_view):
    rows = []
    for name, uname, chat_id in owner_view:
        rows.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"mc:del:{chat_id}")])
    rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data="mc:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def giveaways_manage(items):
    rows = []
    for gid, title in items:
        rows.append([InlineKeyboardButton(text=f"#{gid} {title or 'Без названия'}", callback_data=f"gw:open:{gid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

def giveaway_actions(gid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Получить пост", callback_data=f"gw:post:{gid}")],
        [InlineKeyboardButton(text="🎯 Выбрать победителя", callback_data=f"gw:draw:{gid}")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"gw:del:{gid}")]
    ])
