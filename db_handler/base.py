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