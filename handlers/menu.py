from aiogram import Router, F
from aiogram.types import Message
from states import CreateGiveaway
from aiogram.fsm.context import FSMContext
from utils.texts import create_intro
from keyboards.reply import main_menu

router = Router()

@router.message(F.text == "🎁 Создать розыгрыш")
async def create_start(m: Message, state: FSMContext):
    await state.clear()
    await state.update_data(gid=None)
    await m.answer(create_intro(), reply_markup=main_menu())
    await state.set_state(CreateGiveaway.waiting_post)

def setup(dp):
    dp.include_router(router)
