# LinkHub Project Guidelines

## Execution policy

- Treat every user request to continue or complete the project as an instruction to keep implementing, not as a request for a status report.
- A passing test suite, clean lint, successful build, Docker health, or a checkpoint is an intermediate milestone only. Never treat any one of these as project completion.
- Maintain a concrete requirements backlog from the project brief and audit it continuously. Work through the backlog in bounded slices, then immediately select and implement the next incomplete slice.
- Do not stop after reporting a completed slice. Continue until the user explicitly says to stop, pause, or switch tasks.
- Do not ask for confirmation between implementation slices when reasonable defaults and existing project patterns are sufficient.
- Do not create commits, push changes, or alter history unless the user explicitly requests it.
- If an external dependency blocks a slice, record the exact blocker, complete other independent slices, and return to the blocker when possible.
- Report progress only as an interim update while continuing implementation. A final response is allowed only after the current requirements backlog has been exhausted or a genuine external blocker prevents further work.

## Architecture

Preserve the existing Clean Architecture boundaries:

- `backend/app/presentation`: API routers, request validation, and response mapping.
- `backend/app/application`: use cases and business orchestration.
- `backend/app/infrastructure`: PostgreSQL, Redis, Celery, email, and repository implementations.
- `frontend/src`: typed React feature pages and shared API/session components.

Reuse existing repositories, services, DTOs, dependency injection, authorization helpers, and error conventions before adding new abstractions. Keep organization and user data tenant-isolated.

## Validation

For each implementation slice:

1. Add or update focused tests for the requested behavior.
2. Run the smallest relevant backend/frontend test and type/lint checks.
3. Continue to the next backlog item after validation succeeds.
4. Run the broader suites only after the implementation backlog is exhausted or when a change crosses subsystem boundaries.

Use the project commands documented in [README.md](../README.md). Do not use successful validation as a reason to stop.
