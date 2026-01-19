from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CallbackQuery
from psycopg import AsyncConnection

from app.bot.enums.enums import UserRole
from app.bot.filters.filters import IsBanned
import app.infrastructure.database.db as db_func
import app.bot.keyboards.keyboards as keyb
from app.bot.states.states import FSM_Wait

others_router = Router()

async def start_registration(message: Message, state: FSMContext):
    await message.answer("Начинаем! Введите ваше имя:")
    await state.set_state(FSM_Wait.waiting_for_name)

@others_router.message(Command(commands="start"))
async def process_start_command(
        message: Message,
        conn: AsyncConnection,
        admin_ids: list[int],
        state: FSMContext
):
    user_row: dict = await db_func.get_user(conn, telegram_id=message.from_user.id)

    if user_row is None:
        user_role = UserRole.ADMIN if message.from_user.id in admin_ids else UserRole.STUDENT

        await state.update_data(role=user_role.value)

        if user_role == UserRole.ADMIN:
            await start_registration(message, state)
            return

        button = InlineKeyboardButton(text="Зарегистрироваться", callback_data="register_click")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

        await message.answer("Привет! Вас нет в базе :(", reply_markup=keyboard)
        return
    else:
        user_role = user_row['role']
        buttons: ReplyKeyboardMarkup

        if user_role == UserRole.ADMIN:
            buttons = keyb.admin_buttons()
        elif user_role == UserRole.STUDENT:
            buttons = keyb.user_buttons()

        await db_func.update_user(conn, telegram_id=message.from_user.id, is_alive=True)
        await message.answer(f"Рады Вас приветствовать в системе.\nВаша роль — {"студент" if user_role == UserRole.STUDENT else "преподаватель"}", reply_markup=buttons)

@others_router.callback_query(F.data == "register_click")
async def process_register_click(callback: CallbackQuery, state: FSMContext):
    await start_registration(callback.message, state)

@others_router.message(FSM_Wait.waiting_for_name)
async def start_get_name(message: Message, state: FSMContext, conn: AsyncConnection):
    await state.update_data(name=message.text)
    await message.answer("Введите фамилию:")
    await state.set_state(FSM_Wait.waiting_for_surname)

@others_router.message(FSM_Wait.waiting_for_surname)
async def start_get_surname(message: Message, state: FSMContext, conn: AsyncConnection):
    await state.update_data(surname=message.text)
    data = await state.get_data()
    role_value = data['role'].value if isinstance(data['role'], UserRole) else str(data['role']).strip()

    if data['role'] == UserRole.ADMIN:
        await db_func.add_user(
            conn,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            name=data['name'],
            surname=data['surname'],
            role=role_value
        )
        buttons = keyb.admin_buttons()

        await message.answer("Поздравляем, Вы зарегистрированы.", reply_markup=buttons)
    else:
        await db_func.add_access_request(
            conn,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            name=data['name'],
            surname=data['surname'],
        )

        await message.answer("Ожидайте ответа администратора")

    await state.clear()

@others_router.message(IsBanned())
async def process_text_from_banned(message: Message):
    await message.answer("Вас, вероятно, забанил администратор.\nЕсли Вы считаете это ошибкой — свяжитесь с администратором лично."
                         "Либо у Вас просто нет доступа")

@others_router.message()
async def process_any_text(message: Message):
    await message.answer("Кажется, непреднамеренный ввод")