"""Эндпоинты формирования персональной AI-аналитики и рекомендаций."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.schemas.schemas import InsightResponse
from app.services.ai_service import AIService
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get(
    "/",
    response_model=InsightResponse,
    summary="Получить AI-рекомендации по расходам",
)
async def get_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сформировать персонализированные финансовые советы на основе истории транзакций пользователя.

    Анализирует последние операции пользователя и передает сводку в модель Anthropic Claude.
    Если API ключ не задан, возвращает демонстрационные заглушки.

    Аргументы:
        db (Session): Сессия базы данных (инъекция через Depends).
        current_user (User): Текущий аутентифицированный пользователь.

    Возвращает:
        InsightResponse: Список персональных рекомендаций с отметкой времени.
    """
    service = AIService(db)
    return await service.get_insights(current_user.id)
