"""Эндпоинт пакетной синхронизации офлайн данных транзакций и бюджетов."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import AppException, BadRequestException, ErrorCode
from app.models.models import Budget, Transaction, User
from app.schemas.schemas import ApiResponse, ErrorResponse, SyncPayload, SyncResponse
from app.services.auth_service import get_current_user
from app.services.budget_service import BudgetService
from logger.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    responses={
        400: {"model": ErrorResponse, "description": "Ошибка пакетной синхронизации (SYNC_FAILED)"},
        401: {"model": ErrorResponse, "description": "Требуется авторизация"},
        403: {"model": ErrorResponse, "description": "Доступ запрещен"},
        422: {"model": ErrorResponse, "description": "Ошибка валидации входных данных"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера при сохранении"},
    }
)


@router.post(
    "/",
    response_model=ApiResponse[SyncResponse],
    status_code=status.HTTP_200_OK,
    summary="Синхронизировать данные",
)
async def sync_data(
    payload: SyncPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"Начало синхронизации для пользователя {current_user.id}, "
        f"Транзакций: {len(payload.transactions)}, "
        f"Бюджетов: {len(payload.budgets)}, "
        f"Удаляемых ID бюджетов: {len(payload.deleted_budget_ids)}, "
        f"Удаляемых бюджетов (объектов): {len(payload.deleted_budgets)}"
    )
    synced_transactions = []
    synced_budgets = []
    budget_service = BudgetService(db)

    try:
        # 1. Сохраняем транзакции
        for item in payload.transactions:
            logger.debug(f"Синхронизация транзакции: {item}")
            db_transaction = Transaction(
                user_id=current_user.id,
                amount=item.amount,
                description=item.description,
                category=item.category,
                type=item.type,
                date=item.date or datetime.now(timezone.utc),
            )
            db.add(db_transaction)
            synced_transactions.append(db_transaction)

        # 2. Удаляем бюджеты по ID из payload.deleted_budget_ids
        for budget_id in payload.deleted_budget_ids:
            logger.debug(f"Удаление бюджета по ID в процессе синхронизации: {budget_id}")
            existing_budget = (
                db.query(Budget)
                .filter(
                    Budget.user_id == current_user.id,
                    Budget.id == budget_id,
                )
                .first()
            )
            if existing_budget:
                db.delete(existing_budget)

        # 3. Удаляем бюджеты из payload.deleted_budgets
        for item in payload.deleted_budgets:
            logger.debug(
                f"Удаление бюджета по категории/периоду из deleted_budgets: {item.category} ({item.month}/{item.year})"
            )
            existing_budget = (
                db.query(Budget)
                .filter(
                    Budget.user_id == current_user.id,
                    Budget.category == item.category,
                    Budget.month == item.month,
                    Budget.year == item.year,
                )
                .first()
            )
            if existing_budget:
                db.delete(existing_budget)

        # 4. Сохраняем, обновляем или удаляем бюджеты из payload.budgets
        for item in payload.budgets:
            if item.check_deleted:
                logger.debug(f"Удаление бюджета при синхронизации: {item.category} ({item.month}/{item.year})")
                existing_budget = (
                    db.query(Budget)
                    .filter(
                        Budget.user_id == current_user.id,
                        Budget.category == item.category,
                        Budget.month == item.month,
                        Budget.year == item.year,
                    )
                    .first()
                )
                if existing_budget:
                    db.delete(existing_budget)
            else:
                existing_budget = (
                    db.query(Budget)
                    .filter(
                        Budget.user_id == current_user.id,
                        Budget.category == item.category,
                        Budget.month == item.month,
                        Budget.year == item.year,
                    )
                    .first()
                )

                if existing_budget:
                    logger.debug(f"Обновление лимита бюджета для {item.category} ({item.month}/{item.year})")
                    existing_budget.limit_amount = item.limit_amount
                    synced_budgets.append(existing_budget)
                else:
                    logger.debug(f"Создание нового бюджета для {item.category} ({item.month}/{item.year})")
                    db_budget = Budget(
                        user_id=current_user.id,
                        category=item.category,
                        limit_amount=item.limit_amount,
                        month=item.month,
                        year=item.year,
                    )
                    db.add(db_budget)
                    synced_budgets.append(db_budget)

        db.commit()
        # Обновляем объекты из БД после коммита
        for b in synced_budgets:
            db.refresh(b)
        for t in synced_transactions:
            db.refresh(t)

        enriched_budgets = [budget_service._enrich(b, current_user.id) for b in synced_budgets]

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Ошибка базы данных при синхронизации пользователя {current_user.id}: {str(e)}",
            exc_info=True,
        )
        raise AppException(
            code=ErrorCode.SYNC_FAILED,
            message="Ошибка при сохранении данных в базу",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"error": str(e)},
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"Непредвиденная ошибка при синхронизации пользователя {current_user.id}: {str(e)}",
            exc_info=True,
        )
        raise BadRequestException(
            code=ErrorCode.SYNC_FAILED,
            message=f"Не удалось обработать запрос синхронизации: {str(e)}",
        )

    logger.info(f"Синхронизация успешно завершена для пользователя {current_user.id}")
    return {
        "status": "success",
        "data": {
            "synced_transactions": synced_transactions,
            "synced_budgets": enriched_budgets,
        },
    }
