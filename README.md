# Foundation Fundamentals — Backend Engineering & System Design

Welcome to **Foundation Fundamentals**. This repository is a structured, hands-on learning workspace designed to master core backend engineering, system design, and platform infrastructure concepts. 

Instead of reading dry theory, the curriculum is structured around building **SecureOrder**—a mini, production-ready order processing microservices system. 

---

## Project: SecureOrder (Mini Order Processing System)

SecureOrder is a distributed order processing system designed to teach you how to build, secure, scale, and orchestrate independent microservices. 

To keep the development process simple and focused on engineering concepts, **we use Python (FastAPI) throughout the entire codebase**. This avoids the boilerplate of Java/Spring Boot and lets us focus on core protocols, concurrency, event streaming, and caching mechanics.

### What We're Building

A simplified order processing system consisting of:
* **Frontend:** A React Single Page Application (SPA) providing a user dashboard for placing and viewing orders.
* **Order Service (Python/FastAPI):** Exposes REST endpoints to create orders, validates JWT tokens locally, writes to PostgreSQL, and publishes events.
* **Inventory Service (Python/FastAPI):** Manages product inventory levels, caches stock counts in Redis for high-speed reads, and handles stock allocation.
* **Notification Service (Python/FastAPI):** Consumes event messages asynchronously, performs deduplication, and sends simulated notifications (SMS/Email).

---

## Architecture Overview

All requests enter through the Nginx edge proxy, which coordinates routing, security, and rate limiting. The services communicate asynchronously via Apache Kafka.

```text
                                  ┌────────────────────────┐
                                  │      React Frontend    │
                                  └───────────┬────────────┘
                                              │ HTTP
                                              ▼
    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                     NGINX                                        │
    │                           (Reverse Proxy & Load Balancer)                        │
    │   - SSL/TLS Termination                                                          │
    │   - Rate Limiting (via Redis)                                                    │
    │   - Request Routing:                                                             │
    │     ├── /auth/*           ───────> Keycloak (IAM)                                │
    │     ├── /api/orders/*     ───────> Order Service (Python/FastAPI)                │
    │     ├── /api/inventory/*  ───────> Inventory Service (Python/FastAPI)            │
    │     └── /*                ───────> Static SPA Frontend                           │
    └─────────┬───────────────────────────────┬───────────────────────────────┬────────┘
              │                               │                               │
              ▼                               ▼                               ▼
    ┌───────────────────┐           ┌───────────────────┐           ┌───────────────────┐
    │     KEYCLOAK      │◄──────────┤   ORDER SERVICE   │           │ INVENTORY SERVICE │
    │  - User Registry  │ Token     │  (Python/FastAPI) │           │  (Python/FastAPI) │
    │  - OAuth2 / OIDC  │ Verify    │  - JWT Validation │           │  - JWT Validation │
    │  - Token Issuing  │ (Local)   │  - Create Order   │           │  - Stock Management│
    │  - Role Management│           │  - Publish Events │           │  - Cache Stock    │
    └───────────────────┘           └─────────┬─────────┘           └─────────┬─────────┘
                                              │                               │
                                              │ Publish                       │ Consume/Publish
                                              ▼                               ▼
    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                     KAFKA                                        │
    │                               (Event Streaming)                                  │
    │   Topics:                                                                        │
    │     ├── order.created                                                            │
    │     ├── order.confirmed                                                          │
    │     └── stock.updated                                                            │
    └─────────────────────────────────────────┬────────────────────────────────────────┘
                                              │
                                              │ Consume
                                              ▼
                                    ┌───────────────────┐
                                    │NOTIFICATION SERV. │
                                    │  (Python/FastAPI) │
                                    │  - Consume Events │
                                    │  - Send Email/SMS │
                                    │  - Dedup (Redis)  │
                                    └─────────┬─────────┘
                                              │
                                              ▼
    ┌──────────────────────────────────────────────────────────────────────────────────┐
    │                                     REDIS                                        │
    │                         (Caching & Utility Store)                                │
    │   Used by:                                                                       │
    │     ├── Nginx               ───────> Rate limiting state                         │
    │     ├── Order Service       ───────> Idempotency keys                            │
    │     ├── Inventory Service   ───────> Caching product stock data                  │
    │     └── Notification Service ───────> Message deduplication                       │
    └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Learning Roadmap

Mastering backend engineering requires peeling back the abstraction layers. We follow this 10-phase roadmap:

| Phase | Topic | What You'll Learn | Status |
| :---: | :--- | :--- | :---: |
| **1** | [Keycloak Fundamentals](./IAM/01-keycloak-fundamentals.md) | OAuth2, OIDC, JWT payload structures, token verification, roles & scopes. | **Completed** |
| **2** | [Nginx Deep Dive](./NGINX/01-nginx-fundamentals.md) | Reverse proxying, load balancing, SSL/TLS termination, rate limiting, location matching rules. | **Completed** |
| **3** | **Order Service (Python)** | FastAPI routing, Pydantic validation, SQLAlchemy ORM, PostgreSQL connection pools, Local JWT verification, Kafka publishers. | **Completed** |
| **4** | **Inventory Service (Python)** | Redis caching patterns (Cache-Aside, Write-Through), database synchronization, Kafka consumer loops, concurrent stock allocation. | **Completed** |
| **5** | **Notification Service (Python)** | Async execution, consuming event streams, implementing message deduplication in Redis (idempotency). | **Completed** |
| **6** | [Kafka Deep Dive](./MessagingQueue/01-kafka-fundamentals.md) | Partitions, Consumer Groups, Offsets, consumer lag, and dealing with broker failures. | **Completed** |
| **7** | [Redis Deep Dive](./Caching/01-redis-fundamentals.md) | Core data structures (Strings, Hashes, Sorted Sets), TTL expiration, distributed locks (Redlock), and rate limiting algorithms. | **Completed** |
| **8** | **Frontend Integration** | Building a React dashboard, integrating the Keycloak JS adapter, managing access tokens in browser memory. | **Completed** |
| **9** | **Docker Compose Orchestration** | Creating optimized Dockerfiles (multi-stage builds), structuring environment files, configuring container networking and startup dependencies. | **Completed** |
| **10** | [Service Mesh Fundamentals](./ServiceMesh/01-service-mesh-fundamentals.md) | Data Plane (Envoy sidecars) vs Control Plane (Istio/Linkerd), traffic management, observability, mTLS, and sidecar resilience. | **Completed** |
| **11** | [Advanced Patterns](./AdvancedPatterns/01-advanced-patterns.md) | Resilience patterns (Retry, Circuit Breakers, Fallbacks), Saga pattern for distributed transactions, and CQRS basics. | *In Progress* |


---

## Request Flow (How Everything Connects)

### 1. Authentication Flow (User Login)
1. The user visits the frontend application.
2. The user is redirected through **Nginx** to the **Keycloak** login page.
3. Upon entering valid credentials, Keycloak redirects back to the frontend with an `authorization_code`.
4. The frontend exchanges the code for a **JWT Access Token**, an **ID Token**, and a **Refresh Token**.

### 2. Transaction Flow (Order Placement)
1. The client places an order by sending a `POST /api/orders` request with the Access Token in the `Authorization` header.
2. **Nginx** intercepting the traffic:
   * Enforces rate limits using IP state records in **Redis**.
   * Offloads TLS (SSL Termination).
   * Routes the request to the **Order Service** upstream instance.
3. The **Order Service** processes the request:
   * Cryptographically validates the JWT signature locally using Keycloak's public keys.
   * Checks database for duplicate transactions (idempotency check via **Redis**).
   * Inserts the order as `PENDING` in the database.
   * Publishes an `order.created` event to **Kafka**.
4. The **Inventory Service**:
   * Consumes `order.created` from **Kafka**.
   * Performs a rapid stock check against its **Redis** cache.
   * Deducts items from database inventory.
   * Publishes a `stock.allocated` event back to **Kafka**.
5. The **Notification Service**:
   * Consumes `stock.allocated` from **Kafka**.
   * Saves the transaction ID in **Redis** (message deduplication) to guarantee the notification is sent exactly once.
   * Sends a simulated SMS/Email confirmation to the client.
