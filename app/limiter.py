"""Модуль настройки ограничения частоты запросов (Rate Limiting).

Предоставляет синглтон Limiter для защиты эндпоинтов от спама и brute-force атак.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Создание экземпляра лимитера с определением клиента по IP-адресу
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
)
