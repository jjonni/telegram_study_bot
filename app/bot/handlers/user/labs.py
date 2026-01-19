# labs.py
import logging
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from psycopg import AsyncConnection

import app.infrastructure.database.db as db_func

logger = logging.getLogger(__name__)
user_labs_router = Router(name="user_labs")


@user_labs_router.message(F.text == "Лабораторные работы")  # пример вызова
async def show_labs_cmd(message: Message, conn: AsyncConnection):
    labs = await db_func.get_lab_works_with_file_ids(conn)
    if not labs:
        await message.answer("Лабораторных работ нет.")
        return

    lines = []
    for lab in labs:
        lines.append(f"{lab['name']}\n")
    await message.answer("Доступные лабораторные:\n\n" + "\n".join(lines))

    kb_rows = []
    for lab in labs:
        kb_rows.append([InlineKeyboardButton(text=f"{lab['name']}", callback_data=f"download_lab:{lab['id']}\n")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await message.answer("Нажмите кнопку, чтобы скачать лабораторную:", reply_markup=kb)


@user_labs_router.callback_query(F.data.startswith("download_lab:"))
async def download_lab_cb(callback: CallbackQuery, conn: AsyncConnection):
    await callback.answer()
    try:
        lab_id = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer("Неправильный идентификатор.", show_alert=True)
        return

    lab = await db_func.get_lab_work(conn, lab_id=lab_id)
    if not lab:
        await callback.answer("Лабораторная не найдена.", show_alert=True)
        return

    labs = await db_func.get_lab_works_with_file_ids(conn)
    l = next((x for x in (labs or []) if x["id"] == lab_id), None)
    if not l or not l.get("telegram_file_id"):
        await callback.answer("Файл лабораторной отсутствует.", show_alert=True)
        return

    try:
        await callback.message.answer_document(document=l["telegram_file_id"], caption=f"Лабораторная {l['name']}")
    except Exception as e:
        logger.exception("Failed to send lab document: %s", e)
        await callback.answer("Не получилось отправить файл.", show_alert=True)
