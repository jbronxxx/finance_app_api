"""Эндпоинты управления финансовыми транзакциями (доходы и расходы)."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    ApiResponse,
    BaseResponse,
    TransactionCreate,
    TransactionResponse,
)
from app.services.auth_service import get_current_user
from app.services.transaction_service import TransactionService

router = APIRouter()


@router.post(
    "/",
    response_model=ApiResponse[TransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новую транзакцию",
)
async def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новую транзакцию (доход или расход) для авторизованного пользователя.

    Аргументы:
        payload (TransactionCreate): Данные транзакции (сумма, категория, тип, описание).
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        ApiResponse[TransactionResponse]: Сохраненная транзакция с присвоенным ID и временной меткой.
    """
    service = TransactionService(db)
    transaction = service.create(current_user.id, payload)
    return {"status": "success", "data": transaction}


@router.get(
    "/",
    response_model=ApiResponse[list[TransactionResponse]],
    summary="Получить список транзакций",
)
async def list_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить всю историю доходов и расходов текущего пользователя.

    Аргументы:
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        ApiResponse[list[TransactionResponse]]: Список всех транзакций пользователя, отсортированный по дате.
    """
    service = TransactionService(db)
    transactions = service.get_all(current_user.id)
    return {"status": "success", "data": transactions}


@router.delete(
    "/{transaction_id}",
    response_model=BaseResponse,
    summary="Удалить транзакцию",
)
async def delete_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить запись транзакции по её идентификатору.

    Аргументы:
        transaction_id (uuid.UUID): Уникальный ID удаляемой транзакции.
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.
    """
    service = TransactionService(db)
    service.delete(current_user.id, transaction_id)
    return {"status": "success", "message": "Transaction deleted successfully"}
