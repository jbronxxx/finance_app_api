"""Точка входа в приложение Finance App API.

Инициализация FastAPI приложения, подключение роутеров и управление
жизненным циклом сервиса (lifespan).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.models import (  # noqa: F401 - гарантирует регистрацию моделей в Base.metadata
    models,
)
from app.routers import auth, budgets, insights, transactions
from logger.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Управление жизненным циклом приложения FastAPI.

    Выполняет инициализацию ресурсов при старте сервера и освобождение ресурсов при его завершении.

    Аргументы:
        app_instance (FastAPI): Экземпляр веб-приложения FastAPI.

    Исключения:
        Exception: Если при автоматическом создании таблиц в БД возникла ошибка.
    """
    logger.info("Starting Finance App API")
    try:
        logger.info("Checking and initializing database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database tables: {e}")
        raise
    yield
    logger.info("Stopping Finance App API")


app = FastAPI(
    title="Finance App API",
    description="Персональный финансовый трекер с AI-инсайтами и аналитикой",
    version="0.1.0",
    lifespan=lifespan,
)

# Подключение маршрутизаторов модулей
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["transactions"])
app.include_router(budgets.router, prefix="/api/v1/budgets", tags=["budgets"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])


@app.get("/health", summary="Проверка работоспособности сервиса")
async def health_check():
    """Эндпоинт проверки здоровья и доступности API.

    Возвращает:
        dict: Статус работы сервиса и текущую версию API.
    """
    return {"status": "ok", "version": "0.1.0"}
