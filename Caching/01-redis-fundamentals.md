# Redis & Caching Fundamentals

## What is Redis?

**Redis** (Remote Dictionary Server) is an open-source, in-memory, key-value data structure store. It is commonly used as a database, cache, message broker, and queue. 

Because it stores all data in RAM, it provides sub-millisecond latency for read and write operations. Natively supporting data structures (like lists, hashes, and sorted sets) allows complex operations to be executed directly on the database engine.

---

## Why Redis? (in a Microservices Context)

In our **SecureOrder** microservices architecture, Redis acts as a high-performance helper utility across different layers:

```text
  React Frontend
       │
       ▼
   ┌───────┐
   │ Nginx │ ───────> Rate Limiting State (Stashed in Redis)
   └───┬───┘
       ├─────────────────────────┬─────────────────────────┐
       ▼                         ▼                         ▼
 ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
 │ Order Service │         │ Inventory Serv│         │ Notification S│
 └───────┬───────┘         └───────┬───────┘         └───────┬───────┘
         │ Idempotency             │ Product Cache           │ Deduplication
         ▼ Keys                    ▼                         ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                            REDIS                              │
   └───────────────────────────────────────────────────────────────┘
```

1. **Nginx Rate Limiting:** Stores sliding window requests per IP to enforce rate limits.
2. **Order Service Idempotency:** Tracks transaction tokens (idempotency keys) to prevent duplicate order placements.
3. **Inventory Service Caching:** Caches hot product stock data to prevent database bottlenecks during sales.
4. **Notification Service Deduplication:** Stores processed event IDs to prevent duplicate emails or SMS messages if Kafka redelivers events.

---

## Redis Internals & Core Architecture

### 1. The Single-Threaded Event Loop
One of Redis's most distinctive architectural traits is that it executes commands in a **single main thread**.

#### How it works:
Redis uses non-blocking sockets and a multiplexing event loop (using `epoll` or `kqueue`). It continuously listens for events (reads, writes, connections), queues them, and processes them sequentially in a single thread.

```text
 Client Connections
  (Conn 1) (Conn 2) (Conn 3)
     │        │        │
     ▼        ▼        ▼
 ┌─────────────────────────┐
 │   Multiplexer (epoll)   │
 └────────────┬────────────┘
              ▼
 ┌─────────────────────────┐
 │      Event Queue        │
 └────────────┬────────────┘
              ▼
 ┌─────────────────────────┐
 │    Single Main Thread   │ ───> Executes Commands Sequentially
 └─────────────────────────┘
```

#### Why Single-Threaded?
* **No Thread Contention:** No need for CPU locks, mutexes, or synchronization. Deadlocks are structurally impossible.
* **Low CPU Context Switching:** Thread context switching is highly expensive; running on a single thread maximizes CPU efficiency.
* **CPU is Not the Bottleneck:** Redis operations are memory-bound (RAM speed) and network-bound. The CPU easily outpaces network throughput.

---

### 2. Persistence Models: RDB vs. AOF

While Redis is primarily in-memory, it provides persistence options to survive crashes and reboots.

| Metric | RDB (Redis Database Snapshot) | AOF (Append-Only File) |
| :--- | :--- | :--- |
| **How it works** | Takes point-in-time binary snapshots of the dataset at configured intervals (e.g., every 5 mins). | Logs every write operation to a file as it happens. Rewrites log in the background to shrink it. |
| **Data Loss Risk** | **High.** If Redis crashes, you lose all data written since the last snapshot. | **Low.** If `appendfsync everysec` is used, you lose at most 1 second of data. |
| **Performance** | **Excellent.** The main process forks a child (`bgsave`) to do the disk write. The parent thread does no disk I/O. | **Slightly Slower.** Writing to disk on every command (or every second) adds small disk write latency. |
| **Recovery Speed** | **Fast.** It is a compact binary file containing the exact state. | **Slow.** Redis must replay every command in the log sequentially to reconstruct the state. |

> [!TIP]
> **Production Best Practice (Hybrid Mode):**  
> Use **AOF + RDB mixed persistence**. Redis writes RDB snapshots for quick recovery, and appends AOF write logs for modern updates. This gives you both fast startup times and durability.

---

### 3. Eviction Policies
When Redis memory runs out, it frees space using an **Eviction Policy**:
* **Noeviction (Default):** Returns errors for write operations, keeping read operations functional.
* **Allkeys-LRU (Least Recently Used):** Evicts the least recently accessed keys across all keys. (Recommended for standard caches).
* **Volatile-LRU:** Evicts the least recently accessed keys, but *only* among keys that have a configured TTL (expiration).
* **Allkeys-LFU (Least Frequently Used):** Evicts keys that have the lowest access count, regardless of when they were last accessed.
* **Volatile-TTL:** Evicts keys with the shortest remaining Time-To-Live (TTL).

---

## Redis Data Structures: When to Use What

Redis is not just a key-value store; it is a **data structures server**. Choosing the right structure is key to performance.

### 1. Strings
The basic type. It maps a key to a binary-safe string value (up to 512MB).
* **Commands:** `SET`, `GET`, `INCRBY`, `DECRBY`, `EXPIRE`
* **Use Cases:** Simple value caches, JSON serialization objects, integer counters (e.g., API hit counters).

### 2. Hashes
Maps string fields to string values. Ideal for representing objects.
* **Commands:** `HSET`, `HGET`, `HGETALL`, `HINCRBY`
* **Use Cases:** Storing database entity objects (e.g., User profiles, Product details).
  * *Example:* `HSET product:1001 name "Laptop" price "1200" stock "45"`

### 3. Lists
Ordered lists of string elements sorted by insertion order.
* **Commands:** `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `BRPOP` (blocking pop)
* **Use Cases:** Implementing queues and stacks.
  * *Example:* `LPUSH job_queue "send_email_task"` -> Backend workers call `BRPOP job_queue 0` to block and consume jobs.

### 4. Sets
Unordered collections of unique strings.
* **Commands:** `SADD`, `SREM`, `SISMEMBER`, `SINTER` (intersection)
* **Use Cases:** Tagging systems, unique visitors tracking, calculating intersections (e.g., "mutual friends").

### 5. Sorted Sets (ZSET)
Collections of unique strings where each element is mapped to a floating-point **score**. Elements are kept sorted by their score.
* **Commands:** `ZADD`, `ZRANGE`, `ZREMRANGEBYSCORE`
* **Use Cases:** Gaming leaderboards, priority queues, rate limiters (sliding window).

---

## Caching Patterns

When integrating Redis into your microservices, the application must manage synchronization between the cache and the primary database.

```text
1. Cache-Aside               2. Write-Through            3. Write-Behind (Write-Back)
   ┌─────────┐                  ┌─────────┐                  ┌─────────┐
   │   App   │                  │   App   │                  │   App   │
   └─┬─────┬─┘                  └────┬────┘                  └────┬────┘
     │     │                         │ Write                            │ Write
     │1.Get│ 2.Set                   ▼                                  ▼
     ▼     ▼                    ┌─────────┐                  ┌─────────┐
 ┌───────────┐                  │  Cache  │                  │  Cache  │
 │   Cache   │                  └────┬────┘                  └────┬────┘
 └───────────┘                       │ Write (Sync)               │ Write (Async)
     │                               ▼                            ▼
     │ 1.Get (Miss)             ┌─────────┐                  ┌─────────┐
     ▼                          │   DB    │                  │   DB    │
 ┌───────────┐                  └─────────┘                  └─────────┘
 │    DB     │
 └───────────┘
```

### 1. Cache-Aside (Lazy Loading)
The application handles the cache checking and populating.
* **Read Flow:** The app reads from the cache. If it's a *cache miss*, it queries the database, updates the cache, and returns the data.
* **Write Flow:** The app updates the database first, and then **deletes** the cache key. Deleting is safer than updating because it prevents race conditions where two updates write stale values.
* **Pros:** Only requested data is cached (resource efficient); cache node failures are non-fatal.
* **Cons:** First reads result in cache misses (higher initial latency).

### 2. Write-Through
The application treats the cache as the main data store.
* **Write Flow:** The application writes directly to the cache. The cache engine immediately writes the same update to the database synchronously.
* **Pros:** Data in the cache is never stale. Reads are always fast.
* **Cons:** Higher write latency because you write to both memory and disk sequentially.

### 3. Write-Behind (Write-Back)
* **Write Flow:** The application writes to the cache. The cache engine logs the write in memory and queues an asynchronous, batch background job to write the updates to the database.
* **Pros:** Extremely fast write speeds (you write only to memory).
* **Cons:** Risk of data loss. If the cache server crashes before the background queue writes to the database, updates are lost forever.

---

## Cache Failures & Mitigation Strategies

System design interviews heavily focus on how to handle failures when caching at scale.

### 1. Cache Penetration
* **The Problem:** Clients request keys that do **not** exist in either the cache or the primary database (e.g., querying for user ID `-9999`). Every request bypasses the cache and hits the database, which can crash the database under load.
* **Mitigation:**
  * **Cache Nulls:** Store an empty value in the cache with a short TTL (e.g., 2 minutes): `SET user:-9999 "NULL" EX 120`.
  * **Bloom Filter:** Place a space-efficient Bloom Filter in front of Nginx/Redis. The filter determines if a key *might* exist or *definitely does not* exist. If it doesn't, block the request immediately.

### 2. Cache Avalanche
* **The Problem:** A large subset of cached keys expires at the exact same time, or a Redis node crashes. All concurrent client requests fall back to the database at once, causing a crash.
* **Mitigation:**
  * **Jitter TTLs:** Add a small random offset (jitter) to expiration times: `TTL = base_ttl + random_offset` (e.g., 10 minutes + random 0–60 seconds).
  * **High Availability:** Deploy Redis Sentinel or Cluster to ensure automatic failover.

### 3. Cache Breakdown (Hotspot Key)
* **The Problem:** A single cached key that receives massive traffic (e.g., homepage layout, trending product) expires. During the brief window when the cache is empty, thousands of concurrent requests miss the cache and query the database at the exact same moment.
* **Mitigation:**
  * **Mutex Locking (SETNX):** If a cache miss occurs, the worker tries to acquire a lock in Redis before hitting the database. Only the worker that gets the lock queries the database and populates the cache; others wait and retry the cache.
  * **Always-on background refresh:** Never expire hot keys. A background worker periodically updates the cache before the TTL expires.

---

## Distributed Locks using Redis

In distributed systems, traditional language-level locks (like Python's `threading.Lock` or Java's `synchronized`) do not work because multiple instances run on different machines. We use Redis to implement distributed locks.

### Implementing a Lock:

To acquire a lock, use the `SET` command with the `NX` (Not Exists) and `PX` (Expiration in milliseconds) flags:

```redis
# Acquire lock: Key = lock_name, Value = unique_client_uuid, Expiry = 30000ms
SET order_lock_123 "client_uuid_abc" NX PX 30000
```
* **Why `NX`?** Ensures only the first client to request gets the lock.
* **Why Expiry (`PX`)?** Prevents deadlocks. If the client gets the lock but crashes, the lock will automatically release after 30 seconds.
* **Why `unique_client_uuid`?** Prevents a client from accidentally releasing a lock owned by another client.

### Releasing the Lock safely (Lua Script):
We must only release the lock if the stored UUID matches our own. Because checking the value and deleting the key requires multiple steps, we must execute them as an **atomic transaction** using a Lua script:

```lua
-- Lua Script executed inside Redis atomically
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
```

---

## Rate Limiting with Redis: Sliding Window Log

In microservices, rate limiting protects resources. Using Redis Sorted Sets (ZSETs), we can implement a highly accurate **Sliding Window Log** rate limiter.

### How it works:
Every time a user makes a request, we add a timestamp to a ZSET keyed by their user ID. We prune old timestamps outside our window and check the set size.

```text
ZSET: user_101_limit
┌───────────────────┬───────────────────┬───────────────────┐
│ Value (UUID/Time) │ 1699999710        │ 1699999715        │  ◄── Timestamps of requests
│ Score             │ 1699999710        │ 1699999715        │
└───────────────────┴───────────────────┴───────────────────┘
                    ▲                                       ▲
              Window Start                             Current Time
          (Current Time - 60s)
```

### Python Implementation Concept:
```python
import time
import redis

r = redis.Redis(host='localhost', port=6379, db=0)

def is_rate_limited(user_id: str, limit: int, window_seconds: int) -> bool:
    current_time = time.time()
    window_start = current_time - window_seconds
    key = f"rate_limit:{user_id}"
    
    # Start transaction pipeline
    pipe = r.pipeline()
    
    # 1. Remove elements older than window start
    pipe.zremrangebyscore(key, 0, window_start)
    
    # 2. Add current request timestamp
    pipe.zadd(key, {str(current_time): current_time})
    
    # 3. Get count of elements in window
    pipe.zcard(key)
    
    # 4. Set expire on the key to clean up inactive users
    pipe.expire(key, window_seconds + 10)
    
    # Execute transaction
    _, _, request_count, _ = pipe.execute()
    
    # Check limit
    if request_count > limit:
        return True # Limited
    return False # Allowed
```

---

## Common Interview Questions

### Q1: Why is Redis so fast even though it is single-threaded?
1. **In-Memory Storage:** Reading and writing from RAM is orders of magnitude faster than writing to SSDs or HDDs.
2. **Efficient Data Structures:** Custom structures designed for fast execution (e.g., Skip Lists for Sorted Sets, dicts for hashes).
3. **No Lock Contention:** Single-threaded execution means zero overhead for managing locks, context switching, or thread management.
4. **I/O Multiplexing:** Uses system selectors (`epoll` or `kqueue`) to handle multiple socket connections efficiently.

### Q2: What is the difference between Redis Sentinel and Redis Cluster?
* **Redis Sentinel:** A high-availability management tool. It monitors Master-Slave setups. If a master node dies, Sentinel automatically promotes a slave node to master. Clients connect through Sentinel.
* **Redis Cluster:** A scaling solution. It automatically shards (splits) data across multiple master nodes using 16,384 hash slots. It handles both high availability and horizontal write scaling.

### Q3: How do you prevent cache stampede/breakdown?
* Use **distributed locks (SETNX)**. If a cache miss occurs, acquisition of the lock is required before querying the DB.
* Use **logical expirations**. Store the expiration time *inside* the JSON cache value payload. A background thread reads the payload; if the logical expiration is close, it updates the cache asynchronously in the background while the current requests continue to read the cached data.

### Q4: What are the dangers of using Redis Keys command in production?
The `KEYS` command performs a blocking, linear $O(N)$ scan of all keys in the database. Because Redis is single-threaded, running `KEYS` will block all other clients and requests until the scan is complete (which can take seconds or minutes on large datasets). Always use `SCAN` instead, which iterates over keys incrementally without blocking the event loop.
