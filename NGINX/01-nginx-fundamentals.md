# NGINX Fundamentals & Deep Dive

## 1. What is NGINX?

**NGINX** (pronounced "engine-X") is an open-source, ultra-high-performance HTTP web server, reverse proxy server, load balancer, and API gateway. Originally authored by Igor Sysoev in 2004, it was created specifically to solve the **C10k problem**—the challenge of handling 10,000 concurrent client connections simultaneously on a single server without buckling under memory or CPU strain.

Unlike traditional web servers that rely on a thread-per-connection model, NGINX utilizes an asynchronous, event-driven, non-blocking architecture. This design allows it to handle hundreds of thousands of concurrent connections with an extremely small and predictable memory footprint.

## 2. Why NGINX? (In a Microservice Context)

In a microservices architecture, you rarely want clients (like browsers or mobile apps) talking directly to individual microservices. 

1. **Coupling:** Clients would need to know the IP address and port of every single service.
2. **Security:** Every service would need to handle SSL termination, rate limiting, and CORS.
3. **Refactoring:** If you split one service into two, you'd break the client.

Instead, we place NGINX at the edge of our network as an **API Gateway / Edge Proxy**. All external traffic hits NGINX first, which then securely and efficiently routes it to the correct backend service.

```text
                                     ┌─────────────────────────┐
                                     │     Client (Browser)    │
                                     └────────────┬────────────┘
                                                  │ HTTPS (Port 443)
                                                  ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────┐
 │                                       NGINX (Gateway)                                   │
 │                                                                                         │
 │   1. SSL Termination (Decrypts HTTPS)                                                   │
 │   2. Rate Limiting (Prevents DDoS using Redis for state)                                │
 │   3. Static Content Delivery (Serves React/Angular files directly)                      │
 │   4. Request Routing & Load Balancing                                                   │
 └─────────┬───────────────────────────────┬───────────────────────────────┬───────────────┘
           │ /auth                         │ /api/orders                   │ /api/inventory
           ▼                               ▼                               ▼
 ┌───────────────────┐           ┌───────────────────┐           ┌───────────────────┐
 │                   │           │                   │           │                   │
 │     Keycloak      │           │   Order Service   │           │ Inventory Service │
 │   (IAM Server)    │           │ (Python/FastAPI)  │           │ (Python/FastAPI)  │
 │                   │           │                   │           │                   │
 └───────────────────┘           └───────────────────┘           └───────────────────┘
```

### Core Responsibilities

| Capability | Description | Microservice Benefit |
| :--- | :--- | :--- |
| **Reverse Proxy** | Fetches resources from backend servers on behalf of the client. The client is unaware the backend exists. | Decouples the client from internal architecture; allows seamless backend scaling and refactoring. |
| **Load Balancer** | Distributes incoming traffic across a pool of backend servers (e.g., 3 instances of Order Service). | Prevents single points of failure, ensures high availability, and allows horizontal scaling. |
| **SSL/TLS Termination** | Handles the computationally heavy cryptographic handshake and decryption at the edge. | Backend services process simple HTTP. Reduces CPU load on microservices and centralizes certificate management. |
| **Rate Limiting** | Restricts how many requests a client can make in a given window (e.g., 10 req/sec). | Protects fragile backend databases from traffic spikes, brute-force attacks, and noisy neighbors. |
| **Static File Serving** | Directly serves HTML, CSS, JS, and image assets. | Highly optimized for disk I/O; completely offloads this burden from backend application servers. |
| **Request Routing** | Inspects the URL path or headers and forwards to specific upstream clusters. | Core requirement for API Gateways (e.g., routing `/api/users` to User Service). |

---

## 3. NGINX Internals: How It Works

To truly understand NGINX, you must understand how it handles concurrency.

### The Problem with Apache (Thread-Per-Connection)
Historically, servers like Apache used a **process-driven** or **thread-driven** approach. For every incoming HTTP connection, the OS creates a new thread. 
- A thread consumes memory (typically ~1MB-2MB for the stack).
- If you have 10,000 connections, you immediately consume 10GB of RAM just for threads.
- When a thread waits for a slow database query or a slow client network, it **blocks**. It sits idle, doing nothing, holding onto its memory. CPU context switching between 10,000 threads causes massive overhead.

### The NGINX Solution (Asynchronous & Event-Driven)
NGINX does **not** create a new thread per connection. Instead, it uses a highly optimized **Event Loop** (utilizing Linux `epoll` or FreeBSD `kqueue`).

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                             Master Process                             │
 │  - Reads config files                                                  │
 │  - Binds to network ports (80, 443)                                    │
 │  - Spawns and monitors worker processes                                │
 └────────────────────┬─────────────────────────────┬─────────────────────┘
                      │                             │
             ┌────────▼────────┐           ┌────────▼────────┐
             │                 │           │                 │
             │ Worker Process 1│           │ Worker Process 2│
             │   (CPU Core 0)  │           │   (CPU Core 1)  │
             │                 │           │                 │
             │  ┌───────────┐  │           │  ┌───────────┐  │
             │  │Event Loop │  │           │  │Event Loop │  │
             │  └─┬───▲───┬─┘  │           │  └─┬───▲───┬─┘  │
             └────┼───┼───┼────┘           └────┼───┼───┼────┘
                  │   │   │                     │   │   │
     Connect 1 ◄──┘   │   └──► Connect 3        │   │   └──► Connect 6
                      ▼                         ▼   ▼
                  Connect 2                 Conn 4 Conn 5
```

1. **Master Process**: Runs as `root`. It handles privileged operations (binding to port 80/443, reading SSL certs). It spawns unprivileged worker processes.
2. **Worker Process**: Usually, NGINX is configured to spawn **one worker process per physical CPU core** (`worker_processes auto;`). 
3. **The Event Loop**: Each worker process runs a single, continuous, non-blocking event loop. 
   - When a request comes in, the event loop accepts it.
   - If NGINX needs to read a file from disk or wait for a response from an upstream backend service, it **does not block**. 
   - It registers a callback and immediately moves on to process the next incoming request.
   - When the disk read finishes or the backend responds, the OS fires an event, and the loop picks up the callback and sends the response to the client.

Because of this, a single NGINX worker thread can handle tens of thousands of concurrent connections using only a few megabytes of RAM.

---

## 4. Core Configuration Concepts (`nginx.conf`)

NGINX configuration is structured using **Directives** grouped into **Contexts** (also known as blocks).

```nginx
# Global Context (Outside any block)
user www-data;
worker_processes auto; # Spawns 1 worker per CPU core
pid /run/nginx.pid;

# Events Context: Configures connection processing
events {
    # How many concurrent connections one worker can handle
    worker_connections 1024; 
    # Total Max Connections = worker_processes * worker_connections
}

# HTTP Context: Handles all HTTP/HTTPS traffic
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    # Access and Error logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Upstream Context: Defines a cluster of backend servers for load balancing
    upstream order_service_backend {
        server 10.0.1.10:8000;
        server 10.0.1.11:8000;
    }

    # Server Context: Defines a virtual host (domain/port)
    server {
        listen 80;
        server_name api.secureorder.com;

        # Location Context: Matches specific URL paths
        location /api/orders {
            proxy_pass http://order_service_backend;
        }
    }
}
```

---

## 5. Location Block Matching Rules (Crucial!)

When a request comes in (e.g., `GET /api/users`), NGINX must decide which `location` block should handle it. **The order of location blocks in the file does NOT dictate the order of evaluation.** 

NGINX evaluates locations based on specific modifiers and priority rules:

### Priority Order (Highest to Lowest):

1. **Exact Match (`=`)**: Matches the URI exactly. If matched, the search stops immediately. Highest performance.
   ```nginx
   location = /login { ... }
   ```
2. **Preferential Prefix Match (`^~`)**: Matches the beginning of the URI. If this matches, NGINX will **stop searching** for regular expressions.
   ```nginx
   location ^~ /images/ { ... }
   ```
3. **Regular Expression Match (`~` and `~*`)**: `~` is case-sensitive, `~*` is case-insensitive. **Important:** Regex locations *are* evaluated in the order they appear in the configuration file. The first one to match wins.
   ```nginx
   location ~* \.(jpg|jpeg|png)$ { ... }
   ```
4. **Standard Prefix Match (No Modifier)**: Matches the beginning of the URI. If multiple standard prefixes match, NGINX remembers the **longest matching prefix**, then checks Regex. If no Regex matches, it uses the longest standard prefix.
   ```nginx
   location /api/ { ... }
   ```

### Example Quiz:
Given the URI `/api/orders`:
- `location /api/` (Matches)
- `location /api/orders` (Matches - Longest prefix wins)
- `location ~ ^/api/orders$` (Matches - Regex overrides standard prefix)
- `location = /api/orders` (Matches - Exact match overrides EVERYTHING)

---

## 6. Deep Dives

### A. Reverse Proxy Deep Dive

When NGINX acts as a reverse proxy via `proxy_pass`, it effectively makes a brand new HTTP request to the backend server. 

Because of this, the backend server sees the request coming from **NGINX's IP Address**, not the original client's IP. To fix this, we must inject headers.

```nginx
location /api/ {
    proxy_pass http://backend_cluster;
    
    # Send the original Host header (e.g., api.secureorder.com)
    proxy_set_header Host $host;
    
    # Send the client's real IP address
    proxy_set_header X-Real-IP $remote_addr;
    
    # Append the client IP to the chain of proxies
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    
    # Tell the backend the original request was HTTPS
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### B. Load Balancing Algorithms

Defined within the `upstream` block, NGINX supports several algorithms for distributing traffic:

1. **Round Robin (Default)**
   - Requests are dealt out sequentially (Server A, Server B, Server C, Server A...).
   - **Best for:** Environments where backend servers have identical hardware and requests take roughly the same amount of time to process.

2. **Least Connections (`least_conn;`)**
   - Routes the request to the server with the fewest currently active connections.
   - **Best for:** Microservices where request processing times vary wildly (e.g., a reporting service where one request takes 10ms and another takes 10 seconds).

3. **IP Hash (`ip_hash;`)**
   - Hashes the client's IP address (typically the first three octets of IPv4) to determine the server. Ensures a specific client always hits the same backend.
   - **Best for:** Legacy stateful applications (Sticky Sessions). **Avoid in modern stateless microservices!**

4. **Weighted Load Balancing**
   - You can assign weights to direct more traffic to beefier machines.
   ```nginx
   upstream backend {
       server backend1.example.com weight=3; # Receives 75% of traffic
       server backend2.example.com weight=1; # Receives 25% of traffic
   }
   ```

### C. SSL/TLS Termination

SSL Termination means NGINX handles the encryption overhead. It decrypts incoming HTTPS requests and forwards them as HTTP to the backend.

```nginx
server {
    listen 443 ssl;
    server_name myapp.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # Recommended: only allow modern TLS versions
    ssl_protocols TLSv1.2 TLSv1.3;

    location / {
        proxy_pass http://internal_backend; # Plain HTTP
    }
}

# Redirect all HTTP to HTTPS
server {
    listen 80;
    server_name myapp.com;
    return 301 https://$host$request_uri;
}
```

### D. Rate Limiting (Leaky Bucket)

NGINX implements rate limiting using the **Leaky Bucket** algorithm.
- Imagine a bucket with a hole in the bottom.
- Requests pour into the bucket from the top at an unpredictable rate.
- Requests leak out the bottom at a strict, constant rate (e.g., 5 requests per second).
- If requests pour in faster than they leak, the bucket fills up. If the bucket overflows, NGINX drops the request and returns a `503 Service Unavailable` (or `429 Too Many Requests`).

```nginx
http {
    # Define a shared memory zone named 'mylimit' (10MB size can store ~160k IP addresses)
    # Rate limit: 5 requests per second per IP ($binary_remote_addr)
    limit_req_zone $binary_remote_addr zone=mylimit:10m rate=5r/s;

    server {
        location /api/login {
            # Apply the limit. 
            # 'burst=10' is the bucket size (allows brief spikes without immediately rejecting).
            # 'nodelay' means if there's room in the burst bucket, process immediately, don't artificially delay it to enforce the exact 5r/s cadence.
            limit_req zone=mylimit burst=10 nodelay;
            
            proxy_pass http://auth_service;
        }
    }
}
```

### E. Health Checks & Failover

In Open Source NGINX, health checks are **Passive** (In-Band). NGINX only knows a server is down if it tries to send a real user request to it and the connection fails or times out.

```nginx
upstream backend_cluster {
    # If a server fails 3 times within a 10-second window, 
    # NGINX marks it as "down" for 30 seconds.
    server 10.0.1.1 max_fails=3 fail_timeout=30s;
    server 10.0.1.2 max_fails=3 fail_timeout=30s;
}
```
*(Note: NGINX Plus, the paid commercial version, offers **Active** health checks where NGINX proactively pings the backend on a timer).*

---

## 7. Common Interview Questions

**Q: What is the difference between a Forward Proxy and a Reverse Proxy?**
* **Forward Proxy:** Sits in front of the **client**. It hides the client's identity from the internet (e.g., a corporate VPN, or a school network proxy restricting websites). The internet thinks the request came from the proxy.
* **Reverse Proxy:** Sits in front of the **server**. It hides the server's identity from the internet. The client thinks the reverse proxy is the actual web server.

**Q: Why is NGINX drastically faster than Apache for static content?**
* Apache uses a process-per-connection model. To serve a static image, Apache spins up a thread, blocking on disk I/O. NGINX uses a non-blocking event loop. It asks the OS for the file (using optimized syscalls like `sendfile()`) and moves on to the next request immediately, utilizing negligible memory and CPU.

**Q: How do you gracefully reload NGINX configurations without dropping current connections?**
* Run `nginx -s reload`. The Master process reads the new config, starts *new* worker processes with the new config, and sends a graceful shutdown signal to the *old* worker processes. The old workers finish serving their current requests and then exit. Zero downtime.

**Q: What happens if you don't use `proxy_set_header X-Forwarded-For`?**
* Every backend service logs will show that 100% of the traffic is coming from the NGINX server's internal IP address. You lose all visibility into the geographic origin and identity of your actual users, making analytics and fraud detection impossible.

**Q: What is the C10K problem?**
* The challenge of optimizing network sockets to handle 10,000 concurrent connections at once on a single server. Traditional thread-per-connection servers (like Apache) would exhaust memory and CPU with context switching at this scale. NGINX was designed from scratch to solve this using event loops (`epoll`/`kqueue`), handling hundreds of thousands of connections with a tiny memory footprint.

**Q: Explain the difference between `proxy_pass http://backend` and `proxy_pass http://backend/`?**
* Without the trailing slash, NGINX appends the full matched URI to the upstream URL. With the trailing slash, NGINX strips the matched location prefix from the URI before forwarding. This subtle difference is one of the most common sources of NGINX misconfiguration bugs.
