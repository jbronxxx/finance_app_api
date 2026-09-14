"""Сервис управления бюджетами и расчет фактически израсходованных средств."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Budget, Category, Transaction, TransactionType
from app.schemas.schemas import BudgetCreate, BudgetResponse
from logger.logger import get_logger

logger = get_logger(__name__)


class BudgetService:
    """Класс бизнес-логики для установки бюджетов и подсчета остатков лимитов."""

    def __init__(self, db: Session):
        """Инициализация сервиса с сессией базы данных.

        Аргументы:
            db (Session): Сессия SQLAlchemy.
        """
        self.db = db

    def create(self, user_id: uuid.UUID, payload: BudgetCreate) -> BudgetResponse:
        """Создать новый бюджет или обновить существующий лимит расходов по категории на указанный период.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            payload (BudgetCreate): Параметры создаваемого бюджета (категория, лимит, месяц, год).

        Возвращает:
            BudgetResponse: Обогащенная модель бюджета с расчетом потраченной суммы и остатка.
        """
        existing_budget = (
            self.db.query(Budget)
            .filter(
                Budget.user_id == user_id,
                Budget.category == payload.category,
                Budget.month == payload.month,
                Budget.year == payload.year,
            )
            .first()
        )

        if existing_budget:
            logger.info(f"Обновление существующего бюджета {existing_budget.id} для пользователя {user_id}")
            existing_budget.limit_amount = payload.limit_amount
            self.db.commit()
            self.db.refresh(existing_budget)
            return self._enrich(existing_budget, user_id)

        budget = Budget(
            user_id=user_id,
            category=payload.category,
            limit_amount=payload.limit_amount,
            month=payload.month,
            year=payload.year,
        )
        self.db.add(budget)
        self.db.commit()
        self.db.refresh(budget)
        logger.info(f"Создан новый бюджет: {budget}")
        return self._enrich(budget, user_id)

    def get_by_id(self, user_id: uuid.UUID, budget_id: uuid.UUID) -> BudgetResponse:
        """Получить бюджет по его идентификатору.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            budget_id (uuid.UUID): Уникальный ID бюджета.

        Возвращает:
            BudgetResponse: Модель бюджета с расчетом потраченной суммы и остатка.
        """
        budget = self.db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user_id).first()
        if not budget:
            logger.warning(f"Бюджет {budget_id} не найден для пользователя {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Бюджет не найден",
            )
        return self._enrich(budget, user_id)

    def get_all(self, user_id: uuid.UUID, month: int | None, year: int | None) -> list[BudgetResponse]:
        """Получить список всех бюджетов пользователя с фильтрацией по месяцу и году.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            month (int | None): Номер месяца для фильтрации (опционально).
            year (int | None): Год для фильтрации (опционально).

        Возвращает:
            list[BudgetResponse]: Список бюджетов с актуальными данными по расходам.
        """
        query = self.db.query(Budget).filter(Budget.user_id == user_id)
        if month:
            query = query.filter(Budget.month == month)
        if year:
            query = query.filter(Budget.year == year)
        budgets = query.all()
        logger.info(f"Получено {len(budgets)} бюджетов для пользователя {user_id} с фильтром месяц={month}, год={year}")
        return [self._enrich(b, user_id) for b in budgets]

    def delete(self, user_id: uuid.UUID, budget_id: uuid.UUID) -> None:
        """Удалить бюджет по его идентификатору.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя (для проверки прав доступа).
            budget_id (uuid.UUID): ID удаляемого бюджета.

        Исключения:
            HTTPException (404): Если бюджет с указанным ID не найден у данного пользователя.
        """
        budget = self.db.query(Budget).filter(Budget.id == budget_id, Budget.user_id == user_id).first()
        if not budget:
            logger.warning(f"Попытка удаления несуществующего бюджета {budget_id} для пользователя {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Бюджет не найден",
            )
        self.db.delete(budget)
        self.db.commit()
        logger.info(f"Бюджет удален: {budget_id}")

    def delete_by_category_period(self, user_id: uuid.UUID, category: Category, month: int, year: int) -> bool:
        """Удалить бюджет по категории, месяцу и году.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            category (Category): Категория бюджета.
            month (int): Месяц.
            year (int): Год.

        Возвращает:
            bool: True, если бюджет найден и удален, иначе False.
        """
        budget = (
            self.db.query(Budget)
            .filter(
                Budget.user_id == user_id,
                Budget.category == category,
                Budget.month == month,
                Budget.year == year,
            )
            .first()
        )
        if not budget:
            return False
        self.db.delete(budget)
        self.db.commit()
        logger.info(f"Бюджет удален по категории и периоду: {category} ({month}/{year})")
        return True

    def _enrich(self, budget: Budget, user_id: uuid.UUID) -> BudgetResponse:
        """Обогатить объект бюджета агрегированными данными о фактических расходах.

        Вычислить сумму всех расходных транзакций пользователя по данной категории
        за указанный месяц и год, а также остаток от лимита.

        Аргументы:
            budget (Budget): Сущность бюджета из БД.
            user_id (uuid.UUID): Уникальный ID пользователя.

        Возвращает:
            BudgetResponse: Ответ со значениями spent (потрачено) и remaining (остаток).
        """
        spent = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.user_id == user_id,
                Transaction.category == budget.category,
                Transaction.type == TransactionType.expense,
                func.extract("month", Transaction.date) == budget.month,
                func.extract("year", Transaction.date) == budget.year,
            )
            .scalar()
            or 0.0
        )
        logger.info(f"Расчет расходов для бюджета {budget.id}: потрачено={spent}, лимит={budget.limit_amount}")
        return BudgetResponse(
            id=budget.id,
            category=budget.category,
            limit_amount=budget.limit_amount,
            month=budget.month,
            year=budget.year,
            spent=spent,
            remaining=max(0.0, budget.limit_amount - spent),
        )
