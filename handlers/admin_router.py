import random
import os, sys

from dotenv import load_dotenv

from utils.scrap_utils_new import find_info_of_new_claims

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import json

from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import emoji
from create_bot import bot, logger, scheduler
from keyboards.all_keyboards import claim_keyboard, start_keyboard

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


@admin_router.callback_query(lambda c: c.data == "claims")
async def go_to_admin_menu(callback: CallbackQuery):
    await callback.message.edit_text(text="Выберите одно из действий:", reply_markup=claim_keyboard())
    await callback.answer("ok")



@admin_router.callback_query(lambda c: c.data == "new_claims")
async def check_new_claims_handler(callback: CallbackQuery):
    """Проверяет наличие новых заявок и принимает их в работу, а также
    добавляет в базу данных"""
    try:
        await callback.message.answer("Приступили к поиску новых заявок. Подождите...")
        await callback.answer("ok")
        new_claims_by_company = await find_info_of_new_claims()
        await callback.message.answer("Поиск новых заявок завершен!")
        text_message = "Информация по новым заявкам:\n"
        for company, info in new_claims_by_company.items():
            text_message += f"**{company.upper()}**\n"
            for claim_id, details in info.items():
                text_message += f"Заявка ID={claim_id} Срок выполнения: {details.get('due_date')} Срочность: {details.get('urgency')}\n"
        await callback.message.answer(text=text_message)
    except Exception as e:
        print(f'При получении информации о новых заявках произошла ошибка')
        logger.error(f'При получении информации о новых заявках произошла ошибка')
        await callback.answer("ok")
    
        



