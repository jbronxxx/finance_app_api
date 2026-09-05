"""Модуль подключения к базе данных PostgreSQL и управления сессиями SQLAlchemy."""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config_reader.config_reader import config

# Создание движка SQLAlchemy для взаимодействия с базой данных
engine = create_engine(config.db_url)

# Фабрика локальных сессий базы данных
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Базовый декларативный класс для всех ORM-моделей приложения."""

    pass


def get_db() -> Generator[Session, None, None]:
    """Генератор сессий базы данных (FastAPI Dependency).

    Открывает новую сессию SQLAlchemy на время обработки HTTP-запроса
    и гарантированно закрывает её после завершения запроса.

    Возвращает:
        Generator[Session, None, None]: Сессия SQLAlchemy для выполнения запросов к БД.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
