# api_for_1C_77

Реалізація API до 1С:Підприємство 7.7 на базі FastAPI з RabbitMQ та Docker Compose.

## Структура проєкту

```text
.
├── app
│   ├── config.py
│   ├── health.py
│   ├── messages.py
│   ├── main.py
│   └── rabbitmq.py
├── windows_2003
│   ├── bridge.vbs
│   ├── config.py
│   ├── consumer.py
│   └── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Швидкий старт

1. Створіть `.env` на основі прикладу:

	```bash
	cp .env.example .env
	```

2. Запустіть сервіси:

	```bash
	docker compose up --build
	```

3. Перевірте health endpoint:

	```bash
	curl http://localhost:8000/health
	```

4. API захищене ключем доступу. У `.env` задайте `API_KEY`, а для запитів додавайте заголовок `X-API-Key` з тим самим значенням.

	```bash
	curl -X POST http://localhost:8000/messages/process \
	  -H "Content-Type: application/json" \
	  -H "X-API-Key: change-me" \
	  -d '{
	    "procedure": "ping",
	    "parameters": {
	      "consumer_number": 45733,
	      "start_date": "01.01.2025",
	      "end_date": "31.01.2025",
	      "commodity_name": "Бритва"
	    }
	  }'
	```

	Якщо ключ не передати або він неправильний, API поверне `401 Unauthorized`.

5. Надішліть JSON на обробку через API (асинхронна постановка в чергу):

	```bash
	curl -X POST http://localhost:8000/messages/process \
	  -H "Content-Type: application/json" \
	  -H "X-API-Key: change-me" \
	  -d '{
	    "procedure": "ping",
	    "parameters": {
	      "consumer_number": 45733,
	      "start_date": "01.01.2025",
	      "end_date": "31.01.2025",
	      "commodity_name": "Бритва"
	    }
	  }'
	```

	Приклад відповіді:

	```json
	{
	  "status":"accepted",
	  "request_id":"c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e",
	  "result_endpoint":"/messages/result/c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e"
	}
	```

5. Отримайте результат пізніше за `request_id`:

	```bash
	curl http://localhost:8000/messages/result/c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e
	```

	Поки обробка триває:

	```json
	{"status":"pending","request_id":"c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e"}
	```

	Після завершення:

	```json
	{
	  "status":"ready",
	  "request_id":"c0d2f0f0-3d7a-4c42-b72f-8a67ba995d8e",
	  "result":{
	    "status":"ok",
	    "data":{
	      "procedure":"ping",
	      "parameters":{
	        "consumer_number":45733,
	        "start_date":"01.01.2025",
	        "end_date":"31.01.2025",
	        "commodity_name":"Бритва"
	      }
	    }
	  }
	}
	```

## Як працює обмін повідомленнями

1. API приймає JSON у `POST /messages/process`.
2. API публікує повідомлення в RabbitMQ чергу `events` і одразу повертає `request_id`.
3. Для кожного `request_id` API використовує окрему вихідну чергу `results.<request_id>`.
4. Воркер читає `events` (лише одне повідомлення одночасно), виконує бізнес-логіку і публікує відповідь у `reply_to`.
5. Клієнт через деякий час викликає `GET /messages/result/{request_id}` і отримує `pending` або готовий результат.

### Автоочистка результатів

- Повідомлення у вихідній черзі `results.<request_id>` мають TTL (`RABBITMQ_RESULT_TTL_MS`, за замовчуванням 1 година).
- Сама вихідна черга автоматично видаляється після неактивності (`RABBITMQ_RESULT_QUEUE_EXPIRES_MS`, за замовчуванням 24 години).
- Якщо клієнт забрав результат через API, черга також видаляється одразу.

## Сервіси

- `api` - FastAPI застосунок, порт `8000`.
- `rabbitmq` - RabbitMQ + management UI:
  - AMQP: `5672`
  - Web UI: `15672`

### Worker

Worker запускається на Windows Server 2003 (Python 3.4.4).

Переглядіть [windows_2003/README_WINDOWS_2003.md](windows_2003/README_WINDOWS_2003.md) для запуску на Windows Server 2003 із Python 3.4.4.

## RabbitMQ Management

- URL: `http://localhost:15672`
- Логін/пароль за замовчуванням: `guest/guest` (беруться з `.env`).

## Де додавати бізнес-логіку

Основну обробку JSON додайте у воркері в файлі `windows_2003/consumer.py` (у функції `handle_message`).
