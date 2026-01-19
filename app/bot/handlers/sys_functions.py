import logging
from typing import List

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

logger = logging.getLogger(__name__)

async def push_bot_message(message_id: int, state: FSMContext):
    data = await state.get_data()
    bot_messages: List[int] = data.get("bot_messages", [])

    bot_messages.append(message_id)

    await state.update_data(bot_messages=bot_messages)

async def clear_bot_messages(message: Message, state: FSMContext) -> bool:
    data = await state.get_data()
    bot_messages: List = data.get("bot_messages")

    if not bot_messages:
        return False

    for message_id in reversed(bot_messages):
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=message_id)
        except TelegramBadRequest:
            logger.exception("Failed to delete message in clear_bot_messages")
            return False

    await state.update_data(bot_messages=[])

    return True