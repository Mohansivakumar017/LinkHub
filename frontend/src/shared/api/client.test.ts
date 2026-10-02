import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApiClient, sessionStorageKeys } from "./client";

describe("API client refresh handling", () => {
  const originalFetch = globalThis.fetch;
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    globalThis.localStorage = {
      clear: () => storage.clear(),
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      key: (index: number) => [...storage.keys()][index] ?? null,
      get length() { return storage.size; },
    };
    localStorage.setItem(sessionStorageKeys.access, "expired-access");
    localStorage.setItem(sessionStorageKeys.refresh, "valid-refresh");
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("shares one refresh request across concurrent expired requests", async () => {
    let refreshCalls = 0;
    const refreshResolvers: Array<(response: Response) => void> = [];
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        return new Promise<Response>((resolve) => refreshResolvers.push(resolve));
      }
      if (init?.headers instanceof Headers && init.headers.get("Authorization") === "Bearer new-access") {
        return Promise.resolve(new Response("ok", { status: 200 }));
      }
      return Promise.resolve(new Response("expired", { status: 401 }));
    });
    globalThis.fetch = fetchMock;

    const client = createApiClient();
    const first = client.request("/protected");
    const second = client.request("/protected");
    await vi.waitFor(() => expect(refreshCalls).toBe(1));
    refreshResolvers[0](new Response(JSON.stringify({
      access_token: "new-access",
      refresh_token: "new-refresh",
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    await expect(Promise.all([first, second])).resolves.toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(localStorage.getItem(sessionStorageKeys.access)).toBe("new-access");
  });
});
