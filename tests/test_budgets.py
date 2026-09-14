"""Модуль автоматических тестов для проверки эндпоинтов удаления и синхронизации бюджетов.

Запуск тестов: pytest tests/ -v
"""

import uuid

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestBudgets:
    """Набор тестов для роутера бюджетов (/api/v1/budgets)."""

    def test_delete_budget_unauthorized(self):
        """Попытка удаления бюджета без токена возвращает 403 Forbidden."""
        random_id = uuid.uuid4()
        response = client.delete(f"/api/v1/budgets/{random_id}")
        assert response.status_code == 403

    def test_delete_budget_by_category_unauthorized(self):
        """Попытка удаления бюджета по категории без токена возвращает 403 Forbidden."""
        response = client.delete("/api/v1/budgets/category/food/9/2026")
        assert response.status_code == 403

    def test_get_budget_by_id_unauthorized(self):
        """Запрос бюджета по ID без токена возвращает 403 Forbidden."""
        random_id = uuid.uuid4()
        response = client.get(f"/api/v1/budgets/{random_id}")
        assert response.status_code == 403
