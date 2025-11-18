from typing import Optional

from redis import asyncio as aioredis

from app.config import REDIS_URL, REDIS_DEFAULT_TTL_SECONDS


redis_client: Optional[aioredis.Redis] = None


async def init_redis() -> None:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        # simple ping to validate connection on startup
        try:
            await redis_client.ping()
        except Exception:
            # Defer failures to health checks/usage; app should still start
            pass


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None


def get_redis() -> aioredis.Redis:
    if redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() on startup.")
    return redis_client


async def cache_get(key: str) -> Optional[str]:
    try:
        client = get_redis()
        return await client.get(key)
    except Exception as e:
        # Log l'erreur mais ne lève pas d'exception pour ne pas casser l'app
        print(f"Cache get error for key {key}: {e}")
        return None


async def cache_set(key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
    try:
        client = get_redis()
        ttl = ttl_seconds if ttl_seconds is not None else REDIS_DEFAULT_TTL_SECONDS
        return await client.set(key, value, ex=ttl)
    except Exception as e:
        # Log l'erreur mais ne lève pas d'exception pour ne pas casser l'app
        print(f"Cache set error for key {key}: {e}")
        return False


async def cache_delete(key: str) -> int:
    try:
        client = get_redis()
        return await client.delete(key)
    except Exception as e:
        # Log l'erreur mais ne lève pas d'exception pour ne pas casser l'app
        print(f"Cache delete error for key {key}: {e}")
        return 0

