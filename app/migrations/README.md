# Alembic Migrations

Инициализация (выполни один раз):
```bash
alembic init migrations
```

Создать миграцию после изменения моделей:
```bash
alembic revision --autogenerate -m "описание изменений"
```

Применить миграции:
```bash
alembic upgrade head
```

Откатить последнюю миграцию:
```bash
alembic downgrade -1
```
