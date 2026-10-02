"""Сервис управления финансовыми транзакциями (доходы и расходы)."""

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import ErrorCode, NotFoundException
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
            date=payload.date or datetime.now(timezone.utc),
        )
        self.db.add(tx)
        self.db.flush()
        self.db.refresh(tx)
        logger.info(f"Создана новая транзакция: {tx}")
        return tx

    def get_all(
        self,
        user_id: uuid.UUID,
        since: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Transaction], int]:
        """Получение транзакций с поддержкой пагинации и фильтрации по времени создания.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            since (datetime | None): Фильтр по минимальной дате создания (created_at).
            limit (int | None): Максимальное количество возвращаемых записей.
            offset (int | None): Смещение относительно начала выборки.

        Возвращает:
            tuple[list[Transaction], int]: Кортеж из списка транзакций текущей страницы и общего числа записей.
        """
        query = self.db.query(Transaction).filter(Transaction.user_id == user_id)
        if since:
            query = query.filter(Transaction.created_at >= since)

        total = query.count()
        query = query.order_by(Transaction.date.desc())

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        return query.all(), total

    def delete(self, user_id: uuid.UUID, transaction_id: uuid.UUID) -> None:
        """Удалить транзакцию по ее идентификатору.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя (для проверки прав доступа).
            transaction_id (uuid.UUID): ID удаляемой транзакции.

        Исключения:
            NotFoundException (404): Если транзакция с указанным ID не найдена у данного пользователя.
        """
        tx = self.db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.user_id == user_id).first()
        if not tx:
            logger.warning(f"Попытка удаления несуществующей транзакции {transaction_id} для пользователя {user_id}")
            raise NotFoundException(
                code=ErrorCode.TRANSACTION_NOT_FOUND,
                message="Транзакция не найдена",
                details={"transaction_id": str(transaction_id)},
            )
        self.db.delete(tx)
        self.db.flush()
        logger.info(f"Транзакция удалена: {tx.id}")

    def get_etag(
        self,
        user_id: uuid.UUID,
        since: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> str:
        """Быстрый расчет ETag без выгрузки всех объектов с учетом пагинации."""
        query = self.db.query(func.count(Transaction.id), func.max(Transaction.created_at)).filter(
            Transaction.user_id == user_id
        )

        if since:
            query = query.filter(Transaction.created_at >= since)

        count, max_created = query.first()
        raw_str = f"{user_id}:{count}:{max_created.isoformat() if max_created else ''}:{limit}:{offset}"
        return hashlib.md5(raw_str.encode()).hexdigest()
