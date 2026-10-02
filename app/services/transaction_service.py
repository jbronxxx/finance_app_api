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
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Transaction], bool, str | None]:
        """Получение транзакций с поддержкой курсорной пагинации (keyset pagination) и фильтрации.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            since (datetime | None): Фильтр по минимальной дате создания (created_at).
            limit (int): Максимальное количество возвращаемых записей.
            cursor (str | None): Курсор для получения следующей страницы.

        Возвращает:
            tuple[list[Transaction], bool, str | None]: Кортеж из списка транзакций, флага наличия след. страницы и курсора.
        """
        import base64
        import json

        from sqlalchemy import and_, or_

        query = self.db.query(Transaction).filter(Transaction.user_id == user_id)
        if since:
            query = query.filter(Transaction.created_at >= since)

        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode("utf-8"))
                cursor_date = datetime.fromisoformat(cursor_data["d"])
                if cursor_date.tzinfo is None:
                    cursor_date = cursor_date.replace(tzinfo=timezone.utc)
                cursor_id = uuid.UUID(cursor_data["i"])

                query = query.filter(
                    or_(Transaction.date < cursor_date, and_(Transaction.date == cursor_date, Transaction.id < cursor_id))
                )
            except Exception as e:
                logger.warning(f"Некорректный курсор {cursor}: {e}")

        query = query.order_by(Transaction.date.desc(), Transaction.id.desc())

        # Запрашиваем на 1 больше, чтобы определить, есть ли следующая страница
        query = query.limit(limit + 1)

        items = query.all()
        has_more = len(items) > limit
        if has_more:
            items = items[:limit]

        next_cursor = None
        if items:
            last_item = items[-1]
            cursor_data = {"d": last_item.date.isoformat(), "i": str(last_item.id)}
            next_cursor = base64.b64encode(json.dumps(cursor_data).encode("utf-8")).decode("utf-8")

        return items, has_more, next_cursor

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
        limit: int = 50,
        cursor: str | None = None,
    ) -> str:
        """Быстрый расчет ETag без выгрузки всех объектов с учетом пагинации (без count)."""
        query = self.db.query(func.max(Transaction.created_at)).filter(Transaction.user_id == user_id)

        if since:
            query = query.filter(Transaction.created_at >= since)

        max_created = query.scalar()
        raw_str = f"{user_id}:{max_created.isoformat() if max_created else ''}:{limit}:{cursor or ''}"
        return hashlib.md5(raw_str.encode()).hexdigest()
