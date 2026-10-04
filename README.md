# LinkHub

LinkHub is an enterprise-grade link management SaaS for organizations that need secure smart links, analytics, team collaboration, and operational control. It is designed as a production-quality platform similar to Bitly Enterprise and TinyURL, but extended with private links, admin controls, org-level governance, rate limits, API key operations, and operational monitoring.

## Why this exists

The platform is built for the real SaaS use cases that production teams need:

- Share secure, branded, expiration-aware links.
- Control access with password protection, click limits, one-time links, and organization privacy.
- Run link analytics across geography, device, OS, referrer, and daily trends.
- Manage multi-tenant organizations with roles, invites, and auditability.
- Expose developer-friendly API endpoints with auth, refresh tokens, and API keys.
- Keep operations production-ready with Redis, Celery, monitoring, health checks, and structured logging.

## Architecture overview

LinkHub follows Clean Architecture with explicit separation of concerns:

Presentation Layer
  -> API routers and UI consumers
  -> request validation, DTO handling, response shaping

Application Layer
  -> services and use cases
  -> business orchestration, validation, policy enforcement

Domain Layer
  -> core business entities and rules
  -> link lifecycle, org membership, access policy, auth flows

Infrastructure Layer
  -> PostgreSQL access via SQLAlchemy
  -> Redis cache and rate limiting
  -> Celery workers and background jobs
  -> email delivery and observability

This separation keeps business logic independent from database, framework, and infrastructure details. It also supports scalability, independent testing, and cleaner maintenance as the platform grows.

## Technology decisions

### Backend: FastAPI + Python 3.12
FastAPI is used for high-performance async API development, strong type validation, an OpenAPI schema, and a very clean developer experience. Python 3.12 supports modern typing and stability for production backend work.

### Database: PostgreSQL
PostgreSQL is the durable source of truth for organizations, users, URLs, click events, API keys, and audit records. It provides relational integrity, transactional guarantees, and the query flexibility needed for analytics and multi-tenant access.

### ORM: SQLAlchemy
SQLAlchemy provides a clean object-relational mapping layer, transaction control, migrations, and type-safe data access models. It is a good fit for a production SaaS that needs scalable, maintainable persistence patterns.

### Auth: JWT + refresh tokens + bcrypt
Authentication uses access tokens for short-lived user sessions and refresh tokens for controlled token rotation. Passwords are hashed with bcrypt so the system avoids storing raw credentials. Password-reset links use random opaque tokens stored only as hashes and are single-use. This is a standard pattern for SaaS auth that balances security and operational usability.

### Cache and rate limiting: Redis
Redis is used for short-lived data caching, token-bucket rate limiting, and shared operational state. It reduces pressure on PostgreSQL and protects the platform from abusive access patterns.

### Background jobs: Celery + Redis broker
Celery handles non-blocking tasks like analytics processing, email delivery, scheduled cleanups, and notifications. It prevents latency spikes in the user-facing API and makes work execution more resilient and schedulable.

### Frontend: React + TypeScript + Tailwind
The frontend keeps a practical, product-first experience with clean state management, typed API calls, and predictable layouts. Tailwind speeds up maintainability while avoiding heavy UI complexity.

### Deployment: Docker + Docker Compose
Docker makes the stack portable and reproducible across local, CI, and deployment environments. Docker Compose is used to run the full app with PostgreSQL, Redis, API, worker, frontend, and observability services in one command.

### Monitoring: Prometheus + Grafana
These tools give the project operational visibility into API performance, system health, and platform-level metrics for serious production readiness.

### Logging: structured JSON logs
Structured logs improve correlation, debugging, and alerting across services. They also help SRE teams diagnose production incidents faster.

### Testing: pytest + Playwright + httpx
The project validates both backend logic and the user-facing flow. This is critical to avoid issues where business logic works but the real user experience breaks.

## Folder structure

```text
/
├── .github/
│   └── workflows/
│       └── ci.yml
├── backend/
│   ├── app/
│   │   ├── application/
│   │   │   └── services/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── errors.py
│   │   │   └── rate_limit/
│   │   ├── infrastructure/
│   │   │   ├── cache/
│   │   │   ├── db/
│   │   │   ├── email/
│   │   │   ├── repositories/
│   │   │   └── workers/
│   │   ├── presentation/
│   │   │   └── api/
│   │   │       └── v1/
│   │   └── main.py
│   ├── alembic/
│   ├── tests/
│   ├── .env.example
│   ├── pyproject.toml
│   └── requirements or venv managed by tooling
├── frontend/
│   ├── src/
│   ├── e2e/
│   ├── package.json
│   ├── playwright.config.ts
│   └── vite.config.ts
├── monitoring/
│   ├── prometheus/
│   └── grafana/
├── docker-compose.yml
├── docker-compose.production.yml
├── .gitignore
├── README.md
└── package-lock.json
```

## Database design

The database is relational and multi-tenant, with strong boundaries between users, organizations, links, audits, and operational records.

```text
Users
  - id
  - email
  - password_hash
  - full_name
  - is_verified
  - avatar_url
  - created_at
  - updated_at

Organizations
  - id
  - name
  - slug
  - owner_id
  - created_at
  - updated_at

OrganizationMembers
  - id
  - organization_id
  - user_id
  - role
  - status
  - invited_by
  - created_at

URLs
  - id
  - organization_id
  - created_by
  - original_url
  - short_code
  - title
  - custom_alias
  - is_active
  - is_archived
  - is_private
  - password_hash
  - expires_at
  - click_limit
  - one_time
  - created_at
  - updated_at

Clicks
  - id
  - url_id
  - user_id (nullable)
  - ip_address
  - country
  - city
  - browser
  - device
  - os
  - referrer
  - clicked_at

RefreshTokens
  - id
  - user_id
  - token_hash
  - expires_at
  - revoked_at
  - created_at

ApiKeys
  - id
  - user_id
  - organization_id
  - name
  - prefix
  - key_hash
  - last_used_at
  - revoked_at
  - created_at

AuditLogs
  - id
  - organization_id
  - user_id
  - action
  - resource_type
  - resource_id
  - metadata
  - created_at
```

ER diagram (text):

```text
Users ───< OrganizationMembers >─── Organizations
  │                                     │
  │                                     ├──< URLs
  │                                     │
  │                                     └──< AuditLogs
  │
  ├──< RefreshTokens
  ├──< ApiKeys
  └──< Clicks (via URL)

Organizations ──< URLs
URLs ──< Clicks
```

## API design

The backend is versioned under `/api/v1` to keep the public contract predictable while allowing future evolution.

Examples:

- `/api/v1/auth`
- `/api/v1/users`
- `/api/v1/urls`
- `/api/v1/organizations`
- `/api/v1/admin`

API conventions:

- RESTful resource naming.
- Standard HTTP status codes.
- Consistent error envelope for failures.
- Validation at request boundary.
- JWT-based auth for protected endpoints.
- Organization-scoped authorization rules.
- Rate limiting and audit logging on sensitive operations.

## Production readiness checklist

This project is structured to be interview-ready and production-minded:

- Clean architecture with separation of layers.
- Repository pattern for persistence access.
- Dependency injection-friendly service structure.
- DTOs and typed service contracts.
- JWT auth with refresh-token rotation.
- Secure password hashing.
- Redis-backed caching and rate limiting.
- Celery background workers.
- PostgreSQL relational model.
- API versioning and structured errors.
- Monitoring and health checks.
- Docker Compose-based deployment workflow.
- CI automation for lint, tests, build, and smoke validation.
- Organization-scoped API keys with membership validation and usage tracking.
- Migration drift checks with strict Alembic metadata validation.

## Milestone status

The project is being implemented in a production-first sequence:

1. Project setup
2. Authentication
3. Organizations
4. URL management
5. Redis and rate limiting
6. Analytics
7. Background workers
8. Admin features
9. Monitoring
10. Deployment

The current implementation includes the production-grade backend, frontend shell, org flows, protected link handling, Redis controls, analytics logic, admin UI, organization-scoped API keys, CI flow, and Docker orchestration.

## Operating notes

- Local development runs through Docker Compose.
- Compose assigns the frontend proxy the fixed address `172.31.240.2`; the API trusts forwarded client-IP headers only from that address. If that subnet conflicts with an existing Docker network, change the public network subnet, frontend address, and API `FORWARDED_ALLOW_IPS` together. For deployments with another reverse proxy in front of the frontend, add only that proxy's verified source address to `FORWARDED_ALLOW_IPS`.
- Mailpit is used for verification email testing in local and CI smoke flows.
- Redis is used for rate limiting and cache policy.
- Platform-admin account deactivation revokes the account's refresh sessions and API keys; reactivation does not restore those credentials.
- Access tokens carry a per-user authentication version. Password changes/resets and account deactivation invalidate previously issued access tokens immediately, including after account reactivation.
- Organization admins can invite members but cannot grant the admin role; only organization owners can invite admins or change member roles.
- Environment variables are configured through backend env files and deployment secrets.
- For a production Compose deployment, copy `backend/.env.production.example` to `backend/.env.production`, replace every `REPLACE_*` value with generated secrets (`openssl rand -hex 32` produces URL-safe random values), and set the public HTTPS hostname consistently in `PUBLIC_BASE_URL` and `CORS_ORIGINS`. Use the same generated value for `REDIS_PASSWORD` and the Redis DSN password. The Redis DSN uses `redis://` because the Compose Redis service is password-protected on a private Docker network but does not terminate TLS; use `rediss://` only when pointing at a Redis service configured for TLS.
- Deploy with `docker compose --env-file backend/.env.production -f docker-compose.yml -f docker-compose.production.yml up -d --build`. Compose interpolation uses `--env-file`; the service `env_file` alone does not supply `${...}` values used by Compose.
- Production publishes only the frontend on `127.0.0.1:8080` for a host TLS reverse proxy and does not publish the API, PostgreSQL, Redis, Prometheus, or Grafana ports. Configure the host proxy to terminate HTTPS and forward to `http://127.0.0.1:8080`, preserve the original `Host`, and set `X-Forwarded-Proto https`; do not expose port 8080 directly to the internet. Keep production secrets out of source control.
- Before upgrades, take a PostgreSQL backup. The Compose `migrate` service applies migrations before the API, worker, and scheduler start. Verify `https://<hostname>/api/v1/ready`, and inspect `docker compose ... ps` and logs before considering a release healthy.
- Deleting a link soft-deletes its record and releases its short code for reuse. Existing bookmarks and QR codes continue resolving by code, so they will point to a replacement link if that code is reused. Click history remains attached to the original link record; analytics identifies deleted history separately from an active replacement. If the alias has been reused, an administrator cannot restore the old link until the active replacement releases that alias.
- The app is designed to grow into a full enterprise SaaS rather than a simple link shortener.

## Final intent

LinkHub is not just a URL shortener; it is a secure multi-tenant link operations platform meant for business-grade workflows. The architecture is designed so that product complexity can scale without sacrificing maintainability or production readiness.
