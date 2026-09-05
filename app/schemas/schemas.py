"""Модуль Pydantic-схем для валидации входящих запросов и сериализации ответов (DTO)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.models import Category, TransactionType

# ============================================================================
# Схемы аутентификации и пользователей
# ============================================================================


class UserRegister(BaseModel):
    """Схема запроса на регистрацию нового пользователя.

    Атрибуты:
        email (EmailStr): Адрес электронной почты пользователя.
        password (str): Пароль пользователя (открытый текст при передаче).
        name (str): Имя пользователя.
    """

    email: EmailStr = Field(..., description="Email адрес пользователя")
    password: str = Field(..., min_length=6, description="Пароль пользователя (минимум 6 символов)")
    name: str = Field(..., min_length=1, max_length=100, description="Имя пользователя")


class UserLogin(BaseModel):
    """Схема запроса для аутентификации пользователя (логин).

    Атрибуты:
        email (EmailStr): Зарегистрированный адрес электронной почты.
        password (str): Пароль пользователя.
    """

    email: EmailStr = Field(..., description="Email адрес пользователя")
    password: str = Field(..., description="Пароль пользователя")


class TokenResponse(BaseModel):
    """Схема ответа с JWT-токеном доступа.

    Атрибуты:
        access_token (str): Сгенерированный JWT-токен.
        token_type (str): Тип токена (по умолчанию "bearer").
    """

    access_token: str = Field(..., description="JWT токен доступа")
    token_type: str = Field(default="bearer", description="Тип токена авторизации")


class UserResponse(BaseModel):
    """Схема ответа с публичными данными пользователя.

    Атрибуты:
        id (uuid.UUID): Уникальный ID пользователя.
        email (str): Email пользователя.
        name (str): Имя пользователя.
        created_at (datetime): Дата регистрации аккаунта.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="ID пользователя")
    email: str = Field(..., description="Email пользователя")
    name: str = Field(..., description="Имя пользователя")
    created_at: datetime = Field(..., description="Дата и время создания аккаунта")


# ============================================================================
# Схемы финансовых транзакций
# ============================================================================


class TransactionCreate(BaseModel):
    """Схема запроса на создание транзакции (дохода или расхода).

    Атрибуты:
        amount (float): Сумма операции (> 0).
        description (str): Описание операции.
        category (Category): Категория транзакции.
        type (TransactionType): Тип транзакции (income / expense).
        date (datetime | None): Дата и время операции (если не указано — текущее время).
    """

    amount: float = Field(..., gt=0, description="Сумма операции (должна быть больше 0)")
    description: str = Field(
        ..., min_length=1, max_length=255, description="Описание или назначение платежа"
    )
    category: Category = Field(..., description="Категория операции")
    type: TransactionType = Field(
        ..., description="Тип операции: income (доход) или expense (расход)"
    )
    date: datetime | None = Field(
        default=None, description="Дата транзакции (по умолчанию текущая)"
    )


class TransactionResponse(BaseModel):
    """Схема ответа с данными сохраненной транзакции.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор транзакции.
        amount (float): Сумма операции.
        description (str): Описание транзакции.
        category (Category): Категория.
        type (TransactionType): Тип (income / expense).
        date (datetime): Дата и время транзакции.
        created_at (datetime): Дата создания записи в БД.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="ID транзакции")
    amount: float = Field(..., description="Сумма транзакции")
    description: str = Field(..., description="Описание транзакции")
    category: Category = Field(..., description="Категория транзакции")
    type: TransactionType = Field(..., description="Тип операции")
    date: datetime = Field(..., description="Дата транзакции")
    created_at: datetime = Field(..., description="Дата добавления в базу")


# ============================================================================
# Схемы бюджетов
# ============================================================================


class BudgetCreate(BaseModel):
    """Схема запроса на установку лимита бюджета по категории.

    Атрибуты:
        category (Category): Категория расходов.
        limit_amount (float): Устанавливаемый лимит суммы.
        month (int): Месяц (1-12).
        year (int): Год (например, 2026).
    """

    category: Category = Field(..., description="Категория расходов")
    limit_amount: float = Field(..., gt=0, description="Лимит суммы на указанный месяц")
    month: int = Field(..., ge=1, le=12, description="Номер месяца (от 1 до 12)")
    year: int = Field(..., ge=2000, le=2100, description="Год")


class BudgetResponse(BaseModel):
    """Схема ответа с информацией о бюджете и расчетом расходов.

    Атрибуты:
        id (uuid.UUID): Идентификатор записи бюджета.
        category (Category): Категория расходов.
        limit_amount (float): Установленный лимит суммы.
        month (int): Месяц действия.
        year (int): Год действия.
        spent (float): Фактически потраченная сумма за указанный период.
        remaining (float): Оставшаяся доступная сумма лимита.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="ID бюджета")
    category: Category = Field(..., description="Категория расходов")
    limit_amount: float = Field(..., description="Установленный лимит бюджета")
    month: int = Field(..., description="Месяц")
    year: int = Field(..., description="Год")
    spent: float = Field(default=0.0, description="Фактически израсходовано")
    remaining: float = Field(default=0.0, description="Остаток лимита")


# ============================================================================
# Схемы AI-инсайтов
# ============================================================================


class InsightResponse(BaseModel):
    """Схема ответа с персональными рекомендациями AI.

    Атрибуты:
        insights (list[str]): Список текстовых рекомендаций по оптимизации финансов.
        generated_at (datetime): Временная метка генерации ответа.
    """

    insights: list[str] = Field(..., description="Список аналитических советов и выводов")
    generated_at: datetime = Field(..., description="Дата и время формирования аналитики")
