# LinkHub Project Handoff (for any AI/engineer)

## Project
Enterprise Link Management Platform (SaaS) using:
- FastAPI (Python 3.12)
- PostgreSQL + SQLAlchemy + Alembic
- Redis + Celery (scaffolded)
- JWT auth + refresh tokens + bcrypt

## Current Status
- Milestone 1: Project setup ✅
- Milestone 2: Authentication ✅
- Milestone 3: Organizations ✅
- Milestone 4: URL Management ✅ (core lifecycle and bulk APIs)
- Milestone 5: Redis cache + rate limiting foundation ✅
- Milestone 6: Analytics ingestion + aggregation ✅
- Milestone 7: Background workers and scheduled cleanup ✅
- Milestone 8: Monitoring, admin, deployment hardening, and scheduled notifications ✅
- Local Docker runtime: running successfully on the user's machine ✅
- Current work: post-login functional smoke testing

## Important Folders
- `backend/app/core` config, jwt, security, middleware, dependencies
- `backend/app/application/services` business services
- `backend/app/infrastructure/db/models` SQLAlchemy models
- `backend/app/infrastructure/repositories` repository layer
- `backend/app/presentation/api/v1/routers` API endpoints
- `backend/alembic/versions` migrations
- `backend/tests` unit/router tests

## How to Run
```bash
cd backend
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Compose

```bash
cd /home/mohan-siva-kumar/LinkHub
sudo docker compose up -d --build
```

Local URLs:

- Web application: `http://localhost:8080`
- API docs: `http://localhost:8000/docs`
- API liveness: `http://localhost:8000/api/v1/health`
- API readiness: `http://localhost:8000/api/v1/ready`
- Mailpit development inbox: `http://localhost:8025`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Docker notes:

- If Docker permission is denied, run `newgrp docker`, log out/in, or use `sudo docker compose`.
- The Compose stack uses Mailpit for local verification and reset emails; it does not send real external email.
- After source changes affecting containers, use `sudo docker compose build --no-cache <service>` followed by `sudo docker compose up -d`.
- Do not use `docker compose down -v` unless deleting local PostgreSQL data is intentional.

## API Surface Implemented So Far
- Auth: `/api/v1/auth/*`
- Organizations: `/api/v1/organizations/*`
- URLs: `/api/v1/urls/*`
  - includes `/api/v1/urls/resolve/{short_code}` cache-backed resolve
- Analytics: `/api/v1/analytics/*`
- Health: `/api/v1/health`
- Readiness: `/api/v1/ready`
- Admin: `/api/v1/admin/*`
- API keys: `/api/v1/api-keys`

## Validation
- Backend tests, Ruff, and Mypy pass locally.
- Frontend production build passes locally.
- Docker runtime validation requires a host with Docker installed.
- Private links require an authenticated member of the owning organization.
- Analytics click queries use composite organization/time and URL/time indexes.
- API-key usage counters use database-side atomic increments.
- Login and refresh-token rotation require active, verified accounts.
- Frontend Nginx proxies persistent avatar media through to the API service.
- Expiration notifications lock eligible URL rows to prevent duplicate sends from overlapping workers.
- Organization invite acceptance locks invite rows to enforce single-use behavior under concurrency.
- Compose enables Celery workers, scheduled jobs, and Redis rate limiting by default; local `.env.example` remains development-friendly.
- Mutation paths use database row locks for URL edits, API-key rotation, invite acceptance, and expiring-link notifications.
- Email sender configuration is resolved at send time so runtime settings are not frozen at module import.
- Redis cache payloads are schema-validated and safely fall back to PostgreSQL when corrupted.
- The Celery email task uses the direct SMTP sender, avoiding recursive task enqueueing.
- Mailpit is exposed on port 8025 for local email verification.
- SQLAlchemy organization-role enums persist their lowercase PostgreSQL values (`owner`, `admin`, `member`).
- Compose worker healthcheck no longer probes the API-only port, and Beat uses a writable `/tmp` pidfile.

## Current Smoke-Test Checklist

1. Register a user at `http://localhost:8080`.
2. Open `http://localhost:8025` and open the verification email.
3. Verify the email token, then log in.
4. Create an organization and confirm the owner role.
5. Create a normal public link and open its short URL.
6. Confirm the click appears in analytics.
7. Test one advanced control: custom alias, expiration, password protection, private access, or click limit.
8. Download a QR code and verify it resolves to the target URL.
9. Create, rotate, and revoke an API key.
10. Test profile update, avatar upload, and password change.
11. If an operation fails, capture the browser error and the relevant logs:

```bash
sudo docker compose logs --tail=200 api worker
sudo docker compose ps
```

## Resume Point

The implementation and automated validation are complete. The remaining activity is interactive acceptance testing of the running Compose stack. Recent runtime fixes include recursive Celery email delivery and organization-role enum serialization; both are fixed and validated with 49 passing backend tests and Ruff. Continue from the smoke-test checklist above.
