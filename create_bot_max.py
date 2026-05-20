import logging
from aiomax import fsm, Bot
import os
from dotenv import load_dotenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler('claims_control.log')
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d (%(funcName)s) - %(message)s")
file_handler.setFormatter(formatter)

# Очищаем старые обработчики и добавляем новый
logger.handlers.clear()
logger.addHandler(file_handler)

# Отключаем передачу в родительские логгеры
logger.propagate = False

MAX_TOKEN = os.getenv('MAX_TOKEN')

storage = fsm.FSMStorage()

bot = Bot(MAX_TOKEN, default_format="markdown")
scheduler = AsyncIOScheduler(timezone='Europe/Moscow') # Создаем объект AsyncIOScheduler для планирования и выполнения задач по времени. Устанавливаем часовой пояс на Europe/Moscow.

