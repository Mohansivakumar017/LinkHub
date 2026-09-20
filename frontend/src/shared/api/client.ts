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
  async function request(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const accessToken = localStorage.getItem(sessionStorageKeys.access);
    if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

    let response = await fetch(input, { ...init, headers });
    if (response.status !== 401) return response;

    const refreshToken = localStorage.getItem(sessionStorageKeys.refresh);
    if (!refreshToken) return response;
    const refreshed = await fetch(`${apiBaseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!refreshed.ok) return response;
    const tokens = await refreshed.json() as { access_token: string; refresh_token: string };
    localStorage.setItem(sessionStorageKeys.access, tokens.access_token);
    localStorage.setItem(sessionStorageKeys.refresh, tokens.refresh_token);
    onSessionRefresh?.({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
    headers.set("Authorization", `Bearer ${tokens.access_token}`);
    return fetch(input, { ...init, headers });
  }

  return { request };
}

export const publicApiBaseUrl = apiBaseUrl.replace(/\/api\/v1$/, "");
