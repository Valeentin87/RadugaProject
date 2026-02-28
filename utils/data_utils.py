import os, sys

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

from db_handler.base import get_all_not_closed_claims
from create_bot import logger
import json
from typing import List
from db_handler.models import Claim
from pprint import pprint
from utils.scrap_utils_new import get_jsond_data_by_claim
import time

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
    try:
        print("get_info_from_site_to_compare: стартовала")
        start_time = time.time()
        not_closed_dict = await get_chanded_info()
        claim_info_from_site = {key : [] for key in list(not_closed_dict.keys())}
        for company, info in not_closed_dict.items():
            all_claim_ids = list(map(lambda x: x[0], info))
            print(f'{company=}\n{all_claim_ids[-10:]}')
            claims_by_company = get_jsond_data_by_claim(company, all_claim_ids)
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
        
        return claim_info_from_site
    except Exception as e:
        logger.error(f'Произошла ошибка: {e}')
        print(f'Произошла ошибка: {e}')




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

    for company in dict2.keys():
        # Инициализируем пустой список для компании в результате
        result[company] = []

        # Получаем списки заявок для текущей компании
        list1 = dict1.get(company, [])
        list2 = dict2.get(company, [])

        # Создаём словарь для быстрого поиска статусов по номеру заявки из первого словаря
        status_by_claim_id = {claim_id: status for claim_id, status in list1}

        # Проверяем каждую заявку из второго словаря
        for claim_tuple in list2:
            claim_id, new_status, deadline, urgency = claim_tuple

            # Получаем старый статус (если заявка была в первом словаре)
            old_status = status_by_claim_id.get(claim_id)

            # Если заявка есть в первом словаре и статус изменился — добавляем кортеж в результат
            if old_status is not None and old_status != new_status:
                result[company].append(claim_tuple)

    return result
            


if __name__ == "__main__":
    import asyncio

    #asyncio.run(get_chanded_info())
    asyncio.run(get_info_from_site_to_compare())