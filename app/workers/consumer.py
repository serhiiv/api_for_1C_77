import asyncio
import json

import aio_pika
from aio_pika import Message
from aio_pika.abc import AbstractIncomingMessage

from app.core.config import get_settings
from app.messaging.rabbitmq import _connect_with_retry


async def run_consumer() -> None:
    settings = get_settings()
    connection = await _connect_with_retry()

    async with connection:
        channel = await connection.channel()
        # Process strictly one unacked message at a time.
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(settings.rabbitmq_queue, durable=True)

        async def handle_message(message: AbstractIncomingMessage) -> None:
            async with message.process():
                payload: dict = json.loads(message.body.decode("utf-8"))
                print(f"[consumer] received: {payload}")

                # --- Business logic goes here ---
                response: dict = {"status": "ok", "data": payload}
                # --------------------------------

                if message.reply_to:
                    await channel.default_exchange.publish(
                        Message(
                            body=json.dumps(response).encode("utf-8"),
                            correlation_id=message.correlation_id,
                        ),
                        routing_key=message.reply_to,
                    )

        await queue.consume(handle_message)
        print(f"[consumer] listening queue: {settings.rabbitmq_queue}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_consumer())
