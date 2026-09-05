"""Сервис управления бюджетами и расчет фактически израсходованных средств."""

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.models import Budget, Transaction, TransactionType
from app.schemas.schemas import BudgetCreate, BudgetResponse


class BudgetService:
    """Класс бизнес-логики для установки бюджетов и подсчета остатков лимитов."""

    def __init__(self, db: Session):
        """Инициализация сервиса с сессией базы данных.

        Аргументы:
            db (Session): Сессия SQLAlchemy.
        """
        self.db = db

    def create(self, user_id: uuid.UUID, payload: BudgetCreate) -> BudgetResponse:
        """Создать новый бюджет (лимит расходов) по категории на указанный период.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
            payload (BudgetCreate): Параметры создаваемого бюджета (категория, лимит, месяц, год).

        Возвращает:
            BudgetResponse: Обогащенная модель бюджета с расчетом потраченной суммы и остатка.
        """
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
        return self._enrich(budget, user_id)

    def get_all(
        self, user_id: uuid.UUID, month: int | None, year: int | None
    ) -> list[BudgetResponse]:
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
        return [self._enrich(b, user_id) for b in budgets]

    def _enrich(self, budget: Budget, user_id: uuid.UUID) -> BudgetResponse:
        """Обогатить объект бюджета агрегированными данными о фактических расходах.

        Вычисляет сумму всех расходных транзакций пользователя по данной категории
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
        return BudgetResponse(
            id=budget.id,
            category=budget.category,
            limit_amount=budget.limit_amount,
            month=budget.month,
            year=budget.year,
            spent=spent,
            remaining=max(0.0, budget.limit_amount - spent),
        )
