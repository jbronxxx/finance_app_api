"""Юнит и интеграционные тесты для BudgetService и эндпоинтов бюджетов."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.exceptions import NotFoundException
from app.models.models import Category, TransactionType, User
from app.schemas.schemas import BudgetCreate, TransactionCreate
from app.services.budget_service import BudgetService
from app.services.transaction_service import TransactionService


class TestBudgetServiceUnit:
    """Юнит-тесты бизнес-логики BudgetService."""

    def test_create_and_enrich_budget_no_expenses(self, db_session: Session, test_user: User):
        """Создание бюджета при отсутствии расходов возвращает spent=0.0 и remaining=limit."""
        service = BudgetService(db_session)
        payload = BudgetCreate(
            category=Category.food,
            limit_amount=15000.0,
            month=10,
            year=2026,
        )
        budget_resp = service.create(test_user.id, payload)

        assert budget_resp.id is not None
        assert budget_resp.category == Category.food
        assert budget_resp.limit_amount == 15000.0
        assert budget_resp.month == 10
        assert budget_resp.year == 2026
        assert budget_resp.spent == 0.0
        assert budget_resp.remaining == 15000.0

    def test_create_existing_budget_updates_limit(self, db_session: Session, test_user: User):
        """Повторный вызов create с теми же категорией/месяцем/годом обновляет лимит."""
        service = BudgetService(db_session)
        payload1 = BudgetCreate(category=Category.food, limit_amount=10000.0, month=10, year=2026)
        b1 = service.create(test_user.id, payload1)

        payload2 = BudgetCreate(category=Category.food, limit_amount=20000.0, month=10, year=2026)
        b2 = service.create(test_user.id, payload2)

        assert b1.id == b2.id
        assert b2.limit_amount == 20000.0
        assert b2.remaining == 20000.0

    def test_spent_and_remaining_calculation(self, db_session: Session, test_user: User):
        """Расчет spent и remaining учитывает только расходы соответствующей категории и периода."""
        tx_service = TransactionService(db_session)
        budget_service = BudgetService(db_session)

        # Расход за октябрь 2026 по категории food (должен учитываться)
        tx_service.create(
            test_user.id,
            TransactionCreate(
                amount=3000.0,
                description="Супермаркет",
                category=Category.food,
                type=TransactionType.expense,
                date=datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )
        # Доход за октябрь 2026 по категории food (не должен учитываться)
        tx_service.create(
            test_user.id,
            TransactionCreate(
                amount=500.0,
                description="Кешбэк продукты",
                category=Category.food,
                type=TransactionType.income,
                date=datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )
        # Расход за сентябрь 2026 (другой месяц, не должен учитываться)
        tx_service.create(
            test_user.id,
            TransactionCreate(
                amount=2000.0,
                description="Прошлый месяц",
                category=Category.food,
                type=TransactionType.expense,
                date=datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )
        # Расход по другой категории (transport, не должен учитываться)
        tx_service.create(
            test_user.id,
            TransactionCreate(
                amount=1500.0,
                description="Такси",
                category=Category.transport,
                type=TransactionType.expense,
                date=datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )

        budget = budget_service.create(
            test_user.id,
            BudgetCreate(category=Category.food, limit_amount=10000.0, month=10, year=2026),
        )

        assert budget.spent == 3000.0
        assert budget.remaining == 7000.0

    def test_overspent_budget_remaining_zero(self, db_session: Session, test_user: User):
        """Если расходы превышают лимит, remaining равен 0.0 (не уходит в минус)."""
        tx_service = TransactionService(db_session)
        budget_service = BudgetService(db_session)

        tx_service.create(
            test_user.id,
            TransactionCreate(
                amount=12000.0,
                description="Большой банкет",
                category=Category.food,
                type=TransactionType.expense,
                date=datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )

        budget = budget_service.create(
            test_user.id,
            BudgetCreate(category=Category.food, limit_amount=10000.0, month=10, year=2026),
        )

        assert budget.spent == 12000.0
        assert budget.remaining == 0.0

    def test_get_by_id_success_and_not_found(self, db_session: Session, test_user: User):
        """Получение бюджета по ID и обработка отсутствующего ID."""
        service = BudgetService(db_session)
        created = service.create(
            test_user.id,
            BudgetCreate(category=Category.transport, limit_amount=5000.0, month=10, year=2026),
        )

        fetched = service.get_by_id(test_user.id, created.id)
        assert fetched.id == created.id
        assert fetched.category == Category.transport

        with pytest.raises(NotFoundException) as exc_info:
            service.get_by_id(test_user.id, uuid.uuid4())
        assert exc_info.value.code == "BUDGET_NOT_FOUND"

    def test_delete_by_id_and_by_category_period(self, db_session: Session, test_user: User):
        """Удаление бюджета по ID и по (категория, месяц, год)."""
        service = BudgetService(db_session)
        b1 = service.create(
            test_user.id,
            BudgetCreate(category=Category.transport, limit_amount=5000.0, month=10, year=2026),
        )
        service.create(
            test_user.id,
            BudgetCreate(category=Category.entertainment, limit_amount=7000.0, month=10, year=2026),
        )

        # Удаляем по ID
        service.delete(test_user.id, b1.id)
        with pytest.raises(NotFoundException):
            service.get_by_id(test_user.id, b1.id)

        # Удаляем по категории и периоду
        deleted = service.delete_by_category_period(test_user.id, Category.entertainment, 10, 2026)
        assert deleted is True

        # Повторное удаление возвращает False
        deleted_again = service.delete_by_category_period(test_user.id, Category.entertainment, 10, 2026)
        assert deleted_again is False


class TestBudgetEndpointsIntegration:
    """Интеграционные тесты для эндпоинтов /api/v1/budgets/."""

    def test_budget_full_flow(self, client, auth_headers: dict[str, str]):
        """Создание, получение списка, получение по ID и удаление бюджета через API."""
        payload = {
            "category": "food",
            "limit_amount": 15000.0,
            "month": 10,
            "year": 2026,
        }
        # 1. Create budget
        create_res = client.post("/api/v1/budgets/", json=payload, headers=auth_headers)
        assert create_res.status_code == 201
        budget_data = create_res.json()["data"]
        budget_id = budget_data["id"]
        assert Decimal(str(budget_data["limit_amount"])) == Decimal("15000.00")

        # 2. Get list with query params
        list_res = client.get("/api/v1/budgets/?month=10&year=2026", headers=auth_headers)
        assert list_res.status_code == 200
        budgets_list = list_res.json()["data"]
        assert len(budgets_list) == 1
        assert budgets_list[0]["id"] == budget_id
        assert "ETag" in list_res.headers

        # 3. Get by ID
        get_res = client.get(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["data"]["id"] == budget_id

        # 4. Delete by category and period
        del_cat_res = client.delete("/api/v1/budgets/category/food/10/2026", headers=auth_headers)
        assert del_cat_res.status_code == 200
        assert del_cat_res.json()["status"] == "success"

        # 5. Verify deleted
        get_after_del = client.get(f"/api/v1/budgets/{budget_id}", headers=auth_headers)
        assert get_after_del.status_code == 404
