"""Модуль чтения и валидации конфигурации приложения.

Загружает настройки из YAML-файла конфигурации и переопределяет их
значениями из переменных окружения (.env).
"""

import os
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()


@dataclass
class Config:
    """Класс-контейнер для хранения всех настроек приложения.

    Атрибуты:
        debug (bool): Режим отладки приложения.
        host (str): Хост для привязки веб-сервера.
        port (int): Порт для привязки веб-сервера.
        db_url (str): Строка подключения (DSN) к базе данных PostgreSQL.
        secret_key (str): Секретный ключ для подписи JWT-токенов.
        algorithm (str): Алгоритм шифрования JWT (например, HS256).
        access_token_expire_minutes (int): Время жизни JWT токена в минутах.
        anthropic_api_key (str): Ключ API для интеграции с Anthropic Claude.
        ai_model (str): Название используемой модели Anthropic Claude.
    """

    # Настройки приложения
    debug: bool
    host: str
    port: int

    # Настройки базы данных
    db_url: str

    # Настройки авторизации и безопасности
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    # Настройки Anthropic AI
    anthropic_api_key: str
    ai_model: str


def load_config(path: str = "app_config.yaml") -> Config:
    """Загрузить конфигурацию из файла YAML и объединить с переменными окружения.

    Аргументы:
        path (str, optional): Путь к файлу конфигурации YAML. По умолчанию "app_config.yaml".

    Возвращает:
        Config: Инициализированный объект конфигурации с актуальными параметрами.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Определение DSN базы данных из DATABASE_URL либо составных переменных
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pg_user = os.getenv("POSTGRES_USER")
        pg_pass = os.getenv("POSTGRES_PASSWORD")
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = os.getenv("POSTGRES_PORT", "5432")
        pg_db = os.getenv("POSTGRES_DB")

        if pg_user and pg_pass and pg_db:
            db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
        else:
            db_url = raw["db"]["url"]

    return Config(
        debug=bool(os.getenv("APP_DEBUG", raw["app"]["debug"])),
        host=os.getenv("APP_HOST", raw["app"]["host"]),
        port=int(os.getenv("APP_PORT", raw["app"]["port"])),
        db_url=db_url,
        secret_key=os.getenv("SECRET_KEY", raw["auth"]["secret_key"]),
        algorithm=os.getenv("AUTH_ALGORITHM", raw["auth"]["algorithm"]),
        access_token_expire_minutes=int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", raw["auth"]["access_token_expire_minutes"])
        ),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", raw["ai"]["model"]),
    )


# Глобальный синглтон конфигурации для использования во всем приложении
config = load_config()
