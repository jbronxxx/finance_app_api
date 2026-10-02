"""Сервис аутентификации, авторизации и управления пользователями."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Union

import bcrypt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import (
    BadRequestException,
    ErrorCode,
    NotFoundException,
    UnauthorizedException,
)
from app.models.models import Token, User
from app.schemas.schemas import TokenResponse, UserLogin, UserRegister
from config_reader.config_reader import config
from logger.logger import get_logger

logger = get_logger(__name__)

# Схема Bearer токена для извлечения заголовка Authorization
bearer_scheme = HTTPBearer()


class AuthService:
    """Класс бизнес-логики для регистрации, входа и управления токенами пользователей."""

    bearer_scheme = HTTPBearer()

    _revoked_jtis: set[str] = set()

    def __init__(self, db: Session):
        """Инициализация сервиса с сессией базы данных.

        Аргументы:
            db (Session): Активная сессия SQLAlchemy.
        """
        self.db = db

    def register(self, payload: UserRegister) -> User:
        """Зарегистрировать нового пользователя в системе.

        Аргументы:
            payload (UserRegister): Данные нового пользователя (email, пароль, имя).

        Возвращает:
            User: Созданный объект пользователя из базы данных.

        Исключения:
            BadRequestException (400): Если пользователь с указанным email уже существует.
        """
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            logger.warning(f"Попытка регистрации с уже зарегистрированным email: {payload.email}")
            raise BadRequestException(
                code=ErrorCode.USER_ALREADY_EXISTS,
                message="Пользователь с таким email уже зарегистрирован",
            )

        hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
        user = User(email=payload.email, hashed_password=hashed, name=payload.name)
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        logger.info(f"Зарегистрирован новый пользователь: {user.email} (ID: {user.id})")
        return user

    def login(self, payload: UserLogin) -> TokenResponse:
        """Аутентифицировать пользователя и выдать JWT access и refresh токены.

        Аргументы:
            payload (UserLogin): Учетные данные пользователя (email, пароль).

        Возвращает:
            TokenResponse: Объект, содержащий сгенерированные access и refresh токены.

        Исключения:
            UnauthorizedException (401): Если email не найден или пароль не совпадает.
        """
        user = self.db.query(User).filter(User.email == payload.email).first()
        if not user or not bcrypt.checkpw(payload.password.encode(), user.hashed_password.encode()):
            logger.warning(f"Неуспешная попытка входа для email: {payload.email}")
            raise UnauthorizedException(
                code=ErrorCode.INVALID_CREDENTIALS,
                message="Неверный email или пароль",
            )

        access_token = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)
        logger.info(f"Пользователь успешно авторизован: {user.email}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    def logout(self, user_id: uuid.UUID, token_string: str) -> None:
        """Выйти из системы, деактивируя токен в базе данных.

        Аргументы:
            user_id (uuid.UUID): Идентификатор пользователя.
            token_string (str): Строка токена для деактивации.
        """
        self._deactivate_token(user_id, token_string)

    def create_access_token(self, user_id: Union[str, uuid.UUID]) -> str:
        """Сгенерировать access_token для пользователя.

        Аргументы:
            user_id (str | uuid.UUID): Идентификатор пользователя.

        Возвращает:
            str: Закодированный JWT access-токен.
        """
        user_id_str = str(user_id)
        expire = datetime.now(timezone.utc) + timedelta(minutes=config.access_token_expire_minutes)
        payload = {
            "sub": user_id_str,
            "type": "access",
            "exp": expire,
            "jti": uuid.uuid4().hex,
        }
        logger.debug(f"Генерация access-токена для пользователя {user_id_str} (истекает: {expire})")
        token_str = jwt.encode(payload, config.secret_key, algorithm=config.algorithm)
        return token_str

    def create_refresh_token(self, user_id: Union[str, uuid.UUID]) -> str:
        """Сгенерировать и сохранить в БД refresh_token для пользователя.

        Аргументы:
            user_id (str | uuid.UUID): Идентификатор пользователя.

        Возвращает:
            str: Закодированный JWT refresh-токен.
        """
        user_id_str = str(user_id)
        user_uuid = uuid.UUID(user_id_str) if isinstance(user_id, str) else user_id
        expire = datetime.now(timezone.utc) + timedelta(days=config.refresh_token_expire_days)
        payload = {
            "sub": user_id_str,
            "type": "refresh",
            "exp": expire,
            "jti": uuid.uuid4().hex,
        }
        logger.debug(f"Генерация refresh-токена для пользователя {user_id_str} (истекает: {expire})")
        refresh_token_str = jwt.encode(payload, config.secret_key, algorithm=config.algorithm)

        db_token = Token(
            user_id=user_uuid,
            token=refresh_token_str,
            expires_at=expire,
            status="active",
        )
        self.db.add(db_token)
        self.db.flush()
        self.db.refresh(db_token)
        logger.debug(f"Refresh-токен успешно сохранен в БД для пользователя {user_id_str}")
        return db_token.token

    def refresh_tokens(self, refresh_token_string: str) -> TokenResponse:
        """Обновить access_token и получить новый refresh_token по существующему refresh_token.

        Аргументы:
            refresh_token_string (str): Действующий JWT refresh-токен.

        Возвращает:
            TokenResponse: Новые access_token и refresh_token.

        Исключения:
            UnauthorizedException (401): Если токен недействителен, истек или отозван.
        """
        try:
            payload = jwt.decode(refresh_token_string, config.secret_key, algorithms=[config.algorithm])
            user_id = payload.get("sub")
            token_type = payload.get("type")

            if token_type and token_type != "refresh":
                logger.warning("Попытка использования токена доступа вместо refresh-токена при обновлении")
                raise UnauthorizedException(
                    code=ErrorCode.INVALID_TOKEN,
                    message="Недействительный тип токена. Ожидается refresh token",
                )

            if not user_id:
                logger.warning("Refresh-токен не содержит идентификатор пользователя (sub)")
                raise UnauthorizedException(
                    code=ErrorCode.INVALID_TOKEN,
                    message="Недействительный refresh токен",
                )
        except JWTError:
            logger.warning("Недействительная подпись или структура JWT refresh-токена")
            raise UnauthorizedException(
                code=ErrorCode.INVALID_TOKEN,
                message="Недействительный или истекший refresh токен",
            )

        db_token = self.db.query(Token).filter(Token.token == refresh_token_string, Token.status == "active").first()

        if not db_token:
            logger.warning("Refresh-токен отсутствует в базе данных либо неактивен")
            raise UnauthorizedException(
                code=ErrorCode.TOKEN_REVOKED,
                message="Refresh токен недействителен или отозван",
            )

        token_expires_at = db_token.expires_at
        if token_expires_at.tzinfo is None:
            token_expires_at = token_expires_at.replace(tzinfo=timezone.utc)

        if token_expires_at < datetime.now(timezone.utc):
            db_token.status = "expired"
            self.db.flush()
            logger.warning(f"Истек срок действия refresh-токена в базе данных для пользователя {db_token.user_id}")
            raise UnauthorizedException(
                code=ErrorCode.EXPIRED_TOKEN,
                message="Срок действия refresh токена истек",
            )

        try:
            user_uuid = uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            logger.warning(f"Некорректный формат UUID в токене: {user_id}")
            raise UnauthorizedException(
                code=ErrorCode.INVALID_TOKEN,
                message="Недействительный refresh токен",
            )

        if db_token.user_id != user_uuid:
            logger.warning(f"Несоответствие идентификатора пользователя в токене ({user_id}) и БД ({db_token.user_id})")
            raise UnauthorizedException(
                code=ErrorCode.INVALID_TOKEN,
                message="Недействительный refresh токен",
            )

        user = self.db.query(User).filter(User.id == user_uuid).first()
        if not user:
            logger.warning(f"Пользователь с ID {db_token.user_id} не найден при ротации токенов")
            raise UnauthorizedException(
                code=ErrorCode.USER_NOT_FOUND,
                message="Пользователь не найден",
            )

        # Ротация refresh-токена: деактивируем старый refresh_token
        db_token.status = "revoked"
        self.db.flush()

        # Генерируем новую пару токенов
        new_access_token = self.create_access_token(user.id)
        new_refresh_token = self.create_refresh_token(user.id)

        logger.info(f"Успешная ротация токенов для пользователя: {user.email}")
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    def _create_token(self, user_id: str) -> str:
        """Совместимый приватный метод для создания access токена."""
        return self.create_access_token(user_id)

    def _deactivate_token(self, user_id: uuid.UUID, token_string: str) -> None:
        """Деактивировать токен (при выходе пользователя).

        Аргументы:
            user_id (uuid.UUID): Идентификатор пользователя.
            token_string (str): Строка токена для деактивации.
        """
        try:
            payload = jwt.decode(token_string, config.secret_key, algorithms=[config.algorithm])
            jti = payload.get("jti")
            if jti:
                AuthService._revoked_jtis.add(jti)
                logger.info(f"Токен успешно отзывен при выходе пользователя {user_id}")
                return
        except JWTError:
            pass

        logger.warning(f"Попытка отзыва несуществующего токена для пользователя {user_id}")
        raise NotFoundException(
            code=ErrorCode.TOKEN_NOT_FOUND,
            message="Токен не найден для деактивации",
        )

    def cleanup_expired_tokens(self, retention_days: int = 30) -> int:
        """Удалить устаревшие токены, срок действия которых истек более retention_days назад,

        или токены со статусом revoked/expired старше указанного порога.

        Аргументы:
            retention_days (int): Количество дней хранения истекших токенов (по умолчанию 30).

        Возвращает:
            int: Количество удаленных записей токенов.
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted_count = (
            self.db.query(Token)
            .filter(
                (Token.expires_at < threshold) | (Token.status.in_(["expired", "revoked"]) & (Token.created_at < threshold))
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()
        logger.info(f"Очистка токенов: удалено {deleted_count} устаревших токенов (порог: {threshold.isoformat()})")
        return deleted_count


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Зависимость FastAPI (Dependency) для получения текущего авторизованного пользователя.

    Извлекает Bearer-токен из заголовка Authorization, валидирует подпись и срок действия,
    после чего загружает сущность пользователя из БД.

    Аргументы:
        credentials (HTTPAuthorizationCredentials): Учетные данные из заголовка Bearer.
        db (Session): Сессия базы данных.

    Возвращает:
        User: Сущность авторизованного пользователя.

    Исключения:
        UnauthorizedException (401): Если токен невалиден, истек или пользователь не найден.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[config.algorithm])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        jti = payload.get("jti")

        if token_type and token_type != "access":
            logger.warning("Попытка аутентификации с использованием не-access токена")
            raise UnauthorizedException(
                code=ErrorCode.INVALID_TOKEN,
                message="Недействительный тип токена. Ожидается access token",
            )
    except JWTError:
        logger.warning("Ошибка валидации подписи JWT access-токена")
        raise UnauthorizedException(
            code=ErrorCode.INVALID_TOKEN,
            message="Недействительный или истекший токен авторизации",
        )

    if not user_id:
        logger.warning("JWT access-токен не содержит идентификатор пользователя (sub)")
        raise UnauthorizedException(
            code=ErrorCode.INVALID_TOKEN,
            message="Недействительный токен авторизации",
        )

    try:
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        logger.warning(f"Некорректный UUID в токене авторизации: {user_id}")
        raise UnauthorizedException(
            code=ErrorCode.INVALID_TOKEN,
            message="Недействительный токен авторизации",
        )

    if jti in AuthService._revoked_jtis:
        raise UnauthorizedException(
            code=ErrorCode.TOKEN_REVOKED,
            message="Токен отозван или недействителен",
        )

    user = db.query(User).filter(User.id == user_uuid).first()

    if not user:
        logger.warning(f"Пользователь с ID {user_id} из токена не найден в базы данных")
        raise UnauthorizedException(
            code=ErrorCode.USER_NOT_FOUND,
            message="Пользователь не найден",
        )

    logger.debug(f"Аутентификация успешна для пользователя: {user.email}")
    return user
