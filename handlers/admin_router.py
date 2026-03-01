import random
import os, sys

from dotenv import load_dotenv

from utils.scrap_utils_new import find_info_of_new_claims

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import json
import asyncio
from aiogram import Bot, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import emoji
from create_bot import bot, logger, scheduler
from keyboards.all_keyboards import claim_keyboard, start_keyboard

load_dotenv()
admin_router = Router()

'''
@admin_router.message()
async def collect_group_members(message: Message):
    if message.chat.type in ["group", "supergroup"]:
        user_id = message.from_user.id
        # Сохраняем user_id в БД, если его ещё нет
        # Это позволит отправлять сообщения позже
'''

GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")  # замените на реальный ID

@admin_router.message(Command("broadcast"))
async def send_to_group(message: Message):
    # Текст сообщения для рассылки
    text = "📢 Тестовое оповещение в группу!\n\n" \
             "Скоро мы стартуем"

    try:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode="HTML"  # для форматирования текста
        )
        await message.answer("✅ Сообщение успешно отправлено в группу!")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")



# Функция для рассылки сообщений
async def send_broadcast(user_ids: list, text: str):
    for user_id in user_ids:
        try:
            await bot.send_message(chat_id=user_id, text=text)
            logger.info(f"Сообщение отправлено пользователю {user_id}")
            await asyncio.sleep(0.05)  # Задержка для избежания бана
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


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
        user_id = message.from_user.id
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
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text="Приступили к поиску новых заявок. Подождите...")
        await callback.answer("ok")
        new_claims_by_company = await find_info_of_new_claims()
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text="Поиск новых заявок завершен!")
        text_message = "Информация по новым заявкам:\n"
        for company, info in new_claims_by_company.items():
            text_message += f"**{company.upper()}**\n"
            for claim_id, details in info.items():
                text_message += f"Заявка ID={claim_id} Срок выполнения: {details.get('due_date')} Срочность: {details.get('urgency')}\n"
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID,text=text_message)
    except Exception as e:
        print(f'При получении информации о новых заявках произошла ошибка')
        logger.error(f'При получении информации о новых заявках произошла ошибка')
        await callback.answer("ok")
    
        



