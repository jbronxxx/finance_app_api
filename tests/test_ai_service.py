"""Модуль модульных тестов для AIService."""

import asyncio
import time
import uuid
from datetime import datetime
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
    async def test_get_insights_placeholder_api_key(self):
        """Если API ключ - плейсхолдер или пустой, возвращается заглушка."""
        mock_db = MagicMock()
        service = AIService(db=mock_db)

        with patch("app.services.ai_service.config.anthropic_api_key", "sk-ant-your-key-here"):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert result.insights == ["В разработке..."]

    @pytest.mark.asyncio
    async def test_get_insights_empty_api_key(self):
        """Если API ключ пустой, возвращается заглушка."""
        mock_db = MagicMock()
        service = AIService(db=mock_db)

        with patch("app.services.ai_service.config.anthropic_api_key", ""):
            result = await service.get_insights(uuid.uuid4())

        assert isinstance(result, InsightResponse)
        assert result.insights == ["В разработке..."]

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

        # Запускаем 5 одновременных вызовов
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

        # Если бы было синхронное блокирование (как раньше), 5 x 0.1s заняло бы минимум 0.5s.
        # В асинхронном режиме все 5 задач отрабатывают параллельно ~0.1-0.2s.
        assert duration < 0.35, f"Запросы выполнялись последовательно: заняло {duration}s"
