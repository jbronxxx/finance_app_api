"""Модуль модульных тестов для AIService."""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from app.models.models import Category, Transaction, TransactionType
from app.schemas.schemas import InsightResponse
from app.services.ai_service import AIService


class TestAIService:
    """Набор тестов для AIService."""

    def test_init_creates_async_anthropic_client(self):
        """Проверка, что AIService инициализирует асинхронный клиент AsyncAnthropic."""
        mock_db = MagicMock()
        service = AIService(db=mock_db)

        assert isinstance(service.client, anthropic.AsyncAnthropic)
        assert service.db is mock_db

    def test_init_accepts_custom_client(self):
        """Проверка возможности передать собственный клиент (Dependency Injection)."""
        mock_db = MagicMock()
        custom_client = MagicMock(spec=anthropic.AsyncAnthropic)
        service = AIService(db=mock_db, client=custom_client)

        assert service.client is custom_client

    # =========================================================================
    # TASK-1.2: Тестирование надежного парсинга JSON
    # =========================================================================

    def test_extract_json_pure_json(self):
        """Проверка парсинга чистого JSON."""
        raw = '{"insights": ["Совет 1", "Совет 2"]}'
        result = AIService._extract_json(raw)
        assert result == {"insights": ["Совет 1", "Совет 2"]}

    def test_extract_json_markdown_block(self):
        """Проверка извлечения JSON из markdown-блока ```json ... ```."""
        raw = '```json\n{"insights": ["Совет 1", "Совет 2"]}\n```'
        result = AIService._extract_json(raw)
        assert result == {"insights": ["Совет 1", "Совет 2"]}

    def test_extract_json_markdown_block_without_tag(self):
        """Проверка извлечения JSON из markdown-блока без указания языка ``` ... ```."""
        raw = '```\n{"insights": ["Совет 1"]}\n```'
        result = AIService._extract_json(raw)
        assert result == {"insights": ["Совет 1"]}

    def test_extract_json_with_conversational_text(self):
        """Проверка извлечения JSON при наличии вводного и завершающего текста модели."""
        raw = """Конечно! Вот персональные финансовые рекомендации для вас:
```json
{
  "insights": [
    "Оптимизируйте подписки",
    "Создайте подушку безопасности"
  ]
}
```
Надеюсь, эти советы будут полезны!"""
        result = AIService._extract_json(raw)
        assert result == {
            "insights": [
                "Оптимизируйте подписки",
                "Создайте подушку безопасности",
            ]
        }

    def test_extract_json_embedded_brackets_without_code_block(self):
        """Проверка извлечения JSON, заключенного в фигурные скобки посреди текста."""
        raw = 'Вот ваш результат: {"insights": ["Экономьте на такси"]} Всего доброго!'
        result = AIService._extract_json(raw)
        assert result == {"insights": ["Экономьте на такси"]}

    def test_extract_json_invalid_raises_error(self):
        """Если валидный JSON отсутствует, выбрасывается JSONDecodeError."""
        raw = "Извините, я не могу проанализировать эти транзакции."
        with pytest.raises(json.JSONDecodeError):
            AIService._extract_json(raw)

    # =========================================================================
    # TASK-1.1 & TASK-1.3: Вызов Claude, асинхронность и UTC время
    # =========================================================================

    @pytest.mark.asyncio
    async def test_call_claude_uses_awaited_async_client(self):
        """Проверка, что _call_claude асинхронно вызывает messages.create."""
        mock_db = MagicMock()
        mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = '{"insights": ["Снизь расходы на кафе", "Откладывай 10%", "Инвестируй остаток"]}'
        mock_response.content = [mock_content]

        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = AIService(db=mock_db, client=mock_client)
        summary = "2026-10-01 | expense | food | 500.0 руб. | Обед"

        insights = await service._call_claude(summary)

        assert insights == [
            "Снизь расходы на кафе",
            "Откладывай 10%",
            "Инвестируй остаток",
        ]
        mock_client.messages.create.assert_awaited_once()
        create_kwargs = mock_client.messages.create.call_args.kwargs
        assert create_kwargs["max_tokens"] == 500
        assert len(create_kwargs["messages"]) == 1
        assert "2026-10-01" in create_kwargs["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_get_insights_placeholder_api_key_returns_utc_datetime(self):
        """Если API ключ - плейсхолдер, возвращается заглушка с timezone-aware UTC datetime."""
        mock_db = MagicMock()
        service = AIService(db=mock_db)

        with patch("app.services.ai_service.config.anthropic_api_key", "sk-ant-your-key-here"):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert result.insights == ["В разработке..."]
        assert result.generated_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_get_insights_empty_api_key(self):
        """Если API ключ пустой, возвращается заглушка."""
        mock_db = MagicMock()
        service = AIService(db=mock_db)

        with patch("app.services.ai_service.config.anthropic_api_key", ""):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert result.insights == ["В разработке..."]
        assert result.generated_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_get_insights_no_transactions(self):
        """Если у пользователя нет транзакций, возвращается совет добавить первую транзакцию."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []

        service = AIService(db=mock_db)

        with patch("app.services.ai_service.config.anthropic_api_key", "valid-real-api-key"):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert result.insights == ["Добавь первые транзакции, чтобы получить анализ."]
        assert result.generated_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_get_insights_success_with_transactions(self):
        """Успешное получение инсайтов при наличии транзакций."""
        tx1 = MagicMock(spec=Transaction)
        tx1.date = datetime(2026, 10, 1, 12, 0)
        tx1.type = TransactionType.expense
        tx1.category = Category.food
        tx1.amount = 1200.0
        tx1.description = "Супермаркет"

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [tx1]

        mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = '{"insights": ["Траты на еду в норме", "Планируйте бюджет на неделю"]}'
        mock_response.content = [mock_content]

        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service = AIService(db=mock_db, client=mock_client)

        with patch("app.services.ai_service.config.anthropic_api_key", "valid-real-api-key"):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert result.insights == ["Траты на еду в норме", "Планируйте бюджет на неделю"]
        assert result.generated_at.tzinfo == timezone.utc
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_insights_api_error_fallback(self):
        """Если вызов Anthropic API завершился ошибкой, возвращается корректное сообщение об ошибке."""
        tx1 = MagicMock(spec=Transaction)
        tx1.date = datetime(2026, 10, 1, 12, 0)
        tx1.type = TransactionType.expense
        tx1.category = Category.food
        tx1.amount = 500.0
        tx1.description = "Кофе"

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [tx1]

        mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("Anthropic connection timeout"))

        service = AIService(db=mock_db, client=mock_client)

        with patch("app.services.ai_service.config.anthropic_api_key", "valid-real-api-key"):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert "Не удалось сгенерировать AI-инсайты" in result.insights[0]
        assert result.generated_at.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_concurrent_calls_do_not_block_event_loop(self):
        """Проверка, что параллельные вызовы к Claude не блокируют Event Loop."""
        mock_db = MagicMock()
        mock_client = MagicMock(spec=anthropic.AsyncAnthropic)

        async def simulated_async_network_call(*args, **kwargs):
            await asyncio.sleep(0.1)
            mock_resp = MagicMock()
            mock_content = MagicMock()
            mock_content.text = '{"insights": ["Тест параллельности"]}'
            mock_resp.content = [mock_content]
            return mock_resp

        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=simulated_async_network_call)

        service = AIService(db=mock_db, client=mock_client)

        start_time = time.monotonic()
        results = await asyncio.gather(
            service._call_claude("summary 1"),
            service._call_claude("summary 2"),
            service._call_claude("summary 3"),
            service._call_claude("summary 4"),
            service._call_claude("summary 5"),
        )
        duration = time.monotonic() - start_time

        assert len(results) == 5
        for res in results:
            assert res == ["Тест параллельности"]

        assert duration < 0.35, f"Запросы выполнялись последовательно: заняло {duration}s"

    # =========================================================================
    # TASK-5.3: Тестирование кэширования инсайтов
    # =========================================================================

    @pytest.mark.asyncio
    async def test_insights_caching_returns_cached_on_identical_transactions(self):
        """Повторный запрос при неизменных транзакциях возвращает кэшированный ответ без повторного вызова API."""
        user_id = uuid.uuid4()
        tx = MagicMock(spec=Transaction)
        tx.date = datetime(2026, 10, 1, 10, 0)
        tx.type = TransactionType.expense
        tx.category = Category.transport
        tx.amount = 150.0
        tx.description = "Метро"

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [tx]

        mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.text = '{"insights": ["Пользуйтесь проездным"]}'
        mock_response.content = [mock_content]

        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        service1 = AIService(db=mock_db, client=mock_client)

        with patch("app.services.ai_service.config.anthropic_api_key", "valid-real-api-key"):
            first_resp = await service1.get_insights(user_id)
            assert first_resp.insights == ["Пользуйтесь проездным"]
            assert mock_client.messages.create.await_count == 1

            # Создаем новый экземпляр сервиса (симулируя следующий HTTP-запрос)
            service2 = AIService(db=mock_db, client=mock_client)
            second_resp = await service2.get_insights(user_id)

            # Ответ возвращен из кэша
            assert second_resp.insights == ["Пользуйтесь проездным"]
            # API Claude НЕ вызывался повторно!
            assert mock_client.messages.create.await_count == 1
            assert second_resp.generated_at == first_resp.generated_at

    @pytest.mark.asyncio
    async def test_insights_caching_invalidates_when_transactions_change(self):
        """Если транзакции пользователя изменились, кэш инвалидируется и вызывается Claude API."""
        user_id = uuid.uuid4()
        tx1 = MagicMock(spec=Transaction)
        tx1.date = datetime(2026, 10, 1, 10, 0)
        tx1.type = TransactionType.expense
        tx1.category = Category.transport
        tx1.amount = 150.0
        tx1.description = "Метро"

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [tx1]

        mock_client = MagicMock(spec=anthropic.AsyncAnthropic)
        mock_response1 = MagicMock()
        mock_content1 = MagicMock()
        mock_content1.text = '{"insights": ["Совет 1"]}'
        mock_response1.content = [mock_content1]

        mock_response2 = MagicMock()
        mock_content2 = MagicMock()
        mock_content2.text = '{"insights": ["Совет 2 - траты выросли"]}'
        mock_response2.content = [mock_content2]

        mock_client.messages = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=[mock_response1, mock_response2])

        service = AIService(db=mock_db, client=mock_client)

        with patch("app.services.ai_service.config.anthropic_api_key", "valid-real-api-key"):
            first_resp = await service.get_insights(user_id)
            assert first_resp.insights == ["Совет 1"]
            assert mock_client.messages.create.await_count == 1

            # Пользователь совершил новую транзакцию
            tx2 = MagicMock(spec=Transaction)
            tx2.date = datetime(2026, 10, 2, 11, 0)
            tx2.type = TransactionType.expense
            tx2.category = Category.shopping
            tx2.amount = 5000.0
            tx2.description = "Одежда"

            mock_query.all.return_value = [tx2, tx1]

            second_resp = await service.get_insights(user_id)
            assert second_resp.insights == ["Совет 2 - траты выросли"]
            assert mock_client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_and_clear_cache(self):
        """Проверка методов ручной инвалидации кэша."""
        from app.services.ai_service import redis_client

        u1 = uuid.uuid4()
        u2 = uuid.uuid4()

        await redis_client.set(f"insights_cache:{u1}", "data1")
        await redis_client.set(f"insights_cache:{u2}", "data2")

        await AIService.invalidate_cache(u1)
        assert await redis_client.get(f"insights_cache:{u1}") is None
        assert await redis_client.get(f"insights_cache:{u2}") == "data2"

        await AIService.clear_cache()
        assert await redis_client.get(f"insights_cache:{u2}") is None
