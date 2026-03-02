import os
import logging   # Импортируем библиотеку для логирования, чтобы записывать события и ошибки в процессе работы бота.
from aiogram import Bot, Dispatcher # Импортируем классы Bot и Dispatcher из библиотеки aiogram, которые необходимы для создания и управления ботом.
from aiogram.client.default import DefaultBotProperties # Импортируем класс MemoryStorage для хранения состояний конечного автомата (FSM) в памяти.
from aiogram.enums import ParseMode #
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv


load_dotenv()

scheduler = AsyncIOScheduler(timezone='Europe/Moscow') # Создаем объект AsyncIOScheduler для планирования и выполнения задач по времени. Устанавливаем часовой пояс на Europe/Moscow.
admins = [int(admin_id) for admin_id in os.getenv('ADMIN_ID').split()]

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

file_handler = logging.FileHandler('claims_control.log')
file_handler.setLevel(logging.WARNING)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d (%(funcName)s) - %(message)s")
file_handler.setFormatter(formatter)

# Очищаем старые обработчики и добавляем новый
logger.handlers.clear()
logger.addHandler(file_handler)

# Отключаем передачу в родительские логгеры
logger.propagate = False


bot = Bot(token=os.getenv('BOT_TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage()) # основной объект, отвечающий за обработку входящих сообщений и других обновлений, поступающих от Telegram. Именно через диспетчер проходят все сообщения и команды, отправляемые пользователями бота.

