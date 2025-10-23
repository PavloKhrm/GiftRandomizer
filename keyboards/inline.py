from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def button_text_presets():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Беру участь!", callback_data="btnpreset:Беру участь!")],
        [InlineKeyboardButton(text="Взяти участь", callback_data="btnpreset:Взяти участь")],
        [InlineKeyboardButton(text="Участь", callback_data="btnpreset:Участь")]
    ])

def join_button(gid: int, text: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text or "Беру участь!", callback_data=f"join:{gid}")]
    ])

def channels_links(items):
    row = [InlineKeyboardButton(text=n, url=f"https://t.me/{u.lstrip('@')}") for n,u in items]
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None

def req_controls():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати канал", callback_data="req:add")],
        [InlineKeyboardButton(text="✅ Без підписок", callback_data="req:skip")],
        [InlineKeyboardButton(text="➡️ Далі", callback_data="req:next")]
    ])

def channels_manage(owner_view):
    rows = []
    for name, uname, chat_id in owner_view:
        rows.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"mc:del:{chat_id}")])
    rows.append([InlineKeyboardButton(text="➕ Додати", callback_data="mc:add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def giveaways_manage(items):
    rows = []
    for gid, title in items:
        rows.append([InlineKeyboardButton(text=f"#{gid} {title or 'Без назви'}", callback_data=f"gw:open:{gid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

def giveaway_actions(gid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Отримати пост", callback_data=f"gw:post:{gid}")],
        [InlineKeyboardButton(text="🎯 Обрати переможця", callback_data=f"gw:draw:{gid}")],
        [InlineKeyboardButton(text="🗑 Видалити", callback_data=f"gw:del:{gid}")]
    ])
