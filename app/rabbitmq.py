import asyncio
import json
import uuid
from typing import Any

import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage

from app.config import get_settings


def _result_queue_arguments() -> dict[str, int]:
    settings = get_settings()
    return {
        "x-message-ttl": settings.rabbitmq_result_ttl_ms,
        "x-expires": settings.rabbitmq_result_queue_expires_ms,
    }


async def _connect_with_retry(retries: int = 10, delay: int = 3) -> aio_pika.RobustConnection:
    settings = get_settings()
    last_exception: Exception | None = None

    for _ in range(retries):
        try:
            return await aio_pika.connect_robust(settings.rabbitmq_url)
        except Exception as exc:
            last_exception = exc
            await asyncio.sleep(delay)

    if last_exception is None:
        raise RuntimeError("Failed to connect to RabbitMQ")

    raise last_exception


def build_result_queue_name(request_id: str) -> str:
    settings = get_settings()
    return f"{settings.rabbitmq_result_queue_prefix}.{request_id}"


async def submit_request(payload: Any) -> str:
    """Publish payload to input queue and return request_id immediately."""
    settings = get_settings()
    connection = await _connect_with_retry()

    async with connection:
        channel = await connection.channel()
        await channel.declare_queue(settings.rabbitmq_queue, durable=True)
        request_id = str(uuid.uuid4())
        result_queue = build_result_queue_name(request_id)
        await channel.declare_queue(result_queue, durable=True, arguments=_result_queue_arguments())

        await channel.default_exchange.publish(
            Message(
                body=json.dumps(payload).encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                correlation_id=request_id,
                reply_to=result_queue,
            ),
            routing_key=settings.rabbitmq_queue,
        )

        return request_id


async def fetch_result(request_id: str, delete_queue_when_done: bool = True) -> Any | None:
    """Get response for request_id from output queue. Returns None if still pending."""
    connection = await _connect_with_retry()

    async with connection:
        channel = await connection.channel()
        result_queue = build_result_queue_name(request_id)
        queue = await channel.declare_queue(result_queue, durable=True, arguments=_result_queue_arguments())

        message: AbstractIncomingMessage | None = await queue.get(fail=False)
        if message is None:
            return None

        async with message.process():
            payload = json.loads(message.body.decode("utf-8"))

        if delete_queue_when_done:
            await queue.delete(if_unused=False, if_empty=True)

        return payload
