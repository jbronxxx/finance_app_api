"""Сервис аутентификации, авторизации и управления пользователями."""

import uuid
from datetime import datetime, timedelta
from typing import Union

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
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
            HTTPException (400): Если пользователь с указанным email уже существует.
        """
        existing = self.db.query(User).filter(User.email == payload.email).first()
        if existing:
            logger.warning(f"Попытка регистрации с уже зарегистрированным email: {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже зарегистрирован",
            )

        hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
        user = User(email=payload.email, hashed_password=hashed, name=payload.name)
        self.db.add(user)
        self.db.commit()
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
            HTTPException (422): Если email не найден или пароль не совпадает.
        """
        user = self.db.query(User).filter(User.email == payload.email).first()
        if not user or not bcrypt.checkpw(payload.password.encode(), user.hashed_password.encode()):
            logger.warning(f"Неуспешная попытка входа для email: {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Неверный email или пароль",
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
        """Сгенерировать и сохранить в БД access_token для пользователя.

        Аргументы:
            user_id (str | uuid.UUID): Идентификатор пользователя.

        Возвращает:
            str: Закодированный JWT access-токен.
        """
        user_id_str = str(user_id)
        user_uuid = uuid.UUID(user_id_str) if isinstance(user_id, str) else user_id
        expire = datetime.utcnow() + timedelta(minutes=config.access_token_expire_minutes)
        payload = {
            "sub": user_id_str,
            "type": "access",
            "exp": expire,
        }
        logger.debug(f"Генерация access-токена для пользователя {user_id_str} (истекает: {expire})")
        token_str = jwt.encode(payload, config.secret_key, algorithm=config.algorithm)

        try:
            db_token = Token(
                user_id=user_uuid,
                token=token_str,
                expires_at=expire,
                status="active",
            )
            self.db.add(db_token)
            self.db.commit()
            self.db.refresh(db_token)
            logger.debug(f"Access-токен успешно сохранен в БД для пользователя {user_id_str}")
            return db_token.token
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка сохранения access-токена в БД для пользователя {user_id_str}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при создании токена доступа",
            )

    def create_refresh_token(self, user_id: Union[str, uuid.UUID]) -> str:
        """Сгенерировать и сохранить в БД refresh_token для пользователя.

        Аргументы:
            user_id (str | uuid.UUID): Идентификатор пользователя.

        Возвращает:
            str: Закодированный JWT refresh-токен.
        """
        user_id_str = str(user_id)
        user_uuid = uuid.UUID(user_id_str) if isinstance(user_id, str) else user_id
        expire = datetime.utcnow() + timedelta(days=config.refresh_token_expire_days)
        payload = {
            "sub": user_id_str,
            "type": "refresh",
            "exp": expire,
        }
        logger.debug(f"Генерация refresh-токена для пользователя {user_id_str} (истекает: {expire})")
        refresh_token_str = jwt.encode(payload, config.secret_key, algorithm=config.algorithm)

        try:
            db_token = Token(
                user_id=user_uuid,
                token=refresh_token_str,
                expires_at=expire,
                status="active",
            )
            self.db.add(db_token)
            self.db.commit()
            self.db.refresh(db_token)
            logger.debug(f"Refresh-токен успешно сохранен в БД для пользователя {user_id_str}")
            return db_token.token
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ошибка сохранения refresh-токена в БД для пользователя {user_id_str}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при создании refresh токена",
            )

    def refresh_tokens(self, refresh_token_string: str) -> TokenResponse:
        """Обновить access_token и получить новый refresh_token по существующему refresh_token.

        Аргументы:
            refresh_token_string (str): Действующий JWT refresh-токен.

        Возвращает:
            TokenResponse: Новые access_token и refresh_token.

        Исключения:
            HTTPException (401): Если токен недействителен, истек или отозван.
        """
        try:
            payload = jwt.decode(refresh_token_string, config.secret_key, algorithms=[config.algorithm])
            user_id = payload.get("sub")
            token_type = payload.get("type")

            if token_type and token_type != "refresh":
                logger.warning("Попытка использования токена доступа вместо refresh-токена при обновлении")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный тип токена. Ожидается refresh token",
                )

            if not user_id:
                logger.warning("Refresh-токен не содержит идентификатор пользователя (sub)")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительный refresh токен",
                )
        except JWTError:
            logger.warning("Недействительная подпись или структура JWT refresh-токена")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный или истекший refresh токен",
            )

        db_token = self.db.query(Token).filter(Token.token == refresh_token_string, Token.status == "active").first()

        if not db_token:
            logger.warning("Refresh-токен отсутствует в базе данных либо неактивен")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh токен недействителен или отозван",
            )

        if db_token.expires_at < datetime.utcnow():
            db_token.status = "expired"
            self.db.commit()
            logger.warning(f"Истек срок действия refresh-токена в базе данных для пользователя {db_token.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Срок действия refresh токена истек",
            )

        if str(db_token.user_id) != str(user_id):
            logger.warning(f"Несоответствие идентификатора пользователя в токене ({user_id}) и БД ({db_token.user_id})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh токен",
            )

        user = self.db.query(User).filter(User.id == db_token.user_id).first()
        if not user:
            logger.warning(f"Пользователь с ID {db_token.user_id} не найден при ротации токенов")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
            )

        # Ротация refresh-токена: деактивируем старый refresh_token
        db_token.status = "revoked"
        self.db.commit()

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
        user_token = self.db.query(Token).filter(Token.user_id == user_id, Token.token == token_string).first()

        if user_token:
            logger.debug(f"Деактивация токена для пользователя {user_id}")
            user_token.status = "revoked"
            self.db.commit()
            logger.info(f"Токен успешно отзывен при выходе пользователя {user_id}")
        else:
            logger.warning(f"Попытка отзыва несуществующего токена для пользователя {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Токен не найден для деактивации",
            )


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
        HTTPException (401): Если токен невалиден, истек или пользователь не найден.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, config.secret_key, algorithms=[config.algorithm])
        user_id = payload.get("sub")
        token_type = payload.get("type")

        if token_type and token_type != "access":
            logger.warning("Попытка аутентификации с использованием не-access токена")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный тип токена. Ожидается access token",
            )
    except JWTError:
        logger.warning("Ошибка валидации подписи JWT access-токена")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший токен авторизации",
        )

    db_token = db.query(Token).filter(Token.token == token, Token.status == "active").first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен отозван или недействителен",
        )

    if db_token.expires_at < datetime.utcnow():
        db_token.status = "expired"
        db.commit()
        logger.warning(f"Истек срок действия access-токена в базе данных для пользователя {db_token.user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена доступа истек",
        )

    if not user_id:
        logger.warning("JWT access-токен не содержит идентификатор пользователя (sub)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен авторизации",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        logger.warning(f"Пользователь с ID {user_id} из токена не найден в базы данных")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )

    logger.debug(f"Аутентификация успешна для пользователя: {user.email}")
    return user
