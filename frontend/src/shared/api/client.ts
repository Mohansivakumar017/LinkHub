export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type SessionTokens = {
  accessToken: string;
  refreshToken: string;
};

export const sessionStorageKeys = {
  access: "linkhub_access_token",
  refresh: "linkhub_refresh_token",
} as const;

/**
 * One API boundary for all feature modules. It owns bearer injection and
 * refresh-token rotation while leaving response interpretation to features.
 */
export function createApiClient(onSessionRefresh?: (tokens: SessionTokens) => void) {
  let refreshPromise: Promise<SessionTokens | null> | null = null;

  async function refreshSession(refreshToken: string): Promise<SessionTokens | null> {
    if (!refreshPromise) {
      refreshPromise = fetch(`${apiBaseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
        .then(async (response) => {
          if (!response.ok) return null;
          const body = await response.json() as {
            access_token: string;
            refresh_token: string;
          };
          return {
            accessToken: body.access_token,
            refreshToken: body.refresh_token,
          };
        })
        .finally(() => {
          refreshPromise = null;
        });
    }
    return refreshPromise;
  }

  async function request(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const accessToken = localStorage.getItem(sessionStorageKeys.access);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

    let response = await fetch(input, { ...init, headers });
    if (response.status !== 401) return response;

    const refreshToken = localStorage.getItem(sessionStorageKeys.refresh);
    if (!refreshToken) return response;
    const tokens = await refreshSession(refreshToken);
    if (!tokens) return response;

    localStorage.setItem(sessionStorageKeys.access, tokens.accessToken);
    localStorage.setItem(sessionStorageKeys.refresh, tokens.refreshToken);
    onSessionRefresh?.(tokens);
    headers.set("Authorization", `Bearer ${tokens.accessToken}`);
    return fetch(input, { ...init, headers });
  }

  return { request };
}

export const publicApiBaseUrl = apiBaseUrl.replace(/\/api\/v1$/, "");
