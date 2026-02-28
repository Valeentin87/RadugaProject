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
        not_closed_dict = await get_chanded_info()
        claim_info_from_site = {key : [] for key in list(not_closed_dict.keys())}
        for company, info in not_closed_dict.items():
            all_claim_ids = list(map(lambda x: x[0], info))
            print(f'{company=}\n{all_claim_ids[-10:]}')
            claims_by_company = get_jsond_data_by_claim(company, all_claim_ids[-10:])
            claim_info_from_site.update(company=claims_by_company)
        
        print(f"{'Работа функции завершена':.^40}")
        pprint(claim_info_from_site)
        return claim_info_from_site
    except Exception as e:
        logger.error(f'Произошла ошибка: {e}')
        print(f'Произошла ошибка: {e}')

                


if __name__ == "__main__":
    import asyncio

    #asyncio.run(get_chanded_info())
    asyncio.run(get_info_from_site_to_compare())