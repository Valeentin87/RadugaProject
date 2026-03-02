import os, sys

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import re
from bs4 import BeautifulSoup
import importlib

from db_handler.base import get_all_not_closed_claims, get_deadline_exceeded_claims, update_claim_in_db
from create_bot import logger
import json
from typing import Dict, List, Tuple
from db_handler.models import Claim
from pprint import pprint
from redis_db import redis_db
#from utils.scrap_utils_new import get_jsond_data_by_claim
import time
from dotenv import load_dotenv


load_dotenv()

COMPANY_ACCESS = os.getenv('COMPANY_ACCESS')
company_access = json.loads(COMPANY_ACCESS)


async def get_chanded_info():
    """Получает информацию о заявках, статусы которых были 
    поменяны на основе анализа резульатов с сайта и сравнения
    с имеющимися в базе данных"""
    try:
        not_closed_claims:List[Claim] = await get_all_not_closed_claims()
        logger.info(f"Получено всего {len(not_closed_claims)} заявок, статус которых необходимо проверить на сайте")
        print(f"Получено всего {len(not_closed_claims)} заявок, статус которых необходимо проверить на сайте")

        # формируем информацию по компаниям:
        not_closed_dict = dict()
        all_company = [ value[0] for value in list(company_access.values()) ]
        print(f"{all_company=}")
        [not_closed_dict.setdefault(company, []) for company in all_company]
        
        for claim in not_closed_claims:
            try:
                if claim.company_name in not_closed_dict:
                    #print("Совпадение по ключу")
                    not_closed_dict[f'{claim.company_name}'].append((claim.claim_id, claim.status))
                else:
                    raise("Эта компания не в списке оказывающих услуги")
            except Exception:
                logger.error(f"Произошла ошибка")
                continue
        #pprint(not_closed_dict)
        print("get_chanded_info: Завершение работы")
        return not_closed_dict
    except Exception as e:
        logger.error(f"Произошла ошибка {e}")



async def get_info_from_site_to_compare():
    """Получает информацию с сайта по актуальным данным по заявкам 
    с целью использования их для дальнейшего сопоставления с базой данных"""
    
    while True:
        check_new_claims_flag = False
        check_new_claims_flag = redis_db.is_process_running("check_new_claims")
        if not check_new_claims_flag:
            break
        print("Ждем 5 секунд и проверяем завершение процесса поиска новых заявок")
        time.sleep(5) 
    
    redis_db.add_new_process("check_statuses")

    
    try:
        print("get_info_from_site_to_compare: стартовала")
        start_time = time.time()
        not_closed_dict = await get_chanded_info()
        claim_info_from_site = {key : [] for key in list(not_closed_dict.keys())}
        scrap_utils = importlib.import_module('utils.scrap_utils_new')
        for company, info in not_closed_dict.items():
            all_claim_ids = list(map(lambda x: x[0], info))
            print(f'{company=}\n{all_claim_ids[-10:]}')
            claims_by_company = scrap_utils.get_jsond_data_by_claim(company, all_claim_ids)
            print(f"{company=}\n{claims_by_company=}")
            claim_info_from_site.update({company : claims_by_company})
        
        print(f"{'Работа функции завершена':.^40}")
        pprint(claim_info_from_site)
        end_time = time.time()
        execution_time = end_time - start_time
        width = 50  # Общая ширина строки
        print(f"{f'Поиск актуальной информации по заявкам выполнялся: {execution_time} секунд':^{width}}")
        
        print("Приступаем к сравнению данных в базе и на сайте")

        result = compare_statuses(not_closed_dict, claim_info_from_site)
        print(f'{f"Информация по измененным статусам: {result}":.^60}')
        
        redis_db.remove_process("check_statuses")
        return claim_info_from_site
    except Exception as e:
        logger.error(f'Произошла ошибка: {e}')
        print(f'Произошла ошибка: {e}')
        redis_db.remove_process("check_statuses")


def compare_statuses(dict1, dict2):
    """
    Сравнивает два словаря с данными о заявках и возвращает словарь с кортежами из второго словаря,
    для которых изменился статус заявки.

    Args:
        dict1 (dict): словарь с ключами — названиями УК, значениями — списками кортежей (номер_заявки, статус)
        dict2 (dict): словарь с ключами — названиями УК, значениями — списками кортежей
                    (номер_заявки, статус, срок_выполнения, срочность)


    Returns:
        dict: словарь с теми же ключами, значениями — списками кортежей из dict2, где изменился статус
    """
    result = {}

    # Получаем полный набор всех УК из обоих словарей
    all_companies = set(dict1.keys()) | set(dict2.keys())

    for company in all_companies:
        result[company] = []

        # Получаем списки заявок для текущей компании
        list1 = dict1.get(company, [])
        list2 = dict2.get(company, [])

        # Создаём словарь для быстрого поиска статусов по номеру заявки из первого словаря
        status_by_claim_id = {}
        for item in list1:
            if len(item) >= 2:  # проверяем, что кортеж имеет минимум 2 элемента
                claim_id, status = item[0], item[1]

                # Приводим оба значения к строке и нормализуем (убираем пробелы, нижний регистр)
                claim_id_str = str(claim_id).strip()
                status_str = str(status).strip().lower()

                status_by_claim_id[claim_id_str] = status_str

        # Проверяем каждую заявку из второго словаря
        for claim_tuple in list2:
            if len(claim_tuple) < 4:  # проверяем структуру кортежа
                print(f"Предупреждение: некорректный кортеж в dict2 для компании {company}: {claim_tuple}")
                continue

            claim_id, new_status, deadline, urgency = claim_tuple

            # Приводим оба значения к строке и нормализуем
            claim_id_str = str(claim_id).strip()
            new_status_str = str(new_status).strip().lower()

            # Получаем старый статус (если заявка была в первом словаре)
            old_status = status_by_claim_id.get(claim_id_str)

            # Если заявка есть в первом словаре и статус изменился — добавляем кортеж в результат
            if old_status is not None and old_status != new_status_str:
                result[company].append(claim_tuple)

    return result


            

async def get_details_of_exceeded_claims():
    """Подготавливает информацию в виде словаря о заявках с истекшим сроком выполнения"""
    try:
        deadline_exceeded_claims: List[Claim] = await get_deadline_exceeded_claims()
        detail_info = dict()
        all_company = [ value[0] for value in list(company_access.values()) ]
        [detail_info.setdefault(company, []) for company in all_company]

        for claim in deadline_exceeded_claims:
            try:
                if claim.company_name in detail_info:
                    #print("Совпадение по ключу")
                    detail_info[f'{claim.company_name}'].append((claim.claim_id, claim.due_date))
                else:
                    raise("Эта компания не в списке оказывающих услуги")
            except Exception:
                logger.error(f"Произошла ошибка")
                continue
        pprint(detail_info)
        print("get_details_of_exceeded_claims: Завершение работы")
        return detail_info
    except Exception as e:
        logger.error(f"Произошла ошибка {e}")



def find_company_in_html(html_content: str, company_names: list[str]) -> str | None:
    """
    Ищет название управляющей компании в HTML‑контенте с учётом условий.

    Args:
        html_content (str): HTML‑контент страницы.
        company_names (list[str]): список названий управляющих компаний для поиска.

    Returns:
        str | None: найденное название компании или None, если не найдено.
    """
    # Парсим HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Находим блок с классом "claim-view__body"
    claim_body = soup.find('div', class_='claim-view__body')
    if not claim_body:
        return None

    # Получаем текст из блока (сохраняем структуру для анализа позиций)
    body_text = str(claim_body)

    # Приводим к нижнему регистру для регистронезависимого поиска
    body_text_lower = body_text.lower()

    # Ищем все совпадения названий компаний в блоке
    matches = []
    for company in company_names:
        company_lower = company.lower()
        # Используем регулярное выражение для поиска точного совпадения слова
        pattern = r'\b' + re.escape(company_lower) + r'\b'
        for match in re.finditer(pattern, body_text_lower):
            matches.append({
                'company': company,
                'start': match.start(),
                'end': match.end()
            })

    # Фильтруем совпадения: проверяем условие с «Кому» в пределах 80 символов слева
    valid_matches = []
    for match in matches:
        start_pos = match['start']
        # Берём фрагмент текста в пределах 80 символов слева от совпадения
        left_context_start = max(0, start_pos - 80)
        context = body_text_lower[left_context_start:start_pos]
        # Проверяем, есть ли слово «Кому» (в любом регистре) в контексте
        if re.search(r'\bкому\b', context, re.IGNORECASE):
            valid_matches.append(match)

    # Если есть валидные совпадения, возвращаем первое найденное название компании
    if valid_matches:
        return valid_matches[0]['company']

    return None

# тестовый вариант функции поиска названия управляющей компании среди HTML контента


def find_company_in_html_from_file(filename: str, company_names: list[str]) -> str | None:
    """
    Ищет название управляющей компании в HTML‑файле с учётом условий.

    Args:
        filename (str): путь к файлу с HTML‑контентом.
        company_names (list[str]): список названий управляющих компаний для поиска.

    Returns:
        str | None: найденное название компании или None, если не найдено.
    """
    try:
        # Читаем содержимое файла
        with open(filename, 'r', encoding='utf-8') as file:
            html_content = file.read()
    except FileNotFoundError:
        print(f"Ошибка: файл '{filename}' не найден.")
        return None
    except PermissionError:
        print(f"Ошибка: нет прав доступа к файлу '{filename}'.")
        return None
    except UnicodeDecodeError:
        print(f"Ошибка: не удалось декодировать файл '{filename}'. Проверьте кодировку.")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка при чтении файла '{filename}': {e}")
        return None

    # Парсим HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Находим блок с классом "claim-view__body"
    claim_body = soup.find('div', class_='claim-view__body')
    if not claim_body:
        return None

    # Получаем текст из блока
    body_text = str(claim_body)
    body_text_lower = body_text.lower()

    # Ищем все совпадения названий компаний в блоке
    matches = []
    for company in company_names:
        company_lower = company.lower()
        pattern = r'\b' + re.escape(company_lower) + r'\b'
        for match in re.finditer(pattern, body_text_lower):
            matches.append({
                'company': company,
                'start': match.start(),
                'end': match.end()
            })

    # Фильтруем совпадения: проверяем условие с «Кому» в пределах 80 символов слева
    valid_matches = []
    for match in matches:
        start_pos = match['start']
        left_context_start = max(0, start_pos - 80)
        context = body_text_lower[left_context_start:start_pos]
        # Используем флаг re.IGNORECASE для регистронезависимого поиска
        if re.search(r'\bкому\b', context, re.IGNORECASE):
            valid_matches.append(match)

    # Если есть валидные совпадения, возвращаем первое найденное название компании
    if valid_matches:
        return valid_matches[0]['company']

    return None


def update_claims_with_company_names(all_claim_info: list[dict], new_claims_data: dict) -> dict:
    """
    Обновляет словарь new_claims_data, добавляя/обновляя поле "company_name" для каждой заявки
    на основе данных из all_claim_info.

    Args:
        all_claim_info (list[dict]): список словарей с информацией о заявках, содержащих ключи:
            - "url" (str)
            - "claim_id" (str) — ID заявки
            - "company_name" (str) — название компании
            - "title" (str)
            - "html_file" (str)
            - "timestamp" (int)
        new_claims_data (dict): словарь заявок, где ключи — ID заявок (str), значения — словари с полями:
            - "appeal_date" (str)
            - "description" (str)
            - "address" (str)
            - "urgency" (str)
            - "due_date" (str)

    Returns:
        dict: обновлённый словарь new_claims_data с добавленным/обновлённым полем "company_name"
    """
    # Проходим по каждому элементу списка all_claim_info
    for claim_info in all_claim_info:
        claim_id = claim_info["claim_id"]
        company_name = claim_info["company_name"]

        # Если заявка с таким ID есть в new_claims_data, добавляем/обновляем поле company_name
        if claim_id in new_claims_data:
            new_claims_data[claim_id]["company_name"] = company_name

    print("Завершение работы метода update_claims_with_company_names")
    pprint(new_claims_data)
    
    return new_claims_data


async def process_and_update_claims(data: Dict[str, List[Tuple[int, str, str, str]]]) -> Dict[str, List[Tuple]]:
    """
    Обрабатывает словарь с данными о заявках и обновляет БД.

    Возвращает словарь с ключами 'Закрыто' и 'Требуется доработка',
    где каждый кортеж содержит название организации как нулевой элемент.

    Args:
        data: входной словарь с заявками по организациям
    Returns:
        dict: словарь с отфильтрованными заявками, включая название организации
    """
    result = {
        "Закрыто": [],
        "Требуется доработка": []
    }

    # Проходим по всем организациям и их заявкам
    for org_name, claims in data.items():
        for claim_id, status, due_date, urgency in claims:
            # Обновляем запись в БД
            await update_claim_in_db(claim_id=claim_id, 
                                    status=status,
                                    due_date=due_date,
                                    urgency=urgency)

            # Создаём новый кортеж с названием организации как нулевым элементом
            extended_claim = (org_name, claim_id, status, due_date, urgency)

            # Фильтруем заявки по статусам для результата
            if status == "Закрыто":
                result["Закрыто"].append(extended_claim)
            elif status == "Требуется доработка":
                result["Требуется доработка"].append(extended_claim)

    return result






if __name__ == "__main__":
    import asyncio

    #asyncio.run(get_chanded_info())
    #asyncio.run(get_info_from_site_to_compare())
    #asyncio.run(get_details_of_exceeded_claims())

    # company_name = find_company_in_html_from_file("work_parsed_pages/claim_approve_6182669.html",  ["Дивное", "Радуга", "Радэкс"])
    # print(company_name)
