from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MAIN_MENU_TEXTS = {
    "🎁 Створити розіграш",
    "📦 Мої розіграші",
    "📣 Мої канали",
}


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Створити розіграш")],
            [
                KeyboardButton(text="📦 Мої розіграші"),
                KeyboardButton(text="📣 Мої канали"),
            ],
        ],
        resize_keyboard=True,
    )
