from aiogram.fsm.state import StatesGroup, State

class CreateGiveaway(StatesGroup):
    waiting_post = State()
    waiting_button_text = State()
    waiting_requirements = State()
    waiting_end_datetime = State()
    waiting_winners_count = State()
    waiting_post_channel = State()
