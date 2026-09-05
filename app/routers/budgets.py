"""Эндпоинты управления бюджетами и лимитами расходов по категориям."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import BudgetCreate, BudgetResponse
from app.services.auth_service import get_current_user
from app.services.budget_service import BudgetService

router = APIRouter()


@router.post(
    "/",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Установить бюджет по категории",
)
async def create_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Установить лимит бюджета по определенной категории на месяц и год.

    Аргументы:
        payload (BudgetCreate): Параметры бюджета (категория, сумма лимита, месяц, год).
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        BudgetResponse: Созданный бюджет с рассчитанным остатком и израсходованной суммой.
    """
    service = BudgetService(db)
    return service.create(current_user.id, payload)


@router.get(
    "/",
    response_model=list[BudgetResponse],
    summary="Получить список бюджетов",
)
async def list_budgets(
    month: int | None = Query(
        default=None, ge=1, le=12, description="Фильтр по номеру месяца (1-12)"
    ),
    year: int | None = Query(default=None, ge=2000, le=2100, description="Фильтр по году"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить список бюджетов с автоматическим расчетом израсходованных средств и остатка лимита.

    Аргументы:
        month (int | None): Номер месяца для фильтрации (опционально).
        year (int | None): Год для фильтрации (опционально).
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        list[BudgetResponse]: Список бюджетов с актуальными данными по расходам.
    """
    service = BudgetService(db)
    return service.get_all(current_user.id, month=month, year=year)
