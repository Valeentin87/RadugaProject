import random
import os, sys

from dotenv import load_dotenv

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import json

from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import emoji
from create_bot import bot, logger, scheduler
from keyboards.all_keyboards import start_keyboard

load_dotenv()
admin_router = Router()



@admin_router.message(Command(commands=['admin']))
async def admin_start_handler(message:Message, state:FSMContext):
    '''Обработчик для перехода к выбору функций администратора'''
    try:
        await message.answer(text=emoji.emojize(':robot: Режим администратора'))
    except Exception as e:
        logger.error(f'admin_start_handler: Произошла ошибка {e}')


@admin_router.message(F.text.startswith('/start'))
async def cmd_start(message: Message, state:FSMContext):
    """Обработчик команды /start и кнопки Старт"""
    try:
        await message.answer(text=emoji.emojize(':robot: Старт работы бота'), reply_markup=start_keyboard())
    except Exception as e:
        logger.error(f'cmd_start: Произошла ошибка {e}')

