"""Сервис формирования персональных финансовых инсайтов с использованием Anthropic Claude."""

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy.orm import Session

from app.models.models import Transaction
from app.schemas.schemas import InsightResponse
from config_reader.config_reader import config
from logger.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """Сервис взаимодействия с LLM (Anthropic Claude) для анализа транзакций пользователя."""

    # In-memory кэш аналитики: user_id -> (tx_hash, InsightResponse)
    _cache: dict[uuid.UUID, tuple[str, InsightResponse]] = {}

    def __init__(self, db: Session, client: anthropic.AsyncAnthropic | None = None):
        """Инициализация сервиса с сессией базы данных и асинхронным клиентом Anthropic.

        Аргументы:
            db (Session): Сессия SQLAlchemy.
            client (anthropic.AsyncAnthropic, optional): Асинхронный клиент Anthropic Claude.
        """
        self.db = db
        self.client = client or anthropic.AsyncAnthropic(api_key=config.anthropic_api_key or None)

    @classmethod
    def invalidate_cache(cls, user_id: uuid.UUID) -> None:
        """Инвалидировать кэш инсайтов для конкретного пользователя.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.
        """
        cls._cache.pop(user_id, None)

    @classmethod
    def clear_cache(cls) -> None:
        """Очистить весь кэш инсайтов."""
        cls._cache.clear()

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Извлечь и распарсить JSON-объект из ответа модели, очищая markdown и лишний текст.

        Аргументы:
            text (str): Исходный текстовый ответ модели.

        Возвращает:
            dict: Распарсенный словарь.

        Исключения:
            json.JSONDecodeError: Если валидный JSON не обнаружен.
        """
        cleaned = text.strip()

        # Удаляем markdown-блоки вида ```json ... ``` или ``` ... ```
        if "```" in cleaned:
            pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
            match = re.search(pattern, cleaned)
            if match:
                cleaned = match.group(1).strip()

        # Находим границы JSON-объекта от первой { до последней }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end >= start:
            end_idx = end + 1
            cleaned = cleaned[start:end_idx]

        return json.loads(cleaned)

    async def get_insights(self, user_id: uuid.UUID) -> InsightResponse:
        """Сформировать персональные рекомендации по расходам пользователя.

        Если API ключ не указан или оставлен плейсхолдер — возвращаются информационные заглушки.
        Если транзакций нет — возвращается совет добавить первые операции.
        Если транзакции не менялись — возвращается закэшированный результат.

        Аргументы:
            user_id (uuid.UUID): Уникальный ID пользователя.

        Возвращает:
            InsightResponse: Объект со списком рекомендаций и датой их генерации.
        """
        # Если API ключ не задан или остался плейсхолдер — возвращаем заглушку
        is_placeholder = not config.anthropic_api_key or config.anthropic_api_key.startswith("sk-ant-your-key")
        if is_placeholder:
            logger.warning("ANTHROPIC_API_KEY is not set or is a placeholder, returning stub insights")
            return InsightResponse(
                insights=[
                    "В разработке...",
                ],
                generated_at=datetime.now(timezone.utc),
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
                generated_at=datetime.now(timezone.utc),
            )

        summary = self._build_summary(transactions)
        tx_hash = hashlib.sha256(summary.encode("utf-8")).hexdigest()

        # Проверяем кэш инсайтов
        cached = self._cache.get(user_id)
        if cached:
            cached_hash, cached_response = cached
            if cached_hash == tx_hash:
                logger.info(f"Returning cached AI insights for user {user_id}")
                return cached_response

        try:
            insights = await self._call_claude(summary)
            response = InsightResponse(insights=insights, generated_at=datetime.now(timezone.utc))
            self._cache[user_id] = (tx_hash, response)
            return response
        except Exception as e:
            logger.error(f"Error requesting insights from Anthropic API: {e}")
            return InsightResponse(
                insights=[
                    "Не удалось сгенерировать AI-инсайты (ошибка запроса к API).",
                    "Проверьте настройки ANTHROPIC_API_KEY.",
                ],
                generated_at=datetime.now(timezone.utc),
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
        prompt = f"""Вот транзакции пользователя за последнее время:

{summary}

Дай 3 конкретных совета по управлению бюджетом на основе этих данных.
Ответь в формате JSON: {{"insights": ["совет 1", "совет 2", "совет 3"]}}
Только JSON, без лишнего текста."""

        message = await self.client.messages.create(
            model=config.ai_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text
        try:
            data = self._extract_json(text)
            return data.get("insights", [])
        except (json.JSONDecodeError, ValueError) as err:
            logger.error(f"Failed to parse JSON from LLM response: {err}. Raw text: {text}")
            raise
