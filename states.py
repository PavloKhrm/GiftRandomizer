from aiogram.fsm.state import State, StatesGroup


class CreateGiveaway(StatesGroup):
    waiting_post = State()
    waiting_button_text = State()
    waiting_button_style = State()
    waiting_button_icon = State()
    waiting_requirements = State()
    waiting_end_datetime = State()
    waiting_winners_count = State()
    waiting_post_channel = State()
