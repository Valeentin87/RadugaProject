import os
import sys

# Добавляем корень проекта (/RadugaProject) в sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


import aiomax
from aiomax import BotCommand
    
from create_bot_max import bot
from handlers.admin_router_max import admin_router_max
#from handlers.user_router_max import user_router_max
from create_bot_max import logger


def run_max_bot(bot) -> None:
    logger.info("🚀 Запускаем MAX-бота...")
    logger.info("[INFO][run_max_bot] Регистрируем router")
    bot.add_router(admin_router_max)
    #bot.add_router(user_router_max)
    logger.info("[INFO][run_max_bot] Стартуем бот")
    bot.run()

    
@bot.on_ready()
async def send_commands():
    logger.info("[INFO][send_commands] Устанавливаем команды")
    await bot.patch_me(commands=[
        BotCommand('start', 'Начало работы с ботом'),
        BotCommand('admin', 'Панель администратора')
    ])


if __name__ == "__main__":
    run_max_bot(bot)

 