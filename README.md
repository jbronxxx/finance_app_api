# Finance App API

FastAPI бэкенд для персонального финансового трекера с аналитикой расходов и AI-рекомендациями на базе Anthropic Claude.

---

## 🛠 Технологический стек
* **Язык:** Python 3.12 (поддерживается 3.11+)
* **Веб-фреймворк:** FastAPI + Uvicorn
* **База данных:** PostgreSQL 16
* **ORM & Миграции:** SQLAlchemy 2.0 + Alembic
* **Безопасность & Авторизация:** JWT (python-jose) + bcrypt
* **AI Интеграция:** Anthropic Claude API (модель `claude-haiku-4-5`)
* **Контейнеризация:** Docker & Docker Compose
* **Тестирование:** Pytest + HTTPX / TestClient

---

## 📋 Требования к окружению

Для работы с проектом необходимо наличие одного из вариантов:

### Вариант 1 (Запуск через Docker — рекомендуется):
* **Docker Engine** (версия 24.0+)
* **Docker Compose** (версия 2.20+)

### Вариант 2 (Локальный запуск на хосте):
* **Python** 3.11 или 3.12
* **PostgreSQL** 15+ (локально или в Docker)
* **Git**

---

## 🚀 Быстрый запуск в Docker (Рекомендуемый способ)

Все сервисы (API и PostgreSQL) запускаются одной командой. Приложение автоматически ожидает готовности базы данных (`healthcheck`).

### 1. Подготовка конфигурации
Скопируйте файл переменных окружения:
```bash
cp .env.example .env
```

Заполните ваши параметры в файле `.env` (при необходимости измените пароли и логин БД):
```env
POSTGRES_USER=your_postgres_user
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=your_postgres_db
DATABASE_URL=postgresql://your_postgres_user:your_postgres_password@db:5432/your_postgres_db
SECRET_KEY=change-me-in-production-use-long-random-string
ANTHROPIC_API_KEY=sk-ant-api03-...
```
> [!NOTE]
> Если ключ `ANTHROPIC_API_KEY` не указан или оставлен пустым, сервис AI-инсайтов автоматически переключится на безопасный режим заглушек и приложение продолжит работать без ошибок.

### 2. Запуск контейнеров
```bash
# Сборка и запуск в фоновом режиме
docker compose up --build -d
```

### 3. Просмотр логов
```bash
# Логи всех сервисов
docker compose logs -f

# Логи только API
docker compose logs -f api
```

### 4. Остановка контейнеров
```bash
# Остановка сервисов
docker compose down

# Остановка с удалением данных базы (полный сброс)
docker compose down -v
```

---

## 💻 Локальный запуск без Docker (Разработка)

### 1. Запуск базы данных в Docker
```bash
docker compose up db -d
```

### 2. Создание и активация виртуального окружения
```bash
python3 -m venv .venv
source .venv/bin/activate  # Для macOS/Linux
# .venv\Scripts\activate   # Для Windows
```

### 3. Установка зависимостей
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Настройка `.env` для локального хоста
В файле `.env` укажите хост `localhost` (или `127.0.0.1`) вместо имени docker-сервиса `db`:
```env
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}
```

### 5. Запуск сервера разработки
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📖 Как пользоваться API

После запуска сервис доступен по адресам:
* **Интерактивная документация Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc документация:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Проверка статуса сервиса:** [http://localhost:8000/health](http://localhost:8000/health)


---

## 🗄 Подключение к базе данных (DBeaver / DataGrip / psql)

Параметры для подключения сторонних GUI-клиентов берутся из вашего локального файла `.env`:
* **Хост:** `localhost` (при обращении с локальной машины к проброшенному порту)
* **Порт:** значение `POSTGRES_PORT` из `.env` (по умолчанию `5432`)
* **Имя БД:** значение `POSTGRES_DB` из `.env`
* **Пользователь:** значение `POSTGRES_USER` из `.env`
* **Пароль:** значение `POSTGRES_PASSWORD` из `.env`

---

## 🧪 Запуск тестов

Для запуска набора автоматических тестов:
```bash
# Активируйте виртуальное окружение
source .venv/bin/activate

# Запуск тестов
pytest tests/ -v
```

---

## 🔄 Миграции базы данных (Alembic)

Проект использует **Alembic** для управления схемой БД. Все таблицы создаются и обновляются через миграции.

### При запуске в Docker:

```bash
# Создание новой миграции на основе изменений в моделях
docker-compose exec api alembic revision --autogenerate -m "description_of_changes"

# Применение всех миграций
docker-compose exec api alembic upgrade head

# Откат последней миграции
docker-compose exec api alembic downgrade -1

# Просмотр статуса миграций
docker-compose exec api alembic current
```

### При локальном запуске (с активированным venv):

```bash
# Создание новой миграции
alembic revision --autogenerate -m "description_of_changes"

# Применение миграций
alembic upgrade head

# Откат последней миграции
alembic downgrade -1
```

> [!TIP]
> Миграции хранятся в папке `migrations/versions/`. Каждая миграция содержит функции `upgrade()` и `downgrade()` для управления схемой БД.

---

## 📊 Схема базы данных

### Таблицы:

| Таблица | Описание |
|---------|----------|
| `users` | Пользователи системы (email, хешированный пароль, имя) |
| `transactions` | Финансовые операции (доход/расход с категорией и датой) |
| `budgets` | Лимиты расходов по категориям (по месяцам и годам) |
| `tokens` | JWT-токены для сессий пользователей |
| `alembic_version` | Служебная таблица для отслеживания миграций |

### Связи:
- `users` → `transactions` (один пользователь имеет много транзакций)
- `users` → `budgets` (один пользователь имеет много бюджетов)
- `users` → `tokens` (один пользователь имеет много токенов)
