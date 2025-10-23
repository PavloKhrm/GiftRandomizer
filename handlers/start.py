from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from keyboards.reply import main_menu

router = Router()

@router.message(CommandStart())
async def start(m: Message):
    await m.answer("Главное меню", reply_markup=main_menu())

def setup(dp):
    dp.include_router(router)
