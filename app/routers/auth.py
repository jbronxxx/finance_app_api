"""Эндпоинты авторизации и аутентификации пользователей."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Зарегистрировать нового пользователя в системе.

    Аргументы:
        payload (UserRegister): Данные для регистрации (email, пароль, имя).
        db (Session): Сессия базы данных (инъекция через Depends).

    Возвращает:
        UserResponse: Созданный профиль пользователя (без пароля).
    """
    service = AuthService(db)
    user = service.register(payload)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход в систему и получение токена",
)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Аутентификация пользователя по email и паролю с возвратом JWT-токена.

    Аргументы:
        payload (UserLogin): Учетные данные пользователя (email, пароль).
        db (Session): Сессия базы данных (инъекция через Depends).

    Возвращает:
        TokenResponse: JWT токен доступа (Bearer token).
    """
    service = AuthService(db)
    token = service.login(payload)
    return token
