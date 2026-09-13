"""Сервис аутентификации, авторизации и управления пользователями."""

import uuid
from datetime import datetime, timedelta

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
    """Класс бизнес-логики для регистрации и входа пользователей."""

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
            logger.warning(f"Попытка регистрации с уже существующим email: {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже зарегистрирован",
            )

        # Хеширование пароля с помощью bcrypt
        hashed = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
        user = User(email=payload.email, hashed_password=hashed, name=payload.name)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Новый пользователь зарегистрирован: {user.email}")
        logger.info(f"JWT-токен создан для нового пользователя {user.email}")
        return user

    def login(self, payload: UserLogin) -> TokenResponse:
        """Аутентифицировать пользователя и выдать JWT-токен.

        Аргументы:
            payload (UserLogin): Учетные данные пользователя (email, пароль).

        Возвращает:
            TokenResponse: Объект, содержащий сгенерированный access-токен.

        Исключения:
            HTTPException (401): Если email не найден или пароль не совпадает.
        """
        user = self.db.query(User).filter(User.email == payload.email).first()
        if not user or not bcrypt.checkpw(payload.password.encode(), user.hashed_password.encode()):
            logger.warning(f"Попытка входа с неверным email или паролем: {payload.email}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Неверный email или пароль",
            )

        token = self._create_token(str(user.id))
        logger.info(f"Пользователь успешно вошел в систему: {user.email}")
        return TokenResponse(access_token=token)

    def logout(self, user_id: uuid.UUID, token_string: str) -> None:
        """Выйти из системы, удаляя токен из базы данных.

        Аргументы:
            user_id (uuid.UUID): Идентификатор пользователя.
            token_string (str): Строка токена для деактивации.
            db (Session): Сессия базы данных.
        """
        self._deactivate_token(user_id, token_string)

    def _create_token(self, user_id: str) -> str:
        """Сгенерировать подписанный JWT-токен доступа для пользователя.

        Аргументы:
            user_id (str): Строковый идентификатор пользователя (UUID).

        Возвращает:
            str: Закодированный JWT-токен.
        """
        expire = datetime.utcnow() + timedelta(minutes=config.access_token_expire_minutes)
        payload = {"sub": user_id, "exp": expire}
        logger.debug(f"Создание JWT-токена для пользователя {user_id} с истечением {expire}")
        token = jwt.encode(payload, config.secret_key, algorithm=config.algorithm)

        try:
            logger.debug(f"Сохранение JWT-токена в базе данных для пользователя {user_id}")
            self.db.add(Token(user_id=user_id, token=token, expires_at=expire))
            self.db.commit()
            self.db.refresh(token := self.db.query(Token).filter(Token.token == token).first())
            logger.debug(f"JWT-токен сохранен в базе данных для пользователя {user_id}")
            return token.token
        except Exception as e:
            logger.error(f"Ошибка при сохранении JWT-токена: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при создании токена",
            )

    def _deactivate_token(self, user_id: uuid.UUID, token_string: str) -> None:
        """Деактивировать токен (например, при выходе пользователя).

        Аргументы:
            user_id (uuid.UUID): Идентификатор пользователя, чей токен нужно деактивировать.
            token_string (str): Строка токена для деактивации.
        """

        user_token = self.db.query(Token).filter(Token.user_id == user_id, Token.token == token_string).first()

        if user_token:
            logger.debug(f"Деактивация токена для пользователя {user_id}")
            user_token.status = "revoked"
            self.db.commit()
            logger.info(f"Токен успешно деактивирован для пользователя {user_id}")
        else:
            logger.warning(f"Попытка деактивации несуществующего токена для пользователя {user_id}")
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
    except JWTError:
        logger.warning("Ошибка декодирования JWT-токена или истекший срок действия")
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

    if not user_id:
        logger.warning("JWT-токен не содержит идентификатор пользователя (sub)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен авторизации",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        logger.warning(f"Пользователь с ID {user_id} не найден в базе данных")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )

    logger.info(f"Текущий пользователь: {user.email}")
    return user
