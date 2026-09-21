"""Модуль Pydantic-схем для валидации входящих запросов и сериализации ответов (DTO)."""

import uuid
from datetime import datetime
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.models import Category, TransactionType

# ============================================================================
# Базовые response обертки для стандартизации ответов
# ============================================================================

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Универсальная обертка для успешных ответов API.

    Атрибуты:
        status: Статус ответа ('success').
        data: Данные результата (может быть любой тип T).
        message: Опциональное сообщение о результате.
    """

    status: str = Field(default="success", description="Статус ответа")
    data: T = Field(..., description="Данные результата")
    message: Optional[str] = Field(default=None, description="Опциональное сообщение о результате")


class ErrorResponse(BaseModel):
    """Обертка для ошибочных ответов.

    Атрибуты:
        status: Статус ответа ('error').
        code: Уникальный строковый код ошибки (например, 'BUDGET_LIMIT_EXCEEDED').
        message: Понятное описание ошибки для пользователя.
        details: Опциональные структурированные детали ошибки.
    """

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(default="error", description="Статус ответа")
    code: str = Field(..., description="Машиночитаемый строковый код ошибки")
    message: str = Field(..., description="Понятное описание ошибки")
    details: Optional[dict] = Field(default=None, description="Дополнительные детали ошибки")


class BaseResponse(BaseModel):
    """Базовая схема ответа для простых операций (без данных).

    Используется для операций которые не возвращают значимые данные
    (например logout, delete).
    """

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(default="success", description="Статус ответа")
    message: Optional[str] = Field(default=None, description="Сообщение о результате операции")


# ============================================================================
# Схемы аутентификации и пользователей
# ============================================================================


class UserBase(BaseModel):
    """Базовая схема пользователя с общими полями.

    Атрибуты:
        user_id (uuid.UUID): Уникальный идентификатор пользователя.
    """

    user_id: uuid.UUID = Field(..., description="ID пользователя")


class UserRegister(BaseModel):
    """Схема запроса на регистрацию нового пользователя.

    Атрибуты:
        email (EmailStr): Адрес электронной почты пользователя.
        password (str): Пароль пользователя.
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


class RefreshTokenRequest(BaseModel):
    """Схема запроса на обновление access-токена с использованием refresh-токена.

    Атрибуты:
        refresh_token (str): Действительный JWT refresh-токен.
    """

    refresh_token: str = Field(..., description="JWT refresh токен для обновления access токена")


class TokenResponse(BaseModel):
    """Схема ответа с JWT-токенами доступа и обновления.

    Атрибуты:
        access_token (str): Сгенерированный JWT-токен доступа.
        refresh_token (str): JWT-токен для обновления access-токена.
        token_type (str): Тип токена (по умолчанию "bearer").
    """

    access_token: str = Field(..., description="JWT токен доступа")
    refresh_token: str = Field(..., description="JWT токен для обновления access токена")
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
        date (datetime | None): Дата и время операции.
    """

    amount: float = Field(..., gt=0, description="Сумма операции (должна быть больше 0)")
    description: str = Field(..., min_length=1, max_length=255, description="Описание или назначение платежа")
    category: Category = Field(..., description="Категория операции")
    type: TransactionType = Field(..., description="Тип операции: income (доход) или expense (расход)")
    date: datetime | None = Field(default=None, description="Дата транзакции (по умолчанию текущая)")


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
        year (int): Год.
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
# Схемы синхронизации данных оффлайн пользователя с сервером
# ============================================================================


class TransactionSyncItem(BaseModel):
    """Схема отдельной транзакции при пакетной синхронизации."""

    local_id: Optional[int] = Field(default=None, description="Локальный ID на клиенте")
    type: TransactionType = Field(..., description="Тип операции")
    category: Category = Field(..., description="Категория")
    amount: float = Field(..., gt=0, description="Сумма")
    date: datetime = Field(..., description="Дата и время")
    description: str = Field(..., description="Описание")


class BudgetSyncItem(BaseModel):
    """Схема отдельного бюджета при пакетной синхронизации."""

    id: Optional[uuid.UUID] = Field(default=None, description="ID бюджета (если уже создан на сервере)")
    category: Category = Field(..., description="Категория")
    limit_amount: float = Field(default=0.0, ge=0, description="Лимит бюджета")
    month: int = Field(..., ge=1, le=12, description="Месяц")
    year: int = Field(..., ge=2000, le=2100, description="Год")
    is_deleted: bool = Field(default=False, description="Флаг удаления бюджета на клиенте")
    deleted: Optional[bool] = Field(default=None, description="Альтернативный флаг удаления бюджета")

    @property
    def check_deleted(self) -> bool:
        """Проверить флаг удаления."""
        if self.deleted is not None:
            return self.deleted
        return self.is_deleted


class SyncPayload(BaseModel):
    """Схема пакета данных для синхронизации."""

    transactions: List[TransactionSyncItem] = Field(default_factory=list, description="Список транзакций")
    budgets: List[BudgetSyncItem] = Field(default_factory=list, description="Список бюджетов")
    deleted_budget_ids: List[uuid.UUID] = Field(default_factory=list, description="Список ID бюджетов для удаления")
    deleted_budgets: List[BudgetSyncItem] = Field(
        default_factory=list, description="Список объектов бюджетов для удаления по категории и периоду"
    )


class SyncResponse(BaseModel):
    """Схема ответа на синхронизацию."""

    synced_transactions: List[TransactionResponse] = Field(..., description="Синхронизированные транзакции")
    synced_budgets: List[BudgetResponse] = Field(..., description="Синхронизированные бюджеты")


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
