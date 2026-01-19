from aiogram import Router

from app.bot.enums.enums import UserRole
from app.bot.filters.filters import UserRoleFilter, IsBanned
from .user import user_main_router
from .lectures import user_lectures_router
from .labs import user_labs_router
from .tests import user_tests_router

user_router = Router(name="user")

user_router.message.filter(UserRoleFilter(UserRole.STUDENT), ~IsBanned())

user_router.include_router(user_main_router)
user_router.include_router(user_lectures_router)
user_router.include_router(user_labs_router)
user_router.include_router(user_tests_router)

__all__ = ["user_router"]
