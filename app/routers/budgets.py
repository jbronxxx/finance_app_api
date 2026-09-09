"""Эндпоинты управления бюджетами и лимитами расходов по категориям."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import ApiResponse, BudgetCreate, BudgetResponse
from app.services.auth_service import get_current_user
from app.services.budget_service import BudgetService

router = APIRouter()


# TODO: Добавить проверку на существование бюджета по категории,
#  месяцу и году перед созданием нового бюджета (POST /budgets)
# TODO: Добавить эндпоинт для обновления бюджета по категории
#  (PATCH /budgets/{budget_id})
# TODO: Добавить эндпоинт для удаления бюджета по категории
#  (DELETE /budgets/{budget_id})
# TODO: Добавить эндпоинт для получения бюджета по категории
#  (GET /budgets/{budget_id})
# TODO: Добавить эндпоинт для получения бюджета по категории и месяцу
#  (GET /budgets/{category_id}/{month}/{year})
# TODO: Добавить эндпоинт для получения бюджета по категории и году
#  (GET /budgets/{category_id}/{year})
# TODO: Добавить эндпоинт для получения бюджета по категории, месяцу и году
#  (GET /budgets/{category_id}/{month}/{year})
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

    Аргументы:
        payload (BudgetCreate): Параметры бюджета (категория, сумма лимита, месяц, год).
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        ApiResponse[BudgetResponse]: Созданный бюджет с рассчитанным остатком и израсходованной суммой.
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
        ApiResponse[list[BudgetResponse]]: Список бюджетов с актуальными данными по расходам.
    """
    service = BudgetService(db)
    budgets = service.get_all(current_user.id, month=month, year=year)
    return {"status": "success", "data": budgets}
