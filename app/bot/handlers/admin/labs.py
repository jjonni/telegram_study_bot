import asyncio
import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery, InputMediaDocument
from psycopg import AsyncConnection
from aiogram.fsm.context import FSMContext
from app.bot.states.states import AddLabStates, EditLabStates
import app.infrastructure.database.db as db_func
import app.bot.keyboards.keyboards as keyb

admin_labs_router = Router(name="admin_labs")

logger = logging.getLogger(__name__)

ALLOWED_TYPE = ["application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/octet-stream"]

def make_lab_text(lab: dict) -> str:
    text = (
        f"Лабораторная работа «{lab['name']}»\n"
    )
    if lab.get("description"):
        text += f"\nОписание: {lab['description']}"
    return text

# --- Хендлеры клавиатур и навигации ---
@admin_labs_router.callback_query(F.data == "labs_click")
async def process_labs_edit(callback: CallbackQuery):
    await callback.answer()
    inline_keyboard = keyb.admin_labs()

    try:
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except Exception:
        await callback.message.answer("Выберите действие:", reply_markup=inline_keyboard)


@admin_labs_router.callback_query(F.data == "labs_select_click")
async def process_labs_select(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    await state.update_data(media_id=callback.message.message_id)
    labs = await db_func.get_lab_works_with_file_ids(conn)

    if not labs:
        await callback.message.edit_text("Лабораторных работ нет.")
        await state.clear()
        return

    idx = 0
    lab = labs[idx]

    media = InputMediaDocument(
        media=lab["telegram_file_id"],
        caption=make_lab_text(lab)
    )

    inline_keyboard = keyb.admin_lab_select()
    await callback.message.edit_media(media=media, reply_markup=inline_keyboard)

    await state.update_data(lab_index=idx)

@admin_labs_router.callback_query(F.data == "prev_lab_click")
async def process_prev_lab_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    labs = await db_func.get_lab_works_with_file_ids(conn)
    if not labs:
        await callback.message.edit_text("Лабораторных работ нет.")
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("lab_index", 0) - 1
    if idx < 0:
        await callback.answer("Это первая лабораторная.")
        return

    lab = labs[idx]

    media = InputMediaDocument(
        media=lab["telegram_file_id"],
        caption=make_lab_text(lab)
    )

    inline_keyboard = keyb.admin_lab_select()
    await callback.message.edit_media(media=media, reply_markup=inline_keyboard)
    await state.update_data(lab_index=idx)


@admin_labs_router.callback_query(F.data == "next_lab_click")
async def process_next_lab_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    labs = await db_func.get_lab_works_with_file_ids(conn)
    if not labs:
        await callback.message.edit_text("Лабораторных работ нет.")
        await state.clear()
        return

    data = await state.get_data()
    idx = data.get("lab_index", 0) + 1
    if idx >= len(labs):
        await callback.answer("Это последняя лабораторная.")
        return

    lab = labs[idx]

    media = InputMediaDocument(
        media=lab["telegram_file_id"],
        caption=make_lab_text(lab)
    )

    inline_keyboard = keyb.admin_lab_select()
    await callback.message.edit_media(media=media, reply_markup=inline_keyboard)
    await state.update_data(lab_index=idx)

@admin_labs_router.callback_query(F.data == "lab_add_click")
async def lab_add_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddLabStates.waiting_for_name)
    msg_instruction = await callback.message.answer("Введите название новой лабораторной:")
    await state.update_data(msg_instruction_id=msg_instruction.message_id)
    try:
        await callback.message.delete()
    except Exception:
        logger.debug("Couldn't delete original labs message on lab_add_click")
    await callback.answer()


# ----------------- Получаем имя лабораторной -----------------
@admin_labs_router.message(AddLabStates.waiting_for_name)
async def handle_new_lab_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Попробуйте снова.")
        return

    await state.update_data(lab_name=name)
    await state.set_state(AddLabStates.waiting_for_file)
    msg_instruction = await message.answer("Отправьте PDF-файл лабораторной:")

    data = await state.get_data()
    prev_instr = data.get("msg_instruction_id")

    await state.update_data(prev_instruction_id=prev_instr)
    await state.update_data(msg_answer_id=message.message_id)
    await state.update_data(msg_instruction_id=msg_instruction.message_id)


# ----------------- Принимаем PDF и создаём запись -----------------
@admin_labs_router.message(AddLabStates.waiting_for_file, F.document.mime_type.in_(ALLOWED_TYPE))
async def handle_new_lab_file(message: Message, state: FSMContext, conn: AsyncConnection):
    data = await state.get_data()
    lab_name = data.get("lab_name")
    if not lab_name:
        await message.answer("Не найдено имя лабораторной. Операция отменена.")
        await state.clear()
        return

    telegram_file_id = message.document.file_id

    try:
        file_record_id = await db_func.add_file(
            conn,
            file_type="lab",
            telegram_file_id=telegram_file_id,
            path=telegram_file_id
        )
    except Exception as exc:
        logger.exception("Не удалось добавить файл в БД: %s", exc)
        await message.answer("Ошибка при сохранении файла в БД. Повторите попытку или сообщите разработчику.")
        await state.clear()
        return

    if file_record_id is None:
        await message.answer("Не удалось получить id файла. Операция отменена.")
        await state.clear()
        return

    try:
        new_lab_id = await db_func.add_lab_work(
            conn,
            name=lab_name,
            file_id=file_record_id,
            description=None,
            deadline=None,
            allow_late=False
        )
    except Exception as exc:
        logger.exception("Не удалось создать запись лабораторной: %s", exc)
        await message.answer("Ошибка при создании записи лабораторной.")
        await state.clear()
        return

    msg_confirmation = await message.answer(f"Лабораторная '{lab_name}' добавлена.")
    await asyncio.sleep(1.5)

    try:
        prev_instruction_id = data.get("prev_instruction_id")
        msg_instruction_id = data.get("msg_instruction_id")
        msg_answer_id = data.get("msg_answer_id")

        if msg_answer_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_answer_id)
        if msg_instruction_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_instruction_id)
        await message.delete()
        if prev_instruction_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prev_instruction_id)
    except Exception:
        pass
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_confirmation.message_id)
    except Exception:
        pass

    new_lab = {
        "id": new_lab_id,
        "name": lab_name,
        "file_id": file_record_id,
        "telegram_file_id": telegram_file_id,
        "description": None
    }
    try:
        await message.answer(
            text="Выберите действие:",
            reply_markup=keyb.admin_labs()
        )
    except Exception as e:
        logger.warning("Не удалось отправить карточку новой лабораторной: %s", e)

    await state.clear()



# --- Неподходящий файл ---
@admin_labs_router.message(EditLabStates.waiting_for_file, ~F.document.mime_type.in_(ALLOWED_TYPE))
async def handle_new_lab_wrong_file(message: Message):
    await message.answer("Не тот формат файла. Попробуйте снова.")

# --- Удаление лабораторной ---
@admin_labs_router.callback_query(F.data == "lab_delete_click")
async def lab_delete_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    idx = data.get("lab_index")
    if idx is None:
        await callback.answer("Нет выбранной лабораторной для удаления.", show_alert=True)
        return

    labs = await db_func.get_lab_works_with_file_ids(conn)
    if not labs:
        await callback.answer("Лабораторных работ нет.", show_alert=False)
        await state.clear()
        inline_keyboard = keyb.admin_labs()
        try:
            await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        except Exception:
            await callback.message.answer("Выберите действие:", reply_markup=inline_keyboard)
        return

    if idx < 0:
        idx = 0
    elif idx >= len(labs):
        idx = len(labs) - 1

    lab = labs[idx]

    try:
        await db_func.delete_lab_work(conn, lab_id=lab["id"])
        logger.info("Deleted lab id=%s name=%s", lab["id"], lab["name"])
    except Exception as e:
        logger.exception("Failed to delete lab from db: %s", e)
        await callback.answer("Ошибка удаления из БД.", show_alert=True)
        return

    new_labs = await db_func.get_lab_works_with_file_ids(conn)
    if not new_labs:
        await state.clear()
        inline_keyboard = keyb.admin_labs()
        try:
            await callback.message.edit_text(f"Лабораторная '{lab['name']}' удалена.\nЛабораторных работ больше нет.", reply_markup=inline_keyboard)
        except TelegramBadRequest:
            await callback.message.answer(f"Лабораторная '{lab['name']}' удалена.\nЛабораторных работ больше нет.", reply_markup=inline_keyboard)
        await callback.answer("Лабораторная удалена.")
        return

    if idx >= len(new_labs):
        idx = max(len(new_labs) - 1, 0)

    next_lab = new_labs[idx]
    caption = make_lab_text(next_lab)
    inline_keyboard = keyb.admin_lab_select()

    try:
        media = InputMediaDocument(media=next_lab["telegram_file_id"], caption=caption)
        await callback.message.edit_media(media=media, reply_markup=inline_keyboard)
        await state.update_data(lab_index=idx)
        await callback.answer("Лабораторная удалена. Показана следующая.")
        return
    except TelegramBadRequest as e:
        logger.debug("edit_media failed after delete, will send new document: %s", e)

    try:
        new_msg = await callback.message.chat.send_document(
            document=next_lab["telegram_file_id"],
            caption=caption,
            reply_markup=inline_keyboard
        )
        try:
            await callback.message.delete()
        except Exception:
            logger.debug("Old lab message wasn't deleted or already removed.")
        await state.update_data(lab_index=idx, labs_message_id=new_msg.message_id)
        await callback.answer("Лабораторная удалена. Показана следующая.")
    except Exception as e:
        logger.exception("Failed to show next lab after deletion: %s", e)
        inline_keyboard = keyb.admin_labs()
        await callback.message.answer(f"Лабораторная '{lab['name']}' удалена, но не удалось показать следующую.", reply_markup=inline_keyboard)
        await state.set_state(None)
        await state.update_data(msg_instruction_id=None)
        await callback.answer("Лабораторная удалена.")


# --- Переименование ---
@admin_labs_router.callback_query(F.data == "lab_update_name_click")
async def lab_update_name_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    idx = data.get("lab_index")
    if idx is None:
        await callback.answer("Нет выбранной лабораторной для изменения названия.", show_alert=True)
        return

    await state.set_state(EditLabStates.waiting_for_name)
    msg_instruction = await callback.message.answer("Введите новое название лабораторной:")
    await state.update_data(msg_instruction_id=msg_instruction.message_id)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning("Failed to delete lab message: %s", e)


@admin_labs_router.message(EditLabStates.waiting_for_name)
async def handle_edit_lab_name(message: Message, state: FSMContext, conn: AsyncConnection):
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Название не может быть пустым. Попробуйте снова.")
        return

    data = await state.get_data()
    idx = data.get("lab_index")
    if idx is None:
        await message.answer("Не удалось определить выбранную лабораторную. Операция отменена.")
        await state.clear()
        return

    labs = await db_func.get_lab_works_with_file_ids(conn)
    if not labs or idx >= len(labs):
        await message.answer("Лабораторная не найдена. Операция отменена.")
        await state.clear()
        return

    lab = labs[idx]

    await db_func.update_lab_work(conn, lab_id=lab["id"], name=new_name)

    msg_instruction_id = data.get("msg_instruction_id")
    try:
        await message.delete()
    except Exception:
        pass
    if msg_instruction_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_instruction_id)
        except Exception:
            pass

    updated_lab = {**lab, "name": new_name}
    caption = make_lab_text(updated_lab)
    inline_keyboard = keyb.admin_lab_select()
    try:
        new_msg = await message.bot.send_document(
            chat_id=message.chat.id,
            document=lab["telegram_file_id"],
            caption=caption,
            reply_markup=inline_keyboard
        )

        await state.update_data(labs_message_id=new_msg.message_id, lab_index=idx)
    except Exception as e:
        logger.exception("Failed to send updated lab media: %s", e)
        await message.answer("Не удалось показать обновлённую лабораторную.")

    await state.set_state(None)
    await state.update_data(msg_instruction_id=None)


# --- Обновление файла лабораторной ---
@admin_labs_router.callback_query(F.data == "lab_update_click")
async def lab_update_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    logger.debug("lab_update_click")

    data = await state.get_data()
    idx = data.get("lab_index")
    if idx is None:
        await callback.answer("Нет выбранной лабораторной для обновления файла.", show_alert=True)
        return

    await state.set_state(EditLabStates.waiting_for_file)
    msg = await callback.message.answer("Отправьте новый PDF-файл для лабораторной:")
    await state.update_data(msg_instruction_id=msg.message_id)

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning("Failed to delete lab message: %s", e)


@admin_labs_router.message(EditLabStates.waiting_for_file, F.document.mime_type.in_(ALLOWED_TYPE))
async def handle_new_lab_file(message: Message, state: FSMContext, conn: AsyncConnection):
    data = await state.get_data()
    idx = data.get("lab_index")
    labs = await db_func.get_lab_works(conn)
    if labs is None or idx is None or idx >= len(labs):
        await message.answer("Не удалось найти выбранную лабораторную. Операция отменена.")
        await state.clear()
        return

    lab = labs[idx]

    try:
        new_file_record_id = await db_func.add_file(
            connection=conn,
            file_type="lab",
            telegram_file_id=message.document.file_id,
            path=None
        )
    except Exception as e:
        logger.exception("Не удалось добавить/find файл: %s", e)
        await message.answer("Ошибка при сохранении файла в БД.")
        await state.clear()
        return

    if new_file_record_id is None:
        await message.answer("Ошибка при добавлении файла в базу.")
        await state.clear()
        return

    await db_func.update_lab_work(conn, lab_id=lab["id"], file_id=new_file_record_id)

    msg_confirmation = await message.answer(f"Файл лабораторной '{lab['name']}' успешно обновлён.")
    await asyncio.sleep(1.2)
    try:
        await message.delete()
    except Exception:
        logger.exception("")
    try:
        msg_instruction_id = data.get("msg_instruction_id")
        if msg_instruction_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_instruction_id)
        else: logger.warning("msg_instruction_id not found")
    except Exception:
        logger.exception("")
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_confirmation.message_id)
    except Exception:
        logger.exception("")

    new_labs = await db_func.get_lab_works_with_file_ids(conn)
    if not new_labs:
        await message.answer("Обновление прошло, но не удалось получить список лабораторных.")
        await state.clear()
        return

    new_lab = new_labs[idx] if idx < len(new_labs) else new_labs[-1]
    caption = make_lab_text(new_lab)
    inline_keyboard = keyb.admin_lab_select()


    try:
        new_msg = await message.bot.send_document(chat_id=message.chat.id, document=new_lab["telegram_file_id"],
                                                  caption=caption, reply_markup=inline_keyboard)
        try:
            old_msg_id = data.get("labs_message_id")
            if old_msg_id:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=old_msg_id)
        except Exception:
            logger.exception("")
        await state.update_data(lab_index=idx, labs_message_id=new_msg.message_id)
    except Exception as e:
        logger.exception("Не удалось показать обновлённую лабораторную: %s", e)
        await message.answer("Файл обновлен, но не удалось показать обновлённую лабораторную.")

    await state.set_state(None)
    await state.update_data(msg_instruction_id=None)


@admin_labs_router.message(EditLabStates.waiting_for_file, ~F.document.mime_type.in_(ALLOWED_TYPE))
async def handle_wrong_lab_file_type(message: Message):
    await message.answer("Не тот формат файла. Попробуйте снова.")


# --- Описание ---
@admin_labs_router.callback_query(F.data == "lab_update_description_click")
async def lab_update_description_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    idx = data.get("lab_index")
    if idx is None:
        await callback.answer("Нет выбранной лабораторной для изменения описания.", show_alert=True)
        return

    await state.set_state(EditLabStates.waiting_for_description)
    msg_instruction = await callback.message.answer("Введите новое описание лабораторной:")
    await state.update_data(msg_instruction_id=msg_instruction.message_id)

    try:
        await callback.message.delete()
    except Exception:
        logger.exception("")

    await callback.answer()


@admin_labs_router.message(EditLabStates.waiting_for_description)
async def handle_new_lab_description(message: Message, state: FSMContext, conn: AsyncConnection):
    new_description = (message.text or "").strip()
    if new_description == "":
        await message.answer("Описание не может быть пустым. Попробуйте снова.")
        return

    data = await state.get_data()
    idx = data.get("lab_index")
    if idx is None:
        await message.answer("Нет выбранной лабораторной.")
        await state.clear()
        return

    labs = await db_func.get_lab_works_with_file_ids(conn)
    if not labs or idx >= len(labs):
        await message.answer("Лабораторная не найдена.")
        await state.clear()
        return

    lab = labs[idx]
    await db_func.update_lab_work(conn, lab_id=lab["id"], description=new_description)

    msg_confirmation = await message.answer("Описание успешно обновлено.")
    await asyncio.sleep(1.5)

    msg_instruction_id = data.get("msg_instruction_id")
    try:
        await message.delete()
    except Exception:
        pass
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_confirmation.message_id)
    except Exception:
        pass
    if msg_instruction_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_instruction_id)
        except Exception:
            pass

    updated_labs = await db_func.get_lab_works_with_file_ids(conn)
    if updated_labs and idx < len(updated_labs):
        new_lab = updated_labs[idx]
        try:
            new_msg = await message.bot.send_document(chat_id=message.chat.id, document=new_lab["telegram_file_id"],
                                                      caption=make_lab_text(new_lab), reply_markup=keyb.admin_lab_select())
        except Exception as e:
            logger.exception("Failed to send updated lab media after description update")

    await state.set_state(None)
    await state.update_data(msg_instruction_id=None)


@admin_labs_router.callback_query(F.data == "cancel_labs_click")
async def process_cancel_labs_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if state:
        await state.clear()

    try:
        inline_keyboard = keyb.admin_media()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except Exception:
        logger.exception("Failed to edit labs message back to admin menu.")


@admin_labs_router.callback_query(F.data == "cancel_labs_select_click")
async def process_cancel_labs_select_click(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if state:
        await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        logger.warning("Couldn't delete labs selection message.")

    inline_keyboard = keyb.admin_labs()
    await callback.message.answer("Выберите действие:", reply_markup=inline_keyboard)