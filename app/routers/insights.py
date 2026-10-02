"""Эндпоинты формирования персональной AI-аналитики и рекомендаций."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.models import User
from app.schemas.schemas import ApiResponse, ErrorResponse, InsightResponse
from app.services.ai_service import AIService
from app.services.auth_service import get_current_user

router = APIRouter(
    responses={
        401: {"model": ErrorResponse, "description": "Требуется авторизация"},
        403: {"model": ErrorResponse, "description": "Доступ запрещен"},
        429: {"model": ErrorResponse, "description": "Превышен лимит частоты запросов"},
        500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервера"},
    }
)


@router.get(
    "/",
    response_model=ApiResponse[InsightResponse],
    summary="Получить AI-рекомендации по расходам",
)
@limiter.limit("10/minute")
async def get_insights(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сформировать персонализированные финансовые советы на основе истории транзакций пользователя.

    Анализирует последние операции пользователя и передает сводку в модель Anthropic Claude.
    Если API ключ не задан, возвращает демонстрационные заглушки.

    Аргументы:
        request (Request): Объект входящего HTTP запроса (для rate limiting).
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        ApiResponse[InsightResponse]: Список персональных рекомендаций с отметкой времени.
    """
    service = AIService(db)
    insights = await service.get_insights(current_user.id)
    return {"status": "success", "data": insights}
