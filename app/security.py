import hashlib, json
from fastapi import Depends, HTTPException, Request
from redis import Redis
from redis.exceptions import RedisError
from app.config import settings
redis_client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
async def enforce_rate_limit(request: Request):
    host = request.client.host if request.client else "unknown"
    try:
        count = redis_client.incr(f"rl:{host}")
        if count == 1:
            redis_client.expire(f"rl:{host}", 60)
        if count > settings.rate_limit_per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except RedisError:
        # Development fail-open policy; choose and test a deliberate production policy.
        return
def request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
