import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from psycopg import AsyncConnection
from aiogram.fsm.context import FSMContext
import app.infrastructure.database.db as db_func
import app.bot.keyboards.keyboards as keyb
from app.bot.enums.enums import UserRole

logger = logging.getLogger(__name__)

admin_main_router = Router()

def make_user_text(user: dict) -> str:
    return (
        f"Имя пользователя: @{user['username']}\n"
        f"Имя: {user['name']} {user['surname']}\n"
        f"Роль: {"студент" if user['role'] == UserRole.STUDENT else "преподаватель"}\n"
        f"Забанен: {"да " if user['is_banned'] else "нет"}\n"
        f"Дата регистрации: {user['created_at'].strftime("%d-%m-%Y %H:%M %Z")}"
    )

def make_request_text(request: dict) -> str:
    return (
        f"Имя пользователя: @{request['username']}\n"
        f"Имя: {request['name']} {request['surname']}\n"
        f"Дата заявки: {request['requested_at'].strftime("%d-%m-%Y %H:%M %Z")}"
    )

@admin_main_router.message(F.text == "Редактирование материала")
async def process_media_edit(message: Message):
    inline_keyboard = keyb.admin_media()
    await message.answer("Выберите действие:", reply_markup=inline_keyboard)

@admin_main_router.message(F.text == "Контроль активности студентов")
async def check_student_activity(message: Message):
    inline_keyboard = keyb.admin_functions()
    await message.answer("Выберите действие:", reply_markup=inline_keyboard)

@admin_main_router.callback_query(F.data == "ban_user_click")
async def process_ban_user_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    users = await db_func.get_users(conn)
    users = [u for u in users if u['telegram_id'] != callback.from_user.id]

    if not users:
        await callback.answer("Пользователей не существует.")
        return

    current_index = await state.get_data()
    idx = current_index.get("user_index", 0)
    user = users[idx]

    text = make_user_text(user)

    inline_keyboard = keyb.admin_ban_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)
    await state.update_data(user_index=idx)

@admin_main_router.callback_query(F.data == "ban_click")
async def process_ban_click(callback: CallbackQuery, bot: Bot, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    users = await db_func.get_users(conn)
    users = [u for u in users if u['telegram_id'] != callback.from_user.id]

    if not users:
        await asyncio.sleep(1)
        await state.clear()
        await callback.answer("Пользователей не существует.")
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        return

    current_index = await state.get_data()
    idx = current_index.get("user_index", 0)

    if idx < 0:
        idx = 0
    elif idx >= len(users):
        idx = len(users) - 1

    user = users[idx]

    if user['is_banned']:
        await callback.answer("Пользователей уже забанен.")
        return

    await db_func.ban_user(conn, telegram_id=user['telegram_id'])

    await bot.send_message(user['telegram_id'], "Вас забанил администратор.")

    user['is_banned'] = not user['is_banned']
    text = make_user_text(user)

    inline_keyboard = keyb.admin_ban_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)

    await callback.answer("Пользователь забанен.")

@admin_main_router.callback_query(F.data == "unban_click")
async def process_unban_click(callback: CallbackQuery, bot: Bot, conn: AsyncConnection, state: FSMContext):
    await callback.answer()

    users = await db_func.get_users(conn)
    users = [u for u in users if u['telegram_id'] != callback.from_user.id]

    if not users:
        await asyncio.sleep(1)
        await state.clear()
        await callback.answer("Пользователей не существует.")
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        return

    current_index = await state.get_data()
    idx = current_index.get("user_index", 0)

    if idx < 0:
        idx = 0
    elif idx >= len(users):
        idx = len(users) - 1

    user = users[idx]

    if not user['is_banned']:
        await callback.answer("У пользователя нет бана.")
        return

    await db_func.unban_user(conn, telegram_id=user['telegram_id'])

    await bot.send_message(user['telegram_id'], "Вас разбанил администратор.")

    user['is_banned'] = not user['is_banned']
    text = make_user_text(user)

    inline_keyboard = keyb.admin_ban_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)

    await callback.answer("Пользователь разбанен.")

@admin_main_router.callback_query(F.data == "prev_ban_click")
async def process_prev_ban_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    users = await db_func.get_users(conn)
    users = [u for u in users if u['telegram_id'] != callback.from_user.id]

    if not users:
        await callback.message.edit_text("Пользователей не существует.")
        await state.clear()
        return

    current_index = await state.get_data()
    idx = current_index.get("user_index", 0)

    idx -= 1
    if idx < 0:
        await callback.answer("Это первый пользователь.")
        return

    await state.update_data(user_index=idx)
    user = users[idx]

    text = make_user_text(user)

    inline_keyboard = keyb.admin_ban_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)

@admin_main_router.callback_query(F.data == "next_ban_click")
async def process_next_ban_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    users = await db_func.get_users(conn)
    users = [u for u in users if u['telegram_id'] != callback.from_user.id]

    if not users:
        await callback.message.edit_text("Пользователей не существует.")
        await state.clear()
        return

    current_index = await state.get_data()
    idx = current_index.get("user_index", 0)

    idx += 1
    if idx >= len(users):
        await callback.answer("Это последний пользователь.")
        return

    await state.update_data(user_index=idx)
    user = users[idx]

    text = make_user_text(user)

    inline_keyboard = keyb.admin_ban_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)

@admin_main_router.callback_query(F.data == "requests_click")
async def process_requests_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    requests = await db_func.get_access_requests(conn)

    if not requests:
        await callback.answer("Заявок нет.")
        return

    current_index = await state.get_data()
    idx = current_index.get("request_index", 0)
    request = requests[idx]

    text = make_request_text(request)

    inline_keyboard = keyb.admin_request_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)
    await state.update_data(request_index=idx)

@admin_main_router.callback_query(F.data == "approve_click")
async def process_approve_click(callback: CallbackQuery, bot: Bot, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    requests = await db_func.get_access_requests(conn)

    if not requests:
        await asyncio.sleep(1)
        await state.clear()
        await callback.answer("Больше заявок нет.")
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        return

    current_index = await state.get_data()
    idx = current_index.get("request_index", 0)

    if idx < 0:
        idx = 0
    elif idx >= len(requests):
        idx = len(requests) - 1

    request = requests[idx]

    await db_func.create_user_from_request(conn, request_id=request['id'])
    await db_func.delete_access_request(conn, request_id=request['id'])

    await bot.send_message(request['telegram_id'], "Поздравляем, Ваша заявка была одобрена.")

    new_requests = await db_func.get_access_requests(conn)

    if not new_requests:
        await asyncio.sleep(1)
        await state.clear()
        await callback.answer("Больше заявок нет.")
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        return

    if idx >= len(new_requests):
        idx = max(len(new_requests) - 1, 0)

    await state.update_data(request_index=idx)
    next_request = new_requests[idx]
    text = make_request_text(next_request)
    inline_keyboard = keyb.admin_request_action()

    await callback.message.edit_text(text, reply_markup=inline_keyboard)
    await callback.answer("Заявка одобрена.")

@admin_main_router.callback_query(F.data == "reject_click")
async def process_reject_click(callback: CallbackQuery, bot: Bot, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    requests = await db_func.get_access_requests(conn)

    if not requests:
        await asyncio.sleep(1)
        await state.clear()
        await callback.answer("Больше заявок нет.")
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        return

    current_index = await state.get_data()
    idx = current_index.get("request_index", 0)
    request = requests[idx]

    await bot.send_message(request['telegram_id'], "Увы, Ваша заявка была отклонена.\nЕсли Вы считаете это ошибкой, свяжитесь с администратором лично.")

    await db_func.delete_access_request(conn, request_id=request['id'])

    new_requests = await db_func.get_access_requests(conn)

    if not new_requests:
        await asyncio.sleep(1)
        await state.clear()
        await callback.answer("Больше заявок нет.")
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
        return

    if idx >= len(new_requests):
        idx = max(len(new_requests) - 1, 0)

    await state.update_data(request_index=idx)
    next_request = new_requests[idx]
    text = make_request_text(next_request)
    inline_keyboard = keyb.admin_request_action()

    await callback.message.edit_text(text, reply_markup=inline_keyboard)
    await callback.answer("Заявка отклонена.")

@admin_main_router.callback_query(F.data == "prev_request_click")
async def process_prev_request_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    requests = await db_func.get_access_requests(conn)

    if not requests:
        await callback.message.edit_text("Заявок нет.")
        await state.clear()
        return

    current_index = await state.get_data()
    idx = current_index.get("request_index", 0)

    idx -= 1
    if idx < 0:
        await callback.answer("Это первый запрос.")
        return

    await state.update_data(request_index=idx)
    request = requests[idx]

    text = make_request_text(request)

    inline_keyboard = keyb.admin_request_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)

@admin_main_router.callback_query(F.data == "next_request_click")
async def process_next_request_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    requests = await db_func.get_access_requests(conn)

    if not requests:
        await callback.message.edit_text("Заявок нет.")
        await state.clear()
        return

    current_index = await state.get_data()
    idx = current_index.get("request_index", 0)

    idx += 1
    if idx >= len(requests):
        await callback.answer("Это последний запрос.")
        return

    await state.update_data(request_index=idx)
    request = requests[idx]

    text = make_request_text(request)

    inline_keyboard = keyb.admin_request_action()
    await callback.message.edit_text(text, reply_markup=inline_keyboard)

@admin_main_router.callback_query(F.data == "cancel_user_click")
async def process_cancel_user_click(callback: CallbackQuery, conn: AsyncConnection, state: FSMContext):
    await callback.answer()
    if state:
        await state.clear()

    try:
        inline_keyboard = keyb.admin_functions()
        await callback.message.edit_text("Выберите действие:", reply_markup=inline_keyboard)
    except Exception:
        logger.exception("Failed to edit requests message back to admin menu.")