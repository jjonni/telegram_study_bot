import asyncio
import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from psycopg import AsyncConnection
from aiogram.fsm.context import FSMContext
from app.bot.states.states import TestCreationStates, EditTestStates
import app.infrastructure.database.db as db_func
import app.bot.keyboards.keyboards as keyb
from app.bot.handlers.sys_functions import push_bot_message, clear_bot_messages

admin_tests_router = Router(name="admin_tests")

logger = logging.getLogger(__name__)

def _make_test_summary(test: dict) -> str:
    return f"Тест «{test['name']}»"

async def _make_full_test_text(conn: AsyncConnection, test_id: int) -> str:
    text_lines = []

    test = await db_func.get_test(conn, test_id=test_id)
    if not test:
        return "Не найден тест."

    text_lines.append(f"Тест «{test['name']}»\n")
    questions = await db_func.get_questions_by_test(conn, test_id=test_id) or []
    if not questions:
        text_lines.append("Вопросов ещё нет.")
        return "\n".join(text_lines)

    for qi, q in enumerate(questions, start=1):
        text_lines.append(f"{qi}. {q['text']}")
        answers = await db_func.get_answers_by_question(conn, question_id=q['id']) or []
        for ai, a in enumerate(answers, start=1):
            mark = "✓" if a.get("is_right") else "✗"
            text_lines.append(f"   {ai}) {a['text']} [{mark}]")
        text_lines.append("")
    return "\n".join(text_lines)


@admin_tests_router.callback_query(F.data == "tests_click")
async def process_tests_edit(callback: CallbackQuery):
    await callback.answer()
    inline_keyboard = keyb.admin_tests()

    try:
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except Exception:
        await callback.message.answer("Выберите действие:", reply_markup=inline_keyboard)

async def _init_draft(state: FSMContext, test_name: str):
    await state.update_data(draft_test={"name": test_name, "questions": []},
                            msg_instruction_id=None,
                            last_sys_message_id=None)

async def _clear_sys_messages(message_or_bot, chat_id: int, state_data: dict):
    try:
        msg_instruction_id = state_data.get("msg_instruction_id")
        last_sys_message_id = state_data.get("last_sys_message_id")
        if msg_instruction_id:
            await message_or_bot.delete_message(chat_id=chat_id, message_id=msg_instruction_id)
        if last_sys_message_id:
            await message_or_bot.delete_message(chat_id=chat_id, message_id=last_sys_message_id)
    except Exception:
        logger.debug("Не удалось удалить одно из системных сообщений.", exc_info=True)

async def _save_sys_message(state: FSMContext, message: Message, key: str = "last_sys_message_id"):
    await state.update_data(**{key: message.message_id})

async def _build_question_view_and_kb(conn: AsyncConnection, test_id: int, qnum: int):
    questions = await db_func.get_questions_by_test(conn, test_id=test_id) or []
    if qnum < 1 or qnum > len(questions):
        return "Вопрос не найден.", InlineKeyboardMarkup(inline_keyboard=[]), None, []

    q = questions[qnum - 1]
    answers = await db_func.get_answers_by_question(conn, question_id=q["id"]) or []

    lines = [f"Вопрос #{qnum}: {q['text']}", "", "Варианты:"]
    for ai, a in enumerate(answers, start=1):
        mark = "✓" if a.get("is_right") else "✗"
        lines.append(f"{ai}) {a['text']} [{mark}]")

    text = "\n".join(lines)

    kb_rows = []
    for ai, a in enumerate(answers, start=1):
        kb_rows.append([
            InlineKeyboardButton(text=f"Удалить {ai}", callback_data=f"test_delete_variant:{qnum}:{ai}"),
            InlineKeyboardButton(text=f"Изменить {ai}", callback_data=f"test_edit_variant:{qnum}:{ai}")
        ])
        kb_rows.append([InlineKeyboardButton(text=f"Перекл. корректность {ai}", callback_data=f"test_toggle_variant:{qnum}:{ai}")])

    kb_rows.append([InlineKeyboardButton(text="Добавить вариант ответа", callback_data=f"test_add_variant_in_question:{qnum}")])
    kb_rows.append([InlineKeyboardButton(text="Назад", callback_data="test_back_to_edit_click")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    return text, kb, q, answers




@admin_tests_router.callback_query(F.data == "test_add_click")
async def test_add_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.set_state(TestCreationStates.waiting_for_test_name)
    msg = await callback.message.answer("Введите название теста или отправьте 'Отмена' для отмены:")
    await state.update_data(msg_instruction_id=msg.message_id)


@admin_tests_router.callback_query(F.data == "test_cancel_creation_click")
async def test_cancel_creation_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    await _clear_sys_messages(callback.message.bot, callback.message.chat.id, data)
    await state.clear()
    await callback.message.answer("Создание теста отменено.", reply_markup=keyb.admin_tests())
    await callback.answer()


@admin_tests_router.message(TestCreationStates.waiting_for_test_name)
async def handle_test_name(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.lower() == "отмена":

        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.clear()
        await message.answer("Создание теста отменено.", reply_markup=keyb.admin_tests())
        return

    await _init_draft(state, text)

    await push_bot_message(message.message_id, state)

    edit_kb = keyb.admin_test_edit()
    sys_msg = await message.answer(f"Тест: {text}\nДобавляйте вопросы.", reply_markup=edit_kb)
    await _save_sys_message(state, sys_msg, key="last_sys_message_id")
    await state.set_state(TestCreationStates.editing_test)


@admin_tests_router.callback_query(F.data == "test_add_question_click")
async def test_add_question_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    msg = await callback.message.answer("Введите текст вопроса или 'Отмена':")
    await state.update_data(msg_instruction_id=msg.message_id)
    await state.set_state(TestCreationStates.waiting_for_question_text)
    await callback.answer()


@admin_tests_router.callback_query(F.data == "test_cancel_question_click")
async def test_cancel_question_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await _clear_sys_messages(callback.message.bot, callback.message.chat.id, data)

    edit_kb = keyb.admin_test_edit()
    try:
        await callback.message.answer("Возвращаемся к редактированию теста.", reply_markup=edit_kb)
    except Exception:
        pass
    await state.set_state(TestCreationStates.editing_test)
    await state.update_data(msg_instruction_id=None, last_sys_message_id=None)
    await callback.answer()


@admin_tests_router.message(TestCreationStates.waiting_for_question_text)
async def handle_question_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст вопроса не может быть пустым. Попробуйте снова или отправьте 'Отмена'.")
        return
    if text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.set_state(TestCreationStates.editing_test)
        await message.answer("Ввод вопроса отменён.", reply_markup=keyb.admin_test_edit())
        return

    data = await state.get_data()
    draft = data.get("draft_test", {"name": "", "questions": []})

    new_question = {"text": text, "variants": []}
    draft["questions"].append(new_question)
    await state.update_data(draft_test=draft)

    await push_bot_message(message.message_id, state)

    sys_msg = await message.answer("Вопрос принят. Выберите действие:", reply_markup=keyb.admin_question_actions())
    await state.update_data(last_sys_message_id=sys_msg.message_id, msg_instruction_id=None)
    await state.set_state(TestCreationStates.editing_test)


@admin_tests_router.callback_query(F.data == "test_add_variant_click")
async def test_add_variant_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()

    draft = data.get("draft_test")
    if not draft or not draft.get("questions"):
        await callback.answer("Нет вопроса, к которому добавить вариант.", show_alert=True)
        return

    msg = await callback.message.answer("Введите текст варианта ответа или 'Отмена':")
    await state.update_data(msg_instruction_id=msg.message_id)
    await state.set_state(TestCreationStates.waiting_for_variant_text)
    await callback.answer()


@admin_tests_router.message(TestCreationStates.waiting_for_variant_text)
async def handle_variant_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Вариант не может быть пустым. Попробуйте снова или отправьте 'Отмена'.")
        return
    if text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.set_state(TestCreationStates.editing_test)
        await message.answer("Добавление варианта отменено.", reply_markup=keyb.admin_question_actions())
        return

    await state.update_data(last_variant_text=text)

    sys_msg = await message.answer("Вариант — правильный ответ?", reply_markup=keyb.admin_variant_correct())
    await state.update_data(msg_instruction_id=sys_msg.message_id)
    await state.set_state(TestCreationStates.waiting_for_variant_confirm)

    await push_bot_message(message.message_id, state)


@admin_tests_router.callback_query(F.data == "test_variant_correct_yes")
async def variant_correct_yes(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    await _variant_correct_set_db(callback, state, conn, is_right=True)

@admin_tests_router.callback_query(F.data == "test_variant_correct_no")
async def variant_correct_no(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    await _variant_correct_set_db(callback, state, conn, is_right=False)


async def _variant_correct_set_db(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection, *, is_right: bool):
    await callback.answer()
    data = await state.get_data()
    last_variant_text = data.get("last_variant_text")
    draft = data.get("draft_test")
    editing_test_id = data.get("editing_test_id")
    editing_question_idx = data.get("editing_question_idx")

    if editing_test_id is not None and editing_question_idx is not None:
        questions = await db_func.get_questions_by_test(conn, test_id=editing_test_id) or []
        if editing_question_idx < 0 or editing_question_idx >= len(questions):
            await callback.answer("Вопрос не найден.", show_alert=True)
            await state.set_state(TestCreationStates.editing_test)
            return
        q = questions[editing_question_idx]
        try:
            await db_func.add_answer(conn, question_id=q["id"], text=last_variant_text, is_right=bool(is_right))
        except Exception as e:
            logger.exception("Failed to add answer to DB: %s", e)
            await callback.answer("Ошибка при добавлении варианта.", show_alert=True)
            await state.set_state(TestCreationStates.editing_test)
            return

        try:
            msg_instruction_id = data.get("msg_instruction_id")
            if msg_instruction_id:
                await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_instruction_id)
        except Exception:
            pass

        test_id = editing_test_id
        qnum = editing_question_idx + 1
        text_out, kb, q, answers = await _build_question_view_and_kb(conn, test_id=test_id, qnum=qnum)

        last_sys_message_id = data.get("last_sys_message_id") or callback.message.message_id
        try:
            await callback.message.bot.edit_message_text(chat_id=callback.message.chat.id,
                                                        message_id=last_sys_message_id,
                                                        text=text_out,
                                                        reply_markup=kb)
        except Exception:
            new_msg = await callback.message.chat.send_message(text_out, reply_markup=kb)
            await state.update_data(last_sys_message_id=new_msg.message_id)

        await state.update_data(last_variant_text=None, msg_instruction_id=None)
        await state.set_state(TestCreationStates.editing_test)
        await callback.answer("Вариант добавлен.")
        return

    if draft is None:
        await callback.answer("Черновик не найден.", show_alert=True)
        await state.set_state(TestCreationStates.editing_test)
        return
    last_q = draft["questions"][-1]
    last_q["variants"].append({"text": last_variant_text, "is_right": bool(is_right)})
    await state.update_data(draft_test=draft, last_variant_text=None)

    try:
        msg_instruction_id = data.get("msg_instruction_id")
        if msg_instruction_id:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_instruction_id)
    except Exception:
        pass

    sys_msg = await callback.message.answer("Вариант добавлен.", reply_markup=keyb.admin_after_variant())
    await state.update_data(last_sys_message_id=sys_msg.message_id, msg_instruction_id=None)
    await state.set_state(TestCreationStates.editing_test)
    await callback.answer()




@admin_tests_router.callback_query(F.data == "test_next_question_click")
async def test_next_question_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    msg = await callback.message.answer("Введите текст следующего вопроса или 'Отмена':")
    await state.update_data(msg_instruction_id=msg.message_id)
    await state.set_state(TestCreationStates.waiting_for_question_text)
    await callback.answer()


@admin_tests_router.callback_query(F.data == "test_view_question_click")
async def test_view_question_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    draft = data.get("draft_test", {"questions": []})
    if not draft["questions"]:
        await callback.answer("Пока нет вопросов.", show_alert=True)
        return
    q = draft["questions"][-1]
    text = f"Вопрос: {q['text']}\n\nВарианты:\n"
    for i, v in enumerate(q["variants"], start=1):
        mark = "✓" if v.get("is_right") else "✗"
        text += f"{i}. {v['text']} [{mark}]\n"

    await callback.message.answer(text, reply_markup=keyb.admin_question_view(len(draft["questions"])))
    await callback.answer()


@admin_tests_router.callback_query(F.data.startswith("test_delete_question:"))
async def test_delete_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    payload = callback.data.split(":", 1)[1]
    try:
        idx = int(payload) - 1
    except Exception:
        await callback.answer("Неправильный идентификатор вопроса.", show_alert=True)
        return

    data = await state.get_data()
    draft = data.get("draft_test", {"questions": []})
    if idx < 0 or idx >= len(draft["questions"]):
        await callback.answer("Вопрос не найден.", show_alert=True)
        return

    removed = draft["questions"].pop(idx)
    await state.update_data(draft_test=draft)
    await callback.message.answer(f"Вопрос удалён: {removed['text']}", reply_markup=keyb.admin_test_edit())
    await callback.answer()


@admin_tests_router.callback_query(F.data == "test_finish_click")
async def test_finish_click(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    data = await state.get_data()
    draft = data.get("draft_test")
    if not draft or not draft.get("name"):
        await callback.answer("Нечего сохранять.", show_alert=True)
        return

    test_name = draft["name"]
    questions = draft.get("questions", [])

    try:
        test_id = await db_func.add_test(conn, name=test_name, lecture_id=None)
        if test_id is None:
            raise RuntimeError("db returned no test_id")
    except Exception as exc:
        logger.exception("Ошибка при добавлении теста в БД: %s", exc)
        await callback.answer("Ошибка сохранения теста. Попробуйте позже.", show_alert=True)
        return

    for q in questions:
        try:
            q_id = await db_func.add_question(conn, test_id=test_id, text=q["text"], max_points=None)
            if q_id is None:
                logger.warning("Question insertion returned None for q: %s", q)
                continue
            for v in q.get("variants", []):
                await db_func.add_answer(conn, question_id=q_id, text=v["text"], is_right=bool(v.get("is_right")))
        except Exception:
            logger.exception("Ошибка при сохранении вопроса/вариантов в БД")

    await _clear_sys_messages(callback.message.bot, callback.message.chat.id, data)
    await state.clear()

    await callback.message.answer(f"Тест '{test_name}' успешно сохранён в базе.", reply_markup=keyb.admin_tests())
    await callback.answer()

@admin_tests_router.callback_query(F.data == "test_back_to_edit_click")
async def test_back_to_edit_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    draft = data.get("draft_test")

    if not draft:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await state.clear()
        await callback.message.answer("Нет активного черновика теста. Возврат в меню.", reply_markup=keyb.admin_after_variant())
        await callback.answer()
        return

    try:
        await callback.message.delete()
    except Exception:
        pass

    try:
        msg_instruction_id = data.get("msg_instruction_id")
        last_sys_message_id = data.get("last_sys_message_id")
        if msg_instruction_id:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_instruction_id)
        if last_sys_message_id:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=last_sys_message_id)
    except Exception:
        pass

    try:
        edit_kb = keyb.admin_after_variant()
        sys_msg = await callback.message.answer(f"Редактирование теста: {draft.get('name', '')}", reply_markup=edit_kb)
        await state.update_data(last_sys_message_id=sys_msg.message_id, msg_instruction_id=None)
    except Exception:
        await callback.message.answer("Возвращаемся к редактированию теста.")
        await state.update_data(msg_instruction_id=None, last_sys_message_id=None)

    await state.set_state(TestCreationStates.editing_test)

@admin_tests_router.callback_query(F.data == "test_cancel_creation_click")
async def test_cancel_creation_click2(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await _clear_sys_messages(callback.message.bot, callback.message.chat.id, data)
    await state.clear()
    await callback.message.answer("Создание теста отменено.", reply_markup=keyb.admin_tests())
    await callback.answer()



@admin_tests_router.callback_query(F.data == "cancel_tests_click")
async def process_cancel_tests_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if state:
        await state.clear()

    try:
        inline_keyboard = keyb.admin_media()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except Exception:
        logger.exception("Failed to edit requests message back to admin menu.")

async def _fetch_all_tests(conn: AsyncConnection) -> list[dict] | None:
    async with conn.cursor() as cur:
        data = await cur.execute("SELECT id, name, lecture_id FROM tests ORDER BY id;")
        rows = await data.fetchall()
        if not rows:
            return None
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

@admin_tests_router.callback_query(F.data == "tests_select_click")
async def tests_select_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    tests = await _fetch_all_tests(conn)
    if not tests:
        try:
            await callback.message.edit_text("Тестов нет.")
        except Exception:
            await callback.message.answer("Тестов нет.")
        await state.clear()
        await callback.answer()
        return

    idx = 0
    test = tests[idx]
    text = _make_test_summary(test)


    kb = keyb.admin_test_view_edit(test)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        msg = await callback.message.answer(text, reply_markup=kb)
        await state.update_data(tests_message_id=msg.message_id)

    await state.update_data(test_index=idx)
    await callback.answer()


@admin_tests_router.callback_query(F.data == "prev_test_click")
async def prev_test_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    tests = await _fetch_all_tests(conn)
    if not tests:
        await callback.answer("Тестов нет.", show_alert=True)
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("test_index", 0) - 1
    if idx < 0:
        await callback.answer("Это первый тест.")
        return

    test = tests[idx]
    text = _make_test_summary(test)
    kb = keyb.admin_test_view_edit(test)

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)

    await state.update_data(test_index=idx)
    await callback.answer()


@admin_tests_router.callback_query(F.data == "next_test_click")
async def next_test_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    tests = await _fetch_all_tests(conn)
    if not tests:
        await callback.answer("Тестов нет.", show_alert=True)
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("test_index", 0) + 1
    if idx >= len(tests):
        await callback.answer("Это последний тест.")
        return

    test = tests[idx]
    text = _make_test_summary(test)
    kb = keyb.admin_test_view_edit(test)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)

    await state.update_data(test_index=idx)
    await callback.answer()



@admin_tests_router.callback_query(F.data == "test_delete_click")
async def test_delete_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    idx = data.get("test_index")
    if idx is None:
        await callback.answer("Нет выбранного теста.", show_alert=True)
        return


    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Удалить 🔥", callback_data="test_delete_confirm_yes"),
         InlineKeyboardButton(text="Отмена", callback_data="test_delete_confirm_no")]
    ])
    await callback.message.answer("Вы уверены, что хотите удалить тест?", reply_markup=kb)
    await callback.answer()


@admin_tests_router.callback_query(F.data == "test_delete_confirm_no")
async def test_delete_confirm_no(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.answer("Удаление отменено.")


@admin_tests_router.callback_query(F.data == "test_delete_confirm_yes")
async def test_delete_confirm_yes(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    idx = data.get("test_index")
    if idx is None:
        await callback.answer("Нет выбранного теста.", show_alert=True)
        return

    tests = await _fetch_all_tests(conn)
    if not tests:
        await callback.answer("Тестов нет.", show_alert=True)
        await state.clear()
        return


    if idx < 0:
        idx = 0
    elif idx >= len(tests):
        idx = len(tests) - 1

    test = tests[idx]


    try:
        await db_func.delete_test(conn, test_id=test["id"])
        logger.info("Deleted test id=%s name=%s", test["id"], test["name"])
    except Exception as e:
        logger.exception("Failed to delete test from db: %s", e)
        await callback.answer("Ошибка удаления из БД.", show_alert=True)
        return


    new_tests = await _fetch_all_tests(conn)
    if not new_tests:

        try:
            await callback.message.edit_text(f"Тест '{test['name']}' удалён.\nТестов больше нет.", reply_markup=keyb.admin_tests())
        except Exception:
            await callback.message.answer(f"Тест '{test['name']}' удалён.\nТестов больше нет.", reply_markup=keyb.admin_tests())
        await state.clear()
        await callback.answer("Тест удалён.")
        return


    if idx >= len(new_tests):
        idx = len(new_tests) - 1

    next_test = new_tests[idx]
    text = _make_test_summary(next_test)
    kb = keyb.admin_test_view_edit(next_test)


    try:
        await callback.message.edit_text(text, reply_markup=kb)
        await state.update_data(test_index=idx)
        await callback.answer("Тест удалён. Показан следующий.")
        return
    except TelegramBadRequest:
        try:
            new_msg = await callback.message.chat.send_message(text=text, reply_markup=kb)
            try:
                await callback.message.delete()
            except Exception:
                logger.debug("Old test message not deleted.")
            await state.update_data(test_index=idx, tests_message_id=new_msg.message_id)
            await callback.answer("Тест удалён. Показан следующий.")
            return
        except Exception as e:
            logger.exception("Failed to show next test after deletion: %s", e)


    await callback.message.answer(f"Тест '{test['name']}' удалён, но не удалось показать следующий.", reply_markup=keyb.admin_tests())
    await state.clear()
    await callback.answer()



@admin_tests_router.callback_query(F.data.startswith("test_update_name_click"))
async def test_update_name_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    payload_parts = callback.data.split(":", 1)
    test_id = None
    if len(payload_parts) == 2:
        try:
            test_id = int(payload_parts[1])
        except Exception:
            test_id = None


    data = await state.get_data()
    if test_id is None:
        test_id = data.get("editing_test_id")
    if test_id is None:

        idx = data.get("test_index")
        if idx is not None:
            tests = await _fetch_all_tests(callback.bot.session.get_connection()) if False else None


        await callback.answer("Не определён тест для переименования.", show_alert=True)
        return


    await state.update_data(editing_test_id=test_id)
    await state.set_state(EditTestStates.waiting_for_name)
    instr = await callback.message.answer("Введите новое название теста или 'Отмена':")
    await state.update_data(msg_instruction_id=instr.message_id)


    try:
        await callback.message.delete()
    except Exception:
        logger.debug("Could not delete original test message before rename.")
    await callback.answer()

@admin_tests_router.message(EditTestStates.waiting_for_name)
async def handle_test_new_name_edit(message: Message, state: FSMContext, conn: AsyncConnection):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз или отправьте 'Отмена'.")
        return

    if text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.clear()
        await message.answer("Переименование отменено.", reply_markup=keyb.admin_tests())
        return

    data = await state.get_data()
    test_id = data.get("editing_test_id")
    if not test_id:
        await message.answer("Не найден тест для переименования.")
        await state.clear()
        return


    try:
        await db_func.update_test(conn, test_id=test_id, name=text)
    except Exception as exc:
        logger.exception("Ошибка переименования теста: %s", exc)
        await message.answer("Не удалось сохранить новое название. Попробуйте позже.")
        await state.clear()
        return


    await _clear_sys_messages(message.bot, message.chat.id, data)


    try:
        tests_message_id = data.get("tests_message_id")
        text_summary = f"Тест #{test_id}\nНазвание: {text}"
        await message.bot.edit_message_text(chat_id=message.chat.id, message_id=tests_message_id,
                                            text=text_summary,
                                            reply_markup=keyb.admin_test_view_edit({"id": test_id, "name": text}))

        await message.answer(f"{text_summary}", reply_markup=keyb.admin_test_view_edit({"id": test_id, "name": text}))
    except Exception:
        await message.answer(f"{text_summary}", reply_markup=keyb.admin_test_view_edit({"id": test_id, "name": text}))


    try:
        await message.delete()
    except Exception:
        pass

    await state.clear()


@admin_tests_router.message(TestCreationStates.waiting_for_test_name)
async def handle_test_name_message(message: Message, state: FSMContext, conn: AsyncConnection):
    text = (message.text or "").strip()
    if not text or text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.clear()
        await message.answer("Операция отменена.", reply_markup=keyb.admin_tests())
        return

    data = await state.get_data()
    editing_idx = data.get("editing_test_index")

    if editing_idx is not None:
        tests = await _fetch_all_tests(conn)
        if not tests or editing_idx < 0 or editing_idx >= len(tests):
            await message.answer("Не удалось найти тест для переименования.")
            await state.clear()
            return

        test = tests[editing_idx]
        try:
            await db_func.update_test(conn, test_id=test["id"], name=text)
        except Exception as e:
            logger.exception("Error renaming test: %s", e)
            await message.answer("Ошибка при переименовании.")
            await state.clear()
            return


        await asyncio.sleep(0.2)
        await _clear_sys_messages(message.bot, message.chat.id, data)


        updated_test = {"id": test["id"], "name": text}
        kb = keyb.admin_test_view_edit(updated_test)
        try:
            await message.answer(_make_test_summary(updated_test), reply_markup=kb)
        except Exception:
            pass

        await message.answer(f"Название теста успешно изменено на: {text}", reply_markup=keyb.admin_tests())
        await state.clear()
        return

    await message.answer("Создание (или переименование) обработано.")
    await state.clear()



@admin_tests_router.callback_query(F.data.startswith("test_edit_click"))
async def test_edit_click(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()

    payload = callback.data.split(":", 1)
    test_id = None
    if len(payload) == 2:
        try:
            test_id = int(payload[1])
        except Exception:
            test_id = None


    if test_id is None:
        data = await state.get_data()
        idx = data.get("test_index")
        tests = await _fetch_all_tests(conn)
        if tests and idx is not None and 0 <= idx < len(tests):
            test_id = tests[idx]["id"]

    if test_id is None:
        await callback.answer("Не удалось определить тест.", show_alert=True)
        return


    full_text = await _make_full_test_text(conn, test_id=test_id)


    sys_msg = await callback.message.answer(full_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data="test_cancel_view_click")]
    ]))

    await state.update_data(editing_test_id=test_id, last_sys_message_id=sys_msg.message_id, msg_instruction_id=None)
    await state.set_state(TestCreationStates.waiting_for_question_number_to_edit)
    await callback.answer()


@admin_tests_router.callback_query(F.data == "test_cancel_view_click")
async def test_cancel_view_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await _clear_sys_messages(callback.message.bot, callback.message.chat.id, data)
    await state.set_state(TestCreationStates.editing_test)


@admin_tests_router.message(TestCreationStates.waiting_for_question_number_to_edit)
async def handle_question_number_input(message: Message, state: FSMContext, conn: AsyncConnection):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите номер вопроса или 'Отмена'.")
        return
    if text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.set_state(TestCreationStates.editing_test)
        await message.answer("Редактирование отменено.", reply_markup=keyb.admin_tests())
        return

    try:
        qnum = int(text)
    except ValueError:
        await message.answer("Введите корректный номер вопроса.")
        return

    data = await state.get_data()
    test_id = data.get("editing_test_id")
    if not test_id:
        await message.answer("Тест не найден. Вернитесь в меню.")
        await state.clear()
        return


    text_out, kb, q, answers = await _build_question_view_and_kb(conn, test_id=test_id, qnum=qnum)

    try:
        await message.delete()
    except Exception:
        pass


    sys_msg = await message.answer(text_out, reply_markup=kb)
    await state.update_data(editing_question_idx=qnum - 1, last_sys_message_id=sys_msg.message_id, msg_instruction_id=None)
    await state.set_state(TestCreationStates.editing_test)



@admin_tests_router.callback_query(F.data.startswith("test_delete_variant:"))
async def test_delete_variant(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    try:
        _, payload = callback.data.split(":", 1)
        qnum_str, anum_str = payload.split(":")
        qnum = int(qnum_str); anum = int(anum_str)
    except Exception:
        await callback.answer("Неправильный payload.", show_alert=True)
        return

    data = await state.get_data()
    test_id = data.get("editing_test_id")
    last_sys_message_id = data.get("last_sys_message_id')") if False else data.get("last_sys_message_id")
    if not test_id:
        await callback.answer("Тест не найден.", show_alert=True); return

    questions = await db_func.get_questions_by_test(conn, test_id=test_id) or []
    if qnum < 1 or qnum > len(questions): await callback.answer("Вопрос не найден.", show_alert=True); return
    q = questions[qnum - 1]
    answers = await db_func.get_answers_by_question(conn, question_id=q["id"]) or []
    if anum < 1 or anum > len(answers): await callback.answer("Вариант не найден.", show_alert=True); return

    a = answers[anum - 1]
    try:
        await db_func.delete_answer(conn, answer_id=a["id"])
    except Exception as e:
        logger.exception("Failed delete answer: %s", e)
        await callback.answer("Ошибка при удалении варианта.", show_alert=True)
        return


    text_out, kb, q, answers = await _build_question_view_and_kb(conn, test_id=test_id, qnum=qnum)
    edit_msg_id = data.get("last_sys_message_id") or callback.message.message_id
    try:
        await callback.message.bot.edit_message_text(chat_id=callback.message.chat.id,
                                                    message_id=edit_msg_id,
                                                    text=text_out,
                                                    reply_markup=kb)
    except Exception:

        new_msg = await callback.message.chat.send_message(text_out, reply_markup=kb)
        await state.update_data(last_sys_message_id=new_msg.message_id)
    await callback.answer("Вариант удалён.")


@admin_tests_router.callback_query(F.data.startswith("test_toggle_variant:"))
async def test_toggle_variant(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    try:
        _, payload = callback.data.split(":", 1)
        qnum_str, anum_str = payload.split(":")
        qnum = int(qnum_str); anum = int(anum_str)
    except Exception:
        await callback.answer("Неправильный payload.", show_alert=True); return

    data = await state.get_data(); test_id = data.get("editing_test_id")
    if not test_id:
        await callback.answer("Тест не найден.", show_alert=True); return

    questions = await db_func.get_questions_by_test(conn, test_id=test_id) or []
    if qnum < 1 or qnum > len(questions): await callback.answer("Вопрос не найден.", show_alert=True); return
    q = questions[qnum - 1]
    answers = await db_func.get_answers_by_question(conn, question_id=q["id"]) or []
    if anum < 1 or anum > len(answers): await callback.answer("Вариант не найден.", show_alert=True); return

    a = answers[anum - 1]
    new_flag = not bool(a.get("is_right"))
    try:
        await db_func.update_answer(conn, answer_id=a["id"], is_right=new_flag)
    except Exception as e:
        logger.exception("Failed toggle answer correctness: %s", e)
        await callback.answer("Ошибка при переключении корректности.", show_alert=True); return


    text_out, kb, q, answers = await _build_question_view_and_kb(conn, test_id=test_id, qnum=qnum)
    edit_msg_id = data.get("last_sys_message_id") or callback.message.message_id
    try:
        await callback.message.bot.edit_message_text(chat_id=callback.message.chat.id,
                                                    message_id=edit_msg_id,
                                                    text=text_out,
                                                    reply_markup=kb)
    except Exception:
        new_msg = await callback.message.chat.send_message(text_out, reply_markup=kb)
        await state.update_data(last_sys_message_id=new_msg.message_id)

    await callback.answer(f"Вариант #{anum} теперь {'правильный' if new_flag else 'неправильный'}.")



@admin_tests_router.callback_query(F.data.startswith("test_edit_variant:"))
async def test_edit_variant_click(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    try:
        _, payload = callback.data.split(":", 1)
        qnum_str, anum_str = payload.split(":")
        qnum = int(qnum_str); anum = int(anum_str)
    except Exception:
        await callback.answer("Неправильный payload.", show_alert=True)
        return

    data = await state.get_data()
    test_id = data.get("editing_test_id")
    if not test_id:
        await callback.answer("Тест не найден.", show_alert=True)
        return


    await state.update_data(editing_question_idx=qnum - 1, editing_variant_idx=anum - 1)
    instr = await callback.message.answer("Введите новый текст варианта или 'Отмена':")
    await state.update_data(msg_instruction_id=instr.message_id)

    await state.set_state(TestCreationStates.waiting_for_variant_new_text)
    await callback.answer()


@admin_tests_router.message(TestCreationStates.waiting_for_variant_new_text)
async def handle_variant_new_text(message: Message, state: FSMContext, conn: AsyncConnection):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст варианта не может быть пустым. Попробуйте снова или отправьте 'Отмена'.")
        return
    if text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)

        data = await state.get_data()
        test_id = data.get("editing_test_id")
        qidx = data.get("editing_question_idx")
        if test_id is not None and qidx is not None:
            text_out, kb, q, answers = await _build_question_view_and_kb(conn, test_id=test_id, qnum=qidx+1)
            sys_msg = await message.answer(text_out, reply_markup=kb)
            await state.update_data(last_sys_message_id=sys_msg.message_id, msg_instruction_id=None)
            await state.set_state(TestCreationStates.editing_test)
            return
        await state.set_state(TestCreationStates.editing_test)
        await message.answer("Редактирование варианта отменено.", reply_markup=keyb.admin_tests())
        return

    data = await state.get_data()
    test_id = data.get("editing_test_id")
    qidx = data.get("editing_question_idx")
    vidx = data.get("editing_variant_idx")
    if test_id is None or qidx is None or vidx is None:
        await message.answer("Не найдена информация о редактируемом варианте. Операция прервана.")
        await state.clear()
        return


    questions = await db_func.get_questions_by_test(conn, test_id=test_id) or []
    if qidx < 0 or qidx >= len(questions):
        await message.answer("Вопрос не найден.")
        await state.clear()
        return
    q = questions[qidx]
    answers = await db_func.get_answers_by_question(conn, question_id=q["id"]) or []
    if vidx < 0 or vidx >= len(answers):
        await message.answer("Вариант не найден.")
        await state.clear()
        return
    answer_row = answers[vidx]


    try:
        await db_func.update_answer(conn, answer_id=answer_row["id"], text=text)
    except Exception as exc:
        logger.exception("Ошибка при обновлении варианта: %s", exc)
        await message.answer("Не удалось обновить вариант. Попробуйте позже.")
        await state.clear()
        return


    data = await state.get_data()
    await _clear_sys_messages(message.bot, message.chat.id, data)


    text_out, kb, q, answers = await _build_question_view_and_kb(conn, test_id=test_id, qnum=qidx+1)
    edit_msg_id = data.get("last_sys_message_id")
    try:
        if edit_msg_id:
            await message.bot.edit_message_text(chat_id=message.chat.id, message_id=edit_msg_id, text=text_out, reply_markup=kb)
        else:
            new_msg = await message.answer(text_out, reply_markup=kb)
            await state.update_data(last_sys_message_id=new_msg.message_id)
    except Exception:

        new_msg = await message.answer(text_out, reply_markup=kb)
        await state.update_data(last_sys_message_id=new_msg.message_id)


    await state.update_data(editing_variant_idx=None, msg_instruction_id=None)
    await state.set_state(TestCreationStates.editing_test)


    try:
        await message.delete()
    except Exception:
        pass

@admin_tests_router.callback_query(F.data.startswith("test_add_variant_in_question:"))
async def test_add_variant_in_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        payload = callback.data.split(":", 1)[1]
        qnum = int(payload)
    except Exception:
        await callback.answer("Неправильный payload.", show_alert=True)
        return


    await state.update_data(editing_question_idx=qnum - 1)
    msg = await callback.message.answer("Введите текст варианта ответа или отправьте 'Отмена':")
    await state.update_data(msg_instruction_id=msg.message_id)
    await state.set_state(TestCreationStates.waiting_for_variant_text)
    await callback.answer()

@admin_tests_router.message(TestCreationStates.waiting_for_variant_text)
async def handle_variant_text(message: Message, state: FSMContext, conn: AsyncConnection):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Вариант не может быть пустым. Попробуйте снова или отправьте 'Отмена'.")
        return
    if text.lower() == "отмена":
        data = await state.get_data()
        await _clear_sys_messages(message.bot, message.chat.id, data)
        await state.set_state(TestCreationStates.editing_test)
        await message.answer("Добавление варианта отменено.", reply_markup=keyb.admin_question_actions())
        return

    data = await state.get_data()

    editing_test_id = data.get("editing_test_id")
    editing_question_idx = data.get("editing_question_idx")


    await state.update_data(last_variant_text=text)


    sys_msg = await message.answer("Вариант — правильный ответ?", reply_markup=keyb.admin_variant_correct())
    await state.update_data(msg_instruction_id=sys_msg.message_id)
    await state.set_state(TestCreationStates.waiting_for_variant_confirm)

    try:
        await message.delete()
    except Exception:
        pass


@admin_tests_router.callback_query(F.data == "cancel_tests_view_click")
async def cancel_tests_view_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try:
        await callback.message.edit_text("Выберите действие:", reply_markup=keyb.admin_tests())
    except Exception:
        await callback.message.answer("Выберите действие:", reply_markup=keyb.admin_tests())