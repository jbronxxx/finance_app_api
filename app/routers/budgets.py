"""Эндпоинты управления бюджетами и лимитами расходов по категориям."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Category, User
from app.schemas.schemas import ApiResponse, BaseResponse, BudgetCreate, BudgetResponse
from app.services.auth_service import get_current_user
from app.services.budget_service import BudgetService

router = APIRouter()


@router.post(
    "/",
    response_model=ApiResponse[BudgetResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Установить бюджет по категории",
)
async def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Установить лимит бюджета по определенной категории на месяц и год.

    Если бюджет для выбранной категории на этот период уже существует,
    его лимит обновляется.
    """
    service = BudgetService(db)
    budget = service.create(current_user.id, payload)
    return {"status": "success", "data": budget}


@router.get(
    "/",
    response_model=ApiResponse[list[BudgetResponse]],
    summary="Получить список бюджетов",
)
async def list_budgets(
    month: int | None = Query(default=None, ge=1, le=12, description="Фильтр по номеру месяца (1-12)"),
    year: int | None = Query(default=None, ge=2000, le=2100, description="Фильтр по году"),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
    response: Response = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список бюджетов с автоматическим расчетом израсходованных средств и остатка лимита."""
    service = BudgetService(db)

    current_etag = service.get_etag(current_user.id, month=month, year=year)

    if if_none_match and if_none_match.strip('"') == current_etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)

    budgets = service.get_all(current_user.id, month=month, year=year)
    if response:
        response.headers["ETag"] = f'"{current_etag}"'

    return {"status": "success", "data": budgets}


@router.get(
    "/{budget_id}",
    response_model=ApiResponse[BudgetResponse],
    summary="Получить бюджет по ID",
)
async def get_budget(
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить информацию о бюджете по его уникальному ID."""
    service = BudgetService(db)
    budget = service.get_by_id(current_user.id, budget_id)
    return {"status": "success", "data": budget}


@router.delete(
    "/{budget_id}",
    response_model=BaseResponse,
    summary="Удалить бюджет по ID",
)
async def delete_budget(
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить запись бюджета по её уникальному идентификатору."""
    service = BudgetService(db)
    service.delete(current_user.id, budget_id)
    return {"status": "success", "message": "Бюджет успешно удален"}


@router.delete(
    "/category/{category}/{month}/{year}",
    response_model=BaseResponse,
    summary="Удалить бюджет по категории, месяцу и году",
)
async def delete_budget_by_category_period(
    category: Category,
    month: int,
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить бюджет по названию категории, месяцу и году."""
    service = BudgetService(db)
    deleted = service.delete_by_category_period(current_user.id, category, month, year)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Бюджет не найден",
        )
    return {"status": "success", "message": "Бюджет успешно удален"}
