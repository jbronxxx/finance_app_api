"""Модуль автоматических тестов для проверки эндпоинтов API и авторизации.

Запуск тестов: pytest tests/ -v
"""

from fastapi.testclient import TestClient

from main import app

# Тестовый HTTP-клиент FastAPI
client = TestClient(app)


def get_auth_headers(token: str = "test-token") -> dict:
    """Сформировать HTTP-заголовки авторизации с Bearer токеном.

    Аргументы:
        token (str, optional): Значение токена. По умолчанию "test-token".

    Возвращает:
        dict: Словарь с заголовком Authorization.
    """
    return {"Authorization": f"Bearer {token}"}


class TestTransactions:
    """Набор тестов для роутера транзакций (/api/v1/transactions)."""

    def test_create_transaction_unauthorized(self):
        """Попытка создания транзакции без токена возвращает 403 Forbidden."""
        payload = {
            "amount": 500.0,
            "description": "Кофе",
            "category": "food",
            "type": "expense",
        }
        response = client.post("/api/v1/transactions/", json=payload)
        assert response.status_code == 403

    def test_list_transactions_unauthorized(self):
        """Запрос списка транзакций без токена возвращает 403 Forbidden."""
        response = client.get("/api/v1/transactions/")
        assert response.status_code == 403

    def test_health_check(self):
        """Эндпоинт /health всегда доступен публично и возвращает 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestBudgets:
    """Набор тестов для роутера бюджетов (/api/v1/budgets)."""

    def test_list_budgets_unauthorized(self):
        """Запрос списка бюджетов без токена возвращает 403 Forbidden."""
        response = client.get("/api/v1/budgets/")
        assert response.status_code == 403

    def test_create_budget_unauthorized(self):
        """Попытка создания бюджета без токена возвращает 403 Forbidden."""
        payload = {
            "category": "food",
            "limit_amount": 10000.0,
            "month": 9,
            "year": 2026,
        }
        response = client.post("/api/v1/budgets/", json=payload)
        assert response.status_code == 403


class TestInsights:
    """Набор тестов для роутера AI-инсайтов (/api/v1/insights)."""

    def test_insights_unauthorized(self):
        """Запрос AI-инсайтов без токена возвращает 403 Forbidden."""
        response = client.get("/api/v1/insights/")
        assert response.status_code == 403
