"""Интеграционные и функциональные тесты для эндпоинта пакетной синхронизации (/api/v1/sync)."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Budget, Category, Transaction, TransactionType, User


class TestSyncEndpointIntegration:
    """Тесты пакетной офлайн-синхронизации данных."""

    @pytest.mark.asyncio
    async def test_sync_unauthorized(self, client: AsyncClient):
        """Запрос синхронизации без авторизации возвращает 403 Forbidden."""
        response = await client.post("/api/v1/sync/", json={"transactions": [], "budgets": []})
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_sync_create_transactions_and_budgets(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user: User
    ):
        """Пакетная синхронизация создает новые транзакции и бюджеты."""
        user_id = test_user.id
        tx1_id = str(uuid.uuid4())
        tx2_id = str(uuid.uuid4())

        payload = {
            "transactions": [
                {
                    "id": tx1_id,
                    "amount": 750.0,
                    "description": "Обед в кафе",
                    "category": "food",
                    "type": "expense",
                    "date": "2026-10-01T12:00:00Z",
                },
                {
                    "id": tx2_id,
                    "amount": 60000.0,
                    "description": "Аванс",
                    "category": "salary",
                    "type": "income",
                    "date": "2026-10-01T10:00:00Z",
                },
            ],
            "budgets": [
                {
                    "category": "food",
                    "limit_amount": 15000.0,
                    "month": 10,
                    "year": 2026,
                    "check_deleted": False,
                }
            ],
            "deleted_budget_ids": [],
            "deleted_budgets": [],
        }

        response = await client.post("/api/v1/sync/", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()["data"]

        # Проверяем транзакции в ответе
        synced_txs = data["synced_transactions"]
        assert len(synced_txs) == 2
        assert synced_txs[0]["id"] == tx1_id
        assert Decimal(str(synced_txs[0]["amount"])) == Decimal("750.0")

        # Проверяем обогащенные бюджеты в ответе (spent должен учесть расход tx1)
        synced_budgets = data["synced_budgets"]
        assert len(synced_budgets) == 1
        assert synced_budgets[0]["category"] == "food"
        assert Decimal(str(synced_budgets[0]["limit_amount"])) == Decimal("15000.0")
        assert Decimal(str(synced_budgets[0]["spent"])) == Decimal("750.0")
        assert Decimal(str(synced_budgets[0]["remaining"])) == Decimal("14250.0")

        # Проверяем наличие записей в базе данных
        db_tx = (
            await db_session.execute(select(Transaction).filter(Transaction.id == uuid.UUID(tx1_id)))
        ).scalar_one_or_none()
        assert db_tx is not None
        assert db_tx.user_id == user_id

    @pytest.mark.asyncio
    async def test_sync_upsert_existing_transaction(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user: User
    ):
        """Синхронизация обновляет существующую транзакцию при совпадении ID."""
        tx_id = uuid.uuid4()
        existing_tx = Transaction(
            id=tx_id,
            user_id=test_user.id,
            amount=500.0,
            description="Старое описание",
            category=Category.transport,
            type=TransactionType.expense,
            date=datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(existing_tx)
        await db_session.commit()

        payload = {
            "transactions": [
                {
                    "id": str(tx_id),
                    "amount": 650.0,
                    "description": "Обновленное описание",
                    "category": "transport",
                    "type": "expense",
                    "date": "2026-10-01T10:00:00Z",
                }
            ],
            "budgets": [],
            "deleted_budget_ids": [],
            "deleted_budgets": [],
        }

        response = await client.post("/api/v1/sync/", json=payload, headers=auth_headers)
        assert response.status_code == 200

        # Проверяем в базе данных
        db_session.expire_all()
        updated_tx = (await db_session.execute(select(Transaction).filter(Transaction.id == tx_id))).scalar_one_or_none()
        assert updated_tx.amount == 650.0
        assert updated_tx.description == "Обновленное описание"

    @pytest.mark.asyncio
    async def test_sync_delete_budgets(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user: User
    ):
        """Синхронизация удаляет бюджеты по deleted_budget_ids, deleted_budgets и check_deleted."""
        user_id = test_user.id
        # Создаем 3 бюджета
        b1 = Budget(
            user_id=user_id,
            category=Category.food,
            limit_amount=10000.0,
            month=10,
            year=2026,
        )
        b2 = Budget(
            user_id=user_id,
            category=Category.transport,
            limit_amount=5000.0,
            month=10,
            year=2026,
        )
        b3 = Budget(
            user_id=user_id,
            category=Category.entertainment,
            limit_amount=7000.0,
            month=10,
            year=2026,
        )
        db_session.add_all([b1, b2, b3])
        await db_session.commit()
        await db_session.refresh(b1)

        payload = {
            "transactions": [],
            "budgets": [
                # Удаление через флаг is_deleted
                {
                    "category": "entertainment",
                    "limit_amount": 7000.0,
                    "month": 10,
                    "year": 2026,
                    "is_deleted": True,
                }
            ],
            # Удаление по ID
            "deleted_budget_ids": [str(b1.id)],
            # Удаление по категории и периоду
            "deleted_budgets": [
                {
                    "category": "transport",
                    "month": 10,
                    "year": 2026,
                }
            ],
        }

        response = await client.post("/api/v1/sync/", json=payload, headers=auth_headers)
        assert response.status_code == 200

        # Проверяем, что все три бюджета удалены
        db_session.expire_all()
        remaining_budgets = (await db_session.execute(select(Budget).filter(Budget.user_id == user_id))).scalars().all()
        assert len(remaining_budgets) == 0

    @pytest.mark.asyncio
    async def test_sync_batch_multiple_items_and_enrichment(
        self, client: AsyncClient, auth_headers: dict[str, str], db_session: AsyncSession, test_user: User
    ):
        """Пакетная синхронизация 10+ транзакций и нескольких бюджетов корректно рассчитывает агрегаты."""
        tx_items = []
        for i in range(10):
            tx_items.append(
                {
                    "id": str(uuid.uuid4()),
                    "amount": 100.0,
                    "description": f"Exp {i}",
                    "category": "food",
                    "type": "expense",
                    "date": "2026-10-02T10:00:00Z",
                }
            )

        budget_items = [
            {
                "category": "food",
                "limit_amount": 2000.0,
                "month": 10,
                "year": 2026,
            },
            {
                "category": "transport",
                "limit_amount": 1000.0,
                "month": 10,
                "year": 2026,
            },
        ]

        payload = {
            "transactions": tx_items,
            "budgets": budget_items,
            "deleted_budget_ids": [],
            "deleted_budgets": [],
        }

        response = await client.post("/api/v1/sync/", json=payload, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()["data"]

        assert len(data["synced_transactions"]) == 10
        assert len(data["synced_budgets"]) == 2

        food_budget = next(b for b in data["synced_budgets"] if b["category"] == "food")
        transport_budget = next(b for b in data["synced_budgets"] if b["category"] == "transport")

        # 10 транзакций по 100.0 = 1000.0 spent
        assert Decimal(str(food_budget["spent"])) == Decimal("1000.0")
        assert Decimal(str(food_budget["remaining"])) == Decimal("1000.0")
        assert Decimal(str(transport_budget["spent"])) == Decimal("0.00")
        assert Decimal(str(transport_budget["remaining"])) == Decimal("1000.0")
