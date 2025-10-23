from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Створити розіграш")],
            [KeyboardButton(text="📦 Мої розіграші"), KeyboardButton(text="📣 Мої канали")]
        ],
        resize_keyboard=True
    )
