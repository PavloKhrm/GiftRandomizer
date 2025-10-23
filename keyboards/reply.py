from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Создать розыгрыш")],
            [KeyboardButton(text="📦 Мои розыгрыши"), KeyboardButton(text="📣 Мои каналы")]
        ],
        resize_keyboard=True
    )
