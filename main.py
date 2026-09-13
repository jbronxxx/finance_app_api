"""Точка входа в приложение Finance App API.

Инициализация FastAPI приложения, подключение роутеров и управление
жизненным циклом сервиса (lifespan).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.routers import auth, budgets, insights, sync, transactions
from app.schemas.schemas import ErrorResponse
from logger.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Управление жизненным циклом приложения FastAPI.

    Выполняет инициализацию ресурсов при старте сервера и освобождение ресурсов при его завершении.

    Аргументы:
        app_instance (FastAPI): Экземпляр веб-приложения FastAPI.
    """
    logger.info("Starting Finance App API")
    yield
    logger.info("Stopping Finance App API")


app = FastAPI(
    title="Finance App API",
    description="Персональный финансовый трекер с AI-инсайтами и аналитикой",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений с единообразным форматом ответа."""
    error_response = ErrorResponse(
        status="error",
        error="HTTPException",
        message=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации с единообразным форматом ответа."""
    errors_dict = {}
    for error in exc.errors():
        field = str(error["loc"][-1]) if error["loc"] else "unknown"
        msg = error.get("msg", "Неверное значение")
        errors_dict[field] = msg

    error_response = ErrorResponse(
        status="error",
        error="ValidationError",
        message="Ошибка валидации входных данных",
        details={"fields": errors_dict},
    )
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик неожиданных исключений с единообразным форматом ответа."""
    logger.error(f"Неожиданная ошибка: {str(exc)}", exc_info=True)
    error_response = ErrorResponse(
        status="error",
        error="InternalServerError",
        message="Внутренняя ошибка сервера",
    )
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump(),
    )


# Подключение маршрутизаторов модулей
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["transactions"])
app.include_router(budgets.router, prefix="/api/v1/budgets", tags=["budgets"])
app.include_router(insights.router, prefix="/api/v1/insights", tags=["insights"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["sync"])


@app.get("/health", summary="Проверка работоспособности сервиса")
async def health_check():
    """Эндпоинт проверки здоровья и доступности API.

    Возвращает:
        dict: Статус работы сервиса и текущую версию API.
    """
    return {"status": "ok", "version": "0.1.0"}
