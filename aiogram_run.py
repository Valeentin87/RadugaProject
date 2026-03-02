import os
import asyncio

from dotenv import load_dotenv
from create_bot import bot, dp, scheduler, admins, logger
from handlers.admin_router import admin_router, create_sheduler_jobs
from middlewares import CommandMiddleware

load_dotenv()

admins = list(os.getenv('ADMIN_ID').split())

logger.info(f"aiogram_run.py: {admins=}")


async def start_bot():
    #await create_tables()
    await create_sheduler_jobs()
    for admin_id in admins:
        try:
           await  bot.send_message(admin_id, 'Бот запущен')
        except:
            pass


async def stop_bot():
    try:
        for admin_id in admins:
            await bot.send_message(admin_id, 'Бот остановлен!')
    except:
        pass

async def main():
    scheduler.start()
    dp.update.middleware(CommandMiddleware())
    dp.startup.register(start_bot)
    dp.include_router(admin_router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main()) 
