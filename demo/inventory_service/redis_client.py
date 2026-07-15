import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Connection pool for performance
pool = redis.ConnectionPool(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
redis_client = redis.Redis(connection_pool=pool)

def get_stock(product_id: str):
    stock = redis_client.get(f"stock:{product_id}")
    return int(stock) if stock is not None else None

def set_stock(product_id: str, stock: int):
    # Set with TTL of 1 hour (3600 seconds) to ensure eventual consistency
    redis_client.setex(f"stock:{product_id}", 3600, stock)

def decrement_stock(product_id: str, amount: int):
    # Atomic decrement in Redis
    return redis_client.decrby(f"stock:{product_id}", amount)
