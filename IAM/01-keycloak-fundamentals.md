# Keycloak Fundamentals

## What is Keycloak?

Keycloak is an open-source **Identity and Access Management (IAM)** solution. It acts as an authentication and authorization server, offloading complex security requirements from your application code. 

Keycloak handles:
* **Authentication** — "Who are you?" (handles login pages, credentials, password policies, MFA, and social/enterprise login federation)
* **Authorization** — "What can you do?" (manages roles, permissions, scopes, and complex access policies)
* **Single Sign-On (SSO)** — Login once, access multiple independent applications/services without re-authenticating
* **Token Management** — Cryptographically signs, issues, validates, and refreshes JWT tokens (Access, ID, and Refresh tokens)

---

## Core Concepts

Understanding Keycloak's architecture starts with its core entities. Below is a breakdown of how they relate to one another:

### 1. Realm
A realm is a namespace/tenant. It isolates a set of users, credentials, roles, groups, and clients. 

```text
Keycloak Server
├── Master Realm (administrative tenant - do NOT use for applications)
└── SecureOrder Realm (our application realm)
    ├── Users (identities who log in)
    ├── Clients (applications requesting authentication)
    ├── Roles (permissions/labels assigned to users or clients)
    └── Identity Providers (external systems like Google, GitHub)
```

> [!IMPORTANT]  
> **The Master Realm Rule:** The `master` realm is strictly for Keycloak administration. Always create a custom realm (like `SecureOrder` above) for your application workloads to keep configurations, credentials, and users isolated.

### 2. Users & Groups
* **Users:** The actual entities (usually human users, but can be system accounts) logging into the realm. They have attributes like username, email, first name, last name, and custom attributes (e.g., `department_id`, `company_name`).
* **Groups:** Logical collections of users. Roles can be mapped to groups. When a user is added to a group, they automatically inherit all the roles assigned to that group.

### 3. Clients & Client Scopes
* **Clients:** Applications or services that request Keycloak to authenticate users or request tokens.
  * **Public Clients:** Frontends (React, Angular, Vue) or mobile applications. These run in environments where they *cannot* securely store a client secret. They must use flows like Authorization Code with PKCE.
  * **Confidential Clients:** Server-side applications (Spring Boot, Node.js backend, Go API). These can securely store a `client_secret` and perform server-to-server operations.
* **Client Scopes:** Common sets of claims or permissions that can be shared among multiple clients (e.g., `openid`, `profile`, `email`, `offline_access`). When a client requests a scope, Keycloak maps the corresponding claims into the issued tokens.

### 4. Roles
Roles are labels assigned to users or clients that declare a level of access.
* **Realm Roles:** Global roles defined at the realm level. They apply across all clients in that realm (e.g., `admin`, `standard-user`).
* **Client (Resource) Roles:** Roles defined specifically within a single client (e.g., `create-order` and `view-orders` within the `order-service` client). In microservice architectures, this is the preferred way to assign permissions as it isolates service boundaries.

### 5. Identity Providers & User Federation
* **Identity Providers (IdP):** Keycloak can delegate authentication to third-party providers (e.g., Google, GitHub, Okta) using standard protocols like OpenID Connect or SAML 2.0.
* **User Federation:** Integrating existing user storage (like LDAP or Microsoft Active Directory) so Keycloak can sync, read, and authenticate users from those external databases without needing manual migration.

---

## 4. Protocols

Keycloak leverages industry-standard protocols to communicate with clients. Here is a comparison of their usage:

| Protocol | Purpose | Our Use Case |
| :--- | :--- | :--- |
| **OpenID Connect (OIDC)** | Authentication + Identity | **Primary protocol** — used to login users, get ID tokens containing user profiles, and manage active sessions. |
| **OAuth 2.0** | Authorization | Handled implicitly via OIDC to obtain Access Tokens used to call secure APIs. |
| **SAML 2.0** | Enterprise SSO | XML-based legacy/enterprise SSO. Not used in our modern microservices project. |

> [!NOTE]  
> **The OAuth2 vs. OIDC Distinction:**  
> * **OAuth 2.0** is an *authorization* framework. It deals with delegation (issuing an Access Token to a client so it can do things on behalf of a user). It does *not* specify how a client gets information about the user.
> * **OIDC** is an *identity* layer built directly on top of OAuth 2.0. It standardizes authentication by introducing the **ID Token** (containing profile information like name and email) and a `/userinfo` endpoint.

---

## OAuth2 / OIDC Flows

Depending on the client type, different flows are used to retrieve tokens.

### Authorization Code Flow (with PKCE) — For Frontend

This is the standard flow for Single Page Applications (like our React frontend) and mobile applications. Since the frontend codebase runs in the user's browser, it is a **public client** and cannot hide a client secret. 

**PKCE (Proof Key for Code Exchange)** prevents intercept attacks on the authorization code by introducing a temporary dynamic secret (`code_verifier`) and its hash (`code_challenge`).

```text
Browser (React)                Nginx                    Keycloak
       │                         │                          │
       │ 1. User clicks "Login"  │                          │
       ├────────────────────────>│                          │
       │                         │ 2. Redirect to /auth/... │
       │                         │    (with code_challenge) │
       │                         ├─────────────────────────>│
       │                                                    │
       │ 3. User sees Keycloak login page                   │
       │<───────────────────────────────────────────────────┤
       │                                                    │
       │ 4. User enters credentials                         │
       ├───────────────────────────────────────────────────>│
       │                                                    │
       │ 5. Keycloak validates, redirects back to browser   │
       │    (contains authorization_code)                   │
       │<───────────────────────────────────────────────────┤
       │                                                    │
       │ 6. Frontend exchanges code for tokens              │
       │    (sends authorization_code + raw code_verifier)  │
       ├───────────────────────────────────────────────────>│
       │                                                    │
       │ 7. Keycloak returns tokens:                        │
       │    [access_token + refresh_token + id_token]       │
       │<───────────────────────────────────────────────────┤
       │                                                    │
       │ 8. Frontend stores tokens, calls API with Bearer   │
       ├────────────────────────>│                          │
       │                         │ 9. Forward to service    │
       │                         │    Headers:              │
       │                         │    Authorization:        │
       │                         │      Bearer <access_tok> │
       │                         ├─────────────────────────> [Order Service]
```

#### How PKCE Solves the Security Problem:
1. **Dynamic Secret:** The browser generates a cryptographically random string: `code_verifier`.
2. **Challenge Hash:** The browser hashes the verifier: `code_challenge = SHA256(code_verifier)`.
3. **Login Request:** The browser sends the `code_challenge` in Step 2 to Keycloak.
4. **Token Exchange:** In Step 6, the browser sends the `authorization_code` along with the raw `code_verifier`. 
5. **Keycloak Verification:** Keycloak hashes the incoming `code_verifier` and matches it against the stored `code_challenge` from Step 2. If they match, Keycloak is guaranteed that the client requesting the token is the exact same application instance that initiated the login process.

---

### Client Credentials Flow — For Service-to-Service

When a backend microservice needs to call another microservice without any user context (e.g., a background job running in a `Notification Service` that needs metadata from the `Order Service`), we use the **Client Credentials Flow**. 

Because this is a server-to-server interaction, the calling service is a **confidential client** and can securely pass its `client_secret`.

```text
Notification Service                                     Keycloak
       │                                                     │
       │ 1. POST /token                                      │
       │    grant_type=client_credentials                    │
       │    client_id=notification-service                   │
       │    client_secret=xxx                                │
       ├────────────────────────────────────────────────────>│
       │                                                     │
       │ 2. Keycloak validates client credentials & returns: │
       │    { "access_token": "eyJ..." }                     │
       │<────────────────────────────────────────────────────┤
       │                                                     │
       │ 3. Now call Order Service using the token           │
       │    GET /orders                                      │
       │    Headers: { Authorization: Bearer eyJ... }        │
       └────────────────────────────────────────────────────> [Order Service]
```

---

## JWT (JSON Web Token) Structure

Tokens issued by Keycloak are formatted as **JSON Web Tokens (JWT)**. A JWT is a string composed of three distinct parts separated by dots (`.`):
$$\text{Header} \ . \ \text{Payload} \ . \ \text{Signature}$$

### 1. Header
The header contains metadata about the token, such as the algorithm used to sign it and the key identifier.
```json
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "key-id-abc"
}
```
* `alg`: The cryptographic algorithm used (RS256 represents RSA Signature with SHA-256).
* `kid`: Key ID. This allows resource servers to identify which public key in Keycloak's JWKS (certs endpoint) was used to sign the token.

### 2. Payload (Claims)
The payload contains the actual claims (attributes and data) about the user and the session.

```json
{
  "sub": "user-uuid-123",                            // Subject (Unique user ID in Keycloak)
  "iss": "http://keycloak:8080/realms/secureorder",  // Issuer (Who created the token)
  "aud": "order-service",                            // Audience (Intended recipient of the token)
  "exp": 1700000000,                                 // Expiration time (Seconds since Unix Epoch)
  "iat": 1699999700,                                 // Issued At time (Seconds since Unix Epoch)
  "realm_access": {
    "roles": ["user", "admin"]                       // Realm-level roles assigned to the user
  },
  "resource_access": {
    "order-service": {
      "roles": ["create-order", "view-orders"]       // Client-specific roles (for order-service)
    }
  },
  "preferred_username": "sanskar",                    // User's login name
  "email": "sanskar@example.com"                      // User's email
}
```

> [!TIP]
> **Realm Access vs. Resource Access:**  
> Use `realm_access` roles for broad application categories (e.g., checking if the user is a `super-admin`). Use `resource_access` roles for client-specific permissions (e.g., determining if this user has the `create-order` role specifically for the `order-service`).

### 3. Signature
The signature is used to verify that the token was not altered.
* Keycloak generates the signature by taking the base64-encoded Header, base64-encoded Payload, and signing them with Keycloak's **private key**.
* Microservices verify the signature using Keycloak's **public key**.
* **Stateless Validation:** Because the microservices verify the signature using the public key locally, they do not need to call Keycloak on every single request.

---

## Token Verification Mechanics

When a microservice receives a request containing a Bearer token in the `Authorization` header, it must validate it before processing the request.

```text
               ┌────────────────────────┐
               │    Incoming Request    │
               └───────────┬────────────┘
                           ▼
               ┌────────────────────────┐
               │  Extract Bearer Token  │
               └───────────┬────────────┘
                           ▼
               ┌────────────────────────┐
               │ Decode Header/Read kid │
               └───────────┬────────────┘
                           ▼
               ┌────────────────────────┐
               │  Is Public Key cached? ├───────┐
               └───────────┬────────────┘       │
                           │ No                 │ Yes
                           ▼                    │
               ┌────────────────────────┐       │
               │ Fetch keys from JWKS   │       │
               │ & cache public key     │       │
               └───────────┬────────────┘       │
                           │                    │
                           └──────────┬─────────┘
                                      ▼
               ┌────────────────────────┐
               │ Verify Cryptographic   │
               │       Signature        │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │    Signature Valid?    ├───────┐
               └───────────┬────────────┘       │ No
                           │ Yes                ▼
                           │          ┌───────────────────┐
                           ▼          │ Reject Request:   │
               ┌────────────────────────┐ │ 401 Unauthorized  │
               │ Validate claims        │ └─────────▲─────────┘
               │ (exp, iss, aud)        │           │
               └───────────┬────────────┘           │
                           │                        │
                           ▼                        │
               ┌────────────────────────┐           │
               │     Claims Valid?      ├───────────┘
               └───────────┬────────────┘ No
                           │ Yes
                           ▼
               ┌────────────────────────┐
               │     Extract Roles      │
               │   & Authorize Request  │
               └────────────────────────┘
```


### Steps of the Verification Process:
1. **Extraction:** Read the token from the `Authorization: Bearer <token>` header.
2. **Signature Verification:**
   * Extract the `kid` from the token header.
   * Look up the matching public key in the locally cached **JWKS (JSON Web Key Set)** certificates.
   * If not cached, call Keycloak's certs endpoint: `/realms/{realm-name}/protocol/openid-connect/certs`.
   * Verify the cryptographic signature using the key.
3. **Claims Verification:**
   * **Expiration Check (`exp`):** Ensure the current time is less than `exp`.
   * **Not Before Check (`nbf`):** Ensure the current time is greater than or equal to `nbf`.
   * **Issuer Check (`iss`):** Ensure the `iss` matches Keycloak's configured realm URL exactly.
   * **Audience Check (`aud`):** Ensure the `aud` matches the client ID configured in the microservice (preventing tokens intended for other clients from being reused here).

---

## Stateless vs. Stateful Token Validation

Architectures have two primary strategies for verifying JWTs:

### 1. Stateless Verification (Local Verification)
The resource server decodes the token, fetches the public key once, and validates the signature and claims locally.
* **Pros:** Highly scalable, fast (sub-millisecond verification), zero network overhead on Keycloak.
* **Cons:** Hard to revoke immediately. If a user is deleted, their access token remains valid until it reaches its `exp` time (e.g., 5-15 minutes).

### 2. Stateful Verification (Token Introspection)
The resource server makes an HTTP POST request to Keycloak's Introspection endpoint (`/protocol/openid-connect/token/introspect`) on *every* request, passing the token to ask: "Is this token still active?"
* **Pros:** Instant revocation. If a user is locked out in Keycloak, their next request immediately fails.
* **Cons:** Adds network latency to every API call, creates a single point of failure (if Keycloak is down or slow, all services fail).

### Recommended Hybrid Strategy:
Use **Stateless Validation** combined with:
1. **Short token lifetimes (TTL):** Keep the access token expiration short (e.g., 5 minutes) so that invalidation naturally takes effect quickly.
2. **Refresh tokens:** Use a longer-lived **Refresh Token** (e.g., 8 hours) stored securely (e.g., `HttpOnly` cookie) to exchange for new short-lived access tokens without forcing the user to log in again.
3. **Backchannel Logouts:** Keycloak can send HTTP POST logout requests directly to registered backends to clear caches/sessions when a user logs out.

---

## Authorization Models in IAM

Once a user's identity is authenticated, the system must decide if they are allowed to perform the requested operation.

```text
Authentication (Keycloak) ──> Identity Verified (JWT) ──> Authorization (Microservice)
                                                                ├── RBAC: Roles mapped to endpoints
                                                                ├── ABAC: Context rules evaluated
                                                                └── UMA: Keycloak centralized policies
```

### 1. RBAC (Role-Based Access Control)
Access decisions are based purely on roles assigned to users.
* *Example:* "Only users with the `admin` role can delete orders."
* *Implementation:* The microservice checks if `realm_access.roles` contains `"admin"` or if `resource_access.order-service.roles` contains `"delete-orders"`.

### 2. ABAC (Attribute-Based Access Control)
Access decisions are based on attributes of the user, the resource, and the current context (e.g., time of day, IP address).
* *Example:* "Users can edit orders only if they are the creator of the order (`user_id == order.created_by`) AND the request comes during business hours."
* *Implementation:* The microservice decodes the user's ID (`sub`) from the JWT, loads the order entity from the database, and evaluates the conditional logic in code.

### 3. Keycloak Authorization Services (UMA - User-Managed Access)
Centralizes authorization policies inside Keycloak rather than hardcoding role checks in microservices. Keycloak acts as a **PDP (Policy Decision Point)**.
* **Resource:** What is being protected (e.g., `/orders/{id}`).
* **Scope:** Actions allowed on the resource (e.g., `view`, `delete`).
* **Policy:** Conditions defined in Keycloak (e.g., "Must have role `manager` AND reside in country `IN`").
* **Permission:** Links resources/scopes to policies.
* *Flow:* The microservice asks Keycloak: "Can `user-uuid-123` perform `delete` on `/orders/abc`?" and acts on Keycloak's decision.
