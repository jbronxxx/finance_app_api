"""Сервис формирования персональных финансовых инсайтов с использованием Anthropic Claude."""

import json
import uuid
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from app.models.models import Transaction
from app.schemas.schemas import InsightResponse
from config_reader.config_reader import config
from logger.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """Сервис взаимодействия с LLM (Anthropic Claude) для анализа транзакций пользователя."""

    def __init__(self, db: Session):
        """Инициализация сервиса с сессией базы данных.

        Аргументы:
            db (Session): Сессия SQLAlchemy.
        """
        self.db = db

    async def get_insights(self, user_id: uuid.UUID) -> InsightResponse:
        """Сформировать персональные рекомендации по расходам пользователя.

        Если ключ API не указан или оставлен плейсхолдер — возвращаются информационные заглушки.
        Если транзакций нет — возвращается совет добавить первые операции.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.

        Возвращает:
            InsightResponse: Объект со списком рекомендаций и датой их генерации.
        """
        # Если API ключ не задан или остался плейсхолдер — возвращаем заглушку
        is_placeholder = not config.anthropic_api_key or config.anthropic_api_key.startswith("sk-ant-your-key")
        if is_placeholder:
            logger.warning("ANTHROPIC_API_KEY is not set or is a placeholder, " "returning stub insights")
            return InsightResponse(
                insights=[
                    "В разработке...",
                ],
                generated_at=datetime.utcnow(),
            )

        transactions = (
            self.db.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .order_by(Transaction.date.desc())
            .limit(50)
            .all()
        )

        if not transactions:
            return InsightResponse(
                insights=["Добавь первые транзакции, чтобы получить анализ."],
                generated_at=datetime.utcnow(),
            )

        summary = self._build_summary(transactions)
        try:
            insights = await self._call_claude(summary)
            return InsightResponse(insights=insights, generated_at=datetime.utcnow())
        except Exception as e:
            logger.error(f"Error requesting insights from Anthropic API: {e}")
            return InsightResponse(
                insights=[
                    "Не удалось сгенерировать AI-инсайты (ошибка запроса к API).",
                    "Проверьте настройки ANTHROPIC_API_KEY.",
                ],
                generated_at=datetime.utcnow(),
            )

    def _build_summary(self, transactions: list[Transaction]) -> str:
        """Сформировать текстовую сводку транзакций для передачи в системный промпт LLM.

        Аргументы:
            transactions (list[Transaction]): Список объектов транзакций пользователя.

        Возвращает:
            str: Сводка транзакций (дата, тип, категория, сумма, описание).
        """
        lines = []
        for tx in transactions:
            parts = [
                tx.date.strftime("%Y-%m-%d"),
                tx.type.value,
                tx.category.value,
                f"{tx.amount} руб.",
                tx.description,
            ]
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    async def _call_claude(self, summary: str) -> list[str]:
        """Отправить запрос в Anthropic Messages API и распарсить JSON с рекомендациями.

        Аргументы:
            summary (str): Текстовая сводка по операциям пользователя.

        Возвращает:
            list[str]: Список полученных от нейросети советов.
        """
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)

        prompt = f"""Вот транзакции пользователя за последнее время:

{summary}

Дай 3 конкретных совета по управлению бюджетом на основе этих данных.
Ответь в формате JSON: {{"insights": ["совет 1", "совет 2", "совет 3"]}}
Только JSON, без лишнего текста."""

        message = client.messages.create(
            model=config.ai_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text
        data = json.loads(text)
        return data.get("insights", [])
