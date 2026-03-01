import random
import os, sys

from dotenv import load_dotenv

from utils.data_utils import get_details_of_exceeded_claims, get_info_from_site_to_compare, process_and_update_claims
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


import asyncio
from aiogram import Bot
from typing import List


async def send_long_message_to_group(
    bot: Bot,
    chat_id: int,
    text: str,
    max_length: int = 4096,
    delay: float = 0.1,
    add_part_info: bool = False
) -> List[int]:
    """
    Отправляет длинное сообщение в групповой чат, разбивая его на части при превышении max_length.

    Args:
        bot: экземпляр Bot из aiogram
        chat_id: ID группового чата для отправки
        text: текст сообщения
        max_length: максимальная длина одной части (по умолчанию 4096)
        delay: задержка между отправкой частей в секундах
        add_part_info: добавлять ли нумерацию частей («Часть 1/3»)


    Returns:
        list: список message_id отправленных сообщений
    """
    if len(text) <= max_length:
        message = await bot.send_message(chat_id, text)
        return [message.message_id]

    sent_messages = []
    current_pos = 0
    part_number = 1

    while current_pos < len(text):
        # Если остаток текста укладывается в лимит — отправляем его целиком
        if current_pos + max_length >= len(text):
            part = text[current_pos:]
            if add_part_info:
                part = f"Часть {part_number}/{part_number}:\n{part}"
            message = await bot.send_message(chat_id, part)
            sent_messages.append(message.message_id)
            break

        # Ищем ближайший перенос строки в пределах лимита
        search_end = current_pos + max_length
        newline_pos = text.rfind('\n', current_pos, search_end)

        if newline_pos != -1:
            # Отправляем часть до переноса строки
            part = text[current_pos:newline_pos]
            # if add_part_info:
            #     part = f"Часть {part_number}/...:\n{part}"
            message = await bot.send_message(chat_id, part)
            sent_messages.append(message.message_id)
            current_pos = newline_pos + 1  # пропускаем символ \n
            part_number += 1
        else:
            # Если переносов нет — отправляем ровно max_length символов
            part = text[current_pos:current_pos + max_length]
            # if add_part_info:
            #     part = f"Часть {part_number}/...:\n{part}"
            message = await bot.send_message(chat_id, part)
            sent_messages.append(message.message_id)
            current_pos += max_length
            part_number += 1

        # Задержка между сообщениями, чтобы не попасть под rate limiting
        if delay > 0:
            await asyncio.sleep(delay)



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
        text_message = ''
        for company, info in new_claims_by_company.items():
            #text_message += f"**{company.upper()}**\n"
            for claim_id, details in info.items():
                text_message += emoji.emojize(f":NEW_button: <b>Новая заявка</b> для УК {company} ID {claim_id}\n:check_mark_button: Статус заявки для УК {company} ID {claim_id} - <b>В работе</b>\n<b>Тип:</b>{details.get('urgency')}\n<b>Срок ответа исполнителя:</b>{details.get('due_date')}\n\n")
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID,text=text_message)
    except Exception as e:
        print(f'При получении информации о новых заявках произошла ошибка')
        logger.error(f'При получении информации о новых заявках произошла ошибка')
        await callback.answer("ok")


@admin_router.callback_query(lambda c: c.data == "dedline_exceed")
async def dedline_exceed_handler(callback:CallbackQuery):
    """Собирает информацию о заявках с превышенным сроком и отправляет в чат"""
    await callback.answer("ok")   
    exceeded_claims = await get_details_of_exceeded_claims()

    text_message = 'Заявки с статусом “Превышен срок”\n'

    count_info = [(company, len(claims_info)) for company, claims_info in exceeded_claims.items() ]

    for item in count_info:
        text_message += emoji.emojize(f":double_exclamation_mark: <b>УК {item[0]}</b> {item[1]} заявки с превышенным сроком\n")
        for claim in exceeded_claims[item[0]]:
            text_message += f"ID {claim[0]} / Срок ответа: {claim[1]}\n"
        text_message += "\n\n"
    
    
    message_ids = await send_long_message_to_group(
        bot=bot,
        chat_id=GROUP_CHAT_ID,  # ID группового чата
        text=text_message,
        max_length=4096,
        delay=0.3,  # задержка 300 мс между сообщениями
        add_part_info=True  # добавляем нумерацию частей
    )
        
    await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text=text_message)



@admin_router.callback_query(lambda c: c.data == "change_status")
async def change_status_handler(callback: CallbackQuery):
    await callback.answer("ok")
    
    compare_result = await get_info_from_site_to_compare()

    finish_result = await process_and_update_claims(compare_result)

    closed_message = ''
    exceed_message = ''

    for item in finish_result['Закрыто']:
        closed_message += emoji.emojize(f":cross_mark: <b>Заявка закрыта.</b> УК {item[0]} ID {str(item[1])}\n")

    for item in finish_result['Требуется доработка']:
        exceed_message += emoji.emojize(f':warning: Статус заявки для УК {item[0]} ID {str(item[1])} <b>“Требуется доработка”\nСрок ответа исполнителя:</b> {item[3]}\n')

    if closed_message:
        closed_message_ids = await send_long_message_to_group(
        bot=bot,
        chat_id=GROUP_CHAT_ID,  # ID группового чата
        text=closed_message,
        max_length=4096,
        delay=0.3,  # задержка 300 мс между сообщениями
        add_part_info=True  # добавляем нумерацию частей
    )
        
    if exceed_message:
        exceed_message_ids = await send_long_message_to_group(
        bot=bot,
        chat_id=GROUP_CHAT_ID,  # ID группового чата
        text=exceed_message,
        max_length=4096,
        delay=0.3,  # задержка 300 мс между сообщениями
        add_part_info=True  # добавляем нумерацию частей
    )
        
        
     



