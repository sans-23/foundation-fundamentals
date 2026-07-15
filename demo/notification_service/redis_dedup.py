import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Standard Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def is_duplicate(event_id: str) -> bool:
    """
    Checks if we have already processed this event.
    Uses Redis SETNX (Set if Not eXists).
    Returns True if duplicate, False if it's the first time we see it.
    """
    key = f"processed_event:{event_id}"
    
    # setnx returns 1 if key was set (meaning it didn't exist), and 0 if it already existed
    is_new = redis_client.setnx(key, "1")
    
    if is_new:
        # It's a new event. Let's set a TTL so Redis doesn't grow infinitely.
        # We assume if an event is older than 24 hours, Kafka won't redeliver it.
        redis_client.expire(key, 86400) # 24 hours
        return False
    
    return True
