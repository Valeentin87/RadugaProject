import random
import os, sys

from dotenv import load_dotenv

from db_handler.base import get_claims_by_company_from_db
from utils.data_utils import get_details_of_exceeded_claims, get_info_from_site_to_compare, process_and_update_claims, transform_claims_by_status
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List

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



async def create_sheduler_jobs():
    logger.info(f'create_scheduler_jobs стартовал')
    # Создаем задачи запуска функции обновления данных по заведениям каждые 15 минут начиная с 4 до 5.45 утра
    scheduler.add_job(
        check_new_claims_sheduler,
        trigger="cron",
        # hour="22-23",           # часы: 22 и 23
        # minute="59,3,10,25,40",   # минуты: 55 (в 22:55), 10/25/40 (в 23:10/23:25/23:40)
        minute="0,10,20,30,40,50",          # каждые 15 минут
        hour="5-23",           # часы: 4 и 5 (т.е. с 04:00 до 05:59)
        kwargs = {
            "bot" : bot
        }
    )
    '''
    scheduler.add_job(
        dedline_exceed_sheduler,
        trigger="cron",
        # hour="22-23",           # часы: 22 и 23
        # minute="5,3,10,25,40",   # минуты: 55 (в 22:55), 10/25/40 (в 23:10/23:25/23:40)
        minute="59",          # каждые 15 минут
        hour="5-23",           # часы: 4 и 5 (т.е. с 04:00 до 05:59)
        kwargs = {
            "bot" : bot
        }
    )
    '''

    scheduler.add_job(
        change_status_sheduler,
        trigger="cron",
        # hour="22-23",           # часы: 22 и 23
        # minute="59,3,10,25,40",   # минуты: 55 (в 22:55), 10/25/40 (в 23:10/23:25/23:40)
        minute="5,15,25,35,45,55",          # каждые 15 минут
        hour="5-23",           # часы: 4 и 5 (т.е. с 04:00 до 05:59)
        kwargs = {
            "bot" : bot
        }
    )


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



async def send_to_group_shedule(bot: Bot):
    # Текст сообщения для рассылки
    text = "📢 Тестовое оповещение в группу!\n\n" \
             "Скоро мы стартуем"

    try:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode="HTML"  # для форматирования текста
        )
        
    except Exception as e:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text="❌ Ошибка отправки сообщения",
            parse_mode="HTML"  # для форматирования текста
        )



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
        text_message = ''
        if new_claims_by_company:
            for company, info in new_claims_by_company.items():
                #text_message += f"**{company.upper()}**\n"
                if info:
                    for claim_id, details in info.items():
                        text_message += emoji.emojize(f":NEW_button: <b>Новая заявка</b> для УК {company} ID {claim_id}\n:check_mark_button: Статус заявки для УК {company} ID {claim_id} - <b>В работе</b>\n<b>Тип:</b>{details.get('urgency')}\n<b>Срок ответа исполнителя:</b>{details.get('due_date')}\n\n")
            if text_message:
                await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID,text=text_message)
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text="Поиск новых заявок завершен!")
    except Exception as e:
        print(f'При получении информации о новых заявках произошла ошибка {e}')
        logger.error(f'При получении информации о новых заявках произошла ошибка {e}')
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"Произошла ошибка при поиске новых заявок: {e}")
        await callback.answer("ok")


async def check_new_claims_sheduler(bot: Bot):
    """Проверяет наличие новых заявок и принимает их в работу, а также
    добавляет в базу данных о расписанию"""
    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text="Приступили к поиску новых заявок. Подождите...")
        new_claims_by_company = await find_info_of_new_claims()
        text_message = ''
        if new_claims_by_company:
            for company, info in new_claims_by_company.items():
                #text_message += f"**{company.upper()}**\n"
                if info:
                    for claim_id, details in info.items():
                        text_message += emoji.emojize(f":NEW_button: <b>Новая заявка</b> для УК {company} ID {claim_id}\n:check_mark_button: Статус заявки для УК {company} ID {claim_id} - <b>В работе</b>\n<b>Тип:</b>{details.get('urgency')}\n<b>Срок ответа исполнителя:</b>{details.get('due_date')}\n\n")
            if text_message:
                await bot.send_message(chat_id=GROUP_CHAT_ID,text=text_message)
        await bot.send_message(chat_id=GROUP_CHAT_ID, text="Поиск новых заявок завершен!")
    except Exception as e:
        print(f'При получении информации о новых заявках произошла ошибка {e}')
        logger.error(f'При получении информации о новых заявках произошла ошибка {e}')
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=f"Произошла ошибка при поиске новых заявок: {e}")
        


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



async def dedline_exceed_sheduler(bot: Bot):
    """Собирает информацию о заявках с превышенным сроком и отправляет в чат"""
    
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
        
    await bot.send_message(chat_id=GROUP_CHAT_ID, text=text_message)


@admin_router.callback_query(lambda c: c.data == "change_status")
async def change_status_handler(callback: CallbackQuery):
    try:
        await callback.answer("ok")
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text="Приступили к проверке актуальности статусов заявок")
        
        compare_result = await get_info_from_site_to_compare()
        logger.info(f"change_status_handler: compare_result={compare_result}")
        print(f"change_status_handler: compare_result={compare_result}")
        finish_result = await process_and_update_claims(compare_result)
        logger.info(f"change_status_handler: finish_result={finish_result}")
        print(f"change_status_handler: finish_result={finish_result}")

        closed_message = ''
        exceed_message = ''
        deadline_exceeded_message = ''

        for item in finish_result['Закрыто']:
            closed_message += emoji.emojize(f":cross_mark: <b>Заявка закрыта.</b> УК {item[0]} ID {str(item[1])}\n")

        for item in finish_result['Требуется доработка']:
            exceed_message += emoji.emojize(f':warning: Статус заявки для УК {item[0]} ID {str(item[1])} <b>“Требуется доработка”\nСрок ответа исполнителя:</b> {item[3]}\n')
            
        if finish_result['Срок превышен']:
            deadline_exceeded_message = 'Заявки с статусом “Превышен срок”\n'
            for item in finish_result['Срок превышен']:
                deadline_exceeded_message += emoji.emojize(f":double_exclamation_mark: <b>УК {item[0]}</b> ID {str(item[1])}\n<b>Срок ответа</b>: {item[3]}\n")

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
            
        if deadline_exceeded_message:
            exceed_message_ids = await send_long_message_to_group(
            bot=bot,
            chat_id=GROUP_CHAT_ID,  # ID группового чата
            text=deadline_exceeded_message,
            max_length=4096,
            delay=0.3,  # задержка 300 мс между сообщениями
            add_part_info=True  # добавляем нумерацию частей
        )
        await callback.message.bot.send_message(chat_id=GROUP_CHAT_ID, text="Завершили проверку актуальности статусов заявок")
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        

async def change_status_sheduler(bot: Bot):
    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text="Приступили к проверке актуальности статусов заявок")   
               
        compare_result = await get_info_from_site_to_compare()
        logger.info(f"change_status_handler: compare_result={compare_result}")
        print(f"change_status_handler: compare_result={compare_result}")
        finish_result = await process_and_update_claims(compare_result)
        logger.info(f"change_status_handler: finish_result={finish_result}")
        print(f"change_status_handler: finish_result={finish_result}")
        closed_message = ''
        exceed_message = ''
        deadline_exceeded_message = ''

        for item in finish_result['Закрыто']:
            closed_message += emoji.emojize(f":cross_mark: <b>Заявка закрыта.</b> УК {item[0]} ID {str(item[1])}\n")

        for item in finish_result['Требуется доработка']:
            exceed_message += emoji.emojize(f':warning: Статус заявки для УК {item[0]} ID {str(item[1])} <b>“Требуется доработка”\nСрок ответа исполнителя:</b> {item[3]}\n')

        if finish_result['Срок превышен']:
            deadline_exceeded_message = 'Заявки с статусом “Превышен срок”\n'
            for item in finish_result['Срок превышен']:
                deadline_exceeded_message += emoji.emojize(f":double_exclamation_mark: <b>УК {item[0]}</b> ID {str(item[1])}\n<b>Срок ответа</b>: {item[3]}\n")
        
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
            
        if deadline_exceeded_message:
            exceed_message_ids = await send_long_message_to_group(
            bot=bot,
            chat_id=GROUP_CHAT_ID,  # ID группового чата
            text=deadline_exceeded_message,
            max_length=4096,
            delay=0.3,  # задержка 300 мс между сообщениями
            add_part_info=True  # добавляем нумерацию частей
        )
            
        await bot.send_message(chat_id=GROUP_CHAT_ID, text="Проверка актуальности статусов заявок завершена")
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}")
        
        
     
