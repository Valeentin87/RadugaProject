import os, sys
from typing import Dict, List, Tuple


project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import json

from db_handler.models import Claim
from db_handler.db_class import engine, Base, async_session
from create_bot import logger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import select



def connection(func):
    async def wrapper(*args, **kwargs):
        async with async_session() as session:
            return await func(session, *args, **kwargs)
    return wrapper


async def create_tables():
    async with engine.begin() as conn:
        logger.info('Таблицы созданы')
        await conn.run_sync(Base.metadata.create_all)


@connection
async def add_new_claim(session, claim_info:dict) -> Claim:
    """
    Асинхронно добавляет или обновляет запись заявки в БД.

    Если запись с таким claim_id уже существует — удаляет её и создаёт новую.
    Если не существует — создаёт новую.

    Args:
        data (dict): Словарь с данными заявки.
        session (AsyncSession): Асинхронная сессия SQLAlchemy.

    Returns:
        Claim: Созданный или обновлённый объект заявки.
    """
    claim_id = claim_info.get("claim_id")

    if not claim_id:
        raise ValueError("Обязательное поле 'claim_id' отсутствует в данных")

    try:
        # Проверяем, существует ли заявка с таким claim_id
        result = await session.execute(
            select(Claim).where(Claim.claim_id == claim_id)
        )
        existing_claim = result.scalar_one_or_none()

        if existing_claim:
            # Удаляем существующую запись
            await session.delete(existing_claim)
            await session.flush()  # Применяем удаление перед созданием новой записи
            logger.info(f"Удалена существующая запись в таблице __claims__ с {claim_id=}")
            print(f"Удалена существующая запись в таблице __claims__ с {claim_id=}")

        # Создаём новую заявку на основе данных словаря
        new_claim = Claim(**claim_info)
        session.add(new_claim)
        await session.commit()
        await session.refresh(new_claim)  # Обновляем объект с актуальными данными из БД
        logger.info(f"Добавлена запись в таблице __claims__ с {claim_id=}")
        print(f"Добавлена запись в таблице __claims__ с {claim_id=}")

        return new_claim

    except IntegrityError as e:
        await session.rollback()
        raise ValueError(f"Ошибка целостности данных при сохранении заявки {claim_id}: {e}")
    except Exception as e:
        await session.rollback()
        raise Exception(f"Неожиданная ошибка при работе с заявкой {claim_id}: {e}")
    

@connection
async def add_new_claims(session, new_claims_by_company: dict, batch_size: int = 100):
    """Добавляет информацию о новых заявках, принятых в работу (пакетная обработка)"""
    if not new_claims_by_company:
        return None
    items = list(new_claims_by_company.items())
    total_processed = 0

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        try:
            async with session.begin():
                for claim_id, claim_info in batch:
                    # Проверка существования заявки
                    result = await session.execute(
                        select(Claim).where(Claim.claim_id == claim_id)
                    )
                    existing_claim = result.scalar_one_or_none()

                    if existing_claim:
                        await session.delete(existing_claim)
                        await session.flush()  # Явный flush после удаления
                        logger.info(f"Удалена существующая запись в таблице __claims__ с {claim_id=}")

                    # Создание новой заявки
                    new_claim = Claim(claim_id=claim_id, **claim_info)
                    session.add(new_claim)
                    logger.info(f"Добавлена запись в таблице __claims__ с {claim_id=}")
                    total_processed += 1

                    # Логирование прогресса каждые 10 обработанных заявок
                    if total_processed % 10 == 0:
                        logger.info(f"Обработано {total_processed}/{len(items)} заявок")
        except Exception as e:
            logger.error(f"Ошибка в пакете {i//batch_size + 1}: {e}")
            raise

    logger.info(f"Успешно обработано {total_processed} заявок")
    print(f"Успешно обработано {total_processed} заявок")



@connection
async def get_all_not_closed_claims(session):
    """Возвращает список не завершенных работой заявок"""
    try:
        async with async_session() as session:
            not_closed_claims:List[Claim] = (await session.execute(select(Claim).where(Claim.status.notin_(["Решено", "Закрыто", "Закрыто. Отправлено в ДД."])))).scalars().all()
            print(f"Получено {len(not_closed_claims)} заявок")
            logger.warning(f"Получено {len(not_closed_claims)} заявок")
            return not_closed_claims
    except SQLAlchemyError as e:
        logger.error(f"Произошла ошибка при получении информации о незакрытых заявках: {e}")
        print(f"Произошла ошибка при получении информации о незакрытых заявках: {e}")


@connection
async def get_deadline_exceeded_claims(session) -> List[Claim]:
    """Возвращает заявки с превышенным сроком исполнения"""
    try:
        deadline_exceeded_claims = (await session.execute(select(Claim).where(Claim.status == "Срок превышен"))).scalars().all()
        print(f"Получено {len(deadline_exceeded_claims)} заявок с истекшим сроком выполнения" if deadline_exceeded_claims else 'Заявки с превышенным сроком выполнения отсутствуют')
        return deadline_exceeded_claims
    except SQLAlchemyError as e:
        logger.error(f"Произошла ошибка при получении информации о заявках c превышенным сроком выполнения: {e}")
        print(f"Произошла ошибка при получении информации о заявках c превышенным сроком выполнения: {e}")



@connection
async def get_claims_by_company_from_db(session) -> Dict[str, List[Tuple]]:
    """
    Возвращает словарь, где:
    - ключи — уникальные значения поля company_name;
    - значения — списки кортежей (claim_id, status, description, appeal_date, urgency)
      для заявок со статусами «Закрыто» и «Требуется доработка».


    Args:
        session: асинхронная сессия SQLAlchemy


    Returns:
        Словарь с данными по компаниям и их заявкам
    """
    # Определяем нужные статусы
    target_statuses = ["Закрыто", "Требуется доработка"]


    # Формируем запрос — включаем все нужные поля
    stmt = (
        select(
            Claim.company_name,
            Claim.claim_id,
            Claim.status,
            Claim.description,
            Claim.appeal_date,
            Claim.urgency
        )
        .where(Claim.status.in_(target_statuses))
        .order_by(Claim.company_name)
    )

    # Выполняем запрос
    result = await session.execute(stmt)
    rows = result.all()

    # Группируем данные по company_name
    claims_by_company: Dict[str, List[Tuple]] = {}

    for row in rows:
        company_name = row.company_name
        # Формируем кортеж: claim_id — первый элемент, status — второй
        claim_data = (
            row.claim_id,
            row.status,
            row.description,
            row.appeal_date,
            row.urgency
        )

        if company_name not in claims_by_company:
            claims_by_company[company_name] = []

        claims_by_company[company_name].append(claim_data)

    print(f"get_claims_by_company_from_db: {claims_by_company=}")
    return claims_by_company


@connection
async def update_claim_in_db(
    session,
    claim_id: int,
    status: str,
    due_date: str,
    urgency: str
):
    """
    Обновляет запись в таблице Claim по ID заявки.
    """
    try:
        # Ищем заявку по ID
        result = await session.execute(
            select(Claim).where(Claim.claim_id == str(claim_id))
        )
        find_claim: Claim = result.scalar_one_or_none()

        if find_claim is None:
            print(f"Заявка с ID {str(claim_id)} не найдена в БД")
            return False  # Возвращаем флаг неудачи

        # Обновляем поля
        find_claim.status = status
        find_claim.due_date = due_date
        find_claim.urgency = urgency

        # Сохраняем изменения
        await session.commit()
        print(f"Заявка ID {str(claim_id)} успешно обновлена")
        return True  # Успешное обновление

    except Exception as e:
        # Откатываем транзакцию при ошибке
        await session.rollback()
        print(f"Ошибка при обновлении заявки ID {str(claim_id)}: {str(e)}")
        return False




if __name__ == "__main__":
    import asyncio

    #asyncio.run(get_all_not_closed_claims())

    #asyncio.run(get_deadline_exceeded_claims())
    asyncio.run(get_claims_by_company_from_db())