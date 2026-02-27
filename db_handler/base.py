import os, sys


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


