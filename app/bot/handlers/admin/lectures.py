import asyncio
import logging
import os

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InputMediaDocument
from psycopg import AsyncConnection
from aiogram.fsm.context import FSMContext
from app.bot.states.states import AddLectureStates, EditLectureStates
from app.bot.enums.enums import FileType
import app.infrastructure.database.db as db_func
import app.bot.keyboards.keyboards as keyb
from app.bot.handlers.sys_functions import push_bot_message, clear_bot_messages

admin_lectures_router = Router(name="admin_lectures")

logger = logging.getLogger(__name__)

ALLOWED_TYPE = ["application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/octet-stream"]

def make_lecture_text(lecture: dict) -> str:
    return (
        f"Лекция «{lecture['name']}»"
    )

@admin_lectures_router.callback_query(F.data == "lectures_click")
async def process_lectures_edit(callback: CallbackQuery):
    await callback.answer()
    inline_keyboard = keyb.admin_lectures()

    try:
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except TelegramBadRequest:
        logger.exception("Failed to edit message in process_lectures_edit")

@admin_lectures_router.callback_query(F.data == "lectures_select_click")
async def process_lectures_select(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    await state.update_data(media_id=callback.message.message_id)
    lectures = await db_func.get_lectures_with_file_ids(conn)

    if not lectures:
        await callback.message.edit_text("Лекций нет.")
        await state.clear()
        return

    idx = 0
    lecture = lectures[idx]

    media = InputMediaDocument(
        media=lecture["telegram_file_id"],
        caption=make_lecture_text(lecture)
    )

    inline_keyboard = keyb.admin_lecture_select()
    await callback.message.edit_media(media=media, reply_markup=inline_keyboard)

    await state.update_data(lecture_index=idx)

@admin_lectures_router.callback_query(F.data == "prev_lecture_click")
async def process_prev_lecture_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    lectures = await db_func.get_lectures_with_file_ids(conn)
    if not lectures:
        await callback.message.edit_text("Лекций нет.")
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("lecture_index", 0) - 1
    if idx < 0:
        await callback.answer("Это первая лекция.")
        return

    lecture = lectures[idx]

    media = InputMediaDocument(
        media=lecture["telegram_file_id"],
        caption=make_lecture_text(lecture)
    )

    inline_keyboard = keyb.admin_lecture_select()
    await callback.message.edit_media(media=media, reply_markup=inline_keyboard)
    await state.update_data(lecture_index=idx)


@admin_lectures_router.callback_query(F.data == "next_lecture_click")
async def process_next_lecture_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    lectures = await db_func.get_lectures_with_file_ids(conn)
    if not lectures:
        await callback.message.edit_text("Лекций нет.")
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("lecture_index", 0) + 1
    if idx >= len(lectures):
        await callback.answer("Это последняя лекция.")
        return

    lecture = lectures[idx]

    media = InputMediaDocument(
        media=lecture["telegram_file_id"],
        caption=make_lecture_text(lecture)
    )

    inline_keyboard = keyb.admin_lecture_select()
    await callback.message.edit_media(media=media, reply_markup=inline_keyboard)
    await state.update_data(lecture_index=idx)

@admin_lectures_router.callback_query(F.data == "lecture_add_click")
async def process_lecture_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddLectureStates.waiting_for_name)
    msg = await callback.message.answer("Введите название лекции:")

    await push_bot_message(msg.message_id, state)

@admin_lectures_router.message(AddLectureStates.waiting_for_name)
async def process_lecture_name(message: Message, state: FSMContext):
    await push_bot_message(message.message_id, state)

    await state.update_data(lecture_name=message.text)
    await state.set_state(AddLectureStates.waiting_for_pdf)
    msg = await message.answer("Отправьте файл лекции:")

    await push_bot_message(msg.message_id, state)

@admin_lectures_router.message(AddLectureStates.waiting_for_pdf, F.document.mime_type.in_(ALLOWED_TYPE))
async def process_lecture_pdf(message: Message, bot: Bot, conn: AsyncConnection, state: FSMContext):
    await push_bot_message(message.message_id, state)

    data = await state.get_data()
    lecture_name = data.get("lecture_name")

    media_folder = os.path.join("media", "lectures")
    os.makedirs(media_folder, exist_ok=True)

    file_path = os.path.join(media_folder, message.document.file_name)
    await bot.download(
        file=message.document.file_id,
        destination=file_path
    )

    file_id = await db_func.add_file(
        connection=conn,
        file_type=FileType.LECTURE,
        telegram_file_id=message.document.file_id,
        path=file_path
    )

    if file_id is None:
        msg = await message.answer("Ошибка при добавлении файла в базу.")
        await push_bot_message(msg.message_id, state)
        return

    lecture_id = await db_func.add_lecture(
        connection=conn,
        name=lecture_name,
        file_id=file_id
    )

    if lecture_id is None:
        msg = await message.answer("Ошибка при добавлении лекции в базу.")
        await push_bot_message(msg.message_id, state)
        return

    msg = await message.answer(f"Лекция '{lecture_name}' успешно добавлена.")
    await push_bot_message(msg.message_id, state)

    await asyncio.sleep(1.5)
    await clear_bot_messages(message, state)

    await state.clear()

@admin_lectures_router.message(AddLectureStates.waiting_for_pdf)
async def process_invalid_file(message: Message, state: FSMContext):
    await push_bot_message(message.message_id, state)

    msg = await message.answer("Пожалуйста, отправьте PDF-файл.")
    await push_bot_message(msg.message_id, state)

# ----------------- Удалить лекцию -----------------
@admin_lectures_router.callback_query(F.data == "lecture_delete_click")
async def lecture_delete_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    idx = data.get("lecture_index")
    if idx is None:
        await callback.answer("Нет выбранной лекции для удаления.", show_alert=True)
        return

    lectures = await db_func.get_lectures_with_file_ids(conn)
    if not lectures:
        await callback.answer("Лекций нет.", show_alert=False)
        await state.clear()
        inline_keyboard = keyb.admin_functions()
        try:
            await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        except TelegramBadRequest:
            await callback.message.answer("Выберите действие:", reply_markup=inline_keyboard)
        return

    if idx < 0:
        idx = 0
    elif idx >= len(lectures):
        idx = len(lectures) - 1

    lecture = lectures[idx]

    try:
        await db_func.delete_lecture(conn, lecture_id=lecture["id"])
        logger.info("Deleted lecture id=%s name=%s", lecture["id"], lecture["name"])
    except Exception:
        logger.exception("Failed to delete lecture from db")
        await callback.answer("Ошибка удаления из БД.", show_alert=True)
        return

    new_lectures = await db_func.get_lectures_with_file_ids(conn)

    if not new_lectures:
        await state.clear()
        inline_keyboard = keyb.admin_functions()

        try:
            await callback.message.edit_text(f"Лекция '{lecture['name']}' удалена.\nЛекций больше нет.", reply_markup=inline_keyboard)
        except TelegramBadRequest:
            await callback.message.answer(f"Лекция '{lecture['name']}' удалена.\nЛекций больше нет.", reply_markup=inline_keyboard)
        await callback.answer("Лекция удалена.")
        return

    if idx >= len(new_lectures):
        idx = max(len(new_lectures) - 1, 0)

    next_lecture = new_lectures[idx]
    caption = make_lecture_text(next_lecture)
    inline_keyboard = keyb.admin_lecture_select()

    try:
        media = InputMediaDocument(media=next_lecture["telegram_file_id"], caption=caption)

        await callback.message.edit_media(media=media, reply_markup=inline_keyboard)
        await state.update_data(lecture_index=idx)
        await callback.answer("Лекция удалена. Показана следующая.")
        return
    except TelegramBadRequest as e:
        logger.debug("edit_media failed, will send new document: %s", e)

    try:
        new_msg = await callback.message.chat.send_document(
            document=next_lecture["telegram_file_id"],
            caption=caption,
            reply_markup=inline_keyboard
        )

        try:
            await callback.message.delete()
        except TelegramBadRequest:
            logger.exception("Old lecture message wasn't deleted or already removed.")

        await state.update_data(lecture_index=idx, lectures_message_id=new_msg.message_id)
        await callback.answer("Лекция удалена. Показана следующая.")
    except Exception as e:
        logger.exception("Failed to show next lecture after deletion: %s", e)

        inline_keyboard = keyb.admin_functions()
        await callback.message.answer(f"Лекция '{lecture['name']}' удалена, но не удалось показать следующую.", reply_markup=inline_keyboard)
        await state.clear()
        await callback.answer("Лекция удалена.")


# ----------------- Изменить название -----------------
@admin_lectures_router.callback_query(F.data == "lecture_update_name_click")
async def lecture_update_name_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(media_id=callback.message.message_id)

    data = await state.get_data()
    idx = data.get("lecture_index")
    if idx is None:
        await callback.answer("Нет выбранной лекции для изменения названия.", show_alert=True)
        return

    await state.set_state(EditLectureStates.waiting_for_name)
    msg = await callback.message.answer("Введите новое название лекции:")
    await push_bot_message(msg.message_id, state)


@admin_lectures_router.message(EditLectureStates.waiting_for_name)
async def handle_new_lecture_name(message: Message, conn: AsyncConnection, state: FSMContext):
    await push_bot_message(message.message_id, state)

    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым. Попробуйте снова.")
        return

    data = await state.get_data()
    idx = data.get("lecture_index")
    lectures = await db_func.get_lectures_with_file_ids(conn)
    lecture = lectures[idx]

    await db_func.update_lecture(conn, lecture_id=lecture["id"], name=new_name)

    msg = await message.answer(f"Название лекции успешно изменено на: {new_name}")
    await push_bot_message(msg.message_id, state)

    new_lecture = {**lecture, "name": new_name}
    media = InputMediaDocument(
        media=new_lecture["telegram_file_id"],
        caption=make_lecture_text(new_lecture)
    )

    await message.bot.edit_message_media(chat_id=message.chat.id, message_id=data["media_id"], media=media,
                                         reply_markup=keyb.admin_lecture_select())

    await asyncio.sleep(1.5)
    await clear_bot_messages(message, state)

    await state.set_state(None)

# ----------------- Обновить файл лекции -----------------
@admin_lectures_router.callback_query(F.data == "lecture_update_click")
async def lecture_update_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(media_id=callback.message.message_id)

    data = await state.get_data()
    idx = data.get("lecture_index")
    if idx is None:
        await callback.answer("Нет выбранной лекции для обновления файла.", show_alert=True)
        return

    await state.set_state(EditLectureStates.waiting_for_file)

    msg = await callback.message.answer("Отправьте новый PDF-файл для лекции:")
    await push_bot_message(msg.message_id, state)


# ----------------- Обработка нового PDF файла -----------------
@admin_lectures_router.message(EditLectureStates.waiting_for_file, F.document.mime_type.in_(ALLOWED_TYPE))
async def handle_new_lecture_file(message: Message, conn: AsyncConnection, state: FSMContext):
    await push_bot_message(message.message_id, state)

    data = await state.get_data()
    idx = data.get("lecture_index")
    if idx is None:
        await message.answer("Нет выбранной лекции для обновления файла.")
        await state.clear()
        return

    lectures = await db_func.get_lectures(conn)
    lecture = lectures[idx]

    await db_func.update_lecture_file(
        conn,
        lecture_id=lecture['id'],
        telegram_file_id=message.document.file_id,
        file_type="lecture"
    )

    msg = await message.answer(f"Файл лекции '{lecture['name']}' успешно обновлён.")
    await push_bot_message(msg.message_id, state)


    media = InputMediaDocument(
        media=message.document.file_id,
        caption=make_lecture_text(lecture)
    )

    await message.bot.edit_message_media(chat_id=message.chat.id, message_id=data["media_id"], media=media,
                                         reply_markup=keyb.admin_lecture_select())

    await asyncio.sleep(1.5)
    await clear_bot_messages(message, state)

    await state.set_state(None)


@admin_lectures_router.message(EditLectureStates.waiting_for_file, ~F.document.mime_type.in_(ALLOWED_TYPE))
async def handle_wrong_file_type(message: Message):
    await message.answer("Нужен PDF-файл. Попробуйте снова.")


@admin_lectures_router.callback_query(F.data == "cancel_lectures_click")
async def process_cancel_lectures_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if state:
        await state.clear()

    try:
        inline_keyboard = keyb.admin_media()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except TelegramBadRequest:
        logger.exception("Failed to edit lectures message back to admin menu.")


@admin_lectures_router.callback_query(F.data == "cancel_lectures_select_click")
async def process_cancel_lectures_select_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if state:
        await state.clear()

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        logger.exception("Failed to delete lecture message.")

    inline_keyboard = keyb.admin_lectures()
    await callback.message.answer("Выберите действие:", reply_markup=inline_keyboard)

