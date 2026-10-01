import { FormEvent, useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { describeSharedLinkFailure } from "../access";

export function SharedLinkPage() {
  const { code: routeCode } = useParams();
  const location = useLocation();
  const code = routeCode ?? new URLSearchParams(location.search).get("link") ?? "";
  const navigate = useNavigate();
  const { tokens } = useSession();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const open = useCallback(
    async (event?: FormEvent, supplied?: string) => {
      event?.preventDefault();
      if (!code) return;
      setLoading(true);
      setError("");

      const secret = supplied ?? password;
      const query = secret
        ? `?${new URLSearchParams({ password: secret }).toString()}`
        : "";
      const headers: HeadersInit = tokens?.accessToken
        ? { Authorization: `Bearer ${tokens.accessToken}` }
        : {};
      const response = await fetch(
        `${apiBaseUrl}/urls/resolve/${encodeURIComponent(code)}${query}`,
        { headers },
      );

      if (response.ok) {
        const body = (await response.json()) as { original_url: string };
        window.location.assign(body.original_url);
        return;
      }

      const body = (await response.json().catch(() => ({}))) as {
        detail?: string;
        error?: { message?: string };
      };
      const detail = body.detail ?? body.error?.message ?? "";
      setError(describeSharedLinkFailure(response.status, detail).message);
      setLoading(false);
    },
    [code, password, tokens?.accessToken],
  );

  useEffect(() => {
    if (!password) void open(undefined, "");
  }, [open, password]);

  const requiresPassword = error.toLowerCase().includes("password");
  const requiresAuthentication =
    error.toLowerCase().includes("sign in") ||
    error.toLowerCase().includes("authentication");

  return (
    <main className="centered">
      <section className="card auth-card shared-link-page">
        <p className="eyebrow">LINKHUB SHARED LINK</p>
        <h1>Open shared link</h1>
        <p className="muted">
          Link code: <strong>{code}</strong>
        </p>
        {error && <p className="notice" role="alert">{error}</p>}
        {requiresAuthentication && (
          <button
            className="secondary"
            onClick={() =>
              navigate(`/auth?returnTo=/shared/${encodeURIComponent(code)}`)
            }
          >
            Sign in to retry
          </button>
        )}
        {requiresPassword && (
          <form onSubmit={(event) => void open(event, password)}>
            <label htmlFor="shared-link-password">Link password</label>
            <input
              id="shared-link-password"
              autoFocus
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
            <button disabled={loading} type="submit">
              {loading ? "Checking access…" : "Open with password"}
            </button>
          </form>
        )}
        {!requiresPassword && !requiresAuthentication && (
          <button onClick={() => void open(undefined, "")} disabled={loading}>
            {loading ? "Checking access…" : "Open shared link"}
          </button>
        )}
      </section>
    </main>
  );
}
