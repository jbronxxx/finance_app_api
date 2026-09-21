"""Модуль тестов для проверки единого контракта ошибок API и строковых кодов ошибок."""

import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.database import get_db
from app.exceptions import ErrorCode
from main import app

client = TestClient(app)


class TestErrorContract:
    """Проверка структуры ErrorResponse: status, code, message, details."""

    def test_unauthorized_error_contract(self):
        """Проверка структуры ошибки при отсутствии токена авторизации (403)."""
        response = client.get("/api/v1/transactions/")
        assert response.status_code == 403
        data = response.json()
        assert data["status"] == "error"
        assert data["code"] == ErrorCode.FORBIDDEN
        assert "message" in data
        assert isinstance(data["message"], str)

    def test_validation_error_contract(self):
        """Проверка структуры ошибки при невалидных входных данных (422)."""
        # Передаем невалидное тело для регистрации (пустой пароль, некорректный email)
        response = client.post("/api/v1/auth/register", json={"email": "not-an-email", "password": "123"})
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == "error"
        assert data["code"] == ErrorCode.VALIDATION_ERROR
        assert "message" in data
        assert "details" in data
        assert "fields" in data["details"]

    def test_login_invalid_credentials_error_code(self):
        """Проверка кода ошибки INVALID_CREDENTIALS при неверном логине/пароле."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = client.post(
                "/api/v1/auth/login",
                json={"email": "nonexistent@example.com", "password": "wrongpassword"},
            )
            assert response.status_code == 401
            data = response.json()
            assert data["status"] == "error"
            assert data["code"] == ErrorCode.INVALID_CREDENTIALS
            assert data["message"] == "Неверный email или пароль"
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_not_found_error_contract(self):
        """Проверка структуры ошибки 404 (несуществующий URL маршрут)."""
        random_endpoint = f"/api/v1/unknown-route-{uuid.uuid4()}"
        response = client.get(random_endpoint)
        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert data["code"] == ErrorCode.NOT_FOUND
        assert "message" in data
