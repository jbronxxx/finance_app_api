from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Budget, Transaction, User
from app.schemas.schemas import ApiResponse, SyncPayload, SyncResponse
from app.services.auth_service import get_current_user
from logger.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=ApiResponse[SyncResponse],
    status_code=status.HTTP_200_OK,
    summary="Синхронизовать данные",
)
async def sync_data(
    payload: SyncPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"Начало синхронизации для пользователя {current_user.id}, "
        f"Транзакций: {len(payload.transactions)}, "
        f"Бюджетов: {len(payload.budgets)}"
    )
    synced_transactions = []
    synced_budgets = []

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

        # 2. Сохраняем или обновляем бюджеты
        for item in payload.budgets:
            # Ищем бюджет по уникальным полям (без учета суммы лимита)
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

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Ошибка базы данных при синхронизации пользователя {current_user.id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при сохранении данных в базу",
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"Непредвиденная ошибка при синхронизации пользователя {current_user.id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось обработать запрос: {str(e)}",
        )

    logger.info(f"Синхронизация успешно завершена для пользователя {current_user.id}")
    return {
        "status": "success",
        "data": {
            "synced_transactions": synced_transactions,
            "synced_budgets": synced_budgets,
        },
    }
