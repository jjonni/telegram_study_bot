
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from psycopg import AsyncConnection

import app.infrastructure.database.db as db_func

logger = logging.getLogger(__name__)
user_lectures_router = Router(name="user_lectures")


def _lecture_kb(lecture_id: int) -> InlineKeyboardMarkup:
    b_download = InlineKeyboardButton(text="Скачать", callback_data=f"download_lecture:{lecture_id}")
    return InlineKeyboardMarkup(inline_keyboard=[[b_download]])


@user_lectures_router.message(F.text == "Лекции")
async def show_lectures_cmd(message: Message, conn: AsyncConnection):
    lectures = await db_func.get_lectures_with_file_ids(conn)
    if not lectures:
        await message.answer("Лекций нет.")
        return

    lines = []
    for lec in lectures:
        lines.append(f"{lec['name']}\n")
    text = "Доступные лекции:\n\n" + "\n".join(lines)
    await message.answer(text)

    kb_rows = []
    for lec in lectures:
        kb_rows.append([InlineKeyboardButton(text=f"{lec['name']}", callback_data=f"download_lecture:{lec['id']}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.answer("Нажмите на кнопку, чтобы скачать лекцию:", reply_markup=kb)


@user_lectures_router.callback_query(F.data.startswith("download_lecture:"))
async def download_lecture_cb(callback: CallbackQuery, conn: AsyncConnection):
    await callback.answer()
    try:
        payload = callback.data.split(":", 1)[1]
        lecture_id = int(payload)
    except Exception:
        await callback.answer("Неправильный идентификатор.", show_alert=True)
        return

    lecture = await db_func.get_lecture(conn, lecture_id=lecture_id)
    if not lecture:
        await callback.answer("Лекция не найдена.", show_alert=True)
        return

    lectures = await db_func.get_lectures_with_file_ids(conn)
    lec = next((l for l in (lectures or []) if l["id"] == lecture_id), None)
    if not lec or not lec.get("telegram_file_id"):
        await callback.answer("Файл лекции отсутствует.", show_alert=True)
        return

    try:
        await callback.message.answer_document(document=lec["telegram_file_id"], caption=f"Лекция {lec['name']}")
    except Exception as e:
        logger.exception("Failed to send lecture document: %s", e)
        await callback.answer("Не получилось отправить файл.", show_alert=True)

