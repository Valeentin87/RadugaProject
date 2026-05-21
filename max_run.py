import asyncio
import os
import sys

# Добавляем корень проекта (/RadugaProject) в sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


import aiomax
from aiomax import BotCommand
from dotenv import load_dotenv
    
from create_bot_max import bot
from handlers.admin_router_max import admin_router_max, create_sheduler_jobs
#from handlers.user_router_max import user_router_max
from create_bot_max import logger, scheduler



# load_dotenv()

# admins = list(os.getenv('ADMIN_ID').split())

# logger.info(f"aiogram_run.py: {admins=}")


# async def start_bot():
#     #await create_tables()
#     await create_sheduler_jobs()
#     for admin_id in admins:
#         try:
#            await  bot.send_message('Бот запущен', admin_id, format='html')
#         except:
#             pass


# async def stop_bot():
#     try:
#         for admin_id in admins:
#             await bot.send_message('Бот остановлен!', admin_id, format='html')
#     except:
#         pass




# async def run_max_bot(bot) -> None:
#     logger.info("🚀 Запускаем MAX-бота...")
#     logger.info("[INFO][run_max_bot] Регистрируем router")
#     bot.add_router(admin_router_max)
#     await start_bot()
#     #bot.add_router(user_router_max)
#     logger.info("[INFO][run_max_bot] Стартуем бот")
#     bot.run()

    
# @bot.on_ready()
# async def send_commands():
#     logger.info("[INFO][send_commands] Устанавливаем команды")
#     scheduler.start()
#     await bot.patch_me(commands=[
#         BotCommand('start', 'Начало работы с ботом'),
#         BotCommand('admin', 'Панель администратора')
#     ])


# if __name__ == "__main__":
#     #run_max_bot(bot)
    
#     asyncio.run(run_max_bot(bot))

load_dotenv()

# Исправленная обработка ADMIN_ID
admin_ids_str = os.getenv('ADMIN_ID')
if admin_ids_str:
    admins = list(map(int, admin_ids_str.split(' ')))
else:
    admins = []
    logger.warning("ADMIN_ID не задан в окружении")

logger.info(f"aiogram_run.py: {admins=}")

async def start_bot():
    await create_sheduler_jobs()
    for admin_id in admins:
        try:
            await bot.send_message('Бот запущен', admin_id, format='html')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

async def stop_bot():
    for admin_id in admins:
        try:
            await bot.send_message('Бот остановлен!', admin_id, format='html')
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")

async def run_max_bot(bot) -> None:
    logger.info("🚀 Запускаем MAX-бота...")
    logger.info("[INFO][run_max_bot] Регистрируем router")
    bot.add_router(admin_router_max)
    await start_bot()
    logger.info("[INFO][run_max_bot] Стартуем бот")

    # Запускаем polling напрямую, без bot.run()
    try:
        await bot.start_polling()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания. Останавливаем бота...")
    finally:
        await stop_bot()
        await bot.session.close()


@bot.on_ready()
async def send_commands():
    logger.info("[INFO][send_commands] Устанавливаем команды")
    scheduler.start()
    await bot.patch_me(commands=[
        BotCommand('start', 'Начало работы с ботом'),
        BotCommand('admin', 'Панель администратора')
    ])


if __name__ == "__main__":
    try:
        asyncio.run(run_max_bot(bot))
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}") 