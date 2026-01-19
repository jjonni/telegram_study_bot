from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

def admin_buttons() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Редактирование материала")],
            [KeyboardButton(text="Контроль активности студентов")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def user_buttons() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Лекции")],
            [KeyboardButton(text="Лабораторные работы")],
            [KeyboardButton(text="Тесты")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

def admin_functions() -> InlineKeyboardMarkup:
    button_2 = InlineKeyboardButton(text="Бан студента", callback_data="ban_user_click")
    button_3 = InlineKeyboardButton(text="Заявки", callback_data="requests_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_2, button_3]])

def admin_ban_action() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="🚫 Забанить", callback_data="ban_click")
    button_2 = InlineKeyboardButton(text="♻️ Разбанить", callback_data="unban_click")
    button_3 = InlineKeyboardButton(text="⏮ Пред", callback_data="prev_ban_click")
    button_4 = InlineKeyboardButton(text="След ⏭", callback_data="next_ban_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_user_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1, button_2], [button_3, button_4], [button_cancel]])

def admin_request_action() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="✅ Одобрить", callback_data="approve_click")
    button_2 = InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_click")
    button_3 = InlineKeyboardButton(text="⏮ Пред", callback_data="prev_request_click")
    button_4 = InlineKeyboardButton(text="След ⏭", callback_data="next_request_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_user_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1, button_2], [button_3, button_4], [button_cancel]])

def admin_media() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Лекции", callback_data="lectures_click")
    button_2 = InlineKeyboardButton(text="Тесты", callback_data="tests_click")
    button_3 = InlineKeyboardButton(text="Лабораторные работы", callback_data="labs_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1, button_2], [button_3]])

def admin_lectures() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Выбор лекций", callback_data="lectures_select_click")
    button_2 = InlineKeyboardButton(text="Добавить новую лекцию", callback_data="lecture_add_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_lectures_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_cancel]])

def admin_lecture_select() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Удалить", callback_data="lecture_delete_click")
    button_2 = InlineKeyboardButton(text="Изменить название", callback_data="lecture_update_name_click")
    button_3 = InlineKeyboardButton(text="Обновить файл", callback_data="lecture_update_click")
    button_4 = InlineKeyboardButton(text="⏮ Пред", callback_data="prev_lecture_click")
    button_5 = InlineKeyboardButton(text="След ⏭", callback_data="next_lecture_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_lectures_select_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_3], [button_4, button_5], [button_cancel]])

def admin_labs() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Выбор лабораторной", callback_data="labs_select_click")
    button_2 = InlineKeyboardButton(text="Добавить новую лабораторную", callback_data="lab_add_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_labs_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_cancel]])

def admin_lab_select() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Удалить", callback_data="lab_delete_click")
    button_2 = InlineKeyboardButton(text="Изменить название", callback_data="lab_update_name_click")
    button_3 = InlineKeyboardButton(text="Обновить файл", callback_data="lab_update_click")
    button_4 = InlineKeyboardButton(text="Изменить описание", callback_data="lab_update_description_click")
    button_5 = InlineKeyboardButton(text="⏮ Пред", callback_data="prev_lab_click")
    button_6 = InlineKeyboardButton(text="След ⏭", callback_data="next_lab_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_labs_select_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_3], [button_4], [button_5, button_6], [button_cancel]])

def admin_tests() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Выбор тестов", callback_data="tests_select_click")
    button_2 = InlineKeyboardButton(text="Добавить новый тест", callback_data="test_add_click")
    button_3 = InlineKeyboardButton(text="Назад", callback_data="cancel_tests_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_3]])

def admin_test_edit() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Добавить вопрос", callback_data="test_add_question_click")
    button_2 = InlineKeyboardButton(text="Завершить создание", callback_data="test_finish_click")
    button_3 = InlineKeyboardButton(text="Отмена", callback_data="test_cancel_creation_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_3]])

def admin_test_view_edit(test: dict):
    button_1 = InlineKeyboardButton(text="Редактирование теста", callback_data=f"test_edit_click:{test['id']}")
    button_2 = InlineKeyboardButton(text="Изменить название", callback_data=f"test_update_name_click:{test['id']}")
    button_3 = InlineKeyboardButton(text="Удалить тест", callback_data=f"test_delete_click")
    button_4 = InlineKeyboardButton(text="⏮ Пред", callback_data="prev_test_click")
    button_5 = InlineKeyboardButton(text="След ⏭", callback_data="next_test_click")
    button_cancel = InlineKeyboardButton(text="Назад", callback_data="cancel_tests_view_click")

    return InlineKeyboardMarkup(inline_keyboard=[[button_1],[button_2],[button_3],[button_4,button_5],[button_cancel]])

def admin_question_actions() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Добавить вариант ответа", callback_data="test_add_variant_click")
    button_2 = InlineKeyboardButton(text="Отмена вопроса", callback_data="test_cancel_question_click")
    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2]])


def admin_variant_correct() -> InlineKeyboardMarkup:
    button_yes = InlineKeyboardButton(text="✅", callback_data="test_variant_correct_yes")
    button_no = InlineKeyboardButton(text="❌", callback_data="test_variant_correct_no")
    return InlineKeyboardMarkup(inline_keyboard=[[button_yes,button_no]])

def admin_after_variant() -> InlineKeyboardMarkup:
    button_1 = InlineKeyboardButton(text="Добавить вариант ответа", callback_data="test_add_variant_click")
    button_2 = InlineKeyboardButton(text="Добавить следующий вопрос", callback_data="test_next_question_click")
    button_3 = InlineKeyboardButton(text="Внешний вид вопроса", callback_data="test_view_question_click")
    button_4 = InlineKeyboardButton(text="Завершить создание теста", callback_data="test_finish_click")
    return InlineKeyboardMarkup(inline_keyboard=[[button_1], [button_2], [button_3], [button_4]])

def admin_question_view(question_id: int) -> InlineKeyboardMarkup:
    b_delete = InlineKeyboardButton(text="Удалить вопрос", callback_data=f"test_delete_question:{question_id}")
    b_back = InlineKeyboardButton(text="Назад к редактированию", callback_data="test_back_to_edit_click")
    return InlineKeyboardMarkup(inline_keyboard=[[b_delete], [b_back]])

