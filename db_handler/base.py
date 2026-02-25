import os, sys

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import json

from db_handler.db_class import engine, Base, async_session
from create_bot import logger
from sqlalchemy.exc import SQLAlchemyError
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