import logging

from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, ReplyKeyboardMarkup
from app.bot.enums.enums import UserRole
import app.infrastructure.database.db as db_func
import app.bot.keyboards.keyboards as keyb

from psycopg.connection_async import AsyncConnection

logger = logging.getLogger(__name__)

user_main_router = Router()
