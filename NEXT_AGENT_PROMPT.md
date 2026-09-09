# Prompt for Next AI/Engineer

Use this as context when continuing LinkHub:

1. Read:
   - `PROJECT_HANDOFF.md`
   - `IMPLEMENTATION_LOG.md`
2. Validate baseline:
   ```bash
   cd backend
   source .venv/bin/activate
   pytest -q
   ```
3. Continue from Milestone 7:
   - Celery worker wiring for async tasks
   - move email and heavy analytics operations to background jobs
   - scheduled cleanup jobs (expired links, token cleanup)
4. Keep existing architecture patterns:
   - Router -> Service -> Repository -> Model
   - No business logic in router
   - Explicit exceptions and HTTP mapping
5. Add tests for every new behavior before marking done.
