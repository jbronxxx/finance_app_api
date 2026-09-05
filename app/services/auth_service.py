"""Сервис аутентификации, авторизации и управления пользователями."""

from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import TokenResponse, UserLogin, UserRegister
from config_reader.config_reader import config

# Схема Bearer токена для извлечения заголовка Authorization
bearer_scheme = HTTPBearer()


class AuthService:
    """Класс бизнес-логики для регистрации и входа пользователей."""

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
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        token = self._create_token(str(user.id))
        return TokenResponse(access_token=token)

    def _create_token(self, user_id: str) -> str:
        """Сгенерировать подписанный JWT-токен доступа для пользователя.

        Аргументы:
            user_id (str): Строковый идентификатор пользователя (UUID).

        Возвращает:
            str: Закодированный JWT-токен.
        """
        expire = datetime.utcnow() + timedelta(minutes=config.access_token_expire_minutes)
        payload = {"sub": user_id, "exp": expire}
        return jwt.encode(payload, config.secret_key, algorithm=config.algorithm)


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
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный токен авторизации",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный или истекший токен авторизации",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user
