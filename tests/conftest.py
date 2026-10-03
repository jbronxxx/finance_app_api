"""Модуль общих фикстур pytest для изолированного тестирования приложения."""

import uuid
from unittest.mock import patch

import bcrypt
import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.models import User
from app.services.auth_service import AuthService
from main import app

# Создаем in-memory базу SQLite с пулом StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Пересоздание всех таблиц перед каждым тестом для полной изоляции."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Session:
    """Фикстура сессии базы данных для каждого теста."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Фикстура TestClient с переопределенной сессией базы данных."""

    def _override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Фикстура созданного тестового пользователя в базе данных."""
    user_id = uuid.uuid4()
    hashed_pwd = bcrypt.hashpw("Password123!".encode(), bcrypt.gensalt()).decode()
    user = User(
        id=user_id,
        email=f"user_{user_id.hex[:8]}@example.com",
        name="Test User",
        hashed_password=hashed_pwd,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(db_session: Session, test_user: User) -> str:
    """Фикстура активного JWT access-токена для тестового пользователя."""
    auth_service = AuthService(db_session)
    return auth_service.create_access_token(test_user.id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Фикстура HTTP-заголовков с Bearer-токеном авторизации."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(autouse=True)
def mock_redis_client():
    """Фикстура для подмены redis_client в AIService на FakeAsyncRedis."""
    fake_redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    with patch("app.services.ai_service.redis_client", fake_redis):
        yield fake_redis
