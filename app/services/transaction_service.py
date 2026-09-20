"""Сервис управления финансовыми транзакциями (доходы и расходы)."""

import hashlib
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Transaction
from app.schemas.schemas import TransactionCreate
from logger.logger import get_logger

logger = get_logger(__name__)


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
        logger.info(f"Создана новая транзакция: {tx}")
        return tx

    def get_all(self, user_id: uuid.UUID, since: datetime | None = None) -> list[Transaction]:
        """Получение транзакций с поддержкой фильтрации по времени создания."""
        query = self.db.query(Transaction).filter(Transaction.user_id == user_id)
        if since:
            query = query.filter(Transaction.created_at >= since)
        return query.order_by(Transaction.date.desc()).all()

    def delete(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
        """Удалить транзакцию по ее идентификатору.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя (для проверки прав доступа).
            transaction_id (uuid.UUID): ID удаляемой транзакции.

        Исключения:
            HTTPException (404): Если транзакция с указанным ID не найдена у данного пользователя.
        """
        tx = self.db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()
        if not tx:
            logger.warning(f"Попытка удаления несуществующей транзакции {transaction_id} для пользователя {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Транзакция не найдена",
            )
        self.db.delete(tx)
        self.db.commit()
        logger.info(f"Транзакция удалена: {tx.id}")

    def get_etag(self, user_id: uuid.UUID, since: datetime | None = None) -> str:
        """Быстрый расчет ETag без выгрузки всех объектов."""
        query = self.db.query(func.count(Transaction.id), func.max(Transaction.created_at)).filter(
            Transaction.user_id == user_id
        )

        if since:
            query = query.filter(Transaction.created_at >= since)

        count, max_created = query.first()
        raw_str = f"{user_id}:{count}:{max_created.isoformat() if max_created else ''}"
        return hashlib.md5(raw_str.encode()).hexdigest()
