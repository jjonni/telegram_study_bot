from aiogram.fsm.state import State, StatesGroup

class FSM_Wait(StatesGroup):
    waiting_for_name = State()
    waiting_for_surname = State()

class AddLectureStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_pdf = State()

class EditLectureStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_file = State()

class AddLabStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_file = State()

class EditLabStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_file = State()
    waiting_for_description = State()

class TestCreationStates(StatesGroup):
    waiting_for_test_name = State()
    editing_test = State()
    waiting_for_question_text = State()
    waiting_for_variant_text = State()
    waiting_for_variant_confirm = State()
    waiting_for_question_number_to_edit = State()
    waiting_for_variant_new_text = State()

class EditTestStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_new_question_text = State()
    waiting_for_question_new_text = State()