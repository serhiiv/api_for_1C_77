# api_for_1C_77

API для інтеграції з 1С:Підприємство 7.7. Основний сервіс побудований на FastAPI, обмін повідомленнями йде через RabbitMQ, а обробка для Windows Server 2003 винесена в окремий воркер.

## Структура проєкту

```text
.
├── .dockerignore
├── .env.example
├── app
│   ├── __init__.py
│   ├── config.py
│   ├── health.py
│   ├── main.py
│   ├── messages.py
│   ├── rabbitmq.py
│   └── security.py
├── docker-compose.yml
├── Dockerfile
├── LICENSE
├── README.md
├── requirements.txt
└── windows_2003
    ├── .env.example
    ├── bridge.vbs
    ├── config.py
    ├── consumer.py
    ├── logs
    │   └── consumer.log
    ├── README_WINDOWS_2003.md
    ├── reports
    │   ├── test.ert
    │   └── json_for_test
    │       └── test.ert
    └── requirements.txt
```

## Швидкий старт

1. Створіть `.env` на основі прикладу і введіть свої параметри:

```bash
cp .env.example .env
```

2. Запустіть API та RabbitMQ:

```bash
docker compose up --build
```

3. Перевірте health endpoint:

```bash
curl http://localhost:8000/health
```

4. API захищене ключем доступу. У `.env` задайте `API_KEY`, а в запитах передавайте той самий ключ у заголовку `X-API-Key`.

```bash
curl -X POST http://localhost:8000/messages/process \
    -H "Content-Type: application/json" \
    -H "X-API-Key: change-me" \
    -d '{
    "procedure": "ТестАПІ",
    "parameters": {
        "number": 3,
        "date": "18.05.2026",
        "name": "Текст \"Назва іїє\"",
        "array": [3, 4, 5],
        "object": {
            "key1": "value1",
            "key2": "value2"
            }
        }
    }'
```

   Якщо ключ не передати або він неправильний, API повертає `401 Unauthorized`.

5. Надішліть запит на обробку. API повертає `request_id` і адресу для отримання результату:

   Приклад відповіді:

```json
{
    "status": "accepted",
    "request_id": "c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e",
    "result_endpoint": "/messages/result/c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e"
}
```

6. Отримайте результат за `request_id`:

```bash
curl http://localhost:8000/messages/result/c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e
```

Поки обробка триває:

```json
{"status": "pending", "request_id": "c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e"}
```

Після завершення:

```json
{
    "status": "ready",
    "request_id": "c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e",
    "result": {
    "status": "ok",
    "message": "test passed",
    "data":   {
        "number": 3,
        "date": "18.05.26",
        "name": "Текст \"Назва іїє\"",
        "array": [ 3, 4, 5 ],
        "object":     {
            "key1": "value1",
            "key2": "value2"
            }
        },
    "seconds": 0
    }
}
```

## Як це працює

1. `POST /messages/process` приймає будь-який JSON payload.
2. API створює `request_id`, публікує повідомлення в RabbitMQ чергу `events` і одразу повертає `202 Accepted`.
3. Для кожного `request_id` використовується окрема черга результатів `results.<request_id>`.
4. Воркер читає чергу `events`, обробляє повідомлення послідовно та відправляє відповідь у `reply_to`.
5. `GET /messages/result/{request_id}` повертає `pending`, доки результат ще не готовий, або `ready` з payload від воркера.

### Автоочистка результатів

- Повідомлення у черзі `results.<request_id>` мають TTL `RABBITMQ_RESULT_TTL_MS`.
- Сама черга результатів автоматично зникає після неактивності через `RABBITMQ_RESULT_QUEUE_EXPIRES_MS`.
- Коли клієнт забирає результат через API, черга видаляється одразу після читання.

## Конфігурація

Основні змінні для FastAPI та RabbitMQ описані в [.env.example](.env.example). 

- `APP_NAME` - назва застосунку.
- `APP_HOST` і `APP_PORT` - хост та порт API.
- `API_KEY` - ключ доступу для `X-API-Key`.
- `API_KEY_HEADER_NAME` - назва заголовка з ключем доступу.
- `RABBITMQ_DEFAULT_USER` і `RABBITMQ_DEFAULT_PASS` - облікові дані RabbitMQ.
- `RABBITMQ_HOST` і `RABBITMQ_PORT` - адреса RabbitMQ.
- `RABBITMQ_QUEUE` - вхідна черга, за замовчуванням `events`.
- `RABBITMQ_RESULT_QUEUE_PREFIX` - префікс черг результатів.
- `RABBITMQ_RESULT_TTL_MS` - TTL повідомлень у черзі результатів.
- `RABBITMQ_RESULT_QUEUE_EXPIRES_MS` - час життя черги без активності.

## Сервіси

- `api` - FastAPI застосунок на порту `8000`.
- `rabbitmq` - RabbitMQ з management UI на портах `5672` і `15672`.

RabbitMQ Management UI доступний за адресою `http://localhost:15672` з логіном і паролем із `.env`.

## Windows Worker

Воркер для Windows Server 2003 знаходиться в каталозі [windows_2003](windows_2003). Його окрема документація є у файлі [windows_2003/README_WINDOWS_2003.md](windows_2003/README_WINDOWS_2003.md).

Основна бізнес-логіка обробки повідомлень реалізована у функції `handle_message` у файлі [windows_2003/consumer.py](windows_2003/consumer.py). Саме там воркер читає payload, запускає `bridge.vbs`, отримує результат і публікує його назад у RabbitMQ.

## Розширення API

Нове HTTP-API додавайте у папці [app](app). Точки входу вже розбиті на окремі маршрути: health перевірка в [app/health.py](app/health.py), а обробка повідомлень у [app/messages.py](app/messages.py).