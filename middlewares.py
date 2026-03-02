

import os, sys

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

from aiogram import BaseMiddleware, Bot
from aiogram.types import Update, Message, BotCommandScopeChat
from aiogram.types import BotCommand
from commands import BASIC_COMMANDS, ADMIN_COMMANDS
import os
from aiogram import BaseMiddleware, Bot



ADMIN_IDS = set(map(int, os.getenv("ADMIN_ID").split(" ")))

class CommandMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        bot: Bot = data["bot"]

        user_id = None
        if event.message and isinstance(event.message, Message):
            user_id = event.message.from_user.id
        # Добавьте обработку других типов событий, если нужно

        if not user_id:
            return await handler(event, data)

        # Формируем команды
        if user_id in ADMIN_IDS:
            commands = BASIC_COMMANDS + ADMIN_COMMANDS
        else:
            commands = BASIC_COMMANDS

        # Устанавливаем команды для конкретного пользователя
        await bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(chat_id=user_id)  # Вот так правильно!
        )

        return await handler(event, data)
    






