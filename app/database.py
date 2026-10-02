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


class UnitOfWork:
    """Контекстный менеджер Unit of Work для управления транзакциями базы данных.

    Обеспечивает атомарность группы операций: при выходе из блока `with` без ошибок
    транзакция автоматически фиксируется (commit), а при возникновении исключения —
    откатывается (rollback).
    """

    def __init__(self, session_factory: sessionmaker = SessionLocal):
        """Инициализация Unit of Work с фабрикой сессий SQLAlchemy.

        Аргументы:
            session_factory (sessionmaker): Фабрика сессий БД (по умолчанию SessionLocal).
        """
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> Session:
        """Открыть сессию и войти в контекст транзакции."""
        self.session = self._session_factory()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Завершить транзакцию: commit при успехе, rollback при исключении."""
        if self.session is None:
            return False

        try:
            if exc_type is not None:
                self.session.rollback()
            else:
                self.session.commit()
        finally:
            self.session.close()
        return False


def get_db() -> Generator[Session, None, None]:
    """Генератор сессий базы данных (FastAPI Dependency) с автоматическим управлением транзакциями.

    Открывает новую сессию SQLAlchemy на время обработки HTTP-запроса,
    фиксирует (commit) транзакцию при успешном завершении запроса,
    откатывает (rollback) при ошибке и гарантированно закрывает сессию.

    Возвращает:
        Generator[Session, None, None]: Сессия SQLAlchemy для выполнения запросов к БД.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
