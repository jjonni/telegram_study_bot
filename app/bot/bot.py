import logging

import psycopg_pool
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.admin import admin_router
from app.bot.handlers.others import others_router
from app.bot.handlers.user import user_router
from app.bot.middlewares.database import DataBaseMiddleware
from app.bot.middlewares.shadow_ban import ShadowBanMiddleware
from app.infrastructure.database.connection import get_psql_pool
from config.config import Config

logger = logging.getLogger(__name__)

async def main(config: Config) -> None:
    logger.info("Starting bot...")

    storage = MemoryStorage()

    bot = Bot(token=config.bot.token,default=DefaultBotProperties(parse_mode=ParseMode.HTML),)
    dp = Dispatcher(storage=storage)

    db_pool: psycopg_pool.AsyncConnectionPool = await get_psql_pool(
        name=config.db.name,
        host=config.db.host,
        port=config.db.port,
        user=config.db.user,
        password=config.db.password,
    )

    logger.info("Including routers...")
    dp.include_routers(admin_router, user_router, others_router)

    logger.info("Including middlewares...")
    dp.update.middleware(DataBaseMiddleware())
    dp.update.middleware(ShadowBanMiddleware())

    try:
        await dp.start_polling(
            bot, db_pool=db_pool,
            admin_ids=config.bot.super_admin_ids
        )
    except Exception as e:
        logger.exception(e)
    finally:
        await db_pool.close()
        logger.info("Connection to Postgres closed")