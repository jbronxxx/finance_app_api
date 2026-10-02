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


DEFAULT_INSECURE_SECRET = "change-me-in-production-use-long-random-string"


def _to_bool(val: str | bool | None, default: bool = False) -> bool:
    """Преобразует строковое или логическое значение в bool."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "t", "yes")


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
        access_token_expire_minutes (int): Время жизни JWT access токена в минутах.
        refresh_token_expire_days (int): Время жизни JWT refresh токена в днях.
        cors_origins (list[str]): Список разрешенных источников для CORS.
        cors_allow_credentials (bool): Разрешение передачи credentials в CORS.
        cors_allow_methods (list[str]): Список разрешенных HTTP методов CORS.
        cors_allow_headers (list[str]): Список разрешенных заголовков CORS.
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
    refresh_token_expire_days: int

    # Настройки CORS
    cors_origins: list[str]
    cors_allow_credentials: bool
    cors_allow_methods: list[str]
    cors_allow_headers: list[str]

    # Настройки Anthropic AI
    anthropic_api_key: str
    ai_model: str


def validate_security_config(cfg: Config) -> None:
    """Проверяет безопасность конфигурации приложения.

    Блокирует запуск с небезопасным секретным ключом по умолчанию
    при отключенном режиме отладки (debug=False).

    Аргументы:
        cfg (Config): Экземпляр конфигурации.

    Исключения:
        ValueError: Если в production режиме используется дефолтный секретный ключ.
    """
    if not cfg.debug and (not cfg.secret_key or cfg.secret_key == DEFAULT_INSECURE_SECRET):
        raise ValueError(
            "Недопустимо использовать значение по умолчанию для SECRET_KEY в production режиме (debug=False). "
            "Задайте криптографически стойкий SECRET_KEY через переменные окружения."
        )


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

    auth_raw = raw.get("auth", {})
    cors_raw = raw.get("cors", {})

    cors_origins_env = os.getenv("CORS_ORIGINS")
    if cors_origins_env:
        cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    else:
        cors_origins = cors_raw.get("allow_origins", ["*"])

    cors_methods_env = os.getenv("CORS_ALLOW_METHODS")
    if cors_methods_env:
        cors_allow_methods = [m.strip() for m in cors_methods_env.split(",") if m.strip()]
    else:
        cors_allow_methods = cors_raw.get("allow_methods", ["*"])

    cors_headers_env = os.getenv("CORS_ALLOW_HEADERS")
    if cors_headers_env:
        cors_allow_headers = [h.strip() for h in cors_headers_env.split(",") if h.strip()]
    else:
        cors_allow_headers = cors_raw.get("allow_headers", ["*"])

    debug_val = os.getenv("APP_DEBUG")
    debug = _to_bool(debug_val, raw["app"]["debug"]) if debug_val is not None else raw["app"]["debug"]

    cfg = Config(
        debug=debug,
        host=os.getenv("APP_HOST", raw["app"]["host"]),
        port=int(os.getenv("APP_PORT", raw["app"]["port"])),
        db_url=db_url,
        secret_key=os.getenv("SECRET_KEY", auth_raw.get("secret_key")),
        algorithm=os.getenv("AUTH_ALGORITHM", auth_raw.get("algorithm", "HS256")),
        access_token_expire_minutes=int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", auth_raw.get("access_token_expire_minutes", 60))
        ),
        refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", auth_raw.get("refresh_token_expire_days", 7))),
        cors_origins=cors_origins,
        cors_allow_credentials=_to_bool(os.getenv("CORS_ALLOW_CREDENTIALS"), cors_raw.get("allow_credentials", True)),
        cors_allow_methods=cors_allow_methods,
        cors_allow_headers=cors_allow_headers,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        ai_model=os.getenv("AI_MODEL", raw["ai"]["model"]),
    )

    validate_security_config(cfg)
    return cfg


# Глобальный синглтон конфигурации для использования во всем приложении
config = load_config()
