from keyboards.inline import giveaway_actions, join_button, preview_button


def test_join_button_serializes_style_and_custom_emoji_icon() -> None:
    markup = join_button(
        42,
        "🔥 Хочу приз",
        style="danger",
        icon_custom_emoji_id="button-icon-456",
    )

    assert markup.model_dump(mode="json", exclude_none=True) == {
        "inline_keyboard": [
            [
                {
                    "text": "🔥 Хочу приз",
                    "icon_custom_emoji_id": "button-icon-456",
                    "style": "danger",
                    "callback_data": "join:42",
                }
            ]
        ]
    }


def test_preview_button_keeps_design_but_uses_non_joining_callback() -> None:
    button = preview_button(
        7,
        "✨ Спробувати",
        style="primary",
        icon_custom_emoji_id="preview-icon",
    ).inline_keyboard[0][0]

    assert button.style == "primary"
    assert button.icon_custom_emoji_id == "preview-icon"
    assert button.callback_data == "preview:noop:7"


def test_uncertain_delivery_requires_audit_instead_of_direct_redraw() -> None:
    markup = giveaway_actions(
        77,
        published=True,
        closed=False,
        publish_status="active",
        draw_status="delivery_uncertain",
    )
    callbacks = {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }

    assert "gw:drawaudit:77" in callbacks
    assert "gw:draw:77" not in callbacks
    assert "gw:del:77" not in callbacks
