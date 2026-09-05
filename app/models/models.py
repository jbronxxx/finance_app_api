"""Модуль описания ORM-моделей базы данных SQLAlchemy."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TransactionType(str, enum.Enum):
    """Тип финансовой транзакции."""

    income = "income"  # Доход
    expense = "expense"  # Расход


class Category(str, enum.Enum):
    """Категории доходов и расходов."""

    food = "food"  # Продукты и питание
    transport = "transport"  # Транспорт
    entertainment = "entertainment"  # Развлечения
    health = "health"  # Здоровье и медицина
    subscriptions = "subscriptions"  # Подписки и сервисы
    shopping = "shopping"  # Покупки и одежда
    salary = "salary"  # Заработная плата
    other = "other"  # Прочее


class User(Base):
    """ORM-модель пользователя системы.

    Таблица: users

    Поля:
        id (uuid.UUID): Уникальный идентификатор пользователя (Primary Key).
        email (str): Уникальный адрес электронной почты (логин).
        hashed_password (str): Хеш пароля (bcrypt).
        name (str): Имя пользователя.
        created_at (datetime): Дата и время регистрации.
        transactions (list[Transaction]): Список связанных транзакций пользователя.
        budgets (list[Budget]): Список связанных бюджетов пользователя.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связи с другими сущностями
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Transaction(Base):
    """ORM-модель финансовой операции (транзакции).

    Таблица: transactions

    Поля:
        id (uuid.UUID): Уникальный идентификатор транзакции (Primary Key).
        user_id (uuid.UUID): Внешний ключ на владельца операции (users.id).
        amount (float): Сумма операции.
        description (str): Описание / комментарий к операции.
        category (Category): Категория транзакции (Enum).
        type (TransactionType): Тип транзакции (income / expense).
        date (datetime): Дата совершения операции.
        created_at (datetime): Дата и время записи в БД.
        user (User): Связанный объект пользователя.
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[Category] = mapped_column(SAEnum(Category), nullable=False)
    type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связь с пользователем
    user: Mapped["User"] = relationship(back_populates="transactions")


class Budget(Base):
    """ORM-модель бюджета (лимита расходов по категории).

    Таблица: budgets

    Поля:
        id (uuid.UUID): Уникальный идентификатор бюджета (Primary Key).
        user_id (uuid.UUID): Внешний ключ на владельца бюджета (users.id).
        category (Category): Категория расходов, для которой установлен лимит.
        limit_amount (float): Установленный лимит суммы на месяц.
        month (int): Месяц действия бюджета (1-12).
        year (int): Год действия бюджета.
        created_at (datetime): Дата создания бюджета.
        user (User): Связанный объект пользователя.
    """

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[Category] = mapped_column(SAEnum(Category), nullable=False)
    limit_amount: Mapped[float] = mapped_column(Float, nullable=False)
    month: Mapped[int] = mapped_column(nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Связь с пользователем
    user: Mapped["User"] = relationship(back_populates="budgets")
