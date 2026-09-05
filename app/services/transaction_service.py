"""Сервис управления финансовыми транзакциями (доходы и расходы)."""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import Transaction
from app.schemas.schemas import TransactionCreate


class TransactionService:
    """Класс бизнес-логики для создания, получения и удаления финансовых операций."""

    def __init__(self, db: Session):
        """Инициализация сервиса с сессией базы данных.

        Аргументы:
            db (Session): Сессия SQLAlchemy.
        """
        self.db = db

    def create(self, user_id: uuid.UUID, payload: TransactionCreate) -> Transaction:
        """Создать новую транзакцию (доход или расход) для пользователя.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя-владельца.
            payload (TransactionCreate): Данные для создания транзакции.

        Возвращает:
            Transaction: Созданная и сохраненная в БД запись транзакции.
        """
        tx = Transaction(
            user_id=user_id,
            amount=payload.amount,
            description=payload.description,
            category=payload.category,
            type=payload.type,
            date=payload.date or datetime.utcnow(),
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def get_all(self, user_id: uuid.UUID) -> list[Transaction]:
        """Получить все транзакции пользователя, отсортированные по дате (от новых к старым).

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.

        Возвращает:
            list[Transaction]: Список транзакций пользователя.
        """
        return (
            self.db.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc())
            .all()
        )

    def delete(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
        """Удалить транзакцию по ее идентификатору.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя (для проверки прав доступа).
            transaction_id (uuid.UUID): ID удаляемой транзакции.

        Исключения:
            HTTPException (404): Если транзакция с указанным ID не найдена у данного пользователя.
        """
        tx = (
            self.db.query(Transaction)
            .filter(Transaction.id == transaction_id, Transaction.user_id == user_id)
            .first()
        )
        if not tx:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Транзакция не найдена",
            )
        self.db.delete(tx)
        self.db.commit()
