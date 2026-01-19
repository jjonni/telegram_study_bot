
import logging
from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from psycopg import AsyncConnection

import app.infrastructure.database.db as db_func

logger = logging.getLogger(__name__)
user_tests_router = Router(name="user_tests")


class TestRunStates(StatesGroup):
    running = State()


async def _build_question_kb(conn: AsyncConnection, question_id: int) -> InlineKeyboardMarkup:
    answers = await db_func.get_answers_by_question(conn, question_id=question_id) or []
    kb_rows = []
    for a in answers:
        cb = InlineKeyboardButton(text=a["text"], callback_data=f"answer:{question_id}:{a['id']}")
        kb_rows.append([cb])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


@user_tests_router.message(F.text == "Тесты")
async def show_tests_cmd(message: Message, conn: AsyncConnection):
    async def _fetch_all():
        async with conn.cursor() as c:
            data = await c.execute("SELECT id, name, lecture_id FROM tests ORDER BY id;")
            rows = await data.fetchall()
            if not rows:
                return []
            cols = [d.name for d in c.description]
            return [dict(zip(cols, r)) for r in rows]

    tests = await _fetch_all()
    if not tests:
        await message.answer("Тестов нет.")
        return

    lines = []
    kb_rows = []
    for t in tests:
        lines.append(f"{t['name']}")
        kb_rows.append([InlineKeyboardButton(text=f"{t['name']}", callback_data=f"start_test:{t['id']}")])

    await message.answer("Доступные тесты:\n\n" + "\n".join(lines))
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.answer("Нажмите, чтобы пройти тест:", reply_markup=kb)


@user_tests_router.callback_query(F.data.startswith("start_test:"))
async def start_test_cb(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    try:
        test_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Неправильный идентификатор теста.", show_alert=True)
        return

    test = await db_func.get_test(conn, test_id=test_id)
    if not test:
        await callback.answer("Тест не найден.", show_alert=True)
        return

    questions = await db_func.get_questions_by_test(conn, test_id=test_id) or []
    if not questions:
        await callback.answer("В этом тесте нет вопросов.", show_alert=True)
        return

    await state.update_data(test_run={
        "test_id": test_id,
        "questions": [q["id"] for q in questions],
        "cur_idx": 0,
        "score": 0,
        "total": len(questions)
    })

    qid = questions[0]["id"]
    q = questions[0]
    text = f"Вопрос 1/{len(questions)}:\n{q['text']}"
    kb = await _build_question_kb(conn, question_id=qid)
    await state.set_state(TestRunStates.running)
    msg = await callback.message.answer(text, reply_markup=kb)
    await state.update_data(test_msg_id=msg.message_id)
    await state.update_data(last_question_id=qid)


@user_tests_router.callback_query(F.data.startswith("answer:"))
async def answer_cb(callback: CallbackQuery, state: FSMContext, conn: AsyncConnection):
    await callback.answer()
    try:
        _, payload = callback.data.split(":", 1)
        qid_str, aid_str = payload.split(":")
        question_id = int(qid_str); answer_id = int(aid_str)
    except Exception:
        await callback.answer("Неправильный payload.", show_alert=True)
        return

    data = await state.get_data()
    run = data.get("test_run")
    if not run:
        await callback.answer("Тест не найден в сессии. Запустите тест снова.", show_alert=True)
        await state.clear()
        return

    cur_q_idx = run.get("cur_idx", 0)
    questions_ids = run.get("questions", [])
    if cur_q_idx >= len(questions_ids) or questions_ids[cur_q_idx] != question_id:

        await callback.answer("Этот вариант уже не актуален.", show_alert=False)
        return

    answers = await db_func.get_answers_by_question(conn, question_id=question_id) or []
    a = next((x for x in answers if x["id"] == answer_id), None)
    if not a:
        await callback.answer("Вариант не найден.", show_alert=True)
        return

    is_right = bool(a.get("is_right"))
    if is_right:
        run["score"] = run.get("score", 0) + 1

    run["cur_idx"] = cur_q_idx + 1
    await state.update_data(test_run=run)

    if run["cur_idx"] < run["total"]:
        next_qid = run["questions"][run["cur_idx"]]
        q = await db_func.get_question(conn, question_id=next_qid)
        text = f"Вопрос {run['cur_idx']+1}/{run['total']}:\n{q['text']}"
        kb = await _build_question_kb(conn, question_id=next_qid)

        try:
            msg_id = data.get("test_msg_id")
            if msg_id:
                await callback.message.bot.edit_message_text(chat_id=callback.message.chat.id,
                                                            message_id=msg_id,
                                                            text=text,
                                                            reply_markup=kb)
            else:
                new_msg = await callback.message.answer(text, reply_markup=kb)
                await state.update_data(test_msg_id=new_msg.message_id)
        except Exception:
            new_msg = await callback.message.answer(text, reply_markup=kb)
            await state.update_data(test_msg_id=new_msg.message_id)
        return

    score = run.get("score", 0)
    total = run.get("total", 0)
    pct = (score / total * 100) if total else 0

    try:

        await db_func.add_or_update_test_stat(conn, user_id=callback.from_user.id, test_id=run["test_id"],
                                             last_score=score, last_submission_time=None, attempts_count=None)
    except Exception:
        logger.exception("Не удалось обновить статистику теста.")

    try:
        msg_id = data.get("test_msg_id")
        if msg_id:
            await callback.message.bot.delete_message(chat_id=callback.message.chat.id, message_id=msg_id)
    except Exception:
        pass

    await callback.message.answer(f"Тест завершён.\nРезультат: {score}/{total} ({pct:.1f}%)")

    await state.clear()
