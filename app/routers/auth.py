"""Эндпоинты авторизации и аутентификации пользователей."""

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import (
    ApiResponse,
    BaseResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import AuthService, get_current_user

router = APIRouter()


@router.post(
    "/register",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(payload: UserRegister, db: Session = Depends(get_db)) -> ApiResponse:
    """Зарегистрировать нового пользователя в системе.

    Аргументы:
        payload (UserRegister): Данные для регистрации (email, пароль, имя).
        db (Session): Сессия базы данных (инъекция через Depends).

    Возвращает:
        ApiResponse[UserResponse]: Созданный профиль пользователя (без пароля).
    """
    service = AuthService(db)
    user = service.register(payload)
    return {"status": "success", "data": user}


# TODO: Добавить обработку истекшего токена при попытке доступа к защищенным эндпоинтам
@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Вход в систему и получение токена",
)
async def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    """Аутентификация пользователя по email и паролю с возвратом JWT-токена.

    Аргументы:
        payload (UserLogin): Учетные данные пользователя (email, пароль).
        db (Session): Сессия базы данных (инъекция через Depends).

    Возвращает:
        ApiResponse[TokenResponse]: JWT токен доступа (Bearer token).
    """
    service = AuthService(db)
    token = service.login(payload)
    return {"status": "success", "data": token}


@router.post(
    "/logout",
    response_model=BaseResponse,
    summary="Выход из системы и деактивация токена",
)
async def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials: HTTPBearer = Depends(AuthService.bearer_scheme),
) -> BaseResponse:
    """Выйти из системы, удаляя токен из базы данных.

    Аргументы:
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий авторизованный пользователь.
    """
    service = AuthService(db)
    service.logout(current_user.id, credentials.credentials)
    return {"status": "success", "message": "Successfully logged out"}


# @router.post(
#     "/refresh_token",
#     response


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Получение информации о текущем пользователе",
)
async def auth_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Получить информацию о текущем пользователе."""
    return {"status": "success", "data": current_user}
