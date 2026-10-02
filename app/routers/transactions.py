"""Эндпоинты управления финансовыми транзакциями (доходы и расходы)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    ApiResponse,
    BaseResponse,
    ErrorResponse,
    PaginatedResponse,
    TransactionCreate,
    TransactionResponse,
)
from app.services.auth_service import get_current_user
from app.services.transaction_service import TransactionService

router = APIRouter(
    responses={
        400: {"model": ErrorResponse, "description": "Ошибка бизнес-логики"},
        401: {"model": ErrorResponse, "description": "Требуется авторизация"},
        403: {"model": ErrorResponse, "description": "Доступ запрещен"},
        404: {"model": ErrorResponse, "description": "Ресурс не найден"},
        422: {"model": ErrorResponse, "description": "Ошибка валидации входных данных"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
    }
)


@router.post(
    "/",
    response_model=ApiResponse[TransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Добавить новую транзакцию",
)
def create_transaction(
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
    response_model=ApiResponse[PaginatedResponse[TransactionResponse]],
    summary="Получить список транзакций",
)
def list_transactions(
    limit: int = Query(50, ge=1, le=100, description="Количество транзакций на странице (макс. 100)"),
    offset: int = Query(0, ge=0, description="Смещение относительно начала списка"),
    since: datetime | None = None,
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить пагинированный список транзакций пользователя с поддержкой ETag-кэширования."""
    service = TransactionService(db)

    current_etag = service.get_etag(current_user.id, since=since, limit=limit, offset=offset)

    if if_none_match and if_none_match.strip('"') == current_etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    items, total = service.get_all(current_user.id, since=since, limit=limit, offset=offset)
    if response:
        response.headers["ETag"] = f'"{current_etag}"'

    return {
        "status": "success",
        "data": {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.delete(
    "/{transaction_id}",
    response_model=BaseResponse,
    summary="Удалить транзакцию",
)
def delete_transaction(
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
