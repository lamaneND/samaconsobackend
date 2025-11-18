from typing import Optional

import aio_pika

from app.config import (
    RABBITMQ_URL,
    RABBITMQ_DEFAULT_EXCHANGE,
    RABBITMQ_DEFAULT_QUEUE,
)


connection: Optional[aio_pika.RobustConnection] = None
channel: Optional[aio_pika.abc.AbstractChannel] = None


async def init_rabbitmq() -> None:
    global connection, channel
    if connection is None:
        try:
            connection = await aio_pika.connect_robust(RABBITMQ_URL)
            channel = await connection.channel()
            # Ensure default queue exists
            await channel.declare_queue(RABBITMQ_DEFAULT_QUEUE, durable=True)
        except Exception:
            # Allow application to start; failures visible via health checks
            connection = None
            channel = None


async def close_rabbitmq() -> None:
    global connection, channel
    if channel is not None:
        await channel.close()
        channel = None
    if connection is not None:
        await connection.close()
        connection = None


def get_channel() -> aio_pika.abc.AbstractChannel:
    if channel is None:
        raise RuntimeError("RabbitMQ channel not initialized. Call init_rabbitmq() on startup.")
    return channel


async def publish_message(message_body: bytes, routing_key: Optional[str] = None) -> None:
    ch = get_channel()
    rk = routing_key or RABBITMQ_DEFAULT_QUEUE
    exchange = RABBITMQ_DEFAULT_EXCHANGE
    if exchange:
        ex = await ch.get_exchange(exchange)
        await ex.publish(aio_pika.Message(body=message_body), routing_key=rk)
    else:
        await ch.default_exchange.publish(aio_pika.Message(body=message_body), routing_key=rk)

