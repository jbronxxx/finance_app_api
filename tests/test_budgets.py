"""Модуль автоматических тестов для проверки эндпоинтов удаления и синхронизации бюджетов.

Запуск тестов: pytest tests/ -v
"""

import uuid

import pytest
from httpx import AsyncClient


class TestBudgets:
    """Набор тестов для роутера бюджетов (/api/v1/budgets)."""

    @pytest.mark.asyncio
    async def test_delete_budget_unauthorized(self, client: AsyncClient):
        """Попытка удаления бюджета без токена возвращает 403 Forbidden."""
        random_id = uuid.uuid4()
        response = await client.delete(f"/api/v1/budgets/{random_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_budget_by_category_unauthorized(self, client: AsyncClient):
        """Попытка удаления бюджета по категории без токена возвращает 403 Forbidden."""
        response = await client.delete("/api/v1/budgets/category/food/9/2026")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_budget_by_id_unauthorized(self, client: AsyncClient):
        """Запрос бюджета по ID без токена возвращает 403 Forbidden."""
        random_id = uuid.uuid4()
        response = await client.get(f"/api/v1/budgets/{random_id}")
        assert response.status_code == 403
