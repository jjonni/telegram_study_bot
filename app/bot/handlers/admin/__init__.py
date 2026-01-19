from aiogram import Router

from app.bot.enums.enums import UserRole
from app.bot.filters.filters import UserRoleFilter
from .admin import admin_main_router
from .lectures import admin_lectures_router
from .labs import admin_labs_router
from .tests import admin_tests_router

admin_router = Router(name="admin")

admin_router.message.filter(UserRoleFilter(UserRole.ADMIN))

admin_router.include_router(admin_main_router)
admin_router.include_router(admin_lectures_router)
admin_router.include_router(admin_labs_router)
admin_router.include_router(admin_tests_router)

__all__ = ["admin_router"]
