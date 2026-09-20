# LinkHub frontend

The frontend is a Vite/React application organized around an application
composition root (`src/App.tsx`), an explicit router and `AppShell`, shared
API/session/UI utilities, and feature-owned pages:

- `features/auth` and `features/shared-link` handle unauthenticated entry
- `features/links`, `organizations`, and `analytics` provide workspace flows
- `features/profile` and `settings` intentionally separate identity from
  password/session security
- `features/api-keys` and `admin` provide integration and platform operations

`features/workspace/WorkspaceApp` is limited to the authentication entry flow.
Feature pages own their state and API handlers, while
`shared/api/client.ts` owns bearer injection and refresh-token rotation, and
`shared/session` owns token persistence.

```bash
npm run build
npm test
```

Set `VITE_API_BASE_URL` to point at a non-default API when needed.
