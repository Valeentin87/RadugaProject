import os, sys

project_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_directory)

import json
from db_handler.db_class import Base, engine
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Float, ForeignKey, Integer, String, Boolean, DateTime, BigInteger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, delete
from create_bot import logger


class Claim(Base):
    """
    Модель для описания информации о заявке для управляющей компании
    """
    __tablename__ = 'claims'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String, unique=True) # номер заявки
    company_name: Mapped[str] = mapped_column(String, nullable=True) # название УК, которой адресована заявка
    appeal_date: Mapped[str] = mapped_column(String, nullable=False) # дата обращения
    description: Mapped[str] = mapped_column(String, nullable=True) # описание заявки (содержание задачи)
    address: Mapped[str] = mapped_column(String, nullable=False) # адрес зявителя
    urgency: Mapped[str] = mapped_column(String, nullable=True)  # срочность
    due_date: Mapped[str] = mapped_column(String, nullable=False) # срок исполнения
    status: Mapped[str] = mapped_column(String, default="Новая заявка") # статус заявки
    additional_field: Mapped[str] = mapped_column(String, nullable=True) # дополнительная информация о заявке

    def to_dict(self):
        return {
            "id": self.id,
            "claim_id": self.claim_id,
            "company_name": self.company_name,
            "appeal_date": self.appeal_date,
            "description": self.description,
            "address": self.address,
            "urgency": self.urgency,
            "due_date": self.due_date,
            "status": self.status,
            "additional_field": self.additional_field
        }
    
    
    def __repr__(self):
        return (
            f"Заявка № {self.claim_id}\n"
            f"УК: {self.company_name}\n"
            f"Дата подачи: {self.appeal_date}\n"
            f"Описание: {self.description}\n"
            f"Адрес заявителя: {self.address}\n"
            f"Срочность: {self.urgency}\n"
            f"Срок исполнения: {self.due_date}\n"
            f"Статус: {self.status}\n"
            f"Дополнительная информация:{self.additional_field}"
        )
    

if __name__ == '__main__':
    import asyncio

    async def create_table():
        """Вручную создает таблицы БД"""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_table())