"""Юнит и интеграционные тесты для AuthService и эндпоинтов авторизации."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.exceptions import BadRequestException, NotFoundException, UnauthorizedException
from app.models.models import Token, User
from app.schemas.schemas import UserLogin, UserRegister
from app.services.auth_service import AuthService, get_current_user


class TestAuthServiceUnit:
    """Юнит-тесты бизнес-логики AuthService."""

    def test_register_success(self, db_session: Session):
        """Успешная регистрация нового пользователя."""
        service = AuthService(db_session)
        payload = UserRegister(
            email=f"newuser_{uuid.uuid4().hex[:6]}@example.com",
            password="SecurePassword123!",
            name="New User",
        )
        user = service.register(payload)

        assert user.id is not None
        assert user.email == payload.email
        assert user.name == payload.name
        assert user.hashed_password != payload.password

    def test_register_duplicate_email(self, db_session: Session, test_user: User):
        """Регистрация с существующим email вызывает BadRequestException."""
        service = AuthService(db_session)
        payload = UserRegister(
            email=test_user.email,
            password="AnotherPassword123!",
            name="Duplicate User",
        )
        with pytest.raises(BadRequestException) as exc_info:
            service.register(payload)
        assert exc_info.value.code == "USER_ALREADY_EXISTS"

    def test_login_success(self, db_session: Session):
        """Успешный вход пользователя с валидными учетными данными."""
        service = AuthService(db_session)
        email = f"logintest_{uuid.uuid4().hex[:6]}@example.com"
        password = "ValidPassword123!"
        service.register(UserRegister(email=email, password=password, name="Login User"))

        tokens = service.login(UserLogin(email=email, password=password))
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.token_type == "bearer"

    def test_login_invalid_password(self, db_session: Session, test_user: User):
        """Попытка входа с неверным паролем вызывает UnauthorizedException."""
        service = AuthService(db_session)
        with pytest.raises(UnauthorizedException) as exc_info:
            service.login(UserLogin(email=test_user.email, password="WrongPassword!"))
        assert exc_info.value.code == "INVALID_CREDENTIALS"

    def test_login_nonexistent_user(self, db_session: Session):
        """Попытка входа с несуществующим email вызывает UnauthorizedException."""
        service = AuthService(db_session)
        with pytest.raises(UnauthorizedException) as exc_info:
            service.login(UserLogin(email="nonexistent@example.com", password="Password123!"))
        assert exc_info.value.code == "INVALID_CREDENTIALS"

    def test_refresh_tokens_success(self, db_session: Session, test_user: User):
        """Успешная ротация токенов по refresh-токену."""
        service = AuthService(db_session)
        refresh_token = service.create_refresh_token(test_user.id)

        new_tokens = service.refresh_tokens(refresh_token)
        assert new_tokens.access_token is not None
        assert new_tokens.refresh_token is not None
        assert new_tokens.refresh_token != refresh_token

        # Старый refresh токен должен быть revoked
        old_token = db_session.query(Token).filter(Token.token == refresh_token).first()
        assert old_token is not None
        assert old_token.status == "revoked"

    def test_refresh_tokens_revoked(self, db_session: Session, test_user: User):
        """Попытка обновить токены отозванным refresh-токеном вызывает 401."""
        service = AuthService(db_session)
        refresh_token = service.create_refresh_token(test_user.id)
        # Отзываем токен
        db_token = db_session.query(Token).filter(Token.token == refresh_token).first()
        db_token.status = "revoked"
        db_session.commit()

        with pytest.raises(UnauthorizedException) as exc_info:
            service.refresh_tokens(refresh_token)
        assert exc_info.value.code == "TOKEN_REVOKED"

    def test_refresh_tokens_expired(self, db_session: Session, test_user: User):
        """Попытка обновить токены истекшим refresh-токеном вызывает 401."""
        service = AuthService(db_session)
        refresh_token = service.create_refresh_token(test_user.id)

        # Устанавливаем дату истечения в прошлом
        db_token = db_session.query(Token).filter(Token.token == refresh_token).first()
        db_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.commit()

        with pytest.raises(UnauthorizedException) as exc_info:
            service.refresh_tokens(refresh_token)
        assert exc_info.value.code == "EXPIRED_TOKEN"

    def test_refresh_tokens_with_access_token(self, db_session: Session, test_user: User):
        """Попытка передать access-токен в метод refresh_tokens вызывает ошибку типа токена."""
        service = AuthService(db_session)
        access_token = service.create_access_token(test_user.id)

        with pytest.raises(UnauthorizedException) as exc_info:
            service.refresh_tokens(access_token)
        assert exc_info.value.code == "INVALID_TOKEN"

    def test_logout(self, db_session: Session, test_user: User):
        """Выход из системы помечает токен как revoked."""
        service = AuthService(db_session)
        token_str = service.create_access_token(test_user.id)

        service.logout(test_user.id, token_str)

        token_record = db_session.query(Token).filter(Token.token == token_str).first()
        assert token_record.status == "revoked"

    def test_logout_nonexistent_token(self, db_session: Session, test_user: User):
        """Попытка деактивации несуществующего токена вызывает NotFoundException."""
        service = AuthService(db_session)
        with pytest.raises(NotFoundException) as exc_info:
            service.logout(test_user.id, "nonexistent-token")
        assert exc_info.value.code == "TOKEN_NOT_FOUND"


class TestGetCurrentUserDependency:
    """Тесты зависимости get_current_user."""

    def test_valid_token(self, db_session: Session, test_user: User):
        """Валидный токен успешно возвращает пользователя."""
        service = AuthService(db_session)
        token_str = service.create_access_token(test_user.id)

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_str)
        user = get_current_user(credentials=creds, db=db_session)
        assert user.id == test_user.id
        assert user.email == test_user.email

    def test_revoked_token(self, db_session: Session, test_user: User):
        """Отозванный токен вызывает UnauthorizedException."""
        service = AuthService(db_session)
        token_str = service.create_access_token(test_user.id)
        service.logout(test_user.id, token_str)

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_str)
        with pytest.raises(UnauthorizedException) as exc_info:
            get_current_user(credentials=creds, db=db_session)
        assert exc_info.value.code == "TOKEN_REVOKED"

    def test_expired_token(self, db_session: Session, test_user: User):
        """Истекший токен вызывает UnauthorizedException."""
        service = AuthService(db_session)
        token_str = service.create_access_token(test_user.id)

        db_token = db_session.query(Token).filter(Token.token == token_str).first()
        db_token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db_session.commit()

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_str)
        with pytest.raises(UnauthorizedException) as exc_info:
            get_current_user(credentials=creds, db=db_session)
        assert exc_info.value.code == "EXPIRED_TOKEN"


class TestAuthEndpointsIntegration:
    """Интеграционные тесты для эндпоинтов /api/v1/auth/."""

    def test_register_endpoint(self, client):
        """POST /api/v1/auth/register возвращает 201 и профиль пользователя."""
        payload = {
            "email": f"api_user_{uuid.uuid4().hex[:6]}@example.com",
            "password": "Password123!",
            "name": "Api User",
        }
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["email"] == payload["email"]
        assert data["data"]["name"] == payload["name"]
        assert "hashed_password" not in data["data"]

    def test_login_and_me_endpoint(self, client, db_session: Session):
        """POST /api/v1/auth/login возвращает токены, GET /api/v1/auth/me возвращает профиль."""
        email = f"flow_user_{uuid.uuid4().hex[:6]}@example.com"
        password = "Password123!"
        AuthService(db_session).register(UserRegister(email=email, password=password, name="Flow User"))

        # Login
        login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200
        tokens = login_res.json()["data"]
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # GET /me with access token
        headers = {"Authorization": f"Bearer {access_token}"}
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["data"]["email"] == email

        # Refresh tokens
        ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert ref_res.status_code == 200
        assert ref_res.json()["data"]["access_token"] is not None

        # Logout
        logout_res = client.post("/api/v1/auth/logout", headers=headers)
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "success"

        # После логаута старый access token недействителен
        me_after_logout = client.get("/api/v1/auth/me", headers=headers)
        assert me_after_logout.status_code == 401
