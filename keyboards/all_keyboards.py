from copy import deepcopy
from datetime import datetime, timedelta
import calendar
from typing import List, Optional, Tuple
import emoji
from decouple import config
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from create_bot import logger
from data.metro_data import metro_map, stations_by_rayon, dictionary_areas, dictionary_of_correspondences
from db_handler.base import get_info_of_establishments
from utils.save_read_csv import save_statistic_to_csv



def get_monthly_calendar(year: int, month: int) -> list:
    """
    Возвращает календарь заданного месяца в виде списка списков:
    - [0] — сокращённые названия дней недели;
    - [1:] — недели, каждая из 7 элементов: (число, название_дня) или "пусто".
    """
    days_of_week_full = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    days_of_week_short = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

    first_weekday, num_days = calendar.monthrange(year, month)

    calendar_grid = [days_of_week_short]  # 0-й элемент — дни недели (сокращённо)

    current_day = 1
    while current_day <= num_days:
        week = []
        for weekday_idx in range(7):
            if current_day > num_days:
                week.append("пусто")
            else:
                if len(calendar_grid) == 1 and weekday_idx < first_weekday:
                    week.append("пусто")
                else:
                    day_name = days_of_week_full[weekday_idx]
                    week.append((current_day, day_name))
                    current_day += 1
        calendar_grid.append(week)

    return calendar_grid


def finish_kb():
    """Финальная клавиатура после завершения процесса поиска заведения"""
    builder = InlineKeyboardBuilder()

    builder.button(text=emoji.emojize(':magnifying_glass_tilted_right: Начать новый подбор'), callback_data='start_search')
    builder.button(text=emoji.emojize(':white_question_mark: Обратная связь'), callback_data='feedback')
    builder.button(text=emoji.emojize(':ZZZ: Завершить подбор'), callback_data='to_start')
    builder.adjust(1)

    return builder.as_markup()


def change_edit_top_info_kb():
    """Inline клавиатура для редактирования информации о ТОПЕ заведений"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text=emoji.emojize('1'), callback_data=f'edit_top:1'),
        InlineKeyboardButton(text=emoji.emojize('2'), callback_data='edit_top:2'),
        InlineKeyboardButton(text=emoji.emojize('3'), callback_data=f'edit_top:3')
    )

    builder.row(InlineKeyboardButton(text=emoji.emojize(':BACK_arrow: Назад'), callback_data='go_to_admin_kb'))
    

    return builder.as_markup()


def generate_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру для заданного месяца и года.
    """
    try:
        cal = get_monthly_calendar(year, month)

        # Название месяца на русском
        month_names = [
            "январь", "февраль", "март", "апрель", "май", "июнь",
            "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"
        ]
        month_name = month_names[month - 1].capitalize()

        buttons = []

        # Строка 1: заголовок (месяц и год) — одна кнопка на всю ширину
        buttons.append([
            InlineKeyboardButton(
                text=f"{month_name} {year}",
                callback_data="ignore"
            )
        ])

        # Строка 2: дни недели (некликабельные)
        day_row = []
        for day_short in cal[0]:
            day_row.append(
                InlineKeyboardButton(text=day_short, callback_data="ignore")
            )
        buttons.append(day_row)

        # Строки с датами (недели)
        for week in cal[1:]:
            date_row = []
            for cell in week:
                if cell == "пусто":
                    date_row.append(
                        InlineKeyboardButton(text=" ", callback_data="ignore")
                    )
                else:
                    day_num, day_name = cell
                    cb_data = f"select:{day_num}-{month_name.lower()}-{year}-{day_name.lower()}"
                    date_row.append(
                        InlineKeyboardButton(text=str(day_num), callback_data=cb_data)
                    )
            buttons.append(date_row)

        # Последние две кнопки: навигация
        nav_row = [
            InlineKeyboardButton(text=emoji.emojize(":last_track_button: пред. месяц"), callback_data="prev_month"),
            InlineKeyboardButton(text=emoji.emojize("след. месяц :next_track_button:"), callback_data="next_month")
        ]
        buttons.append(nav_row)
        buttons.append([InlineKeyboardButton(text=emoji.emojize(':BACK_arrow: Назад'), callback_data='back_change-day')])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    except Exception as e:
        print(f"Ошибка при генерации клавиатуры: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[])  # пустая клавиатура


# Функция для создания списка часов
def get_hours_list(start_hour: int) -> List[str]:
    hours = []
    current_hour = start_hour
    
    # Генерируем часы до полуночи
    while current_hour < 24:
        hours.append(f"{current_hour:02d}:00")
        current_hour += 1
    
    # Добавляем часы следующего дня до 00:00
    for hour in range(0, 3):
        hours.append(f"{hour:02d}:00")
    
    return hours




def create_time_keyboard(start_hour: int) -> InlineKeyboardMarkup:
    

    builder = InlineKeyboardBuilder()

    hours = get_hours_list(start_hour)
    
    # Создаем кнопки для каждого часа
    for hour in hours:
        builder.button(
            text=hour,
            callback_data=f"time_select:{hour}"
        )        

    builder.adjust(3) 
    builder.row(InlineKeyboardButton(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_time-kb'))
    
    return builder.as_markup()



def raiting_keyboard(rating_value:float=4.8, finish_flag:bool=False) -> InlineKeyboardMarkup:
   
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text=emoji.emojize(':plus:'), callback_data=f'rating_value:{rating_value}_plus'),
        InlineKeyboardButton(text=str(rating_value), callback_data='rating'),
        InlineKeyboardButton(text=emoji.emojize(':minus:'), callback_data=f'rating_value:{rating_value}_minus')
    )

    builder.row(InlineKeyboardButton(text='Не важен', callback_data='back_without-rating'))
    if not finish_flag:
        builder.row(InlineKeyboardButton(text='ПОДТВЕРДИТЬ', callback_data='confirm_rating-value'))
    else:
        builder.row(InlineKeyboardButton(text='ПОДТВЕРДИТЬ', callback_data='confirm-finish::edit_rating'))
    
    return builder.as_markup()


def start_keyboard():
    """Стартовое меню бота"""
       
    builder = InlineKeyboardBuilder()

    
    builder.button(text=emoji.emojize(':magnifying_glass_tilted_right: Начало подбора'), callback_data='start_search')
    builder.button(text=emoji.emojize(':glowing_star: ТОП-3'), callback_data='top3')
    builder.button(text=emoji.emojize(':information: О боте'), callback_data='about_bot')
    # builder.button(text=emoji.emojize(':light_bulb: Ценность бота'), callback_data='value_of_the_bot')
    # builder.button(text=emoji.emojize(':dizzy: Быстрый поиск'), callback_data='quick_search')
    builder.adjust(1)

    return builder.as_markup()


def about_bot_keyboard():
    """Клавиатура для раздела 'О боте'"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text=emoji.emojize(':open_book: Инструкция'), callback_data='how_to_use::start_menu')
    builder.button(text=emoji.emojize(':money_bag: Тарифы'), callback_data='tariffs')
    builder.button(text=emoji.emojize(':white_question_mark: Обратная связь'), callback_data='feedback')
    builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to_start')
    builder.adjust(2)
    
    return builder.as_markup() 



def instruction_kb(message_index:int=0, start_flag=True, end_flag=False):
    """Клавиатура для перелистывания сообщений в инструкции"""
    builder = InlineKeyboardBuilder()
    
    if not start_flag:
        builder.button(text=emoji.emojize('Пред.:left_arrow:'), callback_data='instruction_prev_message')
    if not end_flag:
        builder.button(text=emoji.emojize('След.:right_arrow:'), callback_data='instruction_next_message')
    builder.button(text=emoji.emojize('Скрыть'), callback_data='instruction_hide')

    return builder.as_markup()


def back_keyboard():
    """Клавиатура для быстрого поиска"""
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to_start')
    
    return builder.as_markup()


def alert_kb():
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize('Ok'), callback_data='alert_ok')],
         [InlineKeyboardButton(text=emoji.emojize(':BACK_arrow:Назад'), callback_data='alert_back')]]
    )


def writer_kb():
    return InlineKeyboardMarkup(inline_keyboard=
        [[InlineKeyboardButton(text=emoji.emojize(':keyboard:Текст запроса'), callback_data='writer_text')],
         [InlineKeyboardButton(text=emoji.emojize(':BACK_arrow:Назад'), callback_data='alert_back')]]
    )


def change_search_variant_kb():
    """Клавиатура для выбора варианта поиска заведения"""
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji.emojize(':bullseye:ЧЁТКО ЗНАЮ, ЧЕГО ХОЧУ'), callback_data='variant_1')
    builder.button(text=emoji.emojize(':magnifying_glass_tilted_left:ПОМОГИТЕ ПОДОБРАТЬ'), callback_data='variant_2')
    
    builder.adjust(1)
    return builder.as_markup()


def feedback_keyboard():
    """Клавиатура для обратной связи с администратором"""
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji.emojize('Связаться с админом :incoming_envelope:'), callback_data='feedback_admin')
    builder.button(text=emoji.emojize('Пожаловаться :performing_arts:'), callback_data='feedback_claim')
    builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to_start')

    builder.adjust(1)
    
    return builder.as_markup()



def child_menu_keyboard():
    """Клавиатура для выбора наличия детского меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji.emojize(':plus: Да, обязательно'), callback_data='child_yes')
    builder.button(text=emoji.emojize(':minus: Нет, не обязательно'), callback_data='child_no')
    
    return builder.as_markup()


def show_tariffs_kb(tariffs_info:dict):
    """Клавиатура для демонстрации видов тарифов подписки"""
    builder = InlineKeyboardBuilder()
    
    for key, value in tariffs_info.items():
        if key != 'Бесплатный':
            builder.button(text=key, callback_data=f"tariffs:{value[0]}")    
    
    builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to_start')   
    builder.adjust(1)

    return builder.as_markup()



def date_keyboard(finish_flag=False, param:str=None):
    """Клавиатура для выбора даты посещения"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text='Сегодня', callback_data='date_today')
    builder.button(text='Завтра', callback_data='date_tomorrow')
    builder.button(text=emoji.emojize(':calendar: В другой день'), callback_data='date_select-date')
    if not finish_flag:
        builder.button(text=emoji.emojize(':BACK_arrow: Назад'), callback_data='back_to-changed-variants')
    else:
        builder.button(text=emoji.emojize('ПОДТВЕРДИТЬ :OK_button:'), callback_data=f'confirm-finish::{param}')
    builder.adjust(1)

    return builder.as_markup()


def time_keyboard(flag_day:str=''):
    """Клавиатура для выбора времени посещения"""
    builder = InlineKeyboardBuilder()
    if flag_day == 'today':
        builder.button(text=emoji.emojize(':infinity: В ближайшее время (до 1 часа)'), callback_data='time_now')
        builder.button(text='В течение 1-3 ч. с текущего времени', callback_data='time_two-hour-ago')
    # builder.button(text='В течение 2-3 часов', callback_data='time_three-hour-ago')
    builder.button(text=emoji.emojize(':six-thirty: Указать время'), callback_data='time_change-hour')
    builder.button(text=emoji.emojize(':BACK_arrow: Назад'), callback_data='go_to-step2')
    
    builder.adjust(1)
    
    return builder.as_markup()


def change_time_keyboard(time_flag:str):
    """Клавиатура для выбора времени посещения, в качестве аргумента передается time_flag"""
    builder = InlineKeyboardBuilder()
    
    if time_flag == 'today':
        builder.button(text='Сегодня', callback_data='time_now')
    elif time_flag == 'tomorrow':
        builder.button(text='Завтра', callback_data='time_two-hour-ago')
    
    
    return builder.as_markup()



def start_stations_interface_kb(input_stations:list, selected_stations:list, finish_flag:bool=False):
    '''Демонстрирует стартовую клавиатуру для работы с выбором станции метро'''
    logger.info(f'start_stations_interface_kb: {finish_flag=}')
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji.emojize(':check_mark_button: ') + 'Станции указаны' + emoji.emojize(':check_mark_button: ') if input_stations else 'Написать станции', callback_data='input_station')
    builder.button(text=emoji.emojize(':check_mark_button: ') + 'Станции выбраны(изменить)' + emoji.emojize(':check_mark_button: ') if selected_stations else 'Выбрать из списка', callback_data='demo_station_lines')
    if not finish_flag:
        builder.button(text='ПОДТВЕРДИТЬ', callback_data='confirm_station')
        builder.button(text='НАЗАД', callback_data='back_to')
    else:
        builder.button(text='ПОДТВЕРДИТЬ', callback_data='confirm-finish::all_stations_str')

    builder.adjust(1)
    return builder.as_markup()


def finish_search_kb():
    """Клавиатура для завершающего подтверждения критериев поиска"""
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji.emojize('Внести изменения :pencil:'), callback_data='finish_edit-params')
    builder.button(text=emoji.emojize('Подтвердить выбор и начать поиск :magnifying_glass_tilted_right:'), callback_data='confirm-finish::check_subscribe')

    builder.adjust(1)

    return builder.as_markup()




def metro_keyboard_lines(selected_lines:list[str], finish_flag:bool=False):
    '''Демонстрирует ветки линий метро Московского метрополитена'''
    logger.info(f'metro_keyboard_lines: {finish_flag=}')
    selected_lines_split = [line[:-6] for line in selected_lines]
    logger.info(f'metro_keyboard_lines: {selected_lines_split=}')
    builder = InlineKeyboardBuilder()
    for line in list(metro_map.keys()):
        # logger.info(f'{line=}')
        builder.button(text=emoji.emojize(':check_mark_button: ') + f'{line[:-6]}' + emoji.emojize(':check_mark_button: ') if line[:-6] in selected_lines_split else f'{line[:-6]}', callback_data=f'line_{line[:-6]}')
    builder.adjust(1)
    
    if not selected_lines:
        if not finish_flag:
            logger.info(f'metro_keyboard_lines, finish_flag = False')
            builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to-rayons')
        else:
            logger.info(f'metro_keyboard_lines, finish_flag = True')
            builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='finish_edit-params')
    else:
        if not finish_flag:
            logger.info(f'metro_keyboard_lines, finish_flag = False')
            builder.row(
                InlineKeyboardButton(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to-rayons'),
                InlineKeyboardButton(text=emoji.emojize('ПОДТВЕРДИТЬ :fast-forward_button:'), callback_data='confirm_station')
            )
        else:
            logger.info(f'metro_keyboard_lines, finish_flag = True')
            builder.row(
                InlineKeyboardButton(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='finish_edit-params'),
                InlineKeyboardButton(text=emoji.emojize('ПОДТВЕРДИТЬ :fast-forward_button:'), callback_data='confirm-finish::all_stations_str')
            )
   
    return builder.as_markup()


# Клавиатуры для районов

def csao_keyboard(state_user_data:dict):
    """Клавиатура для районов ЦАО"""
    finish_flag = state_user_data.get('finish_flag')
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'ЦАО'][0]
        logger.info(f'csao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    csao_areas = [
        'Арбат', 'Басманный', 'Замоскворечье', 'Красносельский',
        'Мещанский', 'Пресненский', 'Таганский', 'Тверской',
        'Хамовники', 'Якиманка'
    ]
    for area in csao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')
    
    builder.adjust(1)
    if not finish_flag:
        builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::csao'))
        builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-csao'))
    else:
        builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm-finish::selected_district_str'))        
    return builder.as_markup()



def sao_keyboard(state_user_data:dict):
    """Клавиатура для районов CАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'САО'][0]
        logger.info(f'sao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    sao_areas = ['Аэропорт', 'Беговой', 'Бескудниковский', 'Войковский', 'Восточное Дегунино',
                  'Головинский', 'Дмитровский', 'Западное Дегунино', 'Коптево', 'Левобережный', 
                  'Молжаниновский', 'Савеловский', 'Сокол', 'Тимирязевский', 'Ховрино', 'Хорошевский', "Яхромская", "Окружная"]
    for area in sao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')
    
    builder.adjust(1)

    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::sao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-sao'))
   
    return builder.as_markup()



def svao_keyboard(state_user_data:dict):
    """Клавиатура для районов CВАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'СВАО'][0]
        logger.info(f'svao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    svao_areas = [
        'Алексеевский', 'Алтуфьевский', 'Бабушкинский', 'Бибирево', 'Бутырский', 'Лианозово',
                   'Лосиноостровский', 'Марфино', 'Марьина Роща', 'Останкинский', 'Отрадное',
                     'Ростокино', 'Свиблово', 'Северное Медведково', 'Северный', 'Южное Медведково',
                       'Ярославский', "Марьина Роща", "Савёловская", "Окружная"
    ]
    for area in svao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')
    
    builder.adjust(1)

    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::svao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-svao'))
   
    return builder.as_markup()



def vao_keyboard(state_user_data:dict):
    """Клавиатура для районов ВАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'ВАО'][0]
        logger.info(f'vao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    vao_areas = [
        'Богородское', 'Вешняки', 'Восточное Измайлово', 'Восточный', 'Гольяново',
                  'Ивановское', 'Измайлово', 'Косино-Ухтомский', 'Метрогородок', 'Новогиреево',
                    'Новокосино', 'Перово', 'Преображенское', 'Северное Измайлово', 'Соколиная гора',
                      'Сокольники', "Локомотив", "Семёновская", "Партизанская", "Щёлковская"
    ]
    for area in vao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::vao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-vao'))
   
    return builder.as_markup()



def yvao_keyboard(state_user_data:dict):
    """Клавиатура для районов ЮВАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'ЮВАО'][0]
        logger.info(f'yvao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    yvao_areas = [
        'Жулебино', 'Капотня', 'Кузьминки', 'Лефортово', 'Люблино',
                   'Марьино', 'Некрасовка', 'Нижегородский', 'Печатники', 'Рязанский',
                     'Текстильщики', 'Южнопортовый', "Новохохловская", "Стахановская"
    ]
    for area in yvao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::yvao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-yvao'))
   
    return builder.as_markup()



def yao_keyboard(state_user_data:dict):
    """Клавиатура для районов ЮАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'ЮАО'][0]
        logger.info(f'yao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    yao_areas = [
        'Братеево', 'Бирюлёво Восточное', 'Даниловский', 'Донской', 'Бирюлёво Западное',
                  'Зябликово', 'Москворечье-Сабурово', 'Нагатино-Садовники', 'Нагатинский затон', 
                  'Нагорный', 'Орехово-Борисово Северное', 'Чертаново Северное', 'Царицыно', 
                  'Чертаново Центральное', 'Южное Орехово-Борисово', 'Южное Чертаново', "ЗИЛ",
                  "Кленовый бульвар"
    ]
    for area in yao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')
    
    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::yao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-yao'))
   
    return builder.as_markup()



def yzao_keyboard(state_user_data:dict):
    """Клавиатура для районов ЮЗАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'ЮЗАО'][0]
        logger.info(f'yzao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    yzao_areas = [
        'Академический', 'Гагаринский', 'Зюзино', 'Коньково', 'Котловка',
                   'Ломоносовский', 'Обручевский', 'Северное Бутово', 'Тёплый Стан', 
                   'Черёмушки', 'Южное Бутово', 'Ясенево', "Вавиловская", "Тропарёво",
                   "Университет Дружбы Народов", "Улица Горчакова", "Коммунарка", "Новаторская",
                   "Генерала Тюленева", "Площадь Гагарина", "Бульвар Адмирала Ушакова", "Новоясеневская"
    ]
    for area in yzao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::yzao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-yzao'))
   
    return builder.as_markup()



def zao_keyboard(state_user_data:dict):
    """Клавиатура для районов ЗАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'ЗАО'][0]
        logger.info(f'zao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    zao_areas = [
        'Внуково', 'Дорогомилово', 'Крылатское', 'Кунцево', 'Можайский', 
                 'Ново-Переделкино', 'Очаково-Матвеевское', 'Проспект Вернадского',
                  'Раменки', 'Солнцево', 'Тропарёво-Никулино', 'Филёвский парк', 
                  'Фили-Давыдково', "Тропарёво", "Говорово", "Славянский бульвар", "Давыдково"
    ]
    for area in zao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::zao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-zao'))
   
    return builder.as_markup()



def szao_keyboard(state_user_data:dict):
    """Клавиатура для районов CЗАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'СЗАО'][0]
        logger.info(f'szao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    szao_areas = [
        'Куркино', 'Митино', 'Покровское-Стрешнево', 'Строгино', 'Северное Тушино',
                   'Южное Тушино', 'Хорошёво-Мневники', 'Щукино'
    ]
    for area in szao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::szao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-szao'))
   
    return builder.as_markup()



def sao_keyboard(state_user_data:dict):
    """Клавиатура для районов САО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'САО'][0]
        logger.info(f'sao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    sao_areas = [
        'Аэропорт', 'Беговой', 'Бескудниковский', 'Войковский', 'Восточное Дегунино',
                  'Головинский', 'Дмитровский', 'Западное Дегунино', 'Коптево', 'Левобережный', 
                  'Молжаниновский', 'Савеловский', 'Сокол', 'Тимирязевский', 'Ховрино', 'Хорошевский', "Яхромская", "Окружная"
    ]
    for area in sao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::sao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-sao'))
   
    return builder.as_markup()



def nao_keyboard(state_user_data:dict):
    """Клавиатура для районов НАО"""
    selected_district = state_user_data.get('selected_district')
    check_areas = []
    if selected_district:
        check_areas = [list(area.values())[0] for area in selected_district if list(area.keys())[0] == 'НАО'][0]
        logger.info(f'sao_keyboard: {check_areas=}')
    builder = InlineKeyboardBuilder()
    nao_areas = [
        "Внуково", "Коммунарка", "Филимоновский", "Щербинка"
    ]
    for area in nao_areas:
        builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button: ') if area in check_areas else area, callback_data=f'area_{area}')

    builder.adjust(1)
    
    builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data='all_rayons::nao'))
    builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_areas'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-nao'))
   
    return builder.as_markup()



async def areas_keyboard(rayon:str, state:FSMContext, call:CallbackQuery):
    """Клавиатура для формирования кнопок с названиями подрайнов"""
    builder = InlineKeyboardBuilder()
    logger.info(f'areas_keyboard: {rayon=}')
    state_data:dict = await state.get_value(f'{call.from_user.id}')
    finish_flag = state_data.get('finish_flag')
    push_district = state_data.get('push_district')
    push_district = [key for key, value in dictionary_of_correspondences.items() if value == push_district ][0]

    # selected_areas = state_data.get('selected_areas')

    selected_areas:list = state_data.get('selected_district')
    logger.info(f'areas_keyboard: {selected_areas=}')
    all_areas = [list(item.values())[0] for item in selected_areas]
    logger.info(f'areas_keyboard: {all_areas=}')
    flat_areas = [area for sublist in all_areas for area in sublist]
    logger.info(f'areas_keyboard: {flat_areas=}')
    
    areas_of_rayon = dictionary_areas[rayon]
    
    logger.info(f'areas_keyboard: {areas_of_rayon=}')
    
    for area in areas_of_rayon:
        # if area in selected_areas:
        if area in flat_areas:
            builder.button(text=emoji.emojize(':check_mark_button: ') + area + emoji.emojize(' :check_mark_button:'), callback_data=f'area_{area}')
        else:
            builder.button(text=area, callback_data=f'area_{area}')
    
    builder.adjust(1)
    
    if not finish_flag:
        builder.row(InlineKeyboardButton(text=emoji.emojize(':recycling_symbol: Все районы'), callback_data=f'all_rayons::{push_district}'))
        builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_action'),        
                InlineKeyboardButton(text=emoji.emojize('Выбрать метро :station:'), callback_data='select_metro-csao'))
    else:
        builder.row(InlineKeyboardButton(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_action'))        

    return builder.as_markup()


async def main_search_keyboard(state: FSMContext, call:CallbackQuery):
    """Клавиатура для основного поиска"""
    
    state_user_data:dict = await state.get_value(f'{call.from_user.id}')
    logger.info(f'main_search_keyboard: {state_user_data=}')
    change_location = any([state_user_data.get('location_stations'), state_user_data.get('location_rayon')])
    price_levels = state_user_data.get('price_levels')
    categoryes = state_user_data.get('categoryes')

    check_list = [item for item in ['change_location', 'price_levels', 'view_option', 'selected_types'] if item in state_user_data]
    key_list = ['work_schedule', 'rating_value', 'children_menu', 'panoramic_view']

    builder = InlineKeyboardBuilder()
    
    builder.button(text=emoji.emojize(':check_mark_button: ') + emoji.emojize(':post_office: Тип заведения') + emoji.emojize(' :check_mark_button:') if ('selected_types' in state_user_data and len(state_user_data.get('selected_types'))) else emoji.emojize(':post_office: Тип заведения'), callback_data='select_type')
    # builder.button(text=emoji.emojize(':check_mark_button: ') + emoji.emojize(':sunset: Панорамный вид') + emoji.emojize(' :check_mark_button:') if ('view_option' in state_user_data and state_user_data.get('view_option') == 'yes') else emoji.emojize(':sunset: Панорамный вид'), callback_data='select_view')
    builder.button(text=emoji.emojize(':check_mark_button: ') + emoji.emojize(':flag_in_hole: Местоположение') + emoji.emojize(' :check_mark_button:') if change_location else emoji.emojize(':flag_in_hole: Местоположение'), callback_data='select_location')
    if categoryes:
        builder.button(text=emoji.emojize(':check_mark_button: ') + emoji.emojize(':money_bag: Уровень цен/Указать меню') + emoji.emojize(' :check_mark_button:') if price_levels or [cat for cat, value in categoryes.items() if value]  else emoji.emojize(':money_bag: Уровень цен/Указать меню'), callback_data='select_price')
    else:
        builder.button(text=emoji.emojize(':check_mark_button: ') + emoji.emojize(':money_bag: Уровень цен/Указать меню') + emoji.emojize(' :check_mark_button:') if price_levels else emoji.emojize(':money_bag: Уровень цен/Указать меню'), callback_data='select_price')
    builder.button(text=emoji.emojize(':check_mark_button: ') + 'Другое (указано)' + emoji.emojize(' :check_mark_button:') if [key for key in key_list if key in state_user_data] else 'Другое (указать)', callback_data='custom_criteria')
    if check_list:
        builder.button(text=emoji.emojize('ПОДТВЕРДИТЬ :next_track_button:'), callback_data='go_to-step2')      
    builder.button(text=emoji.emojize(':open_book: Как пользоваться'), callback_data='how_to_use::variant2')
    builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='start_search')
    
    builder.adjust(1)
    return builder.as_markup()



async def work_schedule_week_days_kb(state_user_data:dict, call:CallbackQuery, state:FSMContext, finish_flag:bool=False):
    """Клавиатура для выбора рабочих дней заведения"""
    week_days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']            
    work_schedule = {}
    work_days = []
    if 'work_schedule' in state_user_data:
        work_schedule:dict = state_user_data['work_schedule']
        work_schedule.setdefault('work_days', [])
        work_days = work_schedule.get('work_days')
    state_user_data['work_schedule'] = work_schedule


    builder = InlineKeyboardBuilder()
    [builder.button(text=emoji.emojize(':check_mark_button: ') + day + emoji.emojize(' :check_mark_button:') if day in work_days else day, callback_data=f'work-schedule:day_{day}') 
    for day in week_days]
    builder.button(text=emoji.emojize(':watch: Время работы'), callback_data='work-schedule:change-times')
    if not finish_flag:
        builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_work-schedule')
        builder.button(text=emoji.emojize(':BACK_arrow: Назад'), callback_data='back_work-schedule')
    else:
        builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm-finish::edit_work-days')

    builder.adjust(1)

    
    logger.info(f'work_schedule_week_days_kb: {state_user_data=}')
    await state.update_data({f'{call.from_user.id}': state_user_data})

    return builder.as_markup()


async def work_schedule_work_times_kb(state_user_data:dict, call:CallbackQuery, state:FSMContext, finish_flag:bool=False):
    """Клавиатура для выбора рабочего времени для заведения"""
    all_work_times:list = ['до 9 утра', 'после 22 вечера', 'после полуночи']
    work_schedule = {}
    work_times = []
    if 'work_schedule' in state_user_data:
        work_schedule:dict = state_user_data['work_schedule']
        work_schedule.setdefault('work_times', [])
        work_times = work_schedule.get('work_times')
    state_user_data['work_schedule'] = work_schedule

    builder = InlineKeyboardBuilder()
    [builder.button(text=emoji.emojize(':check_mark_button: ') + time + emoji.emojize(' :check_mark_button:') if time in work_times else time, callback_data=f'work-schedule:time_{time}') 
    for time in all_work_times]
    builder.button(text=emoji.emojize(':BACK_arrow: Назад'), callback_data='back_work-days')


    builder.adjust(1)

    
    logger.info(f'work_schedule_work_times_kb: {state_user_data=}')
    await state.update_data({f'{call.from_user.id}': state_user_data})

    return builder.as_markup()





def custom_criteria_kb(state_user_data:dict):
    """Клавиатура для выбора дооплнительных критериев поиска заведения"""
    rating_value = state_user_data.get('rating_value')
    work_schedule = state_user_data.get('work-schedule')
    children_menu = state_user_data.get('children_menu')
    panoramic_view = state_user_data.get('panoramic_view')

    keyboard = [
        [InlineKeyboardButton(text = emoji.emojize(':check_mark_button: ') + "Рейтинг" + emoji.emojize(' :check_mark_button:')
                              if rating_value else "Рейтинг", callback_data='custom:rating')],
        [InlineKeyboardButton(text = emoji.emojize(':check_mark_button: ') + "Режим работы" + emoji.emojize(' :check_mark_button:')
                              if work_schedule else "Режим работы", callback_data='custom:work-schedule')],
        [InlineKeyboardButton(text = emoji.emojize(':check_mark_button: ') + "Детское меню" + emoji.emojize(' :check_mark_button:')
                              if children_menu else "Детское меню", callback_data='custom:children-menu')],
        [InlineKeyboardButton(text = emoji.emojize(':check_mark_button: ') + "Панорамный вид" + emoji.emojize(' :check_mark_button:')
                              if panoramic_view else "Панорамный вид", callback_data='custom:panoramic-view')],
        [InlineKeyboardButton(text = "ПОДТВЕРДИТЬ", callback_data='confirm_custom-criteria')],
        [InlineKeyboardButton(text = "Назад", callback_data='back_custom')]
        
    ]

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    return markup


async def type_location_kb(state: FSMContext, call:CallbackQuery):
    """Клавиатура для выбора типа выбора местоположения"""
    builder = InlineKeyboardBuilder()
    state_user_data:dict = await state.get_value(f'{call.from_user.id}')

    check_list = [item for item in ['location_rayon', 'location_stations'] if item in state_user_data]
    
    builder.button(text=emoji.emojize(':check_mark_button: ') + 'По районам' + emoji.emojize(' :check_mark_button:') if ('location_rayon' in state_user_data) else 'По районам', callback_data='location_rayon')
    builder.button(text=emoji.emojize(':check_mark_button: ') + 'По станциям метро' + emoji.emojize(' :check_mark_button:') if ('location_stations' in state_user_data) else 'По станциям метро', callback_data='location_stations')

    if check_list:
        builder.button(text=emoji.emojize('ПОДТВЕРДИТЬ :next_track_button:'), callback_data='confirm_type-location')      

    builder.adjust(1)
    return builder.as_markup()



def admin_establs_type_keyboard():
    """Клавиатура для выбора типа заведения при поиске в режиме администратора"""
    builder = InlineKeyboardBuilder()
    types = [
        emoji.emojize(':fondue: Ресторан'), emoji.emojize(':green_salad: Кафе'), emoji.emojize(':curry_rice: Столовая'), emoji.emojize(':piñata: Кальян-бар'), emoji.emojize(':hot_beverage: Кофейня')
    ]
    for t in types:
        builder.button(text=t, callback_data=f'type-admin_{t.split(' ')[1]}')
    builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='establs::back')
    builder.adjust(1)

    return builder.as_markup()



async def establishment_type_keyboard(state: FSMContext, call:CallbackQuery, finish_flag:bool=False):
    """Клавиатура для выбора типа заведения"""
    
    builder = InlineKeyboardBuilder()
    state_user_data:dict = await state.get_value(f'{call.from_user.id}')
    selected_types = state_user_data.get('selected_types')
    types = [
        emoji.emojize(':fondue: Ресторан'), emoji.emojize(':green_salad: Кафе'), emoji.emojize(':curry_rice: Столовая'), emoji.emojize(':piñata: Кальян-бар'), emoji.emojize(':hot_beverage: Кофейня')
    ]
    if selected_types:
        for t in types:
            builder.button(text=emoji.emojize(':check_mark_button: ') + t + emoji.emojize(' :check_mark_button:') if t.split(' ')[1] in selected_types else t, callback_data=f'type_{t.split(' ')[1]}')
        if not finish_flag:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_types')
        else:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm-finish::types_establishment')
    else:
        for t in types:
            builder.button(text=t, callback_data=f'type_{t.split(' ')[1]}')
        
        if not finish_flag:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm_types')
        else:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm-finish::types_establishment')
    if not finish_flag:
        # builder.button(text=emoji.emojize(':check_mark_button: ') + 'Другое (указано)' + emoji.emojize(' :check_mark_button:') if ('another_types' in state_user_data) else 'Другое (указать)', callback_data='another_types')
        builder.button(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to_search')
    
    builder.adjust(1)
    
    return builder.as_markup()





async def location_keyboard(state:FSMContext, call:CallbackQuery, finish_flag=False):
    """Клавиатура для выбора района"""
    
    state_user_data:dict = await state.get_value(f'{call.from_user.id}')
    without_rayon = state_user_data.get('without_rayon')
    
    builder = InlineKeyboardBuilder()
    districts = [
        'ЦАО', 'САО', 'СВАО', 'ВАО', 'ЮВАО',
        'ЮАО', 'ЮЗАО', 'ЗАО', 'СЗАО', 'НАО', 'район не важен'
    ]

    selected_district:list = []
    if 'selected_district' in state_user_data:
        selected_district = state_user_data.get('selected_district')
        if not isinstance(selected_district, list):
            selected_district = [selected_district]

    if not without_rayon:
        for d in districts:
            builder.button(text=emoji.emojize(':check_mark_button: ') + d + emoji.emojize(' :check_mark_button:') if d in [list(item.items())[0][0] for item in selected_district if list(item.items())[0][1]] else d, callback_data=f'district_{d}')
    else:
        if not finish_flag:
            builder.button(text=emoji.emojize('Продолжить :fast-forward_button:'), callback_data='back_action')
    
    builder.adjust(2)
    if not finish_flag:
        builder.row(InlineKeyboardButton(text=emoji.emojize('По станциям метро :station:'), callback_data='select_station'))
    if selected_district:
            if not finish_flag:
                builder.row(InlineKeyboardButton(text=emoji.emojize('ПОДТВЕРДИТЬ :OK_button:'), callback_data='confirm_location'))
            else:
                builder.row(InlineKeyboardButton(text=emoji.emojize('ПОДТВЕРДИТЬ :OK_button:'), callback_data='confirm-finish::selected_district_str'))
    if not finish_flag:
        builder.row(InlineKeyboardButton(text=emoji.emojize('Назад :BACK_arrow:'), callback_data='back_to_search'))
    return builder.as_markup()


def view_keyboard():
    """Клавиатура для выбора панорамного вида"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text=emoji.emojize(':plus: Важен'), callback_data='view_yes')
    builder.button(text=emoji.emojize(':minus: Не важен'), callback_data='view_no')
    
    builder.adjust(2)
    
    return builder.as_markup()


def change_category_menu_kb():
    """Клавиатура для выбора категории блюда"""
    builder = InlineKeyboardBuilder()

    categoryes = {
        emoji.emojize(":green_salad: Закуски"): "snacks",
        emoji.emojize(":pot_of_food: Основные блюда"): "main-courses",
        emoji.emojize(":shortcake: Десерты"): "desserts",
        emoji.emojize(":cup_with_straw: Напитки"): "drinks",
        emoji.emojize(":popcorn: Детское меню"): "сhildren-menu",
        emoji.emojize(":thought_balloon: Кальян"): "hookah",
        emoji.emojize(":BACK_arrow: Назад"): "without-rating"
    }

    for key, value in categoryes.items():
        builder.button(text=key, callback_data=f'category_{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()


def change_snacks_kb():
    """Клавиатура для выбора закусок"""
    builder = InlineKeyboardBuilder()

    snacks = {
        emoji.emojize(":steaming_bowl: Горячие закуски"): "Горячие закуски", #hot_snacks",
        emoji.emojize(":oden: Холодные закуски"): "Холодные закуски", #"cold_snacks",
        emoji.emojize(":cheese_wedge: Сыры и антипасто"):  "Сыры и антипасто",#"cheese",
        emoji.emojize(":green_salad: Салаты"): "Салаты",  #"salads",
        emoji.emojize(":pencil: Другое (указать)"): "Закуски",
        emoji.emojize(":BACK_arrow: Назад"): "to-category"
    }

    for key, value in snacks.items():
        builder.button(text=key, callback_data=f'snacks::{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()


def change_main_courses_kb():
    """Клавиатура для выбора основных блюд"""
    builder = InlineKeyboardBuilder()

    main_courses = {
        emoji.emojize(":shallow_pan_of_food: Первые блюда"): "Первые блюда", #"first-courses",
        emoji.emojize(":steaming_bowl: Вторые блюда"): "Вторые блюда", #"second-courses",
        emoji.emojize(":meat_on_bone: Мясные блюда"): "Мясные блюда", #"meat-dishes",
        emoji.emojize(":fried_shrimp: Рыбные блюда"): "Рыбные блюда", #"fish-dishes",
        emoji.emojize(":pencil: Другое (указать)"): "Основные блюда",
        emoji.emojize(":BACK_arrow: Назад"): "to-category"
    }

    for key, value in main_courses.items():
        builder.button(text=key, callback_data=f'main-courses::{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()


def change_desserts_kb():
    """Клавиатура для выбора десертов"""
    builder = InlineKeyboardBuilder()

    desserts = {
        emoji.emojize(":pancakes: Выпечка"): "Выпечка", #"bakery-products",
        emoji.emojize(":soft_ice_cream: Мороженое"): "Мороженое", #"ice-cream",
        emoji.emojize(":doughnut: Восточные сладости"): "Восточные сладости", #"oriental-sweets",
        emoji.emojize(":pencil: Другое (указать)"): "Десерты",
        emoji.emojize(":BACK_arrow: Назад"): "to-category"
    }

    for key, value in desserts.items():
        builder.button(text=key, callback_data=f'desserts::{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()


def change_drinks_kb():
    """Клавиатура для выбора напитков"""
    builder = InlineKeyboardBuilder()

    drinks = {
        emoji.emojize(":wine_glass: Алкогольные"): "Алкогольные", #"alcoholic-beverages",
        emoji.emojize(":teacup_without_handle: Безалкогольные"): "Безалкогольные", #"non-alcoholic-beverages",
        emoji.emojize(":BACK_arrow: Назад"): "to-category"
    }

    for key, value in drinks.items():
        builder.button(text=key, callback_data=f'drinks_{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()



def change_alcogol_drinks_kb():
    """Клавиатура для выбора алкогольных напитков"""
    builder = InlineKeyboardBuilder()

    alcogol_drinks = {
        emoji.emojize(":wine_glass: Вина"): "Вина", #"guilt",
        emoji.emojize(":cocktail_glass: Коктейли"): "Коктейли", #"coctails",
        emoji.emojize(":beer_mug: Пиво"): "Пиво", #"beer",
        emoji.emojize(":tumbler_glass: Крепкий алкоголь"): "Крепкий алкоголь", #"strong_alcogol",
        emoji.emojize(":pencil: Другое (указать)"): "Алкогольные напитки",
        emoji.emojize(":BACK_arrow: Назад"): "to-category"
    }

    for key, value in alcogol_drinks.items():
        builder.button(text=key, callback_data=f'alcogol-drinks::{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()



def change_non_alcogol_drinks_kb():
    """Клавиатура для выбора безалкоголных напитков"""
    try:
        logger.info(f'Стартовал change_non_alcogol_drinks_kb')
        builder = InlineKeyboardBuilder()

        non_alcogol_drinks = {
            emoji.emojize(":teapot: Чай"): "Чай", #"tea",
            emoji.emojize(":hot_beverage: Кофе"): "Кофе", #"coffee",
            emoji.emojize(":beverage_box: Соки и морсы"): "Соки и морсы", #"juices",
            emoji.emojize(":bubble_tea: Лимонады"): "Лимонады", #"lemonades",
            emoji.emojize(":sake: Вода"): "Вода", #"water",
            emoji.emojize(":tropical_drink: Безалкогольные коктейли"): "Безалкогольные коктейли", #"non-alcogol-coctails",
            emoji.emojize(":pencil: Другое (указать)"): "Безалкогольные напитки",
            emoji.emojize(":BACK_arrow: Назад"): "to-category"
        }

        for key, value in non_alcogol_drinks.items():
            logger.info(f'{key=}\n{value=}')
            builder.button(text=key, callback_data=f'non-alc::{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')
            logger.info('Кнопка успешно создана')
        builder.adjust(1)

        
        return builder.as_markup()
    except Exception as e:
        logger.error(f'change_non_alcogol_drinks_kb: Произошла ошибка {e}')


# def change_non_alcogol_drinks_kb():
#     """Клавиатура для выбора безалкоголных напитков"""
#     builder = InlineKeyboardBuilder()

#     non_alcogol_drinks = {
#         emoji.emojize(":teapot: Чай"): "tea",
#         emoji.emojize(":hot_beverage: Кофе"): "coffee",
#         emoji.emojize(":beverage_box: Соки и морсы"): "juices",
#         emoji.emojize(":bubble_tea: Лимонады"): "lemonades",
#         emoji.emojize(":sake: Вода"): "water",
#         emoji.emojize(":tropical_drink: Безалкогольные коктейли"): "non-alcogol-coctails",
#         emoji.emojize(":BACK_arrow: Назад"): "to-category"
#     }

#     for key, value in non_alcogol_drinks.items():
#         builder.button(text=key, callback_data=f'non-alcogol-drinks_{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

#     builder.adjust(1)

    
#     return builder.as_markup()


def change_strong_alcogol_drinks_kb():
    """Клавиатура для выбора крепких алкоголных напитков"""
    builder = InlineKeyboardBuilder()

    strong_alcogol_drinks = {
        emoji.emojize(":eight-pointed_star: Виски"): "Виски", #"whiskey",
        emoji.emojize(":eight-spoked_asterisk: Ром"): "Ром", #"rum",
        emoji.emojize(":eight-pointed_star: Коньяк и бренди"): "Коньяк и бренди", #"cognac",
        emoji.emojize(":eight-pointed_star: Водка"): "Водка", #"vodka",
        emoji.emojize(":pencil: Другое (указать)"): "Крепкий алкоголь",
        emoji.emojize(":BACK_arrow: Назад"): "to-category"
    }

    for key, value in strong_alcogol_drinks.items():
        builder.button(text=key, callback_data=f'strong-alcogol-drinks::{value}' if key != emoji.emojize(":BACK_arrow: Назад") else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()




def change_hookah_menu_kb():
    """Клавиатура для выбора кальяна"""
    builder = InlineKeyboardBuilder()

    hookah = {
        "Классический": "Кальян_классический", #"classic",
        "Авторский": "Кальян_авторский",#"from-autor",
        "На фрукте": "Кальян_на_фрукте",#"on-fruits",
        "Другое (указать)": "Кальян",
        "Назад": "to-category"
    }

    for key, value in hookah.items():

        builder.button(text=key, callback_data=f'hookah::{value}' if key != 'Назад' else f'back_{value}')

    builder.adjust(1)

    
    return builder.as_markup()


def change_menu_kb():
    """Клавиатура для поиска блюда в меню"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text='Поиск', callback_data='start_search')
    builder.button(text='Подобрать меню', callback_data='start_change-menu')
    
    builder.adjust(2)
    
    return builder.as_markup()



async def price_keyboard(state:FSMContext, call:CallbackQuery, finish_flag:bool=False):
    """Клавиатура для выбора уровня цен"""
    builder = InlineKeyboardBuilder()
    
    state_data:dict = await state.get_value(f'{call.from_user.id}')
    price_levels = state_data.get('price_levels')
    logger.info(f'price_keyboard: {price_levels=}')

    if not price_levels:
        builder.button(text='1000-2000₽ (₽₽)', callback_data='price_1')
        builder.button(text='2000-3000₽ (₽₽₽)', callback_data='price_2')
        builder.button(text='Выше 3000₽ (₽₽₽₽)', callback_data='price_3')
        if not finish_flag:
            builder.button(text='Выбрать меню', callback_data='price_each-dish')
        if not finish_flag:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='back_confirm-price')
        else:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm-finish::summa_amount')
    else:
        builder.button(text=emoji.emojize(':check_mark_button: ') + '1000-2000₽ (₽₽)' + emoji.emojize(' :check_mark_button:') if '1' in price_levels else '1000-2000₽ (₽₽)', callback_data='price_1')
        builder.button(text=emoji.emojize(':check_mark_button: ') + '2000-3000₽ (₽₽₽)' + emoji.emojize(' :check_mark_button:') if '2' in price_levels else '2000-3000₽ (₽₽₽)', callback_data='price_2')
        builder.button(text=emoji.emojize(':check_mark_button: ') + 'Выше 3000₽ (₽₽₽₽)' + emoji.emojize(' :check_mark_button:') if '3' in price_levels else 'Выше 3000₽ (₽₽₽₽)', callback_data='price_3')
        if not finish_flag:
            builder.button(text='Выбрать меню', callback_data='price_each-dish')
        if not finish_flag:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='back_confirm-price')
        else:
            builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='confirm-finish::summa_amount')
    builder.adjust(1)

    return builder.as_markup()

# Аналогично создаются клавиатуры для других районов:
# sao_keyboard(), svao_keyboard(), vao_keyboard(), yvao_keyboard(),
# yao_keyboard(), yuzao_keyboard(), zao_keyboard(), szao_keyboard()


async def each_dish_kb(state:FSMContext, call:CallbackQuery, finish_flag:bool=False):
    """Клавиатура для регулировки уровня цен конкретного блюда"""
    state_user_data:dict = await state.get_value(f'{call.from_user.id}')

    categoryes:dict = state_user_data.get('categoryes', {})
    logger.info(f'each_dish_kb: {categoryes=}')


    def get_info_of_categories(category:str, categoryes:dict = categoryes) -> bool:
        """Возвращает информацию о том, выбрано ли блюдо по конкретной категории или нет"""
        if not categoryes or category not in categoryes:
            logger.info(f'get_info_of_categories: категория {category} не выбиралась')
            return False
        changed_categoryes = [key for key, value in categoryes.items() if value]
        if category == 'Закуски':
            if [item for item in ['Закуски', 'Горячие закуски', 'Холодные закуски', 'Сыры и антипасто', 'Салаты'] if item in changed_categoryes]:
                return True
        elif category == 'Основные блюда':
            if [item for item in ['Основные блюда', 'Первые блюда', 'Вторые блюда', 'Мясные блюда', 'Рыбные блюда'] if item in changed_categoryes]:
                return True
        elif category == 'Десерты':
            if [item for item in ['Десерты', 'Выпечка', 'Мороженое', 'Восточные сладости'] if item in changed_categoryes]:
                return True
        elif category == 'Напитки':
            if [item for item in ['Крепкий алкоголь', 'Безалкогольные напитки', 'Алкогольные напитки', 'Вина', 'Коктейли', 'Пиво', 'Крепкий алкоголь', 'Чай', 'Кофе', 
                                  'Соки и морсы', 'Лимонады', 'Вода', 'Безалкогольные коктейли', 
                                  'Виски', 'Ром', 'Коньяк и бренди', 'Водка'] if item in changed_categoryes]:
                return True
        elif category == 'Детское меню':
            if 'Детское меню' in changed_categoryes:
                return True
        elif category == 'Кальян':
            if [item for item in ['Кальян', 'Классический', 'Авторский', 'На фрукте'] if item in changed_categoryes]:
                return True
        else:
            return False
            
        
        
    
    
    dish_equals = {
        'Закуски':"Выбрать :green_salad:",
        'Основные блюда': "Выбрать :pot_of_food:",
        'Десерты': "Выбрать :shortcake:",
        'Напитки': "Выбрать :cup_with_straw:",
        'Детское меню': "Выбрать :popcorn:", 
        'Кальян': "Выбрать :thought_balloon:"
    }

    categoryes = {
        "Закуски": "snacks",
        "Основные блюда": "main-courses",
        "Десерты": "desserts",
        "Напитки": "drinks",
        "Детское меню": "сhildren-menu",
        "Кальян": "hookah",
        }

    builder = InlineKeyboardBuilder()
    dish_list = ['Закуски','Основные блюда', 'Десерты', 'Напитки', 
                 'Детское меню', 'Кальян']
    price_dish = state_user_data.get('price_dish', dict())
    [price_dish.setdefault(f'{dish}') for dish in dish_list]
    state_user_data['price_dish'] = price_dish
    await state.update_data({f'{call.from_user.id}': state_user_data})

    for key, value in price_dish.items():
        builder.row(InlineKeyboardButton(text=emoji.emojize(':down_arrow: ') + f'{key}' +  emoji.emojize(' :down_arrow:'), callback_data='dish'),
                    InlineKeyboardButton(text=emoji.emojize(':check_mark_button: ') + emoji.emojize(dish_equals[key]) + emoji.emojize(' :check_mark_button:') if get_info_of_categories(key) else emoji.emojize(dish_equals[key]), callback_data=f'dish:{key}'))
        builder.row(InlineKeyboardButton(text=emoji.emojize(':plus:') , callback_data=f'dish-price:{key}_{value}_plus' if value else f'dish-price:{key}_{None}_plus'),
                    InlineKeyboardButton(text=str(value) if value else '---', callback_data='dish'),
                    InlineKeyboardButton(text=emoji.emojize(':minus:') , callback_data=f'dish-price:{key}_{value}_minus' if value else f'dish-price:{key}_{None}_minus'))
    
    
    if not finish_flag:
        builder.row(InlineKeyboardButton(text='ПОДТВЕРДИТЬ', callback_data='confirm_dish-price'))
    else:
        builder.row(InlineKeyboardButton(text='ПОДТВЕРДИТЬ', callback_data='edit::categoryes_str'))
    
    return builder.as_markup()

# Клавиатура для станций метро
async def metro_keyboard(district:str, state:FSMContext, call:CallbackQuery):
    """Клавиатура для выбора станций метро"""
    
    state_user_data = await state.get_value(f'{call.from_user.id}')
    logger.info(f'metro_keyboard: {state_user_data=}')
    
    builder = InlineKeyboardBuilder()
    # Здесь должен быть словарь со станциями метро по районам
    metro_stations = get_metro_stations_for_district(district)
    logger.info(f'{district=}\n{metro_stations=}')
    state_user_data['district'] = district
    await state.update_data({f'{call.from_user.id}': state_user_data})

    for station in metro_stations:
        text = emoji.emojize(':check_mark_button: ') + station + emoji.emojize(' :check_mark_button:') if 'selected_stations' in state_user_data and station in state_user_data.get('selected_stations') else station
        builder.button(text=text, callback_data=f'metro_{station}')
    builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='demo_station_lines')
    
    builder.adjust(1)

    return builder.as_markup()


async def metro_from_rayon(rayon:str, state:FSMContext, call:CallbackQuery):
    """Клавиатура для выбора станций метро по району"""
    state_data = await state.get_value(f'{call.from_user.id}')
    logger.info(f'metro_from_rayon: {state_data=}')
    logger.info(f'metro_from_rayon: {rayon=}')
    
    builder = InlineKeyboardBuilder()
    # Здесь должен быть словарь со станциями метро по районам
    stations_from_rayon = stations_by_rayon[rayon]
    logger.info(f'metro_from_rayon: {stations_from_rayon=}')

    for station in stations_from_rayon:
        text = emoji.emojize(':check_mark_button: ') + station + emoji.emojize(' :check_mark_button:') if 'selected_stations' in state_data and station in state_data.get('selected_stations') else station
        builder.button(text=text, callback_data=f'metro_{station}')
    builder.button(text=emoji.emojize(':OK_button: ПОДТВЕРДИТЬ'), callback_data='back_to-metro')
    
    builder.adjust(1)

    return builder.as_markup()




# Функция для получения станций метро по району
def get_metro_stations_for_district(district):
    # Пример реализации (нужно заполнить реальными данными)
    metro_data = metro_map
    logger.info(f'get_metro_stations_for_district: {district=}')
    return metro_data.get(f'{district} линия', [])
    


def admin_panel_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(text=emoji.emojize(":pencil: Изменить ТОП3"), callback_data="edit_top_info")    
    builder.button(text=emoji.emojize(':recycling_symbol: Изменить прайс'), callback_data='edit_price')
    # builder.button(text="Заведения", callback_data="establishments")
    builder.button(text=emoji.emojize(':woman_and_man_holding_hands: Мои подписчики'), callback_data="my_subscribers")
    builder.button(text=emoji.emojize(':thinking_face: Не подписались'), callback_data='my_not_subscribers')
    # builder.button(text="Не прочитанные", callback_data='new_messages')
    builder.button(text=emoji.emojize(':dollar_banknote: Доходы'), callback_data='my_finance')
    builder.button(text=emoji.emojize(':bento_box: Работа с заведениями'), callback_data='establs::main')
    # builder.button(text=emoji.emojize(':stop_sign: Проверить отсутств. в базе'), callback_data='establs::not_in_base')
    builder.button(text=emoji.emojize('Сменить пароль'), callback_data='another_password')
    builder.button(text=emoji.emojize(':cross_mark: Выйти'), callback_data='main-menu')
    builder.adjust(1) 

    return builder.as_markup()


def establishments_func_kb():
    """Клавиатура с функциями для работы с заведениями со стороны администратора"""
    builder = InlineKeyboardBuilder()

    builder.button(text=emoji.emojize(":magnifying_glass_tilted_right: Найти новые"), callback_data="establs::search-new")
    builder.button(text=emoji.emojize("Уже в базе"), callback_data="establs::establs_info")
    builder.button(text=emoji.emojize(':recycling_symbol: Обновить данные'), callback_data="establs::update_info")
    builder.adjust(1)

    return builder.as_markup()


async def update_info_of_establ_kb(count):
    """Клавиатура с функциями для обновления данных о заведениях"""
    builder = InlineKeyboardBuilder()

    # count = config('UPDATE_COUNT')
    all_establs = await get_info_of_establishments()
    all_establs_count = len(all_establs)

    builder.button(text=emoji.emojize(':flag_in_hole: Выбрать заведение'), callback_data="update::change")
    # builder.row(
    #     InlineKeyboardButton(text=emoji.emojize('Последнее проверенное'), callback_data="not_click"),
    #     InlineKeyboardButton(text=count, callback_data="not_click"))
    builder.button(text=emoji.emojize('Проверить сразу 5'), callback_data="update::check_five")
    builder.row(
        InlineKeyboardButton(text=emoji.emojize('Всего в базе'), callback_data="not_click"),
        InlineKeyboardButton(text=str(all_establs_count), callback_data="not_click"))
    
    builder.adjust(1)

    return builder.as_markup()
    


def get_establishments_keyboard(companies: List[tuple[str, int]], offset: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    keyboard = []
    start = offset
    end = min(offset + page_size, len(companies))
    
    for i in range(start, end):
        keyboard.append([
            InlineKeyboardButton(
                text=f'{companies[i][0][:32] if len(companies[i][0])>15 else companies[i][0]}',
                callback_data=f"company:{companies[i][1]}"
            )
        ])
    
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(
            InlineKeyboardButton(text=emoji.emojize(":last_track_button: Предыдущие"), callback_data=f"prev:{offset}")
        )
    if end < len(companies):
        nav_buttons.append(
            InlineKeyboardButton(text=emoji.emojize("Далее :next_track_button:"), callback_data=f"next:{offset + page_size}")
        )
    
    nav_buttons.append(
        InlineKeyboardButton(text='Найти',callback_data="establs::search_in_base_new")
    )
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    logger.info(f'get_companies_keyboard: Клавиатура успешно создана')

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def find_establ_in_base_kb():
    """Клавиатура для поиска заведений в режиме администратора"""
    builder = InlineKeyboardBuilder()

    builder.button(text='По названию', callback_data='admin_find::by_name')
    builder.button(text='По типу', callback_data='admin_find::by_type')
    builder.button(text='По меню', callback_data='admin_find::by_menu')
    builder.adjust(1)

    return builder.as_markup()



async def input_number_new_establ_kb(state:FSMContext, call:CallbackQuery):
    """Клавиатура для указания количества новых заведений и их типа"""
    builder = InlineKeyboardBuilder()
    state_user_data:dict = await state.get_value(f'{call.from_user.id}', {})
    count_info = state_user_data.get('count-info', '---')
    logger.info(f'input_number_new_establ_kb: {state_user_data=}')
    admin_selected_type_current = state_user_data.get('admin_selected_type_current')
    admin_selected_type_last = admin_selected_type_current
    state_user_data['admin_selected_type_last'] = admin_selected_type_last
    logger.info(f'input_number_new_establ_kb: {state_user_data=}')
    await state.update_data({f'{call.from_user.id}': state_user_data})

    builder.row(
        InlineKeyboardButton(text=emoji.emojize(':plus:'), callback_data='new-estab::plus'),
        InlineKeyboardButton(text=(f'{count_info}'), callback_data='new-estab::count-info'),
        InlineKeyboardButton(text=emoji.emojize(':minus:'), callback_data='new-estab::minus')
    )
    builder.button(text=emoji.emojize(':eight-pointed_star:') + 'Добавить по ссылке' + emoji.emojize(':eight-pointed_star:'), callback_data='new-estab::add_link')
    builder.button(text='Укажите тип', callback_data='not_clicable')
    
    types = [
        emoji.emojize(':fondue: Ресторан'), emoji.emojize(':green_salad: Кафе'), emoji.emojize(':curry_rice: Столовая'), emoji.emojize(':piñata: Кальян-бар'), emoji.emojize(':hot_beverage: Кофейня')
    ]
    if admin_selected_type_current:
        for t in types:
            builder.button(text=emoji.emojize(':check_mark_button: ') + t + emoji.emojize(' :check_mark_button:') if t.split(' ')[1] == admin_selected_type_current else t, callback_data=f'admin-type_{t.split(' ')[1]}')
        
        else:
            builder.button(text=emoji.emojize(':OK_button: НАЙТИ'), callback_data='new-estab::start_search')
    else:
        for t in types:
            builder.button(text=t, callback_data=f'admin-type_{t.split(' ')[1]}')

    builder.adjust(3,1)
    
    return builder.as_markup()
        

async def not_subscribers_info_kb(state: FSMContext, page: int = 0) -> InlineKeyboardMarkup | None:
    """
    Создаёт пагинированную клавиатуру с информацией о пользователях без подписки.
    
    Args:
        state: экземпляр FSMContext для получения данных из состояния
        page: номер текущей страницы (0 = первая)
        
    Returns:
        InlineKeyboardMarkup: готовая клавиатура или None при ошибке
    """
    try:
        # Получаем данные из состояния
        data = await state.get_data()
        not_subscribers = data.get('not_subscribers')
        
        
        # Проверяем наличие данных
        if not not_subscribers:
            logger.warning("not_subscribers_info_kb: данные not_subscribers отсутствуют или пусты")
            return None
            
        total_items = len(not_subscribers)
        items_per_page = 10
        
        # Определяем границы текущей страницы
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        
        page_items = not_subscribers[start_idx:end_idx]
        
        if not page_items:  # Если на странице нет элементов
            logger.warning(f"not_subscribers_info_kb: нет элементов для страницы {page}")
            return None
        
        builder = InlineKeyboardBuilder()
        
        # Формируем кнопки для элементов текущей страницы
        for item in page_items:
            if len(item) < 3:
                logger.error(f"not_subscribers_info_kb: некорректная структура элемента: {item}")
                continue
            # text = f"{item[0]}    ---    {item[1]}    ---    {'ДА' if item[2] else 'НЕТ'}"
            text = f"{item[0]}    ---    {item[1]} "
            builder.button(text=text, callback_data="ignore_me")
        
        
        # Добавляем навигационные кнопки при необходимости
        nav_buttons = []
        
        # Кнопка «Назад» (только если не первая страница)
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"not_subscribers_page_{page - 1}"
                )
            )
        
        # Кнопка «Дальше» (только если есть следующие элементы)
        if end_idx < total_items:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Дальше",
                    callback_data=f"not_subscribers_page_{page + 1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)  # Добавляем навигацию в одну строку
        
        # Кнопка «Главное меню» всегда в конце
        builder.button(
            text=emoji.emojize(':house: Главное меню'),
            callback_data='main-menu'
        )
        builder.adjust(1)  # Все кнопки — по одной в ряду
        
        return builder.as_markup()
        
    except Exception as e:
        logger.error(f"not_subscribers_info_kb: непредвиденная ошибка: {type(e).__name__}: {e}")
        return None




def add_establishment_keyboard():
    builder = InlineKeyboardBuilder()
        
    builder.button(text="Тип заведения", callback_data="select_type")
    builder.button(text="Прикрепить файлы", callback_data="attach_files")
    
    return builder.as_markup()



async def subscribers_info_kb(state:FSMContext):
    sub_associate = {
                "unlimit": "Бесплатный",
                "day": "День",
                "week": "Неделя",
                "month": "Месяц"
            }
    try:
        statistic_data = await state.get_value('statistic_data')
        save_statistic_to_csv(statistic_data=statistic_data)
        builder = InlineKeyboardBuilder()
        for key, value in statistic_data.items():
            builder.button(text=f'{sub_associate[key]}  {value[0]}', callback_data=f"not_click")
        builder.button(text=emoji.emojize(':house:Главное меню'), callback_data='main-menu')
        builder.adjust(1)
        return builder.as_markup()
    except Exception as e:
        logger.error(f'subscribers_info_kb: Произошла ошибка {e}')


def get_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="За весь период", callback_data='all_period')
    builder.button(text="Указать дату", callback_data='choose_date')
    # builder.button(text="Выбрать период", callback_data='choose_period')
    builder.button(text="От пользователя", callback_data='from_user')
    builder.button(text="Назад", callback_data='admin-back_button3')
    builder.adjust(1)
    return builder.as_markup()


def get_years_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=3)
    current_year = datetime.now().year
    buttons = []
    for year in range(current_year, current_year + 3):
        button = InlineKeyboardButton(text=str(year), callback_data=f'year_{year}')
        buttons.append(button)
    keyboard.inline_keyboard = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return keyboard


def get_calendar_keyboard(year:int, month:str) -> InlineKeyboardMarkup:
    import calendar
    #from calendar import monthrange, month_name
    keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=7)
    month_associate = {
        "Декабрь":"December",
        "Январь":"January",
        "Февраль":"February",
        "Март":"March",
        "Апрель":"April",
        "Май":"May",
        "Июнь":"June",
        "Июль":"July",
        "Август":"August",
        "Сентябрь":"September",
        "Октябрь":"October",
        "Ноябрь":"November"
    }

    day_numbers = {
    calendar.MONDAY: 0,
    calendar.TUESDAY: 1,
    calendar.WEDNESDAY: 2,
    calendar.THURSDAY: 3,
    calendar.FRIDAY: 4,
    calendar.SATURDAY: 5,
    calendar.SUNDAY: 6
    }


    buttons = []
    # получаем номер месяца
    month_number = list(calendar.month_name).index(month_associate[month].capitalize())
    logger.info(f'{month_number=}')
    # получаем количество дней в месяце
    _ , num_days = calendar.monthrange(year, month_number)
    logger.info(f'{num_days=}')
    # добавляем дни недели
    days_of_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in days_of_week:
        button = InlineKeyboardButton(text=day, callback_data="ignore")
        buttons.append(button)

    # получаем первый день месяца
    first_week_day, _ = calendar.monthrange(year, month_number)
    logger.info(f'порядковый день недели: {day_numbers[first_week_day]}')

    # Заполняем пустые кнопки для выравнивания
    for _ in range(day_numbers[first_week_day]):
        buttons.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
        #keyboard.insert(InlineKeyboardButton(text=" ", callback_data="ignore"))
        # добавляем дни месяца
    for day in range(1, num_days + 1):
        buttons.append(InlineKeyboardButton(text=str(day), callback_data=f"day_{year}_{month_number}_{day}"))
        #keyboard.insert(InlineKeyboardButton(text=str(day), callback_data=f"day_{year}_{month_number}_{day}"))
    
    buttons_to_list = []

    for i in range(0, len(buttons), 7):
        buttons_to_list.append(buttons[i:i + 7])

    # узнаём количество кнопок, не достающих до 7 в последней строке
    num_to_seven = 7 - len(buttons_to_list[-1])
    logger.info(f'{num_to_seven=}')
    if num_to_seven:
        for i in range(num_to_seven):
            buttons_to_list[-1].append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            logger.info("Пустая кнопка добавлена")
    
    keyboard.inline_keyboard = buttons_to_list
    #keyboard.inline_keyboard = [buttons[i:i + 7] for i in range(0, len(buttons), 7)]
    return keyboard



def get_months_keyboard() -> InlineKeyboardMarkup:
    months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь",
               "Октябрь", "Ноябрь", "Декабрь"]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[], row_width=4)
    buttons = []
    for month in months:
        button = InlineKeyboardButton(text=month, callback_data=f"month_{month}")
        buttons.append(button)
    keyboard.inline_keyboard = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    return keyboard


def create_subscriptions_keyboard(subscribe_dict:dict) -> InlineKeyboardMarkup:
    """Инлайн клавиатура для изменения стоимости подписки"""
    builder = InlineKeyboardBuilder()

    sub_associate = {
        "unlimit": "Бесплатный",
        "day": "День",
        "week": "Неделя",
        "month": "Месяц"
    }
    
    for key, value in subscribe_dict.items():
        if key != 'unlimit':
            value1, value2 = value.split('--')
            builder.button(text=f'{sub_associate.get(key)} {value1} р. --  {value2} р.', callback_data=f'ignore')
            builder.button(text="Изменить", callback_data=f'edit-price_{key}_{value1}_{value2}')
    builder.button(text='Назад', callback_data='go_to_admin_kb')

    builder.adjust(2)
    return builder.as_markup()

# def establishment_type_keyboard():
    
#     builder = InlineKeyboardBuilder()
    
#     types = [
#         "Ресторан", "Кафе", "Столовая", "Закусочная",
#         "Бистро", "Кальян-бар", "Паб", "Кафетерий",
#         "Буфет", "Фудкорт", "Кофейня"
#     ]

#     for type in types:
#         builder.button(text=type, callback_data=f"type_{type}")

#     builder.adjust(2)
#     builder.row(InlineKeyboardButton(text='Подтвердить', callback_data='confirm_type'))

#     return builder.as_markup()

async def edit_categories_kb(categories_info:dict, price_dish:dict, state_user_data:dict, state:FSMContext, call_mess:CallbackQuery | Message):
    """Клавиатура для изменения заказанных блюд на финишном этапе
    перед поиском в базе данных"""
    
    logger.info(f'edit_categories_kb: {price_dish=}')
    logger.info(f'edit_categories_kb: {categories_info=}')
    
    flag_dict = {
        'Закуски': ['Закуски', 'Горячие закуски', 'Холодные закуски', 'Сыры и антипасто', 'Салаты'],
        'Основные блюда': ['Основные блюда', 'Первые блюда', 'Вторые блюда', 'Мясные блюда', 'Рыбные блюда'],
        'Десерты': ['Десерты', 'Выпечка', 'Мороженое', 'Восточные сладости'],
        'Напитки': ['Крепкий алкоголь', 'Безалкогольные напитки', 'Алкогольные напитки', 'Вина', 'Коктейли', 'Пиво', 'Крепкий алкоголь', 'Чай', 'Кофе', 
                                  'Соки и морсы', 'Лимонады', 'Вода', 'Безалкогольные коктейли', 
                                  'Виски', 'Ром', 'Коньяк и бренди', 'Водка'],
        'Детское меню': ['Детское меню'],
        'Кальян': ['Кальян', 'Классический', 'Авторский', 'На фрукте']
    }

    builder = InlineKeyboardBuilder()

    all_flag_dict = {}
    for key, value in deepcopy(categories_info).items():
        logger.info(f'edit_categories_kb: {key=} {value=}')
        
        if value:
            key_from_flag_dict = [key_into for key_into , value_into in flag_dict.items() if key in value_into][0]
                    
            logger.info(f'edit_categories_kb: {key_from_flag_dict=}')
            current_price = price_dish.get(key_from_flag_dict)
            logger.info(f'edit_categories_kb: {current_price=}')
            all_flag_dict.update({key_from_flag_dict: current_price})
            state_user_data.update(all_flag_dict=all_flag_dict)
            if isinstance(call_mess, CallbackQuery):
                await state.update_data({f'{call_mess.message.from_user.id}':state_user_data})
            else:
                await state.update_data({f'{call_mess.from_user.id}': state_user_data})
            [builder.row(
                InlineKeyboardButton(text=f'{value_item[:15]}...' if len(value_item)>15 else value_item, callback_data=f"show_cat::{value_item[:5]}"),
                InlineKeyboardButton(text=f'{current_price} ₽' if current_price else '---', callback_data=f"show_cat::not_active"),
                InlineKeyboardButton(text=emoji.emojize(':pencil:...'), callback_data=f"edit_cat::{value_item[:5]}::{str(current_price) + ' ₽' if current_price else '--- ₽'}"),
                InlineKeyboardButton(text=emoji.emojize(':wastebasket:'), callback_data=f"del_cat::{value_item[:5]}")
            ) for value_item in value]
    builder.row(InlineKeyboardButton(text=emoji.emojize(':plus: Добавить'), callback_data="add_cat"),
                InlineKeyboardButton(text=emoji.emojize(':OK_button: Подтвердить'), callback_data="confirm-finish::add_dish"))
    logger.info(f'{all_flag_dict=}')
    return builder.as_markup()
            


def create_inline_keyboard_from_urls(urls: List[str]) -> Optional[InlineKeyboardMarkup]:
    """
    Создаёт inline‑клавиатуру для aiogram 3 из списка URL‑адресов.

    Нормализация ссылок:
    - 'https://...' → остаётся без изменений;
    - 'www.example.com' → превращается в 'https://example.com';
    - 'example.com' → становится 'https://example.com'.

    Каждая кнопка:
    - text — домен/путь без 'https://' (для читаемости);
    - url — полный нормализованный URL (открывается при нажатии).

    Args:
        urls: Список строк с URL (допускается мусор, пробелы, некорректные значения).

    Returns:
        InlineKeyboardMarkup — готовая клавиатура для отправки,
        или None, если не удалось создать ни одной кнопки.
    """
    if not urls or not isinstance(urls, list):
        return None

    buttons: List[List[InlineKeyboardButton]] = []

    for platform, url in urls:
        try:
            # Пропускаем пустые/нестроковые значения
            if not url or not isinstance(url, str) or url.startswith('https://wa.me'):
                continue

            # Очищаем от пробелов
            url = url.strip()
            if not url:
                continue

            # Нормализация URL
            if url.startswith("https://"):
                normalized_url = url
            elif url.startswith("www."):
                normalized_url = "https://" + url[4:]
            else:
                normalized_url = "https://" + url

            # Формируем текст кнопки (без 'https://')
            display_text = normalized_url.removeprefix("https://")

            # Создаём кнопку с переходом по ссылке
            button = InlineKeyboardButton(
                text=platform,
                url=normalized_url  # aiogram 3: параметр `url` для открытия ссылки
            )
            buttons.append([button])  # Каждая кнопка — отдельная строка

        except (AttributeError, TypeError, ValueError) as e:
            print(f"Ошибка обработки ссылки '{url}': {type(e).__name__}: {e}")
            continue
        except Exception as e:
            print(f"Неожиданная ошибка для '{url}': {type(e).__name__}: {e}")
            continue

    # Возвращаем клавиатуру, только если есть кнопки
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None



