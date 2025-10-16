import os
import redis.asyncio as redis
from kombu.utils.url import safequote

redis_url = os.environ.get('REDIS_URL', 'redis://default:redispw@localhost:49154')
redis_client = redis.from_url(redis_url)

async def add_key_value_redis(key, value, expire=None):
    await redis_client.set(key, value)
    if expire:
        await redis_client.expire(key, expire)

async def get_value_redis(key):
    return await redis_client.get(key)

async def delete_key_redis(key):
    await redis_client.delete(key)
