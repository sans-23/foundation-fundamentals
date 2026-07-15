# Advanced Patterns in Distributed Systems

## 1. Retry with Exponential Backoff

### The Problem: Transient Failures

In distributed systems, services talk to each other over the network. Networks are inherently unreliable. A database might be momentarily overloaded, a Kafka broker might be rebalancing partitions, or a downstream API might return a `503` because it's deploying a new version.

These are **transient failures** — they resolve themselves within seconds or minutes. The worst thing your service can do is immediately give up and return an error to the user.

### The Naive Solution: Immediate Retry (DON'T DO THIS!)

```python
# ❌ BAD: This will hammer the failing service and make things WORSE
for i in range(5):
    try:
        response = call_database()
        break
    except Exception:
        pass  # Immediately retry
```

If the database is overloaded and 100 instances of your service all retry instantly, you create a **Retry Storm** — the failing service gets bombarded with even MORE requests, ensuring it never recovers.

### The Correct Solution: Exponential Backoff + Jitter

Instead of retrying immediately, you wait progressively longer between each attempt:

```text
Attempt 1: Wait  1 second
Attempt 2: Wait  2 seconds
Attempt 3: Wait  4 seconds
Attempt 4: Wait  8 seconds
Attempt 5: Wait 16 seconds (capped at max_delay)
```

The formula is: `delay = min(base_delay * 2^attempt, max_delay)`

But there's still a problem! If 100 instances all start retrying at the same time, they'll all wait 1 second, then all retry simultaneously, then all wait 2 seconds, etc. They're **synchronized**.

**Jitter** solves this by adding randomness:
```text
delay = min(base_delay * 2^attempt, max_delay) * random(0.5, 1.5)
```

This spreads retries across time, preventing thundering herds.

```text
┌──────────────────────────────────────────────────────────────────────┐
│                  Exponential Backoff + Jitter                        │
│                                                                      │
│  Attempt 1       Attempt 2           Attempt 3                       │
│     │               │                    │                           │
│     ▼               ▼                    ▼                           │
│  ───X───────────────X────────────────────X──────────────► time       │
│     ◄──1.2s──►      ◄────2.7s────►       ◄──────5.1s──────►         │
│     (random)        (random)             (random)                    │
│                                                                      │
│  Without jitter, ALL clients retry at the exact same moments.        │
│  With jitter, retries are scattered, giving the server breathing     │
│  room to recover.                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### Implementation (Python)

```python
import time
import random

def retry_with_backoff(func, max_retries=5, base_delay=1.0, max_delay=30.0):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise  # Final attempt failed, propagate the error
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * random.uniform(0.5, 1.5)
            print(f"Attempt {attempt+1} failed: {e}. Retrying in {jitter:.1f}s...")
            time.sleep(jitter)
```

---

## 2. Circuit Breaker Pattern

### The Problem: Cascading Failures

Imagine the Order Service calls the Inventory Service to check stock. If the Inventory Service is down, each request from the Order Service will:
1. Wait for the connection timeout (e.g., 30 seconds)
2. Fail
3. The next request does the same thing

Now the Order Service is stuck waiting on a dead service, its own request threads are exhausted, and it starts failing too. The Notification Service, which depends on the Order Service, also starts failing. **One service going down takes the entire system down.** This is a cascading failure.

### The Solution: Circuit Breaker State Machine

The Circuit Breaker pattern is borrowed from electrical engineering. Just like an electrical circuit breaker "trips" to prevent a fire when too much current flows, a software circuit breaker "trips" to prevent cascading failures when too many errors occur.

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    Circuit Breaker State Machine                     │
│                                                                      │
│   ┌──────────┐    failure_threshold     ┌──────────┐                │
│   │          │    exceeded              │          │                │
│   │  CLOSED  │ ─────────────────────►   │   OPEN   │                │
│   │ (Normal) │                          │ (Failing)│                │
│   │          │   ◄─────────────────     │          │                │
│   └──────────┘   probe succeeds         └─────┬────┘                │
│        ▲                                      │                     │
│        │                              recovery_timeout              │
│        │         ┌──────────────┐       expires│                    │
│        │         │              │              │                    │
│        └─────────┤  HALF-OPEN   │ ◄────────────┘                    │
│    probe         │ (Testing)    │                                    │
│    succeeds      │              │                                    │
│                  └──────┬───────┘                                    │
│                         │                                            │
│                    probe fails ──► back to OPEN                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Three States:**

1. **CLOSED** (Normal Operation): All requests pass through to the downstream service. The breaker monitors failures. If the failure count exceeds a threshold (e.g., 5 failures in 60 seconds), the breaker **trips** to OPEN.

2. **OPEN** (Failing Fast): All requests are **immediately rejected** without even attempting to call the downstream service. This is the key insight — instead of waiting 30 seconds for a timeout, the breaker returns an error in microseconds. A **Fallback** response can be returned instead (e.g., cached data, a default value, or a friendly error message). After a configurable `recovery_timeout` (e.g., 30 seconds), the breaker transitions to HALF-OPEN.

3. **HALF-OPEN** (Probing): The breaker allows a **single probe request** through to the downstream service.
   - If it succeeds → the breaker transitions back to **CLOSED** (service has recovered).
   - If it fails → the breaker transitions back to **OPEN** (service is still down).

### Implementation (Python)

```python
import time
import threading

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self.lock = threading.Lock()

    def call(self, func, fallback=None):
        with self.lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                else:
                    if fallback:
                        return fallback()
                    raise Exception("Circuit is OPEN: service unavailable")

        try:
            result = func()
            with self.lock:
                self.failure_count = 0
                self.state = "CLOSED"
            return result
        except Exception as e:
            with self.lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
            if fallback:
                return fallback()
            raise
```

---

## 3. Fallback & Graceful Degradation

A **Fallback** is a backup behavior that activates when the primary path fails. It ensures the user gets *something* useful instead of a raw `500 Internal Server Error`.

### Common Fallback Strategies

| Strategy | Description | Example |
| :--- | :--- | :--- |
| **Cached Data** | Return stale but valid data from a cache | Inventory Service returns last-known stock from Redis when Postgres is down |
| **Default Value** | Return a safe, hardcoded default | Rating Service returns 4.0 stars when the ML model is unavailable |
| **Queue for Later** | Accept the request and process it asynchronously | Order Service saves to a local queue when Kafka is down, flushes when Kafka recovers |
| **Degraded Response** | Return partial data | Product page shows name/price but omits reviews when the Review Service is down |

### In Our SecureOrder System

```text
Order Service ──► Kafka Publisher
                     │
                     ├── SUCCESS ──► Event published normally
                     │
                     └── FAILURE (Circuit OPEN)
                            │
                            └── FALLBACK: Log the event to a local file
                                         for manual replay later.
                                         Return 202 Accepted to the user.
```

The key principle: **Fail gracefully, never catastrophically.**

---

## 4. Bulkhead Pattern

### The Problem: Resource Exhaustion

If your service has a single thread pool of 100 threads, and a slow downstream dependency causes 90 of those threads to hang waiting for a response, only 10 threads remain to serve all other endpoints. A single failing dependency starves the entire service.

### The Solution: Isolate Resources

Named after the bulkheads in a ship's hull that prevent a leak in one compartment from flooding the entire ship.

```text
┌───────────────────────────────────────────────────┐
│                   Order Service                    │
│                                                    │
│   ┌─────────────────┐   ┌─────────────────┐      │
│   │  Bulkhead A      │   │  Bulkhead B      │      │
│   │  (DB Calls)      │   │  (Kafka Calls)   │      │
│   │  Max: 50 threads │   │  Max: 30 threads │      │
│   └─────────────────┘   └─────────────────┘      │
│                                                    │
│   If Kafka hangs, only Bulkhead B is affected.     │
│   Bulkhead A (DB) continues serving requests       │
│   normally with its dedicated 50 threads.          │
└───────────────────────────────────────────────────┘
```

In Python, this is typically implemented using separate thread pools or async semaphores:

```python
import asyncio

# Create isolated semaphores for different dependencies
db_semaphore = asyncio.Semaphore(50)      # Max 50 concurrent DB calls
kafka_semaphore = asyncio.Semaphore(30)   # Max 30 concurrent Kafka calls

async def call_database():
    async with db_semaphore:
        # If all 50 slots are taken, new callers wait here
        return await db.execute(query)

async def publish_to_kafka():
    async with kafka_semaphore:
        # Kafka hanging doesn't affect DB callers
        return await producer.send(event)
```

---

## 5. Saga Pattern (Distributed Transactions)

### The Problem: No ACID Across Services

In a monolith, you can wrap multiple database operations in a single transaction:

```sql
BEGIN;
  INSERT INTO orders (id, status) VALUES (1, 'CONFIRMED');
  UPDATE inventory SET stock = stock - 1 WHERE product_id = 'P1';
  INSERT INTO payments (order_id, amount) VALUES (1, 99.99);
COMMIT;
```

If any step fails, the entire transaction rolls back. **ACID guarantees.**

In microservices, the `orders` table, the `inventory` table, and the `payments` table live in **different databases owned by different services**. You cannot wrap them in a single transaction. If the payment fails after inventory was already deducted, you have an inconsistency.

### The Solution: Saga

A Saga is a sequence of local transactions where each step publishes an event that triggers the next step. If any step fails, **compensating transactions** are executed to undo the previous steps.

### Two Flavors:

#### A. Choreography-Based Saga (Event-Driven)

Each service listens for events and reacts independently. There is no central coordinator.

```text
┌─────────────┐   order.created   ┌─────────────┐   stock.allocated   ┌─────────────┐
│             │ ──────────────►   │             │ ──────────────────►  │             │
│   Order     │                   │  Inventory  │                      │  Payment    │
│   Service   │                   │  Service    │                      │  Service    │
│             │  ◄──────────────  │             │  ◄──────────────────  │             │
└─────────────┘  stock.failed     └─────────────┘  payment.failed      └─────────────┘
                  (compensate:                      (compensate:
                   cancel order)                     restore stock)
```

**This is what our SecureOrder system uses!** The Order Service publishes `order.created`, the Inventory Service reacts and publishes `stock.allocated`, and the Notification Service reacts to send the confirmation.

**Pros:** Simple, loosely coupled, no single point of failure.  
**Cons:** Hard to debug, difficult to understand the full flow, no central place to see the saga's current state.

#### B. Orchestration-Based Saga (Coordinator)

A central **Saga Orchestrator** service explicitly tells each participant what to do and when.

```text
                    ┌──────────────────┐
                    │  Saga Orchestrator │
                    │  (Order Saga)      │
                    └────────┬─────────┘
                             │
              Step 1         │         Step 2              Step 3
         ┌───────────────────┼────────────────────┬────────────────────┐
         ▼                   │                    ▼                    ▼
  ┌─────────────┐            │            ┌─────────────┐      ┌─────────────┐
  │   Order     │            │            │  Inventory  │      │  Payment    │
  │   Service   │            │            │  Service    │      │  Service    │
  └─────────────┘            │            └─────────────┘      └─────────────┘
                             │
                    On Failure: Execute
                    compensating actions
                    in reverse order
```

**Pros:** Easy to understand the flow, centralized error handling, clear saga state.  
**Cons:** The orchestrator is a single point of failure, tighter coupling.

### When to Use Which?

| Factor | Choreography | Orchestration |
| :--- | :--- | :--- |
| **Complexity** | Best for simple, linear flows (3-5 steps) | Better for complex flows with branching logic |
| **Coupling** | Services are independent | Services depend on the orchestrator |
| **Debugging** | Harder (trace events across services) | Easier (check orchestrator state) |
| **Our System** | ✅ We use this | For future complex workflows |

---

## 6. CQRS (Command Query Responsibility Segregation)

### The Problem: Read vs Write Optimization Conflict

In most applications, reads vastly outnumber writes (often 100:1). But reads and writes have fundamentally different requirements:

- **Writes** need strong consistency, validation, and ACID transactions.
- **Reads** need speed, denormalized data, and can tolerate slight staleness.

A single database model serving both leads to painful compromises.

### The Solution: Separate Models

CQRS separates the **Command** (write) model from the **Query** (read) model.

```text
┌─────────────────────────────────────────────────────────────────────┐
│                            CQRS Architecture                         │
│                                                                      │
│  ┌──────────────┐                         ┌──────────────┐          │
│  │   Command     │     Event Published     │   Query       │          │
│  │   (Write)     │ ───────────────────────►│   (Read)      │          │
│  │              │     via Kafka/Events     │              │          │
│  │  PostgreSQL   │                         │  Redis / ES   │          │
│  │  (Normalized) │                         │ (Denormalized)│          │
│  └──────────────┘                         └──────────────┘          │
│        ▲                                        │                    │
│        │                                        │                    │
│   POST /orders                            GET /orders                │
│   (Create, Update)                        (List, Search)             │
└─────────────────────────────────────────────────────────────────────┘
```

### In Our SecureOrder System

We are *already* doing a lightweight form of CQRS without realizing it:
- **Write Path**: Order Service writes to **PostgreSQL** (normalized, ACID).
- **Read Path**: Inventory Service reads stock from **Redis** (denormalized, fast).
- **Sync Mechanism**: Kafka events keep the read model updated asynchronously.

The trade-off is **Eventual Consistency** — there's a brief window where the Redis cache might be stale. But for most applications, this is perfectly acceptable and delivers massive performance gains.

---

## 7. Common Interview Questions

**Q: What's the difference between a Retry and a Circuit Breaker?**
* Retry repeatedly attempts the same operation hoping for success. Circuit Breaker *prevents* attempts entirely when the downstream service is known to be unhealthy. In practice, you use both together — retry within a closed circuit, and fail fast when the circuit is open.

**Q: Why is jitter important in retry logic?**
* Without jitter, all clients that fail at roughly the same time will retry at the exact same intervals, creating synchronized "retry storms" that overwhelm the recovering service. Jitter adds randomness to spread retries across time.

**Q: What are compensating transactions in a Saga?**
* They are the "undo" operations. If Step 3 of a Saga fails, you execute compensating transactions for Steps 2 and 1 in reverse order. For example, if Payment fails, you compensate by restoring the deducted inventory and canceling the order.

**Q: When would you NOT use CQRS?**
* When your application has simple CRUD operations, roughly equal read/write ratios, or when the added complexity of maintaining two models and an event sync mechanism doesn't justify the performance gains. CQRS adds significant operational overhead.

**Q: How does the Bulkhead pattern differ from the Circuit Breaker?**
* Circuit Breaker prevents calls to a failing dependency. Bulkhead isolates resource pools so that a failure in one dependency doesn't consume resources needed by others. They are complementary — you typically use both together.
