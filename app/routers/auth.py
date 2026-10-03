"""Эндпоинты авторизации и аутентификации пользователей."""

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.models import User
from app.schemas.schemas import (
    ApiResponse,
    BaseResponse,
    ErrorResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import AuthService, get_current_user

router = APIRouter(
    responses={
        400: {"model": ErrorResponse, "description": "Ошибка бизнес-логики (например, USER_ALREADY_EXISTS)"},
        401: {"model": ErrorResponse, "description": "Ошибка авторизации (INVALID_CREDENTIALS, EXPIRED_TOKEN)"},
        403: {"model": ErrorResponse, "description": "Доступ запрещен"},
        404: {"model": ErrorResponse, "description": "Ресурс не найден"},
        422: {"model": ErrorResponse, "description": "Ошибка валидации данных"},
        429: {"model": ErrorResponse, "description": "Превышен лимит частоты запросов"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
    }
)


@router.post(
    "/register",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
@limiter.limit("5/minute")
async def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)) -> dict[str, str | User]:
    """Зарегистрировать нового пользователя в системе.

    Аргументы:
        request (Request): Объект входящего HTTP запроса (для rate limiting).
        payload (UserRegister): Данные для регистрации (email, пароль, имя).
        db (Session): Сессия базы данных.

    Возвращает:
        ApiResponse[UserResponse]: Созданный профиль пользователя.
    """
    service = AuthService(db)
    user = await service.register(payload)
    return {"status": "success", "data": user}


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Вход в систему и получение токенов",
)
@limiter.limit("5/minute")
async def login(request: Request, payload: UserLogin, db: Session = Depends(get_db)) -> dict[str, str | TokenResponse]:
    """Аутентификация пользователя по email и паролю с возвратом JWT access и refresh токенов.

    Аргументы:
        request (Request): Объект входящего HTTP запроса (для rate limiting).
        payload (UserLogin): Учетные данные пользователя (email, пароль).
        db (Session): Сессия базы данных.

    Возвращает:
        ApiResponse[TokenResponse]: Пара токенов access_token и refresh_token.
    """
    service = AuthService(db)
    tokens = await service.login(payload)
    return {"status": "success", "data": tokens}


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Обновление access_token с использованием refresh_token",
)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> dict[str, str | TokenResponse]:
    """Обновить access_token и получить новую пару токенов по действующему refresh_token.

    Используется клиентом (фронтендом) при получении 401 HTTP-статуса для бесшовного обновления сессии.

    Аргументы:
        payload (RefreshTokenRequest): Передаваемый refresh_token.
        db (Session): Сессия базы данных.

    Возвращает:
        ApiResponse[TokenResponse]: Обновленные access_token и refresh_token.
    """
    service = AuthService(db)
    tokens = service.refresh_tokens(payload.refresh_token)
    return {"status": "success", "data": tokens}


@router.post(
    "/logout",
    response_model=BaseResponse,
    summary="Выход из системы и деактивация токена",
)
def logout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    credentials: HTTPBearer = Depends(AuthService.bearer_scheme),
) -> dict[str, str]:
    """Выйти из системы, деактивируя токен в базе данных.

    Аргументы:
        db (Session): Сессия базы данных.
        current_user (User): Текущий авторизованный пользователь.
        credentials (HTTPBearer): Токен из заголовка Authorization.
    """
    service = AuthService(db)
    service.logout(current_user.id, credentials.credentials)
    return {"status": "success", "message": "Successfully logged out"}


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Получение информации о текущем пользователе",
)
def auth_me(
    current_user: User = Depends(get_current_user),
) -> dict[str, str | User]:
    """Получить информацию о текущем пользователе."""
    return {"status": "success", "data": current_user}
