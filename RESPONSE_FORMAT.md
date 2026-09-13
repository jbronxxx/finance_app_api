# Стандартный формат API ответов

## Обзор

API использует единообразный формат ответов для всех эндпоинтов:

- **Успешные ответы**: `ApiResponse[T]` - обертка с данными результата
- **Ошибочные ответы**: `ErrorResponse` - обертка с информацией об ошибке
- **Простые ответы**: `BaseResponse` - для операций без значимых данных

---

## Успешные ответы

### Формат: `ApiResponse[T]`

```json
{
  "status": "success",
  "data": { /* Здесь ваши данные */ },
  "message": "Опциональное сообщение"
}
```

### Примеры:

#### Регистрация пользователя (POST /api/v1/auth/register)

```json
{
  "status": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2026-09-10T10:30:00Z"
  }
}
```

#### Создание транзакции (POST /api/v1/transactions/)

```json
{
  "status": "success",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "amount": 1500.50,
    "description": "Зарплата",
    "category": "income",
    "type": "income",
    "date": "2026-09-10T10:00:00Z",
    "created_at": "2026-09-10T10:30:00Z"
  }
}
```

#### Получение списка транзакций (GET /api/v1/transactions/)

```json
{
  "status": "success",
  "data": [
    { /* Транзакция 1 */ },
    { /* Транзакция 2 */ }
  ]
}
```

---

## Ошибочные ответы

### Формат: `ErrorResponse`

```json
{
  "status": "error",
  "error": "КодОшибки",
  "message": "Человекочитаемое описание ошибки",
  "details": { /* Опциональные детали */ }
}
```

### Примеры:

#### Ошибка валидации (422)

```json
{
  "status": "error",
  "error": "ValidationError",
  "message": "Ошибка валидации входных данных",
  "details": {
    "errors": [
      {
        "loc": ["body", "email"],
        "msg": "invalid email format",
        "type": "value_error.email"
      }
    ]
  }
}
```

#### Не найдено (404)

```json
{
  "status": "error",
  "error": "HTTPException",
  "message": "Транзакция не найдена"
}
```

#### Внутренняя ошибка сервера (500)

```json
{
  "status": "error",
  "error": "InternalServerError",
  "message": "Внутренняя ошибка сервера"
}
```

---

## Простые ответы

### Формат: `BaseResponse`

Используется для операций которые не возвращают значимые данные:

```json
{
  "status": "success",
  "message": "Операция выполнена успешно"
}
```

### Примеры:

#### Выход из системы (POST /api/v1/auth/logout)

```json
{
  "status": "success",
  "message": "Successfully logged out"
}
```

#### Удаление транзакции (DELETE /api/v1/transactions/{transaction_id})

```json
{
  "status": "success",
  "message": "Transaction deleted successfully"
}
```

---

## Использование в роутерах

### Пример 1: Возврат данных

```python
from fastapi import APIRouter
from app.schemas.schemas import ApiResponse, UserResponse

router = APIRouter()

@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(payload: UserRegister, db: Session = Depends(get_db)):
    service = AuthService(db)
    user = service.register(payload)
    return {"status": "success", "data": user}
```

### Пример 2: Возврат списка

```python
@router.get("/", response_model=ApiResponse[list[TransactionResponse]])
async def list_transactions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = TransactionService(db)
    transactions = service.get_all(current_user.id)
    return {"status": "success", "data": transactions}
```

### Пример 3: Простой ответ без данных

```python
from app.schemas.schemas import BaseResponse

@router.post("/logout", response_model=BaseResponse)
async def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    service = AuthService(db)
    await service.logout(current_user.id)
    return {"status": "success", "message": "Successfully logged out"}
```

---

## Автоматическая обработка ошибок

Все ошибки обрабатываются автоматически через exception handlers в `main.py`:

1. **HTTPException** → `ErrorResponse` с кодом статуса HTTP
2. **RequestValidationError** → `ErrorResponse` с деталями валидации (422)
3. **Неожиданные исключения** → `ErrorResponse` (500)

Разработчикам не нужно вручную форматировать ошибки - они обрабатываются автоматически.

---

## Типы данных

### ApiResponse

```python
class ApiResponse(BaseModel, Generic[T]):
    status: str = "success"
    data: T
    message: Optional[str] = None
```

### ErrorResponse

```python
class ErrorResponse(BaseModel):
    status: str = "error"
    error: str
    message: str
    details: Optional[dict] = None
```

### BaseResponse

```python
class BaseResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None
```
