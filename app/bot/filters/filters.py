# Вдохновлено https://stepik.org/course/120924/syllabus

import logging
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from psycopg import AsyncConnection

from typing import Union
import app.infrastructure.database.db as db_func
from app.bot.enums.enums import UserRole
from app.infrastructure.database.db import get_user_role

logger = logging.getLogger(__name__)

class UserRoleFilter(BaseFilter):
    def __init__(self, *roles: str | UserRole):
        if not roles:
            raise ValueError("At least one role must be provided to UserRoleFilter.")

        self.roles = frozenset(
            UserRole(role) if isinstance(role, str) else role
            for role in roles
            if isinstance(role, (str, UserRole))
        )

        if not self.roles:
            raise ValueError("No valid roles provided to UserRoleFilter.")

    async def __call__(self, event: Message | CallbackQuery, conn: AsyncConnection) -> bool:
        user = event.from_user
        if not user:
            logger.warning("No user found in event: %s", event)
            return False

        role = await get_user_role(conn, telegram_id=user.id)

        if role is None:
            logger.info("User %s not found in database", user.id)
            return False

        has_access = role in self.roles
        logger.debug("User %s has role=%s, access=%s", user.id, role, has_access)

        return has_access

class IsBanned(BaseFilter):
    async def __call__(self, message: Message, conn: AsyncConnection) -> bool:
        user = await db_func.get_user(conn, telegram_id=message.from_user.id)
        if not user:
            return False
        return user.get("is_banned")