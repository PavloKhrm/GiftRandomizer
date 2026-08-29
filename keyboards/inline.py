from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _styled_button(
    *,
    text: str,
    callback_data: str,
    style: str | None = None,
    icon_custom_emoji_id: str | None = None,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        style=style,
        icon_custom_emoji_id=icon_custom_emoji_id,
    )


def button_text_presets() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text="🎁 Беру участь!",
                    callback_data="btnpreset:🎁 Беру участь!",
                    style="success",
                )
            ],
            [
                _styled_button(
                    text="✨ Спробувати удачу",
                    callback_data="btnpreset:✨ Спробувати удачу",
                    style="primary",
                )
            ],
            [
                _styled_button(
                    text="🔥 Хочу приз",
                    callback_data="btnpreset:🔥 Хочу приз",
                    style="danger",
                )
            ],
        ]
    )


def button_style_choices() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text="🟢 Зелена", callback_data="btnstyle:success", style="success"
                )
            ],
            [
                _styled_button(
                    text="🔵 Синя", callback_data="btnstyle:primary", style="primary"
                )
            ],
            [
                _styled_button(
                    text="🔴 Червона", callback_data="btnstyle:danger", style="danger"
                )
            ],
            [_styled_button(text="⚪️ Стандартна", callback_data="btnstyle:default")],
        ]
    )


def button_icon_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text="Без анімованої іконки", callback_data="btnicon:skip"
                )
            ],
        ]
    )


def join_button(
    gid: int,
    text: str,
    style: str | None = "success",
    icon_custom_emoji_id: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text=text or "🎁 Беру участь!",
                    callback_data=f"join:{gid}",
                    style=style,
                    icon_custom_emoji_id=icon_custom_emoji_id,
                )
            ]
        ]
    )


def preview_button(
    gid: int,
    text: str,
    style: str | None = "success",
    icon_custom_emoji_id: str | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text=text or "🎁 Беру участь!",
                    callback_data=f"preview:noop:{gid}",
                    style=style,
                    icon_custom_emoji_id=icon_custom_emoji_id,
                )
            ]
        ]
    )


def channels_links(items) -> InlineKeyboardMarkup | None:
    row = [
        InlineKeyboardButton(text=name, url=f"https://t.me/{username.lstrip('@')}")
        for name, username in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else None


def req_controls() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text="➕ Додати канал", callback_data="req:add", style="primary"
                )
            ],
            [
                _styled_button(
                    text="✅ Без додаткових підписок", callback_data="req:skip"
                )
            ],
            [_styled_button(text="➡️ Далі", callback_data="req:next", style="success")],
        ]
    )


def channels_manage(owner_view) -> InlineKeyboardMarkup:
    rows = []
    for name, _username, chat_id in owner_view:
        rows.append(
            [
                _styled_button(
                    text=f"Видалити · {name}",
                    callback_data=f"mc:del:{chat_id}",
                    style="danger",
                )
            ]
        )
    rows.append(
        [_styled_button(text="➕ Додати", callback_data="mc:add", style="primary")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def giveaways_manage(items) -> InlineKeyboardMarkup | None:
    rows = []
    for item in items:
        status = (
            "✅"
            if item["closed"]
            else (
                "⚠️"
                if item["draw_status"] == "delivery_uncertain"
                or item["publish_status"]
                in {"legacy_unknown", "publish_uncertain", "publishing"}
                else (
                    "⏳"
                    if item["draw_status"] in {"drawing", "delivering"}
                    else ("🟢" if item["post_message_id"] else "📝")
                )
            )
        )
        title = item["title"] or "Без назви"
        rows.append(
            [
                _styled_button(
                    text=f"{status} #{item['id']} · {title}",
                    callback_data=f"gw:open:{item['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def giveaway_actions(
    gid: int,
    *,
    published: bool,
    closed: bool,
    publish_status: str = "draft",
    draw_status: str = "pending",
    publish_recovery_allowed: bool = True,
) -> InlineKeyboardMarkup:
    rows = [
        [
            _styled_button(
                text="👀 Попередній перегляд",
                callback_data=f"gw:preview:{gid}",
                style="primary",
            )
        ]
    ]
    if not published and not closed and publish_status == "draft":
        rows.append(
            [
                _styled_button(
                    text="🚀 Опублікувати",
                    callback_data=f"gw:post:{gid}",
                    style="success",
                )
            ]
        )
    if (
        not published
        and not closed
        and publish_status in {"publishing", "publish_uncertain", "legacy_unknown"}
        and publish_recovery_allowed
    ):
        rows.append(
            [
                _styled_button(
                    text="🛠 Я перевірив канал — скинути статус",
                    callback_data=f"gw:postreset:{gid}",
                    style="danger",
                )
            ]
        )
    if published and not closed and draw_status in {"pending", "failed", "dead_letter"}:
        rows.append(
            [
                _styled_button(
                    text="🎯 Провести зараз",
                    callback_data=f"gw:draw:{gid}",
                    style="primary",
                )
            ]
        )
    if published and not closed and draw_status == "delivery_uncertain":
        rows.append(
            [
                _styled_button(
                    text="🚨 Звірити підсумки з каналом",
                    callback_data=f"gw:drawaudit:{gid}",
                    style="danger",
                )
            ]
        )
    deletion_locked = publish_status in {
        "publishing",
        "publish_uncertain",
    } or draw_status in {"drawing", "delivering", "delivery_uncertain"}
    if not deletion_locked:
        rows.append(
            [
                _styled_button(
                    text="🗑 Видалити",
                    callback_data=f"gw:del:{gid}",
                    style="danger",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def publish_recovery_confirm(gid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text="Так, у каналі немає нового поста",
                    callback_data=f"gw:postreset_confirm:{gid}",
                    style="danger",
                )
            ],
            [
                _styled_button(
                    text="Скасувати",
                    callback_data=f"gw:postreset_cancel:{gid}",
                )
            ],
        ]
    )


def draw_delivery_audit(
    gid: int,
    expected_parts: int | None = None,
) -> InlineKeyboardMarkup:
    sent_label = (
        f"Усі {expected_parts} част. є — завершити"
        if expected_parts and expected_parts > 1
        else "Увесь підсумок є — завершити"
    )
    retry_label = (
        "Бракує частини — доправити"
        if expected_parts and expected_parts > 1
        else "Підсумку немає — повторити"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _styled_button(
                    text=sent_label,
                    callback_data=f"gw:drawaudit_sent:{gid}",
                    style="success",
                )
            ],
            [
                _styled_button(
                    text=retry_label,
                    callback_data=f"gw:drawaudit_retry:{gid}",
                    style="danger",
                )
            ],
            [
                _styled_button(
                    text="Скасувати",
                    callback_data=f"gw:drawaudit_cancel:{gid}",
                )
            ],
        ]
    )
